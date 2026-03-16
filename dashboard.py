#!/usr/bin/env python3
"""
ARTEMIS Live Dashboard — localhost-only real-time RF monitor.

Opens in browser at http://127.0.0.1:8080
Auto-refreshes every 5 seconds.
Reads ALL sentinel JSONL logs for history + latest for live data.

Security: binds to 127.0.0.1 only — not accessible from network.
"""

import json
import glob
import os
import time
from datetime import datetime, timezone
from http.server import HTTPServer, BaseHTTPRequestHandler
from pathlib import Path

RESULTS_DIR = os.environ.get("RESULTS_DIR", "results")
SYMPTOM_LOG = f"{RESULTS_DIR}/evidence/symptom_log.jsonl"
PORT = int(os.environ.get("DASH_PORT", "8080"))

HTML = r"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>ARTEMIS</title>
<style>
  :root {
    --bg:       #05050e;
    --bg-card:  #080812;
    --border:   #13132a;
    --border2:  #1c1c36;
    --dim:      #36365a;
    --muted:    #4e4e74;
    --text:     #b0b0cc;
    --za:       #2288ff;
    --zb:       #ff8800;
    --zul:      #aa44ff;
    --accent:   #55aaff;
    --r: 4px;
  }

  * { margin: 0; padding: 0; box-sizing: border-box; }

  body {
    background: var(--bg);
    color: var(--text);
    font-family: 'Consolas', 'Monaco', 'Courier New', monospace;
    font-size: 13px;
    height: 100vh;
    overflow: hidden;
  }

  /* Scanline overlay */
  body::after {
    content: '';
    position: fixed;
    inset: 0;
    pointer-events: none;
    background: repeating-linear-gradient(
      to bottom,
      transparent 0px, transparent 3px,
      rgba(0,0,0,0.08) 3px, rgba(0,0,0,0.08) 4px
    );
    z-index: 9999;
  }

  /* ── Header ── */
  .header {
    background: linear-gradient(180deg, #0d0d1e 0%, #07070f 100%);
    padding: 0 20px;
    height: 5vh;
    border-bottom: 1px solid var(--border2);
    display: flex;
    justify-content: space-between;
    align-items: center;
    position: sticky;
    top: 0;
    z-index: 100;
    box-shadow: 0 2px 24px rgba(0,0,0,0.7);
  }
  .header::after {
    content: '';
    position: absolute;
    bottom: 0; left: 0; right: 0;
    height: 1px;
    background: linear-gradient(90deg,
      transparent 0%, rgba(85,170,255,0.4) 30%,
      rgba(85,170,255,0.6) 50%, rgba(85,170,255,0.4) 70%,
      transparent 100%);
  }
  .header-left { display: flex; align-items: center; gap: 18px; }
  .header h1 {
    font-size: 14px;
    color: var(--accent);
    letter-spacing: 6px;
    font-weight: normal;
    text-shadow: 0 0 20px rgba(85,170,255,0.55), 0 0 50px rgba(85,170,255,0.15);
  }
  .header-sub {
    font-size: 9px;
    color: var(--dim);
    letter-spacing: 2.5px;
    text-transform: uppercase;
    border-left: 1px solid var(--border2);
    padding-left: 16px;
  }
  .header-right { display: flex; align-items: center; gap: 24px; }
  .status { font-size: 11px; color: var(--muted); display: flex; align-items: center; gap: 7px; }
  .dot { display: inline-block; width: 7px; height: 7px; border-radius: 50%; flex-shrink: 0; }
  .dot.live  { background: #00dd44; box-shadow: 0 0 8px #00dd44, 0 0 20px rgba(0,221,68,0.25); animation: pulse 2s ease-in-out infinite; }
  .dot.stale { background: #cc8800; box-shadow: 0 0 6px #cc8800; }
  @keyframes pulse { 0%,100% { opacity:1; } 50% { opacity:0.3; } }

  /* ── Grid ── */
  .grid {
    display: grid;
    grid-template-columns: repeat(4, 1fr);
    gap: 6px;
    padding: 6px 12px;
    height: calc(95vh - 5vh);
    grid-template-rows: auto auto 1fr;
  }
  @media (max-width: 1100px) { .grid { grid-template-columns: repeat(2, 1fr); } }

  /* ── Card base ── */
  .card {
    background: var(--bg-card);
    border: 1px solid var(--border);
    border-radius: var(--r);
    padding: 8px 12px;
    position: relative;
    overflow: hidden;
  }
  .card::before {
    content: '';
    position: absolute;
    top: 0; left: 0; right: 0;
    height: 1px;
    background: linear-gradient(90deg, transparent, var(--border2), transparent);
    pointer-events: none;
  }
  .card h2 {
    font-size: 9px;
    color: var(--dim);
    text-transform: uppercase;
    letter-spacing: 2.5px;
    margin-bottom: 12px;
    font-weight: normal;
    display: flex;
    align-items: center;
    gap: 8px;
  }
  .card h2::after {
    content: '';
    flex: 1;
    height: 1px;
    background: var(--border);
  }

  /* ── Metric cards ── */
  .metric-glow {
    position: absolute;
    top: 0; left: 0; right: 0; bottom: 0;
    pointer-events: none;
    border-radius: var(--r);
    opacity: 0;
    transition: opacity 1.4s ease, background 1.4s ease;
  }
  .metric { font-size: 36px; font-weight: bold; line-height: 1; font-variant-numeric: tabular-nums; transition: color 0.8s ease, text-shadow 0.8s ease; position: relative; z-index: 1; }
  .sub { font-size: 9px; color: var(--muted); margin-top: 4px; letter-spacing: 0.5px; position: relative; z-index: 1; }

  /* ── Zone Exposure bars ── */
  .zone-bars { display: flex; flex-direction: column; gap: 12px; padding-top: 2px; }
  .bar-block { display: flex; flex-direction: column; gap: 5px; }
  .bar-header { display: flex; align-items: baseline; gap: 8px; }
  .bar-zone-name { font-size: 9px; letter-spacing: 2px; text-transform: uppercase; font-weight: bold; width: 52px; flex-shrink: 0; }
  .bar-zone-name.za  { color: var(--za); }
  .bar-zone-name.zb  { color: var(--zb); }
  .bar-zone-name.zul { color: var(--zul); }
  .bar-freq-range { font-size: 9px; color: var(--dim); flex: 1; }
  .bar-val-label { font-size: 12px; font-variant-numeric: tabular-nums; font-weight: bold; text-align: right; min-width: 48px; }
  .bar-val-label.za  { color: var(--za); }
  .bar-val-label.zb  { color: var(--zb); }
  .bar-val-label.zul { color: var(--zul); }
  .bar-track { height: 6px; background: rgba(255,255,255,0.025); border-radius: 2px; overflow: hidden; position: relative; border: 1px solid var(--border); }
  .bar-fill { height: 100%; border-radius: 1px; transition: width 0.9s cubic-bezier(.25,.46,.45,.94); }
  .bar-fill.a  { background: linear-gradient(90deg, rgba(10,24,60,0.5) 0%, #1244aa 50%, var(--za) 100%); box-shadow: 3px 0 12px rgba(34,136,255,0.5); }
  .bar-fill.b  { background: linear-gradient(90deg, rgba(40,12,0,0.5) 0%, #a03000 50%, var(--zb) 100%); box-shadow: 3px 0 12px rgba(255,136,0,0.5); }
  .bar-fill.ul { background: linear-gradient(90deg, rgba(20,6,36,0.5) 0%, #5a1899 50%, var(--zul) 100%); box-shadow: 3px 0 12px rgba(170,68,255,0.5); }

  .span2 { grid-column: span 2; }
  .span4 { grid-column: 1 / -1; }

  /* ── Symptom list ── */
  .sym-list { display: flex; flex-direction: column; max-height: 14vh; overflow-y: auto; }
  .sym-list::-webkit-scrollbar { width: 3px; }
  .sym-list::-webkit-scrollbar-track { background: transparent; }
  .sym-list::-webkit-scrollbar-thumb { background: var(--border2); border-radius: 2px; }

  .sym-item {
    padding: 6px 8px 6px 10px;
    font-size: 11px;
    display: flex;
    gap: 10px;
    align-items: center;
    border-bottom: 1px solid rgba(19,19,42,0.9);
    border-left: 2px solid transparent;
  }
  .sym-item:last-child { border-bottom: none; }
  .sym-item.speech      { border-left-color: #ffbb00; }
  .sym-item.headache    { border-left-color: #ff5555; }
  .sym-item.paresthesia { border-left-color: #44bbff; }
  .sym-item.nausea      { border-left-color: #66dd44; }

  .sym-time { color: var(--muted); width: 58px; flex-shrink: 0; font-size: 10px; }
  .sym-tag { padding: 2px 8px; border-radius: 2px; font-size: 9px; font-weight: bold; letter-spacing: 1px; text-transform: uppercase; flex-shrink: 0; min-width: 82px; text-align: center; }
  .sym-tag.speech      { background: rgba(35,18,0,0.9);  color: #ffbb00; border: 1px solid rgba(80,46,0,0.8); }
  .sym-tag.headache    { background: rgba(32,8,8,0.9);   color: #ff5555; border: 1px solid rgba(70,14,14,0.8); }
  .sym-tag.paresthesia { background: rgba(5,20,34,0.9);  color: #44bbff; border: 1px solid rgba(10,42,70,0.8); }
  .sym-tag.nausea      { background: rgba(20,34,8,0.9);  color: #66dd44; border: 1px solid rgba(40,68,14,0.8); }
  .sym-detail { color: var(--dim); font-size: 10px; flex: 1; }

  /* ── Unified chart panel ── */
  .chart-panel {
    grid-column: 1 / -1;
    grid-row: 3;
    background: var(--bg-card);
    border: 1px solid var(--border);
    border-radius: var(--r);
    overflow: hidden;
    position: relative;
    display: flex;
    flex-direction: column;
    min-height: 0;
  }
  .chart-panel::before {
    content: '';
    position: absolute;
    top: 0; left: 0; right: 0;
    height: 1px;
    background: linear-gradient(90deg, transparent, var(--border2), transparent);
    pointer-events: none;
    z-index: 1;
  }
  .chart-section-header {
    display: flex;
    align-items: center;
    justify-content: space-between;
    padding: 10px 16px 9px;
    border-bottom: 1px solid var(--border);
  }
  .chart-section-title { font-size: 9px; color: var(--dim); text-transform: uppercase; letter-spacing: 2.5px; }
  .chart-legend { display: flex; gap: 16px; font-size: 10px; color: var(--muted); align-items: center; }
  .legend-item { display: flex; align-items: center; gap: 5px; }
  .legend-dot { display: inline-block; width: 20px; height: 3px; border-radius: 2px; flex-shrink: 0; }

  .chart-divider { height: 1px; background: var(--border); position: relative; }
  .chart-divider-label {
    position: absolute; left: 0; top: 50%; transform: translateY(-50%);
    padding: 0 16px; font-size: 9px; color: var(--dim);
    text-transform: uppercase; letter-spacing: 2px;
    background: var(--bg-card); box-shadow: 0 0 0 1px var(--bg-card);
  }
  .chart-divider-right {
    position: absolute; right: 16px; top: 50%; transform: translateY(-50%);
    font-size: 9px; color: var(--dim); letter-spacing: 1px;
    background: var(--bg-card); padding: 0 4px;
  }

  .chart-wrap { width: 100%; position: relative; padding: 2px 0; }
  .chart-wrap canvas { width: 100% !important; }
  .chart-wrap.timeline { height: 22vh; }
  .chart-wrap.heatmap  { height: 35vh; }
</style>
</head>
<body>
<div class="header">
  <div class="header-left">
    <h1>A R T E M I S</h1>
    <div class="header-sub">RF Exposure Monitor</div>
  </div>
  <div class="header-right">
    <div style="display:flex;gap:6px;align-items:center">
      <button onclick="navScroll(-60)" style="background:#1a1a2a;border:1px solid #2a2a3a;color:#888;padding:4px 10px;border-radius:3px;cursor:pointer;font-size:12px">&#9664;&#9664;</button>
      <button onclick="navScroll(-10)" style="background:#1a1a2a;border:1px solid #2a2a3a;color:#888;padding:4px 8px;border-radius:3px;cursor:pointer;font-size:12px">&#9664;</button>
      <span id="navInfo" style="font-size:10px;color:#556;min-width:60px;text-align:center">LIVE</span>
      <button onclick="navScroll(10)" style="background:#1a1a2a;border:1px solid #2a2a3a;color:#888;padding:4px 8px;border-radius:3px;cursor:pointer;font-size:12px">&#9654;</button>
      <button onclick="navScroll(60)" style="background:#1a1a2a;border:1px solid #2a2a3a;color:#888;padding:4px 10px;border-radius:3px;cursor:pointer;font-size:12px">&#9654;&#9654;</button>
      <button onclick="goLive()" style="background:#0a2a0a;border:1px solid #2a4a2a;color:#4a4;padding:4px 10px;border-radius:3px;cursor:pointer;font-size:11px;font-weight:bold">LIVE</button>
    </div>
    <div class="status"><span class="dot live" id="dot"></span><span id="st">connecting...</span></div>
  </div>
</div>

<div class="grid">

  <!-- Metric cards -->
  <div class="card">
    <div class="metric-glow" id="eiGlow"></div>
    <h2>Exposure Index</h2>
    <div class="metric" id="ei" style="color:#334">—</div>
    <div class="sub" id="eiSub">—</div>
  </div>
  <div class="card">
    <div class="metric-glow" id="kurtGlow"></div>
    <h2>Max Kurtosis</h2>
    <div class="metric" id="kurt" style="color:#334">—</div>
    <div class="sub" id="kurtSub">—</div>
  </div>
  <div class="card">
    <div class="metric-glow" id="pulsesGlow"></div>
    <h2>Total Pulses</h2>
    <div class="metric" id="pulses" style="color:#334">—</div>
    <div class="sub" id="pulsesSub">—</div>
  </div>
  <div class="card">
    <div class="metric-glow" id="nactGlow"></div>
    <h2>Active Freqs</h2>
    <div class="metric" id="nact" style="color:#334">—</div>
    <div class="sub" id="nactSub">—</div>
  </div>

  <!-- Zone Power (EI values) -->
  <div class="card span2">
    <h2>Zone Exposure Index</h2>
    <div class="zone-bars">
      <div class="bar-block">
        <div class="bar-header">
          <span class="bar-zone-name za">Zone A</span>
          <span class="bar-freq-range">622 – 636 MHz</span>
          <span class="bar-val-label za" id="vA">—</span>
        </div>
        <div class="bar-track"><div class="bar-fill a" id="bA" style="width:0%"></div></div>
      </div>
      <div class="bar-block">
        <div class="bar-header">
          <span class="bar-zone-name zb">Zone B</span>
          <span class="bar-freq-range">824 – 834 MHz</span>
          <span class="bar-val-label zb" id="vB">—</span>
        </div>
        <div class="bar-track"><div class="bar-fill b" id="bB" style="width:0%"></div></div>
      </div>
      <div class="bar-block">
        <div class="bar-header">
          <span class="bar-zone-name zul">Zone UL</span>
          <span class="bar-freq-range">878 MHz uplink</span>
          <span class="bar-val-label zul" id="vU">—</span>
        </div>
        <div class="bar-track"><div class="bar-fill ul" id="bU" style="width:0%"></div></div>
      </div>
    </div>
  </div>

  <!-- Symptoms -->
  <div class="card span2">
    <h2>Recent Symptoms — CST</h2>
    <div class="sym-list" id="symList"></div>
  </div>

  <!-- Unified chart panel: Timeline + Heatmap in one container -->
  <div class="chart-panel">
    <div class="chart-section-header">
      <span class="chart-section-title">Timeline — 60-cycle window</span>
      <div class="chart-legend">
        <span class="legend-item"><span class="legend-dot" style="background:rgba(34,136,255,0.75)"></span>Zone A</span>
        <span class="legend-item"><span class="legend-dot" style="background:rgba(255,136,0,0.75)"></span>Zone B</span>
        <span class="legend-item"><span class="legend-dot" style="background:rgba(170,68,255,0.75)"></span>878 UL</span>
        <span class="legend-item"><span class="legend-dot" style="background:rgba(255,255,255,0.7); height:2px"></span>Kurtosis</span>
        <span class="legend-item"><span class="legend-dot" style="background:rgba(0,255,140,0.7); height:2px; border:1px dashed rgba(0,255,140,0.5)"></span>Total EI</span>
      </div>
    </div>
    <div class="chart-wrap timeline"><canvas id="cv"></canvas></div>

    <div class="chart-divider">
      <span class="chart-divider-label">Freq &times; Time</span>
      <span class="chart-divider-right">symptom markers at alert time</span>
    </div>

    <div class="chart-wrap heatmap"><canvas id="heatmap"></canvas></div>
  </div>

</div>

<script src="https://cdn.jsdelivr.net/npm/chart.js@4.4.7/dist/chart.umd.min.js"></script>
<script src="https://cdn.jsdelivr.net/npm/chartjs-chart-matrix@2.0.1/dist/chartjs-chart-matrix.min.js"></script>
<script>
let hist = [];

// ── Metric color ──
function metricColor(k) {
  if (k <= 0) return '#334';
  const stops = [[0,0x33,0x33,0x44],[30,0x22,0xcc,0x77],[80,0xff,0xaa,0x00],[200,0xff,0x44,0x22]];
  for (let i = 1; i < stops.length; i++) {
    if (k <= stops[i][0]) {
      const t = (k - stops[i-1][0]) / (stops[i][0] - stops[i-1][0]);
      const lerp = (a, b) => Math.round(a + (b - a) * t);
      return 'rgb(' + lerp(stops[i-1][1],stops[i][1]) + ',' + lerp(stops[i-1][2],stops[i][2]) + ',' + lerp(stops[i-1][3],stops[i][3]) + ')';
    }
  }
  return '#f43';
}

// ── Chart.js setup ──
Chart.defaults.color = '#4e4e74';
Chart.defaults.borderColor = '#13132a';
Chart.defaults.font.family = "'Consolas','Monaco','Courier New',monospace";
Chart.defaults.font.size = 10;
Chart.defaults.animation.duration = 300;

function freqZoneColor(f) {
  if (f < 640) return 'rgba(34,136,255,';
  if (f < 870) return 'rgba(255,136,0,';
  return 'rgba(170,68,255,';
}

// ── Chart.js Timeline Chart ──────────────────────────────────────────────
const timelineChart = new Chart(document.getElementById('cv'), {
  type: 'line',
  data: {
    labels: [],
    datasets: [
      { label: 'Zone A EI', data: [], borderColor: 'rgba(34,136,255,0.8)', backgroundColor: 'rgba(34,136,255,0.12)', fill: true, tension: 0.3, borderWidth: 1.5, pointRadius: 0, yAxisID: 'yA', order: 3 },
      { label: 'Zone B EI', data: [], borderColor: 'rgba(255,136,0,0.8)', backgroundColor: 'rgba(255,136,0,0.12)', fill: true, tension: 0.3, borderWidth: 1.5, pointRadius: 0, yAxisID: 'yB', order: 4 },
      { label: 'UL EI', data: [], borderColor: 'rgba(170,68,255,0.8)', backgroundColor: 'rgba(170,68,255,0.12)', fill: true, tension: 0.3, borderWidth: 1.5, pointRadius: 0, yAxisID: 'yUL', order: 5 },
      { label: 'Total EI', data: [], borderColor: 'rgba(0,255,140,0.6)', backgroundColor: 'transparent', fill: false, tension: 0.3, borderWidth: 1.5, borderDash: [6,4], pointRadius: 0, yAxisID: 'yEI', order: 2 },
      { label: 'Max Kurt', data: [], borderColor: 'rgba(255,255,255,0.85)', backgroundColor: 'transparent', fill: false, tension: 0.3, borderWidth: 2, pointRadius: 0, yAxisID: 'yK', order: 1 },
    ],
  },
  options: {
    responsive: true, maintainAspectRatio: false,
    interaction: { mode: 'index', intersect: false },
    plugins: {
      legend: { display: false },
      tooltip: {
        backgroundColor: 'rgba(8,8,18,0.95)', borderColor: '#2a2a4a', borderWidth: 1,
        titleFont: { size: 10 }, bodyFont: { size: 10 },
        callbacks: { label: ctx => ctx.dataset.label + ': ' + (ctx.parsed.y != null ? ctx.parsed.y.toFixed(1) : '—') }
      },
    },
    scales: {
      x: { display: false },
      yA:  { display: false, beginAtZero: true },
      yB:  { display: false, beginAtZero: true },
      yUL: { display: false, beginAtZero: true },
      yEI: { display: false, beginAtZero: true },
      yK:  { display: false, beginAtZero: true },
    },
  },
});

// ── Chart.js Heatmap ─────────────────────────────────────────────────────
const hmCtx2 = document.getElementById('heatmap');
let freqBins = [];
let symptomsData = [];
let heatmapChart = null;

function buildHeatmap() {
  if (heatmapChart) heatmapChart.destroy();
  if (!hist.length || !freqBins.length) return;

  const labels = hist.map(h => h.ts || '');
  const freqLabels = freqBins.map(f => f + ' MHz');

  // Build matrix data: [{x: timeIdx, y: freqIdx, v: kurtosis}]
  let globalMaxK = 50;
  hist.forEach(h => { if (h.fh) Object.values(h.fh).forEach(k => { if (k > globalMaxK) globalMaxK = k; }); });

  const matrixData = [];
  hist.forEach((h, ti) => {
    if (h.gap) return;
    freqBins.forEach((freq, fi) => {
      const k = (h.fh && h.fh[freq]) ? h.fh[freq] : 0;
      if (k > 0) matrixData.push({ x: ti, y: fi, v: k });
    });
  });

  // Match symptoms to time indices for marker overlay
  const symColors = { speech:'#fb0', headache:'#f55', tinnitus:'#f8f', paresthesia:'#4bf', nausea:'#6d4', pressure:'#aaf', sleep:'#88f' };
  function tsToMin(ts) {
    if (!ts) return -1;
    const m = ts.match(/(\d+):(\d+)\s*(AM|PM)/i);
    if (!m) return -1;
    let hr = parseInt(m[1]); const mn = parseInt(m[2]);
    if (m[3].toUpperCase() === 'PM' && hr !== 12) hr += 12;
    if (m[3].toUpperCase() === 'AM' && hr === 12) hr = 0;
    return hr * 60 + mn;
  }
  const symMarkers = [];
  (symptomsData || []).forEach(s => {
    if (!s.symptom) return;
    const sTime = s.alertLocalTime || s.localTime || '';
    const sMin = tsToMin(sTime);
    if (sMin < 0) return;
    let bestIdx = -1, bestDist = Infinity;
    hist.forEach((h, i) => {
      if (!h.ts) return;
      const d = Math.abs(tsToMin(h.ts) - sMin);
      if (d < bestDist) { bestDist = d; bestIdx = i; }
    });
    if (bestIdx >= 0 && bestDist < 10) {
      symMarkers.push({ x: bestIdx, y: freqBins.length, sym: s.symptom, color: symColors[s.symptom] || '#888' });
    }
  });

  heatmapChart = new Chart(hmCtx2, {
    type: 'matrix',
    data: {
      datasets: [{
        data: matrixData,
        backgroundColor: ctx => {
          if (!ctx.raw) return 'transparent';
          const v = ctx.raw.v;
          if (v <= 0) return 'transparent';
          const t = Math.min(v / globalMaxK, 1);
          const fi = ctx.raw.y;
          const freq = freqBins[fi] || 830;
          const base = freqZoneColor(freq);
          return base + t.toFixed(2) + ')';
        },
        width: ctx => {
          const ca = ctx.chart.chartArea;
          if (!ca) return 10;
          const xScale = ctx.chart.scales.x;
          if (!xScale) return 10;
          return Math.abs(xScale.getPixelForValue(1) - xScale.getPixelForValue(0));
        },
        height: ctx => {
          const ca = ctx.chart.chartArea;
          if (!ca) return 10;
          const yScale = ctx.chart.scales.y;
          if (!yScale) return 10;
          // Size cell to match 1 unit on the y-axis, not chartArea/nFreqs
          return Math.abs(yScale.getPixelForValue(1) - yScale.getPixelForValue(0));
        },
        borderWidth: 0.5,
        borderColor: 'rgba(5,5,14,0.8)',
      },
      // Symptom markers as scatter points below the heatmap
      {
        type: 'scatter',
        data: symMarkers.map(s => ({ x: s.x, y: s.y })),
        backgroundColor: symMarkers.map(s => s.color),
        pointRadius: 5,
        pointStyle: 'triangle',
        pointRotation: 180,
        label: 'Symptoms',
      }],
    },
    plugins: [{
      // Draw symptom text labels below the triangles
      id: 'symLabels',
      afterDraw(chart) {
        if (!symMarkers.length) return;
        const ca = chart.chartArea;
        if (!ca) return;
        const xScale = chart.scales.x;
        const yScale = chart.scales.y;
        if (!xScale || !yScale) return;
        const ctx2 = chart.ctx;
        const dpr = window.devicePixelRatio || 1;
        const fontSize = Math.max(8, Math.round(9 * dpr));
        ctx2.font = 'bold ' + fontSize + 'px monospace';
        ctx2.textAlign = 'center';

        // Group symptoms by x index to stack labels
        const byIdx = {};
        symMarkers.forEach(s => {
          if (!byIdx[s.x]) byIdx[s.x] = [];
          if (!byIdx[s.x].find(e => e.sym === s.sym)) byIdx[s.x].push(s);
        });

        Object.entries(byIdx).forEach(([idx, syms]) => {
          const xPx = xScale.getPixelForValue(parseInt(idx));
          const yBase = yScale.getPixelForValue(freqBins.length) + 8 * dpr;
          syms.forEach((s, si) => {
            ctx2.fillStyle = s.color;
            ctx2.save();
            ctx2.translate(xPx, yBase + si * (fontSize + 2));
            ctx2.rotate(Math.PI / 6);
            ctx2.textAlign = 'left';
            ctx2.fillText(s.sym, 0, 0);
            ctx2.restore();
          });
        });
      }
    }],
    options: {
      responsive: true, maintainAspectRatio: false,
      plugins: {
        legend: { display: false },
        tooltip: {
          backgroundColor: 'rgba(8,8,18,0.95)', borderColor: '#2a2a4a', borderWidth: 1,
          bodyFont: { size: 10 }, titleFont: { size: 11 },
          callbacks: {
            title: ctx => {
              const d = ctx[0].raw;
              const h = hist[d.x] || {};
              return h.ts + '  |  EI-A:' + (h.eiA||0).toFixed(0) + '  B:' + (h.eiB||0).toFixed(0) + '  UL:' + (h.eiUL||0).toFixed(0) + '  k:' + (h.k||0).toFixed(0);
            },
            label: ctx => {
              // Show ALL frequencies for this time column, not just the hovered cell
              const ti = ctx.raw.x;
              const h = hist[ti] || {};
              if (!h.fh) return '';
              // Only called once per tooltip — return array of all freqs
              if (ctx.dataIndex !== ctx.dataset.data.findIndex(d => d.x === ti)) return null;
              const lines = [];
              freqBins.forEach(f => {
                const k = h.fh[f] || 0;
                if (k > 0) {
                  const zone = f < 640 ? 'A' : f < 870 ? 'B' : 'UL';
                  lines.push(f + ' MHz [' + zone + ']: kurt=' + k.toFixed(1));
                }
              });
              return lines;
            },
            // Filter to show only one tooltip item per column (not per cell)
            filter: (item, data) => {
              const ti = item.raw.x;
              const firstIdx = data.datasets[0].data.findIndex(d => d.x === ti);
              return item.dataIndex === firstIdx;
            }
          }
        },
      },
      scales: {
        x: {
          type: 'linear', offset: false, min: -0.5, max: hist.length - 0.5,
          display: false,
        },
        y: {
          type: 'linear', offset: false, min: -0.5, max: freqBins.length + 5, reverse: true,
          display: false,
        },
      },
    },
  });
}

// (old canvas helpers removed — using Chart.js now)

// (old time parsing and canvas helpers removed — Chart.js handles this)

// ── Sync vertical cursor between timeline and heatmap ──
// Converts hover position to a data INDEX, then draws line at that index on both charts
let syncIdx = null;

const verticalLinePlugin = {
  id: 'verticalLine',
  afterDraw(chart) {
    if (syncIdx === null || !hist.length) return;
    const ca = chart.chartArea;
    if (!ca) return;
    const xScale = chart.scales.x;
    if (!xScale) return;
    const xPx = xScale.getPixelForValue(syncIdx);
    if (xPx < ca.left || xPx > ca.right) return;
    const ctx2 = chart.ctx;
    ctx2.save();
    ctx2.beginPath();
    ctx2.moveTo(xPx, ca.top);
    ctx2.lineTo(xPx, ca.bottom);
    ctx2.strokeStyle = 'rgba(255,255,255,0.3)';
    ctx2.lineWidth = 1;
    ctx2.setLineDash([4, 3]);
    ctx2.stroke();
    ctx2.restore();
  },
  afterEvent(chart, args) {
    if (args.event.type === 'mouseout') { syncIdx = null; return; }
    if (args.event.type !== 'mousemove') return;
    const ca = chart.chartArea;
    if (!ca) return;
    const xPx = args.event.x;
    if (xPx < ca.left || xPx > ca.right) { syncIdx = null; return; }
    const xScale = chart.scales.x;
    if (!xScale) return;
    syncIdx = Math.round(xScale.getValueForPixel(xPx));
    // Redraw the other chart so its line updates
    const other = chart === timelineChart ? heatmapChart : timelineChart;
    if (other) other.draw();
  }
};
Chart.register(verticalLinePlugin);

// ── Update timeline chart with new data ──
function updateTimeline() {
  if (hist.length < 2) return;
  const labels = hist.map(h => h.ts || '');
  const nullGap = h => h.gap ? null : undefined;
  timelineChart.data.labels = labels;
  timelineChart.data.datasets[0].data = hist.map(h => h.gap ? null : (h.eiA || 0));
  timelineChart.data.datasets[1].data = hist.map(h => h.gap ? null : (h.eiB || 0));
  timelineChart.data.datasets[2].data = hist.map(h => h.gap ? null : (h.eiUL || 0));
  timelineChart.data.datasets[3].data = hist.map(h => h.gap ? null : ((h.eiA||0)+(h.eiB||0)+(h.eiUL||0)));
  timelineChart.data.datasets[4].data = hist.map(h => h.gap ? null : (h.k || 0));
  timelineChart.update('none');
}

// (old heatmap code removed — using Chart.js matrix plugin)

function drawHeatmap() {
  const { W, H, dpr } = setupCanvas(hmCv);
  hmCtx.clearRect(0, 0, W, H);
  if (!hist.length || !freqBins.length) return;

  const nFreqs = freqBins.length;
  const nTime = hist.length;

  // Layout
  const labelW = 55 * dpr;
  const bottomH = 80 * dpr;
  const topH = 4 * dpr;
  const plotW = W - labelW;
  const plotH = H - bottomH - topH;
  const cellH = Math.max(1, plotH / nFreqs);

  // Use shared time axis (same as timeline above)
  const { tMins: hmTMins, tMin: hmTMin, tRange: hmTRange } = computeTimeAxis();

  function hmXi(i) {
    const t = hmTMins[i];
    if (t === null) return -999;
    return labelW + ((t - hmTMin) / hmTRange) * plotW;
  }

  // Compute cell width per entry based on gap to next
  function hmCellW(i) {
    if (i >= nTime - 1) return plotW / nTime;
    const x1 = hmXi(i);
    const x2 = hmXi(i + 1);
    if (x1 < 0 || x2 < 0) return 0;
    return Math.max(x2 - x1, 1);
  }

  // Find global max kurtosis for normalization
  let globalMaxK = 50;
  hist.forEach(h => {
    if (h.fh) {
      Object.values(h.fh).forEach(k => { if (k > globalMaxK) globalMaxK = k; });
    }
  });

  // Draw cells with time-proportional widths
  for (let fi = 0; fi < nFreqs; fi++) {
    const freq = freqBins[fi];
    const rgb = freqZoneRgb(freq);
    const y = topH + fi * cellH;

    for (let ti = 0; ti < nTime; ti++) {
      const h = hist[ti];
      if (h.gap) continue;
      const x = hmXi(ti);
      if (x < 0) continue;
      const cw = hmCellW(ti);
      const k = (h.fh && h.fh[freq]) ? h.fh[freq] : 0;
      const t = Math.min(k / globalMaxK, 1);

      hmCtx.fillStyle = heatColor(t, rgb);
      hmCtx.fillRect(x, y, cw + 0.5, cellH + 0.5);
    }
  }

  // Zone separator lines
  let prevZone = '';
  const fontSize = Math.max(10, Math.round(dpr * 9));
  hmCtx.font = fontSize + 'px monospace';
  for (let fi = 0; fi < nFreqs; fi++) {
    const freq = freqBins[fi];
    const zone = freqZoneLabel(freq);
    const y = topH + fi * cellH;

    if (zone !== prevZone && prevZone !== '') {
      hmCtx.strokeStyle = '#333';
      hmCtx.lineWidth = 1;
      hmCtx.beginPath();
      hmCtx.moveTo(labelW, y);
      hmCtx.lineTo(W, y);
      hmCtx.stroke();
    }
    prevZone = zone;

    // Freq label
    const zoneColor = freq < 640 ? '#28f' : freq < 870 ? '#f80' : '#a4f';
    hmCtx.fillStyle = '#445';
    hmCtx.textAlign = 'right';
    hmCtx.fillText(freq.toString(), labelW - 6 * dpr, y + cellH * 0.75);
  }

  // No time labels — shared x-axis with timeline above

  // Symptom markers — collect per-column, dedupe, draw at bottom
  const toMin = (ts) => {
    const m = (ts||'').match(/(\d+):(\d+)\s*(AM|PM)/i);
    if (!m) return -1;
    let hr = parseInt(m[1]); const mn = parseInt(m[2]);
    if (m[3].toUpperCase() === 'PM' && hr !== 12) hr += 12;
    if (m[3].toUpperCase() === 'AM' && hr === 12) hr = 0;
    return hr * 60 + mn;
  };
  const symColors = {
    speech: '#fb0', headache: '#f55', tinnitus: '#f8f',
    paresthesia: '#4bf', nausea: '#6d4', pressure: '#aaf'
  };

  // Group unique symptoms per column
  const colSyms = {};  // colIdx -> Set of symptom names
  symptomsData.forEach(s => {
    if (!s.symptom) return;
    const alertLocal = s.alertLocalTime || s.localTime || '';
    if (!alertLocal) return;
    let bestIdx = -1, bestDist = Infinity;
    hist.forEach((h, i) => {
      if (!h.ts) return;
      const d = Math.abs(toMin(h.ts) - toMin(alertLocal));
      if (d < bestDist) { bestDist = d; bestIdx = i; }
    });
    if (bestIdx >= 0 && bestDist < 10) {
      if (!colSyms[bestIdx]) colSyms[bestIdx] = new Set();
      colSyms[bestIdx].add(s.symptom);
    }
  });

  // Draw labels at bottom of heatmap, stacked per column
  const labelFont = Math.round(8 * dpr);
  hmCtx.font = 'bold ' + labelFont + 'px monospace';
  const bottomBase = topH + plotH + 4;

  Object.entries(colSyms).forEach(([idxStr, symSet]) => {
    const idx = parseInt(idxStr);
    const x = hmXi(idx) + hmCellW(idx) / 2;
    let offset = 0;
    Array.from(symSet).forEach(sym => {
      const color = symColors[sym] || '#888';
      hmCtx.save();
      hmCtx.translate(x, bottomBase + offset);
      hmCtx.rotate(Math.PI / 5);
      hmCtx.fillStyle = color;
      hmCtx.textAlign = 'left';
      hmCtx.fillText(sym, 2, 0);
      hmCtx.restore();
      offset += labelFont + 3;
    });

    // Small tick mark from heatmap bottom to labels
    hmCtx.strokeStyle = '#333';
    hmCtx.lineWidth = 1;
    hmCtx.beginPath();
    hmCtx.moveTo(x, topH + plotH);
    hmCtx.lineTo(x, bottomBase);
    hmCtx.stroke();
  });

  // Symptom legend at top-right
  const legendSymptoms = [
    ['speech', '#fb0'], ['headache', '#f55'], ['tinnitus', '#f8f'],
    ['paresthesia', '#4bf'], ['nausea', '#6d4'], ['pressure', '#aaf']
  ];
  // Only show symptoms that actually appear in the data
  const seenSymptoms = new Set(symptomsData.map(s => s.symptom).filter(Boolean));
  const activeLegend = legendSymptoms.filter(([s]) => seenSymptoms.has(s));
  if (activeLegend.length > 0) {
    const legFont = Math.round(8 * dpr);
    hmCtx.font = legFont + 'px monospace';
    hmCtx.textAlign = 'right';
    let lx = W - 8 * dpr;
    let ly = topH - 4;
    activeLegend.reverse().forEach(([label, color]) => {
      const tw = hmCtx.measureText(label).width;
      // Color dot + label
      hmCtx.fillStyle = '#0c0c14';
      hmCtx.fillRect(lx - tw - 14 * dpr, ly - legFont, tw + 16 * dpr, legFont + 4);
      hmCtx.fillStyle = color;
      hmCtx.fillRect(lx - tw - 12 * dpr, ly - legFont + 3, 6 * dpr, legFont - 2);
      hmCtx.fillText(label, lx - 4 * dpr, ly);
      ly -= legFont + 6;
    });
  }

  // Zone labels on right edge
  const zones = [{f: 622, label: 'A', color: '#28f'}, {f: 826, label: 'B', color: '#f80'}, {f: 878, label: 'UL', color: '#a4f'}];
  hmCtx.font = 'bold ' + (fontSize + 2) + 'px monospace';
  hmCtx.textAlign = 'left';
  zones.forEach(z => {
    const fi = freqBins.indexOf(z.f);
    if (fi >= 0) {
      hmCtx.fillStyle = z.color;
      hmCtx.fillText(z.label, W - 20 * dpr, topH + fi * cellH + cellH * 0.7);
    }
  });
}

// ── Main update ──────────────────────────────────────────────────────────
function upd(data) {
  if (!data || !data.current) return;
  const c = data.current;

  // Metric color based on maxK with continuous gradient
  const mcolor = metricColor(c.maxK || 0);

  const setMetric = (id, val, sub) => {
    const el = document.getElementById(id);
    if (!el) return;
    el.textContent = val;
    el.style.color = mcolor;
    if (sub) document.getElementById(id + 'Sub').textContent = sub;
  };

  setMetric('ei',
    c.ei != null ? Math.round(c.ei) : '—',
    'EI-A: ' + (c.eiA != null ? Math.round(c.eiA) : '—') + '  /  EI-B: ' + (c.eiB != null ? Math.round(c.eiB) : '—')
  );
  setMetric('kurt',   c.maxK != null ? c.maxK.toFixed(1) : '—', 'cycle ' + c.cycle);
  setMetric('pulses', c.pulses != null ? c.pulses.toLocaleString() : '—', 'this cycle');
  setMetric('nact',   c.nActive != null ? c.nActive : '—', 'of 13 targets');

  // Zone Power bars — show EI values
  const maxEIForBar = 1500;  // scale bars to this max EI
  const pct = v => Math.min((v || 0) / maxEIForBar * 100, 100).toFixed(1) + '%';

  document.getElementById('bA').style.width = pct(c.eiA);
  document.getElementById('vA').textContent  = (c.eiA != null ? Math.round(c.eiA) : '—');
  document.getElementById('bB').style.width = pct(c.eiB);
  document.getElementById('vB').textContent  = (c.eiB != null ? Math.round(c.eiB) : '—');
  // UL zone: use zoneULMax kurtosis as proxy (no eiUL field in current API)
  const eiU = c.zoneULMax || 0;
  document.getElementById('bU').style.width = Math.min(eiU / 200 * 100, 100).toFixed(1) + '%';
  document.getElementById('vU').textContent  = eiU.toFixed(1);

  // Symptoms — use localTime, newest first
  const sl = document.getElementById('symList');
  sl.innerHTML = '';
  const syms = (data.symptoms || []).filter(s => s.symptom);
  syms.slice(-12).reverse().forEach(s => {
    const d = document.createElement('div');
    d.className = 'sym-item ' + (s.symptom || '');
    const localT = s.localTime || '—';
    const mk = s.alert_max_kurt
               ? Math.round(s.alert_max_kurt)
               : (s.rf_context && s.rf_context.max_kurt ? Math.round(s.rf_context.max_kurt) : null);
    const nf = s.alert_n_active || (s.rf_context ? s.rf_context.n_active : null);
    let detail = '';
    if (mk) detail += 'k=' + mk;
    if (nf) detail += (detail ? '  ' : '') + nf + ' ch';
    d.innerHTML =
      '<span class="sym-time">' + localT + '</span>' +
      '<span class="sym-tag ' + (s.symptom || '') + '">' + (s.symptom || '') + '</span>' +
      '<span class="sym-detail">' + detail + '</span>';
    sl.appendChild(d);
  });

  // Status header — CST from localTime
  document.getElementById('dot').className = 'dot live';
  document.getElementById('st').textContent = c.localTime + '  |  cycle ' + c.cycle;

  // Build history array for timeline + heatmap
  if (data.history) {
    hist = data.history.map(h => ({
      k:    h.gap ? null : (h.maxK || 0),
      eiA:  h.gap ? null : (h.eiA || 0),
      eiB:  h.gap ? null : (h.eiB || 0),
      eiUL: h.gap ? null : (h.eiUL || 0),
      ts:   h.ts     || '',
      sym:  h.symptom || null,
      fh:   h.fh     || {},
      gap:  h.gap     || false,
    }));
  }
  if (data.freqBins) freqBins = data.freqBins;
  symptomsData = data.symptoms || [];

  updateTimeline();
  // Only rebuild heatmap when data length changes (new cycle arrived)
  if (!heatmapChart || hist.length !== heatmapChart._lastLen) {
    buildHeatmap();
    if (heatmapChart) heatmapChart._lastLen = hist.length;
  }
}

// ── Poll loop ─────────────────────────────────────────────────────────────
let currentOffset = 0;
let autoScroll = true;

function navScroll(delta) {
  currentOffset = Math.max(0, currentOffset - delta);
  autoScroll = (currentOffset === 0);
  pollNow();
}

function goLive() {
  currentOffset = 0;
  autoScroll = true;
  pollNow();
}

function pollNow() {
  fetch('/api/state?offset=' + currentOffset)
    .then(r => r.json())
    .then(d => {
      upd(d);
      const nav = document.getElementById('navInfo');
      if (currentOffset === 0) {
        nav.textContent = 'LIVE';
        nav.style.color = '#4a4';
      } else {
        nav.textContent = '-' + currentOffset;
        nav.style.color = '#fa0';
      }
    });
}

function poll() {
  fetch('/api/state?offset=' + currentOffset)
    .then(r => r.json())
    .then(d => { upd(d); setTimeout(poll, autoScroll ? 5000 : 30000); })
    .catch(() => {
      document.getElementById('dot').className = 'dot stale';
      document.getElementById('st').textContent = 'disconnected';
      setTimeout(poll, 5000);
    });
}

poll();
// Chart.js handles resize automatically via responsive:true
</script>
</body>
</html>"""


def parse_cycle(cycle):
    """Extract summary from a sentinel cycle entry."""
    max_k = 0
    n_active = 0
    total_pulses = 0
    zone_a_max = 0
    zone_b_max = 0
    zone_ul_max = 0
    freqs = []

    NOMINAL_TARGETS = [622, 624, 628, 630, 632, 634, 636,
                       826, 828, 830, 832, 834, 878]
    active_targets = set()

    for freq_str, readings in cycle.get("stare", {}).items():
        for r in readings:
            k = r.get("kurtosis", 0)
            p = r.get("pulse_count", 0)
            f = r.get("freq_mhz", r.get("nominal_freq_mhz", 0))
            if k > max_k:
                max_k = k
            if k > 20 and isinstance(f, (int, float)):
                # Bucket to nearest nominal target
                nearest = min(NOMINAL_TARGETS, key=lambda t: abs(t - f))
                if abs(nearest - f) < 4:
                    active_targets.add(nearest)
            total_pulses += p
            if isinstance(f, (int, float)):
                if 618 < f < 640 and k > zone_a_max:
                    zone_a_max = k
                elif 820 < f < 840 and k > zone_b_max:
                    zone_b_max = k
                elif 870 < f < 890 and k > zone_ul_max:
                    zone_ul_max = k
                if k > 10:
                    freqs.append({"freq": round(f, 1), "kurt": round(k, 1), "pulses": p})

    return {
        "cycle": cycle.get("cycle"),
        "timestamp": cycle.get("timestamp", ""),
        "maxK": round(max_k, 1),
        "nActive": len(active_targets),
        "pulses": total_pulses,
        "ei": cycle.get("exposure_index"),
        "eiA": cycle.get("ei_zone_a"),
        "eiB": cycle.get("ei_zone_b"),
        "zoneAMax": round(zone_a_max, 1),
        "zoneBMax": round(zone_b_max, 1),
        "zoneULMax": round(zone_ul_max, 1),
        "freqs": sorted(freqs, key=lambda x: x["kurt"], reverse=True)[:40],
    }


# Cache for all loaded cycles
_cycle_cache = []
_last_file_check = 0
_known_files = set()


def load_all_cycles():
    """Load all sentinel cycles, using cache. Check for new files every 10s."""
    global _cycle_cache, _last_file_check, _known_files

    now = time.time()
    logs = sorted(glob.glob(f"{RESULTS_DIR}/sentinel_*.jsonl"))
    current_files = set(logs)

    # Full reload if files changed, otherwise just tail the latest
    if current_files != _known_files or now - _last_file_check > 10:
        _known_files = current_files
        _last_file_check = now

        # Only reload files we haven't seen or the latest (which may have new lines)
        all_cycles = []
        for logf in logs:
            try:
                with open(logf) as f:
                    for line in f:
                        try:
                            all_cycles.append(json.loads(line))
                        except json.JSONDecodeError:
                            pass
            except (FileNotFoundError, IOError):
                pass
        _cycle_cache = all_cycles

    return _cycle_cache


def get_state():
    """Build full dashboard state from all data."""
    cycles = load_all_cycles()
    if not cycles:
        return None

    latest = parse_cycle(cycles[-1])

    # Add local time
    try:
        ts = cycles[-1].get("timestamp", "")
        if ts:
            from datetime import datetime as dt
            utc_dt = dt.fromisoformat(ts.replace("Z", "+00:00"))
            local_dt = utc_dt.astimezone()
            latest["localTime"] = local_dt.strftime("%I:%M:%S %p")
        else:
            latest["localTime"] = "—"
    except Exception:
        latest["localTime"] = "—"

    # Canonical frequency bins for heatmap (nominal targets, rounded)
    FREQ_BINS = [622, 624, 628, 630, 632, 634, 636,
                 826, 828, 830, 832, 834, 878]

    # History: last 60 cycles with per-freq kurtosis for heatmap
    # Insert null entries for gaps > 5 minutes so the chart shows blank space
    history = []
    prev_cycle_time = None
    # Window: show 60 cycles, offset from end by 'offset' param
    window_size = 60
    total_cycles = len(cycles)
    # offset=0 means latest, offset=60 means one window back
    history_offset = getattr(get_state, '_offset', 0)
    end_idx = total_cycles - history_offset
    start_idx = max(0, end_idx - window_size)
    end_idx = max(start_idx + 1, end_idx)

    for c in cycles[start_idx:end_idx]:
        max_k = 0
        # Build per-bin max kurtosis
        freq_heat = {f: 0.0 for f in FREQ_BINS}
        for freq_str, readings in c.get("stare", {}).items():
            for r in readings:
                k = r.get("kurtosis", 0)
                if k > max_k:
                    max_k = k
                # Bucket into nearest nominal freq
                f = r.get("nominal_freq_mhz",
                          r.get("freq_mhz", 0))
                if isinstance(f, (int, float)):
                    nearest = min(FREQ_BINS, key=lambda b: abs(b - f))
                    if abs(nearest - f) < 4:
                        freq_heat[nearest] = max(freq_heat[nearest],
                                                 round(k, 1))
        try:
            ts = c.get("timestamp", "")
            if ts:
                from datetime import datetime as dt
                utc_dt = dt.fromisoformat(ts.replace("Z", "+00:00"))
                local_dt = utc_dt.astimezone()
                ts_short = local_dt.strftime("%I:%M %p")
            else:
                ts_short = ""
        except Exception:
            ts_short = ""

        # Compute EI if not in the cycle data (old cycles)
        ei = c.get("exposure_index")
        eiA = c.get("ei_zone_a")
        eiB = c.get("ei_zone_b")
        eiUL = 0.0
        if ei is None:
            K_NOISE = 8.5
            ei = 0.0
            eiA = 0.0
            eiB = 0.0
            for freq_str2, readings2 in c.get("stare", {}).items():
                for r2 in readings2:
                    k2 = r2.get("kurtosis", K_NOISE)
                    pdb = r2.get("mean_pwr_db", -44)
                    pl = 10 ** (pdb / 10)
                    pc = r2.get("pulse_count", 0)
                    pls = r2.get("pulses", [])
                    if isinstance(pls, list) and pls and isinstance(pls[0], dict):
                        tw = sum(p.get("width_us", 0) for p in pls if isinstance(p, dict))
                        nl = len([p for p in pls if isinstance(p, dict)])
                        if nl > 0 and pc > nl:
                            tw = (tw / nl) * pc
                    else:
                        tw = pc * 2.5
                    ei_r = pl * tw * max(k2 / K_NOISE, 1.0)
                    ei += ei_r
                    f2 = r2.get("freq_mhz", r2.get("nominal_freq_mhz", 0))
                    if isinstance(f2, (int, float)):
                        if 618 < f2 < 640: eiA += ei_r
                        elif 820 < f2 < 840: eiB += ei_r
                        elif 870 < f2 < 890: eiUL += ei_r
        else:
            # Compute UL EI from stare data even when total EI exists
            K_NOISE = 8.5
            for freq_str2, readings2 in c.get("stare", {}).items():
                for r2 in readings2:
                    f2 = r2.get("freq_mhz", r2.get("nominal_freq_mhz", 0))
                    if isinstance(f2, (int, float)) and 870 < f2 < 890:
                        k2 = r2.get("kurtosis", K_NOISE)
                        pdb = r2.get("mean_pwr_db", -44)
                        pl = 10 ** (pdb / 10)
                        pc = r2.get("pulse_count", 0)
                        pls = r2.get("pulses", [])
                        if isinstance(pls, list) and pls and isinstance(pls[0], dict):
                            tw = sum(p.get("width_us", 0) for p in pls if isinstance(p, dict))
                            nl = len([p for p in pls if isinstance(p, dict)])
                            if nl > 0 and pc > nl:
                                tw = (tw / nl) * pc
                        else:
                            tw = pc * 2.5
                        eiUL += pl * tw * max(k2 / K_NOISE, 1.0)

        # Detect gaps > 5 min — insert null entry so chart shows break
        try:
            cycle_time = local_dt if ts else None
        except:
            cycle_time = None
        if prev_cycle_time and cycle_time:
            gap_sec = (cycle_time - prev_cycle_time).total_seconds()
            if gap_sec > 900:  # > 15 min gap (cycles are ~10 min with 13 targets)
                history.append({
                    "maxK": None, "ei": None, "eiA": None, "eiB": None,
                    "ts": "", "fh": {}, "symptom": None, "gap": True,
                })
        prev_cycle_time = cycle_time

        history.append({
            "maxK": round(max_k, 1),
            "ei": round(ei, 1) if ei else 0,
            "eiA": round(eiA, 1) if eiA else 0,
            "eiB": round(eiB, 1) if eiB else 0,
            "eiUL": round(eiUL, 1),
            "ts": ts_short,
            "fh": freq_heat,
            "symptom": None,
        })

    # Overlay symptoms onto timeline
    symptoms = []
    try:
        with open(SYMPTOM_LOG) as f:
            for line in f:
                try:
                    s = json.loads(line)
                    # Convert timestamps to local time
                    if s.get("timestamp"):
                        try:
                            from datetime import datetime as dt
                            utc_dt = dt.fromisoformat(
                                s["timestamp"].replace("Z", "+00:00"))
                            local_dt = utc_dt.astimezone()
                            s["localTime"] = local_dt.strftime("%I:%M %p")
                        except Exception:
                            pass
                    # Also convert alert_ts to local for heatmap placement
                    if s.get("alert_ts"):
                        try:
                            from datetime import datetime as dt
                            a_dt = dt.fromisoformat(
                                s["alert_ts"].replace("Z", "+00:00"))
                            a_local = a_dt.astimezone()
                            s["alertLocalTime"] = a_local.strftime(
                                "%I:%M %p")
                        except Exception:
                            pass
                    symptoms.append(s)
                except json.JSONDecodeError:
                    pass
    except FileNotFoundError:
        pass

    # Filter symptoms to only those within the displayed time window
    # This prevents old symptoms from matching current cycles by time-of-day
    window_symptoms = []
    if history:
        # Get the date range of displayed history from timestamps
        hist_dates = set()
        for c in cycles[start_idx:end_idx]:
            ts = c.get("timestamp", "")
            if ts:
                hist_dates.add(ts[:10])  # YYYY-MM-DD
        for s in symptoms:
            sts = s.get("timestamp", s.get("alert_ts", ""))
            if sts and sts[:10] in hist_dates:
                window_symptoms.append(s)
    else:
        window_symptoms = symptoms

    return {
        "current": latest,
        "history": history,
        "freqBins": FREQ_BINS,
        "symptoms": window_symptoms,
    }


# ── Direction Finding state ────────────────────────────────────────────────
import subprocess
import threading
import numpy as np
from scipy import stats as sp_stats

_df_running = False
_df_data = {}       # latest capture results
_df_bearings = []   # saved bearing points
_df_lock = threading.Lock()
_df_thread = None

DF_FREQS = [622, 624, 628, 630, 632, 634, 636]
DF_SAMPLE_RATE = 2_400_000
DF_DWELL_MS = 100  # 100ms dwell — fast captures for DF
DF_SETTLE = 24000  # reduced settle for speed
DF_DC_NOTCH = 32


import ctypes

_rtl_lib = None
_rtl_dev = None


def _rtl_open():
    """Open RTL-SDR device once, keep handle for reuse."""
    global _rtl_lib, _rtl_dev
    if _rtl_dev is not None:
        return True
    try:
        _rtl_lib = ctypes.CDLL("librtlsdr.so")
        dev_p = ctypes.c_void_p()
        ret = _rtl_lib.rtlsdr_open(ctypes.byref(dev_p), 0)
        if ret != 0:
            log.error(f"rtlsdr_open failed: {ret}")
            return False
        _rtl_dev = dev_p
        _rtl_lib.rtlsdr_set_sample_rate(_rtl_dev, DF_SAMPLE_RATE)
        _rtl_lib.rtlsdr_set_tuner_gain_mode(_rtl_dev, 1)
        _rtl_lib.rtlsdr_set_tuner_gain(_rtl_dev, 280)  # 28.0 dB
        _rtl_lib.rtlsdr_reset_buffer(_rtl_dev)
        log.info("RTL-SDR opened via ctypes — persistent handle")
        return True
    except Exception as e:
        log.error(f"rtlsdr open error: {e}")
        return False


def _rtl_close():
    """Close RTL-SDR device."""
    global _rtl_dev
    if _rtl_dev is not None and _rtl_lib is not None:
        try:
            _rtl_lib.rtlsdr_close(_rtl_dev)
        except Exception:
            pass
        _rtl_dev = None
        log.info("RTL-SDR closed")


import SoapySDR

_soapy_dev = None
_soapy_stream = None
_soapy_buf = None


def _soapy_open():
    """Open SoapySDR device once, keep for reuse."""
    global _soapy_dev, _soapy_stream, _soapy_buf
    if _soapy_dev is not None:
        return True
    try:
        os.system("pkill -9 rtl_sdr 2>/dev/null")
        time.sleep(0.3)
        _soapy_dev = SoapySDR.Device({"driver": "rtlsdr"})
        _soapy_dev.setSampleRate(SoapySDR.SOAPY_SDR_RX, 0, DF_SAMPLE_RATE)
        _soapy_dev.setGain(SoapySDR.SOAPY_SDR_RX, 0, 28)
        _soapy_stream = _soapy_dev.setupStream(SoapySDR.SOAPY_SDR_RX, SoapySDR.SOAPY_SDR_CF32)
        _soapy_dev.activateStream(_soapy_stream)
        _soapy_buf = np.zeros(240000, dtype=np.complex64)
        log.info("SoapySDR opened — persistent handle")
        return True
    except Exception as e:
        log.error(f"SoapySDR open failed: {e}")
        _soapy_dev = None
        return False


def _soapy_close():
    """Close SoapySDR device."""
    global _soapy_dev, _soapy_stream
    if _soapy_dev and _soapy_stream:
        try:
            _soapy_dev.deactivateStream(_soapy_stream)
            _soapy_dev.closeStream(_soapy_stream)
        except Exception:
            pass
    _soapy_dev = None
    _soapy_stream = None
    log.info("SoapySDR closed")


def _df_capture_one(freq_mhz, gain=28.0):
    """Capture via SoapySDR — retune + read, no process spawning. ~30ms per freq."""
    if not _soapy_open():
        return {"freq": freq_mhz, "kurt": 0, "pulses": 0, "pwr": -99}

    try:
        t0 = time.time()
        _soapy_dev.setFrequency(SoapySDR.SOAPY_SDR_RX, 0, freq_mhz * 1e6)
        time.sleep(0.02)  # PLL settle
        # Flush stale samples
        _soapy_dev.readStream(_soapy_stream, [_soapy_buf], len(_soapy_buf), timeoutUs=100000)
        # Real capture
        sr = _soapy_dev.readStream(_soapy_stream, [_soapy_buf], len(_soapy_buf), timeoutUs=500000)
        dt = time.time() - t0
        if sr.ret <= 0:
            log.warning(f"DF {freq_mhz}MHz: readStream ret={sr.ret}")
            return {"freq": freq_mhz, "kurt": 0, "pulses": 0, "pwr": -99}
        z = _soapy_buf[:sr.ret]
        log.debug(f"DF {freq_mhz}MHz: {sr.ret} samples in {dt:.3f}s")
    except Exception as e:
        log.error(f"DF {freq_mhz}MHz: {e}")
        _soapy_close()
        return {"freq": freq_mhz, "kurt": 0, "pulses": 0, "pwr": -99}

    amp = np.abs(z).astype(np.float32)
    mu, sigma = np.mean(amp), np.std(amp)
    kurt = float(sp_stats.kurtosis(amp, fisher=False))
    pwr = float(10 * np.log10(np.mean(amp**2))) if np.mean(amp**2) > 0 else -99
    thresh = mu + 4 * sigma
    pulses = int(np.sum(np.diff((amp > thresh).astype(np.int8)) == 1))
    return {"freq": freq_mhz, "kurt": round(kurt, 1), "pulses": pulses, "pwr": round(pwr, 1)}


_df_measurement = None  # result of last completed measurement
_df_progress = {"state": "idle", "cycle": 0, "total": 10, "countdown": 0}
N_CYCLES = 10
PREP_SECONDS = 10


def _df_measure(azimuth):
    """Run a full measurement: 10s prep, then N rapid captures, running average updated live."""
    global _df_measurement, _df_progress

    _df_progress = {"state": "prep", "cycle": 0, "total": N_CYCLES, "countdown": PREP_SECONDS}

    for s in range(PREP_SECONDS, 0, -1):
        if not _df_running:
            return
        _df_progress["countdown"] = s
        time.sleep(1)

    _df_progress["state"] = "scanning"
    _df_progress["countdown"] = 0

    # Running accumulators per freq
    sums = {f: {"kurt": 0, "pulses": 0, "pwr": 0, "kurt_max": 0, "kurt_min": 9999, "n": 0} for f in DF_FREQS}

    for cyc in range(N_CYCLES):
        if not _df_running:
            return
        _df_progress["cycle"] = cyc + 1

        # One capture per freq — fast, ~300ms each for 7 freqs = ~2s per cycle
        for f in DF_FREQS:
            if not _df_running:
                return
            r = _df_capture_one(f)
            s = sums[f]
            s["kurt"] += r["kurt"]
            s["pulses"] += r["pulses"]
            s["pwr"] += r["pwr"]
            s["n"] += 1
            if r["kurt"] > s["kurt_max"]:
                s["kurt_max"] = r["kurt"]
            if r["kurt"] < s["kurt_min"]:
                s["kurt_min"] = r["kurt"]

        # Build running average and push to live display
        avg = {}
        for f in DF_FREQS:
            s = sums[f]
            n = max(s["n"], 1)
            avg[f] = {
                "freq": f,
                "kurt": round(s["kurt"] / n, 1),
                "kurt_max": round(s["kurt_max"], 1),
                "kurt_min": round(s["kurt_min"], 1),
                "pulses": round(s["pulses"] / n),
                "pwr": round(s["pwr"] / n, 1),
            }
        with _df_lock:
            _df_data.update({
                "freqs": avg,
                "ts": datetime.now().strftime("%H:%M:%S"),
                "max_kurt": max((v["kurt"] for v in avg.values()), default=0),
            })

    # Final averaged result
    final_avg = {}
    for f in DF_FREQS:
        s = sums[f]
        n = max(s["n"], 1)
        final_avg[f] = {
            "freq": f,
            "kurt": round(s["kurt"] / n, 1),
            "kurt_max": round(s["kurt_max"], 1),
            "kurt_min": round(s["kurt_min"], 1),
            "pulses": round(s["pulses"] / n),
            "pwr": round(s["pwr"] / n, 1),
        }

    result = {
        "azimuth": azimuth,
        "freqs": final_avg,
        "n_cycles": N_CYCLES,
        "ts": datetime.now().strftime("%H:%M:%S"),
        "saved_at": datetime.now().isoformat(),
        "max_kurt": max((r["kurt"] for r in final_avg.values()), default=0),
    }

    _df_bearings.append(result)
    with open("results/df_bearings.json", "w") as f:
        json.dump(_df_bearings, f, indent=2, default=str)

    _df_progress = {"state": "done", "cycle": N_CYCLES, "total": N_CYCLES, "countdown": 0}
    with _df_lock:
        _df_data.update({"freqs": final_avg, "max_kurt": result["max_kurt"], "ts": result["ts"]})


_df_disconnected = False
_df_live = False
_df_live_thread = None


_df_live_accum = {}
_df_live_recent = []  # last 3 full cycle max-kurts
_df_live_all_maxk = []  # ALL cycle max-kurts for running average


def _df_live_loop():
    """Continuous fast scan — real-time + running average + last-3-cycle average."""
    global _df_live, _df_live_accum, _df_live_recent
    _df_live_accum = {f: {"kurt_sum": 0, "pulses_sum": 0, "pwr_sum": 0, "n": 0, "kurt_max": 0} for f in DF_FREQS}
    _df_live_recent = []
    _df_live_all_maxk.clear()
    try:
      while _df_live:
        cycle_kurts = []
        for f in DF_FREQS:
            if not _df_live:
                break
            r = _df_capture_one(f)
            cycle_kurts.append(r["kurt"])
            # Running accumulator
            a = _df_live_accum[f]
            a["kurt_sum"] += r["kurt"]
            a["pulses_sum"] += r["pulses"]
            a["pwr_sum"] += r["pwr"]
            a["n"] += 1
            if r["kurt"] > a["kurt_max"]:
                a["kurt_max"] = r["kurt"]
            # Build avg dict
            avgs = {}
            for ff in DF_FREQS:
                aa = _df_live_accum[ff]
                nn = max(aa["n"], 1)
                avgs[ff] = {
                    "kurt_avg": round(aa["kurt_sum"] / nn, 1),
                    "kurt_max": round(aa["kurt_max"], 1),
                    "pulses_avg": round(aa["pulses_sum"] / nn),
                    "n": aa["n"],
                }
            # Running average: max kurt per cycle averaged over all cycles
            # NOT averaging subband measures — averaging the per-cycle peak kurtosis
            # Use per-freq averages and take the max
            running_avg_k = round(max((aa["kurt_sum"] / max(aa["n"], 1)) for aa in _df_live_accum.values()), 1)
            total_samples = sum(aa["n"] for aa in _df_live_accum.values())
            with _df_lock:
                current = dict(_df_data.get("freqs", {}))
                current[f] = r
                _df_data.update({
                    "freqs": current,
                    "avgs": avgs,
                    "ts": datetime.now().strftime("%H:%M:%S"),
                    "max_kurt": max((v.get("kurt", 0) for v in current.values()), default=0),
                    "running_avg_kurt": running_avg_k,
                    "total_samples": total_samples,
                })
        # End of one full cycle
        # Cycle average = mean kurtosis across all subbands
        cycle_avg_k = round(sum(cycle_kurts) / len(cycle_kurts), 1) if cycle_kurts else 0
        _df_live_recent.append(cycle_avg_k)
        if len(_df_live_recent) > 10:
            _df_live_recent = _df_live_recent[-10:]
        _df_live_all_maxk.append(cycle_avg_k)
        last10 = round(sum(_df_live_recent) / len(_df_live_recent), 1) if _df_live_recent else 0
        lifetime = round(sum(_df_live_all_maxk) / len(_df_live_all_maxk), 1) if _df_live_all_maxk else 0
        with _df_lock:
            _df_data["recent3_avg_kurt"] = last10
            _df_data["running_avg_kurt"] = lifetime
            _df_data["total_cycles"] = len(_df_live_all_maxk)
    except Exception as e:
        log.error(f"DF LIVE LOOP CRASHED: {e}")
        import traceback
        log.error(traceback.format_exc())


def df_start_live():
    """Start continuous live scanning."""
    global _df_live, _df_live_thread, _df_live_recent, _df_live_accum
    log.info("DF LIVE START — killing rtl_sdr, starting scan loop")
    os.system("pkill -9 rtl_sdr 2>/dev/null")
    time.sleep(0.3)
    _df_live_recent = []
    _df_live_accum = {}
    _df_data.clear()
    _df_live = True
    _df_live_thread = threading.Thread(target=_df_live_loop, daemon=True)
    _df_live_thread.start()
    log.info(f"DF LIVE thread started: {_df_live_thread.is_alive()}")


def df_stop_live():
    """Stop live scanning."""
    global _df_live
    _df_live = False
    if _df_live_thread:
        _df_live_thread.join(timeout=3)
    _soapy_close()
    os.system("pkill -9 rtl_sdr 2>/dev/null")


def df_disconnect():
    """Kill sentinel and free the SDR for DF use."""
    global _df_disconnected
    log.info("DF DISCONNECT — killing sentinel + rtl_sdr")
    _soapy_close()
    os.system("pkill -f sentinel.py 2>/dev/null")
    os.system("pkill -9 rtl_sdr 2>/dev/null")
    time.sleep(2)
    _df_disconnected = True
    log.info("DF DISCONNECT done")


def df_reconnect():
    """Restart sentinel after DF session."""
    global _df_disconnected, _df_running
    _df_running = False
    _soapy_close()
    os.system("pkill -9 rtl_sdr 2>/dev/null")
    time.sleep(1)
    subprocess.Popen(
        [".venv/bin/python3", "sentinel.py", "--duration", "2592000", "--iq-budget-mb", "500000"],
        stdout=open("results/sentinel_nohup.log", "a"),
        stderr=subprocess.STDOUT,
        start_new_session=True)
    _df_disconnected = False


def df_start_measure(azimuth):
    """Run one measurement at given azimuth (sentinel must already be disconnected)."""
    global _df_running, _df_thread
    os.system("pkill -9 rtl_sdr 2>/dev/null")
    time.sleep(0.5)
    _df_running = True
    _df_thread = threading.Thread(target=_df_measure, args=(azimuth,), daemon=True)
    _df_thread.start()


def df_abort():
    """Abort current measurement but stay disconnected."""
    global _df_running
    _df_running = False
    if _df_thread:
        _df_thread.join(timeout=5)
    os.system("pkill -9 rtl_sdr 2>/dev/null")


DF_HTML = r"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>ARTEMIS — Direction Finding</title>
<script src="https://cdn.jsdelivr.net/npm/chart.js@4.4.7/dist/chart.umd.min.js"></script>
<style>
  :root { --bg: #05050e; --card: #080812; --border: #13132a; --dim: #36365a; --text: #b0b0cc; --accent: #55aaff; }
  * { margin:0; padding:0; box-sizing:border-box; }
  body { background:var(--bg); color:var(--text); font-family:'Consolas',monospace; font-size:13px; height:100vh; overflow:hidden; }
  .header { background:#0d0d1e; padding:0 20px; height:5vh; display:flex; align-items:center; justify-content:space-between; border-bottom:1px solid #1c1c36; }
  .header h1 { font-size:14px; color:var(--accent); letter-spacing:4px; font-weight:normal; }
  .header a { color:var(--dim); text-decoration:none; font-size:11px; }
  .header a:hover { color:var(--accent); }
  .main { display:grid; grid-template-columns: 1fr 300px; gap:8px; padding:8px; height:95vh; }
  .left { display:flex; flex-direction:column; gap:8px; }
  .right { display:flex; flex-direction:column; gap:8px; }
  .panel { background:var(--card); border:1px solid var(--border); border-radius:4px; padding:10px; }
  .panel h2 { font-size:9px; color:var(--dim); text-transform:uppercase; letter-spacing:2px; margin-bottom:8px; }
  .controls { display:flex; gap:8px; align-items:center; flex-wrap:wrap; }
  .controls input { background:#0a0a18; border:1px solid #2a2a4a; color:#ddd; padding:6px 10px; border-radius:3px; width:80px; font-family:monospace; font-size:14px; text-align:center; }
  .controls button { padding:6px 16px; border-radius:3px; border:none; cursor:pointer; font-family:monospace; font-size:12px; font-weight:bold; }
  .btn-start { background:#0a3a0a; color:#4c4; border:1px solid #2a5a2a; }
  .btn-stop { background:#3a0a0a; color:#f44; border:1px solid #5a2a2a; }
  .btn-save { background:#0a1a3a; color:#4af; border:1px solid #2a3a5a; }
  .btn-start:hover { background:#0c4c0c; } .btn-stop:hover { background:#4c0c0c; } .btn-save:hover { background:#0c2c4c; }
  .status { font-size:11px; color:var(--dim); }
  .status.active { color:#4c4; }
  .live-bars { flex:1; overflow-y:auto; }
  .freq-bar { display:flex; align-items:center; gap:6px; padding:3px 0; border-bottom:1px solid #0a0a14; }
  .freq-label { width:50px; font-size:10px; text-align:right; flex-shrink:0; }
  .freq-label.za { color:#28f; } .freq-label.zb { color:#f80; } .freq-label.zul { color:#a4f; }
  .bar-outer { flex:1; height:14px; background:#0a0a14; border-radius:2px; overflow:hidden; position:relative; }
  .bar-inner { height:100%; border-radius:2px; transition:width 0.3s; }
  .bar-inner.za { background:linear-gradient(90deg,#0a1a3a,#28f); } .bar-inner.zb { background:linear-gradient(90deg,#2a1a00,#f80); } .bar-inner.zul { background:linear-gradient(90deg,#1a0a2a,#a4f); }
  .kurt-val { width:45px; font-size:10px; text-align:right; font-variant-numeric:tabular-nums; }
  .pulse-val { width:40px; font-size:9px; color:var(--dim); text-align:right; }
  .polar-wrap { flex:1; min-height:0; }
  .polar-wrap canvas { width:100% !important; height:100% !important; }
  .bearings-list { max-height:20vh; overflow-y:auto; font-size:10px; }
  .bearing-item { padding:4px 0; border-bottom:1px solid #0a0a14; display:flex; justify-content:space-between; }
  .big-kurt { font-size:48px; font-weight:bold; text-align:center; padding:8px 0; font-variant-numeric:tabular-nums; }
</style>
</head>
<body>
<div class="header">
  <h1>DIRECTION FINDING</h1>
  <div style="display:flex;gap:20px;align-items:center">
    <span>Yagi: 630 MHz / 11el / 35.5&deg; beam</span>
    <a href="/">&#9664; Dashboard</a>
  </div>
</div>
<div class="main">
  <div class="left">
    <div class="panel">
      <div class="controls">
        <button class="btn-stop" id="btnDisconnect" onclick="disconnectSentinel()">DISCONNECT SENTINEL</button>
        <button class="btn-start" id="btnReconnect" onclick="reconnectSentinel()" style="display:none">RECONNECT SENTINEL</button>
        <button class="btn-save" id="btnLive" onclick="startLive()" style="display:none">LIVE SCAN</button>
        <button class="btn-stop" id="btnLiveStop" onclick="stopLive()" style="display:none">STOP LIVE</button>
        <span style="color:#333;margin:0 6px">|</span>
        <label style="font-size:10px;color:var(--dim)">BEARING &deg;</label>
        <input type="number" id="azimuth" min="0" max="360" value="0" step="5">
        <button class="btn-start" id="btnStart" onclick="startMeasurement()" disabled>MEASURE 10x</button>
        <button class="btn-stop" id="btnStop" onclick="stopDF()" style="display:none">ABORT</button>
        <span class="status" id="dfStatus">Disconnect sentinel first</span>
      </div>
    </div>
    <div class="panel" style="flex:1;display:flex;flex-direction:column">
      <h2>Live Kurtosis by Frequency</h2>
      <div style="display:flex;justify-content:center;gap:30px;align-items:baseline">
        <div style="text-align:center">
          <div style="font-size:9px;color:var(--dim);letter-spacing:2px;margin-bottom:2px">LAST 10 CYCLES</div>
          <div class="big-kurt" id="bigKurt" style="color:#334">—</div>
        </div>
        <div style="text-align:center">
          <div style="font-size:9px;color:var(--dim);letter-spacing:2px;margin-bottom:2px">RUNNING AVG</div>
          <div class="big-kurt" id="bigAvg" style="color:#334">—</div>
        </div>
      </div>
      <div class="live-bars" id="liveBars"></div>
    </div>
  </div>
  <div class="right">
    <div class="panel polar-wrap">
      <h2>Polar Plot — Kurtosis vs Bearing</h2>
      <canvas id="polarChart"></canvas>
    </div>
    <div class="panel">
      <h2>Saved Bearings <button onclick="clearAll()" style="float:right;background:#2a0a0a;color:#f55;border:1px solid #4a1a1a;padding:2px 8px;border-radius:3px;cursor:pointer;font-size:9px">CLEAR ALL</button></h2>
      <div class="bearings-list" id="bearingsList"></div>
    </div>
  </div>
</div>
<script>
Chart.defaults.color = '#4e4e74';
Chart.defaults.borderColor = '#13132a';
Chart.defaults.font.family = "'Consolas',monospace";

const FREQS = [622,624,628,630,632,634,636];
const polarChart = new Chart(document.getElementById('polarChart'), {
  type: 'radar',
  data: {
    labels: [],
    datasets: [{
      label: 'Zone A Max Kurt (622-636 MHz)',
      data: [],
      borderColor: 'rgba(34,136,255,0.8)',
      backgroundColor: 'rgba(34,136,255,0.15)',
      pointBackgroundColor: '#28f',
      pointRadius: 5,
    }]
  },
  options: {
    responsive: true, maintainAspectRatio: false,
    scales: {
      r: {
        beginAtZero: true,
        grid: { color: '#1a1a2a' },
        angleLines: { color: '#1a1a2a' },
        ticks: { color: '#3a3a50', backdropColor: 'transparent', font: { size: 9 } },
        pointLabels: { color: '#888', font: { size: 10 } }
      }
    },
    plugins: {
      legend: { display: true, position: 'bottom', labels: { boxWidth: 12, font: { size: 10 } } },
      tooltip: { backgroundColor: 'rgba(8,8,18,0.95)', borderColor: '#2a2a4a', borderWidth: 1 }
    }
  }
});

let pollTimer = null;

function disconnectSentinel() {
  document.getElementById('dfStatus').textContent = 'Disconnecting sentinel...';
  fetch('/api/df/disconnect', {method:'POST'}).then(() => {
    document.getElementById('btnDisconnect').style.display = 'none';
    document.getElementById('btnReconnect').style.display = 'inline';
    document.getElementById('btnStart').disabled = false;
    document.getElementById('btnLive').style.display = 'inline';
    document.getElementById('dfStatus').textContent = 'Ready — LIVE SCAN or MEASURE';
    document.getElementById('dfStatus').className = 'status active';
  });
}

let liveTimer = null;

function startLive() {
  document.getElementById('btnLive').style.display = 'none';
  document.getElementById('btnLiveStop').style.display = 'inline';
  document.getElementById('btnStart').disabled = true;
  document.getElementById('dfStatus').textContent = 'LIVE — point and shoot';
  document.getElementById('dfStatus').className = 'status active';
  fetch('/api/df/live/start', {method:'POST'}).then(() => {
    liveTimer = setInterval(pollLive, 500);
  });
}

function stopLive() {
  clearInterval(liveTimer);
  fetch('/api/df/live/stop', {method:'POST'}).then(() => {
    document.getElementById('btnLive').style.display = 'inline';
    document.getElementById('btnLiveStop').style.display = 'none';
    document.getElementById('btnStart').disabled = false;
    document.getElementById('dfStatus').textContent = 'Live stopped — ready';
    document.getElementById('dfStatus').className = 'status active';
  });
}

function pollLive() {
  fetch('/api/df/data').then(r => r.json()).then(d => {
    if (!d.freqs) return;
    const avgs = d.avgs || {};
    const container = document.getElementById('liveBars');
    const allK = Object.values(d.freqs).map(f => f.kurt || 0);
    const allAvgK = Object.values(avgs).map(a => a.kurt_avg || 0);
    const maxK = Math.max(20, ...allK, ...allAvgK);
    container.innerHTML = '';
    FREQS.forEach(f => {
      const r = d.freqs[f] || {kurt:0, pulses:0};
      const a = avgs[f] || {kurt_avg:0, kurt_max:0, pulses_avg:0, n:0};
      const pctNow = Math.min((r.kurt || 0) / maxK * 100, 100);
      const pctAvg = Math.min((a.kurt_avg || 0) / maxK * 100, 100);
      container.innerHTML += '<div class="freq-bar">' +
        '<span class="freq-label za">' + f + '</span>' +
        '<div class="bar-outer" style="position:relative">' +
          '<div class="bar-inner za" style="width:' + pctNow.toFixed(1) + '%"></div>' +
          '<div style="position:absolute;top:0;left:' + pctAvg.toFixed(1) + '%;width:2px;height:100%;background:#fff;opacity:0.6"></div>' +
        '</div>' +
        '<span class="kurt-val">' + (r.kurt||0).toFixed(1) + '</span>' +
        '<span class="pulse-val" style="color:#28f;min-width:50px" title="avg / max / n">' +
          a.kurt_avg.toFixed(0) + '/' + a.kurt_max.toFixed(0) +
        '</span>' +
        '</div>';
    });
    // Left number: last 3 full cycle average
    const recent3 = d.recent3_avg_kurt || 0;
    const bigEl = document.getElementById('bigKurt');
    bigEl.textContent = recent3.toFixed(1);
    bigEl.style.color = recent3 > 200 ? '#f43' : recent3 > 80 ? '#fa0' : recent3 > 30 ? '#2c8' : '#334';

    // Right number: entire process running average
    const runAvg = d.running_avg_kurt || 0;
    const avgEl = document.getElementById('bigAvg');
    avgEl.textContent = runAvg.toFixed(1);
    avgEl.style.color = runAvg > 200 ? '#f43' : runAvg > 80 ? '#fa0' : runAvg > 30 ? '#2c8' : '#334';

    const nc = d.total_cycles || 0;
    document.getElementById('dfStatus').textContent = 'LIVE — ' + nc + ' cycles';
  });
}

function reconnectSentinel() {
  clearInterval(liveTimer);
  document.getElementById('dfStatus').textContent = 'Reconnecting sentinel...';
  document.getElementById('btnStart').disabled = true;
  fetch('/api/df/live/stop', {method:'POST'}).then(() =>
    fetch('/api/df/reconnect', {method:'POST'})
  ).then(() => {
    document.getElementById('btnDisconnect').style.display = 'inline';
    document.getElementById('btnReconnect').style.display = 'none';
    document.getElementById('btnLive').style.display = 'none';
    document.getElementById('btnLiveStop').style.display = 'none';
    document.getElementById('dfStatus').textContent = 'Sentinel running — disconnect to measure';
    document.getElementById('dfStatus').className = 'status';
  });
}

function startMeasurement() {
  const az = parseInt(document.getElementById('azimuth').value) || 0;
  document.getElementById('btnStart').disabled = true;
  document.getElementById('btnStop').style.display = 'inline';
  document.getElementById('dfStatus').textContent = 'Preparing...';

  fetch('/api/df/start?azimuth=' + az, {method:'POST'}).then(() => {
    pollTimer = setInterval(pollDF, 800);
  });
}

function stopDF() {
  clearInterval(pollTimer);
  fetch('/api/df/stop', {method:'POST'}).then(() => {
    document.getElementById('btnStart').disabled = false;
    document.getElementById('btnStop').style.display = 'none';
    document.getElementById('dfStatus').textContent = 'Aborted — ready for next measurement';
    document.getElementById('dfStatus').className = 'status active';
  });
}

function pollDF() {
  fetch('/api/df/data').then(r => r.json()).then(d => {
    const p = d.progress || {};
    const statusEl = document.getElementById('dfStatus');
    const bigEl = document.getElementById('bigKurt');

    if (p.state === 'prep') {
      statusEl.textContent = 'HOLD STEADY — measuring in ' + p.countdown + 's...';
      statusEl.className = 'status';
      bigEl.textContent = p.countdown;
      bigEl.style.color = '#fa0';
      return;
    }

    if (p.state === 'scanning') {
      statusEl.textContent = 'SCANNING cycle ' + p.cycle + '/' + p.total;
      statusEl.className = 'status active';
    }

    if (p.state === 'done') {
      clearInterval(pollTimer);
      statusEl.textContent = 'SAVED — rotate Yagi, enter next bearing, hit MEASURE';
      statusEl.className = 'status active';
      document.getElementById('btnStart').disabled = false;
      document.getElementById('btnStop').style.display = 'none';
      // Auto-increment azimuth by beamwidth (36 deg)
      const azEl = document.getElementById('azimuth');
      azEl.value = (parseInt(azEl.value) + 36) % 360;
      updatePolar();
      updateBearingsList();
    }

    if (!d.freqs) return;
    const container = document.getElementById('liveBars');
    const maxK = Math.max(50, ...Object.values(d.freqs).map(f => f.kurt || 0));
    container.innerHTML = '';
    FREQS.forEach(f => {
      const r = d.freqs[f] || {kurt:0, pulses:0};
      const pct = Math.min((r.kurt || 0) / maxK * 100, 100);
      container.innerHTML += '<div class="freq-bar">' +
        '<span class="freq-label za">' + f + '</span>' +
        '<div class="bar-outer"><div class="bar-inner za" style="width:' + pct.toFixed(1) + '%"></div></div>' +
        '<span class="kurt-val">' + (r.kurt||0).toFixed(1) + '</span>' +
        '<span class="pulse-val">' + (r.pulses||0) + 'p</span>' +
        '</div>';
    });

    const k = d.max_kurt || 0;
    bigEl.textContent = k.toFixed(1);
    bigEl.style.color = k > 200 ? '#f43' : k > 80 ? '#fa0' : k > 30 ? '#2c8' : '#334';
  });
}

function updatePolar() {
  fetch('/api/df/bearings').then(r => r.json()).then(bearings => {
    if (!bearings.length) return;
    const labels = bearings.map(b => b.azimuth + '\u00B0');
    const zoneAData = bearings.map(b => {
      const freqs = b.freqs || {};
      const vals = [622,624,628,630,632,634,636].map(f => (freqs[f]||{}).kurt||0);
      return Math.max(...vals);
    });
    polarChart.data.labels = labels;
    polarChart.data.datasets[0].data = zoneAData;
    polarChart.update();
  });
}

function deleteBearing(idx) {
  fetch('/api/df/delete?index=' + idx, {method:'POST'}).then(() => {
    updatePolar();
    updateBearingsList();
  });
}

function clearAll() {
  if (!confirm('Delete all bearings?')) return;
  fetch('/api/df/clear', {method:'POST'}).then(() => {
    updatePolar();
    updateBearingsList();
  });
}

function updateBearingsList() {
  fetch('/api/df/bearings').then(r => r.json()).then(bearings => {
    const el = document.getElementById('bearingsList');
    el.innerHTML = '';
    bearings.forEach((b, i) => {
      const freqs = b.freqs || {};
      const maxA = Math.max(...[622,624,628,630,632,634,636].map(f => (freqs[f]||{}).kurt||0));
      el.innerHTML += '<div class="bearing-item">' +
        '<span style="min-width:35px">' + b.azimuth + '&deg;</span>' +
        '<span style="color:#28f;min-width:45px">k=' + maxA.toFixed(0) + '</span>' +
        '<span style="flex:1">' + (b.ts||'') + '</span>' +
        '<button onclick="deleteBearing(' + i + ')" style="background:none;border:none;color:#633;cursor:pointer;font-size:14px;padding:0 4px">&times;</button>' +
        '</div>';
    });
  });
}

// Load existing bearings on page load
updatePolar();
updateBearingsList();
</script>
</body>
</html>"""


class Handler(BaseHTTPRequestHandler):
    def do_GET(self):
        if self.path == "/" or self.path == "/index.html":
            self.send_response(200)
            self.send_header("Content-Type", "text/html")
            self.end_headers()
            self.wfile.write(HTML.encode())
        elif self.path == "/df":
            self.send_response(200)
            self.send_header("Content-Type", "text/html")
            self.end_headers()
            self.wfile.write(DF_HTML.encode())
        elif self.path.startswith("/api/df/data"):
            with _df_lock:
                data = dict(_df_data)
            data["progress"] = dict(_df_progress)
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            self.wfile.write(json.dumps(data, default=str).encode())
        elif self.path.startswith("/api/df/bearings"):
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            self.wfile.write(json.dumps(_df_bearings, default=str).encode())
        elif self.path.startswith("/api/state"):
            # Support ?offset=N for scrolling back in time
            from urllib.parse import urlparse, parse_qs
            parsed = urlparse(self.path)
            params = parse_qs(parsed.query)
            offset = int(params.get("offset", [0])[0])
            get_state._offset = max(0, offset)
            state = get_state()
            if state:
                state["offset"] = offset
                state["total_cycles"] = len(load_all_cycles())
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            self.wfile.write(json.dumps(state or {}).encode())
        else:
            self.send_response(404)
            self.end_headers()

    def do_POST(self):
        from urllib.parse import urlparse, parse_qs
        parsed = urlparse(self.path)
        if parsed.path == "/api/df/live/start":
            df_start_live()
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            self.wfile.write(b'{"ok":true}')
        elif parsed.path == "/api/df/live/stop":
            df_stop_live()
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            self.wfile.write(b'{"ok":true}')
        elif parsed.path == "/api/df/disconnect":
            df_disconnect()
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            self.wfile.write(b'{"ok":true}')
        elif parsed.path == "/api/df/reconnect":
            df_reconnect()
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            self.wfile.write(b'{"ok":true}')
        elif parsed.path == "/api/df/start":
            params = parse_qs(parsed.query)
            az = int(params.get("azimuth", [0])[0])
            df_start_measure(az)
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            self.wfile.write(b'{"ok":true}')
        elif parsed.path == "/api/df/stop":
            df_abort()
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            self.wfile.write(b'{"ok":true}')
        elif parsed.path == "/api/df/delete":
            params = parse_qs(parsed.query)
            idx = int(params.get("index", [-1])[0])
            if 0 <= idx < len(_df_bearings):
                _df_bearings.pop(idx)
                with open("results/df_bearings.json", "w") as f:
                    json.dump(_df_bearings, f, indent=2, default=str)
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            self.wfile.write(b'{"ok":true}')
        elif parsed.path == "/api/df/clear":
            _df_bearings.clear()
            with open("results/df_bearings.json", "w") as f:
                json.dump([], f)
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            self.wfile.write(b'{"ok":true}')
        else:
            self.send_response(404)
            self.end_headers()

    def log_message(self, fmt, *args):
        pass


import logging
logging.basicConfig(
    filename="results/dashboard.log",
    level=logging.DEBUG,
    format="%(asctime)s %(levelname)s %(message)s",
    datefmt="%H:%M:%S",
)
log = logging.getLogger("dashboard")


def main():
    server = HTTPServer(("127.0.0.1", PORT), Handler)
    print(f"ARTEMIS Dashboard — http://127.0.0.1:{PORT}")
    print(f"Localhost only. Reads all {RESULTS_DIR}/sentinel_*.jsonl")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        server.server_close()


if __name__ == "__main__":
    main()
