# Track B offline 60-minute model card

Date: 2026-09-27. Supplementary retrospective study; not a replacement for the Stage 17/19 frozen models. See the [full Phase 3–4 report](PHASE_3_4_OFFLINE_RESEARCH.md) and [protocol](OFFLINE_RESEARCH_PROTOCOL.md).

## Intended use

Compare persistence, sequence-aligned HGB and a bounded LSTM; supply the development-selected forecaster to a small static redistribution **simulation**. Not for live guidance, calibrated risk probabilities or operator dispatch. Track A transfer demand is a separate target.

## Data and input contract

Existing 2026-08-21 09:45:02Z through 2026-09-18 09:45:02Z export (exclusive end), 64 training-selected stations. Chronological 18/5/5-day split; target-boundary purge. Training 54,656 sampled sequences, validation 86,912 and common retrospective evaluation 89,600. Previous Stage 17/19 exposure is disclosed; these are not new independent results.

Raw NumPy input shape `[N,13,9]`, oldest to current within one station; finite values. Feature order:

1. available_bikes
2. available_return_bikes
3. capacity
4. latitude
5. longitude
6. hour_sin
7. hour_cos
8. weekday_sin
9. weekday_cos

Calendar values use Asia/Taipei; hour includes minutes. The sequence builder validates activity, capacities and consecutive 270–330-second intervals. The low-level `predict` API validates shape/finiteness but cannot establish chronology/activity without timestamps; callers must use `station_sequences` or enforce that contract. Future labels must never be supplied as features. Source timestamps can lag actual physical state; no exact real-time availability guarantee.

Standardization and delta scale are training-only. Both learned models predict change relative to current stock, then clip to capacity. HGB uses flattened sequence; LSTM uses a single recurrent layer (32 units). Two LSTM learning rates and three seeds were fixed before evaluation. Validation-selected candidate 0.003; primary LSTM averages seeds 11, 29, 47, not the best evaluation seed.

## Performance and decision

On the common 89,600-row retrospective scope: MAE persistence 3.431339; HGB **3.249886**; LSTM ensemble 3.326271 bikes. LSTM seed MAE mean/std 3.354364/0.022933. RMSE, R², timings and errors by station/hour are in [results](../results/offline_research/comparison.csv). HGB was chosen for simulation by validation MAE before retrospective evaluation; LSTM is not adopted. This does not imply all LSTM designs are inferior.

## Artifacts and safe inference

- `models/offline_research/`: new HGB/scaler joblib, six LSTM state dictionaries, `selection.json` with model hashes, development scores, seed histories and environment.
- `results/offline_research/data_manifest.json`: source/cache SHA-256, exact station list and boundaries.
- `config/offline_research.json`: fixed experiment and simulation settings.
- `src/offline_forecasting.py`: prepare/pilot/train/evaluate/predict, with separate `--run-dir` for reproductions.

`load_selection` verifies config, data-manifest and model hashes before loading. Only load trusted repository joblib files (pickle-based, not an untrusted interchange format). PyTorch loads state dictionaries with `weights_only=True`. Same-version CPU reload tolerance: absolute 1e-5, relative 1e-6; hardware/library changes and training runtimes may differ. Full environment is recorded; exact cross-platform bitwise retraining is not promised.

## Limitations

Limited cohort and fixed four weeks; researcher-selection bias from prior results; no random-split claims, significance tests, seasonal validation, external operator costs or live deployment. Current stock and capacity are not a complete operational dock-status model. Simulated half-capacity deviation is not shortage probability, lost trips or verified real-world benefit. This card closes the bounded study; it does not authorize additional research.
