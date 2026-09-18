# Stage 18 — Track B Collector Resilience Repair

## 1. Scope

This stage repairs the production Cloudflare Worker after several scheduled runs exhausted all three attempts with `malformed_response`. It does not change the D1 schema, delete or rewrite stored snapshots, rotate `EXPORT_TOKEN`, retrain Track B, modify Track A, or alter Stage 17 metrics.

The official endpoint returned valid JSON from a local read-only request while the Worker failures were occurring. That evidence is consistent with a transient upstream or cache-path response problem, but it does not prove one unique root cause.

## 2. Collector changes

- Set Worker `fetch()` to `cache: "no-store"` so requests to the non-Cloudflare origin bypass Cloudflare cache reuse.
- Read the response body as text, remove an optional UTF-8 BOM, reject an empty body explicitly, then parse JSON.
- Log only safe malformed-response metadata: content type, received character count, declared content length, first character, last-modified, and ETag. The response body is not logged.
- Extend retry backoff from 250 ms + 1,000 ms to 2,000 ms + 10,000 ms. All attempts keep the original scheduled `snapshot_time`, and the D1 primary key continues to prevent duplicate station-time rows.

## 3. Tests and build verification

- Cloudflare collector Node tests: 11 passed.
- New coverage: uncached request options, BOM-prefixed valid JSON, empty body, safe malformed metadata, and recovery from one malformed attempt without changing the snapshot key.
- `git diff --check`: passed at the implementation checkpoint.
- Wrangler dry-run: bundle succeeded at 19.55 KiB, gzip 5.50 KiB, with D1 and environment bindings resolved. A sandbox-only warning prevented Wrangler from writing its default user-level log; rerunning with a task-local log path avoided that issue.

## 4. Production deployment evidence

- Deployment date: 2026-09-19 Asia/Taipei.
- Worker version: `30e22fe9-9d56-48d1-9cb3-c84c551112d2`.
- Endpoint: `https://youbike-track-b-collector.mieuxander.workers.dev`.
- Cron: `*/5 * * * *` UTC, unchanged.
- D1 binding and database: unchanged.
- First post-deployment run: scheduled `2026-09-18T17:20:35Z`, finished `2026-09-18T17:21:15.945Z`, success on attempt 1 with 1,803 station rows.
- Second post-deployment run: scheduled `2026-09-18T17:25:01Z`, finished `2026-09-18T17:25:03.962Z`, success on attempt 1 with 1,803 station rows.
- Coverage at the second checkpoint: 8,151 snapshots and 14,657,729 station rows.
- Follow-up checkpoint at `2026-09-18T18:00:01Z`: nine consecutive post-deployment runs had succeeded on attempt 1; coverage reached 8,158 snapshots and 14,670,350 station rows.

## 5. Interpretation and next step

Nine consecutive post-deployment runs prove that cloud collection resumed; they do not by themselves prove long-term stability. Continue monitoring normal scheduled runs. If malformed responses recur, the new `collection_runs.error_message` metadata can distinguish a truncated JSON body from an HTML/error response or an unexpected content type without retaining raw response content.

The Stage 17 fixed 28-day dataset and learned-regression results remain unchanged. Shortage/full-station classification and redistribution optimization are still outside the completed scope.

## 6. Primary references

- [Cloudflare Workers Request API](https://developers.cloudflare.com/workers/runtime-apis/request/)
- [Cloudflare Workers Fetch API](https://developers.cloudflare.com/workers/runtime-apis/fetch/)
- [Cloudflare Workers Logs](https://developers.cloudflare.com/workers/observability/logs/workers-logs/)
