import { test } from 'node:test';
import assert from 'node:assert/strict';
import { IDS, MODEL_SHA, validateLive, clientBlock } from '../app/live-contract.mjs';
const at='2026-09-27T08:00:00.000Z', now=Date.parse(at);
function fixture(){return{schema_version:1,model_sha256:MODEL_SHA,generated_at:at,run:{scheduled_time:at,started_at:at,finished_at:at},stations:IDS.map(station_id=>({station_id,station_name:'測試站',status_30m:'ok',status_60m:'missing_hour_history',observation:{snapshot_time:at,source_update_time:at,station_update_time:at,available_bikes:5,available_return_bikes:5,capacity:10},valid_until:'2026-09-27T08:10:00.000Z',forecast_30m:{bikes:5,method:'persistence',target_time:'2026-09-27T08:30:00.000Z'},forecast_60m:null}))};}
test('strict live response contract rejects wrong model, scope and impossible predictions',()=>{
  assert.equal(validateLive(fixture()).stations.length,12);
  for(const mutate of [p=>p.model_sha256='wrong',p=>p.stations.pop(),p=>p.stations[0].forecast_30m.bikes=999,p=>p.stations[0].forecast_30m.target_time=at]){
    const p=fixture();mutate(p);assert.throws(()=>validateLive(p));
  }
});
test('stale response, client clock anomaly and expiry fail closed without another fetch',()=>{
  const p=fixture(),s=p.stations[0];assert.equal(clientBlock(p,s,now),null);
  assert.match(clientBlock(p,s,now+121_000),/兩分鐘/);
  assert.match(clientBlock(p,s,now-121_000),/時間/);
  p.generated_at='2026-09-27T08:10:00.000Z';assert.match(clientBlock(p,s,now+600_000),/十分鐘/);
});
