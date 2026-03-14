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
  body { background: #08080d; color: #d0d0d0; font-family: 'Consolas', 'Monaco', 'Courier New', monospace; font-size: 13px; }
  .header { background: #0c0c14; padding: 10px 20px; border-bottom: 1px solid #1a1a2a; display: flex; justify-content: space-between; align-items: center; }
  .header h1 { font-size: 16px; color: #6af; letter-spacing: 3px; font-weight: normal; }
  .status { font-size: 12px; color: #666; }
  .dot { display: inline-block; width: 8px; height: 8px; border-radius: 50%; margin-right: 5px; vertical-align: middle; }
  .dot.live { background: #0c0; box-shadow: 0 0 6px #0c0; }
  .dot.stale { background: #c80; }
  .grid { display: grid; grid-template-columns: repeat(4, 1fr); gap: 8px; padding: 10px; }
  @media (max-width: 1100px) { .grid { grid-template-columns: repeat(2, 1fr); } }
  .card { background: #0e0e16; border: 1px solid #1a1a28; border-radius: 6px; padding: 12px; }
  .card h2 { font-size: 10px; color: #556; text-transform: uppercase; letter-spacing: 2px; margin-bottom: 8px; font-weight: normal; }
  .metric { font-size: 42px; font-weight: bold; line-height: 1; font-variant-numeric: tabular-nums; }
  .sub { font-size: 11px; color: #556; margin-top: 4px; }
  .bar-row { display: flex; align-items: center; gap: 6px; margin: 4px 0; }
  .bar-label { width: 50px; text-align: right; font-size: 11px; color: #667; }
  .bar-track { flex: 1; height: 20px; background: #111119; border-radius: 2px; overflow: hidden; position: relative; }
  .bar-fill { height: 100%; transition: width 0.8s ease; }
  .bar-fill.a { background: linear-gradient(90deg, #135, #28f); }
  .bar-fill.b { background: linear-gradient(90deg, #530, #f80); }
  .bar-fill.ul { background: linear-gradient(90deg, #315, #a4f); }
  .bar-val { position: absolute; right: 6px; top: 0; line-height: 20px; font-size: 11px; color: #ccc; }
  .span2 { grid-column: span 2; }
  .span4 { grid-column: 1 / -1; }
  .chart { width: 100%; height: 160px; position: relative; }
  .chart canvas { width: 100%; height: 100%; }
  .freq-grid { display: flex; flex-wrap: wrap; gap: 3px; }
  .fc { padding: 4px 7px; border-radius: 3px; font-size: 10px; font-variant-numeric: tabular-nums; transition: all 0.3s; }
  .sym-item { padding: 4px 0; font-size: 11px; display: flex; gap: 8px; align-items: center; border-bottom: 1px solid #111119; }
  .sym-item .t { color: #889; width: 70px; }
  .sym-tag { padding: 2px 6px; border-radius: 3px; font-size: 10px; font-weight: bold; }
  .sym-tag.speech { background: #2a1800; color: #fa0; }
  .sym-tag.headache { background: #2a0808; color: #f44; }
  .sym-tag.paresthesia { background: #081828; color: #4af; }
  .sym-detail { color: #556; font-size: 10px; }
</style>
</head>
<body>
<div class="header">
  <h1>A R T E M I S</h1>
  <div class="status"><span class="dot live" id="dot"></span><span id="st">connecting...</span></div>
</div>
<div class="grid">
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
  <div class="card span2">
    <h2>Zone Power</h2>
    <div class="bar-row"><span class="bar-label">622-636</span><div class="bar-track"><div class="bar-fill a" id="bA" style="width:0"></div><span class="bar-val" id="vA"></span></div></div>
    <div class="bar-row"><span class="bar-label">824-834</span><div class="bar-track"><div class="bar-fill b" id="bB" style="width:0"></div><span class="bar-val" id="vB"></span></div></div>
    <div class="bar-row"><span class="bar-label">878</span><div class="bar-track"><div class="bar-fill ul" id="bU" style="width:0"></div><span class="bar-val" id="vU"></span></div></div>
  </div>
  <div class="card span2">
    <h2>Recent Symptoms</h2>
    <div id="symList" style="max-height:110px;overflow-y:auto"></div>
  </div>
  <div class="card span4">
    <h2>Timeline — Kurtosis (orange) · Exposure Index (blue)</h2>
    <div class="chart"><canvas id="cv"></canvas></div>
  </div>
  <div class="card span4">
    <h2>Active Frequencies</h2>
    <div class="freq-grid" id="fgrid"></div>
  </div>
</div>
<script>
let hist = [];
const cv = document.getElementById('cv');
const cx = cv.getContext('2d');

// Color gradient: value 0-1 maps from dark to bright
function heatColor(t) {
  // 0=dark blue, 0.3=teal, 0.6=yellow, 1.0=red
  t = Math.max(0, Math.min(1, t));
  if (t < 0.3) { const s=t/0.3; return `rgb(${Math.round(20+s*30)},${Math.round(20+s*80)},${Math.round(40+s*80)})`; }
  if (t < 0.6) { const s=(t-0.3)/0.3; return `rgb(${Math.round(50+s*180)},${Math.round(100+s*70)},${Math.round(120-s*80)})`; }
  const s=(t-0.6)/0.4; return `rgb(${Math.round(230+s*25)},${Math.round(170-s*130)},${Math.round(40-s*30)})`;
}

function metricColor(k) {
  if (k > 200) return '#f43';
  if (k > 80) return '#fa0';
  if (k > 30) return '#4c4';
  return '#334';
}

// Catmull-Rom spline for smooth curves
function smoothPath(points, cx, close) {
  if (points.length < 2) return;
  cx.moveTo(points[0][0], points[0][1]);
  if (points.length === 2) { cx.lineTo(points[1][0], points[1][1]); return; }
  for (let i = 0; i < points.length - 1; i++) {
    const p0 = points[Math.max(0, i-1)];
    const p1 = points[i];
    const p2 = points[Math.min(points.length-1, i+1)];
    const p3 = points[Math.min(points.length-1, i+2)];
    const cp1x = p1[0] + (p2[0] - p0[0]) / 6;
    const cp1y = p1[1] + (p2[1] - p0[1]) / 6;
    const cp2x = p2[0] - (p3[0] - p1[0]) / 6;
    const cp2y = p2[1] - (p3[1] - p1[1]) / 6;
    cx.bezierCurveTo(cp1x, cp1y, cp2x, cp2y, p2[0], p2[1]);
  }
}

function draw() {
  const W = cv.width = cv.offsetWidth * 2;
  const H = cv.height = cv.offsetHeight * 2;
  cx.clearRect(0,0,W,H);
  if (hist.length < 2) return;
  const n = hist.length, dx = W/(n-1);
  const pad = H * 0.08;
  const plotH = H - pad * 2;
  const maxK = Math.max(200, ...hist.map(h=>h.k));
  const maxEI = Math.max(100, ...hist.map(h=>h.ei||0));

  const ky = (k) => pad + plotH - (k/maxK)*plotH;
  const ey = (e) => pad + plotH - ((e||0)/maxEI)*plotH;

  // EI gradient fill
  const eiPts = hist.map((h,i) => [i*dx, ey(h.ei)]);
  cx.beginPath();
  cx.moveTo(0, H-pad);
  smoothPath([[0, ey(hist[0].ei)], ...eiPts], cx);
  cx.lineTo(W, H-pad);
  cx.closePath();
  const eiGrad = cx.createLinearGradient(0, 0, 0, H);
  eiGrad.addColorStop(0, 'rgba(40,100,255,0.35)');
  eiGrad.addColorStop(1, 'rgba(40,100,255,0.02)');
  cx.fillStyle = eiGrad;
  cx.fill();

  // EI smooth line
  cx.beginPath();
  smoothPath(eiPts, cx);
  cx.strokeStyle = 'rgba(80,140,255,0.6)';
  cx.lineWidth = 2;
  cx.stroke();

  // Kurtosis smooth line with gradient stroke
  const kPts = hist.map((h,i) => [i*dx, ky(h.k)]);
  cx.beginPath();
  smoothPath(kPts, cx);
  const kGrad = cx.createLinearGradient(0, 0, 0, H);
  kGrad.addColorStop(0, '#f43');
  kGrad.addColorStop(0.4, '#fa0');
  kGrad.addColorStop(1, '#640');
  cx.strokeStyle = kGrad;
  cx.lineWidth = 2.5;
  cx.stroke();

  // Symptom markers
  hist.forEach((h,i) => {
    if (h.sym) {
      const color = h.sym==='speech'?'#fa0':h.sym==='headache'?'#f44':'#4af';
      cx.beginPath();
      // Triangle marker
      const x = i*dx, y = pad - 2;
      cx.moveTo(x, y); cx.lineTo(x-5, y-10); cx.lineTo(x+5, y-10); cx.closePath();
      cx.fillStyle = color;
      cx.fill();
    }
  });

  // Time labels
  cx.fillStyle = '#334';
  cx.font = (Math.round(W/60)) + 'px monospace';
  const labelIdxs = [0, Math.floor(n*0.25), Math.floor(n*0.5), Math.floor(n*0.75), n-1];
  labelIdxs.forEach(i => {
    if (hist[i] && hist[i].ts) {
      const x = Math.min(Math.max(i*dx, 20), W-50);
      cx.fillText(hist[i].ts, x, H - 2);
    }
  });

  // Y-axis labels
  cx.fillStyle = '#2a2a35';
  cx.font = '16px monospace';
  cx.fillText('k=' + maxK.toFixed(0), 4, pad + 12);
  cx.fillText('k=0', 4, H - pad - 2);
}

function upd(data) {
  if (!data || !data.current) return;
  const c = data.current;

  const setMetric = (id, val, subId, subText) => {
    const el = document.getElementById(id);
    el.textContent = val;
    el.style.color = metricColor(c.maxK);
    if (subId) document.getElementById(subId).textContent = subText;
  };

  setMetric('ei', c.ei != null ? Math.round(c.ei) : '—', 'eiSub',
    'Zone A: ' + Math.round(c.eiA||0) + '  |  Zone B: ' + Math.round(c.eiB||0));
  setMetric('kurt', c.maxK.toFixed(0), 'kurtSub', 'cycle ' + c.cycle);
  setMetric('pulses', c.pulses.toLocaleString(), 'pulsesSub', 'this cycle');
  setMetric('nact', c.nActive, 'nactSub', 'of 13 targets');

  // Zone bars with gradient intensity
  const pct = k => Math.min(k/400*100, 100).toFixed(0) + '%';
  document.getElementById('bA').style.width = pct(c.zoneAMax);
  document.getElementById('vA').textContent = c.zoneAMax.toFixed(0);
  document.getElementById('bB').style.width = pct(c.zoneBMax);
  document.getElementById('vB').textContent = c.zoneBMax.toFixed(0);
  document.getElementById('bU').style.width = pct(c.zoneULMax);
  document.getElementById('vU').textContent = c.zoneULMax.toFixed(0);

  // Frequencies with continuous heat gradient
  const fg = document.getElementById('fgrid');
  fg.innerHTML = '';
  const activeFreqs = c.freqs.filter(f => f.kurt > 15);
  const fMaxK = Math.max(50, ...activeFreqs.map(f=>f.kurt));
  activeFreqs.sort((a,b) => a.freq - b.freq).forEach(f => {
    const d = document.createElement('div');
    const t = Math.min(f.kurt / fMaxK, 1);
    const bg = heatColor(t);
    const zone = f.freq < 640 ? '#28f' : f.freq < 850 ? '#f80' : '#a4f';
    d.className = 'fc';
    d.style.cssText = 'background:' + bg + ';color:#fff;border-left:3px solid ' + zone;
    d.textContent = f.freq.toFixed(0) + ' MHz';
    d.title = 'kurtosis: ' + f.kurt.toFixed(1) + ', pulses: ' + f.pulses;
    fg.appendChild(d);
  });

  // Symptoms — local time, newest first
  const sl = document.getElementById('symList');
  sl.innerHTML = '';
  const syms = (data.symptoms||[]).filter(s => s.symptom);
  syms.slice(-10).reverse().forEach(s => {
    const d = document.createElement('div');
    d.className = 'sym-item';
    const localT = s.localTime || (s.timestamp||'').substring(11,19) + ' UTC';
    const mk = s.alert_max_kurt ? Math.round(s.alert_max_kurt) : (s.rf_context && s.rf_context.max_kurt ? Math.round(s.rf_context.max_kurt) : null);
    const nf = s.alert_n_active || (s.rf_context ? s.rf_context.n_active : null);
    let detail = '';
    if (mk) detail += 'kurtosis ' + mk;
    if (nf) detail += (detail ? ', ' : '') + nf + ' freqs';
    d.innerHTML = '<span class="t">' + localT + '</span>' +
      '<span class="sym-tag ' + (s.symptom||'') + '">' + (s.symptom||'') + '</span>' +
      '<span class="sym-detail">' + detail + '</span>';
    sl.appendChild(d);
  });

  // Status bar
  document.getElementById('dot').className = 'dot live';
  document.getElementById('st').textContent = c.localTime + '  |  cycle ' + c.cycle;

  // Timeline history
  if (data.history) {
    hist = data.history.map(h => ({k: h.maxK, ei: h.ei, ts: h.ts, sym: h.symptom}));
  }
  draw();
}

function poll() {
  fetch('/api/state').then(r=>r.json()).then(d => { upd(d); setTimeout(poll, 5000); })
  .catch(() => { document.getElementById('dot').className='dot stale'; document.getElementById('st').textContent='disconnected'; setTimeout(poll, 5000); });
}
poll();
window.addEventListener('resize', draw);
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

    for freq_str, readings in cycle.get("stare", {}).items():
        for r in readings:
            k = r.get("kurtosis", 0)
            p = r.get("pulse_count", 0)
            f = r.get("freq_mhz", r.get("nominal_freq_mhz", 0))
            if k > max_k:
                max_k = k
            if k > 20:
                n_active += 1
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
        "nActive": n_active,
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

    # History: last 60 cycles summarized for timeline
    history = []
    for c in cycles[-60:]:
        max_k = 0
        for freq_str, readings in c.get("stare", {}).items():
            for r in readings:
                k = r.get("kurtosis", 0)
                if k > max_k:
                    max_k = k
        try:
            ts = c.get("timestamp", "")
            if ts:
                from datetime import datetime as dt
                utc_dt = dt.fromisoformat(ts.replace("Z", "+00:00"))
                local_dt = utc_dt.astimezone()
                ts_short = local_dt.strftime("%H:%M")
            else:
                ts_short = ""
        except Exception:
            ts_short = ""

        history.append({
            "maxK": round(max_k, 1),
            "ei": c.get("exposure_index"),
            "ts": ts_short,
            "symptom": None,
        })

    # Overlay symptoms onto timeline
    symptoms = []
    try:
        with open(SYMPTOM_LOG) as f:
            for line in f:
                try:
                    s = json.loads(line)
                    # Convert timestamp to local time for display
                    if s.get("timestamp"):
                        try:
                            from datetime import datetime as dt
                            utc_dt = dt.fromisoformat(
                                s["timestamp"].replace("Z", "+00:00"))
                            local_dt = utc_dt.astimezone()
                            s["localTime"] = local_dt.strftime("%I:%M %p")
                        except Exception:
                            pass
                    symptoms.append(s)
                except json.JSONDecodeError:
                    pass
    except FileNotFoundError:
        pass

    return {
        "current": latest,
        "history": history,
        "symptoms": symptoms[-15:],
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
