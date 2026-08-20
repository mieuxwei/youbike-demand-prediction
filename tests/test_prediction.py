"""Tests for safe, target-hour prediction feature construction."""

from __future__ import annotations

import hashlib
import tempfile
import unittest
from pathlib import Path

import pandas as pd

from src.prediction import (
    build_prediction_features,
    load_verified_model,
    local_hour,
)


def prediction_demand() -> pd.DataFrame:
    hours = pd.date_range(
        "2023-01-01", periods=170, freq="h", tz="Asia/Taipei"
    )
    rows = []
    for station, offset in [("甲站", 0), ("乙站", 10)]:
        for index, event_time in enumerate(hours):
            rows.append(
                {
                    "event_time": event_time,
                    "station_name": station,
                    "borrow_count": index + offset,
                    "return_count": index,
                }
            )
    return pd.DataFrame(rows)


def target_weather() -> pd.DataFrame:
    return pd.DataFrame(
        {
            "event_time": [pd.Timestamp("2023-01-08T01:00:00+08:00")],
            "temperature_c": [20.0],
            "relative_humidity_percent": [70.0],
            "precipitation_mm": [0.2],
            "wind_speed_kmh": [5.0],
            "is_raining": [True],
        }
    )


class PredictionTest(unittest.TestCase):
    def test_local_hour_rejects_partial_hour(self) -> None:
        with self.assertRaises(ValueError):
            local_hour("2023-01-01T10:30:00+08:00")

    def test_target_actual_never_changes_prediction_features(self) -> None:
        demand = prediction_demand()
        target = "2023-01-08T01:00:00+08:00"
        first = build_prediction_features(
            demand, target_weather(), ["甲站", "乙站"], target
        )
        demand.loc[
            demand["event_time"].eq(pd.Timestamp(target)), "borrow_count"
        ] = 999999
        second = build_prediction_features(
            demand, target_weather(), ["甲站", "乙站"], target
        )
        pd.testing.assert_frame_equal(first, second)

    def test_lags_and_rolling_use_only_prior_hours(self) -> None:
        features = build_prediction_features(
            prediction_demand(),
            target_weather(),
            ["甲站", "乙站"],
            "2023-01-08T01:00:00+08:00",
        ).set_index("station_name")
        self.assertEqual(features.loc["甲站", "borrow_lag_1h"], 168)
        self.assertEqual(features.loc["甲站", "borrow_lag_24h"], 145)
        self.assertEqual(features.loc["甲站", "borrow_lag_168h"], 1)
        self.assertEqual(
            features.loc["甲站", "borrow_rolling_mean_24h"],
            sum(range(145, 169)) / 24,
        )

    def test_checksum_is_checked_before_joblib_load(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            artifact = Path(directory) / "model.joblib"
            artifact.write_bytes(b"not a model")
            metadata = {"artifact_sha256": hashlib.sha256(b"different").hexdigest()}
            with self.assertRaisesRegex(ValueError, "checksum"):
                load_verified_model(artifact, metadata)


if __name__ == "__main__":
    unittest.main()
