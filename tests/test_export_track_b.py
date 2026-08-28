"""Tests for the protected Track B CSV export client and D1 uniqueness."""

from __future__ import annotations

import sqlite3
import tempfile
import unittest
from pathlib import Path
from unittest.mock import Mock

import requests

from src.export_track_b import build_export_windows, export_csv


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

    def test_export_retries_transient_server_error_for_same_page(self) -> None:
        transient = Mock()
        transient.status_code = 500
        transient_error = requests.HTTPError(response=transient)
        transient.raise_for_status.side_effect = transient_error

        success = Mock()
        success.text = "snapshot_time,station_id\n2026-08-20T00:00:00Z,A\n"
        success.headers = {}
        success.raise_for_status.return_value = None
        session = Mock()
        session.get.side_effect = [transient, success]
        sleeps: list[float] = []

        with tempfile.TemporaryDirectory() as directory:
            rows, pages = export_csv(
                "https://example.test/export.csv",
                "secret",
                "2026-08-20",
                "2026-08-20",
                Path(directory) / "export.csv",
                session=session,
                sleep=sleeps.append,
            )

        self.assertEqual((rows, pages), (1, 1))
        self.assertEqual(session.get.call_count, 2)
        self.assertEqual(sleeps, [1])

    def test_export_does_not_retry_authentication_error(self) -> None:
        unauthorized = Mock()
        unauthorized.status_code = 401
        unauthorized.raise_for_status.side_effect = requests.HTTPError(
            response=unauthorized
        )
        session = Mock()
        session.get.return_value = unauthorized

        with tempfile.TemporaryDirectory() as directory:
            with self.assertRaises(requests.HTTPError):
                export_csv(
                    "https://example.test/export.csv",
                    "bad-secret",
                    "2026-08-20",
                    "2026-08-20",
                    Path(directory) / "export.csv",
                    session=session,
                    sleep=Mock(),
                )

        self.assertEqual(session.get.call_count, 1)

    def test_export_windows_follow_taipei_date_boundaries(self) -> None:
        windows = build_export_windows(
            "2026-08-21",
            "2026-08-21",
            window_hours=6,
        )

        self.assertEqual(len(windows), 4)
        self.assertEqual(windows[0][0], "2026-08-20T16:00:00Z")
        self.assertEqual(windows[-1][1], "2026-08-21T16:00:00Z")

    def test_windowed_export_resets_cursor_without_repeating_header(self) -> None:
        first = Mock()
        first.text = "snapshot_time,station_id\n2026-08-21T00:00:00Z,A\n"
        first.headers = {}
        first.raise_for_status.return_value = None
        second = Mock()
        second.text = "snapshot_time,station_id\n2026-08-21T01:00:00Z,A\n"
        second.headers = {}
        second.raise_for_status.return_value = None
        session = Mock()
        session.get.side_effect = [first, second]

        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory) / "windowed.csv"
            rows, pages = export_csv(
                "https://example.test/export.csv",
                "secret",
                "2026-08-21T00:00:00Z",
                "2026-08-21T02:00:00Z",
                output,
                session=session,
                window_hours=1,
            )
            content = output.read_text(encoding="utf-8")

        self.assertEqual((rows, pages), (2, 2))
        self.assertEqual(content.count("snapshot_time,station_id"), 1)
        self.assertNotIn("cursor", session.get.call_args_list[1].kwargs["params"])
        self.assertEqual(
            session.get.call_args_list[1].kwargs["params"]["start"],
            "2026-08-21T01:00:00Z",
        )


if __name__ == "__main__":
    unittest.main()
