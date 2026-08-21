"""Tests for the protected Track B CSV export client and D1 uniqueness."""

from __future__ import annotations

import sqlite3
import tempfile
import unittest
from pathlib import Path
from unittest.mock import Mock

from src.export_track_b import export_csv


class ExportTrackBTests(unittest.TestCase):
    def test_export_csv_combines_cursor_pages_atomically(self) -> None:
        first = Mock()
        first.text = "snapshot_time,station_id\n2026-08-20T00:00:00Z,A\n"
        first.headers = {"x-next-cursor": "next-page"}
        second = Mock()
        second.text = "snapshot_time,station_id\n2026-08-20T00:05:00Z,A\n"
        second.headers = {}
        session = Mock()
        session.get.side_effect = [first, second]

        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory) / "export.csv"
            rows, pages = export_csv(
                "https://example.test/export.csv",
                "secret",
                "2026-08-20",
                "2026-08-20",
                output,
                station_id="A",
                session=session,
            )
            content = output.read_text(encoding="utf-8")

        self.assertEqual((rows, pages), (2, 2))
        self.assertEqual(content.count("snapshot_time,station_id"), 1)
        self.assertIn("2026-08-20T00:05:00Z,A", content)
        self.assertEqual(
            session.get.call_args_list[1].kwargs["params"]["cursor"], "next-page"
        )

    def test_d1_schema_prevents_duplicate_station_snapshot_rows(self) -> None:
        migration = Path(
            "cloudflare/track-b-collector/migrations/0001_track_b_live.sql"
        ).read_text(encoding="utf-8")
        connection = sqlite3.connect(":memory:")
        connection.executescript(migration)
        values = (
            "2026-08-20T13:15:00.000Z",
            "2026-08-20T13:14:52.000Z",
            "2026-08-20T13:14:03.000Z",
            "500101001",
            "YouBike2.0_Test",
            10,
            8,
            20,
            25.0,
            121.5,
            1,
        )
        sql = "INSERT INTO station_snapshots VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)"
        connection.execute(sql, values)

        with self.assertRaises(sqlite3.IntegrityError):
            connection.execute(sql, values)


if __name__ == "__main__":
    unittest.main()
