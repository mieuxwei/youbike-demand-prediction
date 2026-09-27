# Phase 3–4 — Fixed-data forecasting and redistribution simulation

Executed 2026-09-27. Supplementary **retrospective** research, not a new independent validation. Local artifacts; no deployment. Final acceptance is recorded separately in [RESEARCH_FREEZE.md](RESEARCH_FREEZE.md).

## 1. Scope and provenance

This implements the original Deep Learning comparison and Optimization phases under the owner's revised scope. Track A and Stage 17/19 artifacts and conclusions remain unchanged. The Stage 17/19 data and results had already been inspected; repeating chronological splits does not erase that exposure or possible researcher-selection bias.

The [protocol](OFFLINE_RESEARCH_PROTOCOL.md) and [configuration](../config/offline_research.json) were written before this round's experiments. A development-only pilot retained the original bounded budget. No candidates or scenarios were added after retrospective evaluation.

- Existing input: `data/processed/track_b_28_days.csv`, an authorized Cloudflare export; no new export this round.
- Interval: `[2026-08-21T09:45:02Z, 2026-09-18T09:45:02Z)`.
- 14,490,149 station rows, 8,058 snapshots, 1,803 observed stations; original audit: 0 duplicate keys, 7 estimated missing slots.
- SHA-256: `ab55b75f7ecccc3395b4f90f48f0236e4e49f1d993956e81985dc987b74559d4`.
- Training ends September 8 at 09:45:02 UTC; validation ends September 13 at 09:45:02 UTC; retrospective evaluation ends September 18 at 09:45:02 UTC. Intervals are half-open; target timestamps crossing their origin split's end are purged.
- Of 1,752 training-eligible stations, select 64 evenly spaced IDs from sorted IDs using training active coverage ≥95%, not model errors. Cohort raw rows: 515,712.
- Valid sequences: training 327,680, validation 86,912, retrospective 89,600. Training uses every sixth observed global snapshot slot: **54,656** samples for both learned models. Validation/evaluation use every eligible origin.

Full station list, boundaries, features, environment and cache hash: [data manifest](../results/offline_research/data_manifest.json). All six reported predictors share 89,600 evaluation rows and the key hash `9ce318863a41eba6fd5add86ff7e5a3c3b77c8dbb82a8865eb0cc1a9246eea88`.

## 2. Phase 3 methods

Target: available bikes approximately 60 minutes ahead, first observation at/after the desired time within +120 seconds. Inputs: one station's 13 consecutive observations (~60 minutes), each containing available bikes, available return docks, capacity, latitude/longitude and Taipei hour/weekday sine/cosine. Steps must be 270–330 seconds apart; inactive, nonfinite or invalid inventory rows invalidate the sequence/target. No filling across gaps or concatenation across stations. A validation/evaluation history may contain earlier-split observations available at the origin; its target must remain within its own split.

StandardScaler and delta-target scale are fit on training samples only. Learned outputs predict inventory change from current bikes and are clipped to `[0, capacity]`. HGB receives the same 13×9 standardized values flattened into 117 features; LSTM receives them as a sequence. Persistence uses current bikes unchanged. The new HGB is a separate model; it does not replace the Stage 17 model.

- One LSTM layer, 32 hidden units, linear output; Adam/MSE, batch 512, gradient clip 5.
- Two learning rates: 0.003 and 0.001; fixed seeds 11, 29, 47 for both.
- Maximum 10 epochs, patience 3, validation MAE minimum improvement 0.0001; CPU 2 threads, deterministic PyTorch. Budget 180 seconds/fit and 1,200 seconds for the bounded LSTM experiment; budget checks occur between fits/epochs, not as hard process timeouts.
- Select learning rate by mean validation MAE over all seeds. Primary LSTM prediction is the equal-weight prediction average of all three selected seeds, never the best retrospective seed.
- HGB fixed at 120 iterations, 31 leaves, learning rate 0.08, minimum leaf 200, L2=1, seed 11; no early stopping or test tuning.
- Simulation forecaster chosen by validation MAE among persistence, HGB and the selected LSTM ensemble **before** retrospective evaluation.

### Development selection and cost

Pilot: 4,096 training / 2,048 validation samples, one epoch, 0.053 seconds fit; coarse full-epoch extrapolation 0.705 seconds. This was a cost check, not an evaluation result. Formal measured costs supersede the extrapolation.

| Learning rate | Mean validation MAE across seeds | Selected |
|---|---:|---|
| 0.003 | 2.997458 | Yes |
| 0.001 | 3.008862 | No |

Validation MAE: persistence 3.035611; HGB **2.934994**; selected LSTM ensemble 2.975538. Thus the simulation uses **HGB**. All six LSTM fits took 34.784 seconds total; HGB fit took 1.984 seconds. These exclude data preparation, environment installation and documentation/QA. Hardware: Apple M4, 10 cores, 16 GiB; CPU execution, not GPU/MPS. Full per-epoch history and both candidates' seeds are retained in [development results](../results/offline_research/development_results.json).

### Common-scope retrospective results

64 stations, 89,600 rows, September 13–18 split above; units are bikes.

| Model | MAE | RMSE | R² | Fit seconds | Inference seconds |
|---|---:|---:|---:|---:|---:|
| Persistence | 3.431339 | 6.083467 | 0.676325 | 0 | 0.000508 |
| HGB, same sequence information | **3.249886** | **5.322193** | **0.752265** | 1.984 | 0.436607 |
| LSTM seed 11 | 3.323189 | 5.490209 | 0.736377 | 5.773 | 0.238509 |
| LSTM seed 29 | 3.362206 | 5.508562 | 0.734611 | 6.387 | 0.237690 |
| LSTM seed 47 | 3.377696 | 5.617593 | 0.724001 | 3.858 | 0.235813 |
| LSTM equal-weight ensemble | 3.326271 | 5.504263 | 0.735025 | 16.018 | 0.712012 |

Seed MAE mean = 3.354364; population standard deviation = 0.022933 (three seeds, not a statistical confidence interval). The ensemble's MAE is not the arithmetic mean of seed MAEs. Ensemble cost sums its three fits/predict calls; full search cost includes the other candidate. Inference costs exclude model loading, standardization and output serialization and are not service latency guarantees.

**Adoption conclusion:** LSTM improves over persistence but not the aligned HGB on this fixed scope. It is not adopted as the simulator's forecaster. No further tuning was performed. This is a bounded experiment, not evidence that all recurrent architectures are inferior.

Evidence: [comparison](../results/offline_research/comparison.csv), [evaluation](../results/offline_research/evaluation.json), [station errors](../results/offline_research/station_errors.csv), [Taipei-hour errors](../results/offline_research/hour_errors.csv). These files include all seeds as well as primary methods; do not combine their metrics with Track A or the broader Stage 17/19 station scopes.

HGB beats persistence at 47/64 stations; LSTM ensemble at 42/64. LSTM beats HGB at 12/64. The hardest HGB origin hours are 07:00 (MAE 5.499), 16:00 (5.246) and 17:00 (4.696), also the three hardest for the ensemble (5.725, 5.485, 4.891). Largest HGB station MAEs: 500110005 (7.358), 500107024 (7.290), 500106055 (7.132), each with 1,400 rows. These descriptive errors were not used for new tuning or simulation-case selection.

## 3. Phase 4 formulation

One static decision over 12 stations: the first cohort station in lexicographic order and its nearest cohort neighbours by training-period coordinates. No outcome-based station selection. Fixed requests: September 14–17 at 07:00, 12:00 and 17:00 Asia/Taipei. Use the first common valid observation within 15 minutes after each requested time. All 12 requests were available; none omitted. Dashboard defaults to the first chronological request, not the largest improvement.

Let `c_i` be historical current bikes, `C_i` capacity, `f_i` the validation-selected HGB forecast, and `x_ij` nonnegative integer transfers, with no self-transfers. Net change `n_i = Σ_j x_ji − Σ_j x_ij`. No external stock or depot exists.

Minimize:

```text
Σ_i |f_i + n_i − 0.5 C_i| + α Σ_ij d_ij x_ij + 0.05 Σ_ij x_ij
```

Subject to:

```text
Σ_j x_ij ≤ c_i                    (never move future or relay arrivals)
Σ_j x_ji ≤ C_i − c_i              (conservative current receiving capacity)
0 ≤ c_i + n_i ≤ C_i
0 ≤ f_i + n_i ≤ C_i
Σ_ij x_ij ≤ B;  Σ_ij d_ij x_ij ≤ 30 bike-km
```

`d_ij` is great-circle kilometres, **not road distance or a truck route**. Base `B=12`, `α=0.1`; 0.05 handling penalty per moved bike. All costs and the 50% inventory target are dimensionless research assumptions, not money, operator policy, fleet capacity or lost-trip estimates. All modeled empty capacity is assumed usable; actual `available_return_bikes` can be smaller because of unavailable docks. Transfers are assumed instantaneous and additive, without demand response or travel delay.

SciPy/HiGHS MILP linearizes absolute deviations with slack variables; transfers are integral. Only certified optimum is used; other solver statuses fall back to no transfer and retain their status. Zero transfer is feasible for valid inputs. If no strict objective improvement exists, explicitly return no transfer. Limit: 10 seconds/solve.

Baselines use exactly the same current stock, forecasts, constraints and objective:

- No transfer.
- Deterministic greedy: add one feasible bike transfer with the greatest strict objective decrease; ties use sorted edge order; stop if no improvement or budget exhausted.
- MILP.

All 72 solves (12 requests × 6 variants) returned optimal status. All **216 plans** were independently reconstructed from saved transfers and passed integer, conservation, current-stock, capacity and resource checks. 48 optimizer plans moved bikes; 24 returned no-improvement/no-transfer.

### Base results (mean across all 12 requests)

| Method | Objective | Inventory-target deviation | Transfer penalty | Moved bikes | Bike-km proxy |
|---|---:|---:|---:|---:|---:|
| No transfer | 92.1952 | 92.1952 | 0 | 0 | 0 |
| Greedy | 76.8478 | 75.9535 | 0.8943 | 8.4167 | 4.7343 |
| MILP | 76.8478 | 75.9535 | 0.8943 | 8.4167 | 4.7343 |

MILP's aggregate objective is 16.65% lower than no transfer **within this assumed optimization objective**. It ties greedy in all 12 base cases. This does not establish superior operational performance or reduction in unmet trips.

### Predefined sensitivity, including ineffective cases

| Variant | No-transfer objective | Greedy objective | MILP objective | Interpretation |
|---|---:|---:|---:|---|
| Move budget 0 | 92.1952 | 92.1952 | 92.1952 | No resources, no transfer |
| Move budget 6 | 92.1952 | 82.6297 | 82.6297 | Resource-limited improvement |
| Base budget 12 | 92.1952 | 76.8478 | 76.8478 | Tie between active methods |
| Move budget 24 | 92.1952 | 71.2697 | 71.2665 | Only a very small MILP advantage |
| Distance weight 0 | 92.1952 | 76.3670 | 76.3670 | Unpriced distance increases bike-km; equal objective can have different plans |
| Distance weight 10 | 92.1952 | 92.1952 | 92.1952 | Moving costs too much; no transfer |

Predetermined forecast-error probes hold each base plan fixed. Alternate station signs with shocks −5, 0, +5 bikes; clip reference inventory to capacity, then apply the same net intervention and clip again. Under −5 / 0 / +5, mean target deviation is respectively 94.0087 / 92.1952 / 104.7382 without transfer and 87.7854 / 75.9535 / 93.5048 with either active method. These are artificial perturbations, not calibrated forecast distributions.

Aggregate improvement is not universal. With the same fixed plan, the September 14 07:00 `+5` probe worsens deviation from 101.8732 to 105.3583; September 16 12:00 `−5` worsens from 94.0522 to 95.9731. The September 15 07:00 historical-reference probe also worsens from 63 to 66. Both active policies share these outcomes. All 144 method/reference sensitivity rows are retained, including these failures.

The un-intervened historical future is another reference input only: mean deviation 120.1667 without transfer vs 109.4167 under the additive transfer assumption, with mean 0.4167 boundary-clipped bikes for each active method. This clipping is an explicit approximation, not vehicle conservation evidence for an observed future. **There is no observed post-intervention counterfactual and no causal operational-benefit claim.**

Evidence: [all scenarios and transfers](../results/offline_research/optimization.json), [comparison](../results/offline_research/optimization_comparison.csv), [sensitivity](../results/offline_research/optimization_sensitivity.csv).

## 4. Interpretation and reproducibility

The completed work is a fixed-data research prototype, not live serving. Snapshot times are scheduled observation keys, not exact fetch-completion timestamps. Upstream staleness, blocked docks, station selection, a single four-week period and previously inspected data limit external validity. We do not claim statistical significance, calibrated shortage/full probabilities, truck routing or season-wide performance. Track A demand is never used as current inventory or shortage.

The [model card](TRACK_B_OFFLINE_MODEL_CARD.md), [reproduction entry points](REPRODUCIBILITY.md#phase-34-fixed-data-research), [local Dashboard](../dashboard/README.md), and [freeze record](RESEARCH_FREEZE.md) connect the executable code, artifacts and acceptance evidence. No new model or autonomous follow-up is implied by limitations.
