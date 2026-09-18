# Stage 19 — Track B Pre-Registered Independent Temporal Validation

## 1. Current status

Stage 19-A infrastructure is complete. The evaluation window, frozen artifacts, checksums, comparison baseline, data-quality gates, and promotion rules were recorded on 2026-09-19 before the independent export exists. Stage 19-B execution is scheduled after the exclusive window end on 2026-09-26 Asia/Taipei.

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

## 6. Implementation and tests

- `config/track_b_temporal_validation.json`
- `src/validate_track_b_temporal.py`
- `tests/test_track_b_temporal_validation.py`

Tests cover timezone-aware seven-day boundaries, real repository artifact/hash matching, checksum rejection before model loading, end-boundary target purging, expected-slot and gap counting, and pre-registered decision outcomes.

Stage 19-A validation completed with 72 Python repository tests and 11 Cloudflare collector Node tests passing. The CLI help smoke test and `git diff --check` also pass.

## 7. Research boundary

This stage evaluates frozen 30/60-minute available-bike regressions. It does not train a shortage/full-station classifier, choose a risk threshold, create a live prediction service, or justify redistribution optimization. Those remain conditional future stages.
