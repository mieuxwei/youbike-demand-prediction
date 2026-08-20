"""Tests for safe multi-month historical aggregation."""

from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

import pandas as pd

from src.historical_collection import prepare_historical_collection


class HistoricalCollectionTest(unittest.TestCase):
    def test_collection_combines_months_and_boundary_hours(self) -> None:
        columns = ["借車時間", "借車站", "還車時間", "還車站", "租借時數", "借車日期"]
        january = pd.DataFrame(
            [["2023-01-31T23:00:00+08:00", "甲站", "2023-02-01T00:00:00+08:00", "乙站", "00:10:00", "2023-01-31"]],
            columns=columns,
        )
        february = pd.DataFrame(
            [["2023-02-01T00:00:00+08:00", "乙站", "2023-02-01T01:00:00+08:00", "甲站", "00:08:00", "2023-02-01"]],
            columns=columns,
        )

        with tempfile.TemporaryDirectory() as directory:
            first = Path(directory) / "transfers_2023_01.csv"
            second = Path(directory) / "transfers_2023_02.csv"
            january.to_csv(first, index=False)
            february.to_csv(second, index=False)
            outputs = prepare_historical_collection([first, second], {"甲站", "乙站"})

        boundary = outputs["station_hour"].loc[
            lambda frame: frame["event_time"].eq(pd.Timestamp("2023-02-01T00:00:00+08:00"))
            & frame["station_name"].eq("乙站")
        ].iloc[0]
        self.assertEqual(boundary["borrow_count"], 1)
        self.assertEqual(boundary["return_count"], 1)
        quality = dict(outputs["quality"].itertuples(index=False, name=None))
        self.assertEqual(quality["source_files"], 2)
        self.assertEqual(quality["rows"], 2)


if __name__ == "__main__":
    unittest.main()
