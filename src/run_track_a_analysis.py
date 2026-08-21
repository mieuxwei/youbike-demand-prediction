"""Run fixed-parameter HGB feature ablation and complete Track A error analysis."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

import numpy as np
import pandas as pd

try:
    from .baseline_model import (
        build_hourly_model_dataset,
        load_hourly_weather,
        load_model_config,
        load_station_hour_demand,
        select_top_training_stations,
        split_by_time,
    )
    from .track_a_analysis import (
        ablation_metric_row,
        add_error_contexts,
        add_official_calendar_features,
        assign_station_demand_tiers,
        build_ablation_pipeline,
        build_feature_variants,
        load_analysis_config,
        summarize_errors,
    )
    from .tree_model import load_tree_config
except ImportError:
    from baseline_model import (
        build_hourly_model_dataset,
        load_hourly_weather,
        load_model_config,
        load_station_hour_demand,
        select_top_training_stations,
        split_by_time,
    )
    from track_a_analysis import (
        ablation_metric_row,
        add_error_contexts,
        add_official_calendar_features,
        assign_station_demand_tiers,
        build_ablation_pipeline,
        build_feature_variants,
        load_analysis_config,
        summarize_errors,
    )
    from tree_model import load_tree_config


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--baseline-config", type=Path, default=Path("config/baseline_model.json")
    )
    parser.add_argument(
        "--tree-config", type=Path, default=Path("config/tree_model.json")
    )
    parser.add_argument(
        "--analysis-config", type=Path, default=Path("config/track_a_analysis.json")
    )
    parser.add_argument(
        "--demand-input",
        type=Path,
        default=Path("data/processed/historical_station_hour_demand.csv"),
    )
    parser.add_argument(
        "--weather-input",
        type=Path,
        default=Path("data/processed/taipei_weather_hourly.csv"),
    )
    parser.add_argument("--results-dir", type=Path, default=Path("results"))
    return parser.parse_args()


def local_timestamp(value: str) -> pd.Timestamp:
    return pd.Timestamp(value).tz_convert("Asia/Taipei")


def select_candidate(tree_config: dict, candidate_name: str) -> dict:
    matches = [
        candidate
        for candidate in tree_config["candidates"]
        if candidate["candidate"] == candidate_name
    ]
    if len(matches) != 1:
        raise ValueError(f"Expected one tree candidate named {candidate_name!r}.")
    return matches[0]


def main() -> None:
    args = parse_args()
    baseline_config = load_model_config(args.baseline_config)
    tree_config = load_tree_config(args.tree_config)
    analysis_config = load_analysis_config(args.analysis_config)
    candidate = select_candidate(tree_config, analysis_config["model_candidate"])
    target = baseline_config.get("target", "borrow_count")
    train_end = local_timestamp(baseline_config["train_end"])
    validation_end = local_timestamp(baseline_config["validation_end"])
    test_end = local_timestamp(baseline_config["test_end"])

    demand = load_station_hour_demand(args.demand_input)
    weather = load_hourly_weather(args.weather_input)
    stations = select_top_training_stations(
        demand, train_end, baseline_config["top_station_count"]
    )
    model_data = build_hourly_model_dataset(demand, weather, stations)
    model_data = add_official_calendar_features(
        model_data, analysis_config["official_calendar"]
    )
    splits = split_by_time(model_data, train_end, validation_end, test_end)
    train_validation = pd.concat(
        [splits["train"], splits["validation"]], ignore_index=True
    )

    variants = build_feature_variants(analysis_config)
    metric_rows: list[dict] = []
    full_test_prediction: np.ndarray | None = None
    for variant, columns in variants.items():
        validation_model = build_ablation_pipeline(
            columns,
            candidate,
            loss=tree_config["loss"],
            random_state=tree_config["random_state"],
        )
        validation_model.fit(splits["train"][columns], splits["train"][target])
        validation_prediction = np.maximum(
            validation_model.predict(splits["validation"][columns]), 0
        )
        metric_rows.append(
            ablation_metric_row(
                variant,
                "validation",
                splits["validation"][target],
                validation_prediction,
                columns,
            )
        )

        test_model = build_ablation_pipeline(
            columns,
            candidate,
            loss=tree_config["loss"],
            random_state=tree_config["random_state"],
        )
        test_model.fit(train_validation[columns], train_validation[target])
        test_prediction = np.maximum(test_model.predict(splits["test"][columns]), 0)
        metric_rows.append(
            ablation_metric_row(
                variant,
                "test",
                splits["test"][target],
                test_prediction,
                columns,
            )
        )
        if variant == "full":
            full_test_prediction = test_prediction

    assert full_test_prediction is not None
    ablation_metrics = pd.DataFrame(metric_rows)
    full_metrics = ablation_metrics.loc[
        ablation_metrics["variant"].eq("full"),
        ["split", "mae", "rmse", "r2"],
    ].rename(
        columns={
            "mae": "full_mae",
            "rmse": "full_rmse",
            "r2": "full_r2",
        }
    )
    ablation_metrics = ablation_metrics.merge(
        full_metrics, how="left", on="split", validate="many_to_one"
    )
    ablation_metrics["mae_delta_vs_full"] = (
        ablation_metrics["mae"] - ablation_metrics["full_mae"]
    )
    ablation_metrics["mae_percent_change_vs_full"] = (
        ablation_metrics["mae_delta_vs_full"] / ablation_metrics["full_mae"] * 100
    )
    ablation_metrics["rmse_delta_vs_full"] = (
        ablation_metrics["rmse"] - ablation_metrics["full_rmse"]
    )
    ablation_metrics["r2_delta_vs_full"] = (
        ablation_metrics["r2"] - ablation_metrics["full_r2"]
    )

    test = splits["test"].copy()
    test["prediction"] = full_test_prediction
    test["signed_error"] = test[target] - test["prediction"]
    test["absolute_error"] = test["signed_error"].abs()
    test, station_tiers = assign_station_demand_tiers(
        splits["train"], test, target
    )
    test, context_thresholds = add_error_contexts(
        splits["train"], test, target, analysis_config["peak_periods"]
    )
    context_columns = [
        "station_demand_tier",
        "hour",
        "weekday",
        "peak_period",
        "official_day_type",
        "rain_intensity",
        "temperature_band",
        "actual_demand_band",
    ]
    context_errors = summarize_errors(test, target, context_columns)
    station_errors = summarize_errors(test, target, ["station_name"]).drop(
        columns="context"
    )
    station_errors = station_errors.rename(columns={"segment": "station_name"})
    station_errors = station_errors.merge(
        station_tiers, how="left", on="station_name", validate="one_to_one"
    ).sort_values("mae", ascending=False)

    test["date"] = test["event_time"].dt.tz_convert("Asia/Taipei").dt.strftime(
        "%Y-%m-%d"
    )
    daily_errors = summarize_errors(test, target, ["date"]).drop(columns="context")
    daily_errors = daily_errors.rename(columns={"segment": "date"}).sort_values(
        "date"
    )
    worst_cases = test.nlargest(
        int(analysis_config["worst_case_rows"]), "absolute_error"
    )[
        [
            "event_time",
            "station_name",
            target,
            "prediction",
            "signed_error",
            "absolute_error",
            "station_demand_tier",
            "peak_period",
            "official_day_type",
            "rain_intensity",
            "temperature_band",
            "precipitation_mm",
            "temperature_c",
        ]
    ]

    test_summary = ablation_metrics.loc[
        ablation_metrics["split"].eq("test")
    ].sort_values("mae")
    summary = {
        "target": target,
        "target_scope": "hourly transfer-related borrowing demand",
        "station_count": len(stations),
        "train_rows": len(splits["train"]),
        "validation_rows": len(splits["validation"]),
        "test_rows": len(splits["test"]),
        "candidate": candidate,
        "selection_rule": "Fixed previously selected HGB candidate; ablations do not tune on test.",
        "official_calendar": analysis_config["official_calendar"],
        "context_thresholds_derived_from_training_only": context_thresholds,
        "full_test_metrics": test_summary.loc[
            test_summary["variant"].eq("full"), ["mae", "rmse", "r2"]
        ].iloc[0].to_dict(),
        "lowest_test_mae_variant_for_analysis_only": test_summary.iloc[0][
            "variant"
        ],
        "limitations": [
            "Ablation holdout differences describe feature dependence; they are not causal effects.",
            "The DGPA calendar represents government administrative offices, not every employer or school.",
            "Weather uses historical reanalysis; live forecasting would require contemporaneously available forecasts.",
            "Event and transit-disruption data are unavailable, so worst-case causes are not inferred.",
        ],
    }

    args.results_dir.mkdir(parents=True, exist_ok=True)
    ablation_metrics.to_csv(
        args.results_dir / "track_a_ablation_metrics.csv", index=False
    )
    test_summary.to_csv(
        args.results_dir / "track_a_ablation_test_summary.csv", index=False
    )
    context_errors.to_csv(
        args.results_dir / "track_a_error_by_context.csv", index=False
    )
    station_errors.to_csv(
        args.results_dir / "track_a_station_errors_complete.csv", index=False
    )
    daily_errors.to_csv(
        args.results_dir / "track_a_daily_errors.csv", index=False
    )
    worst_cases.to_csv(args.results_dir / "track_a_worst_cases.csv", index=False)
    (args.results_dir / "track_a_analysis_summary.json").write_text(
        json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    full = summary["full_test_metrics"]
    print(
        f"Full HGB test: MAE={full['mae']:.3f}, "
        f"RMSE={full['rmse']:.3f}, R2={full['r2']:.3f}"
    )
    print(f"Ablation variants completed: {len(variants)}")


if __name__ == "__main__":
    main()
