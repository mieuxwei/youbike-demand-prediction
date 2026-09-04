"""Fourteen-day Track B data-quality and persistence stability analysis."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

import numpy as np
import pandas as pd

try:
    from .features import add_future_targets
except ImportError:
    from features import add_future_targets


REQUIRED_COLUMNS = {
    "snapshot_time",
    "station_id",
    "available_bikes",
    "available_return_bikes",
    "capacity",
    "is_active",
}
TAIPEI_TIMEZONE = "Asia/Taipei"


def load_stability_export(path: Path) -> pd.DataFrame:
    """Load and strictly validate columns used by the stability analysis."""
    header = pd.read_csv(path, nrows=0)
    missing = REQUIRED_COLUMNS - set(header.columns)
    if missing:
        raise ValueError(
            "Track B export is missing required columns: "
            + ", ".join(sorted(missing))
        )
    data = pd.read_csv(
        path,
        usecols=sorted(REQUIRED_COLUMNS),
        dtype={"station_id": "string"},
    )
    if data.empty:
        raise ValueError("Track B export contains no station rows.")

    timestamp_text = data["snapshot_time"].astype("string")
    if not timestamp_text.str.contains(r"(?:Z|[+-]\d\d:\d\d)$", regex=True).all():
        raise ValueError("snapshot_time must include an explicit timezone.")
    data["snapshot_time"] = pd.to_datetime(timestamp_text, utc=True, errors="coerce")
    numeric_columns = [
        "available_bikes",
        "available_return_bikes",
        "capacity",
        "is_active",
    ]
    for column in numeric_columns:
        data[column] = pd.to_numeric(data[column], errors="coerce")
    if data[list(REQUIRED_COLUMNS)].isna().any().any():
        raise ValueError("Track B export contains missing or invalid required values.")
    if not data["is_active"].isin([0, 1]).all():
        raise ValueError("is_active must contain only 0 or 1.")
    for column in ("available_bikes", "available_return_bikes", "capacity"):
        if not np.equal(data[column], np.floor(data[column])).all():
            raise ValueError(f"{column} must contain whole numbers.")
    if (data[["available_bikes", "available_return_bikes", "capacity"]] < 0).any().any():
        raise ValueError("Bike and capacity values cannot be negative.")
    if (data["available_bikes"] > data["capacity"]).any():
        raise ValueError("available_bikes cannot exceed capacity.")
    if (data["available_return_bikes"] > data["capacity"]).any():
        raise ValueError("available_return_bikes cannot exceed capacity.")
    if data.duplicated(["station_id", "snapshot_time"]).any():
        raise ValueError("Track B export contains duplicate station snapshots.")

    data["station_id"] = data["station_id"].astype("category")
    for column in ("available_bikes", "available_return_bikes", "capacity"):
        data[column] = data[column].astype("int32")
    data["is_active"] = data["is_active"].astype(bool)
    return data.sort_values(["station_id", "snapshot_time"]).reset_index(drop=True)


def parse_utc_boundary(value: str) -> pd.Timestamp:
    """Parse an explicitly timezone-aware boundary and normalize it to UTC."""
    parsed = pd.Timestamp(value)
    if parsed.tzinfo is None:
        raise ValueError("Analysis boundaries must include an explicit timezone.")
    return parsed.tz_convert("UTC")


def assign_periods(
    data: pd.DataFrame,
    start: pd.Timestamp,
    end: pd.Timestamp,
) -> tuple[pd.Series, pd.Timestamp]:
    """Assign rows to equal week-one/week-two observation periods."""
    if end - start != pd.Timedelta(days=14):
        raise ValueError("The stability analysis requires an exact 14-day window.")
    if data["snapshot_time"].min() < start or data["snapshot_time"].max() >= end:
        raise ValueError("Export rows fall outside the requested [start, end) window.")
    midpoint = start + pd.Timedelta(days=7)
    period = pd.Series("week_2", index=data.index, dtype="string")
    period.loc[data["snapshot_time"].lt(midpoint)] = "week_1"
    return period.astype("category"), midpoint


def build_period_summary(
    data: pd.DataFrame,
    period: pd.Series,
) -> pd.DataFrame:
    """Summarize equal seven-day collection windows."""
    frame = data[["snapshot_time", "station_id", "is_active"]].copy()
    frame["period"] = period
    result = (
        frame.groupby("period", observed=True)
        .agg(
            rows=("station_id", "size"),
            active_rows=("is_active", "sum"),
            snapshots=("snapshot_time", "nunique"),
            stations=("station_id", "nunique"),
            first_snapshot=("snapshot_time", "min"),
            latest_snapshot=("snapshot_time", "max"),
        )
        .reindex(["week_1", "week_2"])
        .reset_index()
    )
    result["expected_snapshots"] = 7 * 24 * 12
    result["snapshot_coverage_percent"] = (
        100 * result["snapshots"] / result["expected_snapshots"]
    )
    return result


def build_distribution_summary(
    data: pd.DataFrame,
    period: pd.Series,
) -> pd.DataFrame:
    """Describe observed active-station availability by period and local day type."""
    active = data.loc[data["is_active"]].copy()
    active["period"] = period.loc[active.index].to_numpy()
    local_time = active["snapshot_time"].dt.tz_convert(TAIPEI_TIMEZONE)
    active["day_type"] = np.where(local_time.dt.dayofweek.ge(5), "weekend", "weekday")
    active["local_hour"] = local_time.dt.hour
    active["availability_fraction"] = np.where(
        active["capacity"].gt(0), active["available_bikes"] / active["capacity"], np.nan
    )

    rows = []
    for (period_name, day_type), group in active.groupby(
        ["period", "day_type"], observed=True
    ):
        rows.append(
            {
                "period": period_name,
                "day_type": day_type,
                "rows": int(len(group)),
                "snapshots": int(group["snapshot_time"].nunique()),
                "stations": int(group["station_id"].nunique()),
                "mean_available_bikes": float(group["available_bikes"].mean()),
                "median_available_bikes": float(group["available_bikes"].median()),
                "mean_available_return_bikes": float(
                    group["available_return_bikes"].mean()
                ),
                "mean_capacity": float(group["capacity"].mean()),
                "mean_availability_fraction": float(
                    group["availability_fraction"].mean()
                ),
                "observed_empty_percent": float(
                    100 * group["available_bikes"].eq(0).mean()
                ),
                "observed_no_return_space_percent": float(
                    100 * group["available_return_bikes"].eq(0).mean()
                ),
            }
        )
    return pd.DataFrame(rows).sort_values(["period", "day_type"]).reset_index(drop=True)


def build_hourly_profile(data: pd.DataFrame, period: pd.Series) -> pd.DataFrame:
    """Build an Asia/Taipei hourly availability profile for interpretation."""
    active = data.loc[data["is_active"]].copy()
    active["period"] = period.loc[active.index].to_numpy()
    local_time = active["snapshot_time"].dt.tz_convert(TAIPEI_TIMEZONE)
    active["day_type"] = np.where(local_time.dt.dayofweek.ge(5), "weekend", "weekday")
    active["local_hour"] = local_time.dt.hour
    return (
        active.groupby(["period", "day_type", "local_hour"], observed=True)
        .agg(
            rows=("station_id", "size"),
            mean_available_bikes=("available_bikes", "mean"),
            mean_available_return_bikes=("available_return_bikes", "mean"),
            observed_empty_percent=("available_bikes", lambda values: 100 * values.eq(0).mean()),
        )
        .reset_index()
        .sort_values(["period", "day_type", "local_hour"])
    )


def evaluate_period_persistence(
    data: pd.DataFrame,
    start: pd.Timestamp,
    end: pd.Timestamp,
    horizons_minutes: tuple[int, ...] = (30, 60),
    cohort: str = "all_stations",
) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Evaluate persistence independently in each week with end-boundary purging."""
    rows = []
    coverage_rows = []
    for week_number in (1, 2):
        period_start = start + pd.Timedelta(days=7 * (week_number - 1))
        period_end = period_start + pd.Timedelta(days=7)
        subset = data.loc[
            data["snapshot_time"].ge(period_start)
            & data["snapshot_time"].lt(period_end)
        ].copy()
        featured = add_future_targets(subset, horizons_minutes=horizons_minutes)
        for horizon in horizons_minutes:
            target_column = f"target_available_bikes_{horizon}m"
            actual_column = f"target_{horizon}m_actual_minutes"
            target_time = featured["snapshot_time"] + pd.to_timedelta(
                featured[actual_column], unit="m"
            )
            mask = featured[target_column].notna() & target_time.lt(period_end)
            actual = featured.loc[mask, target_column].to_numpy(dtype=float)
            prediction = featured.loc[mask, "available_bikes"].to_numpy(dtype=float)
            if not len(actual):
                raise ValueError(f"No usable {horizon}-minute targets in week {week_number}.")
            error = prediction - actual
            denominator = np.square(actual - actual.mean()).sum()
            squared_error = np.square(error)
            rows.append(
                {
                    "cohort": cohort,
                    "period": f"week_{week_number}",
                    "horizon_minutes": horizon,
                    "rows": int(len(actual)),
                    "mae": float(np.abs(error).mean()),
                    "rmse": float(np.sqrt(squared_error.mean())),
                    "r2": float(1 - squared_error.sum() / denominator)
                    if denominator > 0
                    else np.nan,
                    "mean_error_prediction_minus_actual": float(error.mean()),
                }
            )
            active_current = int(featured["is_active"].sum())
            coverage_rows.append(
                {
                    "cohort": cohort,
                    "period": f"week_{week_number}",
                    "horizon_minutes": horizon,
                    "active_current_rows": active_current,
                    "usable_target_rows": int(mask.sum()),
                    "coverage_percent": float(100 * mask.sum() / active_current),
                }
            )
        del featured
    return pd.DataFrame(rows), pd.DataFrame(coverage_rows)


def build_stability_comparison(metrics: pd.DataFrame) -> pd.DataFrame:
    """Compare week-two persistence errors with the matching week-one scope."""
    rows = []
    for (cohort, horizon), group in metrics.groupby(
        ["cohort", "horizon_minutes"], observed=True
    ):
        indexed = group.set_index("period")
        if not {"week_1", "week_2"}.issubset(indexed.index):
            raise ValueError("Both week_1 and week_2 metrics are required.")
        row = {"cohort": cohort, "horizon_minutes": horizon}
        for metric in ("mae", "rmse", "r2"):
            week_one = float(indexed.loc["week_1", metric])
            week_two = float(indexed.loc["week_2", metric])
            row[f"week_1_{metric}"] = week_one
            row[f"week_2_{metric}"] = week_two
            row[f"week_2_minus_week_1_{metric}"] = week_two - week_one
            if metric != "r2":
                row[f"week_2_change_percent_{metric}"] = (
                    100 * (week_two - week_one) / week_one
                )
        rows.append(row)
    return pd.DataFrame(rows).sort_values(["cohort", "horizon_minutes"])


def build_station_cohort_summary(
    data: pd.DataFrame,
    period: pd.Series,
) -> pd.DataFrame:
    """Report station composition and the week-one-defined common cohort."""
    week_one = set(data.loc[period.eq("week_1"), "station_id"].unique())
    week_two = set(data.loc[period.eq("week_2"), "station_id"].unique())
    common = week_one & week_two
    return pd.DataFrame(
        [
            {"measure": "week_1_stations", "value": len(week_one)},
            {"measure": "week_2_stations", "value": len(week_two)},
            {"measure": "common_stations", "value": len(common)},
            {"measure": "week_1_only_stations", "value": len(week_one - week_two)},
            {"measure": "week_2_only_stations", "value": len(week_two - week_one)},
            {
                "measure": "week_1_cohort_retained_percent",
                "value": 100 * len(common) / len(week_one) if week_one else np.nan,
            },
        ]
    )


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", type=Path, required=True)
    parser.add_argument("--start", required=True)
    parser.add_argument("--end", required=True)
    parser.add_argument("--output-dir", type=Path, default=Path("results"))
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    start = parse_utc_boundary(args.start)
    end = parse_utc_boundary(args.end)
    data = load_stability_export(args.input)
    period, midpoint = assign_periods(data, start, end)

    period_summary = build_period_summary(data, period)
    distribution = build_distribution_summary(data, period)
    hourly = build_hourly_profile(data, period)
    metrics, target_coverage = evaluate_period_persistence(data, start, end)
    cohort = build_station_cohort_summary(data, period)
    week_one_stations = set(data.loc[period.eq("week_1"), "station_id"])
    week_two_stations = set(data.loc[period.eq("week_2"), "station_id"])
    common_data = data.loc[data["station_id"].isin(week_one_stations & week_two_stations)]
    common_metrics, common_target_coverage = evaluate_period_persistence(
        common_data,
        start,
        end,
        cohort="week_1_common_stations",
    )
    metrics = pd.concat([metrics, common_metrics], ignore_index=True)
    target_coverage = pd.concat(
        [target_coverage, common_target_coverage], ignore_index=True
    )
    comparison = build_stability_comparison(metrics)
    summary = {
        "status": "fourteen_day_stability_analysis",
        "analysis_window": "[start, end)",
        "timezone_storage": "UTC",
        "calendar_timezone": TAIPEI_TIMEZONE,
        "start_utc": start.isoformat(),
        "midpoint_utc": midpoint.isoformat(),
        "end_utc_exclusive": end.isoformat(),
        "model": "current_availability_persistence",
        "model_training": False,
        "boundary_rule": "Future targets must stay inside the same seven-day period.",
        "interpretation": (
            "Empty/full percentages are observed descriptive states, not risk labels "
            "or classifier results."
        ),
    }

    outputs = {
        "track_b_14d_period_summary.csv": period_summary,
        "track_b_14d_distribution.csv": distribution,
        "track_b_14d_hourly_profile.csv": hourly,
        "track_b_14d_persistence_metrics.csv": metrics,
        "track_b_14d_stability_comparison.csv": comparison,
        "track_b_14d_target_coverage.csv": target_coverage,
        "track_b_14d_station_cohort.csv": cohort,
    }
    args.output_dir.mkdir(parents=True, exist_ok=True)
    for filename, frame in outputs.items():
        frame.to_csv(args.output_dir / filename, index=False)
    (args.output_dir / "track_b_14d_stability_summary.json").write_text(
        json.dumps(summary, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )

    print("Fourteen-day period summary")
    print(period_summary.to_string(index=False))
    print("\nPersistence stability")
    print(metrics.to_string(index=False))
    print("\nWeekday/weekend distribution")
    print(distribution.to_string(index=False))


if __name__ == "__main__":
    main()
