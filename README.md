# YouBike Demand Prediction & Optimization

## Project Overview

This project studies short-term YouBike station demand using historical usage
data, weather information, and time-based features. The long-term goal is to
combine demand forecasting with a bike redistribution strategy.

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
- Requests

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
command runs.

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

## Project Status

🚧 **In development**

Milestones 1 and 2 plus Stage 3 through 7 are complete. The repository now
includes reproducible API samples, validated collection and cleaning pipelines,
leakage-aware time-series feature engineering, automated tests, quality reports,
official full-year 2023 transfer-demand and weather analysis, a chronological
hourly Ridge baseline, a rolling-origin validated gradient-boosting model, and
seven executed notebooks. Multi-day live snapshot coverage, a production-style
prediction interface, deep learning, and optimization are still in development.
