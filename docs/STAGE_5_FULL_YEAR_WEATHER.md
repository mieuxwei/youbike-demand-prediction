# Stage 5：2023 全年歷史需求與天氣整合

## 本階段完成內容

本階段把原本只處理 2023 年 1 月的官方轉乘 YouBike 流程擴充為全年 12 個月份，並加入每小時歷史天氣。目的不是直接宣稱預測成果，而是建立可供下一階段 Baseline Model 使用、來源與限制清楚的 station-hour 資料。

## 資料來源與範圍

### YouBike 歷史需求

- 來源：臺北市政府交通局「臺北市轉乘 YouBike 租借資料」
- 期間：2023-01-01 至 2023-12-31
- 筆數：7,388,479 筆轉乘相關旅次
- 時間粒度：小時
- 產出：4,670,320 筆有活動的站點－小時需求列

這份資料只包含與公車或捷運轉乘相關的 YouBike 旅次，不代表所有 YouBike 使用者，也不能取代自行累積的即時站點快照。

### 天氣

- 來源：Open-Meteo Historical Weather API
- 期間：2023 全年，共 8,760 小時
- 欄位：溫度、相對濕度、降水量、10 公尺風速、weather code
- 需求資料時間匹配率：100%

本階段選擇 Open-Meteo，是因為可用設定檔重現、下載不需將 API Key 寫入專案。資料屬於臺北單一參考點的歷史再分析格點值；API 實際回傳的最近格點約為北緯 25.06151、東經 121.5194，不是每個 YouBike 站點的現地氣象站觀測。中央氣象署資料可在後續作為實測驗證來源。

## 資料品質決策

全年官方交易資料共有 7 個缺漏站名：1 個借車站、6 個還車站。管線不把缺漏值改成虛構站名，也不刪除整筆旅次；缺少借車站時仍保留還車事件，缺少還車站時仍保留借車事件。

另有 16,699 筆「超出第一筆的完全相同列」。因原始資料沒有 ride ID，不可能安全判定是重複上傳或不同使用者在同一小時完成相同路線，因此沿用 Stage 4 的原則：標記並揭露，但不擅自刪除。

## 延伸 EDA 發現

- 全年平日平均每天 21,952.1 筆轉乘相關旅次，週末平均 16,008.8 筆。
- 平日最高峰為 18:00，平均每天約 2,331.1 筆；週末最高峰為 17:00，平均每天約 1,346.2 筆。
- 月平均日需求最高為 5 月 26,106.2 筆，最低為 8 月 16,311.4 筆，顯示季節與月份不能忽略。
- 不控制時間結構時，雨時每小時平均借車量約 802.0 筆，無雨約 999.3 筆。
- 為降低平假日與小時組成差異，改在相同「平日／週末 × 小時」層內比較 06:00–23:00；36 個可比較 strata 的加權雨天差異約為 -21.6%，中位數約為 -22.4%。

雨天結果只是描述性關聯，仍可能受到月份、節日、颱風、事件與溫度等混雜因素影響，不能解讀成因果關係或模型改善幅度。

## 可重現執行方式

```bash
python src/download_historical.py --month all
python src/prepare_historical_collection.py
python src/download_weather.py
python src/prepare_weather.py
python -m unittest discover -s tests -v
```

大型原始與處理後檔案由 `.gitignore` 排除；Git 保存來源 registry、處理程式、測試、Notebook 與小型摘要報告。

## 主要產出

- `config/historical_sources.json`：12 個官方月份來源
- `config/weather_source.json`：天氣位置、期間與欄位設定
- `src/prepare_historical_collection.py`：逐月處理後合併，避免同時載入全年交易
- `src/download_weather.py`、`src/weather_pipeline.py`、`src/prepare_weather.py`
- `results/historical_monthly_summary.csv`
- `results/weather_quality_summary.csv`
- `results/weather_demand_summary.csv`
- `results/weather_rain_hour_profile.csv`
- `notebooks/05_weather_integration.ipynb`

## 下一階段

下一步可建立可解釋的 hourly baseline。建議先預測「站點下一小時轉乘借車量」，採時間順序 train／validation／test split，並依序比較：

1. 同站前一小時或同星期同小時的 naive baseline。
2. 時間＋站點特徵的線性模型。
3. 加入天氣後的線性模型，確認天氣是否真的改善 MAE／RMSE。

短期 30／60 分鐘可用車數預測仍需要自行蒐集至少 7 天即時快照；不能用 hourly 轉乘旅次冒充該 target。
