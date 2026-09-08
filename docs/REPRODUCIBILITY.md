# Reproducibility Guide

This guide collects the repository's supported local commands. The public README focuses on research questions, evidence, and current status; the Stage documents linked below explain the design and interpretation of each pipeline.

Large raw and processed datasets are intentionally excluded from Git. Commands that depend on those datasets require the corresponding source files or an authorized Track B export.

## Environment

From the repository root:

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements.txt
jupyter notebook
```

Run the Python validation suite:

```bash
python -m unittest discover -s tests -v
```

## Track A: historical transfer demand

### Prepare the 2023 data and weather

```bash
python src/download_historical.py --month all
python src/prepare_historical_collection.py
python src/download_weather.py
python src/prepare_weather.py
```

The pipeline processes the official monthly files, creates station-hour transfer-demand data, and joins 8,760 hourly weather records. See the [historical demand guide](STAGE_4_HISTORICAL_DEMAND.md) and [weather integration guide](STAGE_5_FULL_YEAR_WEATHER.md).

### Reproduce model comparisons and analysis

```bash
python src/train_baseline.py
python src/train_tree_models.py
python src/train_xgboost.py
python src/run_track_a_analysis.py
```

On macOS, XGBoost also requires OpenMP:

```bash
brew install libomp
```

The controlled experiment design and outputs are documented in the [baseline guide](STAGE_6_BASELINE_MODEL.md), [HGB comparison](STAGE_7_TREE_MODEL_COMPARISON.md), [XGBoost comparison](STAGE_10_XGBOOST_COMPARISON.md), and [ablation and error analysis](STAGE_12_FEATURE_ABLATION_ERROR_ANALYSIS.md).

### Run one historical prediction

```bash
python src/predict_hourly.py \
  --target-time 2023-12-31T18:00:00+08:00 \
  --include-actual \
  --output results/example_hourly_predictions.csv
```

`--include-actual` is a historical backtest option: actual values are attached only after prediction. Remove it for inference without backtest output. The bundled 2023 inputs do not support a current forecast. See the [prediction-interface guide](STAGE_8_PREDICTION_INTERFACE.md) and [model card](MODEL_CARD.md).

### Historical Dashboard

Rebuild the existing ten-timepoint static bundle only when the underlying research artifacts intentionally change:

```bash
python src/build_dashboard_data.py
```

Run and check the dashboard locally:

```bash
cd dashboard
pnpm install
pnpm run dev
pnpm run lint
pnpm test
```

The interface is a historical holdout demonstration, not a live inventory display. See the [dashboard guide](STAGE_9_HISTORICAL_DASHBOARD.md) and [dashboard-local README](../dashboard/README.md).

## Track B: station availability

### Local collector for testing and fallback

```bash
python src/collect_youbike.py
python src/collect_history.py --count 12 --interval-minutes 5
python src/prepare_data.py
python src/build_features.py
```

These commands require the computer and process to remain active. Formal long-running collection runs in Cloudflare Worker + Cron + D1. See the [snapshot pipeline guide](STAGE_2_DATA_PIPELINE.md), [feature guide](STAGE_3_HISTORY_AND_FEATURES.md), and [cloud collection guide](STAGE_11_TRACK_B_CLOUD_COLLECTION.md).

### Authorized cloud export

Never place the export token in Git or pass it as a command-line argument. On the configured macOS workstation:

```bash
export TRACK_B_EXPORT_URL="https://youbike-track-b-collector.mieuxander.workers.dev/export.csv"
export TRACK_B_EXPORT_TOKEN="$(security find-generic-password \
  -a "$USER" -s youbike-track-b-export -w)"
python src/export_track_b.py \
  --start 2026-08-21 \
  --end 2026-08-27 \
  --output data/processed/track_b_week_1.csv
unset TRACK_B_EXPORT_TOKEN
```

Add `--station-id <station_id>` to limit the export to one station. Date-only bounds are interpreted in Asia/Taipei; exported timestamps are UTC ISO-8601.

### Audit and historical baseline records

```bash
python src/audit_track_b.py \
  --input data/processed/track_b_week_1.csv

python src/track_b_baseline.py \
  --input data/processed/track_b_week_1.csv

python src/track_b_stability.py \
  --input data/processed/track_b_14_days.csv \
  --start 2026-08-21T09:45:02Z \
  --end 2026-09-04T09:45:02Z \
  --output-dir results
```

The seven-day audit and preliminary baseline remain historical evidence. The current completed checkpoint is the fixed fourteen-day stability analysis. See the [first cloud audit](STAGE_14_TRACK_B_FIRST_COVERAGE_AUDIT.md), [seven-day preliminary baseline](STAGE_15_TRACK_B_PRELIMINARY_BASELINE.md), and [fourteen-day stability analysis](STAGE_16_TRACK_B_14_DAY_STABILITY.md).

## Cloud collector checks

From `cloudflare/track-b-collector/`:

```bash
pnpm test
```

Deployment, D1 migration, secret rotation, and production export procedures are intentionally kept in the [Track B cloud guide](STAGE_11_TRACK_B_CLOUD_COLLECTION.md). They require the project owner's Cloudflare authorization and are not part of routine local verification.
