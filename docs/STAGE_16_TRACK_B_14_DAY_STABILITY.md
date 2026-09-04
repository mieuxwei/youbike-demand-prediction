# Stage 16 — Track B Fourteen-Day Stability Analysis

## 1. 目的與研究邊界

本階段使用 Cloudflare Worker + Cron + D1 的真實即時資料，完成固定十四天的資料品質、平日／週末分布與 current-availability persistence stability 分析。這是 Stage 15 七天 preliminary baseline 的延伸檢查，**沒有訓練新模型**，也不是 shortage／full-station risk、live prediction 或 optimization 成果。

Track A 的 target、模型、metrics、artifact 與 Dashboard 均未修改。

## 2. 固定分析期間

- 視窗規則：`[start, end)`。
- Start：2026-08-21 09:45:02 UTC（2026-08-21 17:45:02 Asia/Taipei）。
- End exclusive：2026-09-04 09:45:02 UTC（2026-09-04 17:45:02 Asia/Taipei）。
- Week 1：前七天；Week 2：後七天。
- UTC 用於儲存、target alignment 與邊界判斷；Asia/Taipei 用於 weekday／weekend 與 hour-of-day。

Start 選在部署初期 65 分鐘缺口之後，因此本分析不把已知的啟用期中斷混入十四天固定視窗。匯出使用 Keychain 內的 `EXPORT_TOKEN`，經六小時 bounded windows 下載 7,240,919 rows、728 pages；CSV 位於 Git-ignored `data/processed/track_b_14_days.csv`，不會 commit 到 GitHub。

## 3. 新增分析保護

`src/track_b_stability.py` 會在計算前檢查：

- required columns 完整；
- `snapshot_time` 必須帶明確 timezone，並統一轉成 UTC；
- bike／return-space／capacity 必須是非負整數；
- bike 或 return-space 不可個別大於 capacity；
- `is_active` 只能是 0／1；
- `(station_id, snapshot_time)` 不可重複；
- 分析範圍必須恰好十四天，資料不可落在 `[start, end)` 之外。

未來 target 沿用既有定義：以 station 為單位向前尋找 `t + 30m` 或 `t + 60m`，只接受 horizon 到 horizon + 2 分鐘內的 active observation。兩週比較時，target time 必須留在同一個七天視窗，跨週 target 會 purge。

## 4. 十四天資料完整性

| 指標 | 結果 |
|---|---:|
| Station rows | 7,240,919 |
| Snapshots | 4,031 |
| Distinct stations | 1,800 |
| Duplicate station-time rows | 0 |
| Rows per snapshot | 1,794–1,800 |
| Mean rows per snapshot | 1,796.308 |
| Gaps over 5.5 minutes | 1 |
| Estimated missing 5-minute slots | 1 |
| Maximum interval | 10.0 minutes |

唯一新缺口是 2026-08-28 15:20:23 UTC 至 15:30:23 UTC（Asia/Taipei 23:20:23 至 23:30:23）。Production D1 的 `collection_runs` 在缺口前後均有成功紀錄，但 15:25 UTC 沒有 run record；因此能確認該輪沒有留下 collector log，不能進一步斷言是 API error。Collector 不需要也沒有被重新啟動。

| Period | Rows | Active rows | Snapshots / expected | Stations | Snapshot coverage |
|---|---:|---:|---:|---:|---:|
| Week 1 | 3,617,525 | 3,553,525 | 2,016 / 2,016 | 1,798 | 100.000% |
| Week 2 | 3,623,394 | 3,559,550 | 2,015 / 2,016 | 1,800 | 99.950% |

Week 1 的 1,798 stations 全數出現在 Week 2；Week 2 多 2 個 stations。因此另以 Week-1-defined 1,798-station common cohort 重算 metrics，避免把站點組成變動誤當模型變化。

## 5. Future-target coverage

在完整十四天、以全部 rows 為分母時：

| Horizon | Usable target rows | Coverage |
|---|---:|---:|
| 30 minutes | 7,090,027 | 97.916% |
| 60 minutes | 7,068,746 | 97.622% |

在兩週 stability comparison 中，以 active current rows 為分母，並 purge 跨週 targets：

| Period | Horizon | Usable / active current rows | Coverage |
|---|---:|---:|---:|
| Week 1 | 30m | 3,542,893 / 3,553,525 | 99.701% |
| Week 1 | 60m | 3,532,261 / 3,553,525 | 99.402% |
| Week 2 | 30m | 3,536,538 / 3,559,550 | 99.354% |
| Week 2 | 60m | 3,515,293 / 3,559,550 | 98.757% |

兩組百分比的分母不同，不能直接互相比較。Week 2 coverage 略低與一個缺少的 snapshot、每個七天視窗結尾的 right-censoring，以及 current／future 皆須 active 的 matching 規則一致；本分析不將差額全數歸因於單一原因。

## 6. Persistence stability

Baseline 定義維持不變：

```text
prediction(t + horizon) = available_bikes(t)
```

| Scope | Period | Horizon | Rows | MAE | RMSE | R² | Mean error (pred − actual) |
|---|---|---:|---:|---:|---:|---:|---:|
| All stations | Week 1 | 30m | 3,542,893 | 1.704 | 3.086 | 0.907 | 0.007 |
| All stations | Week 2 | 30m | 3,536,538 | 1.030 | 2.516 | 0.925 | -0.010 |
| All stations | Week 1 | 60m | 3,532,261 | 2.544 | 4.337 | 0.817 | 0.013 |
| All stations | Week 2 | 60m | 3,515,293 | 1.564 | 3.544 | 0.850 | -0.022 |

Week 2 相對 Week 1 的 MAE 變化為 30m -39.55%、60m -38.50%；RMSE 分別 -18.46%、-18.28%。共同 1,798 站 cohort 得到幾乎相同結果（Week 2 MAE 1.030／1.564），因此變化不是新增 2 站造成。

這代表 persistence 在第二週明顯較容易，而不是代表模型「持續進步」：persistence 沒有被訓練，差異反映兩週 station-state dynamics 不同。正式 learned model 必須等待 28 天資料後，用預先固定、leakage-aware 的 chronological split 與相同 test scope 比較。

## 7. 平日／週末描述

以下只包含 active station rows。`observed empty` 與 `no return space` 是當下狀態比例，不是未來風險標籤或 classifier metric。

| Period | Day type | Mean bikes | Median bikes | Mean availability / capacity | Empty | No return space |
|---|---|---:|---:|---:|---:|---:|
| Week 1 | Weekday | 11.387 | 9 | 41.281% | 3.352% | 1.865% |
| Week 1 | Weekend | 12.643 | 10 | 45.005% | 2.047% | 2.086% |
| Week 2 | Weekday | 10.818 | 9 | 39.926% | 3.662% | 1.548% |
| Week 2 | Weekend | 10.581 | 8 | 40.374% | 3.974% | 1.811% |

Week 1 的週末平均可借車高於平日，但 Week 2 方向不同；十四天只包含兩組週末，不能將此差異解讀為穩定的週末因果效果。完整 Asia/Taipei hour × day-type profile 保存於 `results/track_b_14d_hourly_profile.csv`，供後續 28 天特徵與 error analysis 設計使用。

## 8. 產出檔案

- `src/track_b_stability.py`
- `tests/test_track_b_stability.py`
- `results/track_b_14d_live_audit.json`
- `results/track_b_14d_live_gaps.csv`
- `results/track_b_14d_full_target_coverage.csv`
- `results/track_b_14d_period_summary.csv`
- `results/track_b_14d_target_coverage.csv`
- `results/track_b_14d_persistence_metrics.csv`
- `results/track_b_14d_stability_comparison.csv`
- `results/track_b_14d_distribution.csv`
- `results/track_b_14d_hourly_profile.csv`
- `results/track_b_14d_station_cohort.csv`
- `results/track_b_14d_stability_summary.json`

## 9. 結論與下一步

十四天資料足以完成第一輪週間 stability 與 weekday／weekend 描述：去重完整、只有一個 missing slot、兩個 horizon 的 active target coverage 均接近或高於 98.75%。但兩週 persistence 誤差差異明顯，正好說明不能用單週結果宣稱穩定 live prediction。

Collector 應繼續執行。下一個計畫門檻是 2026-09-18 17:45:02 Asia/Taipei 的固定 28 天資料；屆時先做 audit，再建立 Track B 第一版 learned 30／60 分鐘 regression。Shortage／full classification 必須先由研究者明確定義 label 與 threshold，optimization 仍需等待有效預測及營運限制。
