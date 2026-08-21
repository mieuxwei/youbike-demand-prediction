# YouBike Demand Prediction & Optimization — Current-State v2

## 1. 文件目的

本文件以目前 repository 的實際成果為基準，取代把專案描述成「準備建立 Baseline」的舊計畫。專案分為兩條目標、資料與評估方式不同的研究線；兩者不可共用 target，也不可把其中一條的輸出直接解讀成另一條的成果。

- **Track A：歷史轉乘需求預測** — 已完成可重現的主要研究與展示鏈。
- **Track B：即時可用車／缺車風險** — 已完成蒐集與特徵管線基礎，目前仍需累積足夠的連續即時資料。

## 2. 核心研究定義

### Track A：歷史轉乘需求預測

研究問題：能否用站點、時間、歷史需求與天氣特徵，預測指定站點在某小時的**轉乘相關借車量**？

- Target：每站每小時的轉乘相關借車量。
- 資料範圍：2023 年官方轉乘 YouBike 旅次；這不是所有 YouBike 旅次。
- 模型範圍：只涵蓋依 2023 年 1–9 月 training activity 選出的 100 個高需求站點。
- 評估方式：依時間順序切分；1–9 月 training、10–11 月 validation、12 月 holdout test。
- 用途：歷史需求排名、模型比較、回測、研究展示。
- 不代表：現在可借車數、30／60 分鐘後可借車數、缺車／滿站風險或補車數量。

### Track B：即時可用車／缺車風險

研究問題：在有足夠連續即時快照後，能否預測站點 30／60 分鐘後的可借車數，或建立缺車／滿站風險？

- Target：`target_available_bikes_30m`、`target_available_bikes_60m`，或後續明確定義的缺車／滿站標籤。
- 可能輸入：目前可借車數、可還車位、站點容量、時間特徵、只向過去對齊的 lag／rolling 特徵，以及經驗證可取得的外部資訊。
- 現況：蒐集器、清理流程、15／30／60 分鐘 lag／rolling 與 future target 建立流程已完成；可供訓練的多日連續快照仍不足。
- 注意：快照間的車輛數變化可能同時包含租借、還車、調度與資料修正，不能直接當作租借需求。

## 3. 已驗證資料狀態

### Track A

- 2023 全年 12 個月份。
- 7,388,479 筆轉乘相關旅次。
- 4,670,320 筆有活動的 station-hour demand rows。
- 8,760 小時臺北單一參考點歷史天氣。
- 需求資料與天氣同小時匹配率 100%。
- 天氣屬 Open-Meteo 歷史再分析資料，不是每站現地觀測；真正未來預測必須使用預測當下可取得的 weather forecast。

### Track B

- Repository 內固定樣本為 2 個快照、3,580 rows，主要用於重現清理與特徵流程。
- 固定樣本的 30／60 分鐘 future target coverage 均為 0%。
- 曾完成 12 份、約一小時的本機蒐集測試；這仍不足以涵蓋平日、週末與多種需求情境，也不是可用於正式建模的多日資料集。
- 正式建模前至少要有連續 7 天且包含平日與週末的資料；14–28 天會更有利於涵蓋週間差異。這是資料規劃門檻，不是模型有效性的保證。

## 4. Track A 目前成果

### 4.1 已完成

- 全年歷史資料下載、清理、稽核與 station-hour 聚合。
- 小時天氣整合與描述性 EDA。
- Past-only lag／rolling features 與 leakage-aware 時間切分。
- Previous-hour persistence baseline。
- Previous-week same-hour baseline。
- Ridge without weather。
- Ridge with weather。
- Histogram Gradient Boosting（HGB）without weather。
- Histogram Gradient Boosting（HGB）with weather。
- XGBoost with weather，使用相同 scope 與時間切分公平比較。
- 三段 expanding-window rolling-origin validation。
- Permutation importance。
- Station-level 與 hour-level error analysis。
- 含 schema、時間覆蓋、站點、天氣與模型 SHA-256 驗證的單一小時預測介面。
- 歷史回測 Interactive Web Demo。

### 4.2 2023 年 12 月 holdout 結果

| Model | MAE | RMSE | R² |
|---|---:|---:|---:|
| Previous hour | 2.441 | 4.129 | 0.460 |
| Previous week, same hour | 2.176 | 3.701 | 0.566 |
| Ridge without weather | 1.810 | 2.911 | 0.731 |
| Ridge with weather | 1.793 | 2.889 | 0.736 |
| HGB without weather | 1.601 | 2.567 | 0.791 |
| HGB with weather | **1.575** | **2.549** | **0.794** |
| XGBoost with weather | 1.597 | 2.580 | 0.789 |

上述結果只適用於定義內的 100 個站點及 hourly transfer-related borrowing demand，不可外推成全臺北所有 YouBike 需求或 Track B 的 availability 表現。

### 4.3 Interactive Web Demo

- React 19 + Vinext 儀表板已完成。
- 已透過 Cloudflare／Sites 專案配置部署。
- 展示 2023 年 12 月 10 個代表性 holdout 時段、100 站預測／actual／absolute error、模型比較、rolling-origin 結果與 permutation importance。
- 定位為 **Interactive Historical Prediction Dashboard**，不是 Live shortage dashboard。
- Streamlit 不是必要交付項；只有在未來出現明確需求時才列為選配。

## 5. 研究工作完成度

| 項目 | 狀態 | 說明 |
|---|---|---|
| 2023 全年歷史資料 | 已完成 | 12 個月、7,388,479 筆旅次 |
| Station-hour demand | 已完成 | 4,670,320 rows |
| 8,760 小時天氣 | 已完成 | Demand join match 100% |
| Naive baselines | 已完成 | Previous hour、previous week same hour |
| Ridge | 已完成 | 有／無天氣版本 |
| HGB | 已完成 | 有／無天氣版本，現有最佳模型 |
| XGBoost | 已完成 | 相同 target、站點、特徵與時間切分；HGB 仍較佳 |
| Random Forest | 選配 | 不是進入下一階段的必要條件 |
| Ablation Study | 部分完成 | 已比較 Ridge、HGB 的有／無天氣版本；holiday 與移除主要 lag feature groups 尚未完成 |
| Error Analysis | 部分完成 | 已有 station／hour errors 與尖峰觀察；極端天氣、假日、worst cases 等完整情境分析尚未完成 |
| Deep Learning | 未開始 | 須待 Track A 傳統模型研究鏈完整後再評估必要性 |
| Track B availability model | 未開始訓練 | 等待多日連續快照與 target coverage |
| Optimization | 未開始 | 必須建立在 Track B 的有效狀態／風險預測與明確營運限制上 |
| Interactive Web Demo | 已完成 | React 19 + Vinext + Cloudflare／Sites；歷史回測展示 |

## 6. 下一步優先順序

### Priority 1 — 完成 Track A 的 Ablation 與 Error Analysis

1. XGBoost 已使用相同 top-100 scope、feature definition、time split、validation、holdout test 與 rolling-origin 完成比較；HGB 仍保留為主模型。
2. 完成尚缺的 ablation；新增 holiday feature 前必須先確認可靠資料來源與定義。
3. 擴充 error analysis，優先處理 worst cases、尖峰／離峰、高／低需求站、天氣條件與假日；沒有資料支持的事件不得自行推論。
4. Random Forest 只在比較價值明確且資源允許時補做，不是完成 Track A 的必要條件。
5. 完成 Track A 研究摘要，忠實記錄 HGB 略優於 XGBoost。

### Priority 2 — 平行累積 Track B 資料

1. 穩定蒐集至少 7 天、同時包含平日與週末的 5 分鐘左右快照；若可行，以 14–28 天為較佳範圍。
2. 記錄資料缺口、時間間隔、站點 coverage 與 API／設備中斷。
3. 重建 feature coverage，確認 30／60 分鐘 target 有足夠非空資料後，才設計時間切分與 baseline。
4. 明確定義 shortage／full-station label、預測 horizon 與評估指標後，才開始 Track B 模型。

### Priority 3 — 延後研究

- Deep Learning：Track A 的 ablation 與 error analysis 完成後，再判斷是否值得加入 LSTM／GRU。
- Optimization：Track B 建立有效的 availability／risk prediction、站點容量與營運限制後才開始。
- Demo 擴充：沿用現有 Interactive Web Demo；Streamlit 僅為選配。

## 7. Optimization 邊界

Optimization 不得把 Track A 的「每小時轉乘相關借車需求」直接標記成 shortage、surplus 或需補車數量。

進入 Optimization 前至少需要：

1. Track B 對未來可借車數或 shortage／full-station risk 的有效預測。
2. 清楚的站點容量與安全庫存／風險定義。
3. 可用車輛、調度數量、距離、成本與其他營運限制。
4. 與 baseline 比較及時間外推評估。

Track A 可以作為長期需求背景訊號或候選特徵，但必須先經驗證，不能等同即時庫存缺口。

## 8. 評估與資料洩漏規則

- 主要評估不得使用 random split。
- Station selection、feature construction、tuning 與 scaling 只能使用當時可取得的 training／validation 資訊。
- Lag 與 rolling features 必須只向過去對齊；future target 不得進入 predictors。
- Holdout actual 只能在預測完成後用於評估或展示。
- 未來天氣輸入必須是預測當下可取得的 forecast，不可使用事後觀測冒充線上特徵。
- 所有新增模型都必須報告實際 MAE、RMSE、R²；未執行的實驗保留為待辦，不填 placeholder 或假數據。

## 9. 主要交付物

- 可重現的資料與模型 pipeline。
- Naive、Ridge、HGB 與 XGBoost 統一比較。
- Ablation、error analysis、rolling-origin validation 與 model documentation。
- React 19 + Vinext + Cloudflare／Sites Interactive Web Demo。
- `README.md`、`PROJECT_PLAN.md`、`HANDOFF.md` 與各 Stage 文件。
- Deep Learning、Track B 模型及 Optimization 僅在其前置條件滿足後加入。

## 10. Current Priority

```text
Track A: Complete Ablation + Error Analysis
        ↓
Track A Research Summary

Track B: Continue Multi-day Snapshot Collection
        ↓
Coverage / Gap Audit
        ↓
Availability Baseline Only When Data Is Ready
```

目前不要優先進行：Deep Learning、Optimization、重做 Streamlit，或把歷史 Dashboard 改稱 Live prediction。
