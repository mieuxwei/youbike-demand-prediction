"""Leakage-aware time-series features for YouBike station snapshots."""

from __future__ import annotations

from collections.abc import Iterable

import numpy as np
import pandas as pd


REQUIRED_COLUMNS = {
    "snapshot_time",
    "station_id",
    "available_bikes",
    "capacity",
    "is_active",
}


def _validate_input(data: pd.DataFrame) -> None:
    """Check that cleaned station data contains the required fields."""
    missing = REQUIRED_COLUMNS - set(data.columns)
    if missing:
        raise ValueError(f"Feature input is missing columns: {', '.join(sorted(missing))}")
    if data["snapshot_time"].isna().any():
        raise ValueError("snapshot_time contains missing values")


def add_calendar_features(data: pd.DataFrame) -> pd.DataFrame:
    """Add interpretable and cyclical calendar features in local time."""
    _validate_input(data)
    featured = data.copy()
    timestamp = featured["snapshot_time"]

    featured["hour"] = timestamp.dt.hour.astype("int16")
    featured["day_of_week"] = timestamp.dt.dayofweek.astype("int8")
    featured["month"] = timestamp.dt.month.astype("int8")
    featured["is_weekend"] = featured["day_of_week"].ge(5)
    featured["is_rush_hour"] = featured["hour"].between(7, 9) | featured[
        "hour"
    ].between(17, 19)

    hour_angle = 2 * np.pi * featured["hour"] / 24
    weekday_angle = 2 * np.pi * featured["day_of_week"] / 7
    featured["hour_sin"] = np.sin(hour_angle)
    featured["hour_cos"] = np.cos(hour_angle)
    featured["day_of_week_sin"] = np.sin(weekday_angle)
    featured["day_of_week_cos"] = np.cos(weekday_angle)
    return featured


def _align_station_values(
    data: pd.DataFrame,
    horizon_minutes: int,
    tolerance_minutes: float,
    direction: str,
) -> tuple[pd.Series, pd.Series]:
    """Match active station values near a desired past or future timestamp."""
    values = pd.Series(np.nan, index=data.index, dtype="float64")
    actual_minutes = pd.Series(np.nan, index=data.index, dtype="float64")
    horizon = pd.Timedelta(minutes=horizon_minutes)
    tolerance = pd.Timedelta(minutes=tolerance_minutes)

    for _, station in data.groupby("station_id", sort=False):
        station = station.sort_values("snapshot_time")
        left = station[["snapshot_time"]].copy()
        left["row_index"] = station.index
        if direction == "backward":
            left["desired_time"] = left["snapshot_time"] - horizon
        else:
            left["desired_time"] = left["snapshot_time"] + horizon

        right = station[
            ["snapshot_time", "available_bikes", "is_active"]
        ].rename(
            columns={
                "snapshot_time": "matched_time",
                "available_bikes": "matched_available_bikes",
                "is_active": "matched_is_active",
            }
        )
        aligned = pd.merge_asof(
            left.sort_values("desired_time"),
            right.sort_values("matched_time"),
            left_on="desired_time",
            right_on="matched_time",
            direction=direction,
            tolerance=tolerance,
        )

        row_indexes = aligned["row_index"].astype(int)
        current_active = data.loc[row_indexes, "is_active"].fillna(False).to_numpy()
        matched_active = aligned["matched_is_active"].fillna(False).to_numpy()
        valid = current_active & matched_active & aligned["matched_time"].notna().to_numpy()

        matched_values = aligned["matched_available_bikes"].where(valid)
        values.loc[row_indexes] = matched_values.to_numpy()

        if direction == "backward":
            elapsed = aligned["snapshot_time"] - aligned["matched_time"]
        else:
            elapsed = aligned["matched_time"] - aligned["snapshot_time"]
        actual_minutes.loc[row_indexes] = (
            elapsed.dt.total_seconds().div(60).where(valid).to_numpy()
        )

    return values, actual_minutes


def add_lag_features(
    data: pd.DataFrame,
    horizons_minutes: Iterable[int] = (15, 30, 60),
    tolerance_minutes: float = 2,
) -> pd.DataFrame:
    """Add time-aligned station availability from the past only."""
    _validate_input(data)
    featured = data.sort_values(["station_id", "snapshot_time"]).copy()

    for horizon in horizons_minutes:
        if horizon <= tolerance_minutes:
            raise ValueError("Each lag horizon must be greater than the tolerance.")
        values, actual_minutes = _align_station_values(
            featured,
            horizon_minutes=horizon,
            tolerance_minutes=tolerance_minutes,
            direction="backward",
        )
        featured[f"available_bikes_lag_{horizon}m"] = values
        featured[f"lag_{horizon}m_actual_minutes"] = actual_minutes

    return featured


def add_rolling_features(
    data: pd.DataFrame,
    windows_minutes: Iterable[int] = (30, 60),
) -> pd.DataFrame:
    """Add past-only rolling averages and counts for each station."""
    _validate_input(data)
    featured = data.sort_values(["station_id", "snapshot_time"]).copy()

    for window in windows_minutes:
        if window < 1:
            raise ValueError("Rolling windows must be positive.")
        mean_column = f"available_bikes_mean_past_{window}m"
        count_column = f"observations_past_{window}m"
        featured[mean_column] = np.nan
        featured[count_column] = 0

        for _, station in featured.groupby("station_id", sort=False):
            active_values = station["available_bikes"].where(station["is_active"])
            time_series = pd.Series(
                active_values.to_numpy(), index=station["snapshot_time"]
            )
            rolling = time_series.rolling(
                f"{window}min", closed="left", min_periods=1
            )
            featured.loc[station.index, mean_column] = rolling.mean().to_numpy()
            featured.loc[station.index, count_column] = (
                rolling.count().fillna(0).astype(int).to_numpy()
            )

    return featured


def add_future_targets(
    data: pd.DataFrame,
    horizons_minutes: Iterable[int] = (30, 60),
    tolerance_minutes: float = 2,
) -> pd.DataFrame:
    """Add future availability labels, kept separate from model predictors."""
    _validate_input(data)
    featured = data.sort_values(["station_id", "snapshot_time"]).copy()

    for horizon in horizons_minutes:
        if horizon <= tolerance_minutes:
            raise ValueError("Each target horizon must be greater than the tolerance.")
        values, actual_minutes = _align_station_values(
            featured,
            horizon_minutes=horizon,
            tolerance_minutes=tolerance_minutes,
            direction="forward",
        )
        featured[f"target_available_bikes_{horizon}m"] = values
        featured[f"target_{horizon}m_actual_minutes"] = actual_minutes

    return featured


def build_features(data: pd.DataFrame) -> pd.DataFrame:
    """Build all currently approved time-series predictors and targets."""
    featured = add_calendar_features(data)
    featured = add_lag_features(featured)
    featured = add_rolling_features(featured)
    featured = add_future_targets(featured)
    return featured.sort_values(["station_id", "snapshot_time"]).reset_index(drop=True)


def build_feature_coverage(featured_data: pd.DataFrame) -> pd.DataFrame:
    """Report how much real history supports each engineered field."""
    engineered_prefixes = (
        "available_bikes_lag_",
        "lag_",
        "available_bikes_mean_past_",
        "observations_past_",
        "target_available_bikes_",
        "target_",
    )
    calendar_columns = {
        "hour",
        "day_of_week",
        "month",
        "is_weekend",
        "is_rush_hour",
        "hour_sin",
        "hour_cos",
        "day_of_week_sin",
        "day_of_week_cos",
    }
    feature_columns = [
        column
        for column in featured_data.columns
        if column in calendar_columns or column.startswith(engineered_prefixes)
    ]

    rows = []
    for column in feature_columns:
        non_null = int(featured_data[column].notna().sum())
        if column.startswith("observations_past_"):
            usable = int(featured_data[column].gt(0).sum())
        else:
            usable = non_null
        role = "target" if column.startswith("target_") else "predictor"
        rows.append(
            {
                "column": column,
                "role": role,
                "non_null_rows": non_null,
                "usable_rows": usable,
                "coverage_percent": round(usable / len(featured_data) * 100, 2),
            }
        )
    return pd.DataFrame(rows)
