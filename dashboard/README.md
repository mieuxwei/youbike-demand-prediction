# YouBike — 歷史研究、即時可用車預測與調度模擬

Existing React 19 + Vinext website, extended without rebuilding research bundles or fitting models. Track A, Track B and Phase 4 use different targets/models; they are not one direct prediction pipeline.

**[Open the public demonstration](https://youbike-demand-observatory.rwhqgqfdk2.chatgpt.site/#live)** — no login, token or local setup. Sites version 3; public access and deployed desktop/mobile viewport checks are recorded below.

- `#live`: fixed 12-station current observations, explicit 30m persistence and original Stage 17 / independently validated Stage 19 60m HGB.
- `#forecast`: ten representative 2023 December holdout times for historical hourly transfer-related borrowing demand, not current inventory.
- `#track-b`: unchanged recorded Phase 3 LSTM comparison and Phase 4 no-transfer/greedy/MILP simulations. No live optimization or operational recommendations.

Site project: `appgprj_6a87dd803dd48191b841e9d24dea3366`. Deployment/access evidence and exact versions: [v7 delivery record](../docs/LIVE_DEMO_DELIVERY.md). Original local-only acceptance remains in the [v6 research freeze](../docs/RESEARCH_FREEZE.md); it does not describe v7 publication.

## Live serving

The browser anonymously reads only `https://youbike-track-b-collector.mieuxander.workers.dev/demo/live`. No export token, full history or model trees are shipped to it. The existing Worker reads bounded private D1 history and runs the frozen tree export; collector cron and schema remain unchanged. No extra Python inference host or API key.

Refresh every 60 seconds, age labels every second. Source, scheduled origin, fetch-start and completion timestamps are displayed in Asia/Taipei (UTC+8). Horizon is measured from scheduled snapshot, not page-load time. Ten-minute freshness, complete one-hour history, source-time/cadence/activity/station consistency and inference checks fail closed. Network failure clears the live display; expired responses stop forecasts even without another fetch. Decimal forecasts are estimates, not guaranteed bikes or risk probabilities.

All 12 stations come from the prior Phase 4 training-coordinate selection, not forecast performance. [Serving protocol, station rationale and parity](../docs/LIVE_DEMO_PROTOCOL.md). Existing independent-window metrics are not this subset's live metrics.

## Local start and verification

```bash
cd dashboard
pnpm install
pnpm run dev
pnpm run build
node --test tests/*.test.mjs
```

The historical panels work without the live endpoint. Live network access is required only for `#live`. SSR artifact tests run from this repository's `dashboard/` directory because they also check saved research source hashes. The standalone Sites checkout contains website source only; copy its build into the repository's ignored `dashboard/dist/` for the same repository tests.

Strict changed-component verification:

```bash
node node_modules/typescript/bin/tsc --noEmit --target ES2017 --lib dom,dom.iterable,esnext --strict --esModuleInterop --module esnext --moduleResolution bundler --resolveJsonModule --isolatedModules --jsx react-jsx --skipLibCheck --types react app/page.tsx app/offline-research.tsx app/live-availability.tsx
```

`pnpm run lint` remains an optional full-project check; do not infer it passed from build success. Actual executed checks are listed in the delivery record.

The optional local-only `tests/live-fault-server.mjs` harness accepts a saved public `/demo/live` response as its argument and serves `127.0.0.1:3091/?mode=failure#live`. Explicit modes are `failure`, `stale`, `missing-history`, `inference-failure`, and `loading` (15-second timeout). It visibly labels responses **LOCAL QA ONLY**, is not imported by the app, and never changes cloud data. It requires an existing production build; stop it after testing. Do not deploy its simulated responses as live data.

## Frozen bundles — no rebuild needed for viewing

`app/dashboard-data.json` (Track A) and `app/offline-research-data.json` (Phase 3/4) are preserved. Historical reproduction tools remain `python src/build_dashboard_data.py` and `python src/build_offline_dashboard.py` from the research repo root; do not run them merely to start or publish the demo. Neither was rerun for v7.

The server model converter is `python src/export_live_hgb.py` (existing exact library versions and archived CSV required). It validates original artifact/metadata/config SHA and does no fitting. Worker tests compare 72 saved origins against the original Python features and predictions.

## Interpretation

Track A covers transfer-related trips at 100 training-selected stations; weather is one-point historical reanalysis. The 60m original HGB's independent MAE gain is only 1.71%; seasonal generalization and significance are unproven. LSTM did not beat the separate aligned retrospective HGB. Static MILP ties greedy in base cases; immediate transfers, half-capacity target and synthetic distance/costs do not establish operational benefits. Current bikes, future estimates and hypothetical simulation are labeled separately.
