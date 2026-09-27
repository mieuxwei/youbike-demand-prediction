# Live demonstration engineering protocol — 2026-09-27

Research remains frozen at preservation commit `159f059`. This explicitly authorized delivery reopens presentation/serving only. No fitting, evaluation-window changes, new research dataset export or model search. Bounded operational reads for live inference and serving parity are not new evaluation data windows.

## Fixed choices, before observing live performance

- Use all 12 Phase 4 stations, in their saved order in `results/offline_research/optimization.json`. These were chosen by training-period coordinates: lexicographically first of the 64-station cohort and its nearest neighbours. Do not remove poor-looking stations. This is a geographic demonstration subset, not representative all-city evaluation.
- 30 minutes: persistence, current available bikes unchanged. 60 minutes: the original Stage 17 HGB, independently checked in Stage 19, SHA-256 `d4bc2df1c815a7c722e900891b668d3b2a7124f66966913081cb957b5ec7e6f6`. Never substitute the later Phase 3 HGB or LSTM.
- Export the frozen numeric trees losslessly to server-only JSON and execute them in the existing Cloudflare Worker. Assert installed sklearn version, feature order and numeric-only trees. No model or history is delivered to the browser. No extra hosting service or credential is required.
- Match Stage 17's 23 ordered features: float32 coordinates/ratios/calendar, UTC snapshot keys, Asia/Taipei hour and Monday-zero weekday, backward-only 15/30/60 minute lags with two-minute tolerance, rolling `[t-window,t)` active observations, original capacity clipping. Predictions are from scheduled snapshot time, not page-load time.
- Verify conversion against Python's original feature builder/model using all 12 stations at six fixed historical origins: 2026-09-19 03:30/07:00/12:00/17:00/23:55 and 2026-09-20 00:00 Asia/Taipei (first observation within six minutes). The initially requested midnight origin precedes the existing export's 01:30 start and was moved to 03:30 solely for available warm-up, before parity results were computed. This is serving parity, not new performance evaluation.

## Read-only endpoint and conservative serving gates

`GET /demo/live` accepts no filters or date ranges. It reads the latest successful completed run and at most 16 rows per fixed station, only the preceding 65 minutes, via the existing primary key. Response includes current observations, run timestamps, computed forecasts, per-station status, expiry and model identity; it excludes historical rows, trees and export credentials. Public CORS is intentional for these bounded public-source summaries. Protected `/export.csv`, Cron, collection schema and retry behavior stay unchanged.

Current scheduled snapshot and upstream source timestamp must be no more than ten minutes old and no more than 60 seconds ahead of server time; source cannot exceed fetch completion by more than 60 seconds. Inactive/missing/invalid observations suppress both forecasts. Station update time is shown separately and is not assumed to be a heartbeat. For 60m, require valid active continuous history through at least 60 minutes, every interval 270–330 seconds, all three backward lag matches, no stale/anomalous historical source timestamp, and unchanged capacity/location throughout that history. These conservative live gates do not alter historical research eligibility or metrics. Unsupported stations are rejected, never substituted.

Shared edge cache lasts at most 30 seconds; client refresh is 60 seconds. Server validity expires at the earliest current source/snapshot ten-minute limit. Client independently hides predictions after expiry, on network errors, and when client clock materially disagrees with server; no old response masquerades as live. A deployment with invalid model data or failed inference yields explicit unavailable output, not persistence relabeled HGB.

Phase 4 remains recorded static simulation, not current operational advice. Track A does not feed Track B. Inventory changes are not rental-event counts. Final publication and freeze require separately recorded actual acceptance results.
