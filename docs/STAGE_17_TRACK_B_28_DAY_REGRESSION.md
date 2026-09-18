# Stage 17 — Track B 28-Day Audit and First Learned Regression

## 1. Purpose and boundary

This stage uses the fixed 28-day cloud snapshot window to audit Track B data and train the first learned regressions for future station inventory. The targets are the number of available bikes 30 and 60 minutes after each observation.

This is not rental-demand estimation, shortage/full-station classification, a live production prediction service, or redistribution optimization. Track A models and the historical Dashboard are unchanged.

## 2. Fixed dataset

The analysis uses a half-open UTC interval:

```text
[2026-08-21 09:45:02 UTC, 2026-09-18 09:45:02 UTC)
```

The previously verified first 14-day export was combined with a newly authorized second 14-day export. Both files had the same schema and a continuous five-minute boundary: the first ended at `2026-09-04 09:40:21 UTC`, and the second began at `2026-09-04 09:45:21 UTC`. Raw CSV files remain Git-ignored.

| Export | Station rows | SHA-256 |
|---|---:|---|
| Days 1–14 | 7,240,919 | `8f4d4939977c4c5be5639e712048f82aab75410ac05787526a55aba2cabe6c43` |
| Days 15–28 | 7,249,230 | `c5ecfe933acd009fca7e191b4388fbe356dfec40c15138187853d4eed0e2bae0` |
| Combined | 14,490,149 | Local analysis input; not committed |

## 3. Data audit

| Measure | Result |
|---|---:|
| Station rows | 14,490,149 |
| Snapshots | 8,058 |
| Distinct stations | 1,803 |
| Duplicate station-time keys | 0 |
| Rows per snapshot | 1,794–1,803 |
| Estimated missing five-minute slots | 7 |
| Maximum gap | 10 minutes |
| 30-minute target coverage | 97.971% |
| 60-minute target coverage | 97.750% |

All seven gaps are isolated 10-minute intervals. No missing snapshot is imputed or fabricated. Target construction accepts only an active future observation between the requested horizon and horizon plus two minutes.

## 4. Chronological evaluation design

The split was fixed before model comparison:

| Split | UTC interval | Days | Raw rows | Snapshots | Stations |
|---|---|---:|---:|---:|---:|
| Train | `[2026-08-21 09:45:02, 2026-09-08 09:45:02)` | 18 | 9,312,719 | 5,182 | 1,800 |
| Validation | `[2026-09-08 09:45:02, 2026-09-13 09:45:02)` | 5 | 2,588,400 | 1,438 | 1,800 |
| Test | `[2026-09-13 09:45:02, 2026-09-18 09:45:02)` | 5 | 2,589,030 | 1,438 | 1,803 |

Future labels crossing a split boundary are purged. Model choice uses validation MAE only. The holdout test is evaluated only after selecting the candidate. Persistence and learned models use identical complete-case test rows.

To bound training cost without changing the validation or test scope, training uses every sixth snapshot while retaining the full station cross-section at each selected time. This produces 1,513,331 training rows for the 30-minute target and 1,509,783 for the 60-minute target. Final evaluation still uses 2.5 million test rows per horizon.

## 5. Predictors and candidates

All predictors are available at prediction time:

- current bikes, return spaces, capacity, and availability fractions;
- station latitude and longitude;
- Asia/Taipei cyclical hour and weekday features, weekend, and rush-hour flags;
- time-aligned 15/30/60-minute past availability and changes;
- past-only 30/60-minute rolling means and observation counts.

Future targets never enter predictors. UTC is retained for storage and alignment; Asia/Taipei is used only for calendar features.

Two Histogram Gradient Boosting candidates were compared:

| Horizon | Candidate | Validation MAE | RMSE | R² |
|---:|---|---:|---:|---:|
| 30m | HGB shallow | 1.912 | 3.219 | 0.881 |
| 30m | **HGB regularized** | **1.892** | **3.188** | **0.883** |
| 60m | HGB shallow | 2.741 | 4.364 | 0.782 |
| 60m | **HGB regularized** | **2.700** | **4.305** | **0.788** |

The regularized candidate was selected independently for both horizons.

## 6. Holdout results

| Horizon | Model | Test rows | MAE | RMSE | R² |
|---:|---|---:|---:|---:|---:|
| 30m | Persistence | 2,518,633 | **2.043** | 3.702 | 0.846 |
| 30m | HGB regularized | 2,518,633 | 2.057 | **3.454** | **0.866** |
| 60m | Persistence | 2,507,965 | 3.012 | 5.190 | 0.697 |
| 60m | HGB regularized | 2,507,965 | **2.922** | **4.645** | **0.757** |

At 30 minutes, HGB reduces RMSE by 6.70% but its MAE is 0.68% worse than persistence. It therefore does not establish a general 30-minute improvement. At 60 minutes, HGB improves MAE by 2.98% and RMSE by 10.51% on the fixed holdout. This is a modest first learned-model result, not a production-readiness claim.

## 7. Error analysis

The complete-case test scope contains 1,777 stations for both horizons.

- At 30 minutes, HGB improves station-level MAE for 716 of 1,777 stations; the median station change is 1.16% worse than persistence.
- At 60 minutes, HGB improves station-level MAE for 1,138 of 1,777 stations; the median station improvement is 2.63%.
- The largest hourly errors occur around commuting periods. At local hour 07, learned MAE is 3.580 for 30 minutes and 5.024 for 60 minutes, but both are lower than their matching persistence errors of 3.913 and 5.789.
- A small set of stations still has much larger errors than the overall average, so station-specific diagnostics remain necessary before any risk layer.

## 8. Artifacts

- `config/track_b_regression.json`
- `src/train_track_b_regression.py`
- `tests/test_track_b_regression.py`
- `models/track_b_30m_regression.joblib`
- `models/track_b_60m_regression.joblib`
- `models/track_b_30m_regression.metadata.json`
- `models/track_b_60m_regression.metadata.json`
- `results/track_b_28d_live_audit.json`
- `results/track_b_28d_live_gaps.csv`
- `results/track_b_28d_target_coverage.csv`
- `results/track_b_28d_split_summary.csv`
- `results/track_b_28d_feature_coverage.csv`
- `results/track_b_28d_model_tuning.csv`
- `results/track_b_28d_model_metrics.csv`
- `results/track_b_28d_station_errors.csv`
- `results/track_b_28d_hour_errors.csv`
- `results/track_b_28d_training_summary.json`

Artifact SHA-256 values are recorded in the matching metadata files. The 30-minute artifact hash is `47f37095e1ee8e2d208fa8e0136a75e20005aecfd81afda6ffe33f8685bd202b`; the 60-minute artifact hash is `d4bc2df1c815a7c722e900891b668d3b2a7124f66966913081cb957b5ec7e6f6`.

## 9. Decision and next step

Validation completed with 66 Python repository tests and 9 Cloudflare collector Node tests passing. Model artifact hashes match their metadata, local Markdown targets resolve, and `git diff --check` passes.

Track B learned regression has started and produced its first fixed holdout evidence. The 30-minute model does not beat persistence on MAE; the 60-minute model shows a modest improvement. Neither result defines a shortage/full-station event or supports redistribution decisions yet.

Recommended next work:

1. Preserve this split and result as the Stage 17 baseline.
2. Investigate station and commuting-hour errors without touching the holdout for model selection.
3. Define shortage/full-station labels, thresholds, class imbalance handling, and false-alarm/miss costs before beginning classification.
4. Continue collecting cloud data for future temporal validation; do not stop the collector after this fixed analysis.
5. Delay optimization until a risk target and operational constraints are explicit.
