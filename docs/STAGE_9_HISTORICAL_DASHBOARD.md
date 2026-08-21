# Stage 9：歷史需求預測儀表板

## 階段目標

把 Stage 8 的命令列推論流程整理成可互動、可重現且不誤導的作品集展示。儀表板不是重新訓練一個模型，而是使用已驗證的 `hist_gradient_boosting_weather` 模型，針對 2023 年 12 月留出測試期間的代表性時段重新產生預測。

## 使用者可以看到什麼

- 切換 10 個平日、週末、早晚尖峰與下午時段。
- 查看該時段 100 個站點的預測與實際借車總量。
- 比較高需求站點的預測值、實際值與絕對誤差。
- 搜尋完整 100 站明細。
- 比較六種模型在相同 12 月測試集的 MAE。
- 查看三段 expanding-window rolling-origin 驗證結果。
- 查看 permutation importance 的主要歷史與時間訊號。

## 可重複資料流程

`src/build_dashboard_data.py` 會執行以下步驟：

1. 驗證模型 metadata 與 joblib 檔案 SHA-256。
2. 載入全年 station-hour demand 與 hourly weather。
3. 對每個設定時段，只讀取 target 前 168 小時的需求歷史。
4. 使用與 Stage 8 相同的 feature schema 產生 100 站預測。
5. 預測完成後才附加 holdout actual，避免 actual 影響推論特徵。
6. 合併既有模型比較、滾動驗證與特徵重要性結果。
7. 輸出精簡的 `dashboard/app/dashboard-data.json` 供前端使用。

目標時段集中設定於 `config/dashboard_targets.json`，不需修改前端程式即可重新產生同一組展示資料。

## 執行方式

在專案根目錄重新產生資料：

```bash
python src/build_dashboard_data.py
```

啟動網站：

```bash
cd dashboard
pnpm install
pnpm run dev
```

驗證網站：

```bash
pnpm run lint
pnpm test
```

## 設計與互動

儀表板使用深墨綠、螢光黃綠、米白與灰綠建立城市交通觀測站的視覺語言。首屏先說明研究目標，互動區再呈現回測快照，最後補上模型比較與研究限制。響應式版面支援桌面與行動裝置，表格可水平捲動，互動元件皆有可辨識標籤。

社群分享圖以相同色彩、交通路線、站點節點、預測長條與單車元素建立，並透過 Open Graph 與 X metadata 使用絕對圖片網址。

## 驗證結果

- 10 個目標時段皆能通過模型檔案、168 小時歷史、站點、天氣與 feature schema 驗證。
- 完整 Python 測試共 39 項通過。
- Dashboard lint 通過。
- Vinext production build 通過。
- Server-rendered HTML 測試通過，且不再包含 starter skeleton 或暫時預覽標記。

## 解讀限制

1. 目標是 hourly transfer-related borrowing demand，不是所有 YouBike 旅次。
2. 範圍只涵蓋以 training period 選出的 100 個高需求站點。
3. 畫面中的 actual 只用於歷史回測展示，不會進入 target-hour 預測特徵。
4. 天氣是臺北單一參考點的歷史再分析資料；真正未來預測必須改用當時可取得的天氣預報。
5. 需求排名不能直接解讀為即時缺車風險、可借車數或調度數量。

## 下一階段建議

目前專案計畫仍要求累積至少 7 天、同時涵蓋平日與週末的真實即時快照。資料覆蓋足夠後，才適合建立獨立的 30／60 分鐘 station availability 模型；在此之前不應把歷史轉乘需求模型包裝成即時缺車模型。
