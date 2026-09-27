# HANDOFF — YouBike Demand Prediction

**Date:** 2026-09-27

**Current Stage:** Research Complete — Implementation Frozen (local working-directory version; not committed, pushed or deployed)

**Deployment status:** No restart or deployment on September 27. Cloudflare Worker + D1 + five-minute Cron continues collecting. The September 27 read-only health observation showed a successful 01:00:28 Asia/Taipei snapshot (finished 01:00:48), one attempt, 1,807 stations, and cumulative totals of 10,450 snapshots / 18,805,167 rows. These are dated totals, not proof of every historical run succeeding. `EXPORT_TOKEN` remains in macOS Keychain service `youbike-track-b-export`, not in Git. The previous recorded deployment was Worker version `30e22fe9-9d56-48d1-9cb3-c84c551112d2` on September 19.

## 1. 交接摘要

本版定位是固定資料上的預測比較與靜態調度模擬研究原型。使用者於 2026-09-27 明確調整 v5 範圍，要求補完原 Phase 3／4 與必要展示後 freeze，不等待更多資料。接手者必須保持 Track A、原 Stage 17／19、新補充回溯研究的 target、範圍與證據分離。

- **Track A：歷史轉乘需求預測** — 已完成 2023 全年資料、天氣、Naive／Ridge／HGB／XGBoost、rolling-origin validation、feature-group ablation、完整 error analysis、consolidated research summary、預測介面與 Interactive Web Demo；目前進入維護狀態。
- **Track B：即時可用車研究** — 雲端系統、固定 28 天研究與獨立七天驗證已完成。Stage 19-B 於 9/27 按凍結規則執行，資料門檻均通過；30m persistence MAE 1.950 優於 HGB 1.981，60m HGB MAE 2.813 優於 persistence 2.862（改善 1.71%），通過全部 independent gates。結合 Stage 17，固定為 30m persistence／60m HGB 小幅跨窗改善；尚未建立 shortage／full classifier 或 live model serving。
- **Phase 3** — 既有 28 天資料、訓練選定 64 站、共同 89,600 個 60m 序列。Persistence／新 HGB／LSTM ensemble MAE 3.431339／3.249886／3.326271；固定兩 learning rates、三種子、單層 LSTM，未勝過 HGB，不採用。所有新模型另存，沒有覆寫 Stage 17／19。
- **Phase 4** — 12 站 × 12 固定情境、6 資源／成本設定，執行 72 個 MILP、保存 216 組基準／最佳化方案。基本平均目標值不調度 92.1952、greedy／MILP 76.8478；基本案例全數同分。零資源／高成本不調度。限制驗證通過，不宣稱真實營運效益。
- **最終證據入口** — [Phase 3–4 報告](docs/PHASE_3_4_OFFLINE_RESEARCH.md)、[model card](docs/TRACK_B_OFFLINE_MODEL_CARD.md)、[重現](docs/REPRODUCIBILITY.md#phase-34-fixed-data-research)、[freeze 紀錄](docs/RESEARCH_FREEZE.md)。必要本機驗收通過，已 freeze 並停止本版實作；不再安排下一階段。

本輪未匯出新資料，未讀取／重設 token，未更動 collector／雲端設定，也未 commit、push、release 或部署。上方雲端數字是本輪開始前已有的 9/27 查核紀錄，不是本輪新查詢。第 10–20 節保存逐階段歷史交接，當時「等待／不開始」及未完成清單不再是本版執行指令；以本頁前段及 v6 計畫為準。

## 2. 已完成成果

### 本輪新增檔案與模型

| 類別 | 位置 |
|---|---|
| 固定規約／設定 | `docs/OFFLINE_RESEARCH_PROTOCOL.md`、`config/offline_research.json` |
| 訓練／推論／比較 | `src/offline_forecasting.py`、`requirements-research.txt`、`models/offline_research/` |
| MILP 與基準／敏感度 | `src/offline_optimization.py`、`results/offline_research/` |
| 研究面板 | `src/build_offline_dashboard.py`、`dashboard/app/offline-research.tsx`、`dashboard/app/offline-research-data.json` |
| 驗收／完整性 | `tests/test_offline_research.py`、`src/freeze_offline_research.py`、Dashboard SSR tests |
| 精簡結案文件 | `docs/PHASE_3_4_OFFLINE_RESEARCH.md`、`docs/TRACK_B_OFFLINE_MODEL_CARD.md`、`docs/RESEARCH_FREEZE.md` |

修改 README、v6 PROJECT_PLAN、本 HANDOFF、中文總覽、REPRODUCIBILITY、原 model card 的歷史建議註記、Dashboard page/styles/README/tests 及 cache ignore。Stage 19 文件／結果在本輪開始時已有未提交變更，完整保留；不誤記為本輪重跑。模型／資料／result 明細與精確 hashes 由 manifest 記錄，不在文件逐項複製浮點數。

### Data engineering and EDA

- 官方 YouBike 即時 API 單次與固定間隔蒐集器。
- 多快照清理、欄位驗證、品質摘要與自動化測試。
- 15／30／60 分鐘 backward-only lag、past-only rolling 與獨立 future target 管線。
- 獨立 Cloudflare Worker、`*/5 * * * *` Cron、D1 schema、validation、retry、structured logging 與 protected CSV export。
- 2023 全年 12 個月份官方轉乘旅次下載、逐月處理與稽核。
- Station-hour 借還需求聚合。
- 2023 全年小時天氣下載、清理與需求合併。
- Historical demand、時間型態與雨天／非雨天描述性 EDA。

### Track A modeling and evaluation

- 訓練期限定的 top-100 station scope。
- 1–9 月 training、10–11 月 validation、12 月 test 的時間切分。
- Previous-hour persistence 與 previous-week same-hour baselines。
- Ridge without／with weather。
- HGB without／with weather。
- XGBoost with weather；相同 scope 與時間切分，validation 選參數。
- 三段 expanding-window rolling-origin evaluation。
- Permutation importance。
- 固定參數 HGB 的 6 組 leave-one-feature-group-out ablation 與 official day-off 增量檢查。
- Station、hour、weekday、尖離峰、需求層級、weather、official day type、daily 與 worst-case error reports。

### Inference and presentation

- 單一目標小時的 100 站預測 CLI。
- Demand history、168 小時 coverage、站點、target-hour weather、feature schema 與 model SHA-256 驗證。
- Historical actual 只在推論完成後附加的 backtest mode。
- React 19 + Vinext Interactive Historical Prediction Dashboard。
- Cloudflare／Sites 專案部署配置。
- Dashboard 展示 10 個代表性 holdout 時段、模型比較、rolling-origin 與 permutation importance。

## 3. 資料規模與範圍

### Track A historical transfer demand

| 項目 | 已驗證狀態 |
|---|---|
| 期間 | 2023-01-01 至 2023-12-31 |
| 月份 | 12 個月 |
| 轉乘相關旅次 | 7,388,479 筆 |
| 有活動的 station-hour rows | 4,670,320 筆 |
| 小時天氣 | 8,760 小時 |
| Demand-weather match | 100% |
| 模型站點 | Training period 選出的 100 個高需求站點 |

歷史資料只包含與公車／捷運轉乘相關的 YouBike 旅次，時間粒度為小時，不代表所有 YouBike 使用。

天氣來自 Open-Meteo 的臺北單一參考點歷史再分析值，不是每站的現地氣象站觀測。

### Track B live snapshots

| 項目 | 已驗證狀態 |
|---|---|
| Repository 固定樣本 | 2 個 snapshots、3,580 rows |
| 固定樣本 30 分鐘 future target | 0% coverage |
| 固定樣本 60 分鐘 future target | 0% coverage |
| 本機蒐集測試 | 12 份、約一小時；不足以作為正式訓練資料 |
| Cloud live dataset | 固定 28 天分析：14,490,149 rows、8,058 snapshots、1,803 stations |
| Cloud collector | 已部署；`*/5 * * * *` 排程執行中 |
| 多日 coverage | 28 天完成；0 duplicates、7 missing slots；30／60m target coverage 97.971%／97.750% |
| Stage 19 獨立七天 | 3,636,105 evaluation raw rows、2,016 snapshots、1,807 observed stations；0 duplicates／missing slots |
| Stage 19 有效評估 | 1,783 stations；30m／60m rows 3,567,488／3,556,778；active-row coverage 99.696%／99.397% |

快照間車輛數變化混合租借、還車、調度與資料修正，不能直接視為實際租借量。

## 4. 模型結果

本節下表皆為 Track A：2023 年 12 月 holdout、定義內 100 站的 hourly transfer-related borrowing demand。Track B 指標另見第 20 節，不可混成同一排行榜。

| Model | MAE | RMSE | R² |
|---|---:|---:|---:|
| Previous hour | 2.441 | 4.129 | 0.460 |
| Previous week, same hour | 2.176 | 3.701 | 0.566 |
| Ridge without weather | 1.810 | 2.911 | 0.731 |
| Ridge with weather | 1.793 | 2.889 | 0.736 |
| HGB without weather | 1.601 | 2.567 | 0.791 |
| HGB with weather | **1.575** | **2.549** | **0.794** |
| XGBoost with weather | 1.597 | 2.580 | 0.789 |

Rolling-origin HGB folds 的 MAE 為 1.636、1.592、1.606；XGBoost folds 為 1.673、1.624、1.644。HGB 在 holdout 與 rolling-origin 都略優於 XGBoost，因此仍是 Track A 主模型。這些結果不可解讀為即時可用車、缺車風險或補車數量的預測表現。

## 5. Ablation 與 Error Analysis 狀態

### 已完成

- Ridge：with weather vs without weather。
- HGB：with weather vs without weather。
- HGB permutation importance。
- Station-level error ranking。
- Hour-level error analysis；17:00、18:00 與 08:00 等尖峰仍較難預測。
- Rolling-origin stability evaluation。
- XGBoost validation-only tuning、holdout comparison、permutation importance 與 100 筆 worst cases。
- 固定 `deeper` HGB 參數的 station／calendar／immediate／daily／weekly／weather feature-group ablation。
- 行政院人事行政總處 2023 政府機關辦公日曆定義與增量實驗；validation/test 方向不一致，因此不加入主模型。
- HGB 100 筆 worst cases、daily errors 與統一情境比較。

大型活動或交通事件仍沒有可信資料，不得根據誤差自行猜測原因。

## 6. 已知限制

1. Track A 只涵蓋轉乘相關旅次，不是所有 YouBike 旅次。
2. Track A 只評估 training period 選出的 100 個高需求站點。
3. 歷史資料只有 2023 一年，尚未驗證跨年度穩定性。
4. Track A 使用的歷史天氣是事後再分析資料；真正未來預測要改用當時可取得的 forecast。
5. Dashboard 原面板是 2023 年 12 月 holdout；新本機面板是 2026 年固定 Track B 回溯比較／模擬，均不是 live availability。
6. Track A demand ranking 不能直接轉成 shortage、surplus 或 redistribution quantity。
7. Track B 已完成獨立驗證，但 30m MAE 仍未超越 persistence，60m 跨窗改善仍小；尚非 production live prediction，亦未證明統計顯著或季節泛化。
8. 快照車輛數差異不是純租借事件。
9. HGB 雖是現有最佳模型，仍有尖峰時段與高需求站誤差。
10. 新增 LSTM 未超過同範圍 HGB；靜態 MILP 在基本設定與 greedy 同分。半容量目標、距離、成本、可用接收容量及立即生效都是模擬假設，沒有營運效益或風險機率證明。

## 7. Track 狀態

| Track | 狀態 | 本版邊界 |
|---|---|---|
| Track A：歷史轉乘需求 | 原研究與模型、bundle 保留 | 不重訓、不擴充 |
| Track B：availability | Stage 17／19 原結論保留 | 不做 live serving／risk classifier |
| Deep Learning | 60m 有界限比較已執行，LSTM 不採用 | 不追加候選或調參 |
| Optimization | 靜態 MILP、greedy／不調度及敏感度已執行 | 不做真實車隊路線或即時營運服務 |

## 8. 本版驗收與停止規則

實際驗收：Python 80、collector Node 11、Dashboard SSR／資料一致性 2 tests 通過；production build、改動頁面 strict typecheck、瀏覽器桌面／手機控制項、重載推論、137 份舊 artifact 保護及 216 組方案限制通過。額外全專案 typecheck／ESLint 因套件載入耗時中止，未宣稱通過；既有託管頁直接請求逾時，新面板未部署。全部限制記於 freeze 紀錄，本機預覽程序已停止，雲端不變。

1. Phase 3／4 已真實執行，保留未勝出的結果；不把回溯研究說成新獨立驗證。
2. 核對本機 Dashboard、模型 reload、全部方案限制、共同評估範圍、保護檔案 hashes、tests/build 與文件。
3. 全部必要驗收通過後才標記 **Research Complete — Implementation Frozen**，記錄真實工作目錄與未發布狀態。
4. 完成後停止新功能、模型、資料窗、調參、重訓、自動續跑及提醒。只有使用者明確要求才重開。
5. 雲端 collector／原部署維持原狀；即使繼續蒐集也不表示本版需要續做研究。不自行 commit／push／release／deploy。

## 9. Codex 交接規則

每次開始工作前：

1. 先讀 `PROJECT_PLAN.md`、`HANDOFF.md`、`README.md`，以及與當前任務直接相關的最新 Stage 文件。
2. 檢查 `git status` 與現有差異；既有修改視為使用者工作，除非任務明確要求，不得覆蓋無關變更。
3. 確認本次工作屬於 Track A 或 Track B，先寫清楚 target、資料範圍與可宣稱成果。
4. 核對來源檔、實際 row counts、period、feature schema 與 metrics；禁止填假數據或把 planned result 寫成 completed。
5. Track A 與 Track B 必須使用獨立 target、dataset、model artifact、metrics 與文件措辭。
6. 不得用 random split 作為主要時間序列評估；所有 lag／rolling features 只能使用目標時間以前的資料。
7. Holdout actual 只能在預測完成後附加；future targets 絕不可進入 predictor matrix。
8. 不得把歷史 demand、快照差值或 ranking 直接稱為 shortage、surplus、availability 或 redistribution recommendation。
9. 新模型必須與現有 baseline 在相同 scope 下比較並保存可重現設定；test 不得用於 tuning。
10. 新增 holiday、event、weather forecast 或營運資料前，先確認來源、授權、欄位、期間與缺漏。
11. 每完成一個階段，同步更新 `README.md`、對應 Stage 文件與本 `HANDOFF.md`；列出實際產出、測試、限制及下一步。
12. 執行與改動風險相稱的測試；若未執行，明確說明原因，不得宣稱通過。
13. v6 已依明確授權補完 LSTM／靜態 Optimization，不新增 Random Forest、Streamlit、GRU 或 Transformer。
14. Track A 不能當即時庫存缺口；Phase 4 使用 validation 選定的 Track B 預測及明示研究假設，不宣稱營運規則。

## 10. Stage 11 最新交接紀錄

### Track A Status

Track A 未重訓、未修改模型 target、artifact 或 metrics。HGB holdout MAE 1.575、RMSE 2.549、R² 0.794，歷史 React/Vinext Dashboard 維持原部署與歷史回測定位。

### Track B Status

- 本機真實資料：12 snapshots、2026-08-20 20:20:14～21:15:23（Asia/Taipei）、約 55 分鐘、每份約 1,790 站。
- 2026-08-21 單次 schema check：官方 API 回傳 1,794 站，必要欄位全數存在；這只是 schema 驗證，不是正式雲端資料集。
- 雲端資料：2026-08-21 15:50:02、15:55:02、16:00:02（Asia/Taipei）連續成功；3 snapshots、5,382 rows，每輪皆 1 attempt、無錯誤，後續由 `*/5 * * * *` Cron 持續累積。
- 30／60 分鐘 future target coverage 仍不足，沒有 Track B 模型 metrics。

### Cloud architecture

- Primary：standalone Cloudflare Worker + Cron Trigger + D1。
- Cron：`*/5 * * * *`，Cloudflare 以 UTC 執行。
- D1：`station_snapshots` + `collection_runs`。
- R2：本階段不使用；若未來有 raw payload 稽核／冷儲存需求才另行評估。
- Export：Bearer token 保護、cursor pagination 的 `/export.csv`，由 `src/export_track_b.py` 合併成單一 CSV。

### Database schema

`station_snapshots` 保存 UTC snapshot/source/station update times、station ID/name、available bikes、available return bikes、capacity、latitude、longitude、active flag；`PRIMARY KEY (station_id, snapshot_time)` 強制去重，另有 time index。`collection_runs` 保存每次排程成功／失敗、attempts、station count、inserted count 與錯誤資訊。

### New files

- `cloudflare/track-b-collector/package.json`
- `cloudflare/track-b-collector/pnpm-lock.yaml`
- `cloudflare/track-b-collector/wrangler.jsonc`
- `cloudflare/track-b-collector/src/index.mjs`
- `cloudflare/track-b-collector/migrations/0001_track_b_live.sql`
- `cloudflare/track-b-collector/test/collector.test.mjs`
- `cloudflare/track-b-collector/README.md`
- `src/export_track_b.py`
- `tests/test_export_track_b.py`
- `docs/STAGE_11_TRACK_B_CLOUD_COLLECTION.md`

### Modified files

- `PROJECT_PLAN.md`
- `README.md`
- `HANDOFF.md`

### Test results

- 完整 Python repository tests：43 passed；包含 Track B export／D1 的 2 項新測試。
- Node collector tests：9 passed；包含成功／失敗 collection run logging。
- Wrangler dry-run：成功，Worker bundle 約 18.4 KiB，D1／vars bindings 可解析。
- Wrangler local D1 migration：6 個 schema commands 全數成功。
- 目前官方 API 1,794 rows 全數通過實際 transform validation。
- Dashboard lint、Vinext production build 與 server-rendered HTML test 均通過；Track A 展示未受影響。

### Deployment status and user actions required

Cloudflare D1 migration、Worker 與 `*/5 * * * *` Cron 已正式啟用。Production URL 為 `https://youbike-track-b-collector.mieuxander.workers.dev`；`/health` 已驗證連續三輪成功。`EXPORT_TOKEN` 已以 secret text 設定，未授權 export 已驗證回傳 HTTP 401；授權下載測試需由 owner 在本機安全輸入 token。逐步紀錄見 `docs/STAGE_11_TRACK_B_CLOUD_COLLECTION.md` 第 11 節。

### Known limitations

1. 雲端資料仍在第一天累積，尚不足以建立 30／60 分鐘 target 或模型。
2. 5 分鐘 Cron 不能保證無抖動；必須以實際 gap audit 判斷 target coverage。
3. API station count 會變動，不可固定為 1,790。
4. 28 天估計約 14.43M rows、約 2.36 GiB SQLite planning size；Cloudflare 實際用量與帳號方案需由 Console 確認。
5. D1 是結構化主資料；本階段沒有 raw JSON R2 備份。
6. 快照差值仍混合租借、還車、調度與資料修正。
7. Live prediction、shortage／full risk、optimization 均未完成。

### Next recommended step

Collector 持續執行；需要匯出時由 owner 在本機安全輸入 token 完成授權 smoke test。7 天後做第一輪 coverage／gap audit，但 collector 不停止；14／28 天再逐步進入 Track B 資料研究。不要自動開始新模型 Stage。

## 11. Stage 12 最新交接紀錄

### Track A Status

- 固定沿用 Stage 7 validation 選出的 HGB `deeper` 參數，不使用 test 調參。
- 完整 HGB 精確重現 2023 年 12 月 holdout：MAE 1.575、RMSE 2.549、R² 0.794。
- 8 個 variants、16 次 fit 已完成；6 組 feature-group removal 加 full 與 full + official day off。
- Test MAE 退化排序：calendar +10.44%、daily history +3.25%、station identity +2.80%、immediate history +2.22%、weather +1.69%、weekly history +0.70%。
- Official day-off flag 的 validation MAE 改善 0.24%，test MAE 惡化 0.43%；證據不一致，不加入主模型。
- Evening peak MAE 2.631、morning peak 2.267、off peak 1.204；high／medium／low station tiers 為 2.255／1.384／1.065。
- Actual demand ≥10 的 rows MAE 4.231 且平均偏低估；最大個別 absolute error 41.122。

### Track B Status

Cloudflare Worker + D1 + `*/5 * * * *` Cron 持續獨立運作；本階段沒有修改、重新部署或啟動 Track B 模型。

### New files

- `config/track_a_analysis.json`
- `src/track_a_analysis.py`
- `src/run_track_a_analysis.py`
- `tests/test_track_a_analysis.py`
- `results/track_a_ablation_metrics.csv`
- `results/track_a_ablation_test_summary.csv`
- `results/track_a_error_by_context.csv`
- `results/track_a_station_errors_complete.csv`
- `results/track_a_daily_errors.csv`
- `results/track_a_worst_cases.csv`
- `results/track_a_analysis_summary.json`
- `docs/STAGE_12_FEATURE_ABLATION_ERROR_ANALYSIS.md`

### Modified files

- `PROJECT_PLAN.md`
- `README.md`
- `HANDOFF.md`
- `docs/MODEL_CARD.md`

### Test results

- 完整 repository tests：48 passed。
- 完整分析 runner：8 variants、16 fits 成功。
- Full HGB holdout metrics 與既有 Stage 7 完全一致。
- Sites／Dashboard source 未變更，因此本階段不需要重新 build 或 deploy Dashboard。

### Known limitations

1. Ablation 差異描述模型對資訊群的依賴，不是因果效果。
2. DGPA 行事曆代表政府行政機關，不代表所有企業、學校或旅次目的。
3. 12 月 test 沒有特殊 weekday holiday／weekend makeup workday，holiday test evidence 有限。
4. 雨勢、溫度與需求量組成不同，情境 MAE 不可直接解讀成天氣因果。
5. 沒有 event／transit disruption 資料，worst-case 原因不得臆測。

### Next recommended step

整理 Track A consolidated research summary，不新增 Random Forest、LSTM 或 Optimization。Track B collector 繼續累積，滿 7 天後另做 coverage／gap audit。

## 12. Stage 13 最新交接紀錄

### Track A Status

- 已完成 `docs/STAGE_13_TRACK_A_RESEARCH_SUMMARY.md`，整合研究問題、資料範圍、時序切分、防洩漏規則、模型比較、rolling-origin、feature evidence、完整 error analysis、限制與決策。
- HGB with weather 維持主模型：2023 年 12 月 holdout MAE 1.575、RMSE 2.549、R² 0.794。
- 相較 previous hour、previous week same hour 與 Ridge with weather，HGB MAE 分別降低約 35.5%、27.6% 與 12.2%。
- HGB 三段 rolling-origin MAE 1.592–1.636、平均 1.611；每一段均優於 XGBoost。
- Track A 在目前計畫內進入 maintenance 狀態。Random Forest／LSTM 不列為必要下一步；有新年度資料時優先做跨年度驗證。

### Track B Status

Cloudflare Worker + D1 + `*/5 * * * *` Cron 維持獨立蒐集。本階段沒有重新啟動 collector、修改 schema、訓練 availability model 或執行 Optimization。

### New files

- `docs/STAGE_13_TRACK_A_RESEARCH_SUMMARY.md`

### Modified files

- `PROJECT_PLAN.md`
- `README.md`
- `HANDOFF.md`
- `docs/MODEL_CARD.md`

### Validation

- 研究摘要中的模型 metrics、rolling-origin folds、ablation 數值與 context errors 均由既有 committed CSV／JSON 重新核對。
- 完整 Python repository tests：48 passed。
- Track B collector Node tests：9 passed；本階段未修改 collector source。
- Stage 13 metrics assertions 與 Markdown link checks：passed。
- Dashboard source 未修改，因此依 Sites 規範不需要重新 build 或 deploy。

### Known limitations

1. 本階段是既有實驗證據的整合，不是新模型實驗。
2. 結論只適用 2023 年轉乘相關旅次、training-defined top-100 站點與既有切分。
3. 跨年度、全站點、完整 YouBike 旅次及線上 weather forecast 尚未驗證。
4. Peak／station／weather 情境差異不是因果效果。
5. Track A demand 不能當作 Track B availability、shortage 或調度 target。

### Next recommended step

Track B collector 繼續累積；滿 7 天時執行第一輪 coverage／gap audit，但不要停止蒐集。30／60 分鐘 targets 通過資料完整性檢查以前，不開始 Track B 模型。

## 13. 交接時應更新的欄位

每次階段性交接至少記錄：

- 完成項目與目的。
- 新增／修改檔案。
- Dataset 來源、期間、row count、coverage 與已知缺口。
- Target 與 feature definition。
- Train／validation／test 規則與 leakage check。
- Model、hyperparameters、artifact／metadata。
- Validation／test metrics 與適用範圍。
- Tests 或 build checks 的實際結果。
- Known limitations、未完成工作與下一個最小可執行步驟。
- 需要使用者決定的事項。

## 14. Stage 14 最新交接紀錄

### Track B cloud status（follow-up as of 2026-08-28 21:40 Asia/Taipei）

- Cloud Worker + `*/5 * * * *` Cron + D1 持續執行；不是本機背景程序。
- 21:35 audit checkpoint 有 2,074 個成功 runs／snapshots、3,721,765 station rows、1,798 distinct stations。
- 每個 snapshot 有 1,794–1,798 rows，平均 1,794.31。
- 0 個 failed runs；1 個 run 曾 retry。
- D1 21:35 查詢 metadata size 為 784,097,280 bytes（約 747.8 MiB）。
- 只有部署第一天一段 65 分鐘 gap，估計缺少 12 個五分鐘排程；之後沒有大於 5.5 分鐘的 gap。
- 21:40 的 30／60 分鐘 snapshot-time coverage 為 99.422%／98.892%。這不是模型 metric，也不是完整 active station-row coverage。
- 部署初期 gap 後的連續資料已有 7.16 天、2,063 snapshots、3,702,031 rows；期間沒有新增 gap，最大間隔 321 秒。

### New files

- `src/audit_track_b.py`
- `tests/test_audit_track_b.py`
- `cloudflare/track-b-collector/queries/track_b_coverage_audit.sql`
- `docs/STAGE_14_TRACK_B_FIRST_COVERAGE_AUDIT.md`

### Modified files

- `src/features.py`（以 `eq(True)` 處理 unmatched active state，消除 pandas downcast warning；target 定義不變）
- `PROJECT_PLAN.md`
- `README.md`
- `HANDOFF.md`

### Validation and remaining owner action

- Remote `/health` 與 D1 read-only queries 已實際執行。
- 新增 audit tests 驗證 gap／missing-slot、duplicate、required columns 及 30／60 分鐘 active future target alignment。
- 完整 Python repository tests：51 passed；Track B collector Node tests：9 passed。
- `track_b_coverage_audit.sql` 已對 production D1 成功執行：5 queries、rows written 0。
- `EXPORT_TOKEN` 不在目前本機環境中，未讀取或重設 Cloudflare secret；因此全量授權 CSV smoke test 與完整 station-row audit 尚未執行。
- Owner 應在本機設定 `TRACK_B_EXPORT_TOKEN` 後，執行 `src/export_track_b.py` 與 `src/audit_track_b.py`。Token 不可貼入對話或 commit。

### Decision and next step

目前不開始 Track B baseline。連續 7 天 cloud audit 已通過；下一步是完成授權全量 CSV audit。只有 station-row target coverage 與 chronological split 通過後，才建立 30／60 分鐘 preliminary baseline。Collector 在所有後續研究期間持續運作。

## 15. Stage 15 最新交接紀錄

### Authorized export and audit

- Owner 已明確授權重設 `EXPORT_TOKEN`；secret 值未顯示或寫入 Git。Stage 15 完成後依 owner 要求再次旋轉，Cloudflare authorization 已驗證，matching token 保存於 macOS Keychain service `youbike-track-b-export`。
- 真實 smoke test 發現長範圍 deep cursor 會造成 HTTP 500；client 新增 page-level transient retry 與預設六小時 bounded windows。
- 最終成功匯出 3,739,789 rows、377 pages、約 526 MiB；本機 CSV 位於 Git-ignored `data/processed/track_b_week_1.csv`。
- Dataset 涵蓋 2026-08-21 09:45:02Z 至 2026-08-28 15:20:23Z，2,084 snapshots、1,798 stations、7.233 天。
- 0 duplicate station-time rows、0 gaps over 5.5 minutes；最大 interval 5.35 分鐘。
- Active station-row target coverage：30m 97.946%、60m 97.662%。

### Preliminary persistence baseline

- 定義：`prediction(t+h) = available_bikes(t)`；不是 learned model。
- Chronological blocks：五天 train、一天 validation、其餘約 1.23 天 test。
- Future target time 必須留在自己的 split；validation→test boundary labels 會 purge。
- 30m validation：MAE 2.035、RMSE 3.523、R² 0.865。
- 30m test：MAE 2.154、RMSE 3.626、R² 0.852。
- 60m validation：MAE 2.947、RMSE 4.856、R² 0.744。
- 60m test：MAE 3.140、RMSE 5.064、R² 0.712。
- 沒有 shortage／full classifier、threshold、optimization 或 live Dashboard claim。

### New files

- `src/track_b_baseline.py`
- `tests/test_track_b_baseline.py`
- `docs/STAGE_15_TRACK_B_PRELIMINARY_BASELINE.md`
- `results/track_b_live_audit.json`
- `results/track_b_live_gaps.csv`
- `results/track_b_target_coverage.csv`
- `results/track_b_split_summary.csv`
- `results/track_b_persistence_metrics.csv`
- `results/track_b_baseline_summary.json`

### Modified files

- `src/export_track_b.py`
- `tests/test_export_track_b.py`
- `PROJECT_PLAN.md`
- `README.md`
- `HANDOFF.md`
- `cloudflare/track-b-collector/README.md`
- `docs/STAGE_14_TRACK_B_FIRST_COVERAGE_AUDIT.md`

### Next recommended step

當時建議為持續蒐集至 14／28 天後再建立 learned regression；此項已由 Stage 16／17 完成。Risk classification 仍必須先另行定義 label／threshold。

### Validation

- 完整 Python repository tests：58 passed。
- Track B collector Node tests：9 passed。
- Production authorized export：3,739,789 rows／377 pages，成功。
- Audit 與 baseline runner 均在完整 CSV 上執行成功。
- 最終 `/health`（2026-08-28 23:40 Asia/Taipei）：success、1,798 stations、2,098 cumulative snapshots、3,764,917 cumulative rows。

## 16. Stage 16 最新交接紀錄

### Date and Current Stage

- Date：2026-09-05。
- Current Stage：Track B Fourteen-Day Stability Analysis Complete。
- 本階段沒有訓練新模型、修改 Track A 或重新部署 collector。

### Track A Status

維持 maintenance：2023 全年資料、Naive／Ridge／HGB／XGBoost、rolling-origin、ablation、error analysis、research summary 與 React/Vinext historical dashboard 均未變。HGB holdout 仍為 MAE 1.575、RMSE 2.549、R² 0.794。

### Track B Status and cloud architecture

- Production：Cloudflare Worker + `*/5 * * * *` UTC Cron + D1，持續在雲端執行；不是本機背景程序。
- 2026-09-05 `/health` checkpoint：latest run success、1,800 stations；累積 4,141 snapshots、7,438,853 rows，最近 snapshot 為 2026-09-04 17:55:21 UTC（2026-09-05 01:55:21 Asia/Taipei）。
- 固定分析視窗：2026-08-21 09:45:02 UTC 至 2026-09-04 09:45:02 UTC，end exclusive，恰好十四天。
- 授權 export：7,240,919 rows、728 pages；本機 CSV 約 1.0 GiB，位於 Git-ignored `data/processed/track_b_14_days.csv`。
- D1 schema、Worker source、Cron、`EXPORT_TOKEN` 與部署設定均未變更。

### Data audit and target coverage

- 4,031 snapshots、1,800 stations、每輪 1,794–1,800 rows、0 duplicate station-time keys。
- Week 1：2,016／2,016 snapshots；Week 2：2,015／2,016。
- 唯一缺口：2026-08-28 15:20:23–15:30:23 UTC，10 分鐘、估計少一輪。D1 在缺少的 15:25 UTC 沒有 `collection_runs` record，前後兩輪皆 success。
- 全十四天、全部 rows 分母：30m target 97.916%、60m 97.622%。
- 同週 active-row 且 purge 邊界：Week 1 30m／60m 99.701%／99.402%；Week 2 99.354%／98.757%。
- Week 1 的 1,798 stations 全數保留到 Week 2；Week 2 另增 2 stations。

### Persistence stability

- 定義未變：`prediction(t+h) = available_bikes(t)`，沒有 fitting。
- Week 1 30m：MAE 1.704、RMSE 3.086、R² 0.907。
- Week 2 30m：MAE 1.030、RMSE 2.516、R² 0.925。
- Week 1 60m：MAE 2.544、RMSE 4.337、R² 0.817。
- Week 2 60m：MAE 1.564、RMSE 3.544、R² 0.850。
- Week-1-defined 1,798 common-station cohort 的 Week 2 MAE 同為約 1.030／1.564，排除新增 2 站造成主要差異。
- Week 2 MAE 顯著較低只能解讀為兩週 dynamics 不同；不能宣稱 persistence 進步或 learned live prediction 完成。

### Weekday／weekend observations

- Week 1 mean bikes：weekday 11.387、weekend 12.643；observed empty 3.352%／2.047%。
- Week 2 mean bikes：weekday 10.818、weekend 10.581；observed empty 3.662%／3.974%。
- 方向未跨週一致；只有兩組週末，不做因果或穩定季節性宣稱。
- Empty／no-return-space 只代表 observed current state，不是 future risk label。

### New files

- `src/track_b_stability.py`
- `tests/test_track_b_stability.py`
- `docs/STAGE_16_TRACK_B_14_DAY_STABILITY.md`
- `results/track_b_14d_*.csv`
- `results/track_b_14d_*.json`

### Modified files

- `src/features.py`（groupby 明確使用 `observed=True`，避免 categorical future warning；alignment 定義不變）
- `PROJECT_PLAN.md`
- `README.md`
- `HANDOFF.md`

### Database schema and deployment status

Schema 仍是 `station_snapshots` 的 `(station_id, snapshot_time)` primary key、time index，以及 `collection_runs` structured logs。UTC 儲存策略、Cron、Worker、D1 binding 與 protected export 均未修改；沒有 deployment 或 owner action required。

### Test and validation status

- Production authorized export、完整十四天 audit、兩週 persistence runner 與 D1 gap log 查詢均實際成功。
- Stage 16 tests涵蓋 timezone boundary、Asia/Taipei weekday/weekend、跨週 target purge、duplicate／naive timestamp rejection與 stability comparison。
- 完整 Python repository tests：62 passed；Cloudflare collector Node tests：9 passed。

### Known limitations and next recommended step

1. 十四天只有兩組週末，persistence 表現跨週變動明顯，尚不足以宣稱穩定 learned model。
2. 有一輪 Cron 沒有 snapshot 或 run log；不能由現有證據判定根因。
3. 沒有 shortage／full threshold、classifier、optimization 或 live Dashboard。
4. 快照差值仍混合借車、還車、調度與修正，不是純需求。
5. 當時的下一步為固定 28 天 audit 與 learned regression；此項已由 Stage 17 完成。

## 17. Stage 17 最新交接紀錄

### Date and Current Stage

- Date：2026-09-19。
- Current Stage：Track B 28-Day Audit and First Learned Regression Complete。
- Track A model、metrics、data 與 Dashboard 均未修改。

### Fixed dataset and audit

- 分析視窗：`[2026-08-21 09:45:02 UTC, 2026-09-18 09:45:02 UTC)`。
- 14,490,149 station rows、8,058 snapshots、1,803 stations。
- 0 duplicate station-time keys；7 個 isolated 10-minute gaps，估計缺 7 個五分鐘時槽。
- 30／60m future-target coverage：97.971%／97.750%。
- 原始合併 CSV 約 2.0 GiB，位於 Git-ignored `data/processed/track_b_28_days.csv`。
- Days 1–14 SHA-256：`8f4d4939977c4c5be5639e712048f82aab75410ac05787526a55aba2cabe6c43`。
- Days 15–28 SHA-256：`c5ecfe933acd009fca7e191b4388fbe356dfec40c15138187853d4eed0e2bae0`。

### Split and feature rules

- Train：18 日；9,312,719 raw rows、5,182 snapshots。
- Validation：5 日；2,588,400 raw rows、1,438 snapshots。
- Test：5 日；2,589,030 raw rows、1,438 snapshots。
- Future target crossing train／validation／test end is purged。
- Predictors：current bikes、return spaces、capacity、fractions、location、Asia/Taipei cyclical calendar、15／30／60m past-only lag／delta、30／60m past-only rolling statistics。
- Training 使用每第六個 snapshot 的完整站點橫切面以控制成本；validation／test 使用完整 eligible rows。
- HGB shallow 與 HGB regularized 只以 validation MAE 比較；兩個 horizon 均選出 regularized candidate。

### Holdout metrics

| Horizon | Model | Rows | MAE | RMSE | R² |
|---:|---|---:|---:|---:|---:|
| 30m | Persistence | 2,518,633 | **2.043** | 3.702 | 0.846 |
| 30m | HGB regularized | 2,518,633 | 2.057 | **3.454** | **0.866** |
| 60m | Persistence | 2,507,965 | 3.012 | 5.190 | 0.697 |
| 60m | HGB regularized | 2,507,965 | **2.922** | **4.645** | **0.757** |

- 30m：HGB RMSE 改善 6.70%，但 MAE 惡化 0.68%，不可宣稱全面優於 persistence。
- 60m：HGB MAE 改善 2.98%，RMSE 改善 10.51%；屬 modest first result。
- Test 完整 scope 有 1,777 stations；30m 有 716 站改善 MAE，60m 有 1,138 站改善。
- 尖峰時段仍是高誤差情境；local hour 07 learned MAE 為 30m 3.580、60m 5.024。

### New files

- `config/track_b_regression.json`
- `src/train_track_b_regression.py`
- `tests/test_track_b_regression.py`
- `docs/STAGE_17_TRACK_B_28_DAY_REGRESSION.md`
- `models/track_b_30m_regression.joblib`
- `models/track_b_60m_regression.joblib`
- `models/track_b_30m_regression.metadata.json`
- `models/track_b_60m_regression.metadata.json`
- `results/track_b_28d_*.csv`
- `results/track_b_28d_*.json`

### Model artifacts

- 30m SHA-256：`47f37095e1ee8e2d208fa8e0136a75e20005aecfd81afda6ffe33f8685bd202b`。
- 60m SHA-256：`d4bc2df1c815a7c722e900891b668d3b2a7124f66966913081cb957b5ec7e6f6`。
- Metadata records feature order、target、horizon、split、candidate、library versions、capacity clipping 與 holdout metrics。

### Deployment and collector checkpoint

- Worker source、D1 schema、Cron、secret 與 deployment 均未修改。
- 2026-09-19 01:12:02 Asia/Taipei read-only `/health`：累積 8,149 snapshots、14,654,123 rows；最近成功 snapshot 為 2026-09-19 00:50:35 Asia/Taipei。
- 01:10:35 scheduled run after the fixed analysis window failed after three attempts because the Worker received malformed JSON。官方 endpoint 在本機唯讀檢查時已回傳合法 JSON，但 Worker 至最後查核尚未恢復。Stage 17 沒有自行重啟或部署 collector。

### Known limitations and next recommended step

1. 30m HGB 未在 MAE 超越 persistence；60m 改善幅度仍小。
2. 二十八天仍不足以涵蓋季節、長期站點變化與特殊事件。
3. Snapshot changes 混合租借、還車、調度與資料修正。
4. 尚未定義 shortage／full threshold、class cost、classifier 或 optimization。
5. 下一步先處理 station／hour error analysis 的研究假設，並定義 risk target；不得用 holdout 反覆調參。
6. Collector 繼續累積，供未來獨立時間窗驗證。
7. 先監控／診斷 Worker 端 malformed JSON；恢復前不可宣稱雲端資料仍連續累積。

### Validation

- 完整 Python repository tests：66 passed。
- Cloudflare collector Node tests：9 passed。
- 28 天 authorized export、audit、feature construction、candidate tuning、holdout evaluation 與 error aggregation 均實際完成。
- Artifact SHA-256 與 metadata 一致；Markdown local links 與 `git diff --check` 通過。

## 18. Stage 18 最新交接紀錄

### Incident and scope

- Date：2026-09-19。
- Stage 17 固定資料、split、模型、metrics 與 artifact 均未變。
- 事件：部署前多輪 scheduled collection 在三次嘗試後仍收到 malformed JSON；同時本機直接讀取官方 endpoint 可取得合法 JSON，因此只判定為 transient upstream／cache-path 問題的合理假設，不宣稱已證明唯一 root cause。

### Collector repair

- 上游 Worker `fetch()` 新增 `cache: "no-store"`。
- 回應改為先讀文字、移除 optional UTF-8 BOM、明確拒絕空 body，再做 `JSON.parse()`。
- malformed 診斷只保存 content type、長度、首字元、last-modified 與 ETag，不保存完整 response body。
- Retry backoff 從 250 ms + 1,000 ms 延長為 2,000 ms + 10,000 ms；所有 attempts 維持同一 scheduled snapshot key，D1 primary key 去重規則未變。
- D1 schema、既有 rows、Cron `*/5 * * * *`、`EXPORT_TOKEN` 與 Track A 未修改。

### Deployment and health evidence

- Worker version：`30e22fe9-9d56-48d1-9cb3-c84c551112d2`。
- 第一輪 post-deployment Cron：`2026-09-18T17:20:35Z` scheduled，`17:21:15.945Z` finished，attempt 1 success，寫入 1,803 rows。
- 第二輪：`2026-09-18T17:25:01Z` scheduled，`17:25:03.962Z` finished，attempt 1 success，再寫入 1,803 rows。
- 第二輪 checkpoint 累積 8,151 snapshots、14,657,729 rows，最新 snapshot 為 2026-09-19 01:25:01 Asia/Taipei。
- 連續兩輪成功證明 collector 已恢復寫入，但不等於長期穩定；後續仍由正常五分鐘 Cron 持續監控。

### Validation

- Cloudflare collector Node tests：11 passed。
- Wrangler dry-run：19.55 KiB，gzip 5.50 KiB；D1 與 vars bindings 解析成功。
- Production deployment、trigger deployment 與 post-deployment `/health` 查核成功。
- 詳細紀錄：[Stage 18 collector resilience repair](docs/STAGE_18_TRACK_B_COLLECTOR_RESILIENCE.md)。

## 19. Stage 19-A 歷史交接紀錄（2026-09-19）

本節保留當時尚待執行的狀態；9/27 實際結果見第 20 節。

### Pre-registered window and freeze

- Date：2026-09-19；獨立資料尚未匯出前完成。
- History warm-up：`[2026-09-18T17:30:00Z, 2026-09-18T18:30:00Z)`，只供 lag／rolling feature 使用。
- Evaluation：`[2026-09-18T18:30:00Z, 2026-09-25T18:30:00Z)`，即 Asia/Taipei 2026-09-19 02:30 至 2026-09-26 02:30。
- 30m／60m model、metadata、training config SHA 均已寫入 freeze manifest；runner 會在 joblib load 前驗證。
- 不重新訓練、不修改 features、不用 independent window 調參。

### Pre-registered gates

- Snapshot coverage 至少 99.0%，預期七天 2,016 個五分鐘 snapshots。
- 0 duplicate station-time keys。
- 各 horizon usable active-row target coverage 至少 95.0%。
- Learned model 必須同時改善 MAE、RMSE，且至少 50% evaluated stations 的 MAE 優於 persistence，才通過 independent temporal gate。
- 最終 learned model 確認還必須與 Stage 17 primary MAE gate 一致；30m 即使新 window 勝出，也因 Stage 17 MAE 未勝而只能判為 mixed evidence。

### New files and command

- `config/track_b_temporal_validation.json`
- `src/validate_track_b_temporal.py`
- `tests/test_track_b_temporal_validation.py`
- `docs/STAGE_19_TRACK_B_INDEPENDENT_VALIDATION.md`
- `docs/REPRODUCIBILITY.md` 已加入 9/26 export 與單一執行流程。

Stage 19-B 在 2026-09-26 02:30 Asia/Taipei 後執行。Raw CSV 維持 Git-ignored；只提交 compact metrics、coverage、gaps、station/hour errors 與 decision summary。

### Current boundary

- Stage 19-A 只完成工具、凍結與 protocol，尚無 independent metrics。
- 不可把 planned Stage 19-B 結果寫成 completed。
- Shortage／full classifier、live prediction service 與 optimization 仍未開始。

### Validation

- 完整 Python repository tests：72 passed。
- Cloudflare collector Node tests：11 passed。
- Temporal validation CLI `--help` smoke test：passed。
- Freeze manifest 已對真實 30m／60m artifacts、metadata 與 training config 做 checksum integration test。

## 20. Stage 19-B 最新交接紀錄（2026-09-27）

### Execution and evidence

- Protocol commit：`3055c856b246680efbda2383d2fbf8e401816f4e`，2026-09-19 02:12:22 Asia/Taipei，早於 evaluation start 02:30。
- Evaluation：`[2026-09-18T18:30:00Z, 2026-09-25T18:30:00Z)`；前一小時只供 feature warm-up。
- Keychain 授權匯出成功：含 warm-up 3,657,741 rows／2,028 snapshots；原始 CSV 受 Git 忽略。
- SHA-256：`7411c066535d3562d76e84d18bac4b915387e817dccca5d5c68ec4a141d67943`。
- 七天區間 3,636,105 raw rows、2,016／2,016 snapshots、1,807 observed stations、0 duplicates／missing slots；最長 gap 5.05 分鐘。
- 30m／60m 有效 target coverage 為 active current rows 的 99.696%／99.397%，資料門檻均通過。

### Final research conclusion for this version

| Horizon | Eligible rows | Persistence MAE／RMSE | Frozen HGB MAE／RMSE | Lower HGB station MAE | Decision |
|---|---:|---|---|---|---|
| 30m | 3,567,488 | 1.950／3.455 | 1.981／3.253 | 608／1,783（34.10%） | 保留 persistence；HGB MAE 較差 1.56% |
| 60m | 3,556,778 | 2.862／4.833 | 2.813／4.389 | 1,048／1,783（58.78%） | 全部 independent gates 通過；MAE 改善 1.71% |

Stage 17 的 30m MAE 也未勝、60m MAE 改善 2.98%，因此固定本版研究結論為 **30m persistence、60m HGB 的小幅跨窗改善**。未重訓、調參或更換 baseline；不同窗的誤差差異不是模型持續學習。此決策沒有宣稱統計顯著、所有站點改善、季節泛化或 production-ready。

### New and modified files

- 新增 `results/track_b_independent_{metrics,coverage,gaps,station_errors,hour_errors}.csv`、`track_b_independent_summary.json`、`track_b_independent_provenance.json`。
- 更新 `README.md`、`PROJECT_PLAN.md`、本 `HANDOFF.md`、`docs/PROJECT_OVERVIEW_STATUS_AND_TECHNOLOGY.md`、`docs/STAGE_19_TRACK_B_INDEPENDENT_VALIDATION.md`、`docs/REPRODUCIBILITY.md`。
- 未更改模型、metadata、凍結 manifest、features、訓練／評估程式、Stage 17 結果、Track A 或 Dashboard bundle。
- 未部署、重啟 collector、重設 token、commit 或 push。

### Verification and limitations

- 原始驗證 CLI 成功；30m／60m artifacts、metadata、training config SHA 與 feature schema 均通過檢查。
- Python repository tests：72 passed；Cloudflare Node tests：11 passed。
- CLI `--check-only`／`--help`、JSON／CSV 結構、六份更新文件的 80 個本機 Markdown 連結與 `git diff --check` 均通過。未重新驗證線上 Dashboard 存取權限。
- 本機初次科學套件載入緩慢但已完成，未重裝環境；LibreSSL／physical-core detection 為非阻斷警告，後者退回 logical cores。
- 資料來源新鮮度診斷：4 份 evaluation snapshots 的 source update 落後排程超過 300 秒，2 份超過 600 秒，最長 1,092 秒。另有 1 份 source time 晚於 scheduled snapshot；排程時間不等於實際擷取完成時間。未用此診斷事後修改篩選／gates。
- 當前 cloud totals 見檔首，是固定查核點，不是今日持續變動的即時總量。
- Collector 繼續累積；shortage／full classifier、live serving、optimization 尚未開始。

### Next recommended step / user actions

1. 本版研究結論已固定；9/28–9/29 優先做交付檢查：README／中文總覽、展示入口可用性、重現資訊及對外成果措辭。
2. Historical Dashboard 先前記錄為 owner-restricted；不能未驗證就當作公開可訪問。若需要調整分享／部署權限，另行確認，不在本次暗中更改。
3. 本次不需要新 token 或雲端授權；要 commit／push 時再由使用者確認。
4. 不為月底期限追加訓練或風險分類。未來模型改動須另訂 protocol 並留新的 untouched window；risk 與 optimization 維持條件式後續工作。

完整證據與可重現命令：[Stage 19](docs/STAGE_19_TRACK_B_INDEPENDENT_VALIDATION.md)、[reproducibility guide](docs/REPRODUCIBILITY.md)。本版研究結論固定不等於整體專案 Completed／Frozen。
