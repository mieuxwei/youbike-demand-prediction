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

The project also uses the official
[2023 transfer-related YouBike trip dataset](https://data.gov.tw/dataset/169174)
for historical hourly demand analysis. This source covers trips associated with
bus or MRT transfers, not all YouBike trips, and its timestamps are aggregated
to the hour. It complements rather than replaces the real-time snapshots.

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
do not yet contain 30/60-minute targets, so model training has intentionally not
started. See the
[Stage 3 history and feature guide](docs/STAGE_3_HISTORY_AND_FEATURES.md).

## Historical Transfer-Demand Analysis

Download and prepare the registered January 2023 official file:

```bash
python src/download_historical.py --month 2023-01
python src/prepare_historical.py
```

The raw file is approximately 71 MB and is intentionally ignored by Git. The
pipeline builds hourly station demand plus compact daily, hourly, station, and
quality reports. See the executed
[historical demand notebook](notebooks/04_historical_demand_analysis.ipynb) and
the [Stage 4 historical demand guide](docs/STAGE_4_HISTORICAL_DEMAND.md).

## Project Status

🚧 **In development**

Milestones 1 and 2 plus the Stage 3 and 4 tooling are complete. The repository now
includes reproducible API samples, validated collection and cleaning pipelines,
leakage-aware time-series feature engineering, automated tests, quality reports,
official January 2023 transfer-demand analysis, and four executed notebooks.
Multi-day live coverage and additional historical months are still being
accumulated; models, optimization, and evaluation results have not been completed.
