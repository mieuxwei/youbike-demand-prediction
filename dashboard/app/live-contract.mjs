export const LIVE_URL = 'https://youbike-track-b-collector.mieuxander.workers.dev/demo/live';
export const MODEL_SHA = 'd4bc2df1c815a7c722e900891b668d3b2a7124f66966913081cb957b5ec7e6f6';
export const IDS = ['500101001','500101031','500101109','500101141','500101171','500101201','500101231','500101260','500106147','500112001','500119070','500119102'];
const timestamp = x => typeof x === 'string' && x.endsWith('Z') && Number.isFinite(Date.parse(x));
export function validateLive(value) {
  if (!value || value.schema_version !== 1 || value.model_sha256 !== MODEL_SHA || !timestamp(value.generated_at) ||
      !value.run || !['scheduled_time','started_at','finished_at'].every(k=>timestamp(value.run[k])) ||
      !Array.isArray(value.stations) || value.stations.length !== IDS.length) throw new Error('資料格式不符合展示規約');
  for (let i=0;i<IDS.length;i++) {
    const s=value.stations[i], o=s?.observation;
    if (s?.station_id !== IDS[i] || typeof s.station_name !== 'string' || typeof s.status_30m !== 'string' || typeof s.status_60m !== 'string') throw new Error('站點範圍異常');
    if (o && (!['snapshot_time','source_update_time','station_update_time'].every(k=>timestamp(o[k])) ||
      !['available_bikes','available_return_bikes','capacity'].every(k=>Number.isSafeInteger(o[k])&&o[k]>=0) ||
      o.available_bikes+o.available_return_bikes>o.capacity || o.snapshot_time!==value.run.scheduled_time)) throw new Error('站點觀測格式異常');
    for(const m of [30,60]) {
      const f=s[`forecast_${m}m`];
      if (f && (!o || s[`status_${m}m`] !== 'ok' || !timestamp(s.valid_until) || !timestamp(f.target_time) ||
        !Number.isFinite(f.bikes) || f.bikes<0 || f.bikes>o.capacity ||
        Date.parse(f.target_time)!==Date.parse(o.snapshot_time)+m*60_000 ||
        f.method!==(m===30?'persistence':'stage17_hgb'))) throw new Error('預測格式異常');
    }
  }
  return value;
}
export function clientBlock(payload, station, now) {
  if (Date.parse(payload.generated_at)>now+120_000) return '裝置時間與伺服器不一致，暫停預測';
  if (now-Date.parse(payload.generated_at)>120_000) return '超過兩分鐘未取得新回應，暫停預測';
  if (station.valid_until && now>=Date.parse(station.valid_until)) return '資料已超過十分鐘有效期，暫停預測';
  return null;
}
