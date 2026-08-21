# Track B Cloud Live Collector

This standalone Cloudflare Worker collects the official Taipei YouBike station
availability feed every five minutes and stores validated station-time rows in
D1. It is separate from the historical Vinext dashboard and from Track A model
training.

## Architecture

```text
Cloudflare Cron (*/5 * * * *)
        -> Worker validation and retry
        -> D1 station_snapshots + collection_runs
        -> protected /export.csv endpoint
        -> src/export_track_b.py
        -> local CSV for the Python feature pipeline
```

D1 is the primary store because Track B needs indexed station-and-time queries.
R2 is not enabled in this stage. A raw JSON archive can be added later only if a
retention or audit requirement justifies the extra storage and synchronization.

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
export TRACK_B_EXPORT_TOKEN="<secret>"
python src/export_track_b.py \
  --start 2026-08-21 \
  --end 2026-08-27 \
  --output data/processed/track_b_week_1.csv
```

Add `--station-id 500101001` to export one station. Stored and exported times
are UTC ISO-8601. Convert them to `Asia/Taipei` explicitly in the Python feature
pipeline when calendar features are built.

See `docs/STAGE_11_TRACK_B_CLOUD_COLLECTION.md` for the architecture decision,
data-volume estimate, limitations, and owner deployment checklist.
