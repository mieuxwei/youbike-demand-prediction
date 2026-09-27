"""Bounded retrospective 60m sequence comparison; never changes Stage 17/19."""
from __future__ import annotations

import argparse
import copy
import hashlib
import json
import os
import platform
import subprocess
import time
from pathlib import Path

import joblib
import numpy as np
import pandas as pd
from sklearn.ensemble import HistGradientBoostingRegressor
from sklearn.metrics import mean_absolute_error, mean_squared_error, r2_score
from sklearn.preprocessing import StandardScaler

CONFIG = Path("config/offline_research.json")
OUT = Path("results/offline_research")
MODELS = Path("models/offline_research")
CACHE = Path("data/processed/offline_research.npz")
PREDICTIONS = Path("data/processed/offline_research_predictions.csv")
FEATURES = ["available_bikes", "available_return_bikes", "capacity", "latitude", "longitude",
            "hour_sin", "hour_cos", "weekday_sin", "weekday_cos"]


def use_run_directory(path):
    """Isolate intentional reproductions from the frozen research outputs."""
    global OUT, MODELS, CACHE, PREDICTIONS
    path = Path(path).resolve()
    OUT, MODELS = path / "results", path / "models"
    CACHE, PREDICTIONS = path / "sequences.npz", path / "predictions.csv"


def sha256(path):
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for block in iter(lambda: f.read(1024 * 1024), b""):
            h.update(block)
    return h.hexdigest()


def write_json(path, value):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, ensure_ascii=False, allow_nan=False) + "\n")


def config():
    return json.loads(CONFIG.read_text())


def metrics(y, p):
    return {"mae": float(mean_absolute_error(y, p)),
            "rmse": float(np.sqrt(mean_squared_error(y, p))), "r2": float(r2_score(y, p))}


def split_code(origin, target, cfg):
    """Future labels must stay in their origin split; histories can precede it."""
    edges = [pd.Timestamp(cfg[k]).value for k in
             ("window_start", "train_end", "validation_end", "test_end")]
    codes = np.full(len(origin), -1, dtype=np.int8)
    for code, (a, b) in enumerate(zip(edges[:-1], edges[1:])):
        codes[(origin >= a) & (origin < b) & (target < b)] = code
    return codes


def station_sequences(station, cfg):
    """Construct one-station windows; skip inactive, missing, and gapped history."""
    if station.station_id.nunique() != 1:
        raise ValueError("Sequences must be constructed for exactly one station")
    station = station.sort_values("snapshot_time").reset_index(drop=True)
    t = station.snapshot_time.astype("int64").to_numpy()
    if np.any(np.diff(t) <= 0):
        raise ValueError("Duplicate/non-increasing station times")
    n, length = len(t), cfg["sequence_length"]
    numeric = station[FEATURES[:5]].to_numpy(dtype=np.float32)
    valid = np.isfinite(numeric).all(axis=1) & station.is_active.eq(1).to_numpy()
    valid &= (numeric[:, 2] > 0) & (numeric[:, 0] >= 0) & (numeric[:, 1] >= 0)
    valid &= (numeric[:, 0] + numeric[:, 1] <= numeric[:, 2])
    local = station.snapshot_time.dt.tz_convert("Asia/Taipei")
    hour = local.dt.hour.to_numpy() + local.dt.minute.to_numpy() / 60
    dow = local.dt.dayofweek.to_numpy()
    inputs = np.column_stack([numeric, np.sin(hour * np.pi / 12), np.cos(hour * np.pi / 12),
                              np.sin(dow * 2 * np.pi / 7), np.cos(dow * 2 * np.pi / 7)]).astype("float32")
    origins = np.arange(length - 1, n)
    history = origins[:, None] - np.arange(length - 1, -1, -1)
    gaps = np.diff(t[history], axis=1) / 1e9
    complete = valid[history].all(axis=1)
    complete &= ((gaps >= cfg["minimum_step_seconds"]) & (gaps <= cfg["maximum_step_seconds"])).all(axis=1)
    desired = t[origins] + cfg["horizon_minutes"] * 60 * 10**9
    future = np.searchsorted(t, desired)
    safe = np.minimum(future, n - 1)
    complete &= (future < n) & valid[safe]
    complete &= (t[safe] - desired >= 0) & (t[safe] - desired <= cfg["target_tolerance_seconds"] * 10**9)
    codes = split_code(t[origins], t[safe], cfg)
    keep = complete & (codes >= 0)
    origins, history, safe, codes = origins[keep], history[keep], safe[keep], codes[keep]
    return {"x": inputs[history], "y": numeric[safe, 0], "time": t[origins],
            "target_time": t[safe], "split": codes, "slot": station.slot.to_numpy()[origins]}


def prepare():
    cfg = config()
    runtime = environment()  # Fail before writing any output if a dependency is absent.
    source = Path(cfg["input"])
    if CACHE.exists() or (OUT / "data_manifest.json").exists():
        raise FileExistsError("Prepared research already exists; verify it instead of overwriting")
    start, end = pd.Timestamp(cfg["window_start"]), pd.Timestamp(cfg["test_end"])
    train_end = pd.Timestamp(cfg["train_end"])
    use = ["snapshot_time", "station_id", "station_name", *FEATURES[:5], "is_active"]
    all_times, train_times, counts, first = set(), set(), {}, {}
    rows = 0
    for chunk in pd.read_csv(source, usecols=use, dtype={"station_id": str}, chunksize=250000):
        rows += len(chunk)
        chunk.snapshot_time = pd.to_datetime(chunk.snapshot_time, utc=True)
        if not (chunk.snapshot_time.ge(start) & chunk.snapshot_time.lt(end)).all():
            raise ValueError("Input outside fixed interval")
        all_times.update(chunk.snapshot_time.unique())
        train = chunk[chunk.snapshot_time.lt(train_end)]
        train_times.update(train.snapshot_time.unique())
        ok = train.is_active.eq(1) & train.capacity.gt(0) & train[FEATURES[:5]].notna().all(axis=1)
        for key, val in train.loc[ok].groupby("station_id").size().items():
            counts[key] = counts.get(key, 0) + int(val)
        for row in train.loc[ok].drop_duplicates("station_id").itertuples():
            first.setdefault(row.station_id, {"station_id": row.station_id, "station_name": row.station_name,
                                             "latitude": row.latitude, "longitude": row.longitude})
    eligible = sorted(s for s, count in counts.items()
                      if count / len(train_times) >= cfg["minimum_train_active_fraction"])
    if len(eligible) < cfg["station_count"]:
        raise ValueError("Insufficient training-eligible stations")
    cohort = [eligible[i] for i in np.linspace(0, len(eligible) - 1, cfg["station_count"]).astype(int)]
    chunks = []
    for chunk in pd.read_csv(source, usecols=use, dtype={"station_id": str}, chunksize=250000):
        chunks.append(chunk[chunk.station_id.isin(cohort)].copy())
    data = pd.concat(chunks, ignore_index=True)
    data.snapshot_time = pd.to_datetime(data.snapshot_time, utc=True)
    if data.duplicated(["station_id", "snapshot_time"]).any():
        raise ValueError("Duplicate selected station/time keys")
    slots = {t: i for i, t in enumerate(sorted(all_times))}
    data["slot"] = data.snapshot_time.map(slots)
    pieces = []
    for index, sid in enumerate(cohort):
        part = station_sequences(data[data.station_id.eq(sid)], cfg)
        part["station"] = np.full(len(part["y"]), index, dtype=np.int16)
        pieces.append(part)
    arrays = {key: np.concatenate([p[key] for p in pieces]) for key in pieces[0]}
    train_mask = (arrays["split"] == 0) & (arrays["slot"] % cfg["training_stride"] == 0)
    arrays["train_mask"] = train_mask
    CACHE.parent.mkdir(parents=True, exist_ok=True)
    np.savez_compressed(CACHE, **arrays)
    manifest = {"study_type": cfg["study_type"], "input": str(source), "input_sha256": sha256(source),
                "input_rows": rows, "input_snapshots": len(all_times), "cohort_raw_rows": len(data),
                "training_eligible_station_count": len(eligible), "stations": [first[s] for s in cohort],
                "features": FEATURES, "config_sha256": sha256(CONFIG), "cache": str(CACHE),
                "cache_sha256": sha256(CACHE), "sampled_training_rows": int(train_mask.sum()),
                "split_rows": {name: int((arrays["split"] == i).sum()) for i, name in enumerate(["train", "validation", "retrospective"])},
                "window": {k: cfg[k] for k in ["window_start", "train_end", "validation_end", "test_end"]},
                "environment": runtime, "known_prior_exposure": "Stage 17 and Stage 19 results already inspected; not independent validation"}
    write_json(OUT / "data_manifest.json", manifest)
    print(json.dumps({k: v for k, v in manifest.items() if k not in ("stations", "environment")}, indent=2), flush=True)


def environment():
    from importlib.metadata import version
    hardware = {"processor": platform.processor(), "logical_cpu_count": os.cpu_count()}
    if platform.system() == "Darwin":
        for key, sysctl_name in [("chip", "machdep.cpu.brand_string"), ("memory_bytes", "hw.memsize")]:
            try:
                hardware[key] = subprocess.check_output(["sysctl", "-n", sysctl_name], text=True,
                                                        stderr=subprocess.DEVNULL).strip()
            except (OSError, subprocess.CalledProcessError):
                hardware[key] = "unavailable in this execution context"
    return {"python": platform.python_version(), "platform": platform.platform(),
            "machine": platform.machine(), "hardware_observed": hardware,
            "versions": {k: version(k) for k in ["numpy", "pandas", "scipy", "scikit-learn", "joblib", "torch"]}}


def load_prepared():
    manifest = json.loads((OUT / "data_manifest.json").read_text())
    if sha256(CONFIG) != manifest["config_sha256"] or sha256(CACHE) != manifest["cache_sha256"]:
        raise ValueError("Prepared data/config checksum mismatch")
    return dict(np.load(CACHE)), manifest


def torch_setup(seed, threads):
    import torch
    torch.set_num_threads(threads)
    torch.manual_seed(seed)
    torch.use_deterministic_algorithms(True)
    return torch


def make_lstm(hidden):
    import torch

    class InventoryLSTM(torch.nn.Module):
        def __init__(self):
            super().__init__()
            self.lstm = torch.nn.LSTM(len(FEATURES), hidden, batch_first=True)
            self.head = torch.nn.Linear(hidden, 1)

        def forward(self, x):
            values, _ = self.lstm(x)
            return self.head(values[:, -1]).squeeze(-1)

    return InventoryLSTM()


def lstm_predict(model, x, current, capacity, scale):
    import torch
    model.eval()
    output = []
    with torch.no_grad():
        for i in range(0, len(x), 4096):
            output.append(model(torch.from_numpy(x[i:i + 4096])).numpy())
    return np.clip(current + np.concatenate(output) * scale, 0, capacity)


def fit_lstm(x, y_delta, val_x, val_y, val_current, val_capacity, scale, candidate, seed, cfg):
    torch = torch_setup(seed, cfg["cpu_threads"])
    model = make_lstm(candidate["hidden_size"])
    optimizer = torch.optim.Adam(model.parameters(), lr=candidate["learning_rate"])
    criterion = torch.nn.MSELoss()
    tx, ty = torch.from_numpy(x), torch.from_numpy((y_delta / scale).astype("float32"))
    best, best_state, best_epoch, stale = float("inf"), None, 0, 0
    start, history = time.perf_counter(), []
    stop = "epoch_limit"
    for epoch in range(cfg["max_epochs"]):
        model.train()
        order = torch.randperm(len(tx))
        for batch in order.split(cfg["batch_size"]):
            optimizer.zero_grad()
            loss = criterion(model(tx[batch]), ty[batch])
            if not torch.isfinite(loss):
                raise ValueError("Nonfinite LSTM loss")
            loss.backward()
            torch.nn.utils.clip_grad_norm_(model.parameters(), 5.0)
            optimizer.step()
        pred = lstm_predict(model, val_x, val_current, val_capacity, scale)
        error = float(mean_absolute_error(val_y, pred))
        history.append({"epoch": epoch + 1, "validation_mae": error})
        if error < best - cfg["minimum_validation_improvement"]:
            best, best_state, best_epoch, stale = error, copy.deepcopy(model.state_dict()), epoch + 1, 0
        else:
            stale += 1
        if time.perf_counter() - start >= cfg["max_fit_seconds"]:
            stop = "time_limit_after_epoch"
            break
        if stale >= cfg["patience"]:
            stop = "validation_patience"
            break
    model.load_state_dict(best_state)
    return model, {"candidate": candidate["name"], "seed": seed, "best_epoch": best_epoch,
                   "epochs": len(history), "training_seconds": time.perf_counter() - start,
                   "validation_mae": best, "stop": stop, "history": history}


def development_arrays(arrays):
    train, val = arrays["train_mask"], arrays["split"] == 1
    scaler = StandardScaler().fit(arrays["x"][train].reshape(-1, len(FEATURES)))
    def transform(mask):
        raw = arrays["x"][mask]
        return scaler.transform(raw.reshape(-1, len(FEATURES))).reshape(raw.shape).astype("float32")
    scale = max(float(np.std(arrays["y"][train] - arrays["x"][train, -1, 0])), 1.0)
    return train, val, scaler, scale, transform(train), transform(val)


def pilot():
    cfg = config()
    arrays, _ = load_prepared()
    train, val, scaler, scale, tx, vx = development_arrays(arrays)
    trial = dict(cfg, max_epochs=1)
    _, record = fit_lstm(tx[:4096], (arrays["y"][train] - arrays["x"][train, -1, 0])[:4096],
                        vx[:2048], arrays["y"][val][:2048], arrays["x"][val, -1, 0][:2048],
                        arrays["x"][val, -1, 2][:2048], scale, cfg["candidates"][0], cfg["seeds"][0], trial)
    record.update({"pilot_only": True, "training_rows": min(4096, len(tx)),
                   "estimated_full_epoch_seconds": record["training_seconds"] * len(tx) / min(4096, len(tx)),
                   "formal_fit_budget_seconds": cfg["max_fit_seconds"], "formal_total_budget_seconds": cfg["max_total_training_seconds"]})
    write_json(OUT / "pilot.json", record)
    print(json.dumps(record, indent=2), flush=True)


def train():
    import torch
    cfg = config()
    if not (OUT / "pilot.json").exists():
        raise ValueError("Run and review the bounded pilot before formal training")
    if (MODELS / "selection.json").exists():
        raise FileExistsError("Formal model selection already exists; no automatic re-tuning")
    arrays, manifest = load_prepared()
    tm, vm, scaler, scale, tx, vx = development_arrays(arrays)
    MODELS.mkdir(parents=True, exist_ok=True)
    joblib.dump(scaler, MODELS / "scaler.joblib")
    y, current, cap = arrays["y"][vm], arrays["x"][vm, -1, 0], arrays["x"][vm, -1, 2]
    start = time.perf_counter()
    hgb = HistGradientBoostingRegressor(**cfg["hgb"], early_stopping=False)
    hgb.fit(tx.reshape(len(tx), -1), arrays["y"][tm] - arrays["x"][tm, -1, 0])
    hgb_seconds = time.perf_counter() - start
    joblib.dump(hgb, MODELS / "hgb.joblib")
    records, candidate_means, ensembles = [], {}, {}
    total_start = time.perf_counter()
    for candidate in cfg["candidates"]:
        predictions = []
        for seed in cfg["seeds"]:
            if time.perf_counter() - total_start > cfg["max_total_training_seconds"]:
                raise RuntimeError("Formal budget exhausted before all pre-specified fits; do not evaluate")
            model, record = fit_lstm(tx, arrays["y"][tm] - arrays["x"][tm, -1, 0], vx, y,
                                     current, cap, scale, candidate, seed, cfg)
            record["artifact"] = str(MODELS / f"{candidate['name']}_seed{seed}.pt")
            torch.save(model.state_dict(), record["artifact"])
            records.append(record)
            predictions.append(lstm_predict(model, vx, current, cap, scale))
            print(json.dumps({k: v for k, v in record.items() if k != "history"}), flush=True)
        candidate_means[candidate["name"]] = float(np.mean([r["validation_mae"] for r in records if r["candidate"] == candidate["name"]]))
        ensembles[candidate["name"]] = np.mean(predictions, axis=0)
    selected = min(cfg["candidates"], key=lambda c: candidate_means[c["name"]])
    val_predictions = {"persistence": current,
                       "hgb": np.clip(current + hgb.predict(vx.reshape(len(vx), -1)), 0, cap),
                       "lstm_ensemble": ensembles[selected["name"]]}
    val_metrics = {name: metrics(y, p) for name, p in val_predictions.items()}
    forecaster = min(val_metrics, key=lambda name: val_metrics[name]["mae"])
    selection = {"selected_candidate": selected, "seeds": cfg["seeds"], "target_scale": scale,
                 "candidate_mean_validation_mae": candidate_means, "validation_metrics": val_metrics,
                 "simulation_forecaster": forecaster, "config_sha256": sha256(CONFIG),
                 "data_manifest_sha256": sha256(OUT / "data_manifest.json"),
                 "hgb_training_seconds": hgb_seconds, "fits": records,
                 "selection_locked_before_retrospective_evaluation": True, "environment": environment()}
    selection["artifacts"] = {str(p): sha256(p) for p in sorted(MODELS.iterdir()) if p.is_file()}
    write_json(MODELS / "selection.json", selection)
    write_json(OUT / "development_results.json", selection)
    print("Model selection locked:", selected["name"], "; simulation forecaster:", forecaster, flush=True)


def load_selection():
    selection = json.loads((MODELS / "selection.json").read_text())
    if sha256(CONFIG) != selection["config_sha256"] or sha256(OUT / "data_manifest.json") != selection["data_manifest_sha256"]:
        raise ValueError("Selection/config/data manifest checksum mismatch")
    for path, expected in selection["artifacts"].items():
        if sha256(path) != expected:
            raise ValueError(f"Model checksum mismatch: {path}")
    return selection


def predict_sequences(raw, selection):
    """Inference on raw finite (N,13,9) past-only windows; no labels needed."""
    import torch
    cfg = config()
    if raw.ndim != 3 or raw.shape[1:] != (cfg["sequence_length"], len(FEATURES)) or not np.isfinite(raw).all():
        raise ValueError("Expected finite [N,13,9] sequence input")
    torch_setup(cfg["seeds"][0], cfg["cpu_threads"])
    scaler = joblib.load(MODELS / "scaler.joblib")
    x = scaler.transform(raw.reshape(-1, len(FEATURES))).reshape(raw.shape).astype("float32")
    current, cap = raw[:, -1, 0], raw[:, -1, 2]
    predictions, costs = {}, {}
    start = time.perf_counter()
    predictions["persistence"] = current.copy()
    costs["persistence"] = time.perf_counter() - start
    model = joblib.load(MODELS / "hgb.joblib")
    start = time.perf_counter()
    predictions["hgb"] = np.clip(current + model.predict(x.reshape(len(x), -1)), 0, cap)
    costs["hgb"] = time.perf_counter() - start
    candidate = selection["selected_candidate"]
    for seed in selection["seeds"]:
        model = make_lstm(candidate["hidden_size"])
        model.load_state_dict(torch.load(MODELS / f"{candidate['name']}_seed{seed}.pt", map_location="cpu", weights_only=True))
        start = time.perf_counter()
        predictions[f"lstm_seed{seed}"] = lstm_predict(model, x, current, cap, selection["target_scale"])
        costs[f"lstm_seed{seed}"] = time.perf_counter() - start
    predictions["lstm_ensemble"] = np.mean([predictions[f"lstm_seed{s}"] for s in selection["seeds"]], axis=0)
    costs["lstm_ensemble"] = sum(costs[f"lstm_seed{s}"] for s in selection["seeds"])
    return predictions, costs


def evaluate():
    if (OUT / "comparison.csv").exists():
        raise FileExistsError("Retrospective results already exist; no automatic re-evaluation")
    arrays, manifest = load_prepared()
    selection = load_selection()
    mask = arrays["split"] == 2
    raw, y = arrays["x"][mask], arrays["y"][mask]
    predictions, costs = predict_sequences(raw, selection)
    ids = np.array([s["station_id"] for s in manifest["stations"]])
    frame = pd.DataFrame({"station_id": ids[arrays["station"][mask]],
                          "snapshot_time": pd.to_datetime(arrays["time"][mask], utc=True),
                          "target_time": pd.to_datetime(arrays["target_time"][mask], utc=True),
                          "actual": y, "current_bikes": raw[:, -1, 0], "capacity": raw[:, -1, 2]})
    rows, station_rows, hour_rows = [], [], []
    keys = frame[["station_id", "snapshot_time", "target_time"]].to_csv(index=False).encode()
    for name, prediction in predictions.items():
        frame[name] = prediction
        training_seconds = 0.0
        if name == "hgb":
            training_seconds = selection["hgb_training_seconds"]
        elif name.startswith("lstm"):
            fits = [r for r in selection["fits"] if r["candidate"] == selection["selected_candidate"]["name"]]
            if name != "lstm_ensemble":
                fits = [r for r in fits if name == f"lstm_seed{r['seed']}"]
            training_seconds = sum(r["training_seconds"] for r in fits)
        rows.append({"model": name, "rows": len(y), **metrics(y, prediction),
                     "training_seconds": training_seconds, "inference_seconds": costs[name],
                     "sample_keys_sha256": hashlib.sha256(keys).hexdigest()})
        errors = pd.DataFrame({"station_id": frame.station_id, "hour": frame.snapshot_time.dt.tz_convert("Asia/Taipei").dt.hour,
                               "ae": np.abs(y - prediction)})
        for key, dest in [("station_id", station_rows), ("hour", hour_rows)]:
            for group, records in errors.groupby(key):
                dest.append({"model": name, key: group, "rows": len(records), "mae": float(records.ae.mean())})
    pd.DataFrame(rows).to_csv(OUT / "comparison.csv", index=False)
    pd.DataFrame(station_rows).to_csv(OUT / "station_errors.csv", index=False)
    pd.DataFrame(hour_rows).to_csv(OUT / "hour_errors.csv", index=False)
    frame.to_csv(PREDICTIONS, index=False)
    seed_mae = [r["mae"] for r in rows if r["model"].startswith("lstm_seed")]
    write_json(OUT / "evaluation.json", {"scope": "retrospective, previously inspected fixed dataset",
               "selection_sha256": sha256(MODELS / "selection.json"), "rows": len(y),
               "sample_keys_sha256": hashlib.sha256(keys).hexdigest(), "station_count": int(frame.station_id.nunique()),
               "seed_mae_mean": float(np.mean(seed_mae)), "seed_mae_std_population": float(np.std(seed_mae)),
               "selected_on_validation": selection["simulation_forecaster"],
               "prediction_file_sha256": sha256(PREDICTIONS),
               "inference_cost_scope": "predict calls on CPU, excluding artifact load/scaling; ensemble is sum of seed calls",
               "all_candidate_training_seconds": sum(r["training_seconds"] for r in selection["fits"])})
    print(pd.DataFrame(rows).drop(columns="sample_keys_sha256").to_string(index=False), flush=True)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command", choices=["prepare", "pilot", "train", "evaluate", "predict"])
    parser.add_argument("--input-npy", type=Path)
    parser.add_argument("--run-dir", type=Path, help="Isolated reproduction directory; leave omitted to inspect saved models")
    parser.add_argument("--output", type=Path, default=Path("/tmp/youbike-offline-predictions.csv"))
    args = parser.parse_args()
    if args.run_dir:
        use_run_directory(args.run_dir)
    if args.command == "predict":
        if args.input_npy is None:
            parser.error("predict requires --input-npy containing raw [N,13,9] arrays")
        predictions, _ = predict_sequences(np.load(args.input_npy, allow_pickle=False), load_selection())
        pd.DataFrame(predictions).to_csv(args.output, index=False)
    else:
        globals()[args.command]()


if __name__ == "__main__":
    main()
