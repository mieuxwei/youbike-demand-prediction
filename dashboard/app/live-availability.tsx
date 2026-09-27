"use client";

import { useEffect, useRef, useState } from 'react';
import { LIVE_URL, IDS, validateLive, clientBlock, type LiveData } from './live-contract.mjs';

const reasons: Record<string,string> = {
  missing_observation:'最新成功快照沒有此站', invalid_observation:'站點資料不完整或容量不合理',
  unsupported_station:'模型展示不支援此站', station_inactive:'站點目前未啟用',
  stale_data:'來源或排程資料超過十分鐘', source_time_anomaly:'來源或擷取時間異常／過舊',
  missing_hour_history:'缺少完整一小時歷史', history_gap:'歷史時間序列缺漏或重複',
  missing_lag:'缺少符合時間規則的 lag', invalid_history:'歷史含停用或無效觀測',
  stale_history_source:'歷史含過舊或異常來源時間', station_changed:'歷史期間容量或位置改變',
  station_location_changed:'站點位置與固定研究範圍不同', invalid_features:'特徵資料不完整',
  inference_failed:'模型推論失敗，暫不顯示估計',
};
const localTime = (value: string) => new Date(value).toLocaleString('zh-TW', {timeZone:'Asia/Taipei',hour12:false});
const age = (value: string, now: number) => {
  const seconds=Math.floor((now-Date.parse(value))/1000);
  return seconds<0 ? `較裝置時間晚 ${-seconds} 秒` : `${Math.floor(seconds/60)} 分 ${seconds%60} 秒`;
};
const bikes = (value: number) => value.toLocaleString('zh-TW',{maximumFractionDigits:1});

export default function LiveAvailability() {
  const [payload,setPayload]=useState<LiveData|null>(null);
  const [selected,setSelected]=useState(IDS[0]);
  const [pending,setPending]=useState(true);
  const [error,setError]=useState('');
  const [now,setNow]=useState(0);
  const [refresh,setRefresh]=useState(0);
  const busy=useRef(false);
  useEffect(()=>{
    let alive=true; let controller: AbortController | null=null;
    const load=async()=>{
      if(busy.current)return;
      busy.current=true;setPending(true);controller=new AbortController();
      const timeout=setTimeout(()=>controller?.abort(),15_000);
      try {
        const response=await fetch(LIVE_URL,{signal:controller.signal,credentials:'omit',cache:'no-store'});
        if(!response.ok)throw new Error(`資料服務暫時無法使用（HTTP ${response.status}）`);
        const next=validateLive(await response.json());
        if(alive){setPayload(next);setError('');setNow(Date.now());}
      } catch(e) {
        if(alive){setPayload(null);setError(e instanceof Error && e.name!=='AbortError'?e.message:'讀取逾時，暫不顯示即時觀測或預測');}
      } finally {clearTimeout(timeout);busy.current=false;if(alive)setPending(false);}
    };
    void load(); const interval=setInterval(()=>void load(),60_000);
    return()=>{alive=false;controller?.abort();clearInterval(interval);busy.current=false;};
  },[refresh]);
  useEffect(()=>{const timer=setInterval(()=>setNow(Date.now()),1000);return()=>clearInterval(timer);},[]);
  const station=payload?.stations.find(s=>s.station_id===selected);
  const block=payload&&station?clientBlock(payload,station,now):null;
  const observation=station?.observation;
  const currentHealthy=station?.status_30m==='ok'&&!block;
  const f30=!block?station?.forecast_30m:null;
  const f60=!block?station?.forecast_60m:null;
  return <section className="live-section" id="live" aria-labelledby="live-title">
    <div className="section-heading"><div><p className="section-index">LIVE / TRACK B · 2026</p><h2 id="live-title">此刻的車況，下一小時的估計</h2></div>
      <button className="primary-button" disabled={pending} onClick={()=>setRefresh(r=>r+1)}>{pending?'讀取中…':'更新車況'} <span>↻</span></button></div>
    <p className="live-intro">目前觀測來自臺北市官方資料，每五分鐘蒐集；本頁每分鐘更新。預測的是<strong>可用車數</strong>，不是借車量或缺車機率。時間均為 Asia/Taipei（UTC+8）。</p>
    <div className="live-state" role="status" aria-live="polite">{error?`連線失敗：${error}`:pending?'正在讀取官方快照與伺服端預測…':`已讀取固定 ${payload?.stations.length ?? 0} 站；請留意各站資料狀態。`}</div>
    {payload&&station&&<>
      <label className="live-select">展示站點 <select value={selected} onChange={e=>setSelected(e.target.value)}>{payload.stations.map(s=><option key={s.station_id} value={s.station_id}>{s.station_name.replace('YouBike2.0_','')}</option>)}</select></label>
      <p className="live-station-id">站點 {station.station_id} · 固定 12 站，並非全市樣本</p>
      <div className="live-cards">
        <article className="live-card"><p className="card-label">{currentHealthy?'目前觀測':'最近觀測（非即時或不可用）'}</p><h3>可借／可還</h3>
          <p className="live-number">{observation?`${observation.available_bikes} / ${observation.available_return_bikes}`:'—'} <small>輛／空位</small></p>
          <p>站點容量 {observation?.capacity??'—'}；可還空位不一定等於容量減車數。</p></article>
        <article className="live-card"><p className="card-label">未來估計 · +30 MIN</p><h3>Persistence 基準</h3>
          <p className="live-number">{f30?bikes(f30.bikes):'—'} <small>輛</small></p><p>假設目前車數保持不變，<strong>不是學習模型</strong>。</p>
          <p>{f30?`目標時間 ${localTime(f30.target_time)}`:block||reasons[station.status_30m]||'預測不可用'}</p></article>
        <article className="live-card live-model"><p className="card-label">未來估計 · +60 MIN</p><h3>已凍結 HGB 模型</h3>
          <p className="live-number">{f60?bikes(f60.bikes):'—'} <small>輛</small></p><p>Stage 17 訓練、Stage 19 獨立驗證；不是 Phase 3 新模型。</p>
          <p>{f60?`目標時間 ${localTime(f60.target_time)}`:block||reasons[station.status_60m]||'預測不可用'}</p></article>
      </div>
      <dl className="live-times">
        <div><dt>官方來源時間／資料年齡</dt><dd>{observation?`${localTime(observation.source_update_time)} · ${age(observation.source_update_time,now)}`:'—'}</dd></div>
        <div><dt>排程快照時間（預測起點）</dt><dd>{localTime(payload.run.scheduled_time)} · {age(payload.run.scheduled_time,now)}</dd></div>
        <div><dt>擷取開始 → 寫入完成</dt><dd>{localTime(payload.run.started_at)} → {localTime(payload.run.finished_at)}</dd></div>
        <div><dt>站點更新／本次服務回應</dt><dd>{observation?localTime(observation.station_update_time):'—'} ／ {localTime(payload.generated_at)}</dd></div>
      </dl>
      <p className="live-warning">{block??(!currentHealthy?reasons[station.status_30m]:station.status_60m!=='ok'?`60 分鐘估計已停止：${reasons[station.status_60m]??'資料不可用'}`:'預測值已限制於 0 至站點容量；小數是模型估計，不保證到站時仍有車。')}</p>
    </>}
    <details className="live-details"><summary>站點選擇、模型證據與失效規則</summary>
      <p>沿用 Phase 4 的完整 12 站：從訓練期固定 64 站中，取編號最小站及座標距離最近的 11 站。未依 live 預測表現挑站。任何站缺歷史都保留並說明原因。</p>
      <p>獨立七天驗證：30m persistence MAE 1.950；60m HGB MAE 2.813，persistence 2.862，僅改善 1.71%。這是既有研究整體範圍，不是本頁 12 站的即時準確度或信賴區間。</p>
      <p>使用一小時 past-only 歷史、15／30／60m lag、臺北日曆。來源或快照超過十分鐘停止預測；缺一小時歷史、異常來源、停用、站點變動或推論失敗時不顯示 HGB。無法連線時不以舊值冒充 live。</p>
      <p>官方 srcUpdateTime 與 mday 分別是來源／站點更新；排程時間不是精確實體觀測時間。模型約預測快照後 60 分鐘（研究 target 容差 0–2 分鐘），不是網頁開啟後再加一小時。</p>
      <p>固定模型 SHA-256：<code className="live-sha">{payload?.model_sha256??'d4bc2df1c815a7c722e900891b668d3b2a7124f66966913081cb957b5ec7e6f6'}</code>。不使用瀏覽器內模型、匯出憑證或完整歷史資料。</p>
    </details>
  </section>;
}
