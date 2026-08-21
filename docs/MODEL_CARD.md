# Model Card：Hourly Transfer-demand HGB

## 模型概覽

- 模型名稱：`hist_gradient_boosting_weather`
- 模型類型：Histogram Gradient Boosting Regressor
- 任務：預測指定站點在目標小時的轉乘相關借車量
- 模型範圍：訓練期借車量最高的 100 個站點
- 輸出：每站非負的預測借車筆數與需求排名
- Artifact：`models/hist_gradient_boosting_weather.joblib`
- Metadata：`models/hist_gradient_boosting_weather.metadata.json`

## Intended Use

適合用於：

- 研究 hourly transfer-related YouBike demand。
- 比較站點與時段的相對需求。
- 產生歷史 backtest 或離線批次預測。
- 作為後續模型、特徵與系統設計的 benchmark。

不適合直接用於：

- 預測全體 YouBike 旅次。
- 預測未來 30／60 分鐘可用車輛數。
- 判斷站點是否即將缺車或滿站。
- 未經額外驗證就產生真實車輛調度決策。
- 取代營運單位的即時監控或人工判斷。

## 訓練與評估資料

- 資料來源：2023 臺北市轉乘 YouBike 租借資料。
- Train：2023-01-08 至 2023-09-30，638,098 rows。
- Validation：2023-10-01 至 2023-11-30，146,400 rows。
- Test：2023-12-01 至 2023-12-31，74,282 rows。
- 站點選擇只使用 training-period borrowing activity。
- 天氣為 Open-Meteo 臺北單一參考點的歷史再分析值。

資料只涵蓋與公車／捷運轉乘相關的旅次，且時間戳記只有 hourly granularity。

## 特徵

- 站點名稱 category
- hour／weekday／month sine-cosine
- weekend flag
- borrow lag 1／24／168 小時
- return lag 1 小時
- 過去 24 小時平均借車量
- 溫度、濕度、降水、風速、是否下雨

推論介面只使用目標小時以前的需求；目標小時實際借車量不會進入特徵。

## 效能

2023 年 12 月 holdout：

| MAE | RMSE | R² |
|---:|---:|---:|
| 1.575 | 2.549 | 0.794 |

三段 rolling-origin validation：

- MAE：1.592–1.636，平均 1.611。
- RMSE：2.573–2.716，平均 2.632。
- R²：0.762–0.818，平均 0.793。

模型在 17:00–18:00 與高需求捷運站的誤差較高。這些指標不能外推至未列入的站點、其他年份或全體 YouBike 旅次。

## Feature-group ablation 與情境誤差

Stage 12 以固定 `deeper` HGB 參數逐一移除資訊群，沒有使用 test 調參。12 月 MAE 退化最大的是 calendar（+10.44%），其次為 daily history（+3.25%）、station identity（+2.80%）與 immediate history（+2.22%）；weather（+1.69%）與 weekly history（+0.70%）提供較小增量。

行政院人事行政總處 2023 政府機關放假日 flag 在 validation MAE 小幅改善 0.24%，但 test MAE 惡化 0.43%，而且 12 月沒有特殊 weekday holidays，因此不加入主模型。

完整情境分析顯示 evening peak MAE 2.631、morning peak 2.267、off peak 1.204；high-demand station tier MAE 2.255，低需求 tier 為 1.065。Actual demand ≥10 的 rows MAE 4.231 且整體偏向低估。這些結果描述誤差集中處，不表示任何 feature 或情境具有因果效果。

## XGBoost challenger 比較

Stage 10 以相同 Track A target、100 站、feature schema 與時間切分建立 XGBoost challenger。其 12 月 holdout MAE 為 1.597、RMSE 2.580、R² 0.789；三段 rolling-origin 平均 MAE 為 1.647。兩組評估都略遜於本 HGB，因此沒有替換目前主模型。這項結論只表示在目前受控實驗中 HGB 較佳，不代表 HGB 在所有資料或參數設定下一定優於 XGBoost。

## 主要限制與風險

1. 只有 2023 一年，尚未驗證跨年度穩定性。
2. 只包含轉乘旅次，族群與完整 YouBike 使用者不同。
3. 只建模 top-100 站點，低需求、郊區或新設站點未被公平涵蓋。
4. 歷史天氣為單一格點，不是每站實測。
5. 線上推論必須使用當時可取得的 weather forecast；使用事後實際天氣會高估可部署效果。
6. 突發事件、工程、節慶、颱風與站點更名未被完整建模。
7. `joblib` 使用 pickle 機制，只能載入可信任來源的 artifact。

## 完整性與重現

Metadata 保存：

- 100 個站點清單
- 完整 feature schema
- 訓練截止時間與 holdout 指標
- Python 套件版本
- Artifact SHA-256

推論程式會先比對 SHA-256，再載入模型。這能偵測檔案錯置或損壞，但不是數位簽章；若 artifact 與 metadata 同時遭竄改，仍需依賴可信任的 Git 來源與發布流程。

## 監控與更新建議

- 持續監控整體、站點與尖峰時段 MAE。
- 監控輸入站點、時間與天氣欄位缺漏。
- 站點大規模新增／更名時重新訓練並更新 scope。
- 新年度資料可用後重新做跨年 holdout。
- 若 rolling MAE 明顯高於目前 1.592–1.636 範圍，應檢查資料漂移與模型失效。

Track A 的完整實驗脈絡、模型比較、ablation、情境誤差與研究決策見
[`STAGE_13_TRACK_A_RESEARCH_SUMMARY.md`](STAGE_13_TRACK_A_RESEARCH_SUMMARY.md)。
