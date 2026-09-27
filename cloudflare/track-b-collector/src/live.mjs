import model from './live-model.json' with { type: 'json' };

export const STATIONS = model.stations;
export const MODEL_SHA = 'd4bc2df1c815a7c722e900891b668d3b2a7124f66966913081cb957b5ec7e6f6';
const MINUTE = 60_000;
const iso = (time) => new Date(time).toISOString();
const time = (value) => typeof value === 'string' && /Z$|[+-]\d\d:\d\d$/.test(value) ? Date.parse(value) : NaN;
const active = (row) => row.is_active === 1 || row.is_active === true;
const valid = (r) => r && Number.isFinite(time(r.snapshot_time)) &&
  ['available_bikes', 'available_return_bikes', 'capacity'].every(k => Number.isSafeInteger(r[k]) && r[k] >= 0) &&
  r.capacity > 0 && r.available_bikes + r.available_return_bikes <= r.capacity &&
  Number.isFinite(r.latitude) && Math.abs(r.latitude) <= 90 &&
  Number.isFinite(r.longitude) && Math.abs(r.longitude) <= 180;

export function buildFeatures(history) {
  const rows = [...history].sort((a, b) => time(a.snapshot_time) - time(b.snapshot_time));
  const current = rows.at(-1);
  if (!valid(current)) throw new Error('invalid_observation');
  const t = time(current.snapshot_time);
  if (rows.some(r => r.station_id !== current.station_id)) throw new Error('mixed_stations');
  const local = new Date(t + 8 * 60 * MINUTE);
  const hour = local.getUTCHours(), weekday = (local.getUTCDay() + 6) % 7;
  const f = [current.available_bikes, current.available_return_bikes, current.capacity,
    Math.fround(current.available_bikes / current.capacity), Math.fround(current.available_return_bikes / current.capacity),
    Math.fround(current.latitude), Math.fround(current.longitude),
    Math.fround(Math.sin(2 * Math.PI * hour / 24)), Math.fround(Math.cos(2 * Math.PI * hour / 24)),
    Math.fround(Math.sin(2 * Math.PI * weekday / 7)), Math.fround(Math.cos(2 * Math.PI * weekday / 7)),
    Number(weekday >= 5), Number((hour >= 7 && hour <= 9) || (hour >= 17 && hour <= 19))];
  for (const m of [15, 30, 60]) {
    const lag = rows.filter(r => time(r.snapshot_time) <= t - m * MINUTE && time(r.snapshot_time) >= t - (m + 2) * MINUTE).at(-1);
    if (!lag || !active(lag) || !active(current)) throw new Error('missing_lag');
    f.push(lag.available_bikes, current.available_bikes - lag.available_bikes);
  }
  for (const m of [30, 60]) {
    const past = rows.filter(r => time(r.snapshot_time) >= t - m * MINUTE && time(r.snapshot_time) < t && active(r));
    if (!past.length) throw new Error('missing_history');
    f.push(past.reduce((sum, r) => sum + r.available_bikes, 0) / past.length, past.length);
  }
  if (f.length !== 23 || !f.every(Number.isFinite)) throw new Error('invalid_features');
  return f;
}

// Numeric sklearn HGB trees: thresholds and leaf values are preserved as float64.
// Leaf values already contain the learning-rate multiplier; do not apply it twice.
export function predictRaw(features, forest = model) {
  if (forest.artifact_sha256 !== MODEL_SHA || forest.feature_columns.length !== 23 || features.length !== 23 ||
      !features.every(Number.isFinite) || forest.trees.length !== 120) throw new Error('model_contract');
  let value = forest.baseline;
  for (const tree of forest.trees) {
    let index = 0, steps = 0;
    while (!tree[index]?.[6]) {
      if (++steps > tree.length || !tree[index]) throw new Error('invalid_tree');
      const [feature, threshold, missingLeft, left, right] = tree[index];
      const x = features[feature];
      index = Number.isNaN(x) ? (missingLeft ? left : right) : (x <= threshold ? left : right);
    }
    value += tree[index][5];
  }
  if (!Number.isFinite(value)) throw new Error('inference_failed');
  return value;
}

function sourceValid(row, reference) {
  const source = time(row.source_update_time), snapshot = time(row.snapshot_time);
  return Number.isFinite(source) && snapshot - source <= 10 * MINUTE && source <= reference + MINUTE;
}

export function stationForecast(station, rows, run, now = Date.now(), infer = predictRaw) {
  const result = { station_id: station.station_id, station_name: station.station_name,
    observation: null, forecast_30m: null, forecast_60m: null, valid_until: null,
    status_30m: 'missing_observation', status_60m: 'missing_observation' };
  const fail = (reason) => ({ ...result, status_30m: reason, status_60m: reason });
  if (!STATIONS.some(s => s.station_id === station.station_id)) return fail('unsupported_station');
  const history = rows.filter(r => r.station_id === station.station_id).sort((a,b) => time(a.snapshot_time) - time(b.snapshot_time));
  const current = history.at(-1);
  if (!current || current.snapshot_time !== run.scheduled_time) return fail('missing_observation');
  if (!valid(current)) return fail('invalid_observation');
  result.station_name = current.station_name;
  result.observation = Object.fromEntries(['snapshot_time', 'source_update_time', 'station_update_time',
    'available_bikes', 'available_return_bikes', 'capacity', 'is_active'].map(k => [k, current[k]]));
  const t = time(current.snapshot_time), source = time(current.source_update_time), finished = time(run.finished_at);
  if (!Number.isFinite(finished) || t > now + MINUTE || finished > now + MINUTE || finished < t ||
      !Number.isFinite(source) || source > now + MINUTE || !sourceValid(current, finished)) return fail('source_time_anomaly');
  if (now - t >= 10 * MINUTE || now - source >= 10 * MINUTE) return fail('stale_data');
  if (!active(current)) return fail('station_inactive');
  result.valid_until = iso(Math.min(t, source) + 10 * MINUTE);
  result.forecast_30m = { bikes: current.available_bikes, target_time: iso(t + 30 * MINUTE), method: 'persistence' };
  result.status_30m = 'ok';
  try {
    if (Math.abs(current.latitude - station.latitude) > 0.001 || Math.abs(current.longitude - station.longitude) > 0.001) throw new Error('station_location_changed');
    const relevant = history.filter(r => time(r.snapshot_time) >= t - 62 * MINUTE);
    if (!relevant.length || time(relevant[0].snapshot_time) > t - 60 * MINUTE) throw new Error('missing_hour_history');
    for (let i = 0; i < relevant.length; i++) {
      const r = relevant[i];
      if (!valid(r) || !active(r)) throw new Error('invalid_history');
      if (!sourceValid(r, time(r.snapshot_time) + MINUTE)) throw new Error('stale_history_source');
      if (r.capacity !== current.capacity || Math.abs(r.latitude - current.latitude) > 0.00001 || Math.abs(r.longitude - current.longitude) > 0.00001) throw new Error('station_changed');
      if (i) {
        const gap = time(r.snapshot_time) - time(relevant[i-1].snapshot_time);
        if (gap < 270_000 || gap > 330_000) throw new Error('history_gap');
      }
    }
    const prediction = infer(buildFeatures(history));
    if (!Number.isFinite(prediction)) throw new Error('inference_failed');
    result.forecast_60m = { bikes: Math.max(0, Math.min(current.capacity, prediction)), target_time: iso(t + 60 * MINUTE), method: 'stage17_hgb' };
    result.status_60m = 'ok';
  } catch (error) {
    const allowed = ['station_location_changed','missing_hour_history','invalid_history','stale_history_source','station_changed','history_gap','missing_lag','invalid_features'];
    result.status_60m = allowed.includes(error.message) ? error.message : 'inference_failed';
  }
  return result;
}

export async function demoPayload(db, now = Date.now()) {
  const run = await db.prepare(`SELECT scheduled_time, started_at, finished_at, source_update_time
    FROM collection_runs WHERE status = 'success' ORDER BY scheduled_time DESC LIMIT 1`).first();
  if (!run) throw new Error('No successful collection');
  const start = iso(time(run.scheduled_time) - 65 * MINUTE);
  const batches = await db.batch(STATIONS.map(station => db.prepare(`SELECT snapshot_time, source_update_time,
    station_update_time, station_id, station_name, available_bikes, available_return_bikes, capacity,
    latitude, longitude, is_active FROM station_snapshots
    WHERE station_id = ? AND snapshot_time >= ? AND snapshot_time <= ? ORDER BY snapshot_time DESC LIMIT 16`)
    .bind(station.station_id, start, run.scheduled_time)));
  if (batches.some(b => b.success === false)) throw new Error('History read failed');
  return { schema_version: 1, generated_at: iso(now), refresh_seconds: 60, max_age_seconds: 600,
    model_sha256: MODEL_SHA, selection: 'fixed_phase4_training_coordinate_cohort',
    source: 'Taipei City YouBike 2.0 official API via five-minute Cloudflare collector',
    run, stations: STATIONS.map((s, i) => stationForecast(s, batches[i].results ?? [], run, now)) };
}

export async function liveResponse(request, env, ctx) {
  const headers = { 'access-control-allow-origin': '*', 'cache-control': 'public, max-age=30', 'x-content-type-options': 'nosniff' };
  const url = new URL(request.url);
  if (url.search) return Response.json({ error: 'This endpoint accepts no query parameters' }, { status: 400, headers });
  if (request.method !== 'GET') return Response.json({ error: 'GET only' }, { status: 405, headers: { ...headers, allow: 'GET' } });
  const cache = globalThis.caches?.default;
  const key = new Request(`${url.origin}/demo/live`);
  const cached = await cache?.match(key);
  if (cached) return cached;
  try {
    const payload = await demoPayload(env.DB);
    const response = Response.json(payload, { headers });
    if (cache && ctx) ctx.waitUntil(cache.put(key, response.clone()));
    console.info(JSON.stringify({ event: 'track_b_demo', snapshot_time: payload.run.scheduled_time,
      stations: payload.stations.length, hgb_available: payload.stations.filter(s => s.forecast_60m).length }));
    return response;
  } catch {
    console.error(JSON.stringify({ event: 'track_b_demo_failed' }));
    return Response.json({ error: 'Live data temporarily unavailable' }, { status: 503, headers: { ...headers, 'cache-control': 'no-store' } });
  }
}
