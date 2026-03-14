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
  * { margin: 0; padding: 0; box-sizing: border-box; }
  body { background: #06060b; color: #c8c8d8; font-family: 'Consolas', 'Monaco', 'Courier New', monospace; font-size: 13px; }

  .header {
    background: #0a0a12;
    padding: 10px 20px;
    border-bottom: 1px solid #16162a;
    display: flex;
    justify-content: space-between;
    align-items: center;
  }
  .header h1 { font-size: 15px; color: #5af; letter-spacing: 4px; font-weight: normal; text-shadow: 0 0 12px rgba(80,160,255,0.4); }
  .header-right { display: flex; align-items: center; gap: 20px; }
  .status { font-size: 11px; color: #556; }
  .dot { display: inline-block; width: 7px; height: 7px; border-radius: 50%; margin-right: 5px; vertical-align: middle; }
  .dot.live { background: #0d0; box-shadow: 0 0 8px #0d0; animation: pulse 2s ease-in-out infinite; }
  .dot.stale { background: #c80; }
  @keyframes pulse { 0%,100% { opacity:1; } 50% { opacity:0.4; } }

  .grid {
    display: grid;
    grid-template-columns: repeat(4, 1fr);
    gap: 8px;
    padding: 10px;
  }
  @media (max-width: 1100px) { .grid { grid-template-columns: repeat(2, 1fr); } }

  .card {
    background: #0c0c14;
    border: 1px solid #18182a;
    border-radius: 5px;
    padding: 12px;
  }
  .card h2 {
    font-size: 9px;
    color: #445;
    text-transform: uppercase;
    letter-spacing: 2.5px;
    margin-bottom: 10px;
    font-weight: normal;
    border-bottom: 1px solid #16162a;
    padding-bottom: 6px;
  }

  .metric { font-size: 40px; font-weight: bold; line-height: 1; font-variant-numeric: tabular-nums; transition: color 0.8s ease; }
  .sub { font-size: 11px; color: #445; margin-top: 5px; }

  /* Zone Power bars */
  .bar-row { display: flex; align-items: center; gap: 6px; margin: 5px 0; }
  .bar-label { width: 56px; text-align: right; font-size: 10px; color: #556; flex-shrink: 0; }
  .bar-zone-tag { width: 14px; font-size: 9px; text-align: center; flex-shrink: 0; }
  .bar-track { flex: 1; height: 18px; background: #0a0a12; border-radius: 2px; overflow: hidden; position: relative; border: 1px solid #14141e; }
  .bar-fill { height: 100%; transition: width 0.9s cubic-bezier(.25,.46,.45,.94); }
  .bar-fill.a { background: linear-gradient(90deg, #0a1530 0%, #1244aa 40%, #28f 100%); }
  .bar-fill.b { background: linear-gradient(90deg, #1a0800 0%, #a03000 40%, #f80 100%); }
  .bar-fill.ul { background: linear-gradient(90deg, #120818 0%, #5a1899 40%, #a4f 100%); }
  .bar-val { position: absolute; right: 5px; top: 0; line-height: 18px; font-size: 10px; color: #bbb; }
  .bar-unit { font-size: 9px; color: #445; margin-left: 2px; }

  .span2 { grid-column: span 2; }
  .span4 { grid-column: 1 / -1; }

  /* Timeline */
  .chart-wrap { width: 100%; height: 200px; position: relative; }
  .chart-wrap canvas { width: 100%; height: 100%; display: block; }
  .chart-legend {
    display: flex; gap: 14px; margin-bottom: 6px; font-size: 10px; color: #556;
  }
  .legend-dot { display: inline-block; width: 10px; height: 10px; border-radius: 1px; margin-right: 4px; vertical-align: middle; }

  /* Waterfall frequency heatmap */
  .waterfall { display: flex; flex-direction: column; gap: 2px; }
  .wf-zone { margin-bottom: 6px; }
  .wf-zone-label {
    font-size: 9px; letter-spacing: 2px; text-transform: uppercase;
    margin-bottom: 3px; padding: 0 2px;
  }
  .wf-zone-label.za { color: #28f; }
  .wf-zone-label.zb { color: #f80; }
  .wf-zone-label.zul { color: #a4f; }
  .wf-row { display: flex; align-items: center; gap: 4px; height: 18px; }
  .wf-freq-label { width: 52px; text-align: right; font-size: 10px; color: #556; flex-shrink: 0; }
  .wf-bar-track { flex: 1; height: 14px; background: #090910; border-radius: 1px; overflow: hidden; position: relative; }
  .wf-bar-fill { height: 100%; border-radius: 1px; transition: width 0.6s ease, background 0.6s ease; }
  .wf-val { font-size: 10px; color: #556; width: 40px; text-align: right; flex-shrink: 0; }

  /* Symptoms */
  .sym-item {
    padding: 5px 0;
    font-size: 11px;
    display: flex;
    gap: 8px;
    align-items: center;
    border-bottom: 1px solid #0f0f18;
  }
  .sym-item:last-child { border-bottom: none; }
  .sym-time { color: #778; width: 64px; flex-shrink: 0; font-size: 10px; }
  .sym-tag { padding: 2px 7px; border-radius: 2px; font-size: 9px; font-weight: bold; letter-spacing: 1px; text-transform: uppercase; flex-shrink: 0; }
  .sym-tag.speech   { background: #231200; color: #fb0; border: 1px solid #4a2800; }
  .sym-tag.headache { background: #200808; color: #f55; border: 1px solid #440c0c; }
  .sym-tag.paresthesia { background: #061520; color: #4bf; border: 1px solid #0c2840; }
  .sym-tag.nausea   { background: #162008; color: #6d4; border: 1px solid #2a400c; }
  .sym-detail { color: #445; font-size: 10px; }
</style>
</head>
<body>
<div class="header">
  <h1>A R T E M I S</h1>
  <div class="header-right">
    <div class="status"><span class="dot live" id="dot"></span><span id="st">connecting...</span></div>
  </div>
</div>

<div class="grid">

  <!-- Metric cards -->
  <div class="card">
    <h2>Exposure Index</h2>
    <div class="metric" id="ei" style="color:#334">—</div>
    <div class="sub" id="eiSub">—</div>
  </div>
  <div class="card">
    <h2>Max Kurtosis</h2>
    <div class="metric" id="kurt" style="color:#334">—</div>
    <div class="sub" id="kurtSub">—</div>
  </div>
  <div class="card">
    <h2>Total Pulses</h2>
    <div class="metric" id="pulses" style="color:#334">—</div>
    <div class="sub" id="pulsesSub">—</div>
  </div>
  <div class="card">
    <h2>Active Freqs</h2>
    <div class="metric" id="nact" style="color:#334">—</div>
    <div class="sub" id="nactSub">—</div>
  </div>

  <!-- Zone Power (EI values) -->
  <div class="card span2">
    <h2>Zone Exposure Index</h2>
    <div class="bar-row">
      <span class="bar-label">622–636</span>
      <span class="bar-zone-tag" style="color:#28f">A</span>
      <div class="bar-track"><div class="bar-fill a" id="bA" style="width:0%"></div><span class="bar-val" id="vA"></span></div>
    </div>
    <div class="bar-row">
      <span class="bar-label">824–834</span>
      <span class="bar-zone-tag" style="color:#f80">B</span>
      <div class="bar-track"><div class="bar-fill b" id="bB" style="width:0%"></div><span class="bar-val" id="vB"></span></div>
    </div>
    <div class="bar-row">
      <span class="bar-label">878</span>
      <span class="bar-zone-tag" style="color:#a4f">UL</span>
      <div class="bar-track"><div class="bar-fill ul" id="bU" style="width:0%"></div><span class="bar-val" id="vU"></span></div>
    </div>
  </div>

  <!-- Symptoms -->
  <div class="card span2">
    <h2>Recent Symptoms — CST</h2>
    <div id="symList" style="max-height:120px;overflow-y:auto"></div>
  </div>

  <!-- Timeline -->
  <div class="card span4">
    <h2>Timeline — 60-Cycle Window</h2>
    <div class="chart-legend">
      <span><span class="legend-dot" style="background:rgba(40,136,255,0.55)"></span>Zone A</span>
      <span><span class="legend-dot" style="background:rgba(255,136,0,0.55)"></span>Zone B</span>
      <span><span class="legend-dot" style="background:rgba(170,68,255,0.55)"></span>878 UL</span>
      <span><span class="legend-dot" style="background:#fff; opacity:0.7"></span>Kurtosis</span>
    </div>
    <div class="chart-wrap"><canvas id="cv"></canvas></div>
  </div>

  <!-- Time x Frequency Heatmap (shared x-axis with timeline above) -->
  <div class="card span4" style="margin-top:-6px; border-top:none; border-top-left-radius:0; border-top-right-radius:0;">
    <h2>Frequency × Time — symptom markers at alert time</h2>
    <div class="chart-wrap" style="height:240px"><canvas id="heatmap"></canvas></div>
  </div>

</div>

<script>
let hist = [];
const cv = document.getElementById('cv');
const ctx = cv.getContext('2d');

// ── Continuous metric color gradient ───────────────────────────────────────
// Input: raw kurtosis value. Output: CSS color string.
// dark (#334) → green (#3c8) → amber (#fa0) → red (#f43)
function metricColor(k) {
  if (k <= 0) return '#334';
  // Anchor points: [value, r, g, b]
  const stops = [
    [0,    0x33, 0x33, 0x44],
    [30,   0x22, 0xcc, 0x77],
    [80,   0xff, 0xaa, 0x00],
    [200,  0xff, 0x44, 0x22],
  ];
  for (let i = 1; i < stops.length; i++) {
    if (k <= stops[i][0]) {
      const t = (k - stops[i-1][0]) / (stops[i][0] - stops[i-1][0]);
      const lerp = (a, b) => Math.round(a + (b - a) * t);
      return 'rgb(' + lerp(stops[i-1][1], stops[i][1]) + ',' +
                      lerp(stops[i-1][2], stops[i][2]) + ',' +
                      lerp(stops[i-1][3], stops[i][3]) + ')';
    }
  }
  return '#f43';
}

// ── Waterfall heat color (dark → zone-tinted bright) ──────────────────────
// zoneRgb: [r,g,b] base color; t: 0..1 intensity
function waterfallColor(t, zoneRgb) {
  t = Math.max(0, Math.min(1, t));
  const [zr, zg, zb] = zoneRgb;
  // Dark base: nearly black, tinted slightly with zone color
  const br = Math.round(8  + t * zr * 0.85);
  const bg = Math.round(8  + t * zg * 0.85);
  const bb = Math.round(12 + t * zb * 0.85);
  const alpha = 0.18 + t * 0.82;
  return 'rgba(' + br + ',' + bg + ',' + bb + ',' + alpha.toFixed(2) + ')';
}

const ZONE_A_RGB  = [0x22, 0x88, 0xff];
const ZONE_B_RGB  = [0xff, 0x88, 0x00];
const ZONE_UL_RGB = [0xaa, 0x44, 0xff];

function freqZone(freq) {
  if (freq < 640)  return { label: 'A',  rgb: ZONE_A_RGB,  css: '#28f' };
  if (freq < 850)  return { label: 'B',  rgb: ZONE_B_RGB,  css: '#f80' };
  return           { label: 'UL', rgb: ZONE_UL_RGB, css: '#a4f' };
}

// ── Catmull-Rom spline helper ─────────────────────────────────────────────
function splinePath(pts, ctx2d) {
  if (pts.length < 2) return;
  ctx2d.moveTo(pts[0][0], pts[0][1]);
  if (pts.length === 2) { ctx2d.lineTo(pts[1][0], pts[1][1]); return; }
  for (let i = 0; i < pts.length - 1; i++) {
    const p0 = pts[Math.max(0, i - 1)];
    const p1 = pts[i];
    const p2 = pts[Math.min(pts.length - 1, i + 1)];
    const p3 = pts[Math.min(pts.length - 1, i + 2)];
    const cp1x = p1[0] + (p2[0] - p0[0]) / 6;
    const cp1y = p1[1] + (p2[1] - p0[1]) / 6;
    const cp2x = p2[0] - (p3[0] - p1[0]) / 6;
    const cp2y = p2[1] - (p3[1] - p1[1]) / 6;
    ctx2d.bezierCurveTo(cp1x, cp1y, cp2x, cp2y, p2[0], p2[1]);
  }
}

// Draw a filled area under a spline path
function drawAreaFill(pts, baseY, fillStyle, ctx2d) {
  if (pts.length < 2) return;
  ctx2d.beginPath();
  ctx2d.moveTo(pts[0][0], baseY);
  ctx2d.lineTo(pts[0][0], pts[0][1]);
  splinePath(pts, ctx2d);
  ctx2d.lineTo(pts[pts.length - 1][0], baseY);
  ctx2d.closePath();
  ctx2d.fillStyle = fillStyle;
  ctx2d.fill();
}

// Draw a spline stroke
function drawLine(pts, strokeStyle, lineWidth, ctx2d) {
  if (pts.length < 2) return;
  ctx2d.beginPath();
  splinePath(pts, ctx2d);
  ctx2d.strokeStyle = strokeStyle;
  ctx2d.lineWidth = lineWidth;
  ctx2d.lineJoin = 'round';
  ctx2d.stroke();
}

// ── Main timeline draw ────────────────────────────────────────────────────
function draw() {
  const W = cv.width  = cv.offsetWidth  * (window.devicePixelRatio || 2);
  const H = cv.height = cv.offsetHeight * (window.devicePixelRatio || 2);
  ctx.clearRect(0, 0, W, H);
  if (hist.length < 2) return;

  const dpr = window.devicePixelRatio || 2;
  const n  = hist.length;
  const labelW = 55 * dpr;  // match heatmap left offset
  const padTop    = H * 0.20;
  const padBottom = H * 0.14;
  const plotW = W - labelW;
  const plotH = H - padTop - padBottom;
  const baseY = padTop + plotH;
  const dx = plotW / (n - 1);

  // Compute per-series maxima (with floor)
  const maxK   = Math.max(50,  ...hist.map(h => h.k   || 0));
  const maxEIA = Math.max(10,  ...hist.map(h => h.eiA  || 0));
  const maxEIB = Math.max(10,  ...hist.map(h => h.eiB  || 0));
  const maxEIU = Math.max(10,  ...hist.map(h => h.eiUL || 0));
  // Global EI max for normalizing all three area fills on same scale
  const maxEI  = Math.max(maxEIA, maxEIB, maxEIU, 10);

  const yOf = (v, maxV) => padTop + plotH - Math.max(0, Math.min(1, (v || 0) / maxV)) * plotH;
  const xi   = i => labelW + i * dx;

  // Build point arrays
  const ptsA  = hist.map((h, i) => [xi(i), yOf(h.eiA  || 0, maxEI)]);
  const ptsB  = hist.map((h, i) => [xi(i), yOf(h.eiB  || 0, maxEI)]);
  const ptsUL = hist.map((h, i) => [xi(i), yOf(h.eiUL || 0, maxEI)]);
  const ptsK  = hist.map((h, i) => [xi(i), yOf(h.k    || 0, maxK)]);

  // Subtle grid lines
  ctx.save();
  ctx.strokeStyle = '#131320';
  ctx.lineWidth = 1;
  for (let g = 0; g <= 4; g++) {
    const gy = padTop + (g / 4) * plotH;
    ctx.beginPath();
    ctx.moveTo(labelW, gy);
    ctx.lineTo(W, gy);
    ctx.stroke();
  }
  ctx.restore();

  // Gradient fills — Zone A (blue)
  const gradA = ctx.createLinearGradient(0, padTop, 0, baseY);
  gradA.addColorStop(0, 'rgba(34,136,255,0.45)');
  gradA.addColorStop(1, 'rgba(34,136,255,0.02)');
  drawAreaFill(ptsA, baseY, gradA, ctx);

  // Zone B (orange)
  const gradB = ctx.createLinearGradient(0, padTop, 0, baseY);
  gradB.addColorStop(0, 'rgba(255,136,0,0.38)');
  gradB.addColorStop(1, 'rgba(255,136,0,0.02)');
  drawAreaFill(ptsB, baseY, gradB, ctx);

  // 878 UL (purple)
  const gradUL = ctx.createLinearGradient(0, padTop, 0, baseY);
  gradUL.addColorStop(0, 'rgba(170,68,255,0.38)');
  gradUL.addColorStop(1, 'rgba(170,68,255,0.02)');
  drawAreaFill(ptsUL, baseY, gradUL, ctx);

  // Area outlines
  drawLine(ptsA,  'rgba(60,160,255,0.65)',  1.5, ctx);
  drawLine(ptsB,  'rgba(255,160,0,0.65)',   1.5, ctx);
  drawLine(ptsUL, 'rgba(190,100,255,0.65)', 1.5, ctx);

  // Kurtosis line — bright white/silver on top of everything
  drawLine(ptsK, 'rgba(255,255,255,0.82)', 2.2, ctx);

  // Symptom labels on timeline (angled, stacked if overlapping)
  const tlSymStacks = {};
  symptomsData.forEach(s => {
    if (!s.symptom) return;
    const alertLocal = s.alertLocalTime || s.localTime || '';
    if (!alertLocal) return;
    let bestIdx = -1, bestDist = Infinity;
    const toMin = (ts) => {
      const m = ts.match(/(\d+):(\d+)\s*(AM|PM)/i);
      if (!m) return -1;
      let hr = parseInt(m[1]); const mn = parseInt(m[2]);
      if (m[3].toUpperCase() === 'PM' && hr !== 12) hr += 12;
      if (m[3].toUpperCase() === 'AM' && hr === 12) hr = 0;
      return hr * 60 + mn;
    };
    hist.forEach((h, i) => {
      if (!h.ts) return;
      const d2 = Math.abs(toMin(h.ts) - toMin(alertLocal));
      if (d2 < bestDist) { bestDist = d2; bestIdx = i; }
    });
    if (bestIdx < 0 || bestDist >= 10) return;

    const sym = s.symptom;
    const color = sym === 'speech' ? '#fb0'
                : sym === 'headache' ? '#f55'
                : sym === 'tinnitus' ? '#f8f'
                : sym === 'paresthesia' ? '#4bf'
                : sym === 'nausea' ? '#6d4' : '#888';
    const x = xi(bestIdx);
    if (!tlSymStacks[bestIdx]) tlSymStacks[bestIdx] = 0;
    const stackN = tlSymStacks[bestIdx];
    const lf = Math.round(dpr * 8);

    ctx.save();
    ctx.translate(x, padTop - 6 - stackN * (lf + 4));
    ctx.rotate(-Math.PI / 4);
    ctx.font = 'bold ' + lf + 'px monospace';
    ctx.fillStyle = color;
    ctx.textAlign = 'left';
    ctx.fillText(sym, 0, 0);
    ctx.restore();
    tlSymStacks[bestIdx]++;
  });

  // Y-axis labels on left
  const fontSize = Math.max(12, Math.round(W / 80));
  ctx.font = fontSize + 'px monospace';
  ctx.fillStyle = '#2a2a3a';
  ctx.textAlign = 'right';
  ctx.fillText('k=' + maxK.toFixed(0), labelW - 6, padTop + 10);
  ctx.fillText('k=0', labelW - 6, baseY - 2);
  ctx.textAlign = 'left';

  // Time labels at bottom — shared x-axis for timeline + heatmap below
  ctx.fillStyle = '#3a3a50';
  ctx.textAlign = 'center';
  const timeFontSize = Math.max(14, Math.round(W / 70));
  ctx.font = timeFontSize + 'px monospace';
  const tLabelIdxs = [0, Math.floor(n*0.25), Math.floor(n*0.5), Math.floor(n*0.75), n-1];
  tLabelIdxs.forEach(i => {
    if (i >= 0 && i < n && hist[i] && hist[i].ts) {
      ctx.fillText(hist[i].ts, xi(i), H - 4);
    }
  });
  ctx.textAlign = 'left';
}

// ── Time × Frequency Heatmap ─────────────────────────────────────────────
const hmCv = document.getElementById('heatmap');
const hmCtx = hmCv.getContext('2d');
let freqBins = [];
let symptomsData = [];

function heatColor(t, zoneRgb) {
  // 0=black, 1=zone color at full brightness
  t = Math.max(0, Math.min(1, t));
  const [zr, zg, zb] = zoneRgb;
  return 'rgb(' + Math.round(t*zr) + ',' + Math.round(t*zg) + ',' + Math.round(t*zb) + ')';
}

function freqZoneRgb(f) {
  if (f < 640) return ZONE_A_RGB;
  if (f < 870) return ZONE_B_RGB;
  return ZONE_UL_RGB;
}

function freqZoneLabel(f) {
  if (f < 640) return 'A';
  if (f < 870) return 'B';
  return 'UL';
}

function drawHeatmap() {
  const dpr = window.devicePixelRatio || 2;
  const W = hmCv.width = hmCv.offsetWidth * dpr;
  const H = hmCv.height = hmCv.offsetHeight * dpr;
  hmCtx.clearRect(0, 0, W, H);
  if (!hist.length || !freqBins.length) return;

  const nFreqs = freqBins.length;
  const nTime = hist.length;

  // Layout
  const labelW = 55 * dpr;   // freq labels on left
  const bottomH = 40 * dpr;  // room for bottom symptom labels
  const topH = 45 * dpr;     // room for angled symptom labels
  const plotW = W - labelW;
  const plotH = H - bottomH - topH;
  const cellW = plotW / nTime;
  const cellH = plotH / nFreqs;

  // Find global max kurtosis for normalization
  let globalMaxK = 50;
  hist.forEach(h => {
    if (h.fh) {
      Object.values(h.fh).forEach(k => { if (k > globalMaxK) globalMaxK = k; });
    }
  });

  // Draw cells
  for (let fi = 0; fi < nFreqs; fi++) {
    const freq = freqBins[fi];
    const rgb = freqZoneRgb(freq);
    const y = topH + fi * cellH;

    for (let ti = 0; ti < nTime; ti++) {
      const h = hist[ti];
      const x = labelW + ti * cellW;
      const k = (h.fh && h.fh[freq]) ? h.fh[freq] : 0;
      const t = Math.min(k / globalMaxK, 1);

      hmCtx.fillStyle = heatColor(t, rgb);
      hmCtx.fillRect(x, y, cellW + 0.5, cellH + 0.5);
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
    const x = labelW + idx * cellW + cellW / 2;
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
    d.className = 'sym-item';
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
      k:    h.maxK   || 0,
      eiA:  h.eiA    || 0,
      eiB:  h.eiB    || 0,
      eiUL: 0,
      ts:   h.ts     || '',
      sym:  h.symptom || null,
      fh:   h.fh     || {},
    }));
  }
  if (data.freqBins) freqBins = data.freqBins;
  symptomsData = data.symptoms || [];

  draw();
  drawHeatmap();
}

// ── Poll loop ─────────────────────────────────────────────────────────────
function poll() {
  fetch('/api/state')
    .then(r => r.json())
    .then(d => { upd(d); setTimeout(poll, 5000); })
    .catch(() => {
      document.getElementById('dot').className = 'dot stale';
      document.getElementById('st').textContent = 'disconnected';
      setTimeout(poll, 5000);
    });
}

poll();
window.addEventListener('resize', () => { draw(); drawHeatmap(); });
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
    history = []
    for c in cycles[-60:]:
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

        history.append({
            "maxK": round(max_k, 1),
            "ei": c.get("exposure_index"),
            "eiA": c.get("ei_zone_a"),
            "eiB": c.get("ei_zone_b"),
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

    # Map symptoms onto history by alert_cycle (when signal fired, not button press)
    sym_by_cycle = {}
    for s in symptoms:
        ac = s.get("alert_cycle")
        if ac and s.get("symptom"):
            sym_by_cycle[ac] = s.get("symptom")
    for h_entry in history:
        # Match by cycle number from the original cycle data
        pass  # We'll send symptoms separately and let JS match by alert_ts

    return {
        "current": latest,
        "history": history,
        "freqBins": FREQ_BINS,
        "symptoms": symptoms[-20:],
    }


class Handler(BaseHTTPRequestHandler):
    def do_GET(self):
        if self.path == "/" or self.path == "/index.html":
            self.send_response(200)
            self.send_header("Content-Type", "text/html")
            self.end_headers()
            self.wfile.write(HTML.encode())
        elif self.path == "/api/state":
            state = get_state()
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            self.wfile.write(json.dumps(state or {}).encode())
        else:
            self.send_response(404)
            self.end_headers()

    def log_message(self, fmt, *args):
        pass


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
