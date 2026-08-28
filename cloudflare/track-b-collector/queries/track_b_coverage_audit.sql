-- Read-only Track B cloud coverage audit. Run with Wrangler against remote D1.

SELECT status,
       COUNT(*) AS runs,
       MIN(scheduled_time) AS first_run,
       MAX(scheduled_time) AS latest_run
FROM collection_runs
GROUP BY status
ORDER BY status;

SELECT COUNT(*) AS total_runs,
       SUM(CASE WHEN attempts > 1 THEN 1 ELSE 0 END) AS retried_runs,
       MIN(station_count) AS min_station_count,
       MAX(station_count) AS max_station_count,
       ROUND(AVG(station_count), 2) AS avg_station_count,
       SUM(inserted_count) AS inserted_rows
FROM collection_runs;

WITH ordered AS (
    SELECT scheduled_time,
           LAG(scheduled_time) OVER (ORDER BY scheduled_time) AS previous_time
    FROM collection_runs
    WHERE status = 'success'
), gaps AS (
    SELECT previous_time,
           scheduled_time,
           unixepoch(scheduled_time) - unixepoch(previous_time) AS gap_seconds
    FROM ordered
    WHERE previous_time IS NOT NULL
)
SELECT COUNT(*) AS intervals,
       SUM(CASE WHEN gap_seconds > 330 THEN 1 ELSE 0 END) AS gaps_over_5_5m,
       ROUND(AVG(gap_seconds), 2) AS avg_gap_seconds,
       MAX(gap_seconds) AS max_gap_seconds
FROM gaps;

WITH ordered AS (
    SELECT scheduled_time,
           LAG(scheduled_time) OVER (ORDER BY scheduled_time) AS previous_time
    FROM collection_runs
    WHERE status = 'success'
)
SELECT previous_time,
       scheduled_time,
       unixepoch(scheduled_time) - unixepoch(previous_time) AS gap_seconds,
       CAST((unixepoch(scheduled_time) - unixepoch(previous_time)) / 300 AS INTEGER) - 1
           AS estimated_missing_slots
FROM ordered
WHERE previous_time IS NOT NULL
  AND unixepoch(scheduled_time) - unixepoch(previous_time) > 330
ORDER BY previous_time;

-- Replace the lower bound with the first successful snapshot after any
-- deployment/setup gap when auditing a continuous modeling window.
SELECT COUNT(*) AS continuous_snapshots,
       SUM(station_count) AS continuous_station_rows,
       MIN(scheduled_time) AS continuous_first,
       MAX(scheduled_time) AS continuous_latest,
       ROUND(
           (unixepoch(MAX(scheduled_time)) - unixepoch(MIN(scheduled_time)))
               / 86400.0,
           4
       ) AS continuous_days
FROM collection_runs
WHERE status = 'success'
  AND scheduled_time >= '2026-08-21T09:45:02.000Z';

WITH times AS (
    SELECT scheduled_time
    FROM collection_runs
    WHERE status = 'success'
), coverage AS (
    SELECT current.scheduled_time,
           EXISTS(
               SELECT 1 FROM times future
               WHERE unixepoch(future.scheduled_time)
                   BETWEEN unixepoch(current.scheduled_time) + 1800
                       AND unixepoch(current.scheduled_time) + 1920
           ) AS has_30m,
           EXISTS(
               SELECT 1 FROM times future
               WHERE unixepoch(future.scheduled_time)
                   BETWEEN unixepoch(current.scheduled_time) + 3600
                       AND unixepoch(current.scheduled_time) + 3720
           ) AS has_60m
    FROM times current
)
SELECT COUNT(*) AS snapshots,
       SUM(has_30m) AS snapshots_with_30m,
       ROUND(100.0 * SUM(has_30m) / COUNT(*), 3) AS coverage_30m_percent,
       SUM(has_60m) AS snapshots_with_60m,
       ROUND(100.0 * SUM(has_60m) / COUNT(*), 3) AS coverage_60m_percent
FROM coverage;
