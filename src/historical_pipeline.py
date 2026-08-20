"""Clean and summarize official transfer-related YouBike historical trips."""

from __future__ import annotations

import json
import unicodedata
from pathlib import Path

import pandas as pd


SOURCE_TO_CLEAN_COLUMNS = {
    "借車時間": "borrow_time",
    "借車站": "borrow_station",
    "還車時間": "return_time",
    "還車站": "return_station",
    "租借時數": "duration",
    "借車日期": "borrow_date",
}
REQUIRED_SOURCE_COLUMNS = set(SOURCE_TO_CLEAN_COLUMNS)


def normalize_station_name(value: object) -> str:
    """Normalize station names without using fuzzy or manual matching."""
    normalized = unicodedata.normalize("NFKC", str(value)).strip()
    normalized = normalized.removeprefix("YouBike2.0_")
    return normalized.replace("台", "臺")


def load_historical_trips(source_path: Path) -> pd.DataFrame:
    """Load one official historical CSV and validate its confirmed schema."""
    header = pd.read_csv(source_path, nrows=0)
    missing = REQUIRED_SOURCE_COLUMNS - set(header.columns)
    if missing:
        raise ValueError(
            f"{source_path} is missing required columns: {', '.join(sorted(missing))}"
        )
    return pd.read_csv(source_path, dtype="string")


def load_current_station_names(source_path: Path) -> set[str]:
    """Load normalized current station names from an official snapshot."""
    records = json.loads(source_path.read_text(encoding="utf-8"))
    if not isinstance(records, list) or not records:
        raise ValueError("Current station reference must be a non-empty JSON list.")
    if any(not isinstance(record, dict) or "sna" not in record for record in records):
        raise ValueError("Every current station record must contain sna.")
    return {normalize_station_name(record["sna"]) for record in records}


def _parse_local_timestamp(values: pd.Series) -> pd.Series:
    """Parse source timestamps and standardize them to Asia/Taipei."""
    return pd.to_datetime(values, errors="coerce", utc=True).dt.tz_convert(
        "Asia/Taipei"
    )


def clean_historical_trips(
    raw_data: pd.DataFrame,
    current_station_names: set[str],
) -> pd.DataFrame:
    """Normalize historical transactions while preserving legitimate duplicates."""
    missing = REQUIRED_SOURCE_COLUMNS - set(raw_data.columns)
    if missing:
        raise ValueError(f"Historical data is missing: {', '.join(sorted(missing))}")

    source_columns = list(SOURCE_TO_CLEAN_COLUMNS)
    clean = raw_data[source_columns].rename(columns=SOURCE_TO_CLEAN_COLUMNS).copy()
    clean["borrow_time"] = _parse_local_timestamp(clean["borrow_time"])
    clean["return_time"] = _parse_local_timestamp(clean["return_time"])
    clean["borrow_date"] = pd.to_datetime(clean["borrow_date"], errors="coerce")
    duration = pd.to_timedelta(clean.pop("duration"), errors="coerce")
    clean["duration_minutes"] = duration.dt.total_seconds() / 60

    invalid_counts = clean[
        [
            "borrow_time",
            "return_time",
            "borrow_date",
            "borrow_station",
            "return_station",
            "duration_minutes",
        ]
    ].isna().sum()
    invalid_counts = invalid_counts[invalid_counts > 0]
    if not invalid_counts.empty:
        details = ", ".join(
            f"{column}={count}" for column, count in invalid_counts.items()
        )
        raise ValueError(f"Historical values are missing or invalid: {details}")

    if clean["duration_minutes"].le(0).any():
        count = int(clean["duration_minutes"].le(0).sum())
        raise ValueError(f"Historical data contains {count} non-positive durations.")

    clean["borrow_station"] = clean["borrow_station"].map(normalize_station_name)
    clean["return_station"] = clean["return_station"].map(normalize_station_name)
    clean["borrow_station_current_match"] = clean["borrow_station"].isin(
        current_station_names
    )
    clean["return_station_current_match"] = clean["return_station"].isin(
        current_station_names
    )

    clean["borrow_hour"] = clean["borrow_time"].dt.hour.astype("int8")
    clean["day_of_week"] = clean["borrow_time"].dt.dayofweek.astype("int8")
    clean["is_weekend"] = clean["day_of_week"].ge(5)
    clean["is_rush_hour"] = clean["borrow_hour"].between(7, 9) | clean[
        "borrow_hour"
    ].between(17, 19)
    clean["is_duration_over_2h"] = clean["duration_minutes"].gt(120)
    clean["borrow_date_matches_timestamp"] = (
        clean["borrow_time"].dt.tz_localize(None).dt.normalize()
        == clean["borrow_date"]
    )

    # There is no ride ID. Identical rows may represent separate real trips,
    # so duplicates are flagged for auditing but deliberately retained.
    clean["is_exact_duplicate"] = raw_data[source_columns].duplicated(keep=False)
    return clean.sort_values(["borrow_time", "borrow_station"]).reset_index(drop=True)


def build_station_hour_demand(clean_data: pd.DataFrame) -> pd.DataFrame:
    """Aggregate hourly borrowing and returning activity by station."""
    borrows = (
        clean_data.groupby(["borrow_time", "borrow_station"], as_index=False)
        .size()
        .rename(
            columns={
                "borrow_time": "event_time",
                "borrow_station": "station_name",
                "size": "borrow_count",
            }
        )
    )
    returns = (
        clean_data.groupby(["return_time", "return_station"], as_index=False)
        .size()
        .rename(
            columns={
                "return_time": "event_time",
                "return_station": "station_name",
                "size": "return_count",
            }
        )
    )
    demand = borrows.merge(returns, how="outer", on=["event_time", "station_name"])
    demand[["borrow_count", "return_count"]] = demand[
        ["borrow_count", "return_count"]
    ].fillna(0).astype(int)
    demand["net_flow"] = demand["return_count"] - demand["borrow_count"]
    demand["hour"] = demand["event_time"].dt.hour.astype("int8")
    demand["day_of_week"] = demand["event_time"].dt.dayofweek.astype("int8")
    demand["is_weekend"] = demand["day_of_week"].ge(5)
    return demand.sort_values(["event_time", "station_name"]).reset_index(drop=True)


def build_daily_summary(clean_data: pd.DataFrame) -> pd.DataFrame:
    """Summarize trip activity and duration for every calendar date."""
    return (
        clean_data.groupby("borrow_date", as_index=False)
        .agg(
            trip_count=("borrow_station", "size"),
            unique_borrow_stations=("borrow_station", "nunique"),
            median_duration_minutes=("duration_minutes", "median"),
            trips_over_2h=("is_duration_over_2h", "sum"),
            is_weekend=("is_weekend", "first"),
        )
        .sort_values("borrow_date")
    )


def build_hourly_profile(clean_data: pd.DataFrame) -> pd.DataFrame:
    """Build weekday/weekend hourly totals and per-day averages, including zeros."""
    dates = pd.Index(sorted(clean_data["borrow_date"].unique()), name="borrow_date")
    full_grid = pd.MultiIndex.from_product(
        [dates, range(24)], names=["borrow_date", "borrow_hour"]
    )
    daily_hour = (
        clean_data.groupby(["borrow_date", "borrow_hour"])
        .size()
        .reindex(full_grid, fill_value=0)
        .rename("trip_count")
        .reset_index()
    )
    daily_hour["is_weekend"] = daily_hour["borrow_date"].dt.dayofweek.ge(5)
    return (
        daily_hour.groupby(["is_weekend", "borrow_hour"], as_index=False)
        .agg(
            total_trips=("trip_count", "sum"),
            average_trips_per_day=("trip_count", "mean"),
            observed_days=("borrow_date", "nunique"),
        )
        .sort_values(["is_weekend", "borrow_hour"])
    )


def build_top_station_summary(clean_data: pd.DataFrame) -> pd.DataFrame:
    """Rank normalized station names by transfer-related activity."""
    borrows = clean_data["borrow_station"].value_counts().rename("borrow_count")
    returns = clean_data["return_station"].value_counts().rename("return_count")
    summary = pd.concat([borrows, returns], axis=1).fillna(0).astype(int)
    summary["total_activity"] = summary["borrow_count"] + summary["return_count"]
    matched_names = set(
        clean_data.loc[
            clean_data["borrow_station_current_match"], "borrow_station"
        ]
    ) | set(
        clean_data.loc[
            clean_data["return_station_current_match"], "return_station"
        ]
    )
    summary["current_station_match"] = summary.index.isin(matched_names)
    return (
        summary.rename_axis("station_name")
        .reset_index()
        .sort_values("total_activity", ascending=False)
        .reset_index(drop=True)
    )


def build_historical_quality_summary(
    raw_data: pd.DataFrame,
    clean_data: pd.DataFrame,
) -> pd.DataFrame:
    """Report scope, time resolution, matching, and retained duplicates."""
    historical_names = set(clean_data["borrow_station"]) | set(
        clean_data["return_station"]
    )
    matched_names = set(
        clean_data.loc[
            clean_data["borrow_station_current_match"], "borrow_station"
        ]
    ) | set(
        clean_data.loc[
            clean_data["return_station_current_match"], "return_station"
        ]
    )
    metrics = [
        ("dataset_scope", "transfer_related_trips_only"),
        ("rows", len(clean_data)),
        ("date_start", clean_data["borrow_date"].min().date().isoformat()),
        ("date_end", clean_data["borrow_date"].max().date().isoformat()),
        ("timestamp_granularity", "hour"),
        ("raw_missing_cells", int(raw_data.isna().sum().sum())),
        ("exact_duplicate_extra_rows_retained", int(raw_data.duplicated().sum())),
        ("unique_historical_station_names", len(historical_names)),
        ("unique_names_matching_current", len(matched_names)),
        (
            "borrow_rows_matching_current_percent",
            round(clean_data["borrow_station_current_match"].mean() * 100, 2),
        ),
        (
            "return_rows_matching_current_percent",
            round(clean_data["return_station_current_match"].mean() * 100, 2),
        ),
        (
            "borrow_date_mismatch_rows",
            int((~clean_data["borrow_date_matches_timestamp"]).sum()),
        ),
        ("duration_over_2h_rows", int(clean_data["is_duration_over_2h"].sum())),
    ]
    return pd.DataFrame(metrics, columns=["metric", "value"])
