"""Build only the new static research panel, preserving the Track A bundle."""
import json
from pathlib import Path

import pandas as pd

try:
    from .offline_forecasting import OUT, MODELS, sha256, write_json
except ImportError:
    from offline_forecasting import OUT, MODELS, sha256, write_json


def build():
    data = json.loads((OUT / "data_manifest.json").read_text())
    selection = json.loads((MODELS / "selection.json").read_text())
    evaluation = json.loads((OUT / "evaluation.json").read_text())
    simulation = json.loads((OUT / "optimization.json").read_text())
    comparisons = pd.read_csv(OUT / "comparison.csv")
    primary = comparisons[comparisons.model.isin(["persistence", "hgb", "lstm_ensemble"])]
    legacy = pd.read_csv("results/track_b_independent_metrics.csv")
    legacy_summary = json.loads(Path("results/track_b_independent_summary.json").read_text())
    bundle = {"kind": "historical observations, retrospective forecasts, and simulated transfers; not live",
              "window": data["window"], "station_count": evaluation["station_count"], "rows": evaluation["rows"],
              "models": primary.to_dict(orient="records"),
              "seed_results": comparisons[comparisons.model.str.startswith("lstm_seed")].to_dict(orient="records"),
              "selection": {"candidate": selection["selected_candidate"]["name"],
                            "simulation_forecaster": selection["simulation_forecaster"],
                            "validation_metrics": selection["validation_metrics"]},
              "legacy_track_b": {"window": legacy_summary["window_utc"], "metrics": legacy.to_dict(orient="records")},
              "scenarios": simulation["scenarios"], "source_sha256": {
                  str(p): sha256(p) for p in [OUT / "comparison.csv", OUT / "optimization.json", OUT / "evaluation.json"]}}
    write_json("dashboard/app/offline-research-data.json", bundle)
    print("Built research panel:", len(bundle["models"]), "models,", len(bundle["scenarios"]), "scenarios")


if __name__ == "__main__":
    build()
