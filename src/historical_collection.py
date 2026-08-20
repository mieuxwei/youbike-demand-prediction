"""Combine multiple monthly historical files without retaining all trips in memory."""

from __future__ import annotations

from pathlib import Path

import pandas as pd

try:
    from .historical_pipeline import (
        build_daily_summary,
        build_hourly_profile,
        build_station_hour_demand,
        build_top_station_summary,
        clean_historical_trips,
        load_historical_trips,
    )
except ImportError:
    from historical_pipeline import (
        build_daily_summary,
        build_hourly_profile,
        build_station_hour_demand,
        build_top_station_summary,
        clean_historical_trips,
        load_historical_trips,
    )


def prepare_historical_collection(
    source_paths: list[Path], current_station_names: set[str]
) -> dict[str, pd.DataFrame]:
    """Process monthly files one at a time and combine compact outputs."""
    if not source_paths:
        raise ValueError("At least one historical source file is required.")

    station_hours: list[pd.DataFrame] = []
    daily_summaries: list[pd.DataFrame] = []
    hourly_profiles: list[pd.DataFrame] = []
    top_stations: list[pd.DataFrame] = []
    historical_names: set[str] = set()
    matched_names: set[str] = set()
    totals = {
        "rows": 0,
        "raw_missing_cells": 0,
        "borrow_station_missing_rows": 0,
        "return_station_missing_rows": 0,
        "exact_duplicate_extra_rows_retained": 0,
        "borrow_matches": 0,
        "return_matches": 0,
        "borrow_date_mismatch_rows": 0,
        "duration_over_2h_rows": 0,
    }
    date_start: pd.Timestamp | None = None
    date_end: pd.Timestamp | None = None

    for source_path in sorted(source_paths):
        raw = load_historical_trips(source_path)
        clean = clean_historical_trips(raw, current_station_names)
        station_hours.append(build_station_hour_demand(clean))
        daily_summaries.append(build_daily_summary(clean))
        hourly_profiles.append(build_hourly_profile(clean))
        top_stations.append(build_top_station_summary(clean))

        rows = len(clean)
        totals["rows"] += rows
        totals["raw_missing_cells"] += int(raw.isna().sum().sum())
        totals["borrow_station_missing_rows"] += int(clean["borrow_station"].isna().sum())
        totals["return_station_missing_rows"] += int(clean["return_station"].isna().sum())
        totals["exact_duplicate_extra_rows_retained"] += int(raw.duplicated().sum())
        totals["borrow_matches"] += int(clean["borrow_station_current_match"].sum())
        totals["return_matches"] += int(clean["return_station_current_match"].sum())
        totals["borrow_date_mismatch_rows"] += int(
            (~clean["borrow_date_matches_timestamp"]).sum()
        )
        totals["duration_over_2h_rows"] += int(clean["is_duration_over_2h"].sum())

        historical_names.update(clean["borrow_station"].dropna())
        historical_names.update(clean["return_station"].dropna())
        matched_names.update(
            clean.loc[clean["borrow_station_current_match"], "borrow_station"]
        )
        matched_names.update(
            clean.loc[clean["return_station_current_match"], "return_station"]
        )
        month_start = clean["borrow_date"].min()
        month_end = clean["borrow_date"].max()
        date_start = month_start if date_start is None else min(date_start, month_start)
        date_end = month_end if date_end is None else max(date_end, month_end)

    station_hour = pd.concat(station_hours, ignore_index=True)
    station_hour = (
        station_hour.groupby(["event_time", "station_name"], as_index=False)[
            ["borrow_count", "return_count"]
        ]
        .sum()
        .sort_values(["event_time", "station_name"])
        .reset_index(drop=True)
    )
    station_hour["net_flow"] = (
        station_hour["return_count"] - station_hour["borrow_count"]
    )
    station_hour["hour"] = station_hour["event_time"].dt.hour.astype("int8")
    station_hour["day_of_week"] = station_hour["event_time"].dt.dayofweek.astype(
        "int8"
    )
    station_hour["is_weekend"] = station_hour["day_of_week"].ge(5)

    daily = pd.concat(daily_summaries, ignore_index=True).sort_values("borrow_date")
    monthly = daily.assign(month=daily["borrow_date"].dt.to_period("M").astype(str))
    monthly = (
        monthly.groupby("month", as_index=False)
        .agg(
            trip_count=("trip_count", "sum"),
            average_trips_per_day=("trip_count", "mean"),
            observed_days=("borrow_date", "nunique"),
            average_unique_borrow_stations=("unique_borrow_stations", "mean"),
            trips_over_2h=("trips_over_2h", "sum"),
        )
        .sort_values("month")
    )
    hourly = pd.concat(hourly_profiles, ignore_index=True)
    hourly = (
        hourly.groupby(["is_weekend", "borrow_hour"], as_index=False)
        .agg(total_trips=("total_trips", "sum"), observed_days=("observed_days", "sum"))
        .sort_values(["is_weekend", "borrow_hour"])
    )
    hourly["average_trips_per_day"] = hourly["total_trips"] / hourly["observed_days"]
    hourly = hourly[
        ["is_weekend", "borrow_hour", "total_trips", "average_trips_per_day", "observed_days"]
    ]

    top = pd.concat(top_stations, ignore_index=True)
    top = (
        top.groupby("station_name", as_index=False)
        .agg(
            borrow_count=("borrow_count", "sum"),
            return_count=("return_count", "sum"),
            current_station_match=("current_station_match", "max"),
        )
    )
    top["total_activity"] = top["borrow_count"] + top["return_count"]
    top = top.sort_values("total_activity", ascending=False).reset_index(drop=True)

    rows = totals["rows"]
    quality = pd.DataFrame(
        [
            ("dataset_scope", "transfer_related_trips_only"),
            ("source_files", len(source_paths)),
            ("rows", rows),
            ("date_start", date_start.date().isoformat()),
            ("date_end", date_end.date().isoformat()),
            ("timestamp_granularity", "hour"),
            ("raw_missing_cells", totals["raw_missing_cells"]),
            ("borrow_station_missing_rows", totals["borrow_station_missing_rows"]),
            ("return_station_missing_rows", totals["return_station_missing_rows"]),
            (
                "exact_duplicate_extra_rows_retained",
                totals["exact_duplicate_extra_rows_retained"],
            ),
            ("unique_historical_station_names", len(historical_names)),
            ("unique_names_matching_current", len(matched_names)),
            (
                "borrow_rows_matching_current_percent",
                round(totals["borrow_matches"] / rows * 100, 2),
            ),
            (
                "return_rows_matching_current_percent",
                round(totals["return_matches"] / rows * 100, 2),
            ),
            ("borrow_date_mismatch_rows", totals["borrow_date_mismatch_rows"]),
            ("duration_over_2h_rows", totals["duration_over_2h_rows"]),
        ],
        columns=["metric", "value"],
    )
    return {
        "station_hour": station_hour,
        "daily": daily,
        "monthly": monthly,
        "hourly": hourly,
        "top_stations": top,
        "quality": quality,
    }
