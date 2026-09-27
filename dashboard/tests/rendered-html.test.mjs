import assert from "node:assert/strict";
import test from "node:test";
import { readFileSync, createReadStream } from "node:fs";
import { createHash } from "node:crypto";

async function render() {
  const workerUrl = new URL("../dist/server/index.js", import.meta.url);
  workerUrl.searchParams.set("test", `${process.pid}-${Date.now()}`);
  const { default: worker } = await import(workerUrl.href);
  return worker.fetch(new Request("http://localhost/", { headers: { accept: "text/html" } }), { ASSETS: { fetch: async () => new Response("Not found", { status: 404 }) } }, { waitUntil() {}, passThroughOnException() {} });
}

test("server-renders the historical demand dashboard", async () => {
  const response = await render();
  assert.equal(response.status, 200);
  const html = await response.text();
  assert.match(html, /YouBike 需求分析、可用車預測與調度模擬/);
  assert.match(html, /此刻的車況，下一小時的估計/);
  assert.match(html, /站點選擇、模型證據與失效規則/);
  assert.match(html, /看見城市/);
  assert.match(html, /歷史回測模式/);
  assert.match(html, /2023-12-01 至 2023-12-31/);
  assert.match(html, /XGBoost \+ 天氣/);
  assert.match(html, /Phase 3 · 60 分鐘 LSTM 回溯比較/);
  assert.match(html, /89,600/);
  assert.match(html, /Phase 4 · 單次庫存調度模擬/);
  assert.match(html, /歷史決策情境/);
  assert.match(html, /不是目前即時車況/);
  assert.doesNotMatch(html, /codex-preview|react-loading-skeleton|Your site is taking shape/);
});

test("research panel matches saved artifacts and retains every predefined scenario", async () => {
  const data = JSON.parse(readFileSync(new URL("../app/offline-research-data.json", import.meta.url)));
  assert.equal(data.rows, 89600);
  assert.equal(data.station_count, 64);
  assert.deepEqual(data.models.map((r) => r.model), ["persistence", "hgb", "lstm_ensemble"]);
  assert.equal(new Set(data.models.map((r) => r.sample_keys_sha256)).size, 1);
  assert.equal(data.scenarios.length, 12);
  assert.equal(data.scenarios[0].requested, "2026-09-14 07:00 Asia/Taipei");
  for (const scenario of data.scenarios) {
    assert.equal(scenario.stations.length, 12);
    assert.equal(scenario.variants.length, 6);
    for (const variant of scenario.variants) {
      for (const plan of Object.values(variant.plans)) assert.equal(plan.constraints_verified, true);
      if (variant.budget === 0 || variant.cost === 10) assert.equal(variant.plans.milp.moved_bikes, 0);
    }
  }
  for (const [path, expected] of Object.entries(data.source_sha256)) {
    const hash = createHash("sha256");
    for await (const chunk of createReadStream(new URL(`../../${path}`, import.meta.url))) hash.update(chunk);
    assert.equal(hash.digest("hex"), expected);
  }
});
