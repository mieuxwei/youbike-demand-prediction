# YouBike 站點需求分析、短期可用車預測與靜態調度模擬

個人自主時間序列研究作品。研究與展示已完成，實作凍結。

文件更新日期：2026-09-27。此日期不代表重新訓練、重做評估或重算雲端累積資料量。

[開啟展示](https://youbike-demand-observatory.rwhqgqfdk2.chatgpt.site/#live) ·
[English README](../README.md) ·
[研究證據索引](README.md) ·
[重現方式](REPRODUCIBILITY.md)

## 專案介紹

YouBike 站點的「需求高」與「即將沒車」是不同問題。本專案分別研究歷史轉乘相關借車需求及短期站點庫存，再以固定假設比較搬運方案。三者共享交通研究主題，但資料、target、模型與評估範圍不同。

| 部分 | 問題與目標 | 完成內容 |
|---|---|---|
| Track A | 每站每小時的轉乘相關借車量 | 2023 全年資料、天氣、模型比較、滾動驗證、特徵消融、誤差分析與歷史回測展示 |
| Track B | 30／60 分鐘後的可用車數 | 雲端資料管線、固定 28 天研究、獨立七天驗證、固定 12 站即時觀測與預測展示 |
| Phase 3 | LSTM 是否優於同範圍的 HGB？ | 64 站固定資料比較；LSTM 未勝 HGB，不採用 |
| Phase 4 | 固定預測與資源假設下，搬運是否降低目標偏差？ | 不調度、greedy、MILP 比較與敏感度分析；靜態結果展示 |

Track A 的輸出不直接輸入 Track B 或調度。Phase 4 使用另外保存、依 validation 選定的回溯 HGB；即時 60 分鐘展示使用原 Stage 17 訓練、Stage 19 獨立驗證的 HGB。快照車數差異混合借還、人工調度及資料修正，不能視為實際借車量。

## 四項核心結論

1. Track A：HGB with weather 的 holdout MAE 為 **1.575**。範圍是 2023 年、訓練期選出的 100 站、74,282 筆十二月 station-hour rows。
2. Track B：獨立七天驗證中，30m 保留 persistence；60m HGB 的 MAE 比 persistence 低 **1.71%**，屬於小幅跨窗改善。
3. LSTM：共同 64 站／89,600 序列的回溯 MAE 為 3.326271，未超越對應 HGB 的 3.249886，因此不採用。
4. 靜態調度：基本情境的 MILP 與 greedy 全數同分；**16.65%** 是十二個情境的平均假設目標函數下降，不是實際營運收益。

原始數值：[Track A](../results/model_comparison_metrics.csv)、[Track B 獨立驗證](../results/track_b_independent_metrics.csv)、[LSTM 比較](../results/offline_research/comparison.csv)、[調度比較](../results/offline_research/optimization_comparison.csv)。不同資料範圍的分數不合併排名，R² 不換算成準確率。

## 展示怎麼看

### 即時觀測與未來估計

![固定 12 站展示中的第一站：目前車況、30m persistence、60m HGB 與時間資訊](assets/live-availability-20260927.png)

這是 2026-09-27 公開網站的真實截圖，顯示固定首站「捷運科技大樓站」；並非以成績挑站。快照起點為臺北時間 18:00:32，30m／60m 目標時間為 18:30:32／19:00:32。截圖是有日期的展示紀錄，不是現在的即時數字或模型評估。

`#live` 沿用 Phase 4 的完整 12 站：從訓練期 64 站中，取編號最小站與距離最近的十一站。每五分鐘蒐集、頁面每分鐘更新。顯示站名、可借車、可還空位、來源時間、排程時間、擷取開始／寫入完成時間與資料年齡。

30m persistence 假設目前車數保持不變，不是學習模型。60m 是已凍結的原 HGB。資料／來源超過十分鐘、來源時間異常、停用、站點不支援、歷史不足或推論失敗時，頁面顯示原因並停止不可靠的預測；連線失敗不以舊值冒充 live。

### 歷史回測與靜態模擬

`#forecast` 顯示十個代表性 2023 年十二月 holdout 時段，並非完整測試集，也不是目前站點庫存。

![第一個固定歷史決策情境的無調度、greedy 與 MILP 比較](assets/static-redistribution-20260927.png)

`#track-b` 保留 LSTM 比較及已記錄的調度結果。圖中是 2026-09-14 07:00 Asia/Taipei 的首個情境、基本 12 輛／30 bike-km 設定；不調度目標值為 76.877，greedy／MILP 均為 71.343。這是單一情境，不能套用全部情境的 16.65% 平均改善。

[完整展示說明](../dashboard/README.md) · [截圖來源](assets/README.md)

## Track A：歷史轉乘需求

### 資料與評估

- 官方 2023 年十二個月份轉乘相關旅次共 7,388,479 筆；不是全部 YouBike 旅次。
- 聚合為 4,670,320 筆有活動的 station-hour 資料，整合 8,760 小時天氣，匹配率 100%。
- 100 個高需求站只依 training period 選出。
- 1–9 月 training、10–11 月 validation、12 月 holdout；需求 lag／rolling 只使用過去。
- 天氣是 Open-Meteo 臺北單一參考點的歷史再分析值，不是預測當時已知的未來天氣。

### 方法與結果

比較前一小時、前一週同時段、Ridge、HGB 及 XGBoost。HGB with weather 的十二月 MAE 1.575、RMSE 2.549、R² 0.794；三段 rolling-origin MAE 為 1.636、1.592、1.606。XGBoost 沒有超越 HGB。

![十二月 holdout 模型比較](assets/track-a-model-comparison.svg)

原圖保留；所有模型使用相同 74,282 筆 holdout rows。[完整比較與設計](STAGE_13_TRACK_A_RESEARCH_SUMMARY.md)。

六組特徵消融顯示 calendar 最重要，移除後 test MAE 惡化 10.44%；weather 增益較小。政府機關放假日特徵在 validation 略改善、test 反而惡化，因此未加入主模型。尖峰、高需求站與高需求時段誤差仍大。這些關聯不是因果解釋。[消融與誤差分析](STAGE_12_FEATURE_ABLATION_ERROR_ANALYSIS.md)。

## Track B：短期可用車預測

### 固定資料研究與獨立驗證

| 項目 | 28 天研究 | 獨立七天驗證 |
|---|---|---|
| UTC 半開區間 | [2026-08-21 09:45:02, 2026-09-18 09:45:02) | [2026-09-18 18:30:00, 2026-09-25 18:30:00) |
| 原始 station rows | 14,490,149 | 3,636,105，不含前一小時暖身 |
| Snapshots | 8,058 | 2,016／2,016 |
| 觀測站點 | 1,803 | 1,807；有效評估站點 1,783 |
| 重複 station-time keys | 0 | 0 |
| 估計缺少五分鐘時槽 | 7 | 0 |
| 評估設計 | 18／5／5 日 chronological split；validation 選參數 | 原模型、特徵與事前 gates 固定，不重訓或調參 |

Target 是 desired future time 後 0–2 分鐘內第一筆有效 snapshot，current／future station 必須 active；跨 split 邊界的 target 會排除。HGB 使用 current bikes、return spaces、capacity、location、臺北日曆、15／30／60m backward lag 及 past-only rolling。原訓練用每第六個 snapshot 控制成本，validation／test 使用全部 eligible rows。

Persistence 定義固定為 `prediction(t+h) = available_bikes(t)`。獨立驗證於 2026-09-27 執行：

| Horizon | 共同有效 rows | Persistence MAE | HGB MAE | 決策 |
|---|---:|---:|---:|---|
| 30m | 3,567,488 | 1.950 | 1.981 | 保留 persistence |
| 60m | 3,556,778 | 2.862 | 2.813 | HGB MAE 改善 1.71% |

60m 在 1,048／1,783 站改善 MAE，通過事前規則；30m 僅 608 站改善。原 28 天 holdout 的方向一致：30m persistence／HGB MAE 2.043／2.057；60m 3.012／2.922。不同窗誤差變動不是模型持續學習，也未證明統計顯著或季節泛化。

[28 天資料與模型報告](STAGE_17_TRACK_B_28_DAY_REGRESSION.md) · [獨立驗證及來源新鮮度診斷](STAGE_19_TRACK_B_INDEPENDENT_VALIDATION.md)

### 早期資料檢查點

2026-08-28 的七天 preliminary baseline，以及固定 `[2026-08-21 09:45:02Z, 2026-09-04 09:45:02Z)` 的十四天 stability analysis，保留為有日期的歷史證據。十四天共 7,240,919 rows／4,031 snapshots／1,800 站；兩週 persistence MAE 為 30m 1.704／1.030、60m 2.544／1.564。定義並未改變，差異反映兩週資料情境變動，不代表模型進步。

[七天 baseline](STAGE_15_TRACK_B_PRELIMINARY_BASELINE.md) · [十四天穩定性](STAGE_16_TRACK_B_14_DAY_STABILITY.md)。以上均不是今日累積總量。

## Phase 3／4：LSTM 與靜態調度

補充研究重用已檢視的 28 天資料及 18／5／5 切分，不冒稱新獨立測試。64 站只按 training coverage 與固定排序選取；每筆序列是同站 13 步、約一小時。StandardScaler 只 fit training，future labels 不跨 split end。

LSTM 為單層 32 units、兩組固定 learning rates、三個固定 seeds。設定依三種子 validation 平均 MAE 選定，主要結果用三種子等權預測平均，不挑最好 test seed。另存的 HGB 接收相同 13×9 序列資訊。共同回溯範圍為 2026-09-13 09:45:02 至 09-18 09:45:02 UTC、89,600 序列；MAE 為 persistence 3.431339、HGB 3.249886、LSTM 3.326271。LSTM 不採用。

調度使用 validation 選出的回溯 HGB，不替換即時服務模型。12 站由 training 座標選定，12 個請求時間預先固定為 9/14–9/17 的臺北時間 07:00／12:00／17:00。SciPy/HiGHS MILP 求非負整數搬運量，與相同資訊、目標與限制下的 deterministic greedy／不調度比較。

- 守恆：沒有外部車源，調入／調出總量相等。
- 可行性：只能搬當下已有的車，限制當下與模擬未來容量、搬運總量及 bike-km。
- 假設：目標為容量 50%，立即搬運、座標大圓距離代理及合成成本；不是道路路線、業者成本或損失旅次。
- 基本設定：12 輛、30 bike-km。平均目標 92.1952 → 76.8478；greedy／MILP 在所有基本情境同分。
- 六組資源／成本設定、72 次 MILP、216 組方案與 144 筆敏感度紀錄完整保存，包括無效或變差情境。

[完整規約](OFFLINE_RESEARCH_PROTOCOL.md) · [方法、成本、結果與負面案例](PHASE_3_4_OFFLINE_RESEARCH.md) · [模型卡](TRACK_B_OFFLINE_MODEL_CARD.md)

## 技術架構與用途

| 層次 | 技術與實際用途 |
|---|---|
| 資料研究 | Python、pandas、NumPy：下載、清理、station-hour 聚合、時間對齊及 features；Jupyter／Matplotlib：研究與圖表 |
| 模型比較 | scikit-learn：Ridge／HGB；XGBoost：Track A challenger；PyTorch：LSTM 比較；joblib：可信來源模型保存 |
| 調度模擬 | SciPy／HiGHS MILP：整數搬運、容量、守恆及資源限制 |
| 雲端資料 | Cloudflare Worker、Cron、D1、SQL：五分鐘蒐集、validation、retry、logging 與主鍵去重 |
| 匯出 | Bearer token 保護 CSV、cursor pagination、六小時 bounded windows、有限 retry；本機 token 存 Keychain，不進 Git |
| 展示 | React 19、Vinext、TypeScript、Vite、Tailwind：歷史回測、即時預測及靜態模擬 |
| 驗證 | Python unittest、Node tests、feature schema、SHA-256 與固定 artifact manifests |

D1 的 `station_snapshots` 保存時間、station ID/name、bikes、return spaces、capacity、座標及 active flag；`PRIMARY KEY (station_id, snapshot_time)` 防止重複。`collection_runs` 保存成功／失敗、attempts、站數與錯誤。儲存 UTC；calendar 與畫面使用 Asia/Taipei。選擇 D1 是為了 station/time 查詢、targets 與訓練匯出，沒有額外使用 R2。

唯讀 `/demo/live` 最多私下讀取 12 站各 16 筆／65 分鐘歷史，只傳回最新摘要與預測。原 23-feature、120-tree HGB 轉成伺服端數值樹推論，不訓練新模型；72 組保存的歷史樣本、12 組實際雲端輸出與 Python 差異皆為 0。這是推論一致性，不是新成績。瀏覽器不取得匯出 token 或完整歷史。

正式 collector 在雲端，本機 `collect_youbike.py`／`collect_history.py` 是測試、除錯、fallback；電腦關機不會因此停止雲端排程。持續蒐集與已完成的研究版本分開，仍須管理服務可用性與儲存成本。

[雲端 schema 與部署](STAGE_11_TRACK_B_CLOUD_COLLECTION.md) · [服務規約](LIVE_DEMO_PROTOCOL.md) · [精確部署版本與驗收](LIVE_DEMO_DELIVERY.md)

## 原始階段與成果對照

| 原階段 | 對應成果 |
|---|---|
| Phase 1 — Data Analysis | 官方歷史／即時資料、清理、天氣、EDA、時間序列特徵與 audit |
| Phase 2 — Machine Learning | Track A 基準／Ridge／HGB／XGBoost、完整分析；Track B persistence／HGB 及獨立驗證 |
| Phase 3 — Deep Learning | 60m 共同範圍 LSTM 比較；未勝 HGB，不採用 |
| Phase 4 — Optimization | 靜態 MILP／greedy／不調度與限制、敏感度驗證 |
| Phase 5 — Visualization | React/Vinext 歷史回測、已記錄的研究面板及固定 12 站公開即時展示 |

研究凍結版與公開展示版的部署差異、實際驗收及限制保留於原始紀錄；本輪只有文件與展示素材整理。[文件版本與完整性](DOCUMENTATION_REVISION.md)。

## 本機啟動與重現

只看展示不需要訓練、資料匯出或憑證：

```bash
cd dashboard
pnpm install --frozen-lockfile
pnpm run dev
```

完整操作集中在 [重現 guide](REPRODUCIBILITY.md)：保留歷史資料下載、天氣、特徵、訓練、CSV 授權匯出與隔離重現的原參數。重新研究需用隔離目錄，避免覆寫凍結成果。

文件完整性檢查：

```bash
python3 scripts/verify_publication.py
python3 -m unittest tests.test_publication_integrity -v
```

2026-09-27 展示交付曾執行 Python 80、Worker 18、Dashboard 4 tests、build、改動元件 strict TypeScript、公開存取、桌面／手機 viewport 及故障情境檢查。實體手機、Safari private、全專案 lint 未宣稱通過；本輪文件整理沒有重新執行研究或以舊測試冒充新驗收。

## 限制與資料權利

- Track A 只涵蓋 2023 年定義內轉乘旅次、100 站及單點再分析天氣，不能外推全部旅次或其他年度。
- Track B 的固定四週與獨立七天，仍不足以代表季節、特殊事件或全部站點；來源更新可能落後排程時間。
- Persistence 不是學習模型；60m HGB 改善幅度小，不保證到站有車。
- LSTM 比較是回溯研究；靜態調度沒有介入後真實反事實，也沒有證明營運收益。
- 本版不含缺車／滿站風險分類、校準風險機率、真實車隊路線或營運系統。

原始程式與文件採 [MIT](../LICENSE)，上游資料仍依各自授權：[政府轉乘資料](https://data.gov.tw/dataset/169174)、[臺北即時資料](https://data.taipei/dataset/detail?id=c6bc8aed-557d-41d5-bfb1-8da24f78f2fb)、[Open-Meteo 歷史天氣](https://open-meteo.com/en/docs/historical-weather-api)。大型 raw／processed data 不提交 Git；模型重現需要正確版本與獲授權的 archived export。截圖保留真實時間及模擬性質，不作為新的評估證據。
