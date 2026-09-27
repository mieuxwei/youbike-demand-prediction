"""Convert the verified Stage 17 trees (no fit) and save historical parity fixtures."""
import hashlib
import json
from pathlib import Path

import joblib
import numpy as np
import pandas as pd
import sklearn

from train_track_b_regression import build_track_b_features, feature_columns, load_config

ROOT = Path(__file__).resolve().parents[1]
SHA = "d4bc2df1c815a7c722e900891b668d3b2a7124f66966913081cb957b5ec7e6f6"


def main():
    artifact = ROOT / "models/track_b_60m_regression.joblib"
    assert hashlib.sha256(artifact.read_bytes()).hexdigest() == SHA
    for path, expected in {
        "models/track_b_60m_regression.metadata.json": "b583107f9416cf161e3d937c3b09f1b20e433f6579c62651c5e2cf09068cf356",
        "config/track_b_regression.json": "6a1fb0ace9044086973ba8bd5aad44b42df9dbfd208b79e8026f185d3ae7289f",
    }.items():
        assert hashlib.sha256((ROOT / path).read_bytes()).hexdigest() == expected
    meta = json.loads((ROOT / "models/track_b_60m_regression.metadata.json").read_text())
    assert sklearn.__version__ == meta["library_versions"]["scikit_learn"]
    model = joblib.load(artifact)
    assert model.is_categorical_ is None and model.n_features_in_ == 23
    forest = []
    for predictors in model._predictors:
        assert len(predictors) == 1
        nodes = predictors[0].nodes
        assert not nodes["is_categorical"].any()
        forest.append([[int(n["feature_idx"]), float(n["num_threshold"]),
                        int(n["missing_go_to_left"]), int(n["left"]), int(n["right"]),
                        float(n["value"]), int(n["is_leaf"])] for n in nodes])
    optimization = json.loads((ROOT / "results/offline_research/optimization.json").read_text())
    stations = [{k: s[k] for k in ("station_id", "station_name", "latitude", "longitude")}
                for s in optimization["scenarios"][0]["stations"]]
    assert [s["station_id"] for s in stations] == optimization["station_ids"]
    output = {"format_version": 1, "artifact_sha256": SHA,
              "feature_columns": meta["feature_columns"], "stations": stations,
              "baseline": float(model._baseline_prediction[0, 0]), "trees": forest}
    dest = ROOT / "cloudflare/track-b-collector/src/live-model.json"
    dest.write_text(json.dumps(output, ensure_ascii=False, separators=(",", ":")) + "\n")

    requests = pd.to_datetime(["2026-09-19 03:30", "2026-09-19 07:00", "2026-09-19 12:00",
                              "2026-09-19 17:00", "2026-09-19 23:55", "2026-09-20 00:00"]).tz_localize("Asia/Taipei").tz_convert("UTC")
    chunks = []
    for chunk in pd.read_csv(ROOT / "data/processed/track_b_independent_7d.csv", chunksize=250_000,
                             dtype={"station_id": str}):
        chunk = chunk[chunk.station_id.isin(optimization["station_ids"])].copy()
        chunk["snapshot_time"] = pd.to_datetime(chunk.snapshot_time, utc=True)
        chunk = chunk[(chunk.snapshot_time >= requests.min() - pd.Timedelta(minutes=65)) &
                      (chunk.snapshot_time <= requests.max() + pd.Timedelta(minutes=6))]
        chunks.append(chunk)
    raw = pd.concat(chunks).sort_values(["station_id", "snapshot_time"]).reset_index(drop=True)
    data = raw.copy()
    for col in ["available_bikes", "available_return_bikes", "capacity"]:
        data[col] = data[col].astype("int16")
    for col in ["latitude", "longitude"]:
        data[col] = data[col].astype("float32")
    data["is_active"] = data.is_active.astype(bool)
    config = load_config(ROOT / "config/track_b_regression.json")
    features = build_track_b_features(data, config)
    columns = feature_columns(config)
    assert columns == meta["feature_columns"]
    fixtures = []
    for station_id in optimization["station_ids"]:
        for request in requests:
            matched = raw[(raw.station_id == station_id) & (raw.snapshot_time >= request) &
                          (raw.snapshot_time <= request + pd.Timedelta(minutes=6))]
            if matched.empty:
                raise ValueError(f"Missing predetermined origin {station_id} {request}")
            origin = matched.iloc[0]
            history = raw[(raw.station_id == station_id) & (raw.snapshot_time <= origin.snapshot_time) &
                          (raw.snapshot_time >= origin.snapshot_time - pd.Timedelta(minutes=65))].copy()
            history["snapshot_time"] = history.snapshot_time.map(lambda t: t.isoformat().replace("+00:00", "Z"))
            row = features.loc[[origin.name], columns]
            assert np.isfinite(row.to_numpy(dtype=float)).all()
            pred = float(model.predict(row)[0])
            fixtures.append({"station_id": station_id, "history": history.to_dict(orient="records"),
                             "features": row.iloc[0].tolist(), "raw_prediction": pred,
                             "prediction": float(np.clip(pred, 0, origin.capacity))})
    fixture = {"purpose": "Historical serving parity only; not new evaluation", "model_sha256": SHA,
               "source": "existing track_b_independent_7d.csv", "cases": fixtures}
    path = ROOT / "cloudflare/track-b-collector/test/live-parity.json"
    path.write_text(json.dumps(fixture, ensure_ascii=False, separators=(",", ":")) + "\n")
    print(json.dumps({"trees": len(forest), "features": len(columns), "cases": len(fixtures),
                      "model_export_sha256": hashlib.sha256(dest.read_bytes()).hexdigest()}))


if __name__ == "__main__":
    main()
