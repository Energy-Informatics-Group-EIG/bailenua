<?php
require __DIR__ . '/lib.php';
cfg();
$logged = is_logged_in();
header('X-Content-Type-Options: nosniff');
header('Referrer-Policy: no-referrer');
?><!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Baile Nua Data Viewer</title>
<style>
:root{
  color-scheme: light;
  --surface:#f6f6f4; --panel:#fcfcfb; --ink:#0b0b0b; --ink-2:#52514e; --ink-3:#7a7974; --line:#e3e2dc; --grid:#ecebe6;
  --accent:#2a78d6; --accent-ink:#ffffff; --err:#b3261e;
  --s1:#2a78d6; --s2:#eb6834; --s3:#1baf7a; --s4:#eda100; --s5:#e87ba4; --s6:#008300; --s7:#6250d6; --s8:#e34948; --other:#9a998f;
  --mono: ui-monospace, SFMono-Regular, Menlo, Consolas, monospace;
}
@media (prefers-color-scheme: dark){
  :root:where(:not([data-theme="light"])){
    color-scheme: dark;
    --surface:#121211; --panel:#1a1a19; --ink:#f0efec; --ink-2:#c3c2b7; --ink-3:#8f8e86; --line:#2f2e2b; --grid:#262624;
    --accent:#3987e5; --accent-ink:#0b0b0b; --err:#ff8a80;
    --s1:#3987e5; --s2:#d95926; --s3:#199e70; --s4:#c98500; --s5:#d55181; --s6:#008300; --s7:#9085e9; --s8:#e66767; --other:#6f6e67;
  }
}
:root[data-theme="dark"]{
  color-scheme: dark;
  --surface:#121211; --panel:#1a1a19; --ink:#f0efec; --ink-2:#c3c2b7; --ink-3:#8f8e86; --line:#2f2e2b; --grid:#262624;
  --accent:#3987e5; --accent-ink:#0b0b0b; --err:#ff8a80;
  --s1:#3987e5; --s2:#d95926; --s3:#199e70; --s4:#c98500; --s5:#d55181; --s6:#008300; --s7:#9085e9; --s8:#e66767; --other:#6f6e67;
}
*{box-sizing:border-box}
body{margin:0;background:var(--surface);color:var(--ink);font:14px/1.45 system-ui,-apple-system,"Segoe UI",Roboto,sans-serif}
header{display:flex;flex-wrap:wrap;gap:8px 16px;align-items:baseline;padding:14px 16px 0;background:var(--panel);border-bottom:1px solid var(--line)}
header h1{margin:0;font-size:17px;font-weight:650}
header .label{font-size:12px;color:var(--ink-2)}
header .right{margin-left:auto;display:flex;gap:8px;align-items:center}
nav{display:flex;gap:2px;overflow-x:auto;width:100%;margin-top:8px;scrollbar-width:thin}
nav button{border:0;background:none;color:var(--ink-2);padding:9px 12px;font:inherit;cursor:pointer;border-bottom:2px solid transparent;white-space:nowrap}
nav button[aria-selected="true"]{color:var(--ink);border-bottom-color:var(--accent);font-weight:600}
main{padding:16px;max-width:1500px;margin:0 auto}
.grid{display:grid;grid-template-columns:repeat(auto-fill,minmax(min(100%,520px),1fr));gap:14px}
.card{background:var(--panel);border:1px solid var(--line);border-radius:10px;padding:12px 14px;min-width:0}
.card.wide{grid-column:1/-1}
.card h3{margin:0 0 2px;font-size:14px;font-weight:620}
.card .meta{display:flex;gap:8px;align-items:center;justify-content:space-between;margin-bottom:6px}
.card .unit{font-size:12px;color:var(--ink-3)}
.card .note{font-size:12px;color:var(--ink-2);margin-top:6px}
.card .tools{display:flex;gap:6px;align-items:center}
.chartbox{position:relative;height:300px}
.chartbox.tall{height:420px}
select,button,input{font:inherit}
.btn{padding:5px 10px;border:1px solid var(--line);border-radius:7px;background:var(--surface);color:var(--ink);cursor:pointer;font-size:12px}
.btn.primary{background:var(--accent);border-color:var(--accent);color:var(--accent-ink)}
select.btn{padding:4px 6px}
.kpis{display:grid;grid-template-columns:repeat(auto-fit,minmax(170px,1fr));gap:10px}
.kpi{border:1px solid var(--line);border-radius:9px;padding:10px 12px;background:var(--surface)}
.kpi .v{font-size:24px;font-weight:650;letter-spacing:-.01em}
.kpi .l{font-size:12px;color:var(--ink-2)}
.kpi .s{font-size:11px;color:var(--ink-3)}
.tablewrap{overflow:auto;max-height:420px;border:1px solid var(--line);border-radius:8px}
table{border-collapse:collapse;font-size:12px;width:max-content;min-width:100%}
th,td{padding:4px 8px;border-bottom:1px solid var(--line);text-align:right;white-space:nowrap}
th:first-child,td:first-child{text-align:left}
th{position:sticky;top:0;background:var(--panel);color:var(--ink-2);font-weight:600}
td.ok{color:var(--s6)} td.bad{color:var(--err);font-weight:600}
.status{color:var(--ink-2);font-size:13px;padding:8px 0}
.status.err{color:var(--err)}
.heat{position:relative}
.heat canvas{width:100%;display:block}
.heat .legend{display:flex;align-items:center;gap:6px;font-size:11px;color:var(--ink-2);margin-top:6px}
.heat .legend i{display:block;height:8px;width:160px;border-radius:4px}
.figval{display:flex;align-items:baseline;justify-content:space-between;gap:8px;margin:-2px 0 8px}
.figval .v{font-size:22px;font-weight:650;letter-spacing:-.01em}
.badge{font-size:12px;font-weight:600;padding:2px 9px;border-radius:999px}
.badge.ok{background:#d9f2e3;color:#0b5d2a} .badge.warn{background:#fde7a6;color:#6b4a00} .badge.bad{background:#f9d0cc;color:#7d1a12}
.gbar{position:relative;height:10px;border-radius:6px;margin:10px 0 4px;background:linear-gradient(90deg,#66bd63,#d9ef8b,#fee08b,#fdae61,#f46d43)}
.gbar i{position:absolute;top:-4px;width:3px;height:18px;background:var(--ink);border-radius:2px}
.gbar-l{display:flex;justify-content:space-between;font-size:12px;color:var(--ink-2)}
.tip{position:fixed;pointer-events:none;background:var(--panel);color:var(--ink);border:1px solid var(--line);border-radius:6px;padding:4px 8px;font-size:12px;box-shadow:0 2px 8px rgba(0,0,0,.15);z-index:20;display:none}
.login{max-width:340px;margin:12vh auto;background:var(--panel);border:1px solid var(--line);border-radius:12px;padding:20px}
.login input{width:100%;padding:8px 10px;margin:8px 0 12px;border:1px solid var(--line);border-radius:8px;background:var(--surface);color:var(--ink)}
/* raw browser */
.raw{display:grid;grid-template-columns:minmax(240px,340px) 1fr;gap:14px}
@media (max-width:860px){.raw{grid-template-columns:1fr}}
.crumbs{font-family:var(--mono);font-size:12px;margin-bottom:6px;word-break:break-all}
.crumbs a{color:var(--accent);cursor:pointer}
ul.ls{list-style:none;margin:0;padding:0;max-height:65vh;overflow:auto;border-top:1px solid var(--line)}
ul.ls li{display:flex;justify-content:space-between;gap:8px;padding:5px 4px;border-bottom:1px solid var(--line);cursor:pointer;font-size:12px;font-family:var(--mono)}
ul.ls li:hover{background:var(--surface)}
ul.ls li span:last-child{color:var(--ink-3);font-family:inherit}
pre{font-family:var(--mono);font-size:12px;white-space:pre-wrap;word-break:break-word;max-height:60vh;overflow:auto;margin:0;background:var(--surface);padding:10px;border-radius:8px;border:1px solid var(--line)}
</style>
</head>
<body>
<?php if (!$logged): ?>
<div class="login">
  <h1 style="font-size:17px;margin:0 0 4px">Baile Nua Data Viewer</h1>
  <div style="font-size:12px;color:var(--ink-2)">Synthetic town data. Sign in to continue.</div>
  <form id="loginForm">
    <input type="password" id="pw" placeholder="Password" autocomplete="current-password" required>
    <button class="btn primary" type="submit">Sign in</button>
    <div class="status" id="loginStatus"></div>
  </form>
</div>
<script>
document.getElementById('loginForm').onsubmit = async (e) => {
  e.preventDefault();
  const fd = new FormData(); fd.append('password', document.getElementById('pw').value);
  const r = await fetch('api.php?a=login', {method:'POST', body:fd, credentials:'same-origin'});
  if (r.ok) location.reload(); else document.getElementById('loginStatus').textContent = 'Wrong password.';
};
</script>
<?php else: ?>
<header>
  <h1>Baile Nua Data Viewer</h1>
  <span class="label" id="releaseLabel">v1 release · loading…</span>
  <span class="right">
    <button class="btn" id="themeBtn" title="Toggle light/dark">Theme</button>
    <?php if (auth_required()): ?><button class="btn" id="logoutBtn">Sign out</button><?php endif; ?>
  </span>
  <nav id="tabs" role="tablist"></nav>
</header>
<main id="main"><div class="status">Loading figure index…</div></main>
<div class="tip" id="tip"></div>

<script src="https://cdn.jsdelivr.net/npm/chart.js@4.4.1/dist/chart.umd.js"></script>
<script type="module">
const $ = (s, el=document) => el.querySelector(s);
const API = (q) => fetch('api.php?' + new URLSearchParams(q), {credentials:'same-origin'}).then(async r => {
  if (r.status === 401) { location.reload(); throw new Error('login'); }
  if (!r.ok) { let m = r.status; try { m = (await r.json()).error || m; } catch(_){} throw new Error(m); }
  return r;
});
const esc = s => String(s ?? '').replace(/[&<>"]/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;'}[c]));
const css = n => getComputedStyle(document.documentElement).getPropertyValue(n).trim();
const SERIES = () => ['--s1','--s2','--s3','--s4','--s5','--s6','--s7','--s8'].map(css);
const fmt = v => v == null ? '–' : (typeof v === 'number' ? (Math.abs(v) >= 1000 ? v.toLocaleString(undefined,{maximumFractionDigits:0}) : v.toLocaleString(undefined,{maximumFractionDigits:2})) : String(v));

/* ---------- theme ---------- */
try { const t = localStorage.getItem('bn-theme'); if (t) document.documentElement.dataset.theme = t; } catch(_){}
$('#themeBtn').onclick = () => {
  const cur = document.documentElement.dataset.theme || (matchMedia('(prefers-color-scheme: dark)').matches ? 'dark' : 'light');
  const nxt = cur === 'dark' ? 'light' : 'dark';
  document.documentElement.dataset.theme = nxt;
  try { localStorage.setItem('bn-theme', nxt); } catch(_){}
  redrawAll();
};
const lo = $('#logoutBtn'); if (lo) lo.onclick = async () => { await fetch('api.php?a=logout',{method:'POST',credentials:'same-origin'}); location.reload(); };

/* ---------- state ---------- */
let INDEX = null;
const loaded = new Set();         // tabs already rendered
const live = [];                  // {fig, el, chart}
const tip = $('#tip');

/* ---------- tabs ---------- */
async function boot(){
  try {
    INDEX = await (await API({a:'index'})).json();
  } catch(e) {
    $('#main').innerHTML = `<div class="status err">Could not load the figure index: ${esc(e.message)}</div>`;
    INDEX = {tabs:[]};
  }
  $('#releaseLabel').textContent = `v1 release · figures built ${INDEX.built || '?'} · ${INDEX.label || ''}`;
  const tabs = [...(INDEX.tabs||[]), {id:'raw', title:'Raw files', figures:[]}];
  const nav = $('#tabs');
  nav.innerHTML = '';
  tabs.forEach(t => {
    const b = document.createElement('button');
    b.role = 'tab'; b.textContent = t.title; b.dataset.tab = t.id;
    b.onclick = () => show(t);
    nav.appendChild(b);
  });
  let want = location.hash.slice(1) || ((INDEX.tabs||[]).length ? '' : 'raw');
  show(tabs.find(t => t.id === want) || tabs[0]);
}
function show(tab){
  location.hash = tab.id;
  document.querySelectorAll('#tabs button').forEach(b => b.setAttribute('aria-selected', b.dataset.tab === tab.id));
  document.querySelectorAll('main > section').forEach(s => s.hidden = s.dataset.tab !== tab.id);
  $('#main > .status')?.remove();
  if (loaded.has(tab.id)) return;
  loaded.add(tab.id);
  const sec = document.createElement('section'); sec.dataset.tab = tab.id;
  $('#main').appendChild(sec);
  if (tab.id === 'raw') return rawBrowser(sec);
  const grid = document.createElement('div'); grid.className = 'grid'; sec.appendChild(grid);
  tab.figures.forEach(f => {
    const card = document.createElement('div'); card.className = 'card';
    card.innerHTML = `<div class="meta"><div><h3>${esc(f.title)}</h3><div class="unit"></div></div><div class="tools"></div></div><div class="body"><div class="status">Loading…</div></div><div class="note"></div>`;
    grid.appendChild(card);
    const tools = $('.tools', card);
    let year = '';
    if (f.years && f.years.length){
      const sel = document.createElement('select'); sel.className = 'btn'; sel.setAttribute('aria-label','Year');
      f.years.forEach(y => sel.add(new Option(y, y)));
      year = String(INDEX.profile_year && f.years.includes(INDEX.profile_year) ? INDEX.profile_year : f.years[f.years.length-1]);
      sel.value = year;
      sel.onchange = () => loadFigure(card, f, sel.value);
      tools.appendChild(sel);
    }
    const tb = document.createElement('button'); tb.className = 'btn'; tb.textContent = 'Table';
    tb.onclick = () => { card.dataset.table = card.dataset.table === '1' ? '0' : '1'; render(card, card._fig); };
    tools.appendChild(tb);
    loadFigure(card, f, year);
  });
}

async function loadFigure(card, f, year){
  $('.body', card).innerHTML = '<div class="status">Loading…</div>';
  try {
    const q = {a:'figure', id:f.id}; if (year) q.year = year;
    const fig = await (await API(q)).json();
    card._fig = fig;
    render(card, fig);
  } catch(e) {
    $('.body', card).innerHTML = `<div class="status err">${esc(e.message)}</div>`;
  }
}

/* ---------- rendering ---------- */
function render(card, fig){
  const body = $('.body', card);
  const old = live.findIndex(x => x.card === card);
  if (old >= 0) { live[old].chart?.destroy?.(); live.splice(old, 1); }
  $('.unit', card).textContent = fig.unit || '';
  $('.note', card).textContent = fig.note || '';
  if (fig.kind === 'kpi' || fig.kind === 'table' || fig.kind === 'heatmap') card.classList.add('wide');
  if (fig.kind === 'kpi') { $('.tools', card).hidden = true; body.innerHTML = `<div class="kpis">${fig.items.map(i => `<div class="kpi"><div class="v">${esc(i.value)}</div><div class="l">${esc(i.label)}</div><div class="s">${esc(i.sub||'')}</div></div>`).join('')}</div>`; return; }
  if (fig.kind === 'table' || card.dataset.table === '1') { body.innerHTML = tableHtml(fig); return; }
  if (fig.kind === 'heatmap') { const h = heatmap(body, fig); live.push({card, fig, chart:h}); return; }
  if (COMFORT[fig.kind]) { if (fig.kind === 'psychro') card.classList.add('wide'); const ch = COMFORT[fig.kind](body, fig); live.push({card, fig, chart:ch}); return; }
  body.innerHTML = '';
  const box = document.createElement('div'); box.className = 'chartbox' + ((fig.horizontal && (fig.labels||[]).length > 10) ? ' tall' : '');
  const cv = document.createElement('canvas'); box.appendChild(cv); body.appendChild(box);
  const chart = new Chart(cv, chartConfig(fig));
  live.push({card, fig, chart});
}

function tableHtml(fig){
  if (fig.kind === 'table') {
    return `<div class="tablewrap"><table><thead><tr>${fig.columns.map(c => `<th>${esc(c)}</th>`).join('')}</tr></thead><tbody>${
      fig.rows.map(r => `<tr>${r.map((v,i) => `<td class="${i && v==='PASS'?'ok':''} ${i && v==='FAIL'?'bad':''}">${esc(v)}</td>`).join('')}</tr>`).join('')}</tbody></table></div>`;
  }
  if (fig.kind === 'heatmap') {
    return `<div class="tablewrap"><table><thead><tr><th></th>${fig.x.map(x => `<th>${esc(x)}</th>`).join('')}</tr></thead><tbody>${
      fig.y.map((y,i) => `<tr><td>${esc(y)}</td>${fig.z[i].map(v => `<td>${fmt(v)}</td>`).join('')}</tr>`).join('')}</tbody></table></div>`;
  }
  if (fig.kind === 'pmvppd') {
    return `<div class="tablewrap"><table><thead><tr><th>PMV</th><th>PPD %</th></tr></thead><tbody><tr><td>${fmt(fig.point.pmv)}</td><td>${fmt(fig.point.ppd)}</td></tr></tbody></table></div>`;
  }
  if (fig.kind === 'psychro') {
    return `<div class="tablewrap"><table><thead><tr><th>dry-bulb °C (bin)</th><th>humidity ratio g/kg (bin)</th><th>% of hours</th></tr></thead><tbody>${
      fig.bins.slice().sort((a,b)=>b[2]-a[2]).map(b => `<tr><td>${fmt(b[0])}</td><td>${fmt(b[1])}</td><td>${fmt(b[2])}</td></tr>`).join('')}</tbody></table></div>`;
  }
  if (fig.kind === 'scatter') {
    const s = fig.series[0];
    return `<div class="tablewrap"><table><thead><tr><th>${esc(fig.xlabel||'x')}</th><th>${esc(fig.unit||'y')}</th></tr></thead><tbody>${
      s.data.map(p => `<tr><td>${fmt(p.x)}</td><td>${fmt(p.y)}</td></tr>`).join('')}</tbody></table></div>`;
  }
  return `<div class="tablewrap"><table><thead><tr><th></th>${fig.series.map(s => `<th>${esc(s.name)}</th>`).join('')}</tr></thead><tbody>${
    fig.labels.map((l,i) => `<tr><td>${esc(l)}</td>${fig.series.map(s => `<td>${fmt(s.data[i])}</td>`).join('')}</tr>`).join('')}</tbody></table></div>`;
}

/* colours that mean something: fossil = reds/browns, renewables = greens, grid electricity = blue,
   seasons, weekday/weekend, BER bands (official A green ... G red), data quality */
const BER_COL = {A:'#00a651', B:'#50b848', C:'#bed630', D:'#ffd200', E:'#fdb913', F:'#f37021', G:'#ed1c24'};
const SEM = [
  [/^(a1|a2|a3|b1|b2|b3|c1|c2|c3|d1|d2|e1|e2|f|g)$/i, n => BER_COL[n[0].toUpperCase()]],
  [/heat ?pump|\bhp\b|ashp|gshp/i, '#1a9850'], [/solar|\bpv\b|photovolt/i, '#91cf60'], [/wind/i, '#006837'],
  [/biomass|wood|pellet|renew/i, '#66a61e'], [/\bexport/i, '#1a9850'],
  [/\bgas\b|natural gas|mains gas/i, '#d7301f'], [/\boil\b|kerosene|heating oil/i, '#7f2704'], [/lpg/i, '#e6550d'],
  [/coal/i, '#4d4d4d'], [/peat|turf/i, '#8c510a'], [/solid/i, '#a6611a'], [/fossil|boiler/i, '#b2182b'],
  [/\bimport/i, '#d73027'], [/electric|grid/i, '#4575b4'],
  [/winter/i, '#2c7bb6'], [/spring/i, '#66bd63'], [/summer/i, '#f4a11d'], [/autumn/i, '#d95f0e'],
  [/weekday/i, '#4575b4'], [/weekend/i, '#f46d43'],
  [/^ok$|\bpass\b/i, '#1a9850'], [/estimated/i, '#fdae61'], [/missing/i, '#9a998f'], [/suspect/i, '#f46d43'],
  [/drift/i, '#8073ac'], [/fault|fail/i, '#d73027'],
  [/no smart meter/i, '#bdbdbd'], [/smart meter \(30/i, '#4575b4'], [/study enrolment/i, '#1a9850'],
  [/^flexible$/i, '#1a9850'], [/shifted/i, '#f4a11d'],
];
function semanticColor(name){
  const n = String(name ?? '').trim();
  for (const [re, c] of SEM) if (re.test(n)) return typeof c === 'function' ? c(n) : c;
  return null;
}
function seriesColor(name, i){ return name === 'Other' ? css('--other') : (semanticColor(name) || SERIES()[i % 8]); }
/* single-series bars whose categories have meanings (BER bands, fuels) get one colour per bar */
function barColors(fig, s, i){
  if ((fig.series||[]).length !== 1 || !fig.labels) return seriesColor(s.name, i);
  const cols = fig.labels.map(semanticColor);
  return cols.filter(Boolean).length >= Math.ceil(fig.labels.length / 2) ? cols.map(c => c || css('--other')) : seriesColor(s.name, i);
}

function chartConfig(fig){
  const ink2 = css('--ink-2'), grid = css('--grid'), surface = css('--panel');
  const multi = (fig.series||[]).length > 1;
  const common = {
    responsive:true, maintainAspectRatio:false, animation:false,
    plugins:{
      legend:{display:multi, position:'top', align:'start', labels:{color:ink2, boxWidth:10, boxHeight:10, usePointStyle:true, pointStyle:'rectRounded'}},
      tooltip:{mode: fig.kind==='scatter' ? 'nearest' : 'index', intersect: fig.kind==='scatter',
        callbacks:{label: c => ` ${c.dataset.label}: ${fmt(fig.kind==='scatter' ? c.parsed.y : c.parsed[fig.horizontal?'x':'y'])} ${fig.unit||''}`}}
    },
    scales:{
      x:{ticks:{color:ink2, maxRotation:0, autoSkip:true}, grid:{color:grid, drawTicks:false}, border:{display:false}, stacked:!!fig.stacked,
          title:{display:!!fig.xlabel, text:fig.xlabel, color:ink2}},
      y:{ticks:{color:ink2}, grid:{color:grid, drawTicks:false}, border:{display:false}, stacked:!!fig.stacked, beginAtZero: fig.kind==='bar'}
    }
  };
  if (fig.kind === 'scatter') {
    common.scales.x.type = 'linear';
    common.scales.y.title = {display:true, text:fig.unit, color:ink2};
    return {type:'scatter', data:{datasets: fig.series.map((s,i) => ({label:s.name, data:s.data, backgroundColor:seriesColor(s.name,i), pointRadius:3, pointHoverRadius:5}))}, options:common};
  }
  if (fig.kind === 'line') {
    return {type:'line', data:{labels:fig.labels, datasets: fig.series.map((s,i) => ({label:s.name, data:s.data, borderColor:seriesColor(s.name,i), backgroundColor:seriesColor(s.name,i),
      borderWidth:2, pointRadius:0, pointHoverRadius:4, tension:0.2, spanGaps:true}))},
      options:{...common, interaction:{mode:'index', intersect:false}}};
  }
  // bar
  const opts = {...common, indexAxis: fig.horizontal ? 'y' : 'x', interaction:{mode:'index', intersect:false}};
  if (fig.horizontal) { const t = opts.scales.x; opts.scales.x = {...opts.scales.y, beginAtZero:true}; opts.scales.y = {...t, beginAtZero:false, grid:{display:false}}; }
  return {type:'bar', data:{labels:fig.labels, datasets: fig.series.map((s,i) => ({label:s.name, data:s.data, backgroundColor:barColors(fig,s,i),
      borderRadius: fig.stacked ? 0 : 4, borderSkipped:'start', borderColor:surface, borderWidth: fig.stacked ? {top:2} : 0,
      maxBarThickness:28, categoryPercentage:0.8, barPercentage:0.9}))}, options:opts};
}

/* heatmap colour scales. domain: fixed [lo, hi] or null (data range); center: diverging midpoint */
const SCALES = {
  blue:     {stops:['#cde2fb','#9ec5f4','#6da7ec','#3987e5','#256abf','#184f95','#0d366b']},
  temp_out: {stops:['#2166ac','#67a9cf','#d1e5f0','#f7f7f7','#fddbc7','#ef8a62','#b2182b'], center:10, label:'cold → warm'},
  temp_in:  {stops:['#2166ac','#67a9cf','#c7e9c0','#1a9850','#fee08b','#f46d43','#a50026'], domain:[14,28], center:21, label:'cold · comfortable · hot'},
  demand:   {stops:['#fff5d6','#fed976','#feb24c','#fd8d3c','#e31a1c','#800026'], label:'low → high demand'},
  solar:    {stops:['#fffbe0','#fff0a3','#ffd84d','#ffb400','#e08600','#a65e00'], label:'dull → sunny'},
  loading:  {stops:['#e5f5e0','#a1d99b','#41ab5d','#fee08b','#fc8d59','#d73027'], domain:[0,100], label:'% of rating: green safe, red near limit'},
  co2:      {stops:['#1a9850','#91cf60','#fee08b','#fc8d59','#d73027'], domain:[400,2000], label:'fresh → stale'},
  pmv:      {stops:['#2166ac','#92c5de','#1a9850','#fddbc7','#b2182b'], domain:[-2,2], center:0, label:'cold · neutral · hot'},
};
const SCALE_BY_ID = {w_dayhour:'temp_out', w_temp_month:'temp_out', w_ghi_month:'solar', e_month:'demand',
                     c_temp_month:'temp_in', n_load_month:'loading'};
function scaleFor(fig){
  if (fig.scale && SCALES[fig.scale]) return SCALES[fig.scale];
  if (SCALE_BY_ID[fig.id]) return SCALES[SCALE_BY_ID[fig.id]];
  const u = String(fig.unit||'');
  if (/°C/.test(u)) return /^c_/.test(fig.id||'') ? SCALES.temp_in : SCALES.temp_out;
  if (/MWh|kWh(?!\/m)/.test(u)) return SCALES.demand;
  if (/kWh\/m/.test(u)) return SCALES.solar;
  if (/rating/.test(u)) return SCALES.loading;
  if (/ppm/.test(u)) return SCALES.co2;
  return SCALES.blue;
}
function hex2rgb(h){ const n = parseInt(h.slice(1),16); return [n>>16&255, n>>8&255, n&255]; }
function interp(stops, t){
  t = Math.max(0, Math.min(1, t)); const x = t * (stops.length-1), i = Math.min(stops.length-2, Math.floor(x)), f = x - i;
  const a = hex2rgb(stops[i]), b = hex2rgb(stops[i+1]);
  return `rgb(${a.map((v,k)=>Math.round(v+(b[k]-v)*f)).join(',')})`;
}
function makeScale(sc, lo, hi){
  if (sc.domain) { lo = sc.domain[0]; hi = sc.domain[1]; }
  const c = sc.center;
  const pos = v => (c == null || c <= lo || c >= hi) ? (v - lo) / ((hi - lo) || 1)
                 : v < c ? 0.5 * (v - lo) / (c - lo) : 0.5 + 0.5 * (v - c) / (hi - c);
  return {lo, hi, color: v => interp(sc.stops, pos(v)),
          gradient: `linear-gradient(90deg,${[0,.1,.2,.3,.4,.5,.6,.7,.8,.9,1].map(t => interp(sc.stops, t)).join(',')})`};
}

function heatmap(body, fig){
  body.innerHTML = '';
  const wrap = document.createElement('div'); wrap.className = 'heat';
  const cv = document.createElement('canvas'); wrap.appendChild(cv);
  const vals = fig.z.flat().filter(v => v != null);
  const sc = scaleFor(fig);
  const SC = makeScale(sc, Math.min(...vals), Math.max(...vals));
  const lo = SC.lo, hi = SC.hi;
  const leg = document.createElement('div'); leg.className = 'legend';
  leg.innerHTML = `<span>${fmt(lo)}</span><i style="background:${SC.gradient}"></i><span>${fmt(hi)} ${esc(fig.unit||'')}</span>${sc.label ? `<span style="margin-left:8px;color:var(--ink-3)">${esc(sc.label)}</span>` : ''}`;
  wrap.appendChild(leg); body.appendChild(wrap);
  const ink2 = css('--ink-2'), surface = css('--panel');
  const padL = 46, padT = 4, padB = 22;
  const nx = fig.x.length, ny = fig.y.length;
  function draw(){
    const w = cv.clientWidth || body.clientWidth; const cellH = ny > 14 ? 12 : 26; const h = padT + ny * cellH + padB;
    const dpr = devicePixelRatio || 1; cv.width = w * dpr; cv.height = h * dpr; cv.style.height = h + 'px';
    const ctx = cv.getContext('2d'); ctx.setTransform(dpr,0,0,dpr,0,0); ctx.clearRect(0,0,w,h);
    const cw = (w - padL) / nx;
    const gap = cw > 6 ? 1 : 0;
    for (let j = 0; j < ny; j++) for (let i = 0; i < nx; i++) {
      const v = fig.z[j][i];
      ctx.fillStyle = v == null ? surface : SC.color(v);
      ctx.fillRect(padL + i*cw, padT + j*cellH, Math.max(1, cw - gap), cellH - 1);
    }
    ctx.fillStyle = ink2; ctx.font = '11px system-ui'; ctx.textBaseline = 'middle'; ctx.textAlign = 'right';
    const ystep = ny > 14 ? 3 : 1;
    fig.y.forEach((y, j) => { if (j % ystep === 0) ctx.fillText(String(y), padL - 6, padT + j*cellH + cellH/2); });
    ctx.textAlign = 'center'; ctx.textBaseline = 'top';
    const xstep = Math.ceil(nx / Math.max(1, Math.floor((w - padL) / 44)));
    fig.x.forEach((x, i) => { if (i % xstep === 0) ctx.fillText(String(x), padL + i*cw + cw/2, padT + ny*cellH + 6); });
    cv._geom = {cw, cellH};
  }
  cv.onmousemove = e => {
    const r = cv.getBoundingClientRect(); const g = cv._geom; if (!g) return;
    const i = Math.floor((e.clientX - r.left - padL) / g.cw), j = Math.floor((e.clientY - r.top - padT) / g.cellH);
    if (i < 0 || j < 0 || i >= nx || j >= ny) { tip.style.display = 'none'; return; }
    tip.innerHTML = `<b>${esc(fig.y[j])}</b> · ${esc(fig.x[i])}<br>${fmt(fig.z[j][i])} ${esc(fig.unit||'')}`;
    tip.style.display = 'block'; tip.style.left = (e.clientX + 12) + 'px'; tip.style.top = (e.clientY + 12) + 'px';
  };
  cv.onmouseleave = () => tip.style.display = 'none';
  draw();
  return {destroy(){}, redraw: draw};
}


/* ---------- comfort figures (PMV / PPD / psychrometric), after ISO 7730 ---------- */
const PPD = p => 100 - 95 * Math.exp(-0.03353 * p**4 - 0.2179 * p**2);
function pmvStatus(p){ const a = Math.abs(p);
  if (a <= 0.5) return ['comfortable','ok']; if (a <= 1) return [p < 0 ? 'slightly cool, stressed' : 'slightly warm, stressed','warn'];
  return [p < 0 ? 'cold' : 'hot','bad']; }
function ppdStatus(v){ return v <= 10 ? ['within 10 %','ok'] : v <= 20 ? [`${fmt(v)}% dissatisfied`,'warn'] : [`${fmt(v)}% dissatisfied`,'bad']; }
function headline(body, value, unitText, [label, cls]){
  const d = document.createElement('div'); d.className = 'figval';
  d.innerHTML = `<span class="v">${esc(fmt(value))}${unitText ? `<span style="font-size:13px;color:var(--ink-3);font-weight:500"> ${esc(unitText)}</span>` : ''}</span><span class="badge ${cls}">${esc(label)}</span>`;
  body.appendChild(d);
}
function box(body, h){ const b = document.createElement('div'); b.className = 'chartbox'; if (h) b.style.height = h + 'px'; const cv = document.createElement('canvas'); b.appendChild(cv); body.appendChild(b); return cv; }
/* plugin: horizontal band (e.g. PMV -0.5..+0.5) and vertical coloured zones */
const bandPlugin = {id:'bands', beforeDatasetsDraw(ch, _a, o){
  const {ctx, chartArea:a, scales:{x, y}} = ch;
  ctx.save();
  (o.yBands||[]).forEach(b => { const y1 = y.getPixelForValue(b.from), y2 = y.getPixelForValue(b.to);
    ctx.fillStyle = b.color; ctx.fillRect(a.left, Math.min(y1,y2), a.right - a.left, Math.abs(y2-y1)); });
  (o.xBands||[]).forEach(b => { const x1 = x.getPixelForValue(b.from), x2 = x.getPixelForValue(b.to);
    ctx.fillStyle = b.color; ctx.fillRect(Math.min(x1,x2), a.top, Math.abs(x2-x1), a.bottom - a.top); });
  (o.polys||[]).forEach(p => { if (!p.pts.length) return; ctx.beginPath();
    p.pts.forEach(([px,py], i) => { const X = x.getPixelForValue(px), Y = y.getPixelForValue(py); i ? ctx.lineTo(X,Y) : ctx.moveTo(X,Y); });
    ctx.closePath(); ctx.fillStyle = p.fill; ctx.fill(); ctx.strokeStyle = p.stroke; ctx.lineWidth = 2; ctx.stroke(); });
  ctx.restore();
}};
function baseOpts(xTitle, yTitle){
  const ink2 = css('--ink-2'), grid = css('--grid');
  return {responsive:true, maintainAspectRatio:false, animation:false,
    plugins:{legend:{display:false}, tooltip:{mode:'index', intersect:false}},
    scales:{x:{ticks:{color:ink2, maxRotation:0, autoSkip:true}, grid:{color:grid}, border:{display:false}, title:{display:!!xTitle, text:xTitle, color:ink2}},
            y:{ticks:{color:ink2}, grid:{color:grid}, border:{display:false}, title:{display:!!yTitle, text:yTitle, color:ink2}}}};
}
const COMFORT = {
  pmv(body, fig){
    body.innerHTML = ''; headline(body, fig.value, '', pmvStatus(fig.value));
    const [med, p10, p90] = fig.series;
    const o = baseOpts('', 'PMV');
    o.scales.y.suggestedMin = -1.5; o.scales.y.suggestedMax = 1;
    o.plugins.bands = {yBands:[{from:fig.band[0], to:fig.band[1], color:'rgba(26,152,80,.12)'}]};
    o.plugins.legend = {display:true, position:'top', align:'start', labels:{color:css('--ink-2'), boxWidth:10, usePointStyle:true, filter: it => it.text !== p10.name}};
    const cv = box(body, 240);
    const ch = new Chart(cv, {type:'line', plugins:[bandPlugin], options:o, data:{labels:fig.labels, datasets:[
      {label:'10th to 90th percentile', data:p90.data, borderWidth:0, pointRadius:0, fill:'+1', backgroundColor:'rgba(57,135,229,.18)'},
      {label:p10.name, data:p10.data, borderWidth:0, pointRadius:0, fill:false},
      {label:med.name, data:med.data, borderColor:'#1c5cab', borderWidth:1.6, pointRadius:0, tension:.2}]}});
    const t = document.createElement('div'); t.className = 'note'; t.textContent = `Target band: ${fig.band[0]} to +${fig.band[1]} (green). Shaded blue: 10th to 90th percentile across homes.`; body.appendChild(t);
    return ch;
  },
  ppd(body, fig){
    body.innerHTML = ''; headline(body, fig.value, '%', ppdStatus(fig.value));
    const o = baseOpts('', '%'); o.scales.y.beginAtZero = true;
    o.plugins.legend = {display:true, position:'top', align:'start', labels:{color:css('--ink-2'), boxWidth:10, usePointStyle:true}};
    o.plugins.bands = {yBands:[{from:0, to:10, color:'rgba(26,152,80,.10)'}]};
    const cv = box(body, 200);
    const ch = new Chart(cv, {type:'line', plugins:[bandPlugin], options:o, data:{labels:fig.labels, datasets:fig.series.map((s,i) => (
      {label:s.name, data:s.data, borderColor: i ? '#f46d43' : '#1c5cab', borderWidth:1.5, pointRadius:0, tension:.2}))}});
    const lo = 5, hi = 50, pos = Math.max(0, Math.min(1, (fig.value - lo) / (hi - lo))) * 100;
    const g = document.createElement('div'); g.innerHTML = `<div class="gbar"><i style="left:calc(${pos}% - 1px)"></i></div><div class="gbar-l"><span>low</span><span>moderate</span><span>high</span></div>`;
    body.appendChild(g);
    return ch;
  },
  pmvppd(body, fig){
    body.innerHTML = ''; headline(body, fig.point.pmv, `PMV · PPD ${fmt(fig.point.ppd)}%`, pmvStatus(fig.point.pmv));
    const xs = []; for (let p = -3; p <= 3.0001; p += 0.05) xs.push(+p.toFixed(2));
    const o = baseOpts('PMV (−3 cold … +3 hot)', 'PPD (%)');
    o.scales.x.type = 'linear'; o.scales.x.min = -3; o.scales.x.max = 3; o.scales.y.min = 0; o.scales.y.max = 100;
    o.plugins.tooltip = {callbacks:{label: c => ` PMV ${fmt(c.parsed.x)} · PPD ${fmt(c.parsed.y)}%`}};
    o.plugins.bands = {xBands:[
      {from:-3, to:-2, color:'rgba(33,102,172,.10)'}, {from:-2, to:-1, color:'rgba(103,169,207,.10)'}, {from:-1, to:-0.5, color:'rgba(199,233,192,.25)'},
      {from:-0.5, to:0.5, color:'rgba(254,224,139,.25)'}, {from:0.5, to:1, color:'rgba(199,233,192,.25)'},
      {from:1, to:2, color:'rgba(253,174,97,.12)'}, {from:2, to:3, color:'rgba(215,48,39,.10)'}]};
    const cv = box(body, 240);
    return new Chart(cv, {type:'scatter', plugins:[bandPlugin], options:o, data:{datasets:[
      {type:'line', label:'cold side', data:xs.filter(x => x <= 0).map(x => ({x, y:PPD(x)})), borderColor:'#2c5aa0', borderWidth:2, pointRadius:0},
      {type:'line', label:'warm side', data:xs.filter(x => x >= 0).map(x => ({x, y:PPD(x)})), borderColor:'#a50f15', borderWidth:2, pointRadius:0},
      {label:'this town', data:[{x:fig.point.pmv, y:fig.point.ppd}], backgroundColor:'#0d366b', borderColor:'#fff', borderWidth:2, pointRadius:6, pointHoverRadius:8}]}});
  },
  psychro(body, fig){
    body.innerHTML = '';
    const psat = t => 610.94 * Math.exp(17.625 * t / (t + 243.04));
    const wOf = (t, rh) => { const pa = rh / 100 * psat(t); return 622 * pa / (101325 - pa); };
    const T = []; for (let t = 10; t <= 35.001; t += 0.5) T.push(+t.toFixed(1));
    const curves = [20,40,60,80,100].map(rh => ({type:'line', label:`RH ${rh}%`, data:T.map(t => ({x:t, y:wOf(t, rh)})).filter(p => p.y <= 30),
      borderColor: rh === 100 ? css('--ink-3') : css('--line'), borderWidth: rh === 100 ? 2 : 1.2, pointRadius:0}));
    const mx = Math.max(...fig.bins.map(b => b[2]), 1e-9);
    const cells = fig.bins.map(b => ({x:b[0] + .25, y:b[1] + .25, s:b[2]}));
    const o = baseOpts('Dry-bulb temperature (°C)', 'Humidity ratio (g/kg dry air)');
    o.scales.x.type = 'linear'; o.scales.x.min = 10; o.scales.x.max = 35; o.scales.y.min = 0; o.scales.y.max = 30;
    o.plugins.legend = {display:true, position:'top', align:'start', labels:{color:css('--ink-2'), boxWidth:10, usePointStyle:true,
      filter: it => !/^RH/.test(it.text)}};
    o.plugins.tooltip = {mode:'nearest', intersect:true, callbacks:{label: c => c.raw.s != null ? ` ${fmt(c.raw.x-.25)}–${fmt(c.raw.x+.25)} °C · ${fmt(c.raw.y-.25)}–${fmt(c.raw.y+.25)} g/kg: ${fmt(c.raw.s)}% of hours` : ` ${fmt(c.parsed.x)} °C · ${fmt(c.parsed.y)} g/kg`}};
    o.plugins.bands = {polys:(fig.polygons||[]).map((p,i) => ({pts:p.pts, fill: i ? 'rgba(244,165,29,.18)' : 'rgba(57,135,229,.20)', stroke: i ? '#d9a21b' : '#6b8fc7'}))};
    const cv = box(body, 460);
    const pt = fig.point;
    return new Chart(cv, {type:'scatter', plugins:[bandPlugin], options:o, data:{datasets:[
      ...curves,
      ...(fig.polygons||[]).map((p,i) => ({type:'line', label:`Comfort zone, ${p.name}`, data:[], borderColor: i ? '#d9a21b' : '#6b8fc7', backgroundColor: i ? 'rgba(244,165,29,.4)' : 'rgba(57,135,229,.4)'})),
      {label:'Occupied hours (darker = more)', data:cells, pointStyle:'rect', pointRadius:5,
       backgroundColor: cells.map(c => `rgba(13,54,107,${(0.12 + 0.88 * Math.sqrt(c.s / mx)).toFixed(3)})`), borderWidth:0},
      {label:`Median: ${fmt(pt.t)} °C · RH ${fmt(pt.rh)}%`, data:[{x:pt.t, y:pt.w}], backgroundColor:'#0d366b', borderColor:'#e34948', borderWidth:3, pointRadius:8, pointHoverRadius:10}]}});
  },
};

function redrawAll(){ live.slice().forEach(x => render(x.card, x.fig)); }
let rz; addEventListener('resize', () => { clearTimeout(rz); rz = setTimeout(() => live.forEach(x => x.chart?.redraw?.()), 150); });

/* ---------- raw browser (server lists, browser reads Parquet via presigned URLs) ---------- */
let HYP = null, COMP;
async function hyparquet(){
  if (!HYP) {
    HYP = await import('https://cdn.jsdelivr.net/npm/hyparquet@1.8.2/+esm');
    try { COMP = (await import('https://cdn.jsdelivr.net/npm/hyparquet-compressors@1.1.1/+esm')).compressors; } catch(_) {}
  }
  return HYP;
}
function rawBrowser(sec){
  sec.innerHTML = `<div class="raw"><div class="card"><div class="meta"><select class="btn" id="rb" aria-label="Bucket"></select></div><div class="crumbs" id="rc"></div><ul class="ls" id="rl"></ul><div class="status" id="rs"></div></div>
    <div class="card"><div id="rv" class="status">Pick a file. Parquet shows schema and rows; text files (JSON, CSV, logs, code) show as text; anything else can be downloaded.</div></div></div>`;
  const sel = $('#rb', sec), crumbs = $('#rc', sec), list = $('#rl', sec), st = $('#rs', sec), view = $('#rv', sec);
  let B = null, BUCKETS = [];
  const TEXT = /\.(json|jsonl|ndjson|md|txt|log|csv|tsv|yaml|yml|toml|ini|cfg|conf|py|sh|sql|xml|html|php|js|ts|r|ipynb)$/i;
  function li(html, fn){ const e = document.createElement('li'); e.innerHTML = html; e.onclick = fn; list.appendChild(e); return e; }
  async function ls(prefix, token){
    if (!token) { list.innerHTML = ''; }
    list.querySelector('.more')?.remove();
    st.className = 'status'; st.textContent = 'Listing…';
    crumbs.innerHTML = ''; let acc = '';
    const top = document.createElement('a'); top.textContent = B.title; top.onclick = () => ls(B.root); crumbs.append(top);
    prefix.slice(B.root.length).split('/').filter(Boolean).forEach(p => { acc += p + '/'; const a = document.createElement('a'); const pp = B.root + acc; a.textContent = p; a.onclick = () => ls(pp); crumbs.append(' / ', a); });
    try {
      const q = {a:'list', b:B.id, prefix}; if (token) q.token = token;
      const d = await (await API(q)).json();
      if (!token && prefix !== B.root) li('<span>..</span><span>up</span>', () => ls(prefix.split('/').filter(Boolean).slice(0,-1).join('/') + (prefix.split('/').filter(Boolean).length > 1 ? '/' : '')));
      d.dirs.forEach(p => li(`<span>📁 ${esc(p.slice(prefix.length))}</span><span></span>`, () => ls(p)));
      d.files.forEach(f => li(`<span>${esc(f.key.slice(prefix.length))}</span><span>${(f.size/1048576).toFixed(f.size>1048576?1:3)} MB</span>`, () => open(f)));
      const n = list.querySelectorAll('li').length;
      st.textContent = `${n} entries shown`;
      if (d.next) { const m = li('<span>Load more…</span><span></span>', () => ls(prefix, d.next)); m.className = 'more'; }
    } catch(e) { st.textContent = e.message; st.className = 'status err'; }
  }
  async function dl(f){ const {url} = await (await API({a:'presign', b:B.id, key:f.key, dl:1})).json(); location.href = url; }
  async function open(f){
    view.className = '';
    const head = () => `<div class="meta"><div class="crumbs">${esc(f.key)}</div><button class="btn" id="dlb">Download</button></div>`;
    view.innerHTML = head() + '<div class="status">Loading…</div>';
    const wire = () => { const b = $('#dlb', view); if (b) b.onclick = () => dl(f).catch(e => alert(e.message)); };
    wire();
    try {
      if (/\.parquet$/i.test(f.key)) {
        const H = await hyparquet();
        let cached = null;
        const sign = async () => { if (!cached || Date.now() - cached.t > 600000) cached = {t:Date.now(), url:(await (await API({a:'presign', b:B.id, key:f.key})).json()).url}; return cached.url; };
        const file = {byteLength:f.size, async slice(s, e){ const url = await sign();
          const r = await fetch(url, {headers:{Range:`bytes=${s}-${(e ?? f.size)-1}`}}); if (!(r.ok || r.status === 206)) throw new Error('HTTP ' + r.status); return r.arrayBuffer(); }};
        const md = await H.parquetMetadataAsync(file);
        const cols = md.schema.slice(1).map(s => s.name);
        const rows = await new Promise((res, rej) => H.parquetRead({file, metadata:md, rowStart:0, rowEnd:Math.min(200, Number(md.num_rows)), compressors:COMP, onComplete:res}).catch(rej));
        const cell = v => v == null ? '' : typeof v === 'bigint' ? v.toString() : v instanceof Date ? v.toISOString() : typeof v === 'object' ? JSON.stringify(v, (k,x) => typeof x === 'bigint' ? String(x) : x) : String(v);
        view.innerHTML = head() + `<div class="note" style="margin-bottom:8px">${Number(md.num_rows).toLocaleString()} rows · ${cols.length} columns · first 200 rows</div>
          <div class="tablewrap"><table><thead><tr>${cols.map(c => `<th>${esc(c)}</th>`).join('')}</tr></thead><tbody>${rows.map(r => `<tr>${r.map(v => `<td>${esc(cell(v))}</td>`).join('')}</tr>`).join('')}</tbody></table></div>`;
      } else if (TEXT.test(f.key)) {
        const t = await (await API({a:'text', b:B.id, key:f.key})).text();
        let s = t; if (/\.(json|ipynb)$/i.test(f.key)) { try { s = JSON.stringify(JSON.parse(t), null, 2); } catch(_){} }
        view.innerHTML = head() + (f.size > 2097152 ? '<div class="note">First 2 MB only.</div>' : '') + '<pre></pre>'; $('pre', view).textContent = s;
      } else {
        view.innerHTML = head() + `<div class="status">${(f.size/1048576).toFixed(2)} MB · no preview for this file type.</div>`;
      }
      wire();
    } catch(e) { view.innerHTML = head() + `<div class="status err">${esc(e.message)}. For Parquet, the bucket's CORS rule must allow https://ultrasoftware.ie (no trailing slash).</div>`; wire(); }
  }
  (async () => {
    try { BUCKETS = (await (await API({a:'buckets'})).json()).buckets; } catch(e) { st.textContent = e.message; st.className = 'status err'; return; }
    BUCKETS.forEach(b => sel.add(new Option(b.title, b.id)));
    let want = null; try { want = localStorage.getItem('bn-bucket'); } catch(_){}
    B = BUCKETS.find(b => b.id === want) || BUCKETS[0]; sel.value = B.id;
    sel.hidden = BUCKETS.length < 2;
    sel.onchange = () => { B = BUCKETS.find(b => b.id === sel.value); try { localStorage.setItem('bn-bucket', B.id); } catch(_){} ls(B.root); };
    ls(B.root);
  })();
}

boot();
</script>
<?php endif; ?>
</body>
</html>
