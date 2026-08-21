import assert from "node:assert/strict";
import test from "node:test";

import {
  CollectorError,
  fetchSnapshot,
  fetchSnapshotWithRetry,
  parseExportRange,
  parseTaipeiTimestamp,
  runScheduledCollection,
  transformApiPayload,
} from "../src/index.mjs";

function validRecord(overrides = {}) {
  return {
    srcUpdateTime: "2026-08-20 21:14:52",
    mday: "2026-08-20 21:14:03",
    sno: "500101001",
    sna: "YouBike2.0_捷運科技大樓站",
    Quantity: 28,
    available_rent_bikes: 24,
    available_return_bikes: 4,
    latitude: 25.02605,
    longitude: 121.5436,
    act: "1",
    ...overrides,
  };
}

function fakeDb(insertChanges = 1) {
  const calls = [];
  return {
    calls,
    prepare(sql) {
      return {
        bind(...values) {
          calls.push({ sql, values });
          return {
            async run() {
              return {
                meta: {
                  changes: sql.includes("INSERT OR IGNORE INTO station_snapshots")
                    ? insertChanges
                    : 1,
                },
              };
            },
          };
        },
      };
    },
  };
}

test("transforms the confirmed official schema into UTC storage rows", () => {
  const [row] = transformApiPayload(
    [validRecord()],
    "2026-08-20T13:15:00.000Z",
  );

  assert.equal(row.snapshot_time, "2026-08-20T13:15:00.000Z");
  assert.equal(row.source_update_time, "2026-08-20T13:14:52.000Z");
  assert.equal(row.station_update_time, "2026-08-20T13:14:03.000Z");
  assert.equal(row.station_id, "500101001");
  assert.equal(row.available_bikes, 24);
  assert.equal(row.available_return_bikes, 4);
  assert.equal(row.capacity, 28);
  assert.equal(row.latitude, 25.02605);
  assert.equal(row.longitude, 121.5436);
  assert.equal(row.is_active, 1);
});

test("rejects missing required API fields", () => {
  const record = validRecord();
  delete record.available_return_bikes;

  assert.throws(
    () => transformApiPayload([record], "2026-08-20T13:15:00Z"),
    /missing: available_return_bikes/,
  );
});

test("rejects duplicate station ids inside one snapshot", () => {
  assert.throws(
    () =>
      transformApiPayload(
        [validRecord(), validRecord()],
        "2026-08-20T13:15:00Z",
      ),
    /Duplicate station_id/,
  );
});

test("converts Asia Taipei timestamps explicitly and rejects invalid dates", () => {
  assert.equal(
    parseTaipeiTimestamp("2026-08-20 21:14:52"),
    "2026-08-20T13:14:52.000Z",
  );
  assert.throws(
    () => parseTaipeiTimestamp("2026-02-31 10:00:00"),
    /not a valid calendar time/,
  );
});

test("retries HTTP failures without changing the scheduled snapshot time", async () => {
  let attempts = 0;
  const sleeps = [];
  const result = await fetchSnapshotWithRetry({
    snapshotTime: "2026-08-20T13:15:00Z",
    attempts: 3,
    sleep: async (milliseconds) => sleeps.push(milliseconds),
    fetchImpl: async () => {
      attempts += 1;
      if (attempts < 3) return new Response("failure", { status: 503 });
      return Response.json([validRecord()]);
    },
  });

  assert.equal(result.attempts, 3);
  assert.equal(result.rows[0].snapshot_time, "2026-08-20T13:15:00.000Z");
  assert.deepEqual(sleeps, [250, 1000]);
});

test("reports malformed and empty API responses", async () => {
  await assert.rejects(
    fetchSnapshot({
      snapshotTime: "2026-08-20T13:15:00Z",
      fetchImpl: async () => new Response("not-json"),
    }),
    (error) => error instanceof CollectorError && error.category === "malformed_response",
  );
  await assert.rejects(
    fetchSnapshot({
      snapshotTime: "2026-08-20T13:15:00Z",
      fetchImpl: async () => Response.json([]),
    }),
    (error) => error instanceof CollectorError && error.category === "empty_response",
  );
});

test("interprets date-only export ranges in Asia Taipei", () => {
  assert.deepEqual(parseExportRange("2026-08-20", "2026-08-20"), {
    startIso: "2026-08-19T16:00:00.000Z",
    endIso: "2026-08-20T16:00:00.000Z",
  });
});

test("scheduled collection stores rows and a successful run log", async () => {
  const DB = fakeDb(1);
  const result = await runScheduledCollection(
    { DB, YOUBIKE_API_URL: "https://example.test/youbike.json" },
    new Date("2026-08-20T13:15:00Z"),
    { fetchImpl: async () => Response.json([validRecord()]), sleep: async () => {} },
  );

  assert.deepEqual(result, { stationCount: 1, insertedCount: 1, attempts: 1 });
  assert.equal(DB.calls.length, 2);
  assert.match(DB.calls[0].sql, /json_each\(\?1\)/);
  assert.equal(DB.calls[1].values[3], "success");
  assert.equal(DB.calls[1].values[5], 1);
  assert.equal(DB.calls[1].values[6], 1);
});

test("exhausted API retries persist a failed collection run", async () => {
  const DB = fakeDb();
  await assert.rejects(
    runScheduledCollection(
      { DB, YOUBIKE_API_URL: "https://example.test/youbike.json" },
      new Date("2026-08-20T13:15:00Z"),
      {
        attempts: 2,
        fetchImpl: async () => new Response("failure", { status: 503 }),
        sleep: async () => {},
      },
    ),
    /HTTP 503/,
  );

  assert.equal(DB.calls.length, 1);
  assert.equal(DB.calls[0].values[3], "failure");
  assert.equal(DB.calls[0].values[4], 2);
  assert.equal(DB.calls[0].values[8], "http_error");
});
