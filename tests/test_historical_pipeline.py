"""Tests for official historical transfer-trip processing."""

from __future__ import annotations

import unittest

import pandas as pd

from src.historical_pipeline import (
    build_hourly_profile,
    build_station_hour_demand,
    clean_historical_trips,
    normalize_station_name,
)


def example_raw_data() -> pd.DataFrame:
    """Create valid hourly historical rows, including a legitimate duplicate."""
    row = {
        "借車時間": "2023-01-02T08:00:00+08:00",
        "借車站": "YouBike2.0_台北車站",
        "還車時間": "2023-01-02T09:00:00+08:00",
        "還車站": "科技大樓",
        "租借時數": "00:12:30",
        "借車日期": "2023-01-02",
    }
    return pd.DataFrame(
        [
            row,
            row.copy(),
            {
                **row,
                "借車時間": "2023-01-07T18:00:00+08:00",
                "還車時間": "2023-01-07T19:00:00+08:00",
                "借車站": "科技大樓",
                "還車站": "台北車站",
                "借車日期": "2023-01-07",
            },
        ]
    )


class HistoricalPipelineTest(unittest.TestCase):
    def test_station_name_normalization(self) -> None:
        self.assertEqual(normalize_station_name(" YouBike2.0_台北車站 "), "臺北車站")

    def test_cleaning_retains_and_flags_identical_rows(self) -> None:
        clean = clean_historical_trips(
            example_raw_data(), {"臺北車站", "科技大樓"}
        )

        self.assertEqual(len(clean), 3)
        self.assertEqual(int(clean["is_exact_duplicate"].sum()), 2)
        self.assertEqual(clean.loc[0, "duration_minutes"], 12.5)
        self.assertTrue(clean["borrow_station_current_match"].all())

    def test_station_hour_demand_counts_borrows_and_returns(self) -> None:
        clean = clean_historical_trips(
            example_raw_data(), {"臺北車站", "科技大樓"}
        )
        demand = build_station_hour_demand(clean)
        taipei_at_eight = demand[
            demand["station_name"].eq("臺北車站") & demand["hour"].eq(8)
        ].iloc[0]

        self.assertEqual(taipei_at_eight["borrow_count"], 2)
        self.assertEqual(taipei_at_eight["return_count"], 0)
        self.assertEqual(taipei_at_eight["net_flow"], -2)

    def test_missing_station_keeps_the_usable_side_of_trip(self) -> None:
        raw = example_raw_data().iloc[[0]].copy()
        raw.loc[raw.index[0], "借車站"] = pd.NA
        clean = clean_historical_trips(raw, {"科技大樓"})
        demand = build_station_hour_demand(clean)

        self.assertTrue(clean.loc[0, "borrow_station"] is pd.NA or pd.isna(clean.loc[0, "borrow_station"]))
        self.assertEqual(demand["borrow_count"].sum(), 0)
        self.assertEqual(demand["return_count"].sum(), 1)

    def test_hourly_profile_includes_zero_activity_hours(self) -> None:
        clean = clean_historical_trips(
            example_raw_data(), {"臺北車站", "科技大樓"}
        )
        profile = build_hourly_profile(clean)

        self.assertEqual(len(profile), 48)
        weekday_midnight = profile[
            profile["is_weekend"].eq(False) & profile["borrow_hour"].eq(0)
        ].iloc[0]
        self.assertEqual(weekday_midnight["total_trips"], 0)


if __name__ == "__main__":
    unittest.main()
