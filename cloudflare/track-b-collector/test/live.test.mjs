import { test } from 'node:test';
import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import worker from '../src/index.mjs';
import { buildFeatures, predictRaw, stationForecast, demoPayload, STATIONS, MODEL_SHA } from '../src/live.mjs';

const fixtures = JSON.parse(readFileSync(new URL('./live-parity.json', import.meta.url)));
const sample = fixtures.cases[0];
const current = sample.history.at(-1);
const now = Date.parse(current.snapshot_time) + 60_000;
const run = { scheduled_time: current.snapshot_time, started_at: current.snapshot_time, finished_at: new Date(now).toISOString() };
const station = STATIONS[0];
const copy = () => structuredClone(sample.history);

test('72 fixed real historical origins: all 23 features and original Python HGB outputs match', () => {
  assert.equal(fixtures.model_sha256, MODEL_SHA);
  assert.equal(fixtures.cases.length, 72);
  let maxFeature = 0, maxPrediction = 0;
  for (const c of fixtures.cases) {
    const features = buildFeatures(c.history);
    for (let i=0; i<23; i++) {
      const delta = Math.abs(features[i] - c.features[i]);
      maxFeature = Math.max(maxFeature, delta);
      assert.ok(delta <= 1e-7, `${c.station_id} feature ${i}: ${features[i]} != ${c.features[i]}`);
    }
    const prediction = predictRaw(features);
    maxPrediction = Math.max(maxPrediction, Math.abs(prediction - c.raw_prediction));
    assert.ok(Math.abs(prediction - c.raw_prediction) <= 1e-8);
    assert.ok(Math.abs(Math.max(0,Math.min(c.history.at(-1).capacity,prediction))-c.prediction) <= 1e-8);
  }
  console.log(JSON.stringify({ parity_cases: 72, max_feature_error: maxFeature, max_prediction_error: maxPrediction }));
});

test('calendar Taipei midnight/weekend, past-only rolling and backward-only lag', () => {
  const c = fixtures.cases[5];
  const f = buildFeatures(c.history);
  assert.equal(f[7], 0); assert.equal(f[8], 1); assert.equal(f[11], 1);
  const history = copy(); history.at(-1).available_bikes = 1;
  assert.equal(buildFeatures(history)[19], buildFeatures(sample.history)[19]);
  const desired = Date.parse(current.snapshot_time) - 15*60_000;
  const noBackward = copy().filter(r => !(Date.parse(r.snapshot_time) <= desired && Date.parse(r.snapshot_time) >= desired-120_000));
  assert.throws(() => buildFeatures(noBackward), /missing_lag/);
});

test('valid original-model serving, persistence and capacity clipping', () => {
  const output = stationForecast(station, copy(), run, now);
  assert.equal(output.status_30m, 'ok'); assert.equal(output.status_60m, 'ok');
  assert.equal(output.forecast_30m.bikes, current.available_bikes);
  assert.ok(Math.abs(output.forecast_60m.bikes - sample.prediction) < 1e-8);
  assert.equal(stationForecast(station, copy(), run, now, () => -3).forecast_60m.bikes, 0);
  assert.equal(stationForecast(station, copy(), run, now, () => 999).forecast_60m.bikes, current.capacity);
});

test('stale/malformed/future source or inactive current suppresses predictions', () => {
  assert.equal(stationForecast(station, copy(), run, now+600_000).forecast_30m, null);
  for (const value of ['bad','2099-01-01T00:00:00Z','2020-01-01T00:00:00Z']) {
    const h=copy(); h.at(-1).source_update_time=value;
    const r=stationForecast(station,h,run,now); assert.equal(r.forecast_60m,null); assert.equal(r.forecast_30m,null);
  }
  const h=copy();h.at(-1).is_active=0;
  assert.equal(stationForecast(station,h,run,now).status_60m,'station_inactive');
});

test('missing hour, duplicate time, gap, inactive or stale history suppress HGB only', () => {
  const variants=[copy().slice(-10), copy().filter((_,i)=>i!==5), [...copy(),current]];
  const inactive=copy();inactive[4].is_active=0;variants.push(inactive);
  const stale=copy();stale[4].source_update_time='2020-01-01T00:00:00Z';variants.push(stale);
  const changed=copy();changed[4].capacity+=1;variants.push(changed);
  for(const h of variants){const r=stationForecast(station,h,run,now);assert.equal(r.forecast_60m,null);assert.equal(r.status_30m,'ok');}
});

test('unsupported station and inference failures never silently fall back to HGB label', () => {
  assert.equal(stationForecast({station_id:'unknown'},[],run,now).status_60m,'unsupported_station');
  assert.equal(stationForecast(station,copy(),run,now,()=>{throw new Error('secret details');}).status_60m,'inference_failed');
  assert.equal(stationForecast(station,copy(),run,now,()=>NaN).forecast_60m,null);
});

test('bounded endpoint, read-only statements, model/history/credentials excluded', async () => {
  const statements=[];
  const db={prepare(sql){statements.push(sql);return{first:async()=>run,bind(...args){assert.equal(args.length,3);return{sql,args};}};},
    async batch(queries){assert.equal(queries.length,12);return queries.map(q=>({success:true,results:fixtures.cases.find(c=>c.station_id===q.args[0]).history}));}};
  const payload=await demoPayload(db,now);
  assert.equal(payload.stations.length,12);
  assert.ok(statements.every(sql=>/^\s*SELECT/.test(sql)));
  assert.ok(statements.slice(1).every(sql=>sql.includes('LIMIT 16')&&sql.includes('station_id = ?')));
  const text=JSON.stringify(payload);
  for(const forbidden of ['trees','features','history":','EXPORT_TOKEN','raw_prediction'])assert.ok(!text.includes(forbidden));
  const bad=await worker.fetch(new Request('https://demo/demo/live?station_id=anything'),{DB:db});assert.equal(bad.status,400);
  const post=await worker.fetch(new Request('https://demo/demo/live',{method:'POST'}),{DB:db});assert.equal(post.status,405);
  const exp=await worker.fetch(new Request('https://demo/export.csv'),{EXPORT_TOKEN:'test-secret'});assert.equal(exp.status,401);
  const failure=await worker.fetch(new Request('https://demo/demo/live'),{DB:{prepare(){throw new Error('private SQL');}}});
  assert.equal(failure.status,503);assert.ok(!(await failure.text()).includes('private SQL'));
});
