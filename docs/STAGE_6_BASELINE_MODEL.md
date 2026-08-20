# Stage 6：時間序列 Hourly Baseline Model

## 研究目標

本階段第一次建立正式且可重現的模型評估。預測目標為：

> 指定站點在目標小時的「轉乘相關借車量」。

這不是所有 YouBike 使用需求，也不是未來 30／60 分鐘可用車數。模型範圍限定為訓練期借車活動最高的 100 個站點，避免一開始就把數千個低活動或改名站點混入實驗。

## 防止資料洩漏

- 站點排名只使用 2023 年 1–9 月訓練資料。
- 特徵只使用目標小時以前的 1、24、168 小時需求。
- 24 小時 rolling mean 先 shift 1 小時，排除目標小時本身。
- 1–9 月為 training、10–11 月為 validation、12 月為 test。
- Ridge alpha 只在 validation 選擇；選定後以 training + validation 重訓，test 只評估一次。
- Ridge 若產生負需求預測，統一 floor 為 0。

## 資料集

| Split | Rows | Stations | Period | 平均目標 | 零需求比例 |
|---|---:|---:|---|---:|---:|
| Train | 638,098 | 100 | 2023-01-08～2023-09-30 | 5.244 | 28.65% |
| Validation | 146,400 | 100 | 2023-10-01～2023-11-30 | 4.140 | 30.78% |
| Test | 74,282 | 100 | 2023-12-01～2023-12-31 | 4.011 | 31.00% |

前 168 小時因無法建立完整一週 lag 而排除。站點活動期間內沒有交易的時數補為 0；站點第一筆與最後一筆活動範圍之外不擅自假設為 0，以免把尚未啟用、停用或改名誤當零需求。

## 模型與特徵

### Naive baselines

1. `persistence_1h`：直接使用前一小時借車量。
2. `seasonal_168h`：使用前一週同星期、同小時借車量。

### Ridge

- station one-hot encoding
- hour／weekday／month sine-cosine
- weekend flag
- borrow lag 1／24／168 小時
- return lag 1 小時
- 過去 24 小時平均借車量
- 天氣版本另加入溫度、濕度、降水、風速與是否下雨

Ridge alpha 候選為 0.1、1、10、100。無天氣版本選到 100；天氣版本選到 0.1。

## 12 月測試結果

| Model | MAE | RMSE | R² |
|---|---:|---:|---:|
| 前一小時 | 2.441 | 4.129 | 0.460 |
| 前一週同時段 | 2.176 | 3.701 | 0.566 |
| Ridge：時間＋歷史 | 1.810 | 2.911 | 0.731 |
| Ridge：時間＋歷史＋天氣 | **1.793** | **2.889** | **0.736** |

含天氣 Ridge 相較前一週 baseline 的 MAE 改善約 17.6%。相較不含天氣 Ridge，MAE 只改善約 0.9%，RMSE 改善約 0.8%。因此可說天氣帶來小幅增量，但主要訊號仍來自站點、週期時間與歷史需求。

這些是實際 2023 年 12 月 holdout 結果，不可外推成全臺北所有 YouBike 需求的表現。

## 誤差分析

- 測試集 18:00 的 MAE 最高，約 3.395；17:00 約 3.240，08:00 約 3.038。
- 「捷運公館站（2 號出口）」MAE 約 6.045，是目前誤差最高站點。
- 高需求通勤站與尖峰時段仍明顯比離峰難預測。
- 目前使用歷史實際天氣；若部署成未來預測，必須改接對應預測時點可取得的天氣預報，否則會高估線上表現。

## 產出

- `config/baseline_model.json`：模型範圍、切分與 alpha 設定
- `src/baseline_model.py`：資料集、lag、切分、模型與評估函式
- `src/train_baseline.py`：完整訓練與報告流程
- `models/ridge_time_history.joblib`
- `models/ridge_time_history_weather.joblib`
- `results/baseline_metrics.csv`
- `results/baseline_ridge_tuning.csv`
- `results/baseline_split_summary.csv`
- `results/baseline_station_errors.csv`
- `results/baseline_hour_errors.csv`
- `notebooks/06_baseline_model.ipynb`

## 重現方式

先完成 Stage 5 的全年需求與天氣資料，再執行：

```bash
python src/train_baseline.py
python -m unittest discover -s tests -v
```

## 下一步

下一階段可比較 Random Forest 或梯度提升樹，並特別檢查：

1. 非線性模型能否降低通勤尖峰誤差。
2. 天氣增量是否在樹模型中仍然存在。
3. 高需求站與一般站的誤差差異。
4. 使用 rolling-origin validation 確認結果不是單一月份偶然現象。

此時仍不應開始 LSTM 或車輛調度最佳化。
