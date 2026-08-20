"""Tests for weather cleaning and leakage-free hourly joins."""

from __future__ import annotations

import unittest

import pandas as pd

from src.weather_pipeline import (
    build_rain_hour_profile,
    clean_weather,
    merge_weather_with_demand,
)


class WeatherPipelineTest(unittest.TestCase):
    def setUp(self) -> None:
        self.weather = clean_weather(
            pd.DataFrame(
                {
                    "event_time": ["2023-01-01T08:00", "2023-01-01T09:00"],
                    "temperature_2m": [18.0, 19.0],
                    "relative_humidity_2m": [80, 82],
                    "precipitation": [0.0, 1.2],
                    "wind_speed_10m": [5.0, 6.0],
                    "weather_code": [3, 61],
                }
            )
        )

    def test_clean_weather_creates_rain_flag(self) -> None:
        self.assertEqual(self.weather["is_raining"].tolist(), [False, True])
        self.assertEqual(str(self.weather["event_time"].dt.tz), "Asia/Taipei")

    def test_merge_matches_only_the_same_hour(self) -> None:
        demand = pd.DataFrame(
            {
                "event_time": ["2023-01-01T08:00:00+08:00", "2023-01-01T10:00:00+08:00"],
                "station_name": ["甲站", "甲站"],
                "borrow_count": [3, 2],
                "return_count": [1, 1],
            }
        )
        merged = merge_weather_with_demand(demand, self.weather)
        self.assertEqual(merged["weather_matched"].tolist(), [True, False])
        self.assertEqual(merged.loc[0, "temperature_c"], 18.0)

    def test_rain_profile_keeps_time_strata(self) -> None:
        demand = pd.DataFrame(
            {
                "event_time": ["2023-01-01T08:00:00+08:00", "2023-01-01T09:00:00+08:00"],
                "station_name": ["甲站", "甲站"],
                "borrow_count": [3, 2],
                "return_count": [1, 1],
            }
        )
        profile = build_rain_hour_profile(
            merge_weather_with_demand(demand, self.weather)
        )
        self.assertEqual(set(profile["hour"]), {8, 9})
        self.assertEqual(set(profile["is_raining"]), {False, True})


if __name__ == "__main__":
    unittest.main()
