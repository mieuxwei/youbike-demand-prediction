# YouBike Demand Prediction — Research & Live Demonstration Plan v7

更新日期：2026-09-27。**研究維持 frozen；展示工程重新開啟，最終公開驗收中。** 原本機研究版已保存於 `159f059`。原 [研究 freeze 紀錄](docs/RESEARCH_FREEZE.md) 保留不改寫；本輪展示的版本、部署、驗收與再次 freeze 另見 [live demo 交付紀錄](docs/LIVE_DEMO_DELIVERY.md)。

## 1. 本版定位與範圍決策

本版對外定位為「**YouBike 站點需求分析、短期可用車預測與調度模擬**」，不是正式營運系統。v6 已依 2026-09-27 授權補完 Phase 3／4。v7 依後續明確要求，只重開有限的 live demo 工程、文件、版本整理與公開部署；不重開研究。

不等待新研究資料、不重訓、不擴大搜尋；原模型、評估、資料窗與 Phase 3／4 結論不變。Collector 只增加固定 12 站唯讀展示端點及既有模型推論；D1 schema、資料定義、五分鐘 Cron、匯出 secret 不變。網站已由 owner-restricted 改為可分享公開展示，允許必要 commit／push／deploy。

Track A 使用 2023 轉乘相關借車量，Track B 使用 2026 站點可用車數，Phase 4 使用另一個 validation 選定的回溯 HGB 及固定模擬假設。三者同屬一個研究主題，但不是 A → B → 調度的直接模型串接。庫存差值不是實際借車量。

## 2. 原始 Phase 1–5 對照

原始計畫來源：Git commit `4742f10:PROJECT_PLAN.md`。

| 原始階段 | 對應成果與本版驗收 | 目前狀態 |
|---|---|---|
| Phase 1 — Data Analysis | 官方歷史／即時資料、清理、EDA、天氣、時間序列特徵及 audit | 已完成；不重做 |
| Phase 2 — Machine Learning | Track A Naive／Ridge／HGB／XGBoost 與完整分析；Track B persistence／HGB、固定 28 天研究與獨立七天驗證 | 已完成；保存原始證據 |
| Phase 3 — Deep Learning | Track B 60m persistence／HGB／LSTM 的共同範圍比較、固定種子、成本及結論 | 已執行；LSTM 未勝 HGB，不採用 |
| Phase 4 — Optimization | 小型靜態整數調度、無調度／greedy／MILP 比較、限制驗證及敏感度分析 | 已執行；基本設定 MILP／greedy 同分 |
| Phase 5 — Visualization / Demo | React/Vinext 保留 A 歷史與 Phase 3／4 面板，增加固定 12 站目前觀測、30m persistence、原 Stage 17 60m HGB 與安全失效處理 | v7 新增 live serving 與公開部署；驗收見交付紀錄 |

Random Forest／GRU 為非必要例子或選做項，不增加新模型。原範例的「缺車警報」不冒充已校準風險機率；本版 Phase 4 使用明確模擬庫存目標，不需要 classifier。

## 3. 保留的既有研究

### Track A：歷史轉乘需求

- 2023 官方轉乘相關旅次 7,388,479 筆、4,670,320 有活動 station-hour rows、8,760 小時天氣；非全部 YouBike 旅次。
- 訓練期選出的 top-100 站；1–9 月 training、10–11 月 validation、12 月 holdout。
- HGB with weather：74,282 holdout rows，MAE 1.575、RMSE 2.549、R² 0.794。XGBoost 已比較但未超越。
- 三段 rolling-origin、ablation、error analysis、prediction interface 與 React/Vinext 歷史展示已完成。
- 不改既有模型、分析與十時點 Dashboard bundle。天氣為單一臺北參考點再分析值，不是預測當時可取得的未來天氣。

### Track B：Stage 17／19 歷史證據

- 固定 28 天：`[2026-08-21 09:45:02Z, 2026-09-18 09:45:02Z)`，14,490,149 rows、8,058 snapshots、1,803 stations；0 duplicates、7 estimated missing slots。
- Stage 17 原模型 holdout MAE：30m persistence／HGB 2.043／2.057；60m 3.012／2.922。
- Stage 19 已於 9/27 執行：`[2026-09-18 18:30Z, 2026-09-25 18:30Z)`，評估原始 3,636,105 rows、2,016 snapshots；無重複鍵或缺少時槽。
- Stage 19 MAE：30m persistence／HGB 1.950／1.981；60m 2.862／2.813，60m 通過原事前 gates。原 artifacts、manifest、時段與歷史結論必須保留。
- 這些資料與結果已被檢視；新回溯研究不冒稱新的獨立驗證。
- 最後既有 cloud 查核：9/27 最新 snapshot 01:00:28 Asia/Taipei，success，1,807 stations，當時累積 10,450 snapshots／18,805,167 rows。固定查核點不等於持續更新總量。

## 4. Phase 3：有界限的 LSTM 比較

完整規約：[OFFLINE_RESEARCH_PROTOCOL.md](docs/OFFLINE_RESEARCH_PROTOCOL.md)；設定：[offline_research.json](config/offline_research.json)。

- 主要 target 只做 60m available bikes，30m 沿用舊成果。
- 沿用 18／5／5 日切分；64 站只依訓練期 coverage 與固定排序選取，與模型勝負無關。
- 單站 13 步、約 60 分鐘歷史輸入；停用、非有限值、缺口序列排除，不跨站串接；future labels 不跨 split end。
- 特徵／標準化只用允許的訓練資訊；HGB 用同一完整歷史的 flattened inputs，另存 artifact，不覆寫原模型。
- 先做 bounded pilot，再依規約執行一種 LSTM、至多兩組設定、三個事先固定種子。
- 只用 validation 選設定與 simulation forecaster；種子結果完整保留，primary LSTM 為 seed ensemble，不選最佳 test seed。
- 比較使用共同有效資料列，報 MAE／RMSE／R²、訓練與推論成本、分站／分時誤差及 LSTM 採用結論。
- 看過本輪 retrospective evaluation 後不追加候選或調參。

驗收：實際 fit／predict／evaluate 完成；模型、scaler、設定、資料／樣本 key hashes、環境與成本可追溯；序列洩漏與共同範圍測試通過。未勝出可結案，未執行不可。

## 5. Phase 4：靜態整數調度模擬

- 訓練期座標選定 12 站；固定 12 個日期／時段請求，不能依改善挑案例。
- 輸出非負整數站點間搬運量；沒有外部車源、倉庫或真實車隊假設。
- outgoing 不超過當下可用車、incoming 不超過模擬剩餘容量；不得搬未來才出現的車。守恆、當下與預測後容量、搬運數量及 bike-km 資源均檢查。
- 未來庫存以「固定預測＋立即搬運淨量」作顯式模擬，非真實反事實。
- 只採 SciPy/HiGHS MILP；對照無調度與同資訊／同成本／同限制的 deterministic greedy。
- 庫存目標為容量 50%，數量、距離代理與成本均為研究設定；座標 great-circle km 不是道路路線。
- 預先固定資源、成本、預測誤差敏感度；沒有改善時如實回傳不調度或 solver 狀態。
- 不把目標偏差叫 lost trips；歷史未介入觀測不是調度後真實結果。

驗收：至少一個事前固定請求有效且全部方法真實執行；報全部可用／缺少案例、限制檢查、基準差異與有效／無效情況，不挑選展示勝例。

## 6. 展示與文件

沿用 React 19 + Vinext，不重做網站、不新增 Streamlit。歷史觀測、目前觀測、未來估計、假設性模擬分開標示。Phase 4 維持固定歷史情境，不增即時 what-if。

本輪 [live 規約](docs/LIVE_DEMO_PROTOCOL.md)：沿用 Phase 4 訓練期座標選出的完整 12 站；30m 用 persistence，60m 用 SHA 已驗證的原 Stage 17 HGB。23 特徵、UTC／臺北日曆、backward lag、past-only rolling、容量裁切維持原定義。既有樹結構轉為 Worker 伺服端數值推論；以保存的 72 組歷史樣本驗證 Python／Worker 一致性，非新模型評估。

`GET /demo/live` 僅回傳 12 站最新觀測與預測，不接受站點／日期查詢，不公開歷史或 token。快照／來源超過十分鐘、時間異常、停用、缺歷史或推論錯誤時 fail closed；前端每 60 秒更新，資料年齡每秒更新。公開分享、匿名存取、桌面／手機、既有面板與實際部署均須驗收。

v7 同步 README、中文總覽、HANDOFF、Dashboard 說明及新的展示 freeze 紀錄。原重現 guide、model documentation、Phase 3／4 報告、研究 manifest 與 Stage 文件保持原樣；此次不是再開離線研究。

公開網址：[YouBike 研究展示](https://youbike-demand-observatory.rwhqgqfdk2.chatgpt.site/#live)。Sites version 3 已部署，匿名 HTTP 200、桌面／手機 viewport、更新與舊面板已驗證；12 組真實雲端 HGB 輸出與原 Python 模型差異為 0。未驗證的 Safari private／實體手機與所有實際版本見交付紀錄，不推定全瀏覽器相容。

## 7. 已知限制與本版不含項目

- 既有資料已檢視，存在研究者選擇偏差；時間切分不會使它重新變成 untouched data。
- 時間使用 UTC，calendar 使用 Asia/Taipei；scheduled snapshot 不等於 fetch completion。上游偶有延遲，不能宣稱精確物理庫存。
- 庫存差值混合借還、人工調度與修正。Track A demand 不直接變成 shortage 或補車量。
- 有限站點／四週研究不能推論全年或全部站點；不主張統計顯著或正式營運效益。
- 本版不含 shortage/full classifier、校準風險機率、多車路線、即時重排、營運部署、新年度／跨季節資料、GRU／Transformer 或 RL。

## 8. v7 展示 freeze 與停止條件

只有以下全部完成才標為 **研究與展示交付完成，實作 frozen**：

1. Phase 3 真實比較、跨種子／成本／誤差與採用結論完成。
2. Phase 4 真實最佳化、基準與敏感度完成，守恆／容量／資源檢查通過。
3. 歷史面板與 live demo 實際部署，非 owner 也可開啟；30m／60m 有真實端點與已驗證推論，故障時明示原因。
4. 資料／模型／設定／程式／結果校驗碼與環境可追溯，重現入口經檢查。
5. 相稱測試、build、文件與 artifact 檢查完成，沒有影響結論的未解洩漏或錯誤。
6. 新 freeze 紀錄包含真實 Git／Sites／Worker 版本、分享權限、URL、部署後 E2E、桌面／手機、故障及未驗證項目。保留 v6 本機 freeze 的原始紀錄。

達標後停止本版功能、模型、特徵、調參、訓練、新資料窗與自動研究；不建立提醒或背景任務。只有使用者另行明確要求才重開。

本輪必要 commit、push、部署已獲明確授權；不建立 tag／Release 或自動續做。研究／展示交付與持續蒐集分開，collector 繼續執行不表示仍需研究開發。

## 9. v6 已完成研究（保留）

規約與資料核對 → pilot／固定運算預算 → development-only 模型選擇 → retrospective evaluation → 固定情境調度模擬 → Dashboard 本機整合 → 測試／重現／文件驗收 → freeze 與停止，均已完成。Phase 3 MAE：persistence 3.431339、HGB 3.249886、LSTM ensemble 3.326271；Phase 4 基本平均目標值：不調度 92.1952、greedy／MILP 76.8478。詳見 [正式結果](docs/PHASE_3_4_OFFLINE_RESEARCH.md)。不再自動進入下一階段。
