"""Validate weather data and join it to hourly transfer demand."""

from __future__ import annotations

import json
from pathlib import Path

import pandas as pd


WEATHER_COLUMNS = {
    "temperature_2m": "temperature_c",
    "relative_humidity_2m": "relative_humidity_percent",
    "precipitation": "precipitation_mm",
    "wind_speed_10m": "wind_speed_kmh",
    "weather_code": "weather_code",
}


def load_weather_json(source_path: Path) -> tuple[pd.DataFrame, dict[str, object]]:
    """Load the raw Open-Meteo response and validate equal-length hourly arrays."""
    payload = json.loads(source_path.read_text(encoding="utf-8"))
    hourly = payload.get("hourly")
    if not isinstance(hourly, dict) or "time" not in hourly:
        raise ValueError("Weather payload must contain hourly.time.")
    missing = set(WEATHER_COLUMNS) - set(hourly)
    if missing:
        raise ValueError(f"Weather payload is missing: {', '.join(sorted(missing))}")
    lengths = {len(hourly[column]) for column in ["time", *WEATHER_COLUMNS]}
    if len(lengths) != 1:
        raise ValueError("Weather hourly arrays must have equal lengths.")
    frame = pd.DataFrame(
        {"event_time": hourly["time"], **{name: hourly[name] for name in WEATHER_COLUMNS}}
    )
    return frame, payload


def clean_weather(raw_weather: pd.DataFrame) -> pd.DataFrame:
    """Standardize timestamps, numeric fields, and interpretable weather flags."""
    required = {"event_time", *WEATHER_COLUMNS}
    missing = required - set(raw_weather)
    if missing:
        raise ValueError(f"Weather data is missing: {', '.join(sorted(missing))}")

    weather = raw_weather.rename(columns=WEATHER_COLUMNS).copy()
    event_time = pd.to_datetime(weather["event_time"], errors="coerce")
    if event_time.dt.tz is None:
        event_time = event_time.dt.tz_localize(
            "Asia/Taipei", ambiguous="raise", nonexistent="raise"
        )
    else:
        event_time = event_time.dt.tz_convert("Asia/Taipei")
    weather["event_time"] = event_time
    numeric_columns = list(WEATHER_COLUMNS.values())
    weather[numeric_columns] = weather[numeric_columns].apply(
        pd.to_numeric, errors="coerce"
    )
    if weather[["event_time", *numeric_columns]].isna().any().any():
        raise ValueError("Weather data contains missing or invalid required values.")
    if weather["event_time"].duplicated().any():
        raise ValueError("Weather data contains duplicate hourly timestamps.")
    weather["is_raining"] = weather["precipitation_mm"].gt(0)
    weather["temperature_band"] = pd.cut(
        weather["temperature_c"],
        bins=[-float("inf"), 15, 20, 25, 30, float("inf")],
        labels=["<=15", "15-20", "20-25", "25-30", ">30"],
    )
    return weather.sort_values("event_time").reset_index(drop=True)


def merge_weather_with_demand(
    station_hour_demand: pd.DataFrame, weather: pd.DataFrame
) -> pd.DataFrame:
    """Attach one city-level weather row to each station-hour demand row."""
    demand = station_hour_demand.copy()
    demand["event_time"] = pd.to_datetime(demand["event_time"], utc=True).dt.tz_convert(
        "Asia/Taipei"
    )
    merged = demand.merge(weather, on="event_time", how="left", validate="many_to_one")
    merged["weather_matched"] = merged["temperature_c"].notna()
    return merged


def build_weather_quality_summary(
    weather: pd.DataFrame, merged: pd.DataFrame, metadata: dict[str, object]
) -> pd.DataFrame:
    """Report weather coverage and the spatial-scope limitation."""
    return pd.DataFrame(
        [
            ("weather_source", "Open-Meteo historical weather API"),
            ("weather_scope", "single_city_reference_point_reanalysis"),
            ("weather_rows", len(weather)),
            ("weather_date_start", weather["event_time"].min().isoformat()),
            ("weather_date_end", weather["event_time"].max().isoformat()),
            ("weather_missing_cells", int(weather.isna().sum().sum())),
            ("weather_latitude", metadata.get("latitude")),
            ("weather_longitude", metadata.get("longitude")),
            (
                "demand_rows_weather_matched_percent",
                round(merged["weather_matched"].mean() * 100, 2),
            ),
        ],
        columns=["metric", "value"],
    )


def build_weather_demand_summary(merged: pd.DataFrame) -> pd.DataFrame:
    """Compare citywide hourly borrowing totals across weather conditions."""
    matched = merged.loc[merged["weather_matched"]].copy()
    city_hour = (
        matched.groupby("event_time", as_index=False)
        .agg(
            borrow_count=("borrow_count", "sum"),
            return_count=("return_count", "sum"),
            temperature_c=("temperature_c", "first"),
            precipitation_mm=("precipitation_mm", "first"),
            relative_humidity_percent=("relative_humidity_percent", "first"),
            is_raining=("is_raining", "first"),
            temperature_band=("temperature_band", "first"),
        )
    )
    summary = (
        city_hour.groupby(["is_raining", "temperature_band"], observed=True)
        .agg(
            observed_hours=("event_time", "size"),
            average_borrows=("borrow_count", "mean"),
            median_borrows=("borrow_count", "median"),
            average_returns=("return_count", "mean"),
            average_precipitation_mm=("precipitation_mm", "mean"),
            average_humidity_percent=("relative_humidity_percent", "mean"),
        )
        .reset_index()
    )
    return summary


def build_rain_hour_profile(merged: pd.DataFrame) -> pd.DataFrame:
    """Compare rain and dry demand within weekday/weekend and hour strata."""
    matched = merged.loc[merged["weather_matched"]].copy()
    city_hour = (
        matched.groupby("event_time", as_index=False)
        .agg(
            borrow_count=("borrow_count", "sum"),
            return_count=("return_count", "sum"),
            is_raining=("is_raining", "first"),
        )
    )
    city_hour["hour"] = city_hour["event_time"].dt.hour
    city_hour["is_weekend"] = city_hour["event_time"].dt.dayofweek.ge(5)
    return (
        city_hour.groupby(["is_weekend", "hour", "is_raining"], as_index=False)
        .agg(
            observed_hours=("event_time", "size"),
            average_borrows=("borrow_count", "mean"),
            median_borrows=("borrow_count", "median"),
            average_returns=("return_count", "mean"),
        )
        .sort_values(["is_weekend", "hour", "is_raining"])
    )
