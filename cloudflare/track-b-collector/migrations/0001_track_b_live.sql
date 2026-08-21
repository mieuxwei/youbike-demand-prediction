CREATE TABLE IF NOT EXISTS station_snapshots (
    snapshot_time TEXT NOT NULL,
    source_update_time TEXT NOT NULL,
    station_update_time TEXT NOT NULL,
    station_id TEXT NOT NULL,
    station_name TEXT NOT NULL,
    available_bikes INTEGER NOT NULL CHECK (available_bikes >= 0),
    available_return_bikes INTEGER NOT NULL CHECK (available_return_bikes >= 0),
    capacity INTEGER NOT NULL CHECK (capacity >= 0),
    latitude REAL NOT NULL CHECK (latitude BETWEEN -90 AND 90),
    longitude REAL NOT NULL CHECK (longitude BETWEEN -180 AND 180),
    is_active INTEGER NOT NULL CHECK (is_active IN (0, 1)),
    PRIMARY KEY (station_id, snapshot_time),
    CHECK (available_bikes + available_return_bikes <= capacity)
) WITHOUT ROWID;

CREATE INDEX IF NOT EXISTS idx_station_snapshots_time
ON station_snapshots(snapshot_time);

CREATE TABLE IF NOT EXISTS collection_runs (
    scheduled_time TEXT PRIMARY KEY,
    started_at TEXT NOT NULL,
    finished_at TEXT NOT NULL,
    status TEXT NOT NULL CHECK (status IN ('success', 'failure')),
    attempts INTEGER NOT NULL CHECK (attempts >= 1),
    station_count INTEGER NOT NULL DEFAULT 0 CHECK (station_count >= 0),
    inserted_count INTEGER NOT NULL DEFAULT 0 CHECK (inserted_count >= 0),
    source_update_time TEXT,
    error_type TEXT,
    error_message TEXT
);

CREATE INDEX IF NOT EXISTS idx_collection_runs_status_time
ON collection_runs(status, scheduled_time);

PRAGMA optimize;
