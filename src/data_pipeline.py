"""Load, validate, clean, and summarize YouBike station snapshots."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Iterable

import numpy as np
import pandas as pd


SOURCE_TO_CLEAN_COLUMNS = {
    "srcUpdateTime": "snapshot_time",
    "mday": "station_updated_at",
    "sno": "station_id",
    "sna": "station_name",
    "sarea": "district",
    "ar": "address",
    "latitude": "latitude",
    "longitude": "longitude",
    "Quantity": "capacity",
    "available_rent_bikes": "available_bikes",
    "available_return_bikes": "available_return_spaces",
    "act": "is_active",
}

REQUIRED_SOURCE_COLUMNS = set(SOURCE_TO_CLEAN_COLUMNS)
NUMERIC_COLUMNS = [
    "latitude",
    "longitude",
    "capacity",
    "available_bikes",
    "available_return_spaces",
]


def discover_snapshot_files(raw_directory: Path) -> list[Path]:
    """Return every JSON snapshot below the raw-data directory."""
    files = sorted(path for path in raw_directory.rglob("*.json") if path.is_file())
    if not files:
        raise FileNotFoundError(f"No JSON snapshots found under {raw_directory}")
    return files


def _validate_records(records: Any, source_path: Path) -> list[dict[str, Any]]:
    """Validate the top-level JSON structure and required API fields."""
    if not isinstance(records, list) or not records:
        raise ValueError(f"{source_path}: expected a non-empty JSON list")

    invalid_records = [index for index, record in enumerate(records) if not isinstance(record, dict)]
    if invalid_records:
        raise ValueError(
            f"{source_path}: station records must be JSON objects; "
            f"invalid indexes: {invalid_records[:5]}"
        )

    missing_by_record = [
        (index, sorted(REQUIRED_SOURCE_COLUMNS - record.keys()))
        for index, record in enumerate(records)
        if REQUIRED_SOURCE_COLUMNS - record.keys()
    ]
    if missing_by_record:
        index, fields = missing_by_record[0]
        raise ValueError(
            f"{source_path}: record {index} is missing required fields: "
            f"{', '.join(fields)}"
        )

    return records


def load_snapshot(source_path: Path) -> pd.DataFrame:
    """Load one official API JSON file without changing its source fields."""
    try:
        records = json.loads(source_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as error:
        raise ValueError(f"{source_path}: invalid JSON") from error

    validated_records = _validate_records(records, source_path)
    frame = pd.DataFrame(validated_records)
    frame["source_file"] = source_path.as_posix()
    return frame


def load_snapshots(source_paths: Iterable[Path]) -> pd.DataFrame:
    """Load and combine multiple snapshots."""
    paths = list(source_paths)
    if not paths:
        raise ValueError("At least one snapshot path is required.")
    return pd.concat(
        [load_snapshot(path) for path in paths],
        ignore_index=True,
        sort=False,
    )


def _parse_taipei_time(values: pd.Series) -> pd.Series:
    """Parse API timestamps and attach the Asia/Taipei timezone."""
    parsed = pd.to_datetime(values, errors="coerce")
    return parsed.dt.tz_localize("Asia/Taipei", ambiguous="NaT", nonexistent="NaT")


def clean_snapshots(raw_data: pd.DataFrame) -> pd.DataFrame:
    """Normalize fields, validate values, and create basic quality features."""
    missing_columns = REQUIRED_SOURCE_COLUMNS - set(raw_data.columns)
    if missing_columns:
        missing = ", ".join(sorted(missing_columns))
        raise ValueError(f"Combined data is missing required fields: {missing}")

    selected_columns = list(SOURCE_TO_CLEAN_COLUMNS) + ["source_file"]
    clean = raw_data[selected_columns].rename(columns=SOURCE_TO_CLEAN_COLUMNS).copy()

    for column in ["station_id", "station_name", "district", "address"]:
        clean[column] = clean[column].astype("string").str.strip()

    for column in NUMERIC_COLUMNS:
        clean[column] = pd.to_numeric(clean[column], errors="coerce")

    clean["snapshot_time"] = _parse_taipei_time(clean["snapshot_time"])
    clean["station_updated_at"] = _parse_taipei_time(clean["station_updated_at"])
    clean["is_active"] = clean["is_active"].map(
        {"1": True, "0": False, 1: True, 0: False}
    ).astype("boolean")

    required_clean_columns = [
        "snapshot_time",
        "station_updated_at",
        "station_id",
        "station_name",
        "district",
        "capacity",
        "available_bikes",
        "available_return_spaces",
        "is_active",
    ]
    invalid_counts = clean[required_clean_columns].isna().sum()
    invalid_counts = invalid_counts[invalid_counts > 0]
    if not invalid_counts.empty:
        details = ", ".join(
            f"{column}={count}" for column, count in invalid_counts.items()
        )
        raise ValueError(f"Required cleaned values are missing or invalid: {details}")

    negative_counts = (clean[NUMERIC_COLUMNS] < 0).sum()
    negative_counts = negative_counts[negative_counts > 0]
    if not negative_counts.empty:
        details = ", ".join(
            f"{column}={count}" for column, count in negative_counts.items()
        )
        raise ValueError(f"Negative values found where they are not allowed: {details}")

    if not clean["latitude"].between(-90, 90).all():
        raise ValueError("Latitude values must be between -90 and 90.")
    if not clean["longitude"].between(-180, 180).all():
        raise ValueError("Longitude values must be between -180 and 180.")

    clean = clean.drop_duplicates(
        subset=["snapshot_time", "station_id"], keep="last"
    )

    clean["unavailable_docks"] = (
        clean["capacity"]
        - clean["available_bikes"]
        - clean["available_return_spaces"]
    )
    if (clean["unavailable_docks"] < 0).any():
        invalid_rows = int((clean["unavailable_docks"] < 0).sum())
        raise ValueError(
            f"Available bikes and return spaces exceed capacity in {invalid_rows} rows."
        )

    clean["availability_rate"] = np.where(
        clean["capacity"] > 0,
        clean["available_bikes"] / clean["capacity"],
        np.nan,
    )
    clean["is_empty"] = clean["is_active"] & clean["available_bikes"].eq(0)
    clean["is_full"] = clean["is_active"] & clean["available_return_spaces"].eq(0)
    clean["station_data_age_minutes"] = (
        clean["snapshot_time"] - clean["station_updated_at"]
    ).dt.total_seconds() / 60

    return clean.sort_values(["station_id", "snapshot_time"]).reset_index(drop=True)


def add_change_features(clean_data: pd.DataFrame) -> pd.DataFrame:
    """Add between-snapshot net changes without calling them rental demand."""
    featured = clean_data.sort_values(["station_id", "snapshot_time"]).copy()
    grouped = featured.groupby("station_id", sort=False)

    featured["previous_snapshot_time"] = grouped["snapshot_time"].shift()
    featured["previous_available_bikes"] = grouped["available_bikes"].shift()
    featured["previous_is_active"] = grouped["is_active"].shift()
    featured["elapsed_minutes"] = (
        featured["snapshot_time"] - featured["previous_snapshot_time"]
    ).dt.total_seconds() / 60

    valid_interval = (
        featured["previous_snapshot_time"].notna()
        & featured["elapsed_minutes"].gt(0)
        & featured["is_active"].eq(True)
        & featured["previous_is_active"].eq(True)
    )
    featured["bike_net_change"] = (
        featured["available_bikes"] - featured["previous_available_bikes"]
    ).where(valid_interval)
    featured["estimated_net_outflow"] = (-featured["bike_net_change"]).where(
        valid_interval
    )

    return featured.reset_index(drop=True)


def build_quality_summary(
    raw_data: pd.DataFrame,
    processed_data: pd.DataFrame,
    source_paths: Iterable[Path],
) -> pd.DataFrame:
    """Create a compact table of reproducibility and quality checks."""
    source_paths = list(source_paths)
    metrics = [
        ("source_files", len(source_paths)),
        ("raw_rows", len(raw_data)),
        ("processed_rows", len(processed_data)),
        ("unique_snapshots", processed_data["snapshot_time"].nunique()),
        ("unique_stations", processed_data["station_id"].nunique()),
        ("raw_missing_cells", int(raw_data.isna().sum().sum())),
        (
            "duplicate_station_snapshot_rows_removed",
            len(raw_data) - len(processed_data),
        ),
        ("inactive_records", int((~processed_data["is_active"]).sum())),
        ("active_empty_records", int(processed_data["is_empty"].sum())),
        ("active_full_records", int(processed_data["is_full"].sum())),
        (
            "records_with_unavailable_docks",
            int(processed_data["unavailable_docks"].gt(0).sum()),
        ),
        (
            "valid_change_intervals",
            int(processed_data["bike_net_change"].notna().sum()),
        ),
        (
            "nonzero_bike_change_intervals",
            int(processed_data["bike_net_change"].fillna(0).ne(0).sum()),
        ),
    ]
    return pd.DataFrame(metrics, columns=["metric", "value"])


def build_snapshot_summary(processed_data: pd.DataFrame) -> pd.DataFrame:
    """Aggregate core availability and quality measures by snapshot."""
    return (
        processed_data.groupby("snapshot_time", as_index=False)
        .agg(
            station_records=("station_id", "size"),
            active_stations=("is_active", "sum"),
            total_capacity=("capacity", "sum"),
            available_bikes=("available_bikes", "sum"),
            return_spaces=("available_return_spaces", "sum"),
            unavailable_docks=("unavailable_docks", "sum"),
            empty_stations=("is_empty", "sum"),
            full_stations=("is_full", "sum"),
            valid_change_intervals=("bike_net_change", "count"),
            net_bike_change=("bike_net_change", "sum"),
        )
        .sort_values("snapshot_time")
        .reset_index(drop=True)
    )
