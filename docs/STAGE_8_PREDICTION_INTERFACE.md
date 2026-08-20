# Stage 8：可重現預測介面與 Model Card

## 本階段完成內容

Stage 7 已得到最佳 HGB 模型，本階段把研究程式轉成可呼叫的預測流程。使用者提供目標小時、更新至前一小時的 station-hour demand，以及目標小時天氣，就能輸出 100 個模型站點的預測借車量與排名。

## 使用方式

歷史回測範例：

```bash
python src/predict_hourly.py \
  --target-time 2023-12-31T18:00:00+08:00 \
  --include-actual \
  --output results/example_hourly_predictions.csv
```

正式預測不要加 `--include-actual`。輸入檔仍使用預設路徑，也可透過 `--demand-input`、`--weather-input`、`--model`、`--metadata` 與 `--output` 替換。

## 強制輸入檢查

1. Target 必須對齊整點並轉為 Asia/Taipei。
2. Demand 必須包含 target 前 168 小時至前 1 小時的資料範圍。
3. 100 個模型站點都必須出現在 demand history。
4. Demand 不得有重複 station-hour。
5. Weather 必須恰好有一筆 target-hour row。
6. Feature 欄位與順序必須完全符合 metadata。
7. Model artifact SHA-256 必須符合 metadata，才會載入 joblib。

站點活動表沒有出現的內部小時會補成 0。目標小時的實際 demand 即使存在於歷史 CSV，也只會在預測完成後、使用 `--include-actual` 時附加，不會進入模型特徵。

## 輸出欄位

- `prediction_rank`
- `target_time`
- `station_name`
- `predicted_borrow_count`
- 歷史回測選配：`actual_borrow_count`、`absolute_error`

## 範例結果

2023-12-31 18:00 是 12 月 holdout 中的一個週末尖峰小時：

| Rank | Station | Prediction | Actual |
|---:|---|---:|---:|
| 1 | 捷運公館站（2 號出口） | 27.83 | 24 |
| 2 | 捷運芝山站（2 號出口）_1 | 18.14 | 20 |
| 3 | 捷運龍山寺站（1 號出口） | 16.90 | 22 |
| 4 | 捷運中山國中站 | 16.19 | 13 |
| 5 | 捷運科技大樓站 | 16.03 | 15 |

該單一時段 100 站 MAE 為 2.472，高於整個 12 月 test MAE 1.575。單點範例的用途是展示介面與輸出，不應取代完整 holdout 指標。

## 新增程式與產出

- `src/prediction.py`：feature construction、checksum、預測與歷史 actual
- `src/predict_hourly.py`：CLI
- `models/*.metadata.json`：模型 schema、scope、版本、指標與 checksum
- `results/example_hourly_predictions.csv`
- `docs/MODEL_CARD.md`
- `notebooks/08_prediction_demo.ipynb`

## 真正未來預測的必要條件

目前版本能可靠重現 2023 歷史 backtest。若要預測新的未來小時，必須先：

1. 更新同一 target 定義的 transfer-demand station-hour 歷史至 target 前一小時。
2. 提供 target hour 當時可取得的 weather forecast，不能使用事後觀測。
3. 確認站名與 metadata 中的 100 站一致。
4. 監控資料時間戳記與缺漏，不可把尚未更新的資料誤當 0。

## 下一步

下一階段可建立簡單的批次 backtest／展示頁面，讓使用者選擇歷史小時並查看站點排名、實際值與誤差。短期 availability 模型仍需先累積至少 7 天即時快照。
