# Stage 10：XGBoost 公平比較

## 階段目標

依照 Current-State v2 的 Track A 優先順序，在不改變 target、站點、特徵或時間切分的前提下補做 XGBoost，確認知名的 gradient-boosted tree 實作是否優於現有 HGB。研究不預設 XGBoost 一定較好，test set 也不參與調參。

## 固定實驗範圍

- Target：每站每小時的轉乘相關借車量。
- Station scope：只使用 2023 年 1–9 月 training activity 選出的 100 個站點。
- Train：2023-01-08 至 2023-09-30，共 638,098 rows。
- Validation：2023-10-01 至 2023-11-30，共 146,400 rows。
- Test：2023-12-01 至 2023-12-31，共 74,282 rows。
- Features：與含天氣 HGB 相同的 station、calendar、past-only lag／rolling 與 weather features。
- Objective：`count:poisson`。
- Tree method：`hist`。
- Evaluation：MAE、RMSE、R²，以及三段 expanding-window rolling-origin validation。

站點使用 sparse one-hot encoding；數值特徵維持原值。這與 HGB 的 station ordinal categorical encoding 不同，但輸入資訊、資料列與評估期間完全相同，沒有額外加入 XGBoost 專用資料。

## Validation-only 候選比較

只建立兩組受控候選，避免一開始做大量 tuning：

| Candidate | Trees | Learning rate | Max depth | Min child weight | L1 | L2 | Validation MAE |
|---|---:|---:|---:|---:|---:|---:|---:|
| compact | 300 | 0.05 | 6 | 20 | 0.0 | 2.0 | 1.665 |
| regularized | 500 | 0.03 | 8 | 30 | 0.1 | 5.0 | **1.646** |

兩組皆使用 `subsample=0.85` 與 `colsample_bytree=0.9`。`regularized` 只因 validation MAE 較低而獲選；12 月 test 在候選選定以前沒有被使用。

## 2023 年 12 月 Holdout 結果

| Model | MAE | RMSE | R² |
|---|---:|---:|---:|
| Previous week, same hour | 2.176 | 3.701 | 0.566 |
| Ridge + weather | 1.793 | 2.889 | 0.736 |
| XGBoost + weather | 1.597 | 2.580 | 0.789 |
| HGB + weather | **1.575** | **2.549** | **0.794** |

XGBoost 相較含天氣 Ridge 的 MAE 改善約 10.9%，證明非線性 boosting 的優勢；但 HGB 的 MAE 又比 XGBoost 低約 1.4%。因此專案忠實保留 HGB 為 Track A 主模型，不因 XGBoost 名稱較知名就替換表現更好的模型。

## Rolling-origin 結果

| Fold | Validation period | MAE | RMSE | R² |
|---|---|---:|---:|---:|
| 1 | 10/01–10/20 | 1.673 | 2.787 | 0.750 |
| 2 | 10/21–11/10 | 1.624 | 2.609 | 0.813 |
| 3 | 11/11–11/30 | 1.644 | 2.663 | 0.789 |

三段平均 MAE 為 1.647，範圍 1.624–1.673；同樣略高於 HGB 的平均 1.611。單一 12 月 holdout 與多段 rolling-origin 得到一致結論。

## Permutation importance

XGBoost 在固定 10,000 筆 test sample 的主要訊號為：

1. `borrow_lag_1h`：MAE +0.490
2. `hour_cos`：+0.306
3. `borrow_lag_168h`：+0.276
4. `borrow_lag_24h`：+0.221
5. `borrow_rolling_mean_24h`：+0.220
6. `hour_sin`：+0.163

降雨量的增幅為 +0.027，再次顯示天氣有小幅訊號，但前一小時、前一週、前一天與時間週期才是主要來源。Permutation importance 代表模型依賴程度，不代表因果關係。

## Worst cases 與誤差觀察

- 最高站點 MAE 仍是捷運公館站（2 號出口），約 5.172。
- 18:00 MAE 約 3.102、17:00 約 2.903、08:00 約 2.721。
- 最大個別誤差同時包含明顯低估與高估，集中出現於部分高需求站與尖峰時段。
- `results/xgboost_worst_cases.csv` 保存 100 筆最大 absolute error，供後續情境化 error analysis 使用。

目前沒有事件或交通異常資料，因此不能僅依 worst cases 推論某一天的失準原因。

## 主要產出

- `config/xgboost_model.json`
- `src/xgboost_model.py`
- `src/train_xgboost.py`
- `models/xgboost_weather.joblib`
- `models/xgboost_weather.metadata.json`
- `results/xgboost_metrics.csv`
- `results/xgboost_tuning.csv`
- `results/xgboost_rolling_origin_metrics.csv`
- `results/xgboost_permutation_importance.csv`
- `results/xgboost_station_errors.csv`
- `results/xgboost_hour_errors.csv`
- `results/xgboost_worst_cases.csv`
- `notebooks/09_xgboost_comparison.ipynb`

## 重現方式

macOS 必須先提供 OpenMP runtime；XGBoost 官方安裝文件建議：

```bash
brew install libomp
```

接著安裝專案依賴並執行：

```bash
python -m pip install -r requirements.txt
python src/train_xgboost.py
python -m unittest discover -s tests -v
```

## 結論與下一步

XGBoost 完成了新版計畫要求的模型比較，但沒有超越 HGB。Track A 下一步不再增加 Random Forest 或繼續大規模 tuning，而是完成 feature-group ablation、holiday 定義與情境化 error analysis，再撰寫研究摘要。
