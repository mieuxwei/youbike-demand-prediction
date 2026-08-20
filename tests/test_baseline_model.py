"""Tests for chronological hourly baseline dataset construction."""

from __future__ import annotations

import unittest

import pandas as pd

from src.baseline_model import (
    build_hourly_model_dataset,
    complete_station_hours,
    evaluate_predictions,
    select_top_training_stations,
    split_by_time,
)


def hourly_demand(periods: int = 220) -> pd.DataFrame:
    hours = pd.date_range("2023-01-01", periods=periods, freq="h", tz="Asia/Taipei")
    rows = []
    for station, multiplier in [("甲站", 1), ("乙站", 2)]:
        for index, event_time in enumerate(hours):
            if station == "甲站" and index == 10:
                continue
            rows.append(
                {
                    "event_time": event_time,
                    "station_name": station,
                    "borrow_count": index * multiplier,
                    "return_count": index,
                }
            )
    return pd.DataFrame(rows)


def hourly_weather(periods: int = 220) -> pd.DataFrame:
    return pd.DataFrame(
        {
            "event_time": pd.date_range(
                "2023-01-01", periods=periods, freq="h", tz="Asia/Taipei"
            ),
            "temperature_c": 20.0,
            "relative_humidity_percent": 70.0,
            "precipitation_mm": 0.0,
            "wind_speed_kmh": 5.0,
            "is_raining": False,
        }
    )


class BaselineModelTest(unittest.TestCase):
    def test_station_selection_uses_training_period_only(self) -> None:
        demand = hourly_demand(12)
        train_end = pd.Timestamp("2023-01-01T05:00:00+08:00")
        stations = select_top_training_stations(demand, train_end, 1)
        self.assertEqual(stations, ["乙站"])

    def test_missing_internal_hour_is_filled_with_zero(self) -> None:
        completed = complete_station_hours(hourly_demand(20), ["甲站"])
        missing_hour = pd.Timestamp("2023-01-01T10:00:00+08:00")
        row = completed.loc[completed["event_time"].eq(missing_hour)].iloc[0]
        self.assertEqual(row["borrow_count"], 0)
        self.assertEqual(row["return_count"], 0)

    def test_lags_only_use_past_values(self) -> None:
        model_data = build_hourly_model_dataset(
            hourly_demand(), hourly_weather(), ["甲站"]
        )
        row = model_data.loc[
            model_data["event_time"].eq(
                pd.Timestamp("2023-01-09T00:00:00+08:00")
            )
        ].iloc[0]
        self.assertEqual(row["borrow_lag_1h"], 191)
        self.assertEqual(row["borrow_lag_24h"], 168)
        self.assertEqual(row["borrow_lag_168h"], 24)

    def test_time_splits_do_not_overlap(self) -> None:
        frame = pd.DataFrame(
            {
                "event_time": pd.date_range(
                    "2023-01-01", periods=6, freq="h", tz="Asia/Taipei"
                ),
                "value": range(6),
            }
        )
        splits = split_by_time(
            frame,
            pd.Timestamp("2023-01-01T01:00:00+08:00"),
            pd.Timestamp("2023-01-01T03:00:00+08:00"),
            pd.Timestamp("2023-01-01T05:00:00+08:00"),
        )
        self.assertLess(
            splits["train"]["event_time"].max(),
            splits["validation"]["event_time"].min(),
        )
        self.assertLess(
            splits["validation"]["event_time"].max(),
            splits["test"]["event_time"].min(),
        )

    def test_metrics_floor_negative_predictions(self) -> None:
        metrics = evaluate_predictions(pd.Series([0, 2]), pd.Series([-3, 2]))
        self.assertEqual(metrics["mae"], 0)
        self.assertEqual(metrics["rmse"], 0)


if __name__ == "__main__":
    unittest.main()
