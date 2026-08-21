"use client";

import { useState } from "react";
import data from "./dashboard-data.json";

type Station = (typeof data.targets)[number]["stations"][number];

const number = new Intl.NumberFormat("zh-TW", { maximumFractionDigits: 0 });

function Mark() {
  return (
    <span className="brand-mark" aria-hidden="true">
      <svg viewBox="0 0 48 48" role="img">
        <circle cx="13" cy="34" r="8" />
        <circle cx="36" cy="34" r="8" />
        <path d="m13 34 8-17h7l8 17M18 25h14M21 17l-3-5h7" />
      </svg>
    </span>
  );
}

function ArrowIcon() {
  return (
    <svg viewBox="0 0 20 20" aria-hidden="true">
      <path d="m5 8 5 5 5-5" />
    </svg>
  );
}

export default function Home() {
  const [targetId, setTargetId] = useState(data.targets.at(-1)?.id ?? "");
  const [query, setQuery] = useState("");
  const [showAll, setShowAll] = useState(false);
  const target = data.targets.find((item) => item.id === targetId) ?? data.targets[0];
  const topStations = target.stations.slice(0, 8);
  const maxPrediction = Math.max(...topStations.map((station) => station.predicted));
  const normalizedQuery = query.trim().toLocaleLowerCase("zh-TW");
  const matchedStations = normalizedQuery
    ? target.stations.filter((station) =>
        station.station.toLocaleLowerCase("zh-TW").includes(normalizedQuery),
      )
    : target.stations;
  const stationRows =
    showAll || normalizedQuery ? matchedStations : matchedStations.slice(0, 10);

  return (
    <main>
      <header className="site-header">
        <a className="brand" href="#top" aria-label="回到頁首">
          <Mark />
          <span>
            <strong>YouBike</strong>
            <small>需求觀測站</small>
          </span>
        </a>
        <nav aria-label="主要導覽">
          <a href="#forecast">需求預測</a>
          <a href="#model">模型表現</a>
          <a href="#method">研究說明</a>
        </nav>
        <span className="status-pill"><i />歷史回測模式</span>
      </header>

      <section className="hero" id="top">
        <div className="hero-copy">
          <p className="eyebrow">TAIPEI · 2023 TRANSFER DEMAND</p>
          <h1>看見城市<br /><em>下一小時</em>的流動</h1>
          <p className="hero-lead">
            用 2023 全年歷史轉乘資料與天氣，預測臺北 100 個高需求站點的每小時借車需求。
          </p>
          <div className="hero-actions">
            <a className="primary-button" href="#forecast">探索預測 <span>↘</span></a>
            <a className="text-link" href="#method">了解資料限制 <span>→</span></a>
          </div>
        </div>
        <div className="hero-visual" aria-label="模型摘要">
          <div className="orbit orbit-one" />
          <div className="orbit orbit-two" />
          <div className="bike-glyph"><Mark /></div>
          <div className="metric-float metric-r2">
            <span>TEST R²</span><strong>{data.meta.testMetrics.r2}</strong>
          </div>
          <div className="metric-float metric-stations">
            <strong>{data.meta.stationCount}</strong><span>個觀測站點</span>
          </div>
          <div className="route route-a" /><div className="route route-b" />
        </div>
        <div className="hero-footnote">
          <span>MODEL</span>
          <strong>{data.meta.model}</strong>
          <span>HOLDOUT</span>
          <strong>{data.meta.testPeriod}</strong>
        </div>
      </section>

      <section className="forecast-section" id="forecast">
        <div className="section-heading">
          <div>
            <p className="section-index">01 / 歷史預測</p>
            <h2>選一個時刻，看看站點需求</h2>
          </div>
          <label className="target-select">
            <span>回測時段</span>
            <select value={targetId} onChange={(event) => setTargetId(event.target.value)}>
              {data.targets.map((item) => (
                <option value={item.id} key={item.id}>
                  {item.dateLabel} {item.weekdayLabel} · {item.timeLabel}
                </option>
              ))}
            </select>
            <ArrowIcon />
          </label>
        </div>

        <div className="snapshot-grid">
          <article className="time-card">
            <span className="card-label">TARGET HOUR</span>
            <strong className="giant-time">{target.timeLabel}</strong>
            <p>{target.dateLabel} · {target.weekdayLabel} · {target.periodLabel}</p>
            <div className="weather-row">
              <span>{target.weather.isRaining ? "☂" : "☀"} {target.weather.isRaining ? "有雨" : "無雨"}</span>
              <span>{target.weather.temperatureC}°C</span>
              <span>濕度 {target.weather.humidityPercent}%</span>
            </div>
          </article>
          <article className="kpi-card accent-card">
            <span className="card-label">預測借車總量</span>
            <strong>{number.format(target.summary.totalPredicted)}</strong>
            <p>100 站合計 · 輛次／小時</p>
          </article>
          <article className="kpi-card">
            <span className="card-label">實際借車總量</span>
            <strong>{number.format(target.summary.totalActual)}</strong>
            <p>回測資料 · 輛次／小時</p>
          </article>
          <article className="kpi-card">
            <span className="card-label">本時段 MAE</span>
            <strong>{target.summary.mae.toFixed(2)}</strong>
            <p>每站平均絕對誤差</p>
          </article>
        </div>

        <div className="analysis-grid">
          <article className="chart-panel">
            <div className="panel-heading">
              <div><span>預測排名</span><h3>高需求站點 TOP 8</h3></div>
              <div className="legend"><i className="predicted-dot" />預測 <i className="actual-dot" />實際</div>
            </div>
            <div className="bar-chart">
              {topStations.map((station) => (
                <div className="bar-row" key={station.station}>
                  <span className="bar-rank">{String(station.rank).padStart(2, "0")}</span>
                  <span className="bar-name" title={station.station}>{station.station}</span>
                  <div className="bar-track">
                    <i className="bar predicted" style={{ width: `${(station.predicted / maxPrediction) * 100}%` }} />
                    <i className="bar actual" style={{ width: `${(station.actual / maxPrediction) * 100}%` }} />
                  </div>
                  <strong>{station.predicted.toFixed(1)}</strong>
                </div>
              ))}
            </div>
          </article>

          <aside className="insight-panel">
            <p className="section-index">本時段觀察</p>
            <div className="insight-number">01</div>
            <h3>{target.summary.largestDemandStation}</h3>
            <p>模型判斷此站是這個時段的最高需求站點。排名用於理解歷史需求分布，不等同即時缺車風險。</p>
            <dl>
              <div><dt>降雨量</dt><dd>{target.weather.precipitationMm} mm</dd></div>
              <div><dt>風速</dt><dd>{target.weather.windSpeedKmh} km/h</dd></div>
            </dl>
          </aside>
        </div>

        <article className="station-panel">
          <div className="panel-heading table-heading">
            <div><span>完整明細</span><h3>站點預測與誤差</h3></div>
            <label className="search-box">
              <svg viewBox="0 0 20 20" aria-hidden="true"><circle cx="8.5" cy="8.5" r="5.5" /><path d="m13 13 4 4" /></svg>
              <input value={query} onChange={(event) => setQuery(event.target.value)} placeholder="搜尋站點" aria-label="搜尋站點" />
            </label>
          </div>
          <div className="table-wrap">
            <table>
              <thead><tr><th>排名</th><th>站點</th><th>預測借車</th><th>實際借車</th><th>絕對誤差</th></tr></thead>
              <tbody>
                {stationRows.map((station: Station) => (
                  <tr key={station.station}>
                    <td><span className="rank-chip">{String(station.rank).padStart(2, "0")}</span></td>
                    <td>{station.station}</td>
                    <td><strong>{station.predicted.toFixed(2)}</strong></td>
                    <td>{station.actual.toFixed(0)}</td>
                    <td>{station.absoluteError.toFixed(2)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
          {!query && (
            <button className="show-button" onClick={() => setShowAll((value) => !value)}>
              {showAll ? "收合站點" : `查看全部 ${target.stations.length} 站`} <span>{showAll ? "↑" : "↓"}</span>
            </button>
          )}
        </article>
      </section>

      <section className="model-section" id="model">
        <div className="section-heading light-heading">
          <div><p className="section-index">02 / 模型表現</p><h2>不只看一次漂亮的分數</h2></div>
          <p>使用時間順序切分與三段滾動驗證，避免把未來資訊洩漏給模型。</p>
        </div>
        <div className="model-grid">
          <article className="score-card">
            <span>2023 年 12 月留出測試</span>
            <div className="score-main"><strong>{data.meta.testMetrics.mae}</strong><em>MAE</em></div>
            <div className="score-details"><p><b>{data.meta.testMetrics.rmse}</b> RMSE</p><p><b>{data.meta.testMetrics.r2}</b> R²</p></div>
          </article>
          <article className="comparison-card">
            <div className="panel-heading"><div><span>相同測試集</span><h3>模型 MAE 比較</h3></div><small>越低越好</small></div>
            <div className="model-bars">
              {data.modelComparison.map((model) => (
                <div className={model.model === "hist_gradient_boosting_weather" ? "best" : ""} key={model.model}>
                  <span>{model.label}</span><i style={{ width: `${(model.mae / 2.5) * 100}%` }} /><strong>{model.mae.toFixed(3)}</strong>
                </div>
              ))}
            </div>
          </article>
          <article className="rolling-card">
            <div className="panel-heading"><div><span>EXPANDING WINDOW</span><h3>滾動驗證</h3></div></div>
            <div className="rolling-list">
              {data.rollingOrigin.map((fold, index) => (
                <div key={fold.fold}><span>0{index + 1}</span><p>{fold.period}<small>驗證區間</small></p><strong>{fold.mae.toFixed(3)}<small>MAE</small></strong></div>
              ))}
            </div>
          </article>
        </div>
        <article className="importance-card">
          <div><p className="section-index">模型在看什麼？</p><h3>需求主要由時間與歷史訊號驅動</h3><p>置換特徵後造成的 MAE 增幅越大，代表該特徵越重要。天氣帶來小幅增益，但不是主要預測來源。</p></div>
          <div className="importance-bars">
            {data.featureImportance.slice(0, 6).map((feature) => (
              <div key={feature.feature}><span>{feature.label}</span><i><b style={{ width: `${(feature.mae_increase_mean / data.featureImportance[0].mae_increase_mean) * 100}%` }} /></i><strong>{feature.mae_increase_mean.toFixed(3)}</strong></div>
            ))}
          </div>
        </article>
      </section>

      <section className="method-section" id="method">
        <div className="method-title"><p className="section-index">03 / 研究說明</p><h2>把模型成果，放回正確的脈絡</h2></div>
        <div className="method-grid">
          <article><span>01</span><h3>預測的是什麼</h3><p>100 個高需求站點、每小時、與公車或捷運轉乘相關的借車量。</p></article>
          <article><span>02</span><h3>資料來自哪裡</h3><p>2023 官方轉乘旅次，搭配臺北單一參考點的歷史天氣再分析資料。</p></article>
          <article><span>03</span><h3>不是什麼</h3><p>不是所有 YouBike 旅次，也不是即時可借車數、30／60 分鐘缺車風險或調度建議。</p></article>
        </div>
        <div className="pipeline" aria-label="研究流程">
          <span>歷史旅次</span><i>→</i><span>時間＋Lag 特徵</span><i>→</i><span>HGB 模型</span><i>→</i><span>站點需求排名</span>
        </div>
      </section>

      <footer>
        <div className="brand"><Mark /><span><strong>YouBike</strong><small>需求觀測站</small></span></div>
        <p>資料科學作品集 · 歷史回測展示</p>
        <a href="#top">回到頁首 ↑</a>
      </footer>
    </main>
  );
}
