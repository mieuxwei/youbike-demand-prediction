# Stage 15：Track B 七天資料稽核與 Preliminary Persistence Baseline

## 1. 階段目的與成果邊界

本階段在 Track B 雲端 collector 通過連續七天門檻後，完成受保護 CSV 的真實下載、station-row coverage audit、chronological split 與第一個必要 baseline。

Baseline 定義為：

```text
predicted available bikes at t + horizon = available bikes at t
```

這是 current-availability persistence，不是訓練出的 AI 模型。它只建立之後模型必須超越的參考值；沒有建立 shortage／full-station classifier、threshold 或 optimization。Track A 完全未修改。

## 2. 授權匯出 smoke test

Owner 已明確授權重設 `EXPORT_TOKEN`。Smoke test 使用的值只存在執行程序記憶體，未輸出至對話、檔案或 Git。Cloudflare secret propagation 經 HTTP probe 確認後才開始下載。階段完成後 owner 要求保存，因此 token 再次安全旋轉；matching value 已保存於 macOS Keychain service `youbike-track-b-export`，Cloudflare authorization 與 Keychain read-back 均已驗證。

第一次全期間 cursor export 在約 410,000 rows 時遇到 HTTP 500。加入 page-level bounded retry 後，進一步確認深 cursor query 會逐漸頻繁出現 500。因此 export client 增加兩項可靠性措施：

1. 單頁遇到 network error、HTTP 429 或 5xx 時，最多五次有限 exponential backoff retry；401 不 retry。
2. CLI 預設把 requested range 切成六小時 UTC windows，每個 window 重設 cursor，避免 D1 query range 隨整體資料量持續擴張。

最終成功結果：

| 項目 | 結果 |
|---|---:|
| Export range | 2026-08-21 09:45:02Z 至 2026-08-28 15:30:14Z |
| CSV rows | 3,739,789 |
| Pages | 377 |
| Local CSV size | 約 526 MiB |
| Output | `data/processed/track_b_week_1.csv`（Git ignored） |

CSV 使用 `.tmp` 後原子替換；失敗嘗試沒有留下假的完成檔。

## 3. Station-row audit

| 項目 | 結果 |
|---|---:|
| 實際 snapshots | 2,084 |
| Distinct stations | 1,798 |
| First snapshot | 2026-08-21 09:45:02Z／17:45:02 Asia/Taipei |
| Latest snapshot | 2026-08-28 15:20:23Z／23:20:23 Asia/Taipei |
| Coverage | 7.233 天 |
| Duplicate station + snapshot rows | 0 |
| Gaps over 5.5 minutes | 0 |
| Maximum interval | 5.35 分鐘 |
| Rows per snapshot | 1,794–1,798 |

Active current／future station-row target coverage：

| Horizon | Usable rows | Coverage |
|---|---:|---:|
| 30 分鐘 | 3,662,981 | 97.946% |
| 60 分鐘 | 3,652,349 | 97.662% |

Coverage 小於 100% 的合理來源包括資料尾端尚無 future observation，以及 current 或 matched future station inactive。這些比例不是 prediction metrics。

## 4. Chronological split 與 leakage protection

以 current snapshot time 做固定時間區塊：

| Split | UTC range | Snapshots | Rows | Stations |
|---|---|---:|---:|---:|
| Train | 2026-08-21 09:45:02 至 2026-08-26 09:40:23 | 1,440 | 2,583,360 | 1,794 |
| Validation | 2026-08-26 09:45:23 至 2026-08-27 09:40:23 | 288 | 516,672 | 1,794 |
| Test | 2026-08-27 09:45:23 至 2026-08-28 15:20:23 | 356 | 639,757 | 1,798 |

- Train 約五天、validation 一天、test 約 1.23 天。
- 不使用 random split。
- Validation row 的 future target time 必須仍小於 validation end；跨入 test 的 label 會 purge。
- Test 只使用已實際存在的 future target。
- Persistence baseline 不需 fit；train block 是為後續模型固定 scope，沒有用 test 調參。

## 5. Preliminary baseline 結果

| Horizon | Split | Usable rows | MAE | RMSE | R² | Mean error（prediction − actual） |
|---|---|---:|---:|---:|---:|---:|
| 30m | Validation | 496,952 | 2.035 | 3.523 | 0.865 | -0.008 |
| 30m | Test | 617,847 | **2.154** | **3.626** | **0.852** | -0.001 |
| 60m | Validation | 486,374 | 2.947 | 4.856 | 0.744 | -0.024 |
| 60m | Test | 607,245 | **3.140** | **5.064** | **0.712** | 0.000 |

30 分鐘比 60 分鐘容易，符合短期庫存狀態具有較強延續性的預期。很小的平均 signed error 只表示整體正負誤差接近平衡，不代表個別站點或尖峰情境誤差小。

## 6. 產出

- `src/track_b_baseline.py`
- `tests/test_track_b_baseline.py`
- `results/track_b_live_audit.json`
- `results/track_b_live_gaps.csv`
- `results/track_b_target_coverage.csv`
- `results/track_b_split_summary.csv`
- `results/track_b_persistence_metrics.csv`
- `results/track_b_baseline_summary.json`

## 7. 限制與下一步

1. 只有 7.233 天；雖包含平日與週末，仍不足以代表多週變異、天氣、事件或長期站點變化。
2. Persistence 的高 R² 反映可用車短期自相關，不是因果或營運改善。
3. 尚未建立 station／hour／weekday error analysis，也未比較 learned model。
4. 尚未定義 shortage／full-station label 與 threshold，不可引用 regression baseline 作為 risk 結果。
5. Collector 必須繼續累積；14 天做平日／週末與穩定性比較，28 天再建立正式 Track B 第一版模型。
6. 下一個 learned model 必須使用 past-only 特徵、相同 chronological boundaries、validation-only 選擇，並在同一 test scope 超越 persistence。
7. 新 `EXPORT_TOKEN` 保存於 macOS Keychain，不在 repository 或一般文字檔。未來匯出可用 `security find-generic-password -a "$USER" -s youbike-track-b-export -w` 載入環境變數，不可把結果印出、貼入對話或寫入 Git。
