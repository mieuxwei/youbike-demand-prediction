"""Tests for repeated historical snapshot collection."""

from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from src.collect_history import collect_history


class HistoryCollectorTest(unittest.TestCase):
    def test_collect_history_observes_count_and_interval(self) -> None:
        sleeps: list[float] = []
        save_number = 0

        def fake_fetcher() -> list[dict[str, object]]:
            return [{"sno": "test"}]

        def fake_saver(
            records: list[dict[str, object]], output_directory: Path
        ) -> Path:
            nonlocal save_number
            save_number += 1
            return output_directory / f"snapshot_{save_number}.json"

        with tempfile.TemporaryDirectory() as directory:
            paths = collect_history(
                count=3,
                interval_seconds=300,
                output_directory=Path(directory),
                fetcher=fake_fetcher,
                saver=fake_saver,
                sleep=sleeps.append,
            )

        self.assertEqual(len(paths), 3)
        self.assertEqual(sleeps, [300, 300])

    def test_collect_history_continues_after_recoverable_error(self) -> None:
        attempts = 0
        errors: list[str] = []

        def sometimes_fails() -> list[dict[str, object]]:
            nonlocal attempts
            attempts += 1
            if attempts == 1:
                raise ValueError("temporary invalid response")
            return [{"sno": "test"}]

        def fake_saver(
            records: list[dict[str, object]], output_directory: Path
        ) -> Path:
            return output_directory / "saved.json"

        paths = collect_history(
            count=2,
            interval_seconds=1,
            output_directory=Path("unused"),
            fetcher=sometimes_fails,
            saver=fake_saver,
            sleep=lambda _: None,
            report_error=errors.append,
        )

        self.assertEqual(len(paths), 1)
        self.assertIn("Attempt 1/2 failed", errors[0])


if __name__ == "__main__":
    unittest.main()
