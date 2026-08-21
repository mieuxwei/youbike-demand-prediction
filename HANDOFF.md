# HANDOFF — YouBike Demand Prediction & Optimization

## 1. 交接摘要

目前專案已有一條成熟的歷史需求研究線與一條仍在累積資料的即時 availability 研究線。接手者必須保持兩者的 target、資料、評估與對外說法分離。

- **Track A：歷史轉乘需求預測** — 已完成 2023 全年資料、天氣、Naive／Ridge／HGB、rolling-origin validation、預測介面與 Interactive Web Demo；下一步是 XGBoost、完整 ablation 與完整 error analysis。
- **Track B：即時可用車／缺車風險** — 已完成蒐集、清理與特徵工程基礎，但連續快照不足，尚未開始正式建模。
- **Deep Learning 與 Optimization** — 尚未開始；Optimization 不能使用 Track A demand 直接當 shortage。

## 2. 已完成成果

### Data engineering and EDA

- 官方 YouBike 即時 API 單次與固定間隔蒐集器。
- 多快照清理、欄位驗證、品質摘要與自動化測試。
- 15／30／60 分鐘 backward-only lag、past-only rolling 與獨立 future target 管線。
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
- 三段 expanding-window rolling-origin evaluation。
- Permutation importance。
- Station-level 與 hour-level error reports。

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

Rolling-origin HGB folds 的 MAE 為 1.636、1.592、1.606。這些結果不可解讀為即時可用車、缺車風險或補車數量的預測表現。

## 5. Ablation 與 Error Analysis 狀態

### 已完成部分

- Ridge：with weather vs without weather。
- HGB：with weather vs without weather。
- HGB permutation importance。
- Station-level error ranking。
- Hour-level error analysis；17:00、18:00 與 08:00 等尖峰仍較難預測。
- Rolling-origin stability evaluation。

### 尚待完成

- Holiday feature 的可靠來源、定義與 ablation。
- 移除主要 historical lag groups 的 ablation。
- Worst prediction cases。
- 天氣條件、假日、尖峰／離峰、高／低需求站的統一情境比較。
- 大型活動或交通事件只能在取得可信資料後分析，不得根據誤差自行猜測原因。

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
10. XGBoost 未完成，Random Forest 僅為選配；Deep Learning 與 Optimization 未開始。

## 7. Track 狀態

| Track | 狀態 | 下一個有效成果 |
|---|---|---|
| Track A：歷史轉乘需求 | 主要 pipeline 與展示已完成 | XGBoost + 完整 ablation／error analysis + research summary |
| Track B：即時 availability／risk | 資料與 feature pipeline 已完成；資料不足 | 多日 snapshot dataset + coverage／gap audit |
| Deep Learning | 未開始 | Track A 研究鏈完成後再決定是否執行 |
| Optimization | 未開始 | Track B 有效預測與營運限制定義完成後才設計 |

## 8. 下一步優先順序

1. **Track A：補 XGBoost。** 使用完全相同的 target、top-100 stations、特徵規則、time split 與 metrics，比較 HGB；不要預設 XGBoost 一定較好。
2. **Track A：完成 ablation。** 先補 holiday 定義，再做 feature-group 比較；現有 weather on／off 結果保留。
3. **Track A：完成 error analysis。** 建立可重現的 worst-case 與情境化結果，不加入無資料支持的原因解釋。
4. **Track B：持續蒐集 snapshots。** 至少 7 天且包含平日／週末，較佳為 14–28 天；記錄中斷與資料缺口。
5. **Track B：重新做 coverage audit。** 只有 30／60 分鐘 targets 足夠後，才定義 baseline 與 time split。
6. **延後 Deep Learning。** 等 XGBoost、ablation、error analysis 完成後再決定是否有比較價值。
7. **延後 Optimization。** 不得以 Track A hourly demand 直接推導缺車或調度。
8. **沿用現有 Web Demo。** Streamlit 不是必要工作；不要為符合舊計畫重做前端。

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

## 10. 交接時應更新的欄位

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
