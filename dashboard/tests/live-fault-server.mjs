// Local-only browser QA. Never imported by the application or production build.
// Usage: node tests/live-fault-server.mjs /absolute/path/to/public-summary.json
import http from 'node:http';
import { readFile } from 'node:fs/promises';
import { resolve, extname } from 'node:path';
import { fileURLToPath } from 'node:url';
import worker from '../dist/server/index.js';
const fixture = JSON.parse(await readFile(process.argv[2], 'utf8'));
const assets = fileURLToPath(new URL('../dist/client/', import.meta.url));
const endpoint = 'https://youbike-track-b-collector.mieuxander.workers.dev/demo/live';
const modes = ['failure','stale','missing-history','inference-failure','loading'];
http.createServer(async (req,res)=>{
  try {
    const url = new URL(req.url,'http://127.0.0.1:3091');
    if (url.pathname !== '/') {
      const path=resolve(assets, `.${decodeURIComponent(url.pathname)}`);
      if(!path.startsWith(assets))throw new Error('Invalid asset');
      const types={'.js':'text/javascript','.css':'text/css','.png':'image/png','.svg':'image/svg+xml','.woff2':'font/woff2'};
      res.setHeader('content-type',types[extname(path)]??'application/octet-stream');
      res.end(await readFile(path));return;
    }
    const mode=url.searchParams.get('mode');
    if(!modes.includes(mode)){res.writeHead(400);res.end('Choose an explicit local QA mode');return;}
    const shift=Date.now()-60_000-Date.parse(fixture.run.scheduled_time);
    const p=JSON.parse(JSON.stringify(fixture),(_k,v)=>typeof v==='string'&&/^2026-.*Z$/.test(v)?new Date(Date.parse(v)+shift).toISOString():v);
    p.generated_at=new Date().toISOString();
    for(const s of p.stations){
      if(mode==='stale'){
        s.status_30m=s.status_60m='stale_data';s.forecast_30m=s.forecast_60m=null;s.valid_until=null;
        s.observation.source_update_time=new Date(Date.now()-11*60_000).toISOString();
      }else if(mode==='missing-history'||mode==='inference-failure'){
        s.forecast_60m=null;s.status_60m=mode==='missing-history'?'missing_hour_history':'inference_failed';
      }
    }
    const response=await worker.fetch(new Request(url,{headers:{accept:'text/html'}}),{ASSETS:{fetch:async()=>new Response('',{status:404})}},{waitUntil(){},passThroughOnException(){}});
    const shim=`<script>const nativeFetch=window.fetch;window.fetch=(...args)=>{if(String(args[0])!==${JSON.stringify(endpoint)})return nativeFetch(...args);const mode=${JSON.stringify(mode)};if(mode==='loading')return new Promise((resolve,reject)=>args[1].signal.addEventListener('abort',()=>reject(new DOMException('Aborted','AbortError'))));return Promise.resolve(new Response(JSON.stringify(${JSON.stringify(p)}),{status:mode==='failure'?503:200,headers:{'content-type':'application/json'}}));};</script>`;
    const html=(await response.text()).replace('</head>',`${shim}</head>`).replace('<body>','<body><aside style="position:fixed;bottom:0;z-index:9999;background:#7b1424;color:white;padding:10px">LOCAL QA ONLY — simulated '+mode+'; not live observations</aside>');
    res.setHeader('content-type','text/html; charset=utf-8');res.end(html);
  }catch{res.writeHead(404);res.end('Local QA asset unavailable');}
}).listen(3091,'127.0.0.1',()=>console.log('Local fault harness: http://127.0.0.1:3091/?mode=failure#live (temporary; no production mutation)'));
