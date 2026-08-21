# Stage 11：Track B 雲端即時資料蒐集基礎設施

## 1. 階段目標與完成邊界

本階段只建立 Track B 的雲端資料蒐集、儲存、品質控管、查詢與匯出基礎，不訓練新模型，也不修改 Track A 的 HGB／XGBoost 或歷史 Dashboard。

程式碼與 D1 schema 已完成並通過本機測試；正式 Cloudflare Worker、D1 與 Cron 已於 2026-08-21 部署。15:50、15:55、16:00（Asia/Taipei）三輪排程均成功，累積 3 snapshots、5,382 rows。`EXPORT_TOKEN` 已設定且未授權 export 會回傳 HTTP 401；資料仍在累積，仍不可宣稱 30／60 分鐘 availability prediction、shortage prediction 或 optimization 已完成。

## 2. D1 與 R2 評估

| 需求 | D1 | R2 |
|---|---|---|
| 依 `station_id` + 時間區間查詢 | 可用複合主鍵與索引直接查詢 | 必須掃描或另建索引 |
| 產生 30／60 分鐘 future target | 可用時間排序結果直接交給 Python 對齊 | 需先下載、解壓與合併物件 |
| Dashboard 即時查詢 | Worker 可直接查 D1 | 不適合大量小型條件查詢 |
| 原始 JSON 備份 | 可保存結構化欄位，但不是 blob archive | 適合保存完整原始回應 |
| 本階段複雜度 | 單一權威資料庫 | 若與 D1 並用需處理雙寫與一致性 |

結論：本階段採用 **Cloudflare Worker + Cron Trigger + D1**。Track B 的核心需求是結構化的 station-time range query，D1 明顯較合理。R2 暫不啟用；未來只有在出現稽核、長期冷儲存或重播原始 payload 的明確需求時，再評估壓縮 JSON 備份。

## 3. 雲端資料流

```text
Cloudflare Cron：*/5 * * * *
        ↓
YouBike 官方即時 JSON API
        ↓
HTTP／timeout／JSON／schema validation
        ↓
最多 3 次有限 retry（snapshot_time 保持不變）
        ↓
D1 station_snapshots（主資料）
        +
D1 collection_runs（成功／失敗日誌）
        ↓
Bearer token 保護的分頁 CSV export
        ↓
Python Track B feature／target pipeline
```

本機 `src/collect_youbike.py` 與 `src/collect_history.py` 保留，定位為 local testing、debugging 與 fallback；它們不是正式長期蒐集方案，執行期間仍需要本機保持開機。

## 4. 真實 API schema

2026-08-21 再次對官方 endpoint 做單次 schema 檢查，回傳 1,794 個站點；所有紀錄皆包含本階段使用的必要欄位。站點數會隨官方新增、停用或調整而變動，因此不能把 1,790 或 1,794 寫死成 validation 規則。

| 官方欄位 | D1 欄位 | 處理方式 |
|---|---|---|
| `srcUpdateTime` | `source_update_time` | Asia/Taipei 無 offset 字串解析後轉 UTC |
| `mday` | `station_update_time` | 個別站點更新時間，解析後轉 UTC |
| `sno` | `station_id` | 非空字串 |
| `sna` | `station_name` | 保留官方名稱 |
| `available_rent_bikes` | `available_bikes` | 非負整數 |
| `available_return_bikes` | `available_return_bikes` | 非負整數 |
| `Quantity` | `capacity` | 非負整數 |
| `latitude` | `latitude` | 有效緯度 |
| `longitude` | `longitude` | 有效經度 |
| `act` | `is_active` | 只接受 0／1 |

`snapshot_time` 不取自單一站點欄位，而使用 Cloudflare Cron event 的 `scheduledTime`。同一排程即使因 HTTP retry 重抓，仍保持相同 snapshot time，讓寫入具備 idempotency。

## 5. D1 schema 與去重

### `station_snapshots`

保存每站每次排程的 availability 狀態。複合主鍵為：

```text
PRIMARY KEY (station_id, snapshot_time)
```

因此同一站點、同一排程時間不能重複存在。Worker 使用 `INSERT OR IGNORE ... SELECT ... FROM json_each(?1)`，把整份已驗證 JSON 轉換結果以單一 bound parameter 寫入，既避免 SQL 字串拼接，也避免對約 1,790 個站點逐列送出 D1 query。

索引 `idx_station_snapshots_time` 支援全站時間區間匯出；主鍵本身支援 station ID + time range 查詢。

### `collection_runs`

每次 Cron 保存：

- scheduled／started／finished time
- success／failure
- attempts
- API station count
- 實際新增 row count
- 最新 source update time
- failure category 與截短後的 error message

Worker 同時輸出結構化 `console.info`／`console.warn`／`console.error`，可在 Cloudflare Logs 追蹤每次排程。

## 6. 時間策略

- **D1 儲存：** UTC ISO-8601，例如 `2026-08-20T13:15:00.000Z`。
- **官方來源：** `srcUpdateTime` 與 `mday` 是沒有 offset 的臺北本地時間；Worker 明確以 `Asia/Taipei`（UTC+08:00）解析後轉 UTC。
- **Cron：** Cloudflare Cron 本身以 UTC 執行；`*/5 * * * *` 不依賴時區，因此每個時區都是每五分鐘一次。
- **研究與展示：** Python 讀入 UTC 後必須明確轉為 `Asia/Taipei`，才能建立 hour、weekday、weekend 等日曆特徵。
- **CSV 日期參數：** `YYYY-MM-DD` 依 Asia/Taipei 解讀；帶時間的值必須明確包含 `Z` 或 offset。

## 7. API 失敗、validation 與 retry

Collector 會拒絕並記錄以下情況：

- 非 2xx HTTP response。
- 15 秒 timeout 或 network failure。
- JSON 解析失敗。
- 空陣列。
- 任一站點不是 object。
- 任一必要欄位缺失。
- 無效時間、負數、無效經緯度、非 0／1 `act`。
- 可借車數加可還車位超過 capacity。
- 同一 API response 出現重複 station ID。

API 讀取最多嘗試 3 次，採 250 ms、1,000 ms 的有限 backoff。所有 retry 共用同一 scheduled snapshot time；D1 主鍵與 `INSERT OR IGNORE` 讓重試不會重複寫入。若 D1 本身不可用，Worker 仍會輸出 Cloudflare error log；若 D1 可寫，失敗狀態也會保存於 `collection_runs`。

## 8. 排程與 Cloudflare 限制

`wrangler.jsonc` 將 Cron 設為：

```text
*/5 * * * *
```

這是 Cloudflare 支援的五欄 cron expression，會呼叫 Worker 的 `scheduled()` handler。Cloudflare 文件說明 Cron 以 UTC 執行，新增或修改 trigger 可能需要數分鐘、最長約 15 分鐘傳播。

專案不在文件內硬寫免費額度。部署前請在 Cloudflare Console 確認帳號方案的 D1 storage／rows read／rows written、Workers Cron、CPU time 與 request limits；正式運行後也要以 Console 的實際 usage 為準。

## 9. 資料量與儲存估算

以 1,790 站、每 5 分鐘一次估算：

| 期間 | Snapshots | Station rows |
|---|---:|---:|
| 每天 | 288 | 515,520 |
| 7 天 | 2,016 | 3,608,640 |
| 14 天 | 4,032 | 7,217,280 |
| 28 天 | 8,064 | 14,434,560 |

使用目前 12 份真實快照共 21,480 rows，套用本階段 D1 SQLite schema 與索引後，本機檔案約 3.59 MiB，平均約 175 bytes／row。線性推估：

| 期間 | 粗估 D1 資料庫大小 |
|---|---:|
| 每天 | 約 0.08 GiB |
| 7 天 | 約 0.59 GiB |
| 14 天 | 約 1.18 GiB |
| 28 天 | 約 2.36 GiB |

這只是以目前站名長度、SQLite page 與索引做的 planning estimate；D1 實際壓縮、metadata、索引與站點數變化會造成差異。現有原始 JSON 約 0.98 MiB／snapshot，若未壓縮全部另存 R2，約為 282 MiB／日，因此本階段不為了形式完整而加入 raw JSON 雙寫。

## 10. 匯出給 Python

Worker 提供 bearer-token 保護的 `/export.csv`，支援：

- start date／timestamp
- end date／timestamp
- optional exact `station_id`
- cursor pagination

`src/export_track_b.py` 會自動逐頁下載、只保留一次 CSV header，並先寫 `.tmp` 再原子替換正式輸出。Token 只從 `TRACK_B_EXPORT_TOKEN` 環境變數讀取，不接受命令列 token，避免把秘密留在 shell history。

範例：

```bash
export TRACK_B_EXPORT_URL="https://youbike-track-b-collector.mieuxander.workers.dev/export.csv"
export TRACK_B_EXPORT_TOKEN="<secret>"
python src/export_track_b.py \
  --start 2026-08-21 \
  --end 2026-08-27 \
  --output data/processed/track_b_week_1.csv
```

## 11. 正式部署紀錄與剩餘使用者操作

已由 repository owner 完成登入與 OAuth 授權；D1 Database ID、migration、Worker、Cron 與 `EXPORT_TOKEN` 已正式設定。Secret 值沒有被讀回、寫入文件或保存於 Git。

已完成：

1. D1 `youbike-track-b-live` 已建立並套用 `0001_track_b_live.sql`，共 6 個 schema commands。
2. Worker 已部署至 `https://youbike-track-b-collector.mieuxander.workers.dev`。
3. Cron 已建立為 `*/5 * * * *`。
4. `/health` 已驗證第一輪排程成功：scheduled time `2026-08-21T07:50:02.000Z`、1,794 stations、1,794 inserted rows、1 attempt、無錯誤。

已完成的 export security check：

1. `EXPORT_TOKEN` 已以 Cloudflare secret text 保存。
2. 未帶 Bearer token 的 `/export.csv` 已驗證回傳 HTTP 401；不再是 secret 未生效時的 HTTP 503。
3. 因 Cloudflare secret 無法讀回，授權下載 smoke test 留待 owner 在本機安全提供 `TRACK_B_EXPORT_TOKEN` 時執行，不得把 token 貼入對話或 Git。
4. 持續查看 `/health`、Worker Logs 與 D1 Console：

```sql
SELECT * FROM collection_runs ORDER BY scheduled_time DESC LIMIT 10;
SELECT COUNT(*) AS rows,
       COUNT(DISTINCT snapshot_time) AS snapshots,
       MIN(snapshot_time) AS first_snapshot,
       MAX(snapshot_time) AS latest_snapshot
FROM station_snapshots;
```

最後還需在 Cloudflare Console 確認本帳號的實際用量與方案是否能承擔 7／14／28 天的預估資料量。

## 12. 測試與產出

本階段測試涵蓋：

- confirmed API response transformation
- required-field schema validation
- duplicate station ID rejection
- UTC／Asia-Taipei timestamp conversion
- invalid calendar time rejection
- HTTP retry
- malformed／empty response
- date-range interpretation
- successful／failed collection run logging
- D1 primary-key duplicate prevention
- paginated atomic CSV export
- Wrangler dry-run packaging

主要新增檔案：

- `cloudflare/track-b-collector/src/index.mjs`
- `cloudflare/track-b-collector/wrangler.jsonc`
- `cloudflare/track-b-collector/migrations/0001_track_b_live.sql`
- `cloudflare/track-b-collector/test/collector.test.mjs`
- `cloudflare/track-b-collector/README.md`
- `src/export_track_b.py`
- `tests/test_export_track_b.py`

## 13. 下一步

完成 owner deployment 後，collector 應持續運作：

1. 7 天：先做 coverage／gap audit 與 baseline feasibility check。
2. 14 天：比較平日與週末 coverage／分布。
3. 28 天：建議作為 Track B 第一版正式模型的最低資料目標。
4. 即使 7 天後開始 preliminary modeling，雲端 collector 也不停止。
5. 只有 30／60 分鐘 target coverage 足夠並完成時間切分設計後，才建立 regression／risk classification。
6. Optimization 必須再等待 current bikes、capacity、預測 availability／inflow／outflow 與 shortage／surplus 定義，不能使用 Track A historical demand 直接替代。

## 14. 官方參考

- [Cloudflare Cron Triggers](https://developers.cloudflare.com/workers/configuration/cron-triggers/)
- [Cloudflare Wrangler configuration](https://developers.cloudflare.com/workers/wrangler/configuration/)
- [Cloudflare D1 Worker Binding API](https://developers.cloudflare.com/d1/worker-api/)
- [Cloudflare D1 JSON functions](https://developers.cloudflare.com/d1/sql-api/query-json/)
- [Cloudflare D1 limits](https://developers.cloudflare.com/d1/platform/limits/)
- [臺北市 YouBike 2.0 即時資訊資料集](https://data.taipei/dataset/detail?id=c6bc8aed-557d-41d5-bfb1-8da24f78f2fb)
