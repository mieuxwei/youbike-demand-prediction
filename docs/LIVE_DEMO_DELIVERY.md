# Live demonstration delivery — v7

Date: 2026-09-27, Asia/Taipei. **研究與展示交付完成，實作 frozen — Research and demonstration delivered; implementation frozen.** This record supplements, never rewrites, the [v6 research freeze](RESEARCH_FREEZE.md).

## 中文交付速讀

作品主題是「YouBike 站點需求分析、短期可用車預測與調度模擬」。不是把一個模型包裝成所有任務：Track A 研究 2023 轉乘相關小時借車量；Track B 預測 2026 站點庫存；Phase 4 比較固定假設下的搬運方案。Track A 不直接輸入後兩者，庫存差值不等於租借事件。

- **既有研究成果：** Track A HGB 在 74,282 筆十二月 holdout 上 MAE 1.575、RMSE 2.549、R² 0.794。Track B 獨立七天驗證，30m persistence MAE 1.950；60m 原 HGB 2.813，對照 persistence 2.862，只改善 1.71%。
- **補充研究：** 64 站回溯 LSTM MAE 3.326271，未優於相同範圍 HGB 3.249886，不採用。12 站靜態模擬中 greedy／MILP 基本平均目標都為 76.8478，不調度 92.1952；16.65% 是假設目標下降，不是真實營運收益。
- **此次工程差異：** v6 只有本機研究面板；v7 增加免登入公開網站、完整固定 12 站的車況／資料年齡、30m 基準與原 60m HGB 伺服端推論、安全失效提示。未重訓、未改資料窗或歷史成績，也未重建原 Dashboard bundle。
- **使用方式：** 直接開啟下方公開連結。約五分鐘依序看：兩 Track 的問題 → 即時觀測與兩種估計 → Track A 歷史時段 → LSTM 負面結果 → 無調度／greedy／MILP 與零資源情境。完整時間分配見下方。
- **限制：** 這是研究展示，不是缺車機率、到站保證或派車建議。歷史天氣是再分析值；模型跨季節及實際調度效益未驗證；資料過舊或不完整時刻意不提供估計。Collector 持續蒐集與本研究交付的停止邊界分開。

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
| GitHub research preservation commit | `159f059d0e9ff4afcdbf9ad206d1b426aa1339aa` |
| GitHub live implementation commit | `f3e27e055195818c3c4ddc4e53d92bd18c1c1cdf`, pushed to `main` and fetched back successfully |
| Sites project | `appgprj_6a87dd803dd48191b841e9d24dea3366` |
| Website source commit (separate Sites repository) | `930ef06b094ffde278b93201150f1e9e40c17b54` |
| Saved version | 3, `appgprj_6a87dd803dd48191b841e9d24dea3366~appgver_e5d6fb29f48881919a9229df858c06b8` |
| Deployment | `appgdep_6ab8cdcfd9648191b6f76878881b25e7` — succeeded; latest deployment record updated at `2026-09-27T08:04:28.632738Z` |
| Version archive content hash | `sha256:f9563d48497b4a6b59a5309eb34a3b958e62cdf91fb008a60d5bca4ac4153842` |
| Access | `public`, revision 2, set at `2026-09-27T08:04:03.254248Z` |
| Anonymous HTTP acceptance | HTTP 200 at `2026-09-27T08:04:12Z`; no cookies, authorization or bypass token sent; new live/A/Phase 3/4 HTML present, no sign-in page |
| Anonymous asset acceptance | At `2026-09-27T08:50:18.830Z`, HTML and all six referenced JS/CSS resources returned 200 with expected content types, without a cookie jar or authorization |

The old Sites source mirrored the whole research repository and lacked root hosting metadata. A metadata-only compatibility commit (`7f008a09286b4bc5bf87a6a6c3dbcd1c97674fb9`) allowed the standard workflow to open it. The subsequent website-only source commit preserves that repository's history; it does not remove anything from the GitHub research repository. GitHub and Sites have different commit identities. A missing version-controlled `dashboard/build/sites-vite-plugin.ts` was restored to tracking unchanged, fixing fresh-checkout build reproducibility.

The deployed Sites checkout's `app/` and `public/` trees match the GitHub working source byte-for-byte. Later repository-only delivery notes and the local fault-test harness do not change the deployed runtime. GitHub HTTPS push lacked a terminal credential; the existing SSH login succeeded without changing permanent remote/configuration, exposing a token, or force-pushing.

## Executed acceptance

- Worker deployment succeeded: `069e3f5a-5966-4efa-aafc-0ab2697dfa62`; same `*/5 * * * *` Cron and D1 binding.
- Anonymous `/demo/live` returned 12/12 valid persistence and HGB results at `2026-09-27T07:49:15.653Z`, from scheduled snapshot `07:45:28Z`, source `07:44:52Z`, fetch start `07:45:47.310Z`, completion `07:45:48.966Z`.
- Unauthorized export 401; arbitrary station query 400; POST to demo 405; direct `/src/live-model.json` access 404. All checked anonymously on the deployed Worker.
- Following deployment, two different scheduled keys appeared at `07:50:28Z` and `07:50:32Z`. A bounded, read-only query confirmed the four-second interval (16 rows read, zero written). A schedule handover is the likely explanation, not a separately proven root cause. The conservative cadence guard correctly stopped HGB and displayed the history-gap reason; persistence remained available. No records deleted, no research data corrected, no gate relaxed. Availability resumes automatically only when the preceding history is valid again.
- Recovery actually verified at `2026-09-27T08:56:09.146Z`: HTTP 200, all **12/12 persistence and 12/12 HGB** forecasts valid; scheduled origin `08:55:32Z`, source `08:54:52Z`, fetch start `08:55:32.830Z`, completion `08:55:36.923Z`. Public desktop and mobile both displayed the first fixed station's actual 4 bikes / 24 return spaces, 30m baseline 4, 60m HGB 4.9 (unrounded API 4.850597722947602); target times 17:25:32 / 17:55:32 Asia/Taipei. The guard recovered naturally, with no second deployment or restart. This is operational acceptance, not an accuracy metric.
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

Native Safari/private-window automation hung and was interrupted. No Safari-private or physical-phone pass is claimed; the owner reported being unable to test on a phone at this time. Public access is supported by the connector's public sharing setting, a credential-free HTTP 200 response and actual deployed-page browser checks without a login step; there is no owner-bypass credential in the demo. Full-project ESLint and whole-project TypeScript were not rerun: scoped strict typing, build, tests and browser checks are the executed boundary. No long-term uptime, performance under load or all-browser guarantee is claimed.

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

Required website, document, public-access, serving-parity, normal/degraded UI and regression acceptance is complete. The final file boundary is recorded in `results/live_demo/freeze_manifest.json`; its containing Git commit is the final freeze record. The implementation/runtime version is `f3e27e0`, with later completion documentation and verifier metadata recorded separately. No tag or Release is created.

No automatic next stage, reminder or research monitor is created. Existing cloud collection is ongoing infrastructure, separate from this frozen research/demonstration delivery; storage/cost lifecycle remains the owner's operational responsibility, not a new autonomous research task. The task-owned local test servers were stopped. No user authentication or token setup is required to view the public demo. **Stop this version's implementation now; reopen only on an explicit new request.**
