const DEFAULT_API_URL =
  "https://tcgbusfs.blob.core.windows.net/dotapp/youbike/v2/youbike_immediate.json";
const DEFAULT_TIMEOUT_MS = 15_000;
const MAX_RETRIES = 3;
const RETRY_DELAYS_MS = [250, 1_000];
const MAX_EXPORT_PAGE_SIZE = 25_000;

export const REQUIRED_API_FIELDS = [
  "srcUpdateTime",
  "mday",
  "sno",
  "sna",
  "Quantity",
  "available_rent_bikes",
  "available_return_bikes",
  "latitude",
  "longitude",
  "act",
];

export class CollectorError extends Error {
  constructor(category, message, options = {}) {
    super(message, options);
    this.name = "CollectorError";
    this.category = category;
  }
}

function requireNonEmptyString(value, field, index) {
  if (typeof value !== "string" || value.trim() === "") {
    throw new CollectorError(
      "schema_validation",
      `Station record ${index} has invalid ${field}`,
    );
  }
  return value.trim();
}

function requireNonNegativeInteger(value, field, index) {
  const parsed = typeof value === "string" && /^\d+$/.test(value) ? Number(value) : value;
  if (!Number.isSafeInteger(parsed) || parsed < 0) {
    throw new CollectorError(
      "schema_validation",
      `Station record ${index} has invalid ${field}`,
    );
  }
  return parsed;
}

function requireCoordinate(value, field, minimum, maximum, index) {
  const parsed = typeof value === "string" && value.trim() !== "" ? Number(value) : value;
  if (typeof parsed !== "number" || !Number.isFinite(parsed) || parsed < minimum || parsed > maximum) {
    throw new CollectorError(
      "schema_validation",
      `Station record ${index} has invalid ${field}`,
    );
  }
  return parsed;
}

export function parseTaipeiTimestamp(value, field = "timestamp") {
  if (typeof value !== "string") {
    throw new CollectorError("schema_validation", `${field} must be a string`);
  }
  const match = value.match(
    /^(\d{4})-(\d{2})-(\d{2})[ T](\d{2}):(\d{2}):(\d{2})$/,
  );
  if (!match) {
    throw new CollectorError(
      "schema_validation",
      `${field} must use YYYY-MM-DD HH:mm:ss`,
    );
  }
  const milliseconds = Date.parse(
    `${match[1]}-${match[2]}-${match[3]}T${match[4]}:${match[5]}:${match[6]}+08:00`,
  );
  if (!Number.isFinite(milliseconds)) {
    throw new CollectorError("schema_validation", `${field} is not a valid time`);
  }
  const parsed = new Date(milliseconds);
  const roundTrip = new Intl.DateTimeFormat("en-CA", {
    timeZone: "Asia/Taipei",
    year: "numeric",
    month: "2-digit",
    day: "2-digit",
    hour: "2-digit",
    minute: "2-digit",
    second: "2-digit",
    hourCycle: "h23",
  })
    .format(parsed)
    .replace(",", "");
  const expected = `${match[1]}-${match[2]}-${match[3]} ${match[4]}:${match[5]}:${match[6]}`;
  if (roundTrip !== expected) {
    throw new CollectorError("schema_validation", `${field} is not a valid calendar time`);
  }
  return parsed.toISOString();
}

export function transformApiPayload(payload, snapshotTime) {
  if (!Array.isArray(payload) || payload.length === 0) {
    throw new CollectorError(
      "empty_response",
      "YouBike API response must be a non-empty array",
    );
  }
  const parsedSnapshotTime = new Date(snapshotTime);
  if (!Number.isFinite(parsedSnapshotTime.getTime())) {
    throw new CollectorError("timestamp", "snapshot_time is invalid");
  }
  const snapshotIso = parsedSnapshotTime.toISOString();
  const seenStationIds = new Set();

  return payload.map((record, index) => {
    if (record === null || typeof record !== "object" || Array.isArray(record)) {
      throw new CollectorError(
        "schema_validation",
        `Station record ${index} is not an object`,
      );
    }
    const missing = REQUIRED_API_FIELDS.filter((field) => !(field in record));
    if (missing.length > 0) {
      throw new CollectorError(
        "schema_validation",
        `Station record ${index} is missing: ${missing.join(", ")}`,
      );
    }

    const stationId = requireNonEmptyString(record.sno, "sno", index);
    if (seenStationIds.has(stationId)) {
      throw new CollectorError(
        "schema_validation",
        `Duplicate station_id ${stationId} in one API response`,
      );
    }
    seenStationIds.add(stationId);

    const capacity = requireNonNegativeInteger(record.Quantity, "Quantity", index);
    const availableBikes = requireNonNegativeInteger(
      record.available_rent_bikes,
      "available_rent_bikes",
      index,
    );
    const availableReturnBikes = requireNonNegativeInteger(
      record.available_return_bikes,
      "available_return_bikes",
      index,
    );
    if (availableBikes + availableReturnBikes > capacity) {
      throw new CollectorError(
        "schema_validation",
        `Station record ${index} has availability greater than capacity`,
      );
    }

    const active = requireNonNegativeInteger(record.act, "act", index);
    if (active !== 0 && active !== 1) {
      throw new CollectorError(
        "schema_validation",
        `Station record ${index} has invalid act`,
      );
    }

    return {
      snapshot_time: snapshotIso,
      source_update_time: parseTaipeiTimestamp(
        record.srcUpdateTime,
        `record ${index} srcUpdateTime`,
      ),
      station_update_time: parseTaipeiTimestamp(
        record.mday,
        `record ${index} mday`,
      ),
      station_id: stationId,
      station_name: requireNonEmptyString(record.sna, "sna", index),
      available_bikes: availableBikes,
      available_return_bikes: availableReturnBikes,
      capacity,
      latitude: requireCoordinate(record.latitude, "latitude", -90, 90, index),
      longitude: requireCoordinate(record.longitude, "longitude", -180, 180, index),
      is_active: active,
    };
  });
}

export async function fetchSnapshot({
  url = DEFAULT_API_URL,
  snapshotTime,
  fetchImpl = fetch,
  timeoutMs = DEFAULT_TIMEOUT_MS,
}) {
  let response;
  try {
    response = await fetchImpl(url, {
      headers: { accept: "application/json" },
      signal: AbortSignal.timeout(timeoutMs),
    });
  } catch (error) {
    const category = error?.name === "TimeoutError" ? "timeout" : "network_error";
    throw new CollectorError(category, `YouBike API request failed: ${error.message}`, {
      cause: error,
    });
  }
  if (!response.ok) {
    throw new CollectorError(
      "http_error",
      `YouBike API returned HTTP ${response.status}`,
    );
  }
  let payload;
  try {
    payload = await response.json();
  } catch (error) {
    throw new CollectorError("malformed_response", "YouBike API returned invalid JSON", {
      cause: error,
    });
  }
  return transformApiPayload(payload, snapshotTime);
}

function delay(milliseconds) {
  return new Promise((resolve) => setTimeout(resolve, milliseconds));
}

export async function fetchSnapshotWithRetry(options) {
  const attempts = options.attempts ?? MAX_RETRIES;
  const sleep = options.sleep ?? delay;
  let lastError;
  for (let attempt = 1; attempt <= attempts; attempt += 1) {
    try {
      return { rows: await fetchSnapshot(options), attempts: attempt };
    } catch (error) {
      lastError = error;
      console.warn(
        JSON.stringify({
          event: "track_b_collection_attempt_failed",
          attempt,
          category: error.category ?? "unknown",
          message: error.message,
        }),
      );
      if (attempt < attempts) {
        await sleep(RETRY_DELAYS_MS[Math.min(attempt - 1, RETRY_DELAYS_MS.length - 1)]);
      }
    }
  }
  lastError.attempts = attempts;
  throw lastError;
}

const INSERT_SNAPSHOTS_SQL = `
INSERT OR IGNORE INTO station_snapshots (
  snapshot_time, source_update_time, station_update_time, station_id,
  station_name, available_bikes, available_return_bikes, capacity,
  latitude, longitude, is_active
)
SELECT
  json_extract(value, '$.snapshot_time'),
  json_extract(value, '$.source_update_time'),
  json_extract(value, '$.station_update_time'),
  json_extract(value, '$.station_id'),
  json_extract(value, '$.station_name'),
  json_extract(value, '$.available_bikes'),
  json_extract(value, '$.available_return_bikes'),
  json_extract(value, '$.capacity'),
  json_extract(value, '$.latitude'),
  json_extract(value, '$.longitude'),
  json_extract(value, '$.is_active')
FROM json_each(?1)
`;

const UPSERT_RUN_SQL = `
INSERT INTO collection_runs (
  scheduled_time, started_at, finished_at, status, attempts,
  station_count, inserted_count, source_update_time, error_type, error_message
) VALUES (?1, ?2, ?3, ?4, ?5, ?6, ?7, ?8, ?9, ?10)
ON CONFLICT(scheduled_time) DO UPDATE SET
  started_at = excluded.started_at,
  finished_at = excluded.finished_at,
  status = excluded.status,
  attempts = excluded.attempts,
  station_count = excluded.station_count,
  inserted_count = excluded.inserted_count,
  source_update_time = excluded.source_update_time,
  error_type = excluded.error_type,
  error_message = excluded.error_message
`;

async function saveRun(db, values) {
  return db
    .prepare(UPSERT_RUN_SQL)
    .bind(
      values.scheduledTime,
      values.startedAt,
      values.finishedAt,
      values.status,
      values.attempts,
      values.stationCount,
      values.insertedCount,
      values.sourceUpdateTime,
      values.errorType,
      values.errorMessage,
    )
    .run();
}

export async function runScheduledCollection(env, scheduledTime, options = {}) {
  const scheduledIso = new Date(scheduledTime).toISOString();
  const startedAt = new Date().toISOString();
  let attempts = 1;
  try {
    const fetched = await fetchSnapshotWithRetry({
      url: env.YOUBIKE_API_URL ?? DEFAULT_API_URL,
      snapshotTime: scheduledIso,
      fetchImpl: options.fetchImpl ?? fetch,
      sleep: options.sleep,
      attempts: options.attempts,
    });
    attempts = fetched.attempts;
    const insertResult = await env.DB.prepare(INSERT_SNAPSHOTS_SQL)
      .bind(JSON.stringify(fetched.rows))
      .run();
    const insertedCount = Number(insertResult.meta?.changes ?? 0);
    const sourceUpdateTime = fetched.rows
      .map((row) => row.source_update_time)
      .sort()
      .at(-1);
    const finishedAt = new Date().toISOString();
    await saveRun(env.DB, {
      scheduledTime: scheduledIso,
      startedAt,
      finishedAt,
      status: "success",
      attempts,
      stationCount: fetched.rows.length,
      insertedCount,
      sourceUpdateTime,
      errorType: null,
      errorMessage: null,
    });
    console.info(
      JSON.stringify({
        event: "track_b_collection_succeeded",
        scheduled_time: scheduledIso,
        source_update_time: sourceUpdateTime,
        station_count: fetched.rows.length,
        inserted_count: insertedCount,
        attempts,
      }),
    );
    return { stationCount: fetched.rows.length, insertedCount, attempts };
  } catch (error) {
    attempts = Number(error.attempts ?? attempts);
    const finishedAt = new Date().toISOString();
    const category = error.category ?? "storage_or_unknown";
    const message = String(error.message ?? error).slice(0, 500);
    try {
      await saveRun(env.DB, {
        scheduledTime: scheduledIso,
        startedAt,
        finishedAt,
        status: "failure",
        attempts,
        stationCount: 0,
        insertedCount: 0,
        sourceUpdateTime: null,
        errorType: category,
        errorMessage: message,
      });
    } catch (loggingError) {
      console.error(
        JSON.stringify({
          event: "track_b_collection_logging_failed",
          scheduled_time: scheduledIso,
          message: String(loggingError.message ?? loggingError),
        }),
      );
    }
    console.error(
      JSON.stringify({
        event: "track_b_collection_failed",
        scheduled_time: scheduledIso,
        category,
        message,
      }),
    );
    throw error;
  }
}

function dateOnlyBoundary(value, endExclusive) {
  if (!/^\d{4}-\d{2}-\d{2}$/.test(value)) return null;
  const base = Date.parse(`${value}T00:00:00+08:00`);
  if (!Number.isFinite(base)) return null;
  const local = new Intl.DateTimeFormat("en-CA", {
    timeZone: "Asia/Taipei",
    year: "numeric",
    month: "2-digit",
    day: "2-digit",
  }).format(new Date(base));
  if (local !== value) return null;
  return new Date(base + (endExclusive ? 86_400_000 : 0)).toISOString();
}

export function parseExportRange(start, end) {
  if (!start || !end) {
    throw new CollectorError("invalid_request", "start and end are required");
  }
  const parseBoundary = (value, endExclusive) => {
    const dateOnly = dateOnlyBoundary(value, endExclusive);
    if (/^\d{4}-\d{2}-\d{2}$/.test(value)) return dateOnly;
    if (!/(?:Z|[+-]\d{2}:\d{2})$/.test(value)) return null;
    const milliseconds = Date.parse(value);
    if (!Number.isFinite(milliseconds)) return null;
    return new Date(milliseconds).toISOString();
  };
  const startIso = parseBoundary(start, false);
  const endIso = parseBoundary(end, true);
  if (!startIso || !endIso) {
    throw new CollectorError("invalid_request", "start or end is invalid");
  }
  if (startIso >= endIso) {
    throw new CollectorError("invalid_request", "start must be before end");
  }
  return { startIso, endIso };
}

function encodeCursor(row) {
  return btoa(JSON.stringify([row.snapshot_time, row.station_id]))
    .replaceAll("+", "-")
    .replaceAll("/", "_")
    .replaceAll("=", "");
}

function decodeCursor(value) {
  if (!value) return null;
  try {
    const normalized = value.replaceAll("-", "+").replaceAll("_", "/");
    const [snapshotTime, stationId] = JSON.parse(atob(normalized));
    if (typeof snapshotTime !== "string" || typeof stationId !== "string") throw new Error();
    return { snapshotTime, stationId };
  } catch {
    throw new CollectorError("invalid_request", "cursor is invalid");
  }
}

function csvCell(value) {
  const text = value === null || value === undefined ? "" : String(value);
  return /[",\r\n]/.test(text) ? `"${text.replaceAll('"', '""')}"` : text;
}

async function exportCsv(request, env) {
  if (!env.EXPORT_TOKEN) {
    return Response.json({ error: "EXPORT_TOKEN is not configured" }, { status: 503 });
  }
  const authorization = request.headers.get("authorization") ?? "";
  if (authorization !== `Bearer ${env.EXPORT_TOKEN}`) {
    return Response.json({ error: "Unauthorized" }, { status: 401 });
  }
  const url = new URL(request.url);
  let range;
  let cursor;
  try {
    range = parseExportRange(url.searchParams.get("start"), url.searchParams.get("end"));
    cursor = decodeCursor(url.searchParams.get("cursor"));
  } catch (error) {
    return Response.json({ error: error.message }, { status: 400 });
  }
  const stationId = url.searchParams.get("station_id")?.trim() || null;
  const configuredPageSize = Number(env.EXPORT_PAGE_SIZE ?? 10_000);
  const requestedLimit = Number(url.searchParams.get("limit") ?? configuredPageSize);
  const limit = Math.min(
    Number.isSafeInteger(requestedLimit) && requestedLimit > 0 ? requestedLimit : configuredPageSize,
    MAX_EXPORT_PAGE_SIZE,
  );

  const predicates = ["snapshot_time >= ?", "snapshot_time < ?"];
  const bindings = [range.startIso, range.endIso];
  if (stationId) {
    predicates.push("station_id = ?");
    bindings.push(stationId);
  }
  if (cursor) {
    predicates.push("(snapshot_time > ? OR (snapshot_time = ? AND station_id > ?))");
    bindings.push(cursor.snapshotTime, cursor.snapshotTime, cursor.stationId);
  }
  bindings.push(limit + 1);
  const result = await env.DB.prepare(`
    SELECT snapshot_time, source_update_time, station_update_time,
           station_id, station_name, available_bikes,
           available_return_bikes, capacity, latitude, longitude, is_active
    FROM station_snapshots
    WHERE ${predicates.join(" AND ")}
    ORDER BY snapshot_time, station_id
    LIMIT ?
  `)
    .bind(...bindings)
    .all();
  const rows = result.results ?? [];
  const hasMore = rows.length > limit;
  const page = rows.slice(0, limit);
  const columns = [
    "snapshot_time",
    "source_update_time",
    "station_update_time",
    "station_id",
    "station_name",
    "available_bikes",
    "available_return_bikes",
    "capacity",
    "latitude",
    "longitude",
    "is_active",
  ];
  const csv = [
    columns.join(","),
    ...page.map((row) => columns.map((column) => csvCell(row[column])).join(",")),
  ].join("\n");
  const headers = new Headers({
    "content-type": "text/csv; charset=utf-8",
    "content-disposition": "attachment; filename=track_b_snapshots.csv",
    "cache-control": "no-store",
    "x-row-count": String(page.length),
  });
  if (hasMore && page.length > 0) {
    headers.set("x-next-cursor", encodeCursor(page.at(-1)));
  }
  return new Response(`${csv}\n`, { headers });
}

async function health(env) {
  const [run, coverage] = await Promise.all([
    env.DB.prepare(`
      SELECT scheduled_time, finished_at, status, attempts, station_count,
             inserted_count, source_update_time, error_type, error_message
      FROM collection_runs ORDER BY scheduled_time DESC LIMIT 1
    `).first(),
    env.DB.prepare(`
      SELECT COUNT(*) AS row_count, COUNT(DISTINCT snapshot_time) AS snapshot_count,
             MIN(snapshot_time) AS first_snapshot_time,
             MAX(snapshot_time) AS latest_snapshot_time
      FROM station_snapshots
    `).first(),
  ]);
  return Response.json(
    { service: "youbike-track-b-collector", schedule: "*/5 * * * * UTC", latest_run: run, coverage },
    { headers: { "cache-control": "no-store", "access-control-allow-origin": "*" } },
  );
}

export default {
  async scheduled(controller, env, ctx) {
    ctx.waitUntil(runScheduledCollection(env, new Date(controller.scheduledTime)));
  },
  async fetch(request, env) {
    const path = new URL(request.url).pathname;
    if (request.method === "GET" && path === "/health") return health(env);
    if (request.method === "GET" && path === "/export.csv") return exportCsv(request, env);
    return Response.json({ error: "Not found" }, { status: 404 });
  },
};
