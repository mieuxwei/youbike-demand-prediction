# Reproducibility Guide

This guide collects the repository's supported local commands. The public README focuses on research questions, evidence, and current status; the Stage documents linked below explain the design and interpretation of each pipeline.

Large raw and processed datasets are intentionally excluded from Git. Commands that depend on those datasets require the corresponding source files or an authorized Track B export.

Research and public demonstration are complete and frozen. The [original research freeze](RESEARCH_FREEZE.md) and [published delivery record](LIVE_DEMO_DELIVERY.md) describe separate accepted versions. Later documentation changes are recorded in a [separate revision](DOCUMENTATION_REVISION.md), without replacing either original manifest. Use an isolated copy/directory for intentional reproductions; do not rerun old research as routine verification.

## Verify the current documentation revision

These standard-library checks need no datasets, model loading, cloud access or training:

```bash
python3 scripts/verify_publication.py
python3 -m unittest tests.test_publication_integrity -v
git diff --check
```

The verifier compares every original delivery file with the immutable September 27 manifest, allowing only the exact documentation changes/deletions recorded in the additive amendment. It also verifies new files, relative links and anchors. Original whole-delivery verifiers remain unchanged: they deliberately report later documentation edits as differences. For their exact original checkouts, see [version boundaries](DOCUMENTATION_REVISION.md#original-version-checks).

## Environment

From the repository root:

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements.txt
jupyter notebook
```

Run the Python validation suite:

```bash
python -m unittest discover -s tests -v
```

## Track A: historical transfer demand

### Prepare the 2023 data and weather

```bash
python src/download_historical.py --month all
python src/prepare_historical_collection.py
python src/download_weather.py
python src/prepare_weather.py
```

The pipeline processes the official monthly files, creates station-hour transfer-demand data, and joins 8,760 hourly weather records. See the [historical demand guide](STAGE_4_HISTORICAL_DEMAND.md) and [weather integration guide](STAGE_5_FULL_YEAR_WEATHER.md).

### Reproduce model comparisons and analysis

```bash
python src/train_baseline.py
python src/train_tree_models.py
python src/train_xgboost.py
python src/run_track_a_analysis.py
```

On macOS, XGBoost also requires OpenMP:

```bash
brew install libomp
```

The controlled experiment design and outputs are documented in the [baseline guide](STAGE_6_BASELINE_MODEL.md), [HGB comparison](STAGE_7_TREE_MODEL_COMPARISON.md), [XGBoost comparison](STAGE_10_XGBOOST_COMPARISON.md), and [ablation and error analysis](STAGE_12_FEATURE_ABLATION_ERROR_ANALYSIS.md).

### Run one historical prediction

```bash
python src/predict_hourly.py \
  --target-time 2023-12-31T18:00:00+08:00 \
  --include-actual \
  --output results/example_hourly_predictions.csv
```

`--include-actual` is a historical backtest option: actual values are attached only after prediction. Remove it for inference without backtest output. The bundled 2023 inputs do not support a current forecast. See the [prediction-interface guide](STAGE_8_PREDICTION_INTERFACE.md) and [model card](MODEL_CARD.md).

### Historical Dashboard

Rebuild the existing ten-timepoint static bundle only when the underlying research artifacts intentionally change:

```bash
python src/build_dashboard_data.py
```

Run and check the dashboard locally:

```bash
cd dashboard
pnpm install
pnpm run dev
pnpm run lint
pnpm test
```

The Track A section is a historical holdout demonstration, not live inventory. The current website separately includes live Track B observations/forecasts and recorded simulations. See the [original historical dashboard guide](STAGE_9_HISTORICAL_DASHBOARD.md) and [current dashboard README](../dashboard/README.md).

## Track B: station availability

### Local collector for testing and fallback

```bash
python src/collect_youbike.py
python src/collect_history.py --count 12 --interval-minutes 5
python src/prepare_data.py
python src/build_features.py
```

These commands require the computer and process to remain active. Formal long-running collection runs in Cloudflare Worker + Cron + D1. See the [snapshot pipeline guide](STAGE_2_DATA_PIPELINE.md), [feature guide](STAGE_3_HISTORY_AND_FEATURES.md), and [cloud collection guide](STAGE_11_TRACK_B_CLOUD_COLLECTION.md).

### Authorized cloud export

Never place the export token in Git or pass it as a command-line argument. On the configured macOS workstation:

```bash
export TRACK_B_EXPORT_URL="https://youbike-track-b-collector.mieuxander.workers.dev/export.csv"
export TRACK_B_EXPORT_TOKEN="$(security find-generic-password \
  -a "$USER" -s youbike-track-b-export -w)"
python src/export_track_b.py \
  --start 2026-08-21 \
  --end 2026-08-27 \
  --output data/processed/track_b_week_1.csv
unset TRACK_B_EXPORT_TOKEN
```

Add `--station-id <station_id>` to limit the export to one station. Date-only bounds are interpreted in Asia/Taipei; exported timestamps are UTC ISO-8601.

### Audit and historical baseline records

```bash
python src/audit_track_b.py \
  --input data/processed/track_b_week_1.csv

python src/track_b_baseline.py \
  --input data/processed/track_b_week_1.csv

python src/track_b_stability.py \
  --input data/processed/track_b_14_days.csv \
  --start 2026-08-21T09:45:02Z \
  --end 2026-09-04T09:45:02Z \
  --output-dir results
```

The seven-day audit and preliminary baseline plus fourteen-day stability analysis remain historical evidence. See the [first cloud audit](STAGE_14_TRACK_B_FIRST_COVERAGE_AUDIT.md), [seven-day preliminary baseline](STAGE_15_TRACK_B_PRELIMINARY_BASELINE.md), and [fourteen-day stability analysis](STAGE_16_TRACK_B_14_DAY_STABILITY.md).

### Fixed 28-day audit and first learned regression

Export the exact half-open analysis interval. The output is approximately 2 GiB and remains Git-ignored:

```bash
export TRACK_B_EXPORT_URL="https://youbike-track-b-collector.mieuxander.workers.dev/export.csv"
export TRACK_B_EXPORT_TOKEN="$(security find-generic-password \
  -a "$USER" -s youbike-track-b-export -w)"
python src/export_track_b.py \
  --start 2026-08-21T09:45:02Z \
  --end 2026-09-18T09:45:02Z \
  --output data/processed/track_b_28_days.csv
unset TRACK_B_EXPORT_TOKEN
```

Audit the exact file without overwriting earlier checkpoint results:

```bash
python src/audit_track_b.py \
  --input data/processed/track_b_28_days.csv \
  --summary-output results/track_b_28d_live_audit.json \
  --gaps-output results/track_b_28d_live_gaps.csv \
  --targets-output results/track_b_28d_target_coverage.csv
```

Train the two candidate HGB regressions per horizon and compare the validation-selected model with persistence on the fixed holdout:

```bash
python src/train_track_b_regression.py \
  --input data/processed/track_b_28_days.csv
```

The command uses the committed boundaries in `config/track_b_regression.json`, purges targets crossing a split boundary, and stores only compact metrics, error summaries, model artifacts, and metadata in Git. See the [Stage 17 report](STAGE_17_TRACK_B_28_DAY_REGRESSION.md).

### Pre-registered independent temporal validation

Stage 19 uses frozen Stage 17 artifacts and was executed on **2026-09-27**. Do not retrain or edit the validation config after inspecting the independent data. The window ended at `2026-09-26 02:30 Asia/Taipei`; reproduce the committed warm-up and evaluation range as follows:

Verify the frozen configuration without needing the future CSV:

```bash
python src/validate_track_b_temporal.py --check-only
```

```bash
export TRACK_B_EXPORT_URL="https://youbike-track-b-collector.mieuxander.workers.dev/export.csv"
export TRACK_B_EXPORT_TOKEN="$(security find-generic-password \
  -a "$USER" -s youbike-track-b-export -w)"
python src/export_track_b.py \
  --start 2026-09-18T17:30:00Z \
  --end 2026-09-25T18:30:00Z \
  --output data/processed/track_b_independent_7d.csv
unset TRACK_B_EXPORT_TOKEN
```

Run the frozen comparison:

```bash
python src/validate_track_b_temporal.py \
  --input data/processed/track_b_independent_7d.csv \
  --config config/track_b_temporal_validation.json \
  --output-dir results
```

The tool verifies model, metadata, and training-config hashes before loading, evaluates HGB and persistence on identical rows, applies the pre-registered data/model gates, and writes compact coverage, metric, station, hour, and decision outputs. See the [Stage 19 protocol](STAGE_19_TRACK_B_INDEPENDENT_VALIDATION.md).

The September 27 input SHA-256, runtime versions, exact counts, and dated cloud checkpoint are in [`results/track_b_independent_provenance.json`](../results/track_b_independent_provenance.json). Use `--output-dir /tmp/youbike-stage19-reproduction` to compare a repeat run without overwriting the committed results. Raw export files remain local and Git-ignored. The completed decision retains persistence at 30m and supports a modest HGB gain at 60m across the two evaluated windows; this is not a live-serving deployment.

## Cloud collector checks

From `cloudflare/track-b-collector/`:

```bash
pnpm test
```

Deployment, D1 migration, secret rotation, and production export procedures are intentionally kept in the [Track B cloud guide](STAGE_11_TRACK_B_CLOUD_COLLECTION.md). They require the project owner's Cloudflare authorization and are not part of routine local verification.

## Phase 3–4 fixed-data research

Run from the repository root. Install the separate research dependency set (Python 3.9+; recorded run used 3.9.6, Apple M4, CPU):

```bash
python -m pip install -r requirements-research.txt
python -m unittest discover -s tests -v
python3 scripts/verify_publication.py
```

The publication check verifies the original research/runtime files and the separately recorded documentation revision without training or cloud access. Saved research is under `models/offline_research/` and `results/offline_research/`. The original Stage 17/19 models/results and Track A bundle remain unchanged. The [data manifest](../results/offline_research/data_manifest.json) records exact versions and hashes; install only trusted model files. The original `freeze_offline_research.py verify` applies to preservation commit `159f059`, not to later documentation revisions.

### Data prerequisite

The exact existing `data/processed/track_b_28_days.csv` SHA-256 is `ab55b75f7ecccc3395b4f90f48f0236e4e49f1d993956e81985dc987b74559d4`. Obtain this authorized archived export from the owner, or use the exact 28-day export command above if access remains available. No data waiting is necessary. A new export may differ in serialization/content: do not label a hash-mismatched file the frozen dataset. Raw CSV, sequence cache and row-level prediction CSV are ignored, not distributed in Git.

### Execute a separate reproduction

The following was the executed pipeline; `--run-dir` directs intentional repeats away from frozen outputs. Defaults were used for the original run. The new directory must not contain previous results. Config and raw input remain the checked-in/root paths; do not change settings to pursue better scores.

```bash
python src/offline_forecasting.py prepare --run-dir /tmp/youbike-phase34-reproduction
python src/offline_forecasting.py pilot --run-dir /tmp/youbike-phase34-reproduction
python src/offline_forecasting.py train --run-dir /tmp/youbike-phase34-reproduction
python src/offline_forecasting.py evaluate --run-dir /tmp/youbike-phase34-reproduction
python src/offline_optimization.py --run-dir /tmp/youbike-phase34-reproduction
```

Review the pilot before formal training; fixed budgets/settings are in [the protocol](OFFLINE_RESEARCH_PROTOCOL.md). There is one architecture, two learning rates, seeds 11/29/47, and no post-evaluation tuning. `prepare`, `train`, `evaluate` and optimization refuse existing finalized outputs. Retraining can show version/hardware numerical differences; CPU reloaded prediction tolerance is `atol=1e-5, rtol=1e-6`. Equal-objective MILP tie plans may differ; compare feasibility and objective, not only exact edge lists. Timings vary.

### Reloaded inference and checks without retraining

At preservation commit `159f059`, on the original workstation with the recorded ignored cache and prediction CSV (the baseline checks predate live-serving changes):

```bash
python src/freeze_offline_research.py check
python src/offline_forecasting.py predict \
  --input-npy /tmp/youbike-offline-inference-smoke.npy \
  --output /tmp/youbike-offline-predictions.csv
```

`check` validates protected original artifacts, raw/config/cache/model hashes, common evaluation scope, saved-versus-reloaded predictions and every recorded simulation plan; it creates the ten-sequence smoke input in `/tmp`. `predict` needs no labels and returns all methods in CSV. For caller-supplied input, use raw `[N,13,9]` arrays in the [model card's feature order](TRACK_B_OFFLINE_MODEL_CARD.md), enforcing per-station chronology, activity and past-only inputs. The tensor-only interface cannot prove timestamps are valid.

The checks and standalone prediction CLI were actually run. The isolated path option uses the same pipeline but the entire experiment was not repeated merely to duplicate results.

### Research Dashboard

The new static panel reads `dashboard/app/offline-research-data.json`; it does not load Python models or require a live cloud/API/token connection. The recorded result-to-panel build is:

```bash
python src/build_offline_dashboard.py
cd dashboard
pnpm run dev
```

Do not rebuild the original Track A bundle for this work. Open the server's printed local URL and use the “Track B 模型與調度模擬” link / `#track-b`. The 12 fixed scenarios, resource/cost variants and three methods are selectable. Rebuilding the panel after freeze is unnecessary unless verifying byte-identical output in an isolated copy.

With already installed Dashboard dependencies, the equivalent direct commands avoid a package-manager wrapper reinstalling packages:

```bash
cd dashboard
WRANGLER_LOG_PATH=.wrangler/wrangler.log node node_modules/vinext/dist/cli.js dev --host 127.0.0.1
# In a separate terminal, for build and SSR assertions:
WRANGLER_LOG_PATH=.wrangler/wrangler.log node node_modules/vinext/dist/cli.js build
node --test tests/rendered-html.test.mjs
node node_modules/typescript/bin/tsc --noEmit --target ES2017 \
  --lib dom,dom.iterable,esnext --strict --esModuleInterop \
  --module esnext --moduleResolution bundler --resolveJsonModule \
  --isolatedModules --jsx react-jsx --skipLibCheck --types react \
  app/page.tsx app/offline-research.tsx
```

Production artifacts are local build outputs only. No deployment, commit, push, tag, release or cloud mutation is part of these verification commands. See [acceptance](RESEARCH_FREEZE.md) for actual passed checks and environment limitations.
