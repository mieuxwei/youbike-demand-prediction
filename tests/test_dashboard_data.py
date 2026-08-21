"""Focused tests for the compact dashboard data builder."""

from __future__ import annotations

import unittest

import pandas as pd

from src.build_dashboard_data import json_records


class DashboardDataTests(unittest.TestCase):
    def test_json_records_converts_dataframe_values(self) -> None:
        frame = pd.DataFrame(
            [{"station": "捷運公館站", "predicted": 12.5, "rank": 1}]
        )

        self.assertEqual(
            json_records(frame),
            [{"station": "捷運公館站", "predicted": 12.5, "rank": 1}],
        )


if __name__ == "__main__":
    unittest.main()
