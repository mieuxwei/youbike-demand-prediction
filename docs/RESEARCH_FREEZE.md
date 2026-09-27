# Research freeze and local acceptance

Date: 2026-09-27, Asia/Taipei. **Research Complete — Implementation Frozen**. Required local research, implementation and acceptance checks passed. This is a local working-directory freeze, not a release, commit or deployed version.

## Scope completed by implementation

- Preserve Track A historical transfer-demand research, original model artifacts and ten-timepoint bundle.
- Preserve original Stage 17/19 protocols, models, results and conclusions, including pre-existing uncommitted Stage 19 work.
- Execute bounded supplementary retrospective Track B 60m persistence/HGB/LSTM comparison, two preset learning rates and three seeds. Common 64 stations / 89,600 evaluation rows. MAE 3.431339 / 3.249886 / 3.326271; LSTM not adopted.
- Execute 12-station static MILP, deterministic greedy and no-transfer comparison across 12 preselected times and six resource/cost variants. All 72 MILP runs optimal; 216 plans feasible. Base mean objective 92.1952 vs 76.8478 for both active methods; MILP does not beat greedy in the base cases. All 144 predefined sensitivity rows retained, including cases where additive-transfer reference deviation worsens.
- Integrate recorded results and selectable simulation inputs/constraints/transfers into the existing React/Vinext Dashboard, without rebuilding the original Track A bundle.

Original Phase 1–5 mapping and v5 scope replacement: [PROJECT_PLAN](../PROJECT_PLAN.md). Methods/results: [Phase 3–4 report](PHASE_3_4_OFFLINE_RESEARCH.md). This does not claim production readiness, live prediction, a risk classifier, real routing or operational benefit.

## Traceability and version boundary

- Existing fixed raw CSV: `[2026-08-21T09:45:02Z, 2026-09-18T09:45:02Z)`, 14,490,149 rows. Obtained previously through authorized Cloudflare export; no new export this task. SHA-256: `ab55b75f7ecccc3395b4f90f48f0236e4e49f1d993956e81985dc987b74559d4`.
- `config/offline_research.json` SHA-256: `2a735737a4913c68f22c9e4bf1cdcc78414529e3adc7dc4a80bc3f6aeeffe445`.
- `models/offline_research/selection.json` SHA-256: `8136ea2b8d0775d6ef150a7eb1875464c480d6215db4c7232d3cf1455813f6cb`.
- Original-artifact protection: [137-file baseline](../results/offline_research/protected_baseline.json), including prior working-tree Stage 19 results, not just HEAD.
- Data/cache/model/feature/selection provenance: [data manifest](../results/offline_research/data_manifest.json), [selection](../models/offline_research/selection.json), [evaluation](../results/offline_research/evaluation.json).
- Parent Git HEAD: `3055c856b246680efbda2383d2fbf8e401816f4e`. This is the parent commit, **not a commit of the new work**. Final manifest captures real dirty/untracked working-directory status and each versioned/intended file hash. No invented tag/release.
- Raw/cache/row-level prediction files remain ignored. Models and compact numeric evidence are saved locally. Reproducing without the ignored data requires the exact owner-supplied archived export (or authorized equivalent whose hash must be checked).

## Executed checks

| Check | Observed result |
|---|---|
| Python suite | 80 passed; includes per-station time alignment, gaps/inactivity, target-boundary purge, train-only scaling, integer/stock/capacity/resource constraints and a tiny brute-force MILP oracle |
| Collector Node tests | 11 passed, mock/local only; no cloud calls |
| New research integrity check | Exact source/config/cache/model hashes, full 89,600-row origin/target/label alignment and metric recomputation, common keys, ten reloaded predictions and all 216 saved plans passed |
| Standalone prediction CLI | Executed on the ten real prepared sequences; no labels used |
| Dashboard production build | Passed; local `dist` only, all five build phases complete |
| Dashboard SSR/data tests | 2 passed; original Track A content plus new panel, 12 scenarios, zero-resource/high-cost outcomes and source artifact hashes |
| Browser interaction | Passed: three plan methods, first/last scenario, base/zero-resource/high-cost controls, original Stage 19 disclosure; no observed error/warning logs |
| Browser layout | Desktop and 390×844 mobile viewport checked; controls readable, no document-wide horizontal overflow; temporary viewport reset |
| TypeScript | Strict no-emit check of both changed React components and their imported data passed |
| Optional changed-component ESLint | Not completed: stopped after >13 minutes still loading existing plugin dependencies; no pass claimed |
| Markdown / whitespace | 133 relative document/image links in 11 updated/new docs resolve; fenced blocks balanced; `git diff --check` passed |
| Freeze manifest | Created after required acceptance; exact file hashes and completion time in `results/offline_research/freeze_manifest.json` |

Only raw/model reloading and stored metrics were checked after the experiment; no old-model retraining or extra tuning. The full isolated `--run-dir` experiment was not repeated solely to duplicate results; original prepare/pilot/train/evaluate/optimize all executed, and the path-isolation entry is documented.

## Warnings and checks not claimed

- The first local preview launch hit a Vite configuration-read timeout during cold dependency access; a warm retry succeeded. No dependency versions, lockfile, deployment config or access settings were changed. The package-manager wrapper also produced an unusable build-approval stub; that task-created stub was removed, and existing installed CLI entry points were used.
- The optional whole-project `tsc --noEmit` scan was stopped after more than 12 minutes of cold reads in unrelated, unchanged Drizzle schemas. Instead, the strict TypeScript check was completed for `app/page.tsx`, `app/offline-research.tsx` and their imports, using the project's compiler options. A whole-project typecheck pass is not claimed.
- Optional ESLint likewise remained in existing plugin dependency reads after more than 13 minutes and was stopped without a result. No lint pass is claimed. Required correctness acceptance rests on executed strict changed-component typing, production build, rendered HTML/artifact tests, browser interactions and numerical/invariant checks, not this optional style/static-analysis run. No known unresolved error affecting the research conclusions remained.
- Python emits the existing LibreSSL/urllib3 warning; sandboxed joblib CPU discovery falls back to logical cores. Tests and reload checks passed; this run does not validate arbitrary platforms. Formal model hardware: Apple M4, 10 cores, 16 GiB, CPU; Python 3.9.6, PyTorch 2.8.0, NumPy 2.0.2, pandas 2.3.3, SciPy 1.13.1, scikit-learn 1.6.1, joblib 1.5.3.
- Build emits plugin timing notices and an existing unknown static-route-classification notice; SSR returned HTTP 200 and rendered expected content. No production-server/deployment compatibility claim beyond the local build/SSR/browser checks.
- September 27 read-only Sites lookup: existing site active, custom access. Direct HEAD request to the server-returned hosted URL timed out after 30 seconds; current hosted page accessibility/content was **not verified**. No bypass token or permission change attempted. The new panel was **not deployed**, so the hosted page cannot be assumed to contain it. Local verification is the agreed acceptance boundary.
- Full-season generalization, significance, operational dock usability, causal redistribution outcomes and risk calibration were not studied. Previously seen data remains retrospective; pure tensor input cannot establish real-world timestamp validity. See [limitations](PHASE_3_4_OFFLINE_RESEARCH.md#4-interpretation-and-reproducibility).

## Reproduction and stop rule

Use [REPRODUCIBILITY](REPRODUCIBILITY.md#phase-34-fixed-data-research) and [Dashboard instructions](../dashboard/README.md). Same-version CPU reloaded predictions use `atol=1e-5, rtol=1e-6`; timing varies; equal-objective MILP edges may differ. Do not overwrite frozen outputs to reproduce.

`results/offline_research/freeze_manifest.json` records exact completion time, HEAD, dirty state, hashes, publication and stop rule. Its companion `acceptance.json` records executed checks and unverified extras. Verify via `python src/freeze_offline_research.py verify`. The task-owned local preview server was stopped after acceptance; restart it with the documented local command when needed. No new background task was left running.

Freeze means stop this implementation: no new features, models, training, windows, reminders, monitoring or automatic next stage. Reopen only on explicit owner request. Cloud collector, schedules, tokens, permissions and existing deployment remain unchanged. Cloud collection continuing is separate from research completion. **No commit, push, tag, release or deployment was performed.**
