# Research and demonstration evidence

[Project](../README.md) · [中文總覽](PROJECT_OVERVIEW_STATUS_AND_TECHNOLOGY.md) · [Public demo](https://youbike-demand-observatory.rwhqgqfdk2.chatgpt.site/#live) · [Reproduce](REPRODUCIBILITY.md)

Research and demonstration are complete; implementation is frozen. Current observations, future inventory estimates, historical borrowing forecasts and recorded simulations answer different questions. Stage reports retain the state and conclusions of their dated experiments, not a current backlog.

## Main evidence

| Question | Evidence |
|---|---|
| What did the historical demand models learn? | [Track A research summary](STAGE_13_TRACK_A_RESEARCH_SUMMARY.md), [model card](MODEL_CARD.md), [full metrics](../results/model_comparison_metrics.csv) |
| Do availability models beat persistence? | [28-day study](STAGE_17_TRACK_B_28_DAY_REGRESSION.md), [independent seven-day validation](STAGE_19_TRACK_B_INDEPENDENT_VALIDATION.md), [independent metrics](../results/track_b_independent_metrics.csv) |
| Was LSTM useful? Did MILP beat greedy? | [Phase 3–4 methods and results](PHASE_3_4_OFFLINE_RESEARCH.md), [protocol](OFFLINE_RESEARCH_PROTOCOL.md), [offline model card](TRACK_B_OFFLINE_MODEL_CARD.md) |
| What is actually live? | [Dashboard guide](../dashboard/README.md), [serving contract](LIVE_DEMO_PROTOCOL.md), [screenshot provenance](assets/README.md) |
| Which exact version was accepted and deployed? | [September 27 live delivery record](LIVE_DEMO_DELIVERY.md), [original research acceptance at its preservation commit](https://github.com/mieuxwei/youbike-demand-prediction/blob/159f059d0e9ff4afcdbf9ad206d1b426aa1339aa/docs/RESEARCH_FREEZE.md) |
| How is the current source checked after documentation cleanup? | [Additive documentation revision](DOCUMENTATION_REVISION.md), [reproducibility guide](REPRODUCIBILITY.md) |

## Original phases and completed work

| Phase | Delivered work |
|---|---|
| 1 — Data Analysis | Historical transfers, weather, live station collection, cleaning, EDA and time-series audits |
| 2 — Machine Learning | Track A baselines/Ridge/HGB/XGBoost, ablation and errors; Track B persistence/HGB and independent validation |
| 3 — Deep Learning | Fixed-data, common-scope LSTM comparison; not adopted |
| 4 — Optimization | Static integer redistribution, greedy/no-transfer baselines, constraints and sensitivity |
| 5 — Visualization | React/Vinext historical holdout, live 12-station availability and recorded simulation |

The original phase names are traceable to `4742f10:PROJECT_PLAN.md` in Git history. This mapping preserves their technical meaning without duplicating an internal work plan. Risk classification and real fleet operations are not delivered capabilities.

## Track A: data, features and experiments

| Topic | Report |
|---|---|
| Snapshot cleaning and validation foundations | [Data pipeline](STAGE_2_DATA_PIPELINE.md) |
| Time-series feature foundations | [History and features](STAGE_3_HISTORY_AND_FEATURES.md) |
| Official transfer-related trips and station-hour aggregation | [Historical demand](STAGE_4_HISTORICAL_DEMAND.md) |
| Full-year source audit and weather | [Full-year integration](STAGE_5_FULL_YEAR_WEATHER.md) |
| Naive and linear comparisons | [Baseline models](STAGE_6_BASELINE_MODEL.md) |
| HGB and rolling-origin validation | [Tree-model comparison](STAGE_7_TREE_MODEL_COMPARISON.md) |
| Feature/schema checks and historical prediction | [Prediction interface](STAGE_8_PREDICTION_INTERFACE.md) |
| Original ten-timepoint holdout display | [Historical dashboard record](STAGE_9_HISTORICAL_DASHBOARD.md) |
| Challenger model | [XGBoost comparison](STAGE_10_XGBOOST_COMPARISON.md) |
| Feature contribution and contextual errors | [Ablation and error analysis](STAGE_12_FEATURE_ABLATION_ERROR_ANALYSIS.md) |
| Consolidated design and interpretation | [Track A summary](STAGE_13_TRACK_A_RESEARCH_SUMMARY.md) |

## Track B: infrastructure and dated research

| Topic / fixed scope | Report |
|---|---|
| Worker, D1 schema, retry, logging and protected export | [Cloud collection](STAGE_11_TRACK_B_CLOUD_COLLECTION.md), [collector operations](../cloudflare/track-b-collector/README.md) |
| August 28 cloud coverage checkpoint | [First audit](STAGE_14_TRACK_B_FIRST_COVERAGE_AUDIT.md) |
| August 21–28 preliminary persistence study | [Seven-day baseline](STAGE_15_TRACK_B_PRELIMINARY_BASELINE.md) |
| August 21–September 4, fixed fourteen days | [Persistence stability](STAGE_16_TRACK_B_14_DAY_STABILITY.md) |
| August 21–September 18, fixed twenty-eight days | [First learned regression](STAGE_17_TRACK_B_28_DAY_REGRESSION.md) |
| September 19 operational incident and repair | [Collector resilience](STAGE_18_TRACK_B_COLLECTOR_RESILIENCE.md) |
| September 18 18:30–September 25 18:30 UTC | [Independent validation](STAGE_19_TRACK_B_INDEPENDENT_VALIDATION.md) |
| Separate fixed-data retrospective study, executed September 27 | [LSTM and redistribution](PHASE_3_4_OFFLINE_RESEARCH.md) |

Exact timestamp boundaries, active-station rules and target purging are specified in each report. Early references to waiting for data or unimplemented models describe those historical checkpoints only. The completed live serving contract is separate from all offline evaluation scores.

## Freeze evidence

The original [research freeze](RESEARCH_FREEZE.md), [live delivery record](LIVE_DEMO_DELIVERY.md), both freeze manifests, Stage reports and numerical artifacts remain preserved. They contain dated execution context as evidence. Their old plan/handoff references are historical, not entry points to current instructions. The immutable research record is best read at the preservation-commit link above, where its original relative links resolve.

The [documentation revision](DOCUMENTATION_REVISION.md) identifies changed public documents and removed internal files without replacing an original manifest or changing a research conclusion.
