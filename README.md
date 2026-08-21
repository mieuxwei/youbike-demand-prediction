# YouBike Demand Prediction & Optimization

## Project Overview

This project studies short-term YouBike station demand using historical usage
data, weather information, and time-based features. The long-term goal is to
combine demand forecasting with a bike redistribution strategy.

## Track A vs Track B

The repository contains two separate research tracks with different data and
targets:

- **Track A — historical transfer-demand forecasting:** predicts hourly
  transfer-related borrowing demand for 100 high-demand stations from the 2023
  official trip dataset. HGB remains the best evaluated model. The React/Vinext
  dashboard is a historical holdout demonstration of this track.
- **Track B — live bike-availability forecasting:** will predict available
  bikes 30 or 60 minutes ahead and later study shortage/full-station risk. Its
  cloud data-collection infrastructure is deployed and multi-day data
  accumulation is in progress. No Track B prediction
  model or optimization result is claimed yet.

Track A hourly demand is not interchangeable with Track B future station
inventory and must not be used directly as a shortage or redistribution label.

## Objectives

- Explore spatial and temporal YouBike usage patterns.
- Build reproducible data-cleaning and feature-engineering pipelines.
- Train and compare baseline machine-learning models for demand prediction.
- Evaluate models with appropriate forecasting metrics.
- Explore redistribution optimization after a reliable forecasting baseline is
  available.

## Planned Workflow

1. Collect and document official YouBike and weather data.
2. Inspect data quality, missing values, and station coverage.
3. Clean and transform the raw data.
4. Create time, weather, and station-level features.
5. Establish a simple baseline model.
6. Train and compare machine-learning models.
7. Evaluate errors by station and time period.
8. Use validated forecasts to explore redistribution optimization.

## Dataset

The real-time samples come from the official
[Taipei City YouBike 2.0 real-time dataset](https://data.taipei/dataset/detail?id=c6bc8aed-557d-41d5-bfb1-8da24f78f2fb).
The source is public, free to use, provided as JSON, and updated every minute.

The repository contains two reproducible snapshots of station availability. Their fields
include station ID and name, district, capacity, available bikes, return spaces,
location, operating status, and update times.

> Bike-count changes between snapshots are not direct rental counts. They may
> include rentals, returns, redistribution, and data corrections. More history
> is required before short-term demand can be modeled reliably.

The project also uses all 12 monthly files from the official
[2023 transfer-related YouBike trip dataset](https://data.gov.tw/dataset/169174)
for historical hourly demand analysis. This source covers trips associated with
bus or MRT transfers, not all YouBike trips, and its timestamps are aggregated
to the hour. It complements rather than replaces the real-time snapshots.

Hourly weather comes from the
[Open-Meteo Historical Weather API](https://open-meteo.com/en/docs/historical-weather-api).
The current integration uses one Taipei reference point and historical
reanalysis values, not a separate observed weather station at every YouBike
location.

## Tech Stack

- Python
- Jupyter Notebook
- pandas
- NumPy
- Matplotlib
- scikit-learn
- XGBoost
- Requests
- Cloudflare Workers, Cron Triggers, and D1

Additional libraries will be added only when the project reaches the stage that
requires them.

## Project Structure

```text
youbike-demand-prediction/
├── data/
│   ├── raw/          # Original, unmodified source data
│   └── processed/    # Cleaned and feature-ready data
├── notebooks/        # Exploration and experiment notebooks
├── src/              # Reusable data and modeling code
├── tests/            # Automated pipeline tests
├── docs/             # Stage explanations and project documentation
├── config/           # Reproducible official data-source registry
├── models/           # Saved model artifacts
├── results/          # Metrics, tables, and experiment outputs
├── images/           # Figures and images used in reports
├── cloudflare/        # Track B cloud collector, D1 migration, and tests
├── .gitignore
├── LICENSE
├── PROJECT_PLAN.md
├── README.md
└── requirements.txt
```

## Getting Started

Create and activate a virtual environment, then install the current
dependencies:

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements.txt
jupyter notebook
```

## Collecting Snapshots

### Cloud collection for Track B

The production design uses a standalone Cloudflare Worker, a five-minute Cron
Trigger, and D1. It validates the confirmed official API schema, stores UTC
station-time rows with database-level duplicate prevention, retries bounded API
failures, logs every run, and exposes a protected paginated CSV export.

The cloud source is under `cloudflare/track-b-collector/`. The production Worker
is running at `https://youbike-track-b-collector.mieuxander.workers.dev`, with a
`*/5 * * * *` Cron Trigger and D1 storage. The first scheduled run on 2026-08-21
wrote 1,794 station rows successfully. Multi-day accumulation is still in
progress, and the repository owner must still configure `EXPORT_TOKEN` before
using the protected CSV export. See the
[Stage 11 deployment record](docs/STAGE_11_TRACK_B_CLOUD_COLLECTION.md).

After deployment, export a date range for Python with:

```bash
export TRACK_B_EXPORT_URL="https://youbike-track-b-collector.mieuxander.workers.dev/export.csv"
export TRACK_B_EXPORT_TOKEN="<secret>"
python src/export_track_b.py \
  --start 2026-08-21 \
  --end 2026-08-27 \
  --output data/processed/track_b_week_1.csv
```

Add `--station-id <station_id>` for a single station. Exported timestamps are
UTC ISO-8601 and must be converted explicitly to `Asia/Taipei` before creating
calendar features.

### Local fallback collector

Run the collector once to save a timestamped snapshot from the official API:

```bash
python src/collect_youbike.py
```

Snapshots are saved under `data/raw/snapshots/`. The JSON files in that folder
are intentionally ignored by Git because repeated collection will create a
large local dataset.

Collect multiple snapshots at a fixed interval (12 snapshots at five-minute
intervals is approximately one hour):

```bash
python src/collect_history.py --count 12 --interval-minutes 5
```

The computer, network connection, and process must remain active while this
command runs. These local scripts remain useful for testing and debugging, but
they are not the formal long-running Track B collection solution.

## Preparing Data

Validate and combine every raw snapshot into a clean analysis table:

```bash
python src/prepare_data.py
```

The command generates `data/processed/youbike_snapshots.csv` plus compact
quality reports under `results/`. Run the automated checks with:

```bash
python -m unittest discover -s tests -v
```

For cleaning decisions, current quality results, limitations, and presentation
notes, read the [Stage 2 data pipeline guide](docs/STAGE_2_DATA_PIPELINE.md).

## Building Time-Series Features

Build calendar, 15/30/60-minute lag, past-only rolling, and separate 30/60-minute
future target columns:

```bash
python src/build_features.py
```

The pipeline prevents predictor features from looking forward in time and
writes a coverage audit to `results/feature_coverage.csv`. Current fixed samples
do not yet contain 30/60-minute targets, so short-term station-availability model
training has intentionally not started. See the
[Stage 3 history and feature guide](docs/STAGE_3_HISTORY_AND_FEATURES.md).

## Full-year Historical Demand and Weather

Download and prepare every registered 2023 official month, then join hourly
weather:

```bash
python src/download_historical.py --month all
python src/prepare_historical_collection.py
python src/download_weather.py
python src/prepare_weather.py
```

The large raw and processed files are intentionally ignored by Git. The pipeline
processes one month at a time, builds full-year hourly station demand, joins
8,760 weather hours, and saves compact reproducible reports. See the executed
[weather integration notebook](notebooks/05_weather_integration.ipynb) and the
[Stage 5 full-year weather guide](docs/STAGE_5_FULL_YEAR_WEATHER.md).

## Baseline Model and Evaluation

Train chronological hourly baselines for the 100 highest-demand training-period
stations:

```bash
python src/train_baseline.py
```

The experiment uses January–September for training, October–November for
validation, and December for a final holdout test. The best current baseline is
Ridge regression with station, calendar, lag, rolling, and weather features:

| Model | Test MAE | Test RMSE | Test R² |
|---|---:|---:|---:|
| Previous hour | 2.441 | 4.129 | 0.460 |
| Previous week, same hour | 2.176 | 3.701 | 0.566 |
| Ridge without weather | 1.810 | 2.911 | 0.731 |
| Ridge with weather | **1.793** | **2.889** | **0.736** |

These metrics apply only to hourly transfer-related borrowing demand in the
defined 100-station experiment. See the executed
[baseline notebook](notebooks/06_baseline_model.ipynb) and the
[Stage 6 baseline guide](docs/STAGE_6_BASELINE_MODEL.md) for leakage controls,
limitations, and error analysis.

## Tree Model Comparison

Train and evaluate the histogram gradient-boosting models:

```bash
python src/train_tree_models.py
```

The weather-enabled HGB model improves the December holdout MAE from 1.793 for
weather Ridge to 1.575, with RMSE 2.549 and R² 0.794. Three expanding-window
validation folds produce MAE values from 1.592 to 1.636. Permutation analysis
shows that time-of-day, previous-hour demand, station identity, and previous-week
demand are the strongest signals; weather provides a smaller incremental gain.
See the executed [tree comparison notebook](notebooks/07_tree_model_comparison.ipynb)
and [Stage 7 guide](docs/STAGE_7_TREE_MODEL_COMPARISON.md).

## XGBoost Comparison

Run the bounded XGBoost comparison on the same Track A target, top-100 stations,
features, and chronological splits:

```bash
python src/train_xgboost.py
```

The validation-selected XGBoost model reaches December holdout MAE 1.597, RMSE
2.580, and R² 0.789. It improves MAE by about 10.9% over weather Ridge but does
not beat weather HGB at MAE 1.575. Three rolling-origin folds confirm the same
ordering, so HGB remains the primary Track A model. On macOS, XGBoost also
requires the OpenMP runtime (`brew install libomp`). See the executed
[XGBoost notebook](notebooks/09_xgboost_comparison.ipynb) and
[Stage 10 guide](docs/STAGE_10_XGBOOST_COMPARISON.md).

## Prediction Interface

Generate a ranked prediction for one target hour:

```bash
python src/predict_hourly.py \
  --target-time 2023-12-31T18:00:00+08:00 \
  --include-actual \
  --output results/example_hourly_predictions.csv
```

The command verifies the model SHA-256, feature schema, 168-hour demand-history
coverage, station scope, and target-hour weather before predicting. Remove
`--include-actual` for a non-backtest prediction. Future use requires updated
transfer-demand history and weather forecasts with the same schemas; the bundled
2023 files alone cannot produce a current prediction. See the
[Model Card](docs/MODEL_CARD.md),
[Stage 8 guide](docs/STAGE_8_PREDICTION_INTERFACE.md), and executed
[prediction demo notebook](notebooks/08_prediction_demo.ipynb).

## Interactive Historical Dashboard

Stage 9 adds a responsive Vinext/React dashboard for exploring 10 representative
December holdout hours. It shows all 100 station predictions, post-prediction
actuals, absolute errors, model comparisons, rolling-origin results, and feature
importance. Rebuild its compact data bundle with:

```bash
python src/build_dashboard_data.py
```

Then run the local interface from `dashboard/`. The display remains explicitly
historical: it does not claim current bike availability, shortage risk, or a
redistribution recommendation. See the
[Stage 9 historical dashboard guide](docs/STAGE_9_HISTORICAL_DASHBOARD.md).

## Project Status

🚧 **In development**

Milestones 1 and 2 plus Stage 3 through 11 source implementation are complete. The repository now
includes reproducible API samples, validated collection and cleaning pipelines,
leakage-aware time-series feature engineering, automated tests, quality reports,
official full-year 2023 transfer-demand and weather analysis, a chronological
hourly Ridge baseline, rolling-origin validated HGB and XGBoost comparisons, and
an integrity-checked prediction interface with nine executed notebooks and an
interactive historical dashboard, and a tested Cloudflare Worker + Cron + D1
collector design with protected CSV export. The cloud collector still requires
owner deployment, and multi-day live snapshot coverage, Track B modeling, deep
learning, and optimization remain incomplete.
