# Live demonstration delivery — v7

Date: 2026-09-27, Asia/Taipei. **Research remains frozen; final demonstration acceptance in progress.** This record supplements, never rewrites, the [v6 research freeze](RESEARCH_FREEZE.md).

## Scope and version boundary

YouBike 站點需求分析、短期可用車預測與調度模擬。Track A uses historical 2023 transfer-related hourly borrowing demand; Track B predicts future 2026 station inventory; Phase 4 is a fixed-assumption retrospective redistribution simulation. Targets, datasets and models differ. Track A outputs do not directly feed Track B or redistribution. Inventory changes are not observed rental counts.

The owner explicitly reopened only presentation engineering and authorized preservation commits, pushes and deployment. No training, new research export, additional search, evaluation change or new data window. Original research and previously uncommitted Stage 19/Phase 3/4 results were verified against all 268 freeze-manifest hashes and preserved in Git commit `159f059`. The original freeze is verifiable at that commit; current presentation files intentionally evolve under v7.

## Architecture

Official Taipei feed → unchanged five-minute Cron/validation/retry → existing D1 → bounded read-only `/demo/live` → server-side frozen numeric HGB/persistence → existing React/Vinext website. Cloudflare Worker remains `youbike-track-b-collector`; D1 database/schema and export token remain unchanged. Site source is separated from the research repository for deployment, preserving its legacy Git history. The full research repository remains on GitHub.

The public endpoint exposes only all 12 preselected Phase 4 stations' latest observations, forecast summaries, reasons, source/schedule/fetch-completion timestamps and expiry. It does not accept ranges, arbitrary stations or writes. Maximum 16 rows × 12 stations / preceding 65 minutes are read privately using the existing station-time primary key. Cache ≤30 seconds; browser refresh 60 seconds; browser clears data on request failure and hides expired predictions. No additional secret, Python host or paid inference provider.

See [prospective demo protocol and station selection](LIVE_DEMO_PROTOCOL.md). 30m persistence is explicitly a constant-current-state baseline. 60m is the original 23-feature, 120-tree Stage 17 HGB, not Phase 3's later 117-feature HGB. Trees are losslessly serialized, never fit; float32 feature casts, numeric thresholds/leaves, backward 15/30/60m lag with two-minute tolerance, `[t-window,t)` rolling, Taipei calendar and capacity clipping match Python.

Model SHA-256: `d4bc2df1c815a7c722e900891b668d3b2a7124f66966913081cb957b5ec7e6f6`. Server tree export SHA-256: `f81a2d3878d83be70659ff384d733ae8e3f6db9c950e7d824c1326d4ba858758`. Weights/history/token are not in browser bundles or API responses.

## Public deployment

**[Open the live research demonstration](https://youbike-demand-observatory.rwhqgqfdk2.chatgpt.site/#live)** — no account, export token or local server required. The historical demand section is `#forecast`; recorded availability research and simulation are `#track-b`.

| Deployment identity | Actual value |
|---|---|
| Sites project | `appgprj_6a87dd803dd48191b841e9d24dea3366` |
| Website source commit (separate Sites repository) | `930ef06b094ffde278b93201150f1e9e40c17b54` |
| Saved version | 3, `appgver_e5d6fb29f48881919a9229df858c06b8` |
| Deployment | `appgdep_6ab8cdcfd9648191b6f76878881b25e7` — succeeded at `2026-09-27T08:03:41.802067Z` |
| Version archive content hash | `sha256:f9563d48497b4a6b59a5309eb34a3b958e62cdf91fb008a60d5bca4ac4153842` |
| Access | `public`, revision 2, set at `2026-09-27T08:04:03.254248Z` |
| Anonymous HTTP acceptance | HTTP 200 at `2026-09-27T08:04:12Z`; no cookies, authorization or bypass token sent; new live/A/Phase 3/4 HTML present, no sign-in page |

The old Sites source mirrored the whole research repository and lacked root hosting metadata. A metadata-only compatibility commit (`7f008a09286b4bc5bf87a6a6c3dbcd1c97674fb9`) allowed the standard workflow to open it. The subsequent website-only source commit preserves that repository's history; it does not remove anything from the GitHub research repository. GitHub and Sites have different commit identities. A missing version-controlled `dashboard/build/sites-vite-plugin.ts` was restored to tracking unchanged, fixing fresh-checkout build reproducibility.

## Executed acceptance

- Worker deployment succeeded: `069e3f5a-5966-4efa-aafc-0ab2697dfa62`; same `*/5 * * * *` Cron and D1 binding.
- Anonymous `/demo/live` returned 12/12 valid persistence and HGB results at `2026-09-27T07:49:15.653Z`, from scheduled snapshot `07:45:28Z`, source `07:44:52Z`, fetch start `07:45:47.310Z`, completion `07:45:48.966Z`.
- Unauthorized export 401; arbitrary station query 400; POST to demo 405; direct `/src/live-model.json` access 404. All checked anonymously on the deployed Worker.
- Following deployment, two different scheduled keys appeared at `07:50:28Z` and `07:50:32Z`. A bounded, read-only query confirmed the four-second interval (16 rows read, zero written). A schedule handover is the likely explanation, not a separately proven root cause. The conservative cadence guard correctly stopped HGB and displayed the history-gap reason; persistence remained available. No records deleted, no research data corrected, no gate relaxed. Availability resumes automatically only when the preceding history is valid again.
- 80 Python tests, 18 collector/server tests and 4 Dashboard contract/SSR/artifact tests passed. 72 historical parity cases: all 23 features and raw/clipped Python/JS outputs have maximum difference **0**. Parity is not performance evaluation.
- A second parity check used the actual deployed response at `07:49:15.653Z` and its `07:45:28Z` origin: all 12 production HGB outputs exactly matched the original Python artifact (maximum difference 0). A bounded read-only D1 query returned 168 history rows (192 rows read, zero written); no new research dataset or metric was produced.
- Website production build and strict changed-component TypeScript checks passed.
- Public deployed website, desktop 1365×900 and mobile viewport 390×844: live cards, source/collection/target times, station switching and responsive layout checked. Mobile document width equals scroll width (375 CSS pixels with the embedded browser's scrollbar); no page-wide overflow. These are browser viewport checks, not a physical-device or all-browser certification.
- The public page refreshed from the `08:20:32Z` to `08:25:32Z` snapshot without reloading; last fixed station changed from 13 to 16 bikes, with target times advancing. No observed browser warning/error logs.
- Deployed Track A regression: December 1 08:00 still shows 726 predicted / 876 observed trips and MAE 2.86. Deployed Phase 4 zero-resource scenario still gives zero transfers for all three methods and objective 76.877. Recorded bundles and old research component are unchanged.
- Local-only fault harness, using clearly labeled simulated response failures: HTTP 503 and 15-second timeout clear live observations/predictions; stale source labels the observation non-live and hides both forecasts; missing one-hour history and inference failure preserve valid persistence but hide HGB with explicit reasons. The harness is not imported or enabled in the production app. The actual deployed history-cadence failure also displayed its reason correctly.
- Integrity: all 256 non-presentation files in the v6 manifest remain byte-identical. The exact 12 permitted documentation/presentation/route changes are listed in `src/freeze_live_demo.py`; the original manifest itself is checked against preservation commit `159f059`. Seven built browser JS chunks contain none of the export-token, tree-serialization or private-key markers. The Worker module is not imported by the browser.
- Markdown: 89 relative document/image links in the eight current delivery documents resolve, fenced blocks are balanced, and `git diff --check` passes.

### Unverified extras and interrupted check

Native Safari/private-window automation hung and was interrupted. No Safari-private or physical-phone pass is claimed. Public access is supported by the connector's public sharing setting, a credential-free HTTP 200 response and actual deployed-page browser checks without a login step; there is no owner-bypass credential in the demo. Full-project ESLint and whole-project TypeScript were not rerun: scoped strict typing, build, tests and browser checks are the executed boundary. No long-term uptime, performance under load or all-browser guarantee is claimed.

The existing LibreSSL/urllib3 and sandboxed physical-core-discovery warnings appeared in Python checks; all tests and model comparisons completed. Vinext reported an existing unknown static-route classification notice; build, server rendering and actual public deployment succeeded. No dependency or lockfile was changed to suppress warnings.

## Rechecking the delivery boundary

```bash
python src/freeze_live_demo.py verify-research
# After the final v7 record exists:
python src/freeze_live_demo.py verify
git log -1 -- results/live_demo/freeze_manifest.json
```

The final delivery manifest captures the accepted source/docs/config/model hashes and actual cloud version IDs; its containing Git commit identifies the final record without a circular self-hash. The original v6 whole-working-directory check remains reproducible at `159f059`. Running it unchanged against v7 would intentionally report the authorized presentation edits; it is not evidence of corrupted research. `record` is an explicit post-acceptance operation, refuses to overwrite a prior record, and does not train, export, publish or schedule anything.

## Research interpretation and a five-minute demonstration

1. **0:00–0:40:** Introduce the three related questions; distinguish hourly borrowing demand, available bikes, and assumed redistribution.
2. **0:40–2:00:** Open the live section; inspect fixed station, bikes/return spaces, source age, schedule and fetch completion. Explain constant 30m persistence versus frozen 60m HGB. A visible unavailable forecast demonstrates a safety gate, not a zero forecast.
3. **2:00–3:00:** Switch a historical Track A holdout time. Explain 100 training-selected stations / 74,282 December rows, HGB MAE 1.575, RMSE 2.549, R² 0.794. Ten displayed timepoints are not the complete test set; reanalysis weather is not future weather.
4. **3:00–4:00:** Open Track B evidence and Phase 3. Independent 30m persistence MAE 1.950; 60m HGB 2.813 versus persistence 2.862 (1.71% improvement). Separately, 64-station retrospective LSTM MAE 3.326271 did not beat aligned HGB 3.249886. Different scopes are not a leaderboard.
5. **4:00–5:00:** Compare no transfer, greedy and MILP for the same historical scenario; try zero resources/high cost. Base mean objective 92.1952 versus 76.8478 for both active methods, a 16.65% assumed-objective reduction, not measured operational benefit. End with limits and the fixed delivery boundary.

## Limits and stopping boundary

This is a public research demo, not production operations, a shortage/full-risk classifier, truck routing or a promise of stock at arrival. Only 12 fixed stations are served; future estimates use scheduled snapshot origin, not page-load time. Source delays and deployment/schedule jitter can intentionally suppress predictions. Real dock usability, seasons, significance and causal operational gains remain unvalidated. Phase 4 stays static; no current-input optimization is added.

No automatic next stage, reminder or research monitor is created. Existing cloud collection is ongoing infrastructure, separate from this frozen research/demonstration delivery. Final freeze is not asserted until publication and acceptance are recorded.
