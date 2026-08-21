# Stage 13：Track A 完整研究成果總結

## 1. Executive summary

Track A 已完成一條可重現、具時間序列防洩漏控制的歷史轉乘需求研究鏈。研究以 2023 年官方「轉乘相關」YouBike 旅次為基礎，預測指定站點在指定小時的借車量；它不代表所有 YouBike 旅次，也不是即時可用車、缺車風險或調度量預測。

在訓練期選出的 100 個高需求站點上，使用 1–9 月訓練、10–11 月驗證、12 月 holdout test。含天氣的 Histogram Gradient Boosting（HGB）為目前主模型，12 月結果為 MAE 1.575、RMSE 2.549、R² 0.794。它相較前一小時 baseline、前一週同時段 baseline 與含天氣 Ridge 的 MAE 分別降低約 35.5%、27.6% 與 12.2%；也小幅優於相同資料範圍的 XGBoost。

三段 expanding-window rolling-origin validation 的 HGB MAE 為 1.592–1.636，平均 1.611，支持主結論不只來自單一 holdout 月份。Feature-group ablation 顯示 calendar 是最重要的資訊群；daily history、station identity 與 immediate history 次之，weather 與 weekly history則提供較小但一致的增量。

模型的主要風險集中在通勤尖峰、高需求站與高實際需求事件。Evening peak MAE 為 2.631，actual demand ≥10 的資料列 MAE 為 4.231，且整體偏向低估。這表示主模型適合做歷史需求研究、模型比較與回測展示，但不能直接用於即時庫存風險或車輛調度。

## 2. 研究問題與成果邊界

### 研究問題

> 能否用站點、週期時間、過去需求與天氣資訊，預測指定站點在某小時的轉乘相關借車量？

### Target

- 欄位：`borrow_count`。
- 定義：每站每小時的轉乘相關借車旅次數。
- 粒度：station-hour。
- 輸出限制：模型預測 floor 為 0。

### 可以宣稱

- 已完成 2023 年定義內 top-100 站點的歷史 hourly transfer-demand forecasting。
- 已完成 Naive、Ridge、HGB、XGBoost 公平比較。
- 已完成 chronological holdout、rolling-origin、feature ablation 與完整 error analysis。
- HGB 是目前受控實驗中表現最佳的 Track A 模型。

### 不可宣稱

- 不代表所有臺北 YouBike 旅次或所有站點。
- 不代表 30／60 分鐘後的可借車數。
- 不代表 shortage、full-station risk、surplus 或補車數量。
- 不代表已完成線上 live prediction 或 Optimization。
- 不可把相關性、permutation importance 或 ablation 差異解讀成因果效果。

## 3. 資料與實驗設計

### 3.1 歷史資料

| 項目 | 已驗證內容 |
|---|---|
| 原始期間 | 2023-01-01～2023-12-31，共 12 個月 |
| 轉乘相關旅次 | 7,388,479 筆 |
| 有活動的 station-hour rows | 4,670,320 筆 |
| 天氣 | 8,760 小時，臺北單一參考點 |
| Demand-weather matching | 100% |
| 模型站點 | 只依 training activity 選出的 100 站 |

資料源只涵蓋與公車／捷運轉乘相關的 YouBike 旅次。天氣為 Open-Meteo 歷史再分析資料，不是每站現地觀測，也不是預測當下可取得的 forecast。

### 3.2 時間切分

| Split | Period | Rows | Stations | Average target | Zero-demand rate |
|---|---|---:|---:|---:|---:|
| Train | 2023-01-08～2023-09-30 | 638,098 | 100 | 5.244 | 28.65% |
| Validation | 2023-10-01～2023-11-30 | 146,400 | 100 | 4.140 | 30.78% |
| Test | 2023-12-01～2023-12-31 | 74,282 | 100 | 4.011 | 31.00% |

前 168 小時因缺少完整 weekly lag 而排除。站點活動期間內沒有旅次的時數補為 0；站點活動範圍外不擅自補 0，避免把尚未啟用、停用或改名誤當成零需求。

### 3.3 Leakage controls

- 不使用 random split；所有主要評估均依時間順序。
- Top-100 station selection 只使用 training period。
- `lag_1h`、`lag_24h`、`lag_168h` 只取目標時間以前資料。
- 24 小時 rolling mean 先 shift 一小時，不含目標值。
- Ridge、HGB 與 XGBoost 候選只依 validation 選擇。
- Test 只在候選固定並以 train + validation 重訓後評估。
- Holdout actual 不會進入 predictor matrix，只在預測後用於評估或 backtest 展示。

## 4. 模型與特徵

### 4.1 比較模型

1. Previous-hour persistence。
2. Previous-week same-hour seasonal baseline。
3. Ridge without／with weather。
4. HGB without／with weather。
5. XGBoost with weather。

HGB 主模型使用 Poisson loss、learning rate 0.05、200 iterations、63 max leaves、40 minimum leaf rows 與 L2 regularization 1.0。此 `deeper` candidate 由 validation 選出，Stage 12 ablation 沿用固定參數，沒有用 test 重新調參。

### 4.2 完整特徵

- Station identity：`station_name`。
- Calendar：hour／weekday／month sine-cosine、`is_weekend`。
- Immediate history：`borrow_lag_1h`、`return_lag_1h`。
- Daily history：`borrow_lag_24h`、`borrow_rolling_mean_24h`。
- Weekly history：`borrow_lag_168h`。
- Weather：temperature、humidity、precipitation、wind speed、`is_raining`。

官方政府機關 day-off flag 只作增量實驗；因 validation 與 test 證據方向不一致，未加入主模型。

## 5. Holdout model comparison

所有指標均來自 2023 年 12 月、定義內 100 站、74,282 rows。

| Model | MAE | RMSE | R² | MAE change vs HGB + weather |
|---|---:|---:|---:|---:|
| Previous hour | 2.441 | 4.129 | 0.460 | HGB 低 35.5% |
| Previous week, same hour | 2.176 | 3.701 | 0.566 | HGB 低 27.6% |
| Ridge without weather | 1.810 | 2.911 | 0.731 | HGB 低 13.0% |
| Ridge with weather | 1.793 | 2.889 | 0.736 | HGB 低 12.2% |
| HGB without weather | 1.601 | 2.567 | 0.791 | HGB 低 1.7% |
| **HGB with weather** | **1.575** | **2.549** | **0.794** | **主模型** |
| XGBoost with weather | 1.597 | 2.580 | 0.789 | HGB 低 1.4% |

主要結論：非線性 boosting 明顯優於線性 Ridge；但在相同 target、station scope、features 與 splits 下，XGBoost 沒有超越 HGB，因此不替換主模型。

## 6. 時間外推穩定性

### HGB rolling-origin

| Fold | Validation period | MAE | RMSE | R² |
|---|---|---:|---:|---:|
| 1 | 10/01–10/20 | 1.636 | 2.716 | 0.762 |
| 2 | 10/21–11/10 | 1.592 | 2.573 | 0.818 |
| 3 | 11/11–11/30 | 1.606 | 2.608 | 0.797 |
| **Average** | — | **1.611** | **2.632** | **0.793** |

### XGBoost rolling-origin

XGBoost 三段 MAE 為 1.673、1.624、1.644，平均 1.647。每一段都高於同期間 HGB，與 12 月 holdout 的模型排序一致。這提升了「HGB 是目前主模型」的可信度，但仍不能代替跨年度驗證。

## 7. Feature evidence

### 7.1 Feature-group ablation

固定完整 HGB 後，每次移除一組資訊；下表為 12 月 MAE 相對完整模型的變化。

| Removed group | Test MAE | MAE degradation |
|---|---:|---:|
| Calendar | 1.739 | +10.44% |
| Daily history | 1.626 | +3.25% |
| Station identity | 1.619 | +2.80% |
| Immediate history | 1.610 | +2.22% |
| Weather | 1.601 | +1.69% |
| Weekly history | 1.586 | +0.70% |

Calendar 是最不可替代的群組；歷史需求與站點資訊構成第二層主要訊號。Weather 與 weekly history 的增量較小，但 validation 與 test 都是正向。這些百分比描述模型對資訊群的依賴，不是該資訊對需求的因果效果。

### 7.2 Permutation importance

HGB 的主要 individual signals 是 `hour_cos`、`borrow_lag_1h`、`hour_sin`、`station_name`、`borrow_lag_168h` 與 `borrow_rolling_mean_24h`。降水與濕度有較小增量；單一 `is_raining` flag 沒有額外增量，表示連續天氣量比二元旗標更有資訊。

### 7.3 Official day-off experiment

政府行政機關行事曆 flag 在 validation MAE 改善 0.24%，但 test MAE 惡化 0.43%；test RMSE 則小幅改善。12 月沒有特殊 weekday holiday 或 weekend makeup workday，證據不足且方向不一致，因此不加入主模型。該行事曆也只是政府機關辦公日代理變數，不代表所有企業、學校與旅次目的。

## 8. Complete error analysis

### 8.1 Peak periods

| Segment | Rows | Average actual | MAE |
|---|---:|---:|---:|
| Evening peak（16–19） | 12,371 | 8.192 | 2.631 |
| Morning peak（07–09） | 9,300 | 5.988 | 2.267 |
| Off peak | 52,611 | 2.678 | 1.204 |

最高誤差小時為 18:00（MAE 3.012）、17:00（2.880）與 08:00（2.700）。Ridge、HGB、XGBoost 與完整情境分析都顯示相同尖峰風險。

### 8.2 Station demand tiers

Station tiers 只依 training-period 平均需求分組。

| Tier | Rows | Average actual | MAE | P90 absolute error |
|---|---:|---:|---:|---:|
| High | 25,254 | 7.010 | 2.255 | 5.468 |
| Medium | 24,518 | 3.031 | 1.384 | 3.333 |
| Low | 24,510 | 1.901 | 1.065 | 2.551 |

最高 station MAE 為「捷運公館站（2 號出口）」5.294。高需求站絕對誤差較大，但這不等同於相對誤差或營運服務風險。

### 8.3 Actual-demand bands

- Actual demand ≥10：8,578 rows，MAE 4.231，平均 `actual - prediction` 為 +2.581，74.7% rows 為低估。
- Actual 4–9：MAE 1.927。
- Actual 1–3：MAE 1.303。
- Actual 0：MAE 0.555。

主模型在高需求事件中仍有明顯低估風險。若未來用途對尖峰漏估成本較高，應另行定義加權 loss、quantile／probabilistic output 或尖峰專屬評估；本階段不以 test 結果直接修改模型。

### 8.4 Weather and day type

Dry MAE 為 1.664，較高雨量情境 MAE 為 1.052，但後者平均需求也較低（1.827）。不同情境的需求量與樣本組成不同，不能由此推論「雨越大越容易預測」或雨量的因果效果。

12 月 regular workday MAE 為 1.624、weekend day off 為 1.470；由於沒有特殊 weekday holiday／weekend makeup workday，不能據此評估連假效果。

### 8.5 Worst cases and daily stability

- 最大個別誤差：2023-12-11 08:00，「捷運芝山站（2 號出口）_1」，actual 19、prediction 60.122、absolute error 41.122。
- 最高 daily MAE：2023-12-11，MAE 1.819。
- 沒有 event／transit disruption 資料，不推測個別失準原因。

## 9. Research conclusions

1. **週期時間是核心訊號。** Calendar ablation 造成 10.44% MAE 退化，遠高於其他群組。
2. **歷史需求與站點差異不可忽略。** Daily、immediate history 與 station identity 都有穩定增量。
3. **非線性 boosting 值得保留。** HGB 相較含天氣 Ridge 降低 12.2% MAE。
4. **HGB 是目前最合理主模型。** 它在 holdout 與三段 rolling-origin 都小幅優於 XGBoost。
5. **天氣有效但不是主要來源。** Weather 對 HGB 的 test MAE 增量約 1.69%；真正未來部署必須改用當時可取得的 forecast。
6. **尖峰與高需求事件仍是主要失誤來源。** 整體平均指標不能取代尖峰、高需求站與需求帶監控。
7. **Holiday evidence 尚不足。** 現有代理變數與 test coverage 不支持加入主模型。
8. **Track A 已完成目前計畫內的主要傳統模型研究鏈。** 繼續增加 Random Forest、LSTM 或大規模 tuning 的邊際研究價值低於跨年度驗證與 Track B 資料累積。

## 10. Limitations and validity threats

1. 只有 2023 一年，尚未驗證跨年度穩定性或制度變化。
2. 只含轉乘相關旅次，不能外推到所有 YouBike 使用。
3. 只涵蓋 training activity top-100 站，新站、低需求站與郊區站未被公平評估。
4. 站點名稱用作 identity；更名、拆站或版本變化需要額外治理。
5. 天氣來自單一臺北參考點的歷史再分析，不是站點現地觀測。
6. 真實未來預測需要 weather forecast；事後天氣不能冒充線上輸入。
7. 缺少活動、工程、交通中斷與營運調度等外部事件資料。
8. Absolute-error metrics 會隨需求量增加；不同需求情境應搭配分層解讀。
9. Ablation 與 permutation importance 都不是因果推論。
10. Track A demand 與 Track B availability 是不同 target，不能互相替代。

## 11. Reproducibility and artifacts

主要可重現入口：

```bash
python src/train_baseline.py
python src/train_tree_models.py
python src/train_xgboost.py
python src/run_track_a_analysis.py
python -m unittest discover -s tests -v
```

主要證據：

- 統一模型比較：`results/model_comparison_metrics.csv`
- HGB rolling-origin：`results/tree_rolling_origin_metrics.csv`
- XGBoost rolling-origin：`results/xgboost_rolling_origin_metrics.csv`
- HGB permutation importance：`results/tree_permutation_importance.csv`
- Ablation：`results/track_a_ablation_test_summary.csv`
- Context errors：`results/track_a_error_by_context.csv`
- Station errors：`results/track_a_station_errors_complete.csv`
- Daily errors：`results/track_a_daily_errors.csv`
- Worst cases：`results/track_a_worst_cases.csv`
- 主模型卡：`docs/MODEL_CARD.md`

Model metadata 保存 station scope、feature schema、訓練截止時間、套件版本與 artifact SHA-256；推論入口在載入前驗證 model hash。

## 12. Decision and next stage

Track A 在目前計畫內標記為 **research summary complete／維護狀態**。保留 HGB with weather 為主模型，不新增 Random Forest、LSTM、Optimization，也不把 historical Dashboard 改稱 live prediction。

下一個有效專案里程碑由 Track B 資料成熟度決定：

1. Cloud collector 繼續每 5 分鐘累積資料，不因 Stage 13 停止。
2. 滿 7 天後做第一輪 coverage／gap audit；仍持續蒐集。
3. 14 天後比較平日／週末 coverage。
4. 以 28 天作為第一版 Track B 正式模型的建議最低資料目標。
5. 只有 30／60 分鐘 future targets、缺口與 station coverage 通過稽核後，才建立 Track B baseline。

本階段只整合既有、已驗證結果，沒有重新訓練模型、修改 Dashboard、建立 Track B prediction 或進行 Optimization。
