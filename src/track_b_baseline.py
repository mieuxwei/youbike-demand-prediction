"""Preliminary leakage-aware persistence baseline for Track B availability."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

import numpy as np
import pandas as pd

try:
    from .audit_track_b import load_track_b_export
    from .features import add_future_targets
except ImportError:
    from audit_track_b import load_track_b_export
    from features import add_future_targets


def assign_chronological_splits(
    data: pd.DataFrame,
    train_days: float = 5,
    validation_days: float = 1,
) -> tuple[pd.Series, dict[str, pd.Timestamp]]:
    """Assign current observations to train/validation/test time blocks."""
    if train_days <= 0 or validation_days <= 0:
        raise ValueError("train_days and validation_days must be positive.")
    start = data["snapshot_time"].min()
    latest = data["snapshot_time"].max()
    train_end = start + pd.Timedelta(days=train_days)
    validation_end = train_end + pd.Timedelta(days=validation_days)
    if latest <= validation_end:
        raise ValueError("Dataset does not extend beyond the validation period.")

    split = pd.Series("test", index=data.index, dtype="string")
    split.loc[data["snapshot_time"].lt(validation_end)] = "validation"
    split.loc[data["snapshot_time"].lt(train_end)] = "train"
    return split, {
        "start": start,
        "train_end": train_end,
        "validation_end": validation_end,
        "latest": latest,
    }


def build_split_summary(
    data: pd.DataFrame,
    split: pd.Series,
) -> pd.DataFrame:
    """Summarize the chronological current-observation blocks."""
    frame = data[["snapshot_time", "station_id"]].copy()
    frame["split"] = split
    return (
        frame.groupby("split", observed=True)
        .agg(
            rows=("station_id", "size"),
            snapshots=("snapshot_time", "nunique"),
            stations=("station_id", "nunique"),
            first_snapshot=("snapshot_time", "min"),
            latest_snapshot=("snapshot_time", "max"),
        )
        .reindex(["train", "validation", "test"])
        .reset_index()
    )


def evaluate_persistence(
    featured: pd.DataFrame,
    split: pd.Series,
    boundaries: dict[str, pd.Timestamp],
    horizons_minutes: tuple[int, ...] = (30, 60),
) -> pd.DataFrame:
    """Evaluate current bikes as the future prediction with boundary purging."""
    rows = []
    for horizon in horizons_minutes:
        target_column = f"target_available_bikes_{horizon}m"
        actual_minutes_column = f"target_{horizon}m_actual_minutes"
        target_time = featured["snapshot_time"] + pd.to_timedelta(
            featured[actual_minutes_column], unit="m"
        )
        for split_name in ("validation", "test"):
            mask = split.eq(split_name) & featured[target_column].notna()
            if split_name == "validation":
                mask &= target_time.lt(boundaries["validation_end"])
            else:
                mask &= target_time.le(boundaries["latest"])

            actual = featured.loc[mask, target_column].to_numpy(dtype=float)
            prediction = featured.loc[mask, "available_bikes"].to_numpy(
                dtype=float
            )
            if len(actual) == 0:
                raise ValueError(
                    f"No usable {horizon}-minute targets in {split_name} split."
                )
            error = prediction - actual
            squared_error = np.square(error)
            denominator = np.square(actual - actual.mean()).sum()
            r_squared = (
                1 - squared_error.sum() / denominator
                if denominator > 0
                else np.nan
            )
            rows.append(
                {
                    "model": "current_availability_persistence",
                    "horizon_minutes": horizon,
                    "split": split_name,
                    "rows": int(len(actual)),
                    "mae": float(np.abs(error).mean()),
                    "rmse": float(np.sqrt(squared_error.mean())),
                    "r2": float(r_squared),
                    "mean_error_prediction_minus_actual": float(error.mean()),
                }
            )
    return pd.DataFrame(rows)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", type=Path, required=True)
    parser.add_argument("--train-days", type=float, default=5)
    parser.add_argument("--validation-days", type=float, default=1)
    parser.add_argument(
        "--metrics-output",
        type=Path,
        default=Path("results/track_b_persistence_metrics.csv"),
    )
    parser.add_argument(
        "--split-output",
        type=Path,
        default=Path("results/track_b_split_summary.csv"),
    )
    parser.add_argument(
        "--summary-output",
        type=Path,
        default=Path("results/track_b_baseline_summary.json"),
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    data = load_track_b_export(args.input)
    featured = add_future_targets(data)
    split, boundaries = assign_chronological_splits(
        featured,
        train_days=args.train_days,
        validation_days=args.validation_days,
    )
    split_summary = build_split_summary(featured, split)
    metrics = evaluate_persistence(featured, split, boundaries)
    summary = {
        "status": "preliminary_7_day_baseline",
        "target": "future available_bikes",
        "model": "current_availability_persistence",
        "timezone_storage": "UTC",
        "train_days": args.train_days,
        "validation_days": args.validation_days,
        "boundaries_utc": {
            key: value.isoformat() for key, value in boundaries.items()
        },
        "boundary_rule": (
            "Future target timestamps must remain inside their evaluation block."
        ),
    }

    for output in (args.metrics_output, args.split_output, args.summary_output):
        output.parent.mkdir(parents=True, exist_ok=True)
    metrics.to_csv(args.metrics_output, index=False)
    split_summary.to_csv(args.split_output, index=False)
    args.summary_output.write_text(
        json.dumps(summary, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )

    print("Chronological split")
    print(split_summary.to_string(index=False))
    print("\nPersistence baseline")
    print(metrics.to_string(index=False))


if __name__ == "__main__":
    main()
