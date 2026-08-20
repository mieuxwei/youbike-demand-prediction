# Stage 3 說明：歷史蒐集與時間序列特徵工程

## 1. 本階段目標

Stage 2 已能下載與清理單一快照；Stage 3 將流程擴充為：

```text
固定間隔連續蒐集
        ↓
多日站點時間序列
        ↓
只使用當下與過去的 Predictor Features
        ↓
獨立產生未來 30／60 分鐘 Target Labels
        ↓
Feature Coverage 檢查
        ↓
資料足夠後才進入 Machine Learning
```

本階段完成蒐集工具與特徵管線，但「多日歷史資料」仍必須隨真實時間累積，不能用複製快照或虛構資料取代。

## 2. 新增的主要檔案

| 檔案 | 用途 |
|---|---|
| `src/collect_history.py` | 依指定間隔連續下載固定份數的快照 |
| `src/features.py` | 建立時間、lag、rolling 與 future target 欄位 |
| `src/build_features.py` | 從 raw snapshots 重新產生完整 feature table |
| `notebooks/03_feature_engineering.ipynb` | 展示特徵工程與 coverage 圖表 |
| `tests/test_history_collector.py` | 測試蒐集次數、間隔與錯誤恢復 |
| `tests/test_features.py` | 測試 lag、rolling、target 與 leakage 防護 |
| `results/feature_coverage.csv` | 記錄每個特徵目前有多少真實可用資料 |

## 3. 如何累積歷史快照

先啟用專案環境：

```bash
source .venv/bin/activate
```

### 一小時測試

每 5 分鐘蒐集一次，共 12 份：

```bash
python src/collect_history.py --count 12 --interval-minutes 5
```

### 約一天資料

```bash
python src/collect_history.py --count 288 --interval-minutes 5
```

程式會立即蒐集第一份，之後依指定間隔繼續。單次網路或 API 錯誤會被記錄，但不會中止後續嘗試；按 `Control+C` 可安全停止。

執行期間電腦必須保持開機、網路連線，Terminal 也不能關閉。若電腦休眠，資料時間軸會出現缺口。因此長期蒐集最終應放在穩定運行的設備或雲端排程上。

## 4. Predictor Features

### 日曆特徵

- `hour`
- `day_of_week`：星期一為 0，星期日為 6
- `month`
- `is_weekend`
- `is_rush_hour`：07:00–09:59 或 17:00–19:59

時間使用 `Asia/Taipei`。另外加入 hour 與 weekday 的 sine／cosine 週期編碼，使模型理解 23:00 與 00:00、星期日與星期一在週期上相鄰。

### Lag 特徵

- `available_bikes_lag_15m`
- `available_bikes_lag_30m`
- `available_bikes_lag_60m`

每筆資料先計算理想的過去時間，再用 backward matching 尋找該時間以前、容許誤差 2 分鐘內的觀測。它永遠不會為了補 lag 而讀取理想時間之後的資料。

`lag_*_actual_minutes` 保留實際匹配間隔，方便日後排除間隔偏差過大的資料。

### Rolling 特徵

- 過去 30／60 分鐘平均可借車數
- 過去 30／60 分鐘有效觀測數

Rolling window 使用 `closed="left"`，表示不包含當前列，避免把正在預測時刻的值錯當成歷史平均的一部分。

## 5. Target Labels

- `target_available_bikes_30m`
- `target_available_bikes_60m`

Target 使用 forward matching 尋找未來指定時間的真實觀測。Target 欄位只作為監督式學習標籤，不能放入 predictor feature matrix，否則會發生嚴重的 future leakage。

如果未來沒有符合時間與容許誤差的快照，target 保持空值。管線不會內插或製造未來答案。

## 6. 目前真實 Coverage

固定樣本共有 2 個快照、3,580 列：

| 特徵 | 可用列 | Coverage |
|---|---:|---:|
| Calendar features | 3,580 | 100% |
| 15-minute lag | 1,761 | 49.19% |
| 30-minute lag | 0 | 0% |
| 60-minute lag | 0 | 0% |
| Past 30/60-minute rolling history | 1,761 | 49.19% |
| 30-minute future target | 0 | 0% |
| 60-minute future target | 0 | 0% |

這些結果是合理且重要的品質訊號：目前資料可以驗證 15 分鐘對齊，但還不能建立 30／60 分鐘預測資料集。

## 7. 如何重建 Features

```bash
python src/build_features.py
```

產物：

- `data/processed/youbike_features.csv`：完整 feature table，本機產物、不加入 Git。
- `results/feature_coverage.csv`：小型 coverage 報告，加入 Git 供審查。

執行全部測試：

```bash
python -m unittest discover -s tests -v
```

目前共有 13 項測試，涵蓋資料蒐集、清理、時間對齊與 leakage 防護。

## 8. 何時才能開始 Machine Learning

建議至少先取得：

- 連續 7 天以上，且同時包含工作日與週末。
- 5 分鐘左右的固定頻率。
- 可量化並處理的資料缺口。
- 30／60 分鐘 target 有足夠 coverage。

若時間允許，14–28 天會比 7 天更能涵蓋週間差異。這是最低資料規劃建議，不代表資料一達門檻就保證模型有效；開始建模前仍需完成擴充 EDA 與時間切分設計。

## 9. 目前不能宣稱的成果

- 尚未建立 Linear Regression、Random Forest 或 XGBoost。
- 尚未產生 MAE、RMSE 或 R²。
- 尚未證明車輛淨變化等於實際租借需求。
- 尚未證明 15／30／60 分鐘特徵能改善預測。
- 尚未開始 Deep Learning 或 Optimization。

## 10. 作品集口頭說明範例

> 我把官方即時 API 擴充為固定間隔的歷史蒐集流程，再建立時間序列特徵管線。Lag features 只向過去對齊，rolling windows 排除當前觀測，future targets 則在獨立步驟向未來對齊，避免資料洩漏。Feature coverage 報告目前誠實顯示只有 15 分鐘 lag 有資料，30 與 60 分鐘 targets 尚未形成，因此我沒有提前訓練模型，而是先持續累積跨工作日與週末的真實歷史資料。
