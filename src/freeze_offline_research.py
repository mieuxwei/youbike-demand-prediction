"""Record and verify local research artifacts without Git or cloud mutations."""
from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo


ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "results/offline_research"
BASELINE = OUT / "protected_baseline.json"
MANIFEST = OUT / "freeze_manifest.json"


def digest(path):
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for block in iter(lambda: f.read(1024 * 1024), b""):
            h.update(block)
    return h.hexdigest()


def git(*args):
    return subprocess.check_output(["git", *args], cwd=ROOT, text=True).strip()


def write(path, data):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2, ensure_ascii=False) + "\n")


def baseline():
    if BASELINE.exists():
        raise FileExistsError("Protected baseline already recorded")
    paths = []
    for prefix in ("models", "config", "results", "cloudflare"):
        paths += [p for p in (ROOT / prefix).rglob("*") if p.is_file()
                  and not any(part in ("offline_research", "node_modules", ".wrangler", "dist") for part in p.parts)
                  and p.name != "offline_research.json" and not p.name.startswith(".")]
    paths += [ROOT / p for p in ("docs/STAGE_17_TRACK_B_28_DAY_REGRESSION.md",
              "docs/STAGE_19_TRACK_B_INDEPENDENT_VALIDATION.md", "dashboard/app/dashboard-data.json")]
    paths += [ROOT / p for p in git("ls-files", "src").splitlines()]
    files = {str(p.relative_to(ROOT)): digest(p) for p in sorted(set(paths))}
    write(BASELINE, {"captured_at": datetime.now(ZoneInfo("Asia/Taipei")).isoformat(),
                    "head": git("rev-parse", "HEAD"), "note": "Protected existing-artifact baseline; pre-existing Stage 19 working-tree results included. captured_at is baseline completion, not experiment start.", "files": files})
    print("Protected artifacts recorded:", len(files))


def verify_files(records):
    for name, expected in records.items():
        path = ROOT / name
        if not path.is_file() or digest(path) != expected:
            raise ValueError(f"Checksum mismatch: {name}")


def check_research():
    import numpy as np
    import pandas as pd
    from offline_forecasting import load_prepared, load_selection, metrics, predict_sequences
    from offline_optimization import assert_feasible, great_circle_km, plan_values

    verify_files(json.loads(BASELINE.read_text())["files"])
    selection = load_selection()
    arrays, data = load_prepared()
    if digest(ROOT / data["input"]) != data["input_sha256"]:
        raise ValueError("Raw input hash mismatch")
    comparison = pd.read_csv(OUT / "comparison.csv")
    expected = {"persistence", "hgb", "lstm_ensemble", *[f"lstm_seed{s}" for s in selection["seeds"]]}
    assert set(comparison.model) == expected
    assert comparison.rows.nunique() == comparison.sample_keys_sha256.nunique() == 1
    evaluation = json.loads((OUT / "evaluation.json").read_text())
    prediction_path = ROOT / "data/processed/offline_research_predictions.csv"
    assert digest(prediction_path) == evaluation["prediction_file_sha256"]
    mask = arrays["split"] == 2
    full = pd.read_csv(prediction_path, dtype={"station_id": str})
    assert len(full) == int(mask.sum()) == evaluation["rows"]
    assert not full.duplicated(["station_id", "snapshot_time"]).any()
    ids = np.array([s["station_id"] for s in data["stations"]])
    np.testing.assert_array_equal(full.station_id, ids[arrays["station"][mask]])
    np.testing.assert_array_equal(pd.to_datetime(full.snapshot_time, utc=True).astype("int64"), arrays["time"][mask])
    np.testing.assert_array_equal(pd.to_datetime(full.target_time, utc=True).astype("int64"), arrays["target_time"][mask])
    np.testing.assert_array_equal(full.actual, arrays["y"][mask])
    keys = full[["station_id", "snapshot_time", "target_time"]].to_csv(index=False).encode()
    assert hashlib.sha256(keys).hexdigest() == evaluation["sample_keys_sha256"]
    for row in comparison.itertuples():
        measured = metrics(full.actual, full[row.model])
        np.testing.assert_allclose([row.mae, row.rmse, row.r2], list(measured.values()), atol=1e-6, rtol=1e-6)
        assert row.rows == len(full) and row.sample_keys_sha256 == evaluation["sample_keys_sha256"]
    sample = arrays["x"][mask][:10]
    prediction, _ = predict_sequences(sample, selection)
    saved = pd.read_csv(prediction_path, nrows=10)
    for name in expected:
        np.testing.assert_allclose(prediction[name], saved[name], atol=1e-5, rtol=1e-6)
    np.save("/tmp/youbike-offline-inference-smoke.npy", sample)
    simulation = json.loads((OUT / "optimization.json").read_text())
    assert simulation["scenarios"]
    assert simulation["simulation_forecaster_selected_on_validation"] == selection["simulation_forecaster"]
    count = 0
    for scenario in simulation["scenarios"]:
        ids = [s["station_id"] for s in scenario["stations"]]
        c = np.array([s["current_bikes"] for s in scenario["stations"]])
        cap = np.array([s["capacity"] for s in scenario["stations"]])
        forecast = np.array([s["forecast"] for s in scenario["stations"]])
        distances = great_circle_km([[s["latitude"], s["longitude"]] for s in scenario["stations"]])
        for variant in scenario["variants"]:
            for method, values in variant["plans"].items():
                plan = np.zeros((len(ids), len(ids)), dtype=int)
                for item in values["transfers"]:
                    plan[ids.index(item["from"]), ids.index(item["to"])] += item["bikes"]
                assert_feasible(plan, c, cap, forecast, distances, variant["budget"], variant["bike_km_budget"])
                computed = plan_values(plan, c, forecast, cap, distances, variant["cost"], variant["handling_cost"])
                assert abs(computed["objective"] - values["objective"]) < 1e-5
                if method == "milp":
                    assert values["status"].startswith("optimal"), "Unresolved solver status must be reviewed before freeze"
                count += 1
    print("Research verified: raw/config/model hashes, common scope, reloaded inference,", count, "simulation plans; protected baseline unchanged.")


def freeze():
    if MANIFEST.exists():
        raise FileExistsError("Already frozen; explicit reopening required")
    check_research()
    record = json.loads((OUT / "acceptance.json").read_text())
    assert record["all_required_checks_passed"] is True
    paths = set(git("ls-files").splitlines()) | set(git("ls-files", "--others", "--exclude-standard").splitlines())
    paths.discard(str(MANIFEST.relative_to(ROOT)))
    hashes = {p: digest(ROOT / p) for p in sorted(paths) if (ROOT / p).is_file()}
    write(MANIFEST, {"status": "Research Complete — Implementation Frozen",
                    "frozen_at": datetime.now(ZoneInfo("Asia/Taipei")).isoformat(),
                    "scope": "Existing Track A/Stage 17/19 plus retrospective 60m LSTM comparison, static MILP simulation, local Dashboard",
                    "git_head": git("rev-parse", "HEAD"), "git_status_before_manifest": git("status", "--short"),
                    "publication": "Local working-directory version; not committed, pushed, tagged, released, or deployed by this task",
                    "cloud_service_changes": "none", "stop_rule": "No autonomous new work; explicit owner request required to reopen",
                    "reproduction_tolerance": "Same-version CPU predictions atol 1e-5, rtol 1e-6; runtimes vary; equal-objective MILP transfer ties may differ",
                    "files": hashes, "manifest_note": "This manifest excludes itself to avoid self-referential hashes; raw/cache hashes are in data_manifest.json"})
    print("Frozen local artifact manifest:", MANIFEST)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command", choices=["baseline", "check", "freeze", "verify"])
    args = parser.parse_args()
    if args.command == "verify":
        verify_files(json.loads(MANIFEST.read_text())["files"])
        print("Freeze manifest file hashes verified")
    else:
        {"baseline": baseline, "check": check_research, "freeze": freeze}[args.command]()
