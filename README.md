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

The initial sample comes from the official
[Taipei City YouBike 2.0 real-time dataset](https://data.taipei/dataset/detail?id=c6bc8aed-557d-41d5-bfb1-8da24f78f2fb).
The source is public, free to use, provided as JSON, and updated every minute.

The sample currently contains one snapshot of station availability. Its fields
include station ID and name, district, capacity, available bikes, return spaces,
location, operating status, and update times.

> A single snapshot cannot measure demand. Multiple snapshots must be collected
> over time before short-term demand can be calculated or predicted.

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

## Project Status

🚧 **In development**

Milestone 1 is complete. The repository includes an official real-time data
sample and an executed initial exploration notebook. Historical collection,
data cleaning, models, optimization, and evaluation results have not been
completed yet.
