# Stage 12：Feature-group Ablation 與完整 Error Analysis

## 1. 階段目標與邊界

本階段完成 Track A 傳統模型研究鏈中尚缺的 feature-group ablation 與統一情境誤差分析。Target、top-100 station scope、2023 時序切分與 HGB 主模型定義均保持不變；沒有重訓 Track B、建立新 live prediction、Random Forest、Deep Learning 或 Optimization。

研究問題仍是：

> 預測指定站點在目標小時的轉乘相關借車量。

這不是所有 YouBike 需求，也不是 30／60 分鐘後可用車數或缺車風險。

## 2. 評估規則

- Train：2023-01-08～2023-09-30，638,098 rows。
- Validation：2023-10-01～2023-11-30，146,400 rows。
- Test：2023-12-01～2023-12-31，74,282 rows。
- 站點仍只依 training-period borrowing activity 選出 100 站。
- 使用 Stage 7 已由 validation 選出的 HGB `deeper` 參數；ablation 不重新調參。
- 每個 variant 先以 train fit、validation evaluate，再以 train + validation fit、test evaluate。
- Test 差異只用來描述 feature dependence，不拿來選參數或宣稱因果。
- 完整模型精確重現既有 holdout：MAE 1.575、RMSE 2.549、R² 0.794。

## 3. Feature groups

Leave-one-group-out ablation 每次只移除一個資訊群：

| Group | Features |
|---|---|
| Station identity | `station_name` |
| Calendar | hour／weekday／month sine-cosine、`is_weekend` |
| Immediate history | `borrow_lag_1h`、`return_lag_1h` |
| Daily history | `borrow_lag_24h`、`borrow_rolling_mean_24h` |
| Weekly history | `borrow_lag_168h` |
| Weather | temperature、humidity、precipitation、wind、`is_raining` |

另建立 `full_plus_official_day_off`，只在完整模型上增加官方政府機關放假日 flag。

## 4. 官方 holiday 定義

Holiday 來源為行政院人事行政總處提供的「112 年中華民國政府行政機關辦公日曆表」，由政府資料開放平臺資料集 14718 取得。原始 CSV 共 365 rows，`是否放假=2` 表示放假、`0` 表示上班；來源 URL、SHA-256、17 個 weekday days off 與 6 個 weekend makeup workdays 固定記錄於 `config/track_a_analysis.json`。

這個 flag 是政府行政機關辦公日的可重現代理變數，不代表所有民間企業、學校或個人行程。12 月 holdout 沒有 weekday day off 或 weekend makeup workday，因此 test 只能比較一般工作日與週末，不能充分評估特殊連假。

## 5. Ablation 結果

### 2023 年 12 月 holdout

| Variant | MAE | Δ MAE vs full | MAE change | RMSE | R² |
|---|---:|---:|---:|---:|---:|
| Full HGB | **1.575** | — | — | 2.549 | 0.794 |
| Full + official day off | 1.581 | +0.007 | +0.43% | **2.536** | **0.796** |
| Without weekly history | 1.586 | +0.011 | +0.70% | 2.567 | 0.791 |
| Without weather | 1.601 | +0.027 | +1.69% | 2.567 | 0.791 |
| Without immediate history | 1.610 | +0.035 | +2.22% | 2.618 | 0.783 |
| Without station identity | 1.619 | +0.044 | +2.80% | 2.625 | 0.782 |
| Without daily history | 1.626 | +0.051 | +3.25% | 2.619 | 0.783 |
| Without calendar | 1.739 | +0.164 | +10.44% | 2.851 | 0.743 |

Validation 的重要性順序大致一致：移除 calendar、daily history、station identity、immediate history 的退化最大。Weather 在 validation／test 的 MAE 退化分別為 1.27%／1.69%，再次支持「天氣有小幅增量，但主要訊號仍是週期時間、歷史需求與站點」。Weekly history 的額外訊號最小但仍為正。

Official day-off feature 在 validation MAE 改善 0.24%，但 test MAE 惡化 0.43%；test RMSE 雖小幅改善，方向並不一致，而且 12 月沒有特殊 weekday holidays。故本階段不替換既有 HGB feature schema，也不宣稱 holiday feature 已證實有效。

## 6. 完整 Error Analysis

### 時段與尖離峰

| Segment | Rows | Average actual | MAE |
|---|---:|---:|---:|
| Evening peak（16–19） | 12,371 | 8.192 | 2.631 |
| Morning peak（07–09） | 9,300 | 5.988 | 2.267 |
| Off peak | 52,611 | 2.678 | 1.204 |

最高小時仍為 18:00（MAE 3.012），其次 17:00（2.880）與 08:00（2.700）。模型對通勤尖峰的困難在 Ridge、HGB、XGBoost 與本階段完整分析中一致。

### Station demand tiers

需求層級只用 training-period 每站平均 target 排序後分三組，沒有使用 test target 選站或分級。

| Tier | Rows | Average actual | MAE | P90 absolute error |
|---|---:|---:|---:|---:|
| High | 25,254 | 7.010 | 2.255 | 5.468 |
| Medium | 24,518 | 3.031 | 1.384 | 3.333 |
| Low | 24,510 | 1.901 | 1.065 | 2.551 |

最高 station MAE 仍為「捷運公館站（2 號出口）」5.294；其次包括捷運公館站（3 號出口）、捷運芝山站（2 號出口）_1 與捷運劍潭站（2 號出口）。高需求站的絕對誤差明顯較大，但本結果不等同相對誤差或服務風險。

### Actual-demand bands

- Actual demand ≥10 的 8,578 rows：MAE 4.231，平均 signed error（actual − prediction）+2.581，顯示高需求事件整體偏向低估。
- Actual 4–9：MAE 1.927。
- Actual 1–3：MAE 1.303。
- Zero-demand rows 的完整結果保存在 context CSV，不以單一摘要取代。

### Weather contexts

Rain intensity threshold 只從 training 中有雨小時的 precipitation median 推導。Test 中 dry MAE 1.664、低於 training rainy median 的時段 1.579、較高雨量時段 1.052。較高雨量時段同時有較低 average actual（1.827），因此不能解讀成「雨越大模型越準」或雨量具有因果效果。

Temperature bands 同樣使用 training q25／q75；warm-training-quartile 在 12 月只有 1,100 rows，MAE 2.176，樣本與需求組成不同，僅作監控切片。

### Holiday／day type

- Regular workday：50,400 rows，MAE 1.624。
- Weekend day off：23,882 rows，MAE 1.470。
- 12 月 test 無 weekday day off 與 weekend makeup workday，不能完成特殊連假的 test 比較。

### Worst cases 與 daily stability

- 最大個別誤差為 2023-12-11 08:00「捷運芝山站（2 號出口）_1」，actual 19、prediction 60.122，absolute error 41.122。
- 最大誤差同時包含高估與低估，且多數落在高需求站與尖峰，但不能在沒有事件／交通資料時推論原因。
- 最高 daily MAE 是 2023-12-11：1.819；完整 31 日報告保存在 `track_a_daily_errors.csv`。

## 7. 產出

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

## 8. 測試與重現

```bash
python src/run_track_a_analysis.py
python -m unittest discover -s tests -v
```

完整 repository tests 為 48 passed。分析 runner 實際完成 8 variants、16 次固定參數 fit，並重現原 HGB holdout metrics。

## 9. 結論與下一步

Track A 的 feature-group ablation 與完整情境 error analysis 已完成。Calendar 是最關鍵的群組；daily、station、immediate history 依序提供較大增量，weather 與 weekly history 提供較小但一致的增量。Official holiday flag 尚無一致證據，不加入主模型。

下一步不是再堆模型。應先整理 Track A research summary；Track B 雲端 collector 同時持續累積，滿 7 天後才做 coverage／gap audit。Deep Learning 與 Optimization 仍延後。
