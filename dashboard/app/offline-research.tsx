"use client";

import { useState } from "react";
import research from "./offline-research-data.json";

const labels: Record<string, string> = { persistence: "Persistence", hgb: "HGB（同序列資訊）", lstm_ensemble: "LSTM（三種子平均）" };
const methods = { no_transfer: "不調度", greedy: "簡單逐車貪婪規則", milp: "整數最佳化 MILP" };
type Method = keyof typeof methods;
const fmt = (n: number) => n.toFixed(3);

export default function OfflineResearch() {
  const [scenarioIndex, setScenarioIndex] = useState(0);
  const [variantIndex, setVariantIndex] = useState(0);
  const [method, setMethod] = useState<Method>("milp");
  const scenario = research.scenarios[scenarioIndex];
  const variant = scenario.variants[variantIndex];
  const plan = variant.plans[method];
  const stationName = (id: string) => scenario.stations.find((s) => s.station_id === id)?.station_name.replace("YouBike2.0_", "") ?? id;

  return (
    <section id="track-b" className="offline-research" aria-labelledby="offline-title">
      <div className="section-heading">
        <div><p className="section-index">04 / 固定資料研究與模擬</p><h2 id="offline-title">從可用車預測，到有限資源的調度模擬</h2></div>
      </div>
      <p className="research-notice">離線研究原型 · 不是目前即時車況，也不是營運調度指令。Track B 預測站點庫存；不可和上方 Track A 的每小時轉乘借車量混用。</p>

      <details className="research-evidence">
        <summary>既有 Track B 獨立驗證：保留原 Stage 19 結論</summary>
        <p>2026/09/19 02:30 至 09/26 02:30（臺北時間，不含終點）。原 30m 保留 persistence，60m HGB 小幅改善；不與下方 64 站回溯研究混成同一排行榜。</p>
        <div className="table-wrap"><table><thead><tr><th>時間</th><th>模型</th><th>Rows</th><th>MAE</th><th>RMSE</th></tr></thead><tbody>
          {research.legacy_track_b.metrics.map((row) => <tr key={`${row.horizon_minutes}-${row.model}`}><td>{row.horizon_minutes}m</td><td>{row.model.includes("persistence") ? "Persistence" : "原 HGB"}</td><td>{row.rows.toLocaleString()}</td><td>{fmt(row.mae)}</td><td>{fmt(row.rmse)}</td></tr>)}
        </tbody></table></div>
      </details>

      <h3>Phase 3 · 60 分鐘 LSTM 回溯比較</h3>
      <p>固定資料 2026/08/21–09/18 UTC；沿用 18／5／5 日切分。{research.station_count} 個訓練期選定站點，{research.rows.toLocaleString()} 個共同有效評估序列。評估窗為 09/13 09:45:02 至 09/18 09:45:02 UTC；既有資料已被檢視，本輪不是新的獨立驗證。</p>
      <div className="table-wrap"><table><thead><tr><th>模型</th><th>MAE（輛）</th><th>RMSE</th><th>R²</th><th>訓練秒數</th><th>推論秒數</th></tr></thead><tbody>
        {research.models.map((row) => <tr key={row.model}><td>{labels[row.model]}</td><td>{fmt(row.mae)}</td><td>{fmt(row.rmse)}</td><td>{fmt(row.r2)}</td><td>{row.training_seconds.toFixed(2)}</td><td>{row.inference_seconds.toFixed(3)}</td></tr>)}
      </tbody></table></div>
      <p><strong>結論：</strong>LSTM 優於 persistence，但未超越 HGB；本版不採用 LSTM 作調度預測器。三個種子全部保留，沒有選測試分數最好的種子。HGB 在回溯評估前就依 validation 選定。</p>
      <details className="research-evidence"><summary>LSTM 種子與比較限制</summary>
        <ul>{research.seed_results.map((row) => <li key={row.model}>{row.model}：MAE {fmt(row.mae)}、RMSE {fmt(row.rmse)}</li>)}</ul>
        <p>兩種模型使用同一約 60 分鐘、13 步歷史資訊；HGB 為 flattened sequence，LSTM 為單層 32 hidden units。不同表示方式、有限設定與有限資料仍限制架構結論。時間為本機 CPU 實測，推論不含載入與標準化，不能當成服務延遲保證。</p>
      </details>

      <h3>Phase 4 · 單次庫存調度模擬</h3>
      <p>12 站與 12 個情境事先固定，沒有挑選改善最大的案例。目標為容量 50%；距離是座標大圓距離代理，不是道路路線。調度假設立即生效，未來庫存＝固定預測＋調入－調出，不模擬行為回饋。</p>
      <div className="simulation-controls">
        <label>歷史決策情境<select aria-label="歷史決策情境" value={scenarioIndex} onChange={(event) => setScenarioIndex(Number(event.target.value))}>{research.scenarios.map((s, i) => <option value={i} key={s.requested}>{s.requested}</option>)}</select></label>
        <label>固定敏感度設定<select aria-label="固定敏感度設定" value={variantIndex} onChange={(event) => setVariantIndex(Number(event.target.value))}>{scenario.variants.map((v, i) => <option value={i} key={v.name}>{v.name} · 最多 {v.budget} 輛／距離權重 {v.cost}</option>)}</select></label>
        <label>查看方案<select aria-label="查看方案" value={method} onChange={(event) => setMethod(event.target.value as Method)}>{Object.entries(methods).map(([key, label]) => <option value={key} key={key}>{label}</option>)}</select></label>
      </div>
      <p>觀測時間：{scenario.snapshot_time}（UTC）｜最多搬 {variant.budget} 輛、{variant.bike_km_budget} bike-km｜距離成本權重 {variant.cost}、每輛處理成本 {variant.handling_cost}。全部為研究假設，非業者成本。只能搬決策當下已有的車，且不可超過模擬空位容量。</p>
      <div className="table-wrap"><table><thead><tr><th>共同條件方案</th><th>目標函數</th><th>庫存目標偏差</th><th>搬運成本項</th><th>搬運輛數</th></tr></thead><tbody>
        {(Object.keys(methods) as Method[]).map((key) => <tr key={key}><td>{methods[key]}</td><td>{fmt(variant.plans[key].objective)}</td><td>{fmt(variant.plans[key].target_deviation)}</td><td>{fmt(variant.plans[key].transfer_penalty)}</td><td>{variant.plans[key].moved_bikes}</td></tr>)}
      </tbody></table></div>
      <p className="research-notice" aria-live="polite">目前方案：{methods[method]} · 搬運 {plan.moved_bikes} 輛 · 限制檢查通過 · {plan.moved_bikes === 0 ? "本設定不調度" : "車輛守恆，符合當下庫存、容量與資源限制"}。基本設定下 MILP 與 greedy 的目標值在 12 個案例全部相同，不能宣稱最佳化全面優於簡單規則。</p>
      <div className="table-wrap"><table><thead><tr><th>站點</th><th>歷史觀測車數</th><th>容量</th><th>60m 預測</th><th>調入－調出</th><th>模擬 60m 庫存</th></tr></thead><tbody>
        {scenario.stations.map((s, i) => <tr key={s.station_id}><td>{stationName(s.station_id)}</td><td>{s.current_bikes}</td><td>{s.capacity}</td><td>{s.forecast.toFixed(2)}</td><td>{plan.post_transfer_current[i] - s.current_bikes}</td><td>{plan.projected_future[i].toFixed(2)}</td></tr>)}
      </tbody></table></div>
      <h4>站點間搬運明細</h4>
      {plan.transfers.length ? <div className="table-wrap"><table><thead><tr><th>來源</th><th>目的</th><th>輛數</th><th>距離代理 km</th></tr></thead><tbody>{plan.transfers.map((t) => <tr key={`${t.from}-${t.to}`}><td>{stationName(t.from)}</td><td>{stationName(t.to)}</td><td>{t.bikes}</td><td>{t.distance_km_proxy.toFixed(2)}</td></tr>)}</tbody></table></div> : <p>無搬運；零資源、高成本或無改善時，維持不調度。</p>}
      <p>模擬偏差不是損失旅次或缺車機率，目標函數降低不代表真實營運收益。上游資料可能延遲，排程時間不等於擷取完成；不提供即時保證、多車路線或正式調度服務。</p>
    </section>
  );
}
