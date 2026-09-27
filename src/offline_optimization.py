"""Static integer transfers under declared assumptions, not vehicle routing."""
from __future__ import annotations

import argparse
import itertools
import json
import time
from pathlib import Path

import numpy as np
import pandas as pd
from scipy.optimize import Bounds, LinearConstraint, milp

try:
    from . import offline_forecasting as forecasting
    from .offline_forecasting import OUT, config, load_selection, sha256, write_json
except ImportError:
    import offline_forecasting as forecasting
    from offline_forecasting import OUT, config, load_selection, sha256, write_json


def great_circle_km(coordinates):
    """Great-circle proxy, explicitly not road/vehicle-route distance."""
    radians = np.radians(np.asarray(coordinates, dtype=float))
    lat, lon = radians[:, 0], radians[:, 1]
    a = np.sin((lat[:, None] - lat[None, :]) / 2) ** 2
    a += np.cos(lat[:, None]) * np.cos(lat[None, :]) * np.sin((lon[:, None] - lon[None, :]) / 2) ** 2
    return 6371.0088 * 2 * np.arcsin(np.sqrt(np.clip(a, 0, 1)))


def validate_inputs(current, capacity, forecast, distance, budget, bike_km_budget, cost, handling):
    arrays = [np.asarray(a, dtype=float) for a in (current, capacity, forecast, distance)]
    current, capacity, forecast, distance = arrays
    n = len(current)
    if n < 2 or capacity.shape != (n,) or forecast.shape != (n,) or distance.shape != (n, n):
        raise ValueError("Incompatible station arrays")
    if not all(np.isfinite(a).all() for a in arrays):
        raise ValueError("Inputs must be finite")
    if np.any(current != np.rint(current)) or np.any(capacity != np.rint(capacity)):
        raise ValueError("Current stock/capacity must be integers")
    if np.any(capacity <= 0) or np.any(current < 0) or np.any(current > capacity):
        raise ValueError("Invalid current inventory/capacity")
    if np.any(forecast < 0) or np.any(forecast > capacity) or np.any(distance < 0):
        raise ValueError("Invalid forecast/distance")
    if not all(np.isfinite(v) and v >= 0 for v in (budget, bike_km_budget, cost, handling)):
        raise ValueError("Invalid resource/cost")
    if int(budget) != budget:
        raise ValueError("Move budget must be integral")
    return arrays


def plan_values(plan, current, forecast, capacity, distance, cost, handling, fraction=0.5):
    net = plan.sum(axis=0) - plan.sum(axis=1)
    projected = forecast + net
    deviation = float(np.abs(projected - capacity * fraction).sum())
    moved = int(plan.sum())
    bike_km = float((plan * distance).sum())
    expense = cost * bike_km + handling * moved
    return {"objective": deviation + expense, "target_deviation": deviation,
            "moved_bikes": moved, "bike_km_proxy": bike_km, "transfer_penalty": expense,
            "post_transfer_current": (current + net).tolist(), "projected_future": projected.tolist()}


def assert_feasible(plan, current, capacity, forecast, distance, budget, bike_km_budget):
    tolerance = 1e-6
    if plan.shape != distance.shape or not np.isfinite(plan).all():
        raise ValueError("Invalid plan shape/values")
    if np.any(plan < 0) or not np.allclose(plan, np.rint(plan), atol=tolerance, rtol=0) or np.any(np.diag(plan)):
        raise ValueError("Transfers must be nonnegative integers without self loops")
    incoming, outgoing = plan.sum(axis=0), plan.sum(axis=1)
    net = incoming - outgoing
    if np.any(outgoing > current + tolerance):
        raise ValueError("Cannot transfer future bikes or relay arriving bikes")
    if np.any(incoming > capacity - current + tolerance):
        raise ValueError("Cannot overfill current empty docks")
    for state in (current + net, forecast + net):
        if np.any(state < -tolerance) or np.any(state > capacity + tolerance):
            raise ValueError("Post-transfer current/projected capacity violation")
    if abs(float((current + net).sum() - current.sum())) > tolerance:
        raise ValueError("Bike conservation violated")
    if plan.sum() > budget + tolerance or (plan * distance).sum() > bike_km_budget + tolerance:
        raise ValueError("Resource budget exceeded")
    return True


def optimize(current, capacity, forecast, distance, budget=12, bike_km_budget=30,
             cost=0.1, handling=0.05, fraction=0.5, time_limit=10):
    current, capacity, forecast, distance = validate_inputs(current, capacity, forecast, distance, budget, bike_km_budget, cost, handling)
    if not 0 <= fraction <= 1:
        raise ValueError("Target fraction outside [0,1]")
    n = len(current)
    edges = list(itertools.permutations(range(n), 2))
    m = len(edges)
    inbound, outbound = np.zeros((n, m)), np.zeros((n, m))
    for k, (i, j) in enumerate(edges):
        outbound[i, k] = 1
        inbound[j, k] = 1
    net = inbound - outbound
    d = np.array([distance[i, j] for i, j in edges])
    objective = np.r_[cost * d + handling, np.ones(n)]
    zero = np.zeros((n, n), dtype=int)
    blocks = []
    def constraint(matrix, lo, hi):
        blocks.append(LinearConstraint(np.c_[matrix, np.zeros((len(matrix), n))], lo, hi))
    constraint(outbound, 0, current)
    constraint(inbound, 0, capacity - current)
    constraint(net, -forecast, capacity - forecast)
    constraint(np.ones((1, m)), 0, budget)
    constraint(d[None, :], 0, bike_km_budget)
    target = capacity * fraction
    blocks.extend([
        LinearConstraint(np.c_[net, -np.eye(n)], -np.inf, target - forecast),
        LinearConstraint(np.c_[-net, -np.eye(n)], -np.inf, forecast - target),
    ])
    start = time.perf_counter()
    result = milp(objective, integrality=np.r_[np.ones(m), np.zeros(n)],
                  bounds=Bounds(np.zeros(m + n), np.r_[np.full(m, budget), np.full(n, np.inf)]),
                  constraints=blocks, options={"time_limit": time_limit, "mip_rel_gap": 0.0})
    status = "optimal"
    plan = zero.copy()
    if result.status == 0 and result.x is not None:
        if not np.allclose(result.x[:m], np.rint(result.x[:m]), atol=1e-6, rtol=0):
            raise ValueError("Solver returned nonintegral transfers")
        for amount, (i, j) in zip(np.rint(result.x[:m]).astype(int), edges):
            plan[i, j] = amount
        assert_feasible(plan, current, capacity, forecast, distance, budget, bike_km_budget)
        if plan_values(plan, current, forecast, capacity, distance, cost, handling, fraction)["objective"] >= plan_values(zero, current, forecast, capacity, distance, cost, handling, fraction)["objective"] - 1e-7:
            plan, status = zero, "optimal_no_improvement_no_transfer"
    else:
        status = f"solver_status_{result.status}_no_transfer_fallback"
    assert_feasible(plan, current, capacity, forecast, distance, budget, bike_km_budget)
    return plan, {"status": status, "solver_message": str(result.message),
                  "solve_seconds": time.perf_counter() - start, "solver_optimal": result.status == 0}


def greedy(current, capacity, forecast, distance, budget=12, bike_km_budget=30,
           cost=0.1, handling=0.05, fraction=0.5):
    current, capacity, forecast, distance = validate_inputs(current, capacity, forecast, distance, budget, bike_km_budget, cost, handling)
    n = len(current)
    plan = np.zeros((n, n), dtype=int)
    for _ in range(budget):
        best = plan_values(plan, current, forecast, capacity, distance, cost, handling, fraction)["objective"]
        chosen = None
        for i, j in itertools.permutations(range(n), 2):
            trial = plan.copy()
            trial[i, j] += 1
            try:
                assert_feasible(trial, current, capacity, forecast, distance, budget, bike_km_budget)
            except ValueError:
                continue
            value = plan_values(trial, current, forecast, capacity, distance, cost, handling, fraction)["objective"]
            if value < best - 1e-8:
                best, chosen = value, trial
        if chosen is None:
            break
        plan = chosen
    return plan


def run():
    cfg = config()["optimization"]
    selection = load_selection()
    manifest = json.loads((OUT / "data_manifest.json").read_text())
    all_stations = manifest["stations"]
    full_distance = great_circle_km([[s["latitude"], s["longitude"]] for s in all_stations])
    chosen = sorted(np.argsort(full_distance[0], kind="stable")[:cfg["station_count"]])
    stations = [all_stations[i] for i in chosen]
    station_ids = [s["station_id"] for s in stations]
    distance = full_distance[np.ix_(chosen, chosen)]
    input_path = forecasting.PREDICTIONS
    evaluation = json.loads((OUT / "evaluation.json").read_text())
    if sha256(input_path) != evaluation["prediction_file_sha256"]:
        raise ValueError("Prediction file checksum mismatch")
    if (OUT / "optimization.json").exists():
        raise FileExistsError("Simulation results already exist; no post-hoc scenario replacement")
    predictions = pd.read_csv(input_path, dtype={"station_id": str}, parse_dates=["snapshot_time", "target_time"])
    predictions = predictions[predictions.station_id.isin(station_ids)]
    common_times = predictions.groupby("snapshot_time").station_id.nunique()
    common_times = common_times[common_times.eq(len(stations))].index
    variants = [{"name": "base", "budget": cfg["base_move_budget"], "cost": cfg["base_cost_per_bike_km"]}]
    variants += [{"name": f"resource_{b}", "budget": b, "cost": cfg["base_cost_per_bike_km"]}
                 for b in cfg["resource_budgets"] if b != cfg["base_move_budget"]]
    variants += [{"name": f"distance_cost_{c}", "budget": cfg["base_move_budget"], "cost": c}
                 for c in cfg["distance_costs"] if c != cfg["base_cost_per_bike_km"]]
    scenarios, missing, table, sensitivities = [], [], [], []
    for date in cfg["scenario_dates_asia_taipei"]:
        for hour in cfg["scenario_hours_asia_taipei"]:
            requested = pd.Timestamp(f"{date}T{hour:02d}:00:00", tz="Asia/Taipei").tz_convert("UTC")
            valid = common_times[(common_times >= requested) & (common_times <= requested + pd.Timedelta(minutes=cfg["max_scenario_delay_minutes"]))]
            label = f"{date} {hour:02d}:00 Asia/Taipei"
            if len(valid) == 0:
                missing.append(label)
                continue
            when = valid[0]
            frame = predictions[predictions.snapshot_time.eq(when)].set_index("station_id").loc[station_ids]
            current, cap = frame.current_bikes.to_numpy(), frame.capacity.to_numpy()
            forecast = frame[selection["simulation_forecaster"]].to_numpy()
            actual = frame.actual.to_numpy()
            scenario = {"requested": label, "snapshot_time": when.isoformat(),
                        "forecaster": selection["simulation_forecaster"], "stations": [dict(s, current_bikes=int(b), capacity=int(c),
                        forecast=float(f), unintervened_recorded_future=float(a), target_time=str(tt)) for s, b, c, f, a, tt in
                        zip(stations, current, cap, forecast, actual, frame.target_time)], "variants": []}
            for variant in variants:
                kwargs = {"budget": variant["budget"], "bike_km_budget": cfg["base_bike_km_budget"],
                          "cost": variant["cost"], "handling": cfg["base_handling_cost_per_bike"],
                          "fraction": cfg["target_capacity_fraction"]}
                start = time.perf_counter()
                simple = greedy(current, cap, forecast, distance, **kwargs)
                greedy_seconds = time.perf_counter() - start
                optimal, info = optimize(current, cap, forecast, distance, **kwargs, time_limit=cfg["solver_time_limit_seconds"])
                plans = {"no_transfer": np.zeros_like(distance, dtype=int), "greedy": simple, "milp": optimal}
                record = dict(variant, bike_km_budget=kwargs["bike_km_budget"], handling_cost=kwargs["handling"], plans={})
                for name, plan in plans.items():
                    assert_feasible(plan, current, cap, forecast, distance, kwargs["budget"], kwargs["bike_km_budget"])
                    values = plan_values(plan, current, forecast, cap, distance, kwargs["cost"], kwargs["handling"], kwargs["fraction"])
                    values["transfers"] = [{"from": station_ids[i], "to": station_ids[j], "bikes": int(plan[i, j]),
                                            "distance_km_proxy": float(distance[i, j])} for i, j in zip(*np.nonzero(plan))]
                    values["status"] = info["status"] if name == "milp" else "feasible"
                    values["solve_seconds"] = info["solve_seconds"] if name == "milp" else (greedy_seconds if name == "greedy" else 0.0)
                    values["constraints_verified"] = True
                    record["plans"][name] = values
                    table.append({"scenario": label, "variant": variant["name"], "method": name,
                                  **{k: v for k, v in values.items() if not isinstance(v, list)}})
                    if variant["name"] == "base":
                        net = plan.sum(axis=0) - plan.sum(axis=1)
                        sign = np.where(np.arange(len(stations)) % 2, -1, 1)
                        references = {f"synthetic_error_{shock:+d}": np.clip(forecast + shock * sign, 0, cap)
                                      for shock in cfg["forecast_error_shocks_bikes"]}
                        references["unintervened_historical_reference"] = actual
                        for ref_name, reference in references.items():
                            unbounded = reference + net
                            simulated = np.clip(unbounded, 0, cap)
                            sensitivities.append({"scenario": label, "method": name, "reference": ref_name,
                                "simulated_target_deviation": float(np.abs(simulated - cap * kwargs["fraction"]).sum()),
                                "boundary_clipped_bikes": float(np.abs(simulated - unbounded).sum()),
                                "transfer_penalty": values["transfer_penalty"],
                                "interpretation": "assumed additive intervention, not observed counterfactual or lost trips"})
                if record["plans"]["milp"]["status"].startswith("optimal"):
                    if record["plans"]["milp"]["objective"] > min(record["plans"][n]["objective"] for n in ("no_transfer", "greedy")) + 1e-5:
                        raise AssertionError("Certified optimum worse than feasible baseline")
                scenario["variants"].append(record)
            scenarios.append(scenario)
            print("Completed simulation:", label, flush=True)
    if not scenarios:
        raise ValueError("No pre-specified scenario has common valid observations; cannot freeze")
    write_json(OUT / "optimization.json", {"study_type": "static simulation only", "config_sha256": sha256("config/offline_research.json"),
        "simulation_forecaster_selected_on_validation": selection["simulation_forecaster"], "station_ids": station_ids,
        "distance_definition": "great-circle km proxy, not roads or routes", "missing_scenario_requests": missing,
        "scenarios": scenarios, "demonstration": scenarios[0]["requested"]})
    pd.DataFrame(table).to_csv(OUT / "optimization_comparison.csv", index=False)
    pd.DataFrame(sensitivities).to_csv(OUT / "optimization_sensitivity.csv", index=False)
    print("Simulation requests:", len(scenarios), "valid,", len(missing), "unavailable", flush=True)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--run-dir", type=Path, help="Same isolated directory used for forecasting reproduction")
    args = parser.parse_args()
    if args.run_dir:
        forecasting.use_run_directory(args.run_dir)
        OUT = forecasting.OUT
    run()
