# YouBike Demand Prediction

## 專案介紹、技術架構與目前狀態

- **文件更新日期：** 2026-09-09
- **作品性質：** Independent Time-Series Research Project · In Progress
- **專案狀態：** Track A 主要研究鏈已完成並進入維護；Track B 十四天 audit、平日週末分布與 persistence stability comparison 已完成，雲端資料持續累積至二十八天門檻
**Repository：** `youbike-demand-prediction`

---

## 1. 專案摘要

本專案研究如何利用 YouBike 歷史旅次、即時站點庫存、時間序列特徵與天氣資訊，建立可重現的需求與可用車預測流程，並為未來的缺車風險分析及車輛調度最佳化建立資料基礎。

專案分成兩條研究問題不同、不可混用 target 的主線：

| 研究線 | 研究問題 | Target | 目前狀態 |
|---|---|---|---|
| Track A：歷史轉乘需求 | 預測某站在指定小時的轉乘相關借車量 | 每站每小時轉乘相關借車量 | 主要研究、模型評估、error analysis 與歷史 Dashboard 已完成 |
| Track B：即時可用車 | 預測某站 30／60 分鐘後的可借車數 | Future available bikes | 雲端蒐集運作中；十四天 audit 與 persistence stability 已完成 |

Track A 的「歷史借車需求」不等於 Track B 的「未來剩餘車輛」。兩者不能共用 target，也不能直接把 Track A demand 解讀成即時 shortage、surplus 或補車數量。

---

## 2. 研究動機與預期應用

YouBike 站點的借還需求會受到時段、平假日、地點、歷史使用情形與天氣影響。當某站可借車數過低，使用者可能無車可借；當可還車位不足，也可能無法還車。

本專案分階段處理以下問題：

1. 建立可靠、可重現的資料蒐集與清理流程。
2. 預測歷史轉乘相關的小時借車需求。
3. 蒐集連續即時站點快照，建立 30／60 分鐘可用車預測。
4. 在 target 與 threshold 定義清楚後，研究缺車／滿站風險。
5. 只有在有效預測及營運限制都建立後，才研究車輛調度最佳化。

可能的未來應用包括：

- 站點短期可用車預測。
- 缺車與滿站風險提示。
- 尖峰時段與高誤差站點分析。
- 調度人員的決策輔助。
- 歷史需求與模型研究的互動式展示。

目前尚未宣稱完成即時 shortage prediction 或 redistribution optimization。

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
十四天 stability analysis（已完成）
                ↓
二十八天資料 → learned regression（尚未開始）
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

固定十四天分析結果：

| 項目 | 結果 |
|---|---:|
| 分析期間 | `[2026-08-21 09:45:02 UTC, 2026-09-04 09:45:02 UTC)` |
| Export rows | 7,240,919 |
| Snapshots | 4,031 |
| Distinct stations | 1,800 |
| Duplicate station-time rows | 0 |
| 估計缺少的五分鐘時槽 | 1 |
| Week 1／Week 2 30m persistence MAE | 1.704／1.030 |
| Week 1／Week 2 60m persistence MAE | 2.544／1.564 |

最後一次雲端查核（與固定分析期間不同）：

| 項目 | 最新狀態 |
|---|---:|
| 查核日期 | 2026-09-05 |
| 最新 snapshot | 2026-09-05 01:55:21 Asia/Taipei |
| 累積 snapshots | 4,141 |
| 累積 station rows | 7,438,853 |
| 最新一輪 station count | 1,800 |
| 最新一輪狀態 | Success，1 attempt |
| Collector 執行位置 | Cloudflare 雲端 |

上述累積數字是有日期的查核紀錄，不是 2026-09-09 的即時總量。十四天兩週 persistence 誤差的變動反映資料情境不同；persistence 不會訓練或更新，因此不可描述成模型持續學習或改善，也不可宣稱正式 learned live model 完成。

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

### 6.5 固定十四天 stability analysis（目前已完成檢查點）

固定期間為 `[2026-08-21 09:45:02 UTC, 2026-09-04 09:45:02 UTC)`。7,240,919 station rows 包含 4,031 snapshots、1,800 stations、0 duplicate station-time keys，估計缺少一個五分鐘時槽。

| Horizon | Week 1 MAE | Week 2 MAE |
|---|---:|---:|
| 30m | 1.704 | 1.030 |
| 60m | 2.544 | 1.564 |

Week 2 誤差較低不代表模型變好：persistence 定義在兩週完全相同，也沒有 fitting。差異表示 station-state dynamics 會跨週變動，因此正式 learned regression 必須等待固定 28 天 audit 後，以同一 test scope 與 persistence 比較。

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

Random Forest、LSTM／GRU 等深度學習不是目前必要工作；只有在資料量與新增研究價值足夠時才重新評估。

### 7.4 Cloud 與即時資料基礎設施

| 技術 | 用途 |
|---|---|
| Cloudflare Worker | 抓取 YouBike API、驗證 schema、retry、寫入 D1、提供 health／export endpoint |
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

目前 Dashboard 是 **Interactive Historical Prediction Dashboard**，展示 2023 年 12 月 holdout 回測，不是即時 shortage dashboard。

### 7.7 測試與可重現性

- Python `unittest`：資料清理、下載、features、模型、prediction、Track A analysis、Track B export／audit／baseline。
- Node test runner：Worker transformation、validation、timestamp、retry、logging 與 export range。
- 固定 config、model metadata 與 SHA-256 artifact validation。
- 大型 raw／processed dataset 不放入 Git；Git 保存 source、schema、config、tests、metrics 與文件。
- 最後一次 Stage 16 完整驗證：Python 62 tests passed、collector 9 tests passed。

---

## 8. Repository 主要結構

```text
youbike-demand-prediction/
├── cloudflare/track-b-collector/  # Track B Worker、Cron、D1、migration、tests
├── config/                        # 資料來源與可重現設定
├── dashboard/                     # React 19 + Vinext 歷史回測網站
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
| Track B protected CSV export | 已完成並通過 724 萬 rows 真實測試 |
| Track B 七天 station-row audit | 已完成 |
| Track B 30／60m persistence baseline | 已完成 |
| Track B 十四天平假日／穩定性分析 | 已完成 |
| Track B 28 天 learned regression | 尚未開始 |
| Shortage／full-station classification | 尚未開始，label／threshold 尚未定義 |
| Optimization | 尚未開始，等待有效 Track B prediction 與營運限制 |
| Deep Learning | 未開始／非優先 |

---

## 10. 已知限制

1. Track A 只涵蓋 2023 年轉乘相關旅次，不是全部 YouBike 旅次。
2. Track A 模型只評估 training-defined top-100 stations。
3. Track A 尚未完成跨年度驗證。
4. 歷史天氣是單一臺北參考點的事後再分析資料。
5. Track B 十四天只包含兩組週末，仍無法代表季節、事件與長期站點變化。
6. Persistence baseline 不是 trained AI model。
7. 快照車數差異不是純租借事件。
8. Shortage／full-station label 與 threshold 尚未完成研究定義。
9. Dashboard 是歷史回測，不是 live availability prediction。
10. Optimization 尚缺有效 risk prediction、車輛與人力資源、距離、成本、安全庫存等營運限制。

---

## 11. 下一步規劃

### 2026-09-04 17:45：固定十四天門檻（已完成）

- 已完成 7,240,919 rows 授權匯出與 cloud health／gap audit。
- 已檢查 duplicate、station coverage 與 30／60m target coverage。
- 已比較 weekday／weekend availability 分布與兩週 persistence stability。
- Collector 持續執行，沒有因分析停止或重新啟動。

### 2026-09-18 17:45:02 Asia/Taipei 之後：固定二十八天檢查

- 先確認固定二十八天資料通過 coverage、缺值、重複及站點變化 audit。
- Audit 通過後才建立 Track B 第一版 learned regression。
- 使用 current bikes、capacity、calendar、past-only lag／rolling features。
- 設計正式 chronological train／validation／test split。
- 只用 validation 做模型選擇。
- 在相同 test scope 與 persistence baseline 比較 MAE、RMSE、R²。
- 進行 station、hour、weekday／weekend error analysis。

日期到達不等於資料通過，也不等於模型完成。

### 後續研究

- 明確定義 shortage／full-station threshold 後才建立 classification。
- Availability／risk model 有效後，才設計 redistribution optimization。
- Track A 未來優先加入新年度資料做跨年度驗證，而不是堆疊相近模型。

---

## 12. 專案結論

目前專案已完成一條完整、可重現的 Track A 歷史需求研究鏈，包含全年資料、天氣整合、baselines、HGB／XGBoost、rolling-origin validation、ablation、error analysis、prediction interface 與 Web Dashboard。

Track B 已從短時間本機測試進展為正式雲端即時資料系統。Cloudflare Worker、Cron、D1、validation、retry、logging、安全匯出、七天 baseline 與十四天 stability analysis 均已完成。雲端資料正在累積至二十八天門檻，但正式 learned availability model、shortage risk 與 optimization 仍未完成，也不應提前宣稱完成。

此專案目前最重要的價值不只是單一模型分數，而是建立了清楚分離研究問題、避免時間洩漏、可持續蒐集、可重現評估且能誠實表達成果邊界的完整研究與工程流程。

---

## 13. 延伸文件

- [GitHub project page](../README.md)
- [Reproducibility guide](REPRODUCIBILITY.md)
- [Historical Dashboard／歷史回測展示](../dashboard/README.md)
- [Current-state project plan](../PROJECT_PLAN.md)
- [Stage 16 Track B fourteen-day stability analysis](STAGE_16_TRACK_B_14_DAY_STABILITY.md)
- [Project handoff](../HANDOFF.md)
- [Track A consolidated research summary](STAGE_13_TRACK_A_RESEARCH_SUMMARY.md)
- [Track B cloud collection](STAGE_11_TRACK_B_CLOUD_COLLECTION.md)
- [Track B seven-day cloud audit](STAGE_14_TRACK_B_FIRST_COVERAGE_AUDIT.md)
- [Track B preliminary baseline](STAGE_15_TRACK_B_PRELIMINARY_BASELINE.md)
- [Model card](MODEL_CARD.md)
