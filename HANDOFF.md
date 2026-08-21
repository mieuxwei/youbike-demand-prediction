# HANDOFF — YouBike Demand Prediction & Optimization

**Date:** 2026-08-21

**Current Stage:** Stage 12 — Track A Feature-group Ablation + Complete Error Analysis

**Deployment status:** Cloudflare D1／Worker／Cron production deployment active; consecutive scheduled snapshots succeeded. `EXPORT_TOKEN` is configured and unauthorized export protection is verified.

## 1. 交接摘要

目前專案已有一條成熟的歷史需求研究線與一條仍在累積資料的即時 availability 研究線。接手者必須保持兩者的 target、資料、評估與對外說法分離。

- **Track A：歷史轉乘需求預測** — 已完成 2023 全年資料、天氣、Naive／Ridge／HGB／XGBoost、rolling-origin validation、feature-group ablation、完整 error analysis、預測介面與 Interactive Web Demo；下一步是整合 research summary。
- **Track B：即時可用車／缺車風險** — 已完成本機 pipeline 並正式部署 Cloudflare Worker + Cron + D1；正在累積多日資料，尚未開始正式建模。
- **Deep Learning 與 Optimization** — 尚未開始；Optimization 不能使用 Track A demand 直接當 shortage。

## 2. 已完成成果

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
| Cloud live dataset | 2026-08-21 15:50:02（Asia/Taipei）起；已驗證連續 3 snapshots、5,382 rows |
| Cloud collector | 已部署；`*/5 * * * *` 排程執行中 |
| 多日 coverage | 尚未完成 |

快照間車輛數變化混合租借、還車、調度與資料修正，不能直接視為實際租借量。

## 4. 模型結果

所有指標皆為 2023 年 12 月 holdout、定義內 100 站的 hourly transfer-related borrowing demand。

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
5. Dashboard 是 2023 年 12 月歷史 holdout 回測，不是 live availability dashboard。
6. Track A demand ranking 不能直接轉成 shortage、surplus 或 redistribution quantity。
7. Track B 尚無足夠多日連續快照；正式 availability／risk model 未開始。
8. 快照車輛數差異不是純租借事件。
9. HGB 雖是現有最佳模型，仍有尖峰時段與高需求站誤差。
10. XGBoost 已完成但未超越 HGB；Random Forest 僅為選配，Deep Learning 與 Optimization 未開始。

## 7. Track 狀態

| Track | 狀態 | 下一個有效成果 |
|---|---|---|
| Track A：歷史轉乘需求 | Naive／Ridge／HGB／XGBoost、ablation、完整 error analysis 與展示已完成 | Consolidated research summary |
| Track B：即時 availability／risk | 雲端 collector 已部署；資料累積中、仍不足以建模 | 持續累積並做 coverage／gap audit；需要時做授權 export smoke test |
| Deep Learning | 未開始 | Track A 研究鏈完成後再決定是否執行 |
| Optimization | 未開始 | Track B 有效預測與營運限制定義完成後才設計 |

## 8. 下一步優先順序

1. **Track B：持續監控。** `EXPORT_TOKEN` 已生效；需要匯出時由 owner 在本機安全輸入 token，完成授權 CSV export smoke test。
2. **Track B：持續蒐集 snapshots。** 7 天做初步可行性、14 天比較平假日、28 天作為第一版正式模型建議最低目標；記錄中斷與資料缺口。
3. **Track B：重新做 coverage audit。** 只有 30／60 分鐘 targets 足夠後，才定義 baseline 與 time split。
4. **Track A：完成 research summary。** 沿用現有 HGB／XGBoost／ablation／error results，不重做已完成模型。
5. **延後 Deep Learning。** 等 ablation、error analysis 完成後再決定是否有比較價值。
6. **延後 Optimization。** 不得以 Track A hourly demand 直接推導缺車或調度。
7. **沿用現有 Web Demo。** Streamlit 不是必要工作；不要為符合舊計畫重做前端。

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
13. 不要因舊計畫指定 Random Forest、Streamlit、LSTM 或 Optimization 就跳過目前優先順序。
14. Optimization 必須等待 Track B 有效預測與營運限制；Track A 只能作為經驗證的背景訊號，不能直接當即時庫存缺口。

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

## 12. 交接時應更新的欄位

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
