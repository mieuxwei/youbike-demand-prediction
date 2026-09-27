# Stage 19 — Track B Pre-Registered Independent Temporal Validation

## 1. Current status

Stage 19-B was executed on **2026-09-27 Asia/Taipei**. The evaluation window, frozen artifacts, checksums, comparison baseline, data-quality gates, and promotion rules were recorded on 2026-09-19 before the independent export existed. Both horizons pass the data-quality gates. The 30-minute HGB does not beat persistence on MAE; the 60-minute HGB passes all independent gates and supports a modest improvement across both evaluated windows.

No model is retrained or tuned in this stage. No Stage 17 holdout result is replaced.

## 2. Fixed time window

| Role | UTC | Asia/Taipei |
|---|---|---|
| History warm-up start | 2026-09-18 17:30:00 | 2026-09-19 01:30:00 |
| Evaluation start | 2026-09-18 18:30:00 | 2026-09-19 02:30:00 |
| Evaluation end, exclusive | 2026-09-25 18:30:00 | 2026-09-26 02:30:00 |

The first hour is used only to construct the frozen 15/30/60-minute lag and 30/60-minute rolling features. It is excluded from metrics. Future labels crossing the evaluation end are purged, matching the Stage 17 split-boundary rule.

The evaluation interval is entirely later than the Stage 17 holdout end (`2026-09-18 09:45:02 UTC`).

## 3. Frozen evidence

| Horizon | Artifact SHA-256 | Metadata SHA-256 | Stage 17 primary MAE gate |
|---:|---|---|---|
| 30m | `47f37095e1ee8e2d208fa8e0136a75e20005aecfd81afda6ffe33f8685bd202b` | `1d6d0d72be3510c55adef1d552f76142e1e92ce128c7fffa59045de7866f9a41` | Failed: HGB 2.057 vs persistence 2.043 |
| 60m | `d4bc2df1c815a7c722e900891b668d3b2a7124f66966913081cb957b5ec7e6f6` | `b583107f9416cf161e3d937c3b09f1b20e433f6579c62651c5e2cf09068cf356` | Passed: HGB 2.922 vs persistence 3.012 |

The feature/training configuration is also frozen at SHA-256 `6a1fb0ace9044086973ba8bd5aad44b42df9dbfd208b79e8026f185d3ae7289f`. The validation runner checks every checksum before loading a model.

## 4. Pre-registered gates

Data quality must satisfy all applicable checks:

- at least 99.0% of the expected 2,016 five-minute snapshots;
- zero duplicate station-time keys;
- at least 95.0% usable active-row coverage for each target after complete-feature and end-boundary rules.

The frozen learned model passes its independent temporal gate only when:

- learned MAE is strictly lower than persistence MAE;
- learned RMSE is strictly lower than persistence RMSE;
- learned MAE is lower for at least 50% of evaluated stations;
- the data-quality gate passes.

The learned model is confirmed across both windows only when its Stage 17 primary MAE gate and this independent gate both pass. Therefore, a 30-minute independent win would still be reported as mixed evidence because its Stage 17 MAE did not beat persistence. A failed or mixed independent result is not hidden and does not trigger tuning on this window.

## 5. Stage 19-B execution

Run only after `2026-09-26 02:30 Asia/Taipei`:

```bash
python src/validate_track_b_temporal.py --check-only
```

This verifies the frozen training config, metadata, model checksums, feature schema, horizons, and non-overlapping evaluation boundary without requiring the future CSV.

```bash
export TRACK_B_EXPORT_URL="https://youbike-track-b-collector.mieuxander.workers.dev/export.csv"
export TRACK_B_EXPORT_TOKEN="$(security find-generic-password \
  -a "$USER" -s youbike-track-b-export -w)"
python src/export_track_b.py \
  --start 2026-09-18T17:30:00Z \
  --end 2026-09-25T18:30:00Z \
  --output data/processed/track_b_independent_7d.csv
unset TRACK_B_EXPORT_TOKEN

python src/validate_track_b_temporal.py \
  --input data/processed/track_b_independent_7d.csv \
  --config config/track_b_temporal_validation.json \
  --output-dir results
```

The raw export remains Git-ignored. Compact outputs are:

- `results/track_b_independent_summary.json`
- `results/track_b_independent_metrics.csv`
- `results/track_b_independent_coverage.csv`
- `results/track_b_independent_gaps.csv`
- `results/track_b_independent_station_errors.csv`
- `results/track_b_independent_hour_errors.csv`
- `results/track_b_independent_provenance.json` (execution date, input hash, counts, environment, cloud checkpoint)

## 6. Implementation and tests

- `config/track_b_temporal_validation.json`
- `src/validate_track_b_temporal.py`
- `tests/test_track_b_temporal_validation.py`

Tests cover timezone-aware seven-day boundaries, real repository artifact/hash matching, checksum rejection before model loading, end-boundary target purging, expected-slot and gap counting, and pre-registered decision outcomes.

Stage 19-A validation completed with 72 Python repository tests and 11 Cloudflare collector Node tests passing. The CLI help smoke test and `git diff --check` also pass.

## 7. Research boundary

This stage evaluates frozen 30/60-minute available-bike regressions. It does not train a shortage/full-station classifier, choose a risk threshold, create a live prediction service, or justify redistribution optimization. Those remain conditional future stages.

## 8. Stage 19-B execution record — 2026-09-27

The protocol was committed as `3055c856b246680efbda2383d2fbf8e401816f4e` at **2026-09-19 02:12:22 Asia/Taipei**, before the evaluation start at 02:30. On September 27, the originally specified export was downloaded using the existing Keychain-backed authorization. Neither the evaluation window nor the frozen artifacts/configuration was changed.

| Export measure | Result |
|---|---:|
| Rows including one-hour warm-up | 3,657,741 |
| Snapshots including warm-up | 2,028 |
| Distinct stations including warm-up | 1,807 |
| Evaluation rows before eligibility filters | 3,636,105 |
| Evaluation snapshots | 2,016 |
| Rows per snapshot | 1,803–1,807 |

The raw CSV remains Git-ignored. Its SHA-256 is `7411c066535d3562d76e84d18bac4b915387e817dccca5d5c68ec4a141d67943`. Exact input boundaries, runtime versions, protocol hash, and the dated cloud observation are recorded in [`track_b_independent_provenance.json`](../results/track_b_independent_provenance.json). Export row counts are not the final model evaluation scope; inactive rows, incomplete features, unavailable labels, and labels crossing the end boundary are excluded by the frozen runner.

### Source freshness limitation

All 2,016 distinct five-minute evaluation slots are represented and the export has zero duplicate station-time keys. This does not prove uniform source freshness: four evaluation snapshots have `snapshot_time - source_update_time` greater than 300 seconds, including two above 600 seconds; the maximum is 1,092 seconds (18.2 minutes). One snapshot has a negative difference, with an export-wide minimum of −51 seconds. The collector stores the scheduled event time as `snapshot_time`, so source updates fetched after that event can be later than this timestamp. The CSV alone does not establish the precise cause of that instance.

These are descriptive diagnostics, not additional pre-registered gates or post-hoc exclusions. Results concern the recorded feed and scheduled timestamps, not exact physical inventory at a guaranteed instantaneous horizon. Upstream staleness and execution latency remain limitations for a future live service.

### Data-quality gates

| Measure | Result | Frozen requirement |
|---|---:|---:|
| Evaluation snapshot coverage | 2,016 / 2,016 (100%) | ≥99% |
| Duplicate station-time keys | 0 | 0 |
| Estimated missing slots | 0 | Descriptive |
| Maximum consecutive snapshot gap | 5.05 minutes | Gaps above 5.5 minutes reported |
| Active current rows | 3,578,354 | Denominator for target coverage |
| Complete-feature rows | 3,578,198 | Same frozen feature schema |
| Usable 30m rows / active rows | 3,567,488 / 3,578,354 (99.696%) | ≥95% |
| Usable 60m rows / active rows | 3,556,778 / 3,578,354 (99.397%) | ≥95% |

Source: [coverage](../results/track_b_independent_coverage.csv) and [summary](../results/track_b_independent_summary.json). Each horizon evaluates 1,783 eligible stations, not all 1,807 stations observed in the export. No missing observation is fabricated.

### Independent model results

The target is future **available bikes**, in bikes per station observation. Persistence predicts the current available-bike count; it is not fitted or updated. Each pair below uses identical eligible rows in the fixed seven-day evaluation interval.

| Horizon | Model | Rows | MAE | RMSE | R² |
|---:|---|---:|---:|---:|---:|
| 30m | Persistence | 3,567,488 | **1.950** | 3.455 | 0.854 |
| 30m | Frozen HGB | 3,567,488 | 1.981 | **3.253** | **0.871** |
| 60m | Persistence | 3,556,778 | 2.862 | 4.833 | 0.714 |
| 60m | Frozen HGB | 3,556,778 | **2.813** | **4.389** | **0.764** |

Source: [full-precision metrics](../results/track_b_independent_metrics.csv).

| Horizon | MAE change vs persistence | RMSE reduction | Stations with lower learned MAE | Decision |
|---:|---:|---:|---:|---|
| 30m | 1.56% worse | 5.84% | 608 / 1,783 (34.10%) | Keep persistence as the primary baseline |
| 60m | 1.71% better | 9.19% | 1,048 / 1,783 (58.78%) | Pass all independent gates |

The 30m result fails both the primary MAE and station-majority gates despite lower RMSE. Its Stage 17 MAE also failed to beat persistence. The 60m result passes data quality, MAE, RMSE, and station-majority gates; combined with its Stage 17 MAE improvement of 2.98%, it satisfies the pre-registered cross-window rule. This is not a claim of statistical significance, improvement at every station, or seasonal generalization. No confidence interval or dependence-aware significance test was part of this protocol.

### Error context

The [station error table](../results/track_b_independent_station_errors.csv) and [Taipei-hour error table](../results/track_b_independent_hour_errors.csv) retain all evaluated groups. HGB has lower MAE in 10 of 24 hour groups at 30m and 16 of 24 at 60m. The largest 30m learned hour-level MAEs occur at 17:00, 07:00, and 08:00 (3.005, 2.912, 2.869); the largest 60m values occur at 07:00, 16:00, and 17:00 (4.170, 4.078, 4.031). Mean prediction-minus-actual error is +0.119 bikes at 30m and +0.226 at 60m. These are descriptive findings, not tuning inputs or inferred causes.

### Execution verification

- Frozen 30m/60m artifact, metadata, training config, and feature-schema checks passed.
- Original validation CLI completed successfully; models, features, gates, and Stage 17 outputs were not modified.
- Repository Python tests: **72 passed**; Cloudflare collector Node tests: **11 passed**.
- CLI `--check-only` and `--help`, JSON/CSV structural checks, 80 local Markdown link targets across the six updated documents, and `git diff --check` passed. Hosted Dashboard accessibility was not rechecked in this run.
- The initial local scientific-package import was slow but completed without reinstalling dependencies. Non-failing LibreSSL and physical-core detection warnings were observed; the latter fell back to logical cores.
- No collector restart, deployment, token reset, Dashboard bundle regeneration, or model training was performed.

## 9. Research conclusion and delivery boundary

The current research conclusion is fixed to **30m persistence / 60m HGB with a modest cross-window gain**. Keep Stage 17 and Stage 19 evidence separately; do not select new parameters using either evaluated window. A later experiment needs a new protocol and untouched future evaluation data.

For the current delivery, preserve Track A, the historical Dashboard, the cloud data pipeline, and both Track B evaluation records. Remaining delivery checks concern documentation links, demonstration accessibility, and reproducibility. The repository remains **In Progress**: risk labels/costs, live model serving, seasonal validation, and redistribution optimization are outside the completed research scope. The cloud collector continues accumulating observations.
