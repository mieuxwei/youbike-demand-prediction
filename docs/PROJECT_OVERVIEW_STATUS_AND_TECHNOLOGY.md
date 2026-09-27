# YouBike 站點需求分析、短期可用車預測與調度模擬

## 專案介紹、技術架構與目前狀態

- **文件更新日期：** 2026-09-27
- **作品性質：** Independent Time-Series Research Project · 研究與展示交付完成，實作 frozen
- **專案狀態：** 原本機研究版已驗證並保存於 `159f059`；v7 live 實作已於 `f3e27e0` 提交並推送，不重訓或重寫成績。固定 12 站目前觀測、30m persistence、原 Stage 17／19 的 60m HGB 已公開部署並通過必要驗收；不是正式營運服務。實際版本、匿名存取與再次 freeze 見 [v7 交付紀錄](LIVE_DEMO_DELIVERY.md)
- **Repository：** `youbike-demand-prediction`
- **公開展示：** [開啟即時車況、歷史需求及調度模擬](https://youbike-demand-observatory.rwhqgqfdk2.chatgpt.site/#live)；Sites version 3，免登入。匿名 HTTP 200 與部署後桌面／手機 viewport 已驗證；不是實體手機或全瀏覽器認證。

---

## 1. 專案摘要

本專案研究如何利用 YouBike 歷史旅次、站點庫存、時間序列特徵與天氣資訊，建立可重現的需求與可用車預測比較，並完成有限資源下的靜態車輛調度模擬。2026-09-27 依使用者決策停止等待新資料，以既有固定資料補完原始 Phase 3／4，驗收後結束本版開發。

專案分成兩條研究問題不同、不可混用 target 的主線：

| 研究線 | 研究問題 | Target | 目前狀態 |
|---|---|---|---|
| Track A：歷史轉乘需求 | 預測某站在指定小時的轉乘相關借車量 | 每站每小時轉乘相關借車量 | 主要研究、模型評估、error analysis 與歷史 Dashboard 已完成 |
| Track B：即時可用車 | 預測某站 30／60 分鐘後的可借車數 | Future available bikes | 28 天研究與獨立七天驗證完成；30m 保留 persistence，60m HGB 跨兩窗小幅改善 |

Track A 的「歷史借車需求」不等於 Track B 的「未來剩餘車輛」。Track A 預測不直接輸入 Track B 或調度；Phase 4 使用另存的回溯 HGB 與固定假設。三者同一研究主題、不同資料／target／模型。庫存差值不是實際借車量，也不能直接把 Track A demand 解讀成 shortage 或補車數量。

---

## 2. 研究動機與預期應用

YouBike 站點的借還需求會受到時段、平假日、地點、歷史使用情形與天氣影響。當某站可借車數過低，使用者可能無車可借；當可還車位不足，也可能無法還車。

本專案分階段處理以下問題：

1. 建立可靠、可重現的資料蒐集與清理流程。
2. 預測歷史轉乘相關的小時借車需求。
3. 蒐集連續即時站點快照，建立 30／60 分鐘可用車預測。
4. 使用既有資料完成 60m LSTM／HGB／persistence 公平比較。
5. 使用 validation 選定預測器，在明確研究假設下比較不調度、簡單規則與 MILP。

可能的未來應用包括：

- 站點短期可用車預測。
- 缺車與滿站風險提示。
- 尖峰時段與高誤差站點分析。
- 調度人員的決策輔助。
- 歷史需求與模型研究的互動式展示。

已執行離線整數調度模擬；未宣稱完成即時 shortage prediction、真實車隊調度或營運效益驗證。上述可能應用不是本版自動續做的工作。

---

## 3. 整體系統架構

```text
Track A：歷史研究

官方 2023 轉乘旅次資料 + Open-Meteo 歷史天氣
                ↓
下載、清理、站點名稱正規化、station-hour 聚合
                ↓
時間／lag／rolling／天氣特徵
                ↓
Naive → Ridge → HGB → XGBoost
                ↓
時間切分、rolling-origin、ablation、error analysis
                ↓
React 19 + Vinext 歷史回測 Dashboard


Track B：即時研究

臺北市 YouBike 即時 API
                ↓
Cloudflare Worker validation + retry
                ↓
Cron Trigger：每 5 分鐘
                ↓
Cloudflare D1
  ├─ station_snapshots
  └─ collection_runs
                ↓
Bearer-token protected CSV export
                ↓
Python gap／duplicate／target coverage audit
                ↓
30／60 分鐘 persistence baseline
                ↓
十四天 stability analysis（歷史檢查點）
                ↓
二十八天 audit + learned regression（已完成第一版）
                ↓
七天獨立時間窗驗證（9/27 已按凍結規則執行）
                ↓
保留原事前規則與歷史結論

既有固定 28 天資料（另開補充回溯研究，不冒稱獨立驗證）
                ↓
共同 64 站／60m：Persistence、HGB、LSTM 比較
                ↓
validation 選定 HGB → 靜態整數調度與敏感度模擬
                ↓
React/Vinext 固定研究面板（保留）

v7 展示工程（不重開研究）
既有 D1 → 固定 12 站唯讀端點 → Worker 原 Stage 17 HGB / persistence
                ↓
React/Vinext 即時展示：目前觀測／未來估計，與歷史研究／模擬分開
                ↓
公開存取與實際部署驗收 → 再次 freeze
```

本機 `collect_youbike.py` 與 `collect_history.py` 保留為測試、除錯及備援工具；正式長期蒐集由 Cloudflare 執行，因此使用者電腦關機後仍能持續收集。

---

## 4. 資料來源與資料規模

### 4.1 Track A：歷史轉乘需求

| 項目 | 已驗證結果 |
|---|---:|
| 期間 | 2023-01-01 至 2023-12-31 |
| 官方月份 | 12 個月 |
| 轉乘相關旅次 | 7,388,479 筆 |
| 有活動的 station-hour rows | 4,670,320 筆 |
| 小時天氣 | 8,760 小時 |
| Demand-weather match | 100% |
| 模型站點 | Training period 選出的 100 個高需求站點 |

注意事項：

- 資料只包含與公車／捷運轉乘相關的 YouBike 旅次，不代表全部 YouBike 使用。
- Open-Meteo 資料是臺北單一參考點的歷史再分析值，不是每站現地觀測。
- 真正的未來線上預測不能使用事後觀測天氣，必須改用預測當下可取得的 weather forecast。

### 4.2 Track B：即時站點快照

固定二十八天分析結果：

| 項目 | 結果 |
|---|---:|
| 分析期間 | `[2026-08-21 09:45:02 UTC, 2026-09-18 09:45:02 UTC)` |
| Export rows | 14,490,149 |
| Snapshots | 8,058 |
| Distinct stations | 1,803 |
| Duplicate station-time rows | 0 |
| 估計缺少的五分鐘時槽 | 7 |
| 30m target coverage | 97.971% |
| 60m target coverage | 97.750% |
| 30m persistence／HGB test MAE | 2.043／2.057 |
| 60m persistence／HGB test MAE | 3.012／2.922 |

v6 當時的雲端累積量查核（與固定分析期間不同，保留歷史紀錄）：

| 項目 | 最新狀態 |
|---|---:|
| 查核日期 | 2026-09-27 |
| 最新 snapshot | 2026-09-27 01:00:28 Asia/Taipei |
| 累積 snapshots | 10,450 |
| 累積 station rows | 18,805,167 |
| 最新一輪 station count | 1,807 |
| 最新一輪狀態 | success，1 attempt，01:00:48 完成 |
| Collector 執行位置 | Cloudflare 雲端 |

上述數字是 v6 當時有日期的查核紀錄，不是今日持續刷新的總量，也不代表已逐輪核對所有歷史執行。v7 已部署 Worker 唯讀展示與原模型推論，排程、schema 與原固定資料／模型結果不變；本輪最新有時間戳的端點查核與部署版本見 [v7 交付紀錄](LIVE_DEMO_DELIVERY.md)，未重新計算整份 live dataset 的累積總量。

### 4.3 Track B：獨立七天驗證（2026-09-27 完成）

評估期間為 `[2026-09-18 18:30 UTC, 2026-09-25 18:30 UTC)`，即臺北時間 9/19 02:30 至 9/26 02:30（不含終點）。9/19 01:30 起的前一小時只供歷史特徵暖身。模型、特徵、時間窗與決策規則均沿用 9/19 在評估開始前 commit 的版本；沒有重訓或調參。

| 項目 | 結果 |
|---|---:|
| 含暖身完整匯出 | 3,657,741 rows、2,028 snapshots |
| 七天評估原始資料 | 3,636,105 rows、2,016 snapshots、1,807 stations |
| 預期時槽涵蓋率 | 100%（2,016／2,016） |
| 重複鍵／估計缺少時槽 | 0／0 |
| 實際納入模型評估站點 | 1,783 |
| 30m 有效 rows／active-row coverage | 3,567,488／99.696% |
| 60m 有效 rows／active-row coverage | 3,556,778／99.397% |

| Horizon | Persistence MAE | HGB MAE | Persistence RMSE | HGB RMSE | 結論 |
|---|---:|---:|---:|---:|---|
| 30m | **1.950** | 1.981 | 3.455 | **3.253** | HGB MAE 較差 1.56%，保留 persistence |
| 60m | 2.862 | **2.813** | 4.833 | **4.389** | HGB MAE 改善 1.71%，通過全部 independent gates |

資料門檻兩者皆過。30m／60m 分別有 34.10%／58.78% 站點 MAE 改善，只有 60m 通過至少 50% 站點改善的規則。結合 Stage 17，研究結論固定為 **30m persistence、60m HGB 小幅跨窗改善**，不是模型持續自動學習、統計顯著性或 production-ready 證明。

來源：[Stage 19 完整報告](STAGE_19_TRACK_B_INDEPENDENT_VALIDATION.md)、[metrics](../results/track_b_independent_metrics.csv)、[coverage／decision](../results/track_b_independent_summary.json)、[輸入 hash 與環境紀錄](../results/track_b_independent_provenance.json)。時槽完整不代表來源永遠新鮮：4 份 snapshot 的官方更新落後排程超過五分鐘，最長 18.2 分鐘；此診斷未用來事後改動篩選規則。

快照間的可用車變化可能同時包含租借、還車、人工調度與資料修正，不能直接稱為實際租借需求。

---

## 5. Track A 模型與研究成果

### 5.1 時間切分

- Training：2023 年 1–9 月。
- Validation：2023 年 10–11 月。
- Holdout test：2023 年 12 月。
- Station selection 只使用 training period activity。
- 不使用 random split 作為主要時間序列評估。

### 5.2 Holdout 模型結果

| Model | MAE | RMSE | R² |
|---|---:|---:|---:|
| Previous hour | 2.441 | 4.129 | 0.460 |
| Previous week, same hour | 2.176 | 3.701 | 0.566 |
| Ridge without weather | 1.810 | 2.911 | 0.731 |
| Ridge with weather | 1.793 | 2.889 | 0.736 |
| HGB without weather | 1.601 | 2.567 | 0.791 |
| **HGB with weather** | **1.575** | **2.549** | **0.794** |
| XGBoost with weather | 1.597 | 2.580 | 0.789 |

HGB with weather 是目前 Track A 的主要模型。上述 holdout 指標皆來自 2023 年 12 月、training-defined top-100 stations 的 74,282 station-hour rows，只適用 hourly transfer-related borrowing demand，不能當作 Track B availability metrics。

### 5.3 已完成的研究分析

- Previous-hour 與 previous-week same-hour baselines。
- Ridge、Histogram Gradient Boosting、XGBoost 公平比較。
- 三段 expanding-window rolling-origin validation。
- Permutation importance。
- 六組 feature-group ablation。
- Official government day-off 增量實驗。
- Station、hour、weekday、尖離峰、需求層級、天氣、日別及 worst-case error analysis。
- 單一小時 prediction interface 與模型 SHA-256 integrity check。
- React／Vinext Interactive Historical Prediction Dashboard。

重要研究發現包括：

- Calendar feature group 對 HGB 最重要；移除後 test MAE 惡化 10.44%。
- Evening peak、morning peak 與高需求站點較難預測。
- Official day-off flag 在 validation 略改善、test 反而惡化，因此沒有加入主模型。
- XGBoost 已完成公平比較，但未超越 HGB。

---

## 6. Track B 已完成檢查點

### 6.1 Target

- `target_available_bikes_30m`
- `target_available_bikes_60m`

Future target 只用於 label，不可進入 predictor matrix。Target alignment 允許 desired future time 後 0–2 分鐘內的第一份有效 snapshot，current 與 future station 都必須為 active。

### 6.2 Persistence baseline

定義：

```text
prediction(t + horizon) = available_bikes(t)
```

這不是 learned model，而是後續模型必須超越的必要基準。

### 6.3 七天 preliminary baseline（歷史證據）

| Split | Snapshots | Rows | 用途 |
|---|---:|---:|---|
| Train | 1,440 | 2,583,360 | 約五天，保留給未來模型訓練 |
| Validation | 288 | 516,672 | 一天，供模型與設定選擇 |
| Test | 356 | 639,757 | 約 1.23 天，最終 preliminary evaluation |

跨越 validation／test 邊界的 future label 會被 purge，避免資料洩漏。

七天資料曾使用五天 train block、一天 validation 與其餘 test，並 purge 跨界 future labels。這是 2026-08-28 的 preliminary checkpoint，不是目前資料總量。

### 6.4 七天 preliminary 結果

| Horizon | Split | MAE | RMSE | R² |
|---|---|---:|---:|---:|
| 30m | Validation | 2.035 | 3.523 | 0.865 |
| 30m | Test | **2.154** | **3.626** | **0.852** |
| 60m | Validation | 2.947 | 4.856 | 0.744 |
| 60m | Test | **3.140** | **5.064** | **0.712** |

30 分鐘比 60 分鐘容易，反映短期庫存具有較強狀態延續性。高 R² 主要代表 availability 的短期自相關，不代表已完成缺車預警或營運改善。

### 6.5 固定十四天 stability analysis（歷史檢查點）

固定期間為 `[2026-08-21 09:45:02 UTC, 2026-09-04 09:45:02 UTC)`。7,240,919 station rows 包含 4,031 snapshots、1,800 stations、0 duplicate station-time keys，估計缺少一個五分鐘時槽。

| Horizon | Week 1 MAE | Week 2 MAE |
|---|---:|---:|
| 30m | 1.704 | 1.030 |
| 60m | 2.544 | 1.564 |

Week 2 誤差較低不代表模型變好：persistence 定義在兩週完全相同，也沒有 fitting。差異表示 station-state dynamics 會跨週變動。

### 6.6 固定二十八天第一版 learned regression（Stage 17 歷史檢查點）

固定期間為 `[2026-08-21 09:45:02 UTC, 2026-09-18 09:45:02 UTC)`，共 14,490,149 rows、8,058 snapshots、1,803 stations、0 duplicates 與 7 個 isolated missing slots。使用 18 日 train／5 日 validation／5 日 test；所有 future targets 必須留在自己的 split。

| Horizon | Model | Test rows | MAE | RMSE | R² |
|---:|---|---:|---:|---:|---:|
| 30m | Persistence | 2,518,633 | **2.043** | 3.702 | 0.846 |
| 30m | HGB | 2,518,633 | 2.057 | **3.454** | **0.866** |
| 60m | Persistence | 2,507,965 | 3.012 | 5.190 | 0.697 |
| 60m | HGB | 2,507,965 | **2.922** | **4.645** | **0.757** |

30m HGB 雖降低 RMSE，但 MAE 比 persistence 差 0.68%；60m HGB 的 MAE 改善 2.98%、RMSE 改善 10.51%。這是第一版固定 holdout 證據，不是 shortage classification 或 production-ready live prediction。

---

## 7. 專案使用的技術

### 7.1 Python 資料與研究工具

| 技術 | 在本專案的用途 |
|---|---|
| Python | 資料下載、清理、特徵工程、模型訓練、推論、audit 與匯出工具 |
| pandas | 表格資料處理、時間對齊、groupby、station-hour aggregation |
| NumPy | 數值運算、cyclical features、metrics 計算 |
| Matplotlib | EDA 與研究圖表 |
| Jupyter Notebook | 分階段研究、分析過程與實驗紀錄 |
| Requests | 官方 API、天氣 API 與受保護 CSV endpoint 存取 |
| Joblib | scikit-learn 模型 artifact 儲存與讀取 |

### 7.2 時間序列與特徵工程

- Hour、weekday、month、weekend、rush-hour features。
- Hour／weekday sine-cosine cyclical encoding。
- 15／30／60 分鐘 past-only lag features。
- 30／60 分鐘 past-only rolling features。
- Previous-hour 與 previous-week same-hour demand history。
- 30／60 分鐘 future target alignment。
- Asia/Taipei 與 UTC 的明確轉換策略。
- Chronological split、boundary purge 與 leakage prevention。

所有 lag／rolling predictor 只能向過去取值，future target 絕不能成為 predictor。

### 7.3 Machine Learning

| 技術 | 用途／狀態 |
|---|---|
| Naive persistence | 建立最低比較基準 |
| Previous-week baseline | 比較週期性需求基準 |
| Ridge Regression | 線性、可解釋的需求預測 baseline |
| Histogram Gradient Boosting | Track A 目前最佳的非線性樹模型 |
| XGBoost 2.1.4 | 與 HGB 在相同 scope 下公平比較 |
| Permutation importance | 解釋模型對特徵的依賴 |
| Feature-group ablation | 驗證 station、calendar、history、weather 等資訊群的增量價值 |
| Rolling-origin validation | 檢查模型跨時間區段穩定性 |

LSTM 已完成固定兩設定、三種子比較，未超越同範圍 HGB，不採用；不追加 Random Forest／GRU 或模型搜尋。

### 7.4 Cloud 與即時資料基礎設施

| 技術 | 用途 |
|---|---|
| Cloudflare Worker | 抓取 YouBike API、驗證／retry／D1、health／protected export；v7 新增固定 12 站唯讀 live summaries 與原 HGB 伺服端推論 |
| Cron Trigger | `*/5 * * * *`，每五分鐘在雲端執行 |
| Cloudflare D1 | 保存結構化 station-time series 與 collection logs |
| Wrangler | Worker、D1 migration、secret 與部署管理 |
| SQL／SQLite schema | 主鍵去重、時間索引、範圍查詢與 audit |
| Bearer token | 保護 `/export.csv`，避免公開下載完整 live dataset |
| macOS Keychain | 本機安全保存 matching export token，不放入 Git |

D1 的核心資料表：

- `station_snapshots`：每站每次 snapshot 的 bikes、return spaces、capacity、座標、active flag 與時間。
- `collection_runs`：每輪排程的成功／失敗、attempts、station count、inserted count 與錯誤資訊。

`PRIMARY KEY (station_id, snapshot_time)` 保證同一站點、同一 snapshot 不重複寫入。

### 7.5 Export 可靠性與安全

七天真實匯出測試曾發現 deep cursor 造成 D1 HTTP 500，因此完成以下修正：

- 六小時 bounded export windows。
- 每個 window 重設 cursor。
- Network、HTTP 429、5xx 的有限 exponential-backoff retry。
- Authentication 401 不重試。
- CSV header 只寫一次。
- 先寫 `.tmp`，成功後才原子替換正式檔案。
- Token 不接受 command-line argument，避免留在 shell history。

### 7.6 Web Dashboard

| 技術 | 用途 |
|---|---|
| React 19 | Dashboard component 與互動狀態 |
| Vinext | React／Next-compatible 應用框架與 Cloudflare runtime 整合 |
| TypeScript | 前端型別安全 |
| Vite | 開發與 production build |
| Tailwind CSS 4 | Dashboard 樣式系統 |
| Cloudflare Vite Plugin／Wrangler | Cloudflare build 與部署 |
| Drizzle ORM | 專案內資料庫 schema／integration tooling |

Dashboard 沿用 React/Vinext，保留 2023 年 12 月 holdout 與固定 Phase 3／4；v7 新增即時區，不是 shortage dashboard。完整 12 站沿用訓練期座標選擇、不挑成績。30m 為車數保持不變的基準，60m 是原 Stage 17 HGB；23 特徵與 Python 經 72 個保存樣本完全一致。樹結構只在 Worker，不把 token／歷史送到瀏覽器。每分鐘更新、顯示來源／排程／擷取時間與資料年齡；過舊、缺歷史或錯誤停止預測。實際部署與驗收見 [交付紀錄](LIVE_DEMO_DELIVERY.md)。

### 7.7 測試與可重現性

- Python `unittest`：資料清理、下載、features、模型、prediction、Track A analysis、Track B export／audit／baseline。
- Node test runner：Worker transformation、validation、timestamp、retry、logging 與 export range。
- 固定 config、model metadata 與 SHA-256 artifact validation。
- 大型 raw／processed dataset 不放入 Git；Git 保存 source、schema、config、tests、metrics 與文件。
- 歷史 Stage 17 驗證：Python 66 tests、collector 9 tests；v6 為 Python 80、collector 11、Dashboard 2。v7 已通過 Python 80、collector／live server 18、Dashboard 4 tests、production build 與改動元件 strict TypeScript。72 組歷史樣本以及 12 組真實雲端輸出與原 Python 模型差異皆為 0，這是推論一致性，不是新研究成績。公開頁及本機故障測試、未驗證項目見 [v7 交付紀錄](LIVE_DEMO_DELIVERY.md)；[v6 紀錄](RESEARCH_FREEZE.md) 保留當時證據。

---

## 8. Repository 主要結構

```text
youbike-demand-prediction/
├── cloudflare/track-b-collector/  # Track B Worker、Cron、D1、migration、tests
├── config/                        # 資料來源與可重現設定
├── dashboard/                     # React/Vinext 歷史、live 與固定模擬展示
├── data/                          # raw／processed data（大型資料由 Git ignore）
├── docs/                          # Stage、model card 與研究文件
├── models/                        # Ridge、HGB、XGBoost artifacts
├── notebooks/                     # 01–09 executed research notebooks
├── results/                       # Metrics、audit、error analysis、comparison tables
├── src/                           # 資料、features、模型、prediction、export、audit
├── tests/                         # Python automated tests
├── PROJECT_PLAN.md                # Current-state plan
├── HANDOFF.md                     # 交接與各 Stage 狀態
└── README.md                      # 專案使用與重現方式
```

---

## 9. 目前完成度

| 項目 | 狀態 |
|---|---|
| 2023 全年歷史資料與天氣 | 已完成 |
| Track A Naive／Ridge／HGB／XGBoost | 已完成 |
| Rolling-origin validation | 已完成 |
| Feature ablation 與完整 error analysis | 已完成 |
| Historical prediction interface | 已完成 |
| React／Vinext Historical Dashboard | 已完成並部署 |
| Track B Worker + Cron + D1 | 已完成並持續運作 |
| Track B protected CSV export | 已完成並通過 1,449 萬 rows 固定分析 |
| Track B 七天 station-row audit | 已完成 |
| Track B 30／60m persistence baseline | 已完成 |
| Track B 十四天平假日／穩定性分析 | 已完成 |
| Track B 28 天 learned regression | 已完成第一版；30m 未超越 persistence，60m 小幅改善 |
| Track B 獨立七天驗證 | 已完成；30m 保留 persistence，60m 通過事前門檻，研究結論已固定 |
| v7 公開 live 研究展示 | 固定 12 站目前觀測、30m persistence 與原 60m HGB 已部署；資料不合格即停止預測，非營運保證 |
| Shortage／full-station classification | 本版不含；label／threshold 未定義，不列為自動續做事項 |
| Optimization | 靜態 MILP 模擬已執行，216 組方案通過限制檢查；非營運系統 |
| Deep Learning | 60m 單層 LSTM、兩設定、三種子比較已執行；未超越 HGB，不採用 |

---

## 10. 已知限制

1. Track A 只涵蓋 2023 年轉乘相關旅次，不是全部 YouBike 旅次。
2. Track A 模型只評估 training-defined top-100 stations。
3. Track A 尚未完成跨年度驗證。
4. 歷史天氣是單一臺北參考點的事後再分析資料。
5. Track B 二十八天研究加上獨立七天驗證，仍無法代表季節、特殊事件與長期站點變化；也沒有進行時間相依性下的顯著性檢定。
6. Persistence baseline 不是 trained AI model。
7. 快照車數差異不是純租借事件。
8. Shortage／full-station label 與 threshold 尚未完成研究定義。
9. 只有明確標示的 live 區提供 12 站短期可用車估計；歷史 A 面板與 Phase 3／4 仍是固定研究，不可混稱即時。Live 不保證到站有車，且資料失效時刻意停止預測。
10. Optimization 採用半容量目標、立即調度、座標距離代理與合成成本；假設容量減當下車數皆可接收，未完整建模不可用車柱。缺乏真實車隊、人力、道路、成本與行為回饋，不能宣稱營運效益。
11. 排程時間並非每筆實際擷取完成時間；官方 feed 偶有延遲。模型結果針對記錄的 feed，不是保證在精確實體時間觀測的庫存。

---

## 11. 已執行里程碑與結案範圍

### 2026-09-04 17:45：固定十四天門檻（已完成）

- 已完成 7,240,919 rows 授權匯出與 cloud health／gap audit。
- 已檢查 duplicate、station coverage 與 30／60m target coverage。
- 已比較 weekday／weekend availability 分布與兩週 persistence stability。
- Collector 持續執行，沒有因分析停止或重新啟動。

### 2026-09-18 17:45:02 Asia/Taipei 之後：固定二十八天檢查（已完成）

- 固定二十八天資料已完成 coverage、缺值、重複及站點變化 audit。
- 第一版 HGB 使用 current bikes、capacity、location、calendar、past-only lag／rolling features。
- 18／5／5 日 chronological train／validation／test split 已固定。
- 只用 validation 做模型選擇，並在相同 test scope 與 persistence 比較。
- Station 與 hour error analysis 已輸出；後續不得用 test 反覆調參。

日期到達不等於資料通過，也不等於模型完成。

### 2026-09-27：獨立七天驗證（已完成，保留原結論）

- 保留 Stage 17 模型與 metrics，按 Stage 19 的事前規則完成獨立驗證。
- 30m 保留 persistence；60m HGB 於兩窗都有小幅改善，但不宣稱適用所有站點或長期季節。
- Stage 19 規則、模型與原結論固定，不重寫歷史。
- 隨後的補充回溯研究明確揭露既有資料已看過，不冒稱新獨立驗證，不於回溯評估後再調參。

### 2026-09-27：Phase 3／4 固定資料研究

- 重用 28 天資料及原 18／5／5 切分；訓練期選出 64 站，13 步約一小時歷史。訓練 54,656、validation 86,912、共同回溯評估 89,600 序列。
- 回溯 MAE：persistence 3.431339、同序列 HGB 3.249886、LSTM 三種子平均預測 3.326271。HGB 是看回溯結果前依 validation 選定；LSTM 不採用。
- PyTorch：單層 32 units、兩 learning rates、三固定 seeds；scikit-learn：另存的同範圍 HGB；SciPy/HiGHS：真正整數規劃。
- 12 站 × 12 預定決策情境；基本資源 12 輛／30 bike-km。平均目標值不調度 92.1952、greedy 與 MILP 都是 76.8478；基本案例全數同分，不宣稱 MILP 全面較好。
- 資源為零或高成本時不調度；所有 216 組方案通過整數、守恆、容量與資源驗證。敏感度與分站／分時誤差皆保留。
- 完整方法、種子、成本及限制：[Phase 3–4 報告](PHASE_3_4_OFFLINE_RESEARCH.md)、[model card](TRACK_B_OFFLINE_MODEL_CARD.md)。

### 本版停止規則

v6 本機 freeze 保留於 [原紀錄](RESEARCH_FREEZE.md)，v7 只重開展示工程、版本保存與公開部署，必要驗收現已完成並再次標記「研究與展示交付完成，實作 frozen」。匿名存取、桌面／手機 viewport、正常預測與故障狀態均已驗證；實體手機、Safari private 與全專案 lint 沒有宣稱通過。不新增模型、資料窗、功能、提醒或自動續做。既有 collector 繼續運作，但不代表研究仍未完成；token、schema、排程不變。實際版本與限制以 [v7 紀錄](LIVE_DEMO_DELIVERY.md) 為準。

---

## 12. 專案結論

目前專案已完成一條完整、可重現的 Track A 歷史需求研究鏈，包含全年資料、天氣整合、baselines、HGB／XGBoost、rolling-origin validation、ablation、error analysis、prediction interface 與 Web Dashboard。

Track B 已完成雲端資料系統、28 天研究、原獨立七天驗證，並依新範圍完成固定資料 LSTM 比較及靜態整數調度模擬。原 30m persistence／60m HGB 小幅跨窗改善結論不變。新增比較不支持採用 LSTM；最佳化完成不代表超越所有簡單規則或證明真實營運效益。Shortage classifier、production live serving、多車路線不在本版範圍。

此專案目前最重要的價值不只是單一模型分數，而是建立了清楚分離研究問題、避免時間洩漏、可持續蒐集、可重現評估且能誠實表達成果邊界的完整研究與工程流程。

---

## 13. 延伸文件

- [GitHub project page](../README.md)
- [Reproducibility guide](REPRODUCIBILITY.md)
- [Historical Dashboard／歷史回測展示](../dashboard/README.md)
- [Current-state project plan](../PROJECT_PLAN.md)
- [Stage 16 Track B fourteen-day stability analysis](STAGE_16_TRACK_B_14_DAY_STABILITY.md)
- [Stage 17 Track B 28-day audit and learned regression](STAGE_17_TRACK_B_28_DAY_REGRESSION.md)
- [Stage 18 Track B collector resilience repair](STAGE_18_TRACK_B_COLLECTOR_RESILIENCE.md)
- [Stage 19 Track B pre-registered independent validation](STAGE_19_TRACK_B_INDEPENDENT_VALIDATION.md)
- [Project handoff](../HANDOFF.md)
- [Track A consolidated research summary](STAGE_13_TRACK_A_RESEARCH_SUMMARY.md)
- [Track B cloud collection](STAGE_11_TRACK_B_CLOUD_COLLECTION.md)
- [Track B seven-day cloud audit](STAGE_14_TRACK_B_FIRST_COVERAGE_AUDIT.md)
- [Track B preliminary baseline](STAGE_15_TRACK_B_PRELIMINARY_BASELINE.md)
- [Model card](MODEL_CARD.md)
