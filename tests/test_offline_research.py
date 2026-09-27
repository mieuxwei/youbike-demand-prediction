"""Behavioral tests for sequence leakage boundaries and feasible integer transfers."""
import itertools
import unittest

import numpy as np
import pandas as pd

from src.offline_forecasting import config, development_arrays, split_code, station_sequences
from src.offline_optimization import assert_feasible, greedy, optimize, plan_values


class SequenceTests(unittest.TestCase):
    def fixture(self):
        cfg = config()
        cfg.update(window_start="2026-01-01T00:00:00Z", train_end="2026-01-02T00:00:00Z",
                   validation_end="2026-01-03T00:00:00Z", test_end="2026-01-04T00:00:00Z")
        n = 50
        frame = pd.DataFrame({"station_id": ["one"] * n, "snapshot_time": pd.date_range("2026-01-01", periods=n, freq="5min", tz="UTC"),
                              "available_bikes": np.arange(n), "available_return_bikes": 100 - np.arange(n),
                              "capacity": 100, "latitude": 25.0, "longitude": 121.5, "is_active": 1, "slot": np.arange(n)})
        return cfg, frame

    def test_alignment_and_future_values_do_not_change_past_predictors(self):
        cfg, data = self.fixture()
        original = station_sequences(data, cfg)
        np.testing.assert_array_equal(original["x"][0, :, 0], np.arange(13))
        self.assertEqual(original["y"][0], 24)
        data.loc[24, "available_bikes"] = 80
        data.loc[24, "available_return_bikes"] = 20
        changed = station_sequences(data, cfg)
        np.testing.assert_array_equal(original["x"][0], changed["x"][0])
        self.assertEqual(changed["y"][0], 80)

    def test_cross_station_gap_inactive_and_boundary_rejected(self):
        cfg, data = self.fixture()
        mixed = data.copy()
        mixed.loc[0, "station_id"] = "another"
        with self.assertRaises(ValueError):
            station_sequences(mixed, cfg)
        inactive = data.copy()
        inactive.loc[5, "is_active"] = 0
        outputs = station_sequences(inactive, cfg)
        self.assertTrue((outputs["time"] > data.loc[17, "snapshot_time"].value).all())
        missing = data.drop(index=5)
        outputs = station_sequences(missing, cfg)
        self.assertTrue((outputs["time"] > data.loc[17, "snapshot_time"].value).all())
        boundary = pd.Timestamp(cfg["train_end"]).value
        codes = split_code(np.array([boundary - 60 * 10**9, boundary]),
                           np.array([boundary, boundary + 3600 * 10**9]), cfg)
        np.testing.assert_array_equal(codes, [-1, 1])

    def test_duplicate_and_invalid_target_excluded(self):
        cfg, data = self.fixture()
        with self.assertRaises(ValueError):
            station_sequences(pd.concat([data, data.iloc[:1]]), cfg)
        data.loc[24, "is_active"] = 0
        outputs = station_sequences(data, cfg)
        self.assertNotIn(data.loc[12, "snapshot_time"].value, outputs["time"])

    def test_scaler_is_unaffected_by_validation_or_evaluation_values(self):
        rng = np.random.default_rng(3)
        arrays = {"x": rng.normal(size=(12, 13, 9)).astype("float32"),
                  "y": rng.normal(size=12).astype("float32"),
                  "split": np.repeat([0, 1, 2], 4),
                  "train_mask": np.arange(12) < 4}
        _, _, before, scale_before, _, _ = development_arrays(arrays)
        arrays["x"][4:] += 10000
        arrays["y"][4:] -= 10000
        _, _, after, scale_after, _, _ = development_arrays(arrays)
        np.testing.assert_array_equal(before.mean_, after.mean_)
        np.testing.assert_array_equal(before.scale_, after.scale_)
        self.assertEqual(scale_before, scale_after)


class RedistributionTests(unittest.TestCase):
    def test_milp_matches_tiny_bruteforce_optimum(self):
        current, cap, forecast = np.array([8., 1., 5.]), np.array([10., 10., 10.]), np.array([8., 2., 5.])
        distance = np.array([[0., 1., 2.], [1., 0., 1.], [2., 1., 0.]])
        edges = list(itertools.permutations(range(3), 2))
        feasible = []
        for v in itertools.product(range(3), repeat=len(edges)):
            if sum(v) > 2:
                continue
            plan = np.zeros((3, 3), dtype=int)
            for (i, j), amount in zip(edges, v):
                plan[i, j] = amount
            try:
                assert_feasible(plan, current, cap, forecast, distance, 2, 4)
                feasible.append(plan_values(plan, current, forecast, cap, distance, .1, .05)["objective"])
            except ValueError:
                pass
        plan, info = optimize(current, cap, forecast, distance, budget=2, bike_km_budget=4)
        self.assertTrue(info["solver_optimal"])
        self.assertAlmostEqual(plan_values(plan, current, forecast, cap, distance, .1, .05)["objective"], min(feasible))
        self.assertEqual(plan.sum(), 2)

    def test_cannot_move_future_bikes_or_exceed_current_docks(self):
        distance = np.array([[0., 1.], [1., 0.]])
        for current, forecast in [(np.array([0., 1.]), np.array([9., 1.])),
                                  (np.array([9., 10.]), np.array([9., 1.]))]:
            plan, _ = optimize(current, np.array([10., 10.]), forecast, distance)
            self.assertEqual(plan.sum(), 0)
        with self.assertRaises(ValueError):
            assert_feasible(np.array([[0., .5], [0., 0.]]), np.array([5., 5.]), np.array([10., 10.]),
                            np.array([5., 5.]), distance, 12, 30)

    def test_no_transfer_for_zero_resources_high_cost_or_balanced_inventory(self):
        c, cap, f = np.array([9., 1.]), np.array([10., 10.]), np.array([9., 1.])
        d = np.array([[0., 1.], [1., 0.]])
        for kwargs in ({"budget": 0}, {"cost": 10}, {"bike_km_budget": 0}):
            plan, _ = optimize(c, cap, f, d, **kwargs)
            self.assertEqual(plan.sum(), 0)
        plan, _ = optimize(c, cap, np.array([5., 5.]), d)
        self.assertEqual(plan.sum(), 0)
        for method in (greedy, lambda *a, **k: optimize(*a, **k)[0]):
            plan = method(c, cap, f, d, budget=3, bike_km_budget=2)
            self.assertTrue(assert_feasible(plan, c, cap, f, d, 3, 2))
            self.assertEqual((c + plan.sum(0) - plan.sum(1)).sum(), c.sum())

    def test_invalid_inputs_fail_explicitly(self):
        with self.assertRaises(ValueError):
            optimize(np.array([11., 0.]), np.array([10., 10.]), np.array([5., 5.]), np.ones((2, 2)))


if __name__ == "__main__":
    unittest.main()
