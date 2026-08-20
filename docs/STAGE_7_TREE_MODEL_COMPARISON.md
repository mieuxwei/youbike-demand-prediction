# Stage 7：樹模型比較與 Rolling-origin 評估

## 本階段目的

Stage 6 已證明線性 Ridge 優於 naive baseline。本階段在完全相同的 top-100 站點、特徵定義與時間切分下，加入可處理非線性關係的 Histogram Gradient Boosting Regressor（HGB），並用 rolling-origin folds 檢查結果是否穩定。

選擇 HGB 而不是直接加入 XGBoost，是因為目前約 86 萬筆訓練資料可直接使用 scikit-learn 的高效率 histogram tree，不需要新增外部套件。這仍屬於 gradient-boosted decision tree，而不是 Deep Learning。

## 公平比較原則

- target、100 個站點與 train／validation／test 和 Stage 6 完全一致。
- 站點仍只依 1–9 月 training activity 排名。
- 兩組候選參數只使用 10–11 月 validation MAE 選擇。
- 選定參數後才使用 train + validation 重訓，最後評估 12 月 test。
- 有／無天氣模型分開比較，避免把演算法改變誤認成天氣效果。
- loss 使用 Poisson，符合非負計數 target；輸出仍以 0 為下限。

## 候選模型

| Candidate | Learning rate | Iterations | Max leaves | Min leaf rows |
|---|---:|---:|---:|---:|
| compact | 0.08 | 150 | 31 | 50 |
| deeper | 0.05 | 200 | 63 | 40 |

有天氣與無天氣版本都由 `deeper` 取得較低 validation MAE，因此最終 test 使用該設定。

## 12 月 Holdout 結果

| Model | MAE | RMSE | R² |
|---|---:|---:|---:|
| 前一週同時段 | 2.176 | 3.701 | 0.566 |
| Ridge＋天氣 | 1.793 | 2.889 | 0.736 |
| HGB，不含天氣 | 1.601 | 2.567 | 0.791 |
| HGB＋天氣 | **1.575** | **2.549** | **0.794** |

HGB＋天氣相較 Ridge＋天氣的 MAE 改善約 12.2%，相較前一週 baseline 改善約 27.6%。HGB 加入天氣後相較無天氣版本再改善約 1.7%，仍是小幅但一致的增量。

## Rolling-origin 結果

| Fold | Validation period | MAE | RMSE | R² |
|---|---|---:|---:|---:|
| 1 | 10/01–10/20 | 1.636 | 2.716 | 0.762 |
| 2 | 10/21–11/10 | 1.592 | 2.573 | 0.818 |
| 3 | 11/11–11/30 | 1.606 | 2.608 | 0.797 |

三段平均 MAE 為 1.611，範圍 1.592–1.636；平均 R² 為 0.793。各 fold 都先擴張訓練資料，再預測後續不重疊期間，因此結果比單一 validation 切分更可靠。

## Permutation importance

在固定抽取的 10,000 筆 test rows 上，打亂特徵後的 MAE 增量前幾名為：

1. `hour_cos`：+0.507
2. `borrow_lag_1h`：+0.408
3. `hour_sin`：+0.230
4. `station_name`：+0.188
5. `borrow_lag_168h`：+0.176
6. `borrow_rolling_mean_24h`：+0.149

天氣中 precipitation（+0.032）與 humidity（+0.023）較有訊號；單一 `is_raining` flag 在此模型中的增量為 0，表示連續天氣量比二元旗標更有用。Permutation importance 只能表示模型依賴程度，不能解讀為因果影響。

由於 test set 只有 12 月，`month_sin` 與 `month_cos` 在測試樣本中為常數，因此其 permutation importance 為 0 是評估設計造成，不能據此判斷月份在跨月預測中沒有價值。

## 誤差分析

- 18:00 仍是最高誤差時段，MAE 約 3.012；17:00 約 2.880、08:00 約 2.700。
- 捷運公館站（2 號出口）仍是最高誤差站，MAE 約 5.294，但已低於 Ridge 的 6.045。
- 樹模型明顯改善尖峰與高需求站，但尚未完全解決突發需求。

## 主要產出

- `config/tree_model.json`
- `src/tree_model.py`
- `src/train_tree_models.py`
- `models/hist_gradient_boosting.joblib`
- `models/hist_gradient_boosting_weather.joblib`
- `results/tree_model_metrics.csv`
- `results/tree_model_tuning.csv`
- `results/tree_rolling_origin_metrics.csv`
- `results/tree_permutation_importance.csv`
- `results/tree_station_errors.csv`
- `results/tree_hour_errors.csv`
- `results/model_comparison_metrics.csv`
- `notebooks/07_tree_model_comparison.ipynb`

## 重現方式

```bash
python src/train_tree_models.py
python -m unittest discover -s tests -v
```

## 限制與下一步

- 結果仍只代表 100 個站點的 hourly transfer-related demand。
- 使用事後實際天氣；線上推論必須改用當時可取得的 forecast。
- 全年只有 2023 一年，仍無法驗證跨年度穩定性。
- 下一步應建立可重現的單一時間點／批次推論介面、模型卡與輸入驗證。
- 在這些工程與評估工作完成以前，仍不進入 LSTM 或調度最佳化。
