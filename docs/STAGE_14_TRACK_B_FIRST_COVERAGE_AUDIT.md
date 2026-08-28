# Stage 14：Track B 第一輪雲端 Coverage／Gap Audit

## 1. 階段目的與邊界

本階段在 2026-08-28 檢查 Cloudflare Worker + Cron + D1 的實際蒐集狀態，並建立可重現的 CSV coverage audit 工具。這不是 Track B 模型訓練；沒有 availability、shortage、full-station 或 optimization metrics。

Track A 的資料、模型、metrics 與 Dashboard 均未修改。

## 2. 雲端稽核結果

第一輪稽核時間點為 2026-08-28 13:25:23（Asia/Taipei）；同日 21:35 再次稽核完整七天門檻。

| 項目 | 實際結果 |
|---|---:|
| 首份 snapshot | 2026-08-21 15:50:02 Asia/Taipei |
| 最新 snapshot（七天 follow-up） | 2026-08-28 21:35:23 Asia/Taipei |
| 全部涵蓋時間 | 約 7 天 5 小時 45 分 |
| 成功 collection runs／snapshots | 2,074 |
| D1 station rows | 3,721,765 |
| Distinct stations | 1,798 |
| 每份 station rows | 1,794–1,798；平均 1,794.31 |
| 失敗 runs | 0 |
| 需要 retry 的 runs | 1 |
| D1 database size（21:35 查詢 metadata） | 784,097,280 bytes（約 747.8 MiB） |

所有已記錄的 2,074 次 run 都成功。資料庫沒有 failure run；collector 仍由雲端 Cron 執行，與本機是否開機無關。

## 3. Gap audit

1,975 個相鄰 snapshot intervals 中只有一段超過 5.5 分鐘：

| 前一份（UTC） | 下一份（UTC） | Gap | 估計缺少排程 |
|---|---|---:|---:|
| 2026-08-21 08:40:02 | 2026-08-21 09:45:02 | 65 分鐘 | 12 |

這段發生於部署第一天；其後截至七天 follow-up 沒有第二段大於 5.5 分鐘的 gap。缺口後的連續區段從 2026-08-21 17:45:02（Asia/Taipei）開始，至 2026-08-28 21:35:23 已涵蓋 7.16 天、2,063 snapshots、3,702,031 rows。連續期間平均間隔 300.01 秒、最大間隔 321 秒，因此完整連續 7 天 cloud schedule audit 已通過。

## 4. Future timestamp coverage

依既有 feature pipeline 的規則：desired future time 後 0–2 分鐘內第一份 snapshot 可形成 timestamp match。對目前 1,976 個 snapshot times 的 D1 稽核結果：

| Horizon | 有 future snapshot | Snapshot-time coverage |
|---|---:|---:|
| 30 分鐘 | 2,063／2,075 | 99.422% |
| 60 分鐘 | 2,052／2,075 | 98.892% |

尾端最新資料必然還沒有未來 label；部署初期的 65 分鐘缺口也會降低部分 coverage。這個表是 **snapshot timestamp coverage**，不是模型準確率，也不是完整 station-row target coverage。

完整 station-row coverage 還需以受保護 CSV export 執行 `src/audit_track_b.py`，同時檢查 station 是否在 future snapshot 存在且 current／future 均為 active。

## 5. 新增的可重現工具

### Cloud D1 read-only audit

`cloudflare/track-b-collector/queries/track_b_coverage_audit.sql` 保存本次使用的唯讀查詢：run status、retry、gap 與 30／60 分鐘 timestamp coverage。

```bash
cd cloudflare/track-b-collector
pnpm exec wrangler d1 execute youbike-track-b-live \
  --remote \
  --file queries/track_b_coverage_audit.sql
```

### Exported station-row audit

先由 owner 在本機安全設定既有 `EXPORT_TOKEN`；token 不可寫入 Git 或對話：

```bash
export TRACK_B_EXPORT_URL="https://youbike-track-b-collector.mieuxander.workers.dev/export.csv"
export TRACK_B_EXPORT_TOKEN="<owner secret>"
python src/export_track_b.py \
  --start 2026-08-21 \
  --end 2026-08-29 \
  --output data/processed/track_b_week_1.csv

python src/audit_track_b.py \
  --input data/processed/track_b_week_1.csv
```

Audit 會輸出：

- `results/track_b_live_audit.json`
- `results/track_b_live_gaps.csv`
- `results/track_b_target_coverage.csv`

Future target coverage 直接沿用既有 `add_future_targets()` 邏輯，不另創 target 定義。

## 6. 決策

1. Collector 保持運作，不重新啟動也不停止。
2. 目前資料已證明 30／60 分鐘 timestamp alignment 可行。
3. 連續完整 7 天 cloud audit 已通過；授權全量 CSV station-row audit 與 preliminary baseline 隨後已在 Stage 15 完成。
4. Collector 持續累積至 14／28 天；Stage 15 不停止或重新啟動雲端 collector。

## 7. 已知限制

- Snapshot-time coverage 不等於 active station-row target coverage。
- 已有缺口後完整連續 7 天，但整個資料集第一天仍保留一段 65 分鐘缺口。
- D1 大小是稽核當下 metadata；會隨每五分鐘寫入持續增加。
- 快照差值仍混合租借、還車、調度及資料修正，不可稱為純需求。
- 尚無 Track B train／validation／test split、baseline metrics 或 risk threshold。
