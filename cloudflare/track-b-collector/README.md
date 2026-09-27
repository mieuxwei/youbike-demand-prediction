# Track B Cloud Live Collector

This standalone Cloudflare Worker collects the official Taipei YouBike station
availability feed every five minutes and stores validated station-time rows in
D1. It is separate from the historical Vinext dashboard and from Track A model
training.

## Architecture

```text
Cloudflare Cron (*/5 * * * *)
        -> uncached Worker fetch, validation, and retry
        -> D1 station_snapshots + collection_runs
        -> protected /export.csv endpoint
        -> src/export_track_b.py
        -> local CSV for the Python feature pipeline
```

D1 is the primary store because Track B needs indexed station-and-time queries.
R2 is not enabled in this stage. A raw JSON archive can be added later only if a
retention or audit requirement justifies the extra storage and synchronization.

The upstream request uses `cache: "no-store"`. Transient HTTP, network,
malformed-body, empty-body, and schema failures are retried up to three times
over a twelve-second backoff window. Every retry keeps the same scheduled
`snapshot_time`, so the D1 primary key still prevents duplicate station-time
rows. Malformed JSON logs include only response metadata (content type, lengths,
first character, last-modified, and ETag), never the full response body.

## Local checks

```bash
pnpm install
pnpm test
pnpm run check
```

For local D1 development, copy `.dev.vars.example` to `.dev.vars`, replace the
placeholder token, and run:

```bash
pnpm run db:migrate:local
pnpm run dev
```

Wrangler's `--test-scheduled` mode exposes a local scheduled-event route. Local
testing does not replace the production Cron Trigger.

## Production setup boundary

Production deployment requires the repository owner's Cloudflare login and a
real D1 database ID. Never commit the ID placeholder as if it were a working
deployment and never store `EXPORT_TOKEN` in Git.

After creating the D1 database, replace `REPLACE_WITH_D1_DATABASE_ID` in
`wrangler.jsonc`, apply the migration, deploy the Worker, and configure the
secret:

```bash
pnpm install
pnpm exec wrangler login
pnpm run db:migrate:remote
pnpm run deploy
pnpm exec wrangler secret put EXPORT_TOKEN
```

The Cron expression is committed in `wrangler.jsonc`; treat it as the source of
truth instead of creating a different schedule in the Cloudflare UI.

## Health and export

`GET /health` reports the latest run and accumulated row/time coverage without
exposing station-level data.

`GET /export.csv` requires `Authorization: Bearer <EXPORT_TOKEN>`. It accepts:

- `start`: inclusive `YYYY-MM-DD` in Asia/Taipei, or an ISO timestamp with timezone.
- `end`: inclusive date in Asia/Taipei, or an exclusive ISO timestamp with timezone.
- `station_id`: optional exact station filter.
- `cursor`: internal pagination cursor returned in `x-next-cursor`.

Use the root Python client to combine all pages atomically:

```bash
export TRACK_B_EXPORT_URL="https://<worker>.workers.dev/export.csv"
export TRACK_B_EXPORT_TOKEN="$(security find-generic-password \
  -a "$USER" -s youbike-track-b-export -w)"
python src/export_track_b.py \
  --start 2026-08-21 \
  --end 2026-08-27 \
  --output data/processed/track_b_week_1.csv
```

The CLI defaults to bounded six-hour query windows and resets the cursor at
each boundary. It retries transient network, HTTP 429, and 5xx page failures
without duplicating already written pages. Authentication errors are not
retried. Use `--window-hours` only when a different bounded range is justified.

Add `--station-id 500101001` to export one station. Stored and exported times
are UTC ISO-8601. Convert them to `Asia/Taipei` explicitly in the Python feature
pipeline when calendar features are built.

See `docs/STAGE_11_TRACK_B_CLOUD_COLLECTION.md` for the architecture decision,
data-volume estimate, limitations, and owner deployment checklist.
# v7 read-only live demonstration (2026-09-27)

The collector now also serves `GET /demo/live`: only the fixed 12 Phase 4 stations' latest observations, 30m persistence and original Stage 17 60m HGB. No parameters, arbitrary dates/stations, historical rows, model trees or secrets are returned. POST is rejected. Existing `/export.csv` authorization, scheduled collection, D1 schema and `*/5 * * * *` remain unchanged.

The frozen numerical HGB export is server-only. `src/export_live_hgb.py` in the repository root verifies original joblib/metadata/config hashes and generates trees plus 72 historical serving-parity fixtures without fitting. `node --test test/*.test.mjs` includes feature/output parity, current/history freshness, missing-history, station/inference failures, clipping and endpoint access tests. [Protocol](../../docs/LIVE_DEMO_PROTOCOL.md) · [deployment and acceptance](../../docs/LIVE_DEMO_DELIVERY.md).

Queries use the existing `(station_id, snapshot_time)` key, at most 16 rows per station within 65 minutes, with a 30-second edge cache. This adds bounded reads, not new stored data or schema. D1/Worker usage remains billed under the account's existing plan; this record makes no free-tier guarantee. Deployment handover may create closely spaced scheduled keys; no rows are deleted and strict live history gates can suppress HGB until a continuous one-hour history is available. This is separate from the frozen research dataset.
