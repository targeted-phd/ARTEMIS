#!/usr/bin/env python3
"""
ARTEMIS Symptom Tag Server — minimal HTTP endpoint for logging symptoms.

Binds to Tailscale IP only. Receives POST /tag from ntfy action buttons
and logs to results/evidence/symptom_log.jsonl.

Usage:
  python tag_server.py                    # auto-detect Tailscale IP
  python tag_server.py --host 100.x.x.x  # explicit IP
  python tag_server.py --host 0.0.0.0     # all interfaces (less secure)
"""

import json
import os
import subprocess
import sys
import time
from datetime import datetime, timezone
from http.server import HTTPServer, BaseHTTPRequestHandler
from urllib.parse import urlparse, parse_qs
from pathlib import Path

RESULTS_DIR = os.environ.get("RESULTS_DIR", "results")
LOG_FILE = f"{RESULTS_DIR}/evidence/symptom_log.jsonl"
PORT = int(os.environ.get("TAG_PORT", "8091"))

Path(f"{RESULTS_DIR}/evidence").mkdir(parents=True, exist_ok=True)

VALID_SYMPTOMS = {
    "speech", "home", "away", "headache", "paresthesia",
    "sleep", "tinnitus", "pressure", "nausea", "clear",
    "other"
}


def get_tailscale_ip():
    """Get this machine's Tailscale IPv4 address."""
    try:
        r = subprocess.run(["tailscale", "ip", "-4"],
                          capture_output=True, text=True, timeout=5)
        ip = r.stdout.strip()
        if ip and ip.startswith("100."):
            return ip
    except (FileNotFoundError, subprocess.TimeoutExpired):
        pass
    return "127.0.0.1"


def get_latest_sentinel_context():
    """Read the most recent sentinel cycle and extract RF context for correlation."""
    try:
        # Find latest sentinel log
        import glob
        logs = sorted(glob.glob(f"{RESULTS_DIR}/sentinel_*.jsonl"))
        if not logs:
            return None
        with open(logs[-1]) as f:
            lines = f.readlines()
        if not lines:
            return None
        cycle = json.loads(lines[-1])

        # Extract per-frequency summary
        freq_summary = {}
        max_kurt = 0
        active_freqs = []
        for freq_str, readings in cycle.get("stare", {}).items():
            for r in readings:
                k = r.get("kurtosis", 0)
                if k > max_kurt:
                    max_kurt = k
                fmhz = r.get("freq_mhz", r.get("nominal_freq_mhz", freq_str))
                key = str(fmhz)
                if key not in freq_summary or r.get("kurtosis", 0) > freq_summary[key].get("max_kurt", 0):
                    freq_summary[key] = {
                        "max_kurt": round(r.get("kurtosis", 0), 1),
                        "pulses": r.get("pulse_count", 0),
                        "pwr_db": r.get("mean_pwr_db", 0),
                        "papr_db": r.get("papr_db", 0),
                    }
                if k > 20 and fmhz not in active_freqs:
                    active_freqs.append(fmhz)

        return {
            "cycle": cycle.get("cycle"),
            "cycle_ts": cycle.get("timestamp"),
            "max_kurt": round(max_kurt, 1),
            "active_freqs": sorted(active_freqs),
            "n_active": len(active_freqs),
            "freq_summary": freq_summary,
        }
    except Exception:
        return None


def get_rf_context_for_cycle(target_cycle):
    """Look up a specific cycle number from sentinel logs."""
    try:
        import glob
        logs = sorted(glob.glob(f"{RESULTS_DIR}/sentinel_*.jsonl"))
        # Search backwards through logs for the target cycle
        for logf in reversed(logs):
            with open(logf) as f:
                for line in f:
                    try:
                        cycle = json.loads(line)
                        if cycle.get("cycle") == target_cycle:
                            return _extract_rf_context(cycle)
                    except json.JSONDecodeError:
                        continue
        # Cycle not found, fall back to latest
        return get_latest_sentinel_context()
    except Exception:
        return get_latest_sentinel_context()


def _extract_rf_context(cycle):
    """Extract RF context dict from a sentinel cycle entry."""
    freq_summary = {}
    max_kurt = 0
    active_freqs = []
    for freq_str, readings in cycle.get("stare", {}).items():
        for r in readings:
            k = r.get("kurtosis", 0)
            if k > max_kurt:
                max_kurt = k
            fmhz = r.get("freq_mhz", r.get("nominal_freq_mhz", freq_str))
            key = str(fmhz)
            if key not in freq_summary or k > freq_summary[key].get("max_kurt", 0):
                freq_summary[key] = {
                    "max_kurt": round(k, 1),
                    "pulses": r.get("pulse_count", 0),
                    "pwr_db": r.get("mean_pwr_db", 0),
                    "papr_db": r.get("papr_db", 0),
                }
            if k > 20 and fmhz not in active_freqs:
                active_freqs.append(fmhz)
    return {
        "cycle": cycle.get("cycle"),
        "cycle_ts": cycle.get("timestamp"),
        "max_kurt": round(max_kurt, 1),
        "active_freqs": sorted(active_freqs),
        "n_active": len(active_freqs),
        "freq_summary": freq_summary,
    }


_last_tag = {"symptom": None, "time": 0}
DEDUP_WINDOW_S = 30  # ignore same symptom within 30 seconds


def log_symptom(symptom, note="", rf_snap=None):
    """Append symptom entry to JSONL log. RF context is self-contained
    from the notification button URL — no lookups needed.
    Deduplicates: same symptom+alert_id within 30s is ignored."""
    now = time.time()
    alert_id = rf_snap.get("aid") if rf_snap else None
    dedup_key = f"{symptom}:{alert_id}" if alert_id else symptom
    if dedup_key == _last_tag["symptom"] and (now - _last_tag["time"]) < DEDUP_WINDOW_S:
        return None  # duplicate, skip
    _last_tag["symptom"] = dedup_key
    _last_tag["time"] = now

    entry = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "symptom": symptom,
        "reporter": "subject",
        "alert_id": alert_id,
        "alert_cycle": rf_snap.get("c") if rf_snap else None,
        "alert_ts": rf_snap.get("ts") if rf_snap else None,
        "alert_max_kurt": rf_snap.get("mk") if rf_snap else None,
        "alert_n_active": rf_snap.get("nf") if rf_snap else None,
        "alert_active_freqs": rf_snap.get("af") if rf_snap else None,
        "response_delay_s": None,
    }
    if note:
        entry["note"] = note
    # Calculate response delay
    if rf_snap and rf_snap.get("ts"):
        try:
            alert_dt = datetime.fromisoformat(rf_snap["ts"].replace('Z', '+00:00'))
            entry["response_delay_s"] = round(
                (datetime.now(timezone.utc) - alert_dt).total_seconds(), 1)
        except (ValueError, TypeError):
            pass
    line = json.dumps(entry)
    with open(LOG_FILE, "a") as f:
        f.write(line + "\n")
        f.flush()
        os.fsync(f.fileno())
    return entry


class TagHandler(BaseHTTPRequestHandler):
    def do_POST(self):
        parsed = urlparse(self.path)

        if parsed.path == "/tag":
            # Accept symptom from query param or JSON body
            params = parse_qs(parsed.query)
            symptom = params.get("s", [None])[0]
            note = params.get("note", [""])[0]

            # Also try JSON body
            if not symptom:
                try:
                    length = int(self.headers.get("Content-Length", 0))
                    if length > 0:
                        body = json.loads(self.rfile.read(length))
                        symptom = body.get("symptom", body.get("s"))
                        note = body.get("note", note)
                except (json.JSONDecodeError, ValueError):
                    pass

            if not symptom or symptom not in VALID_SYMPTOMS:
                self.send_response(400)
                self.end_headers()
                self.wfile.write(
                    f"Bad symptom. Valid: {', '.join(sorted(VALID_SYMPTOMS))}".encode())
                return

            # Unpack self-contained RF snapshot from button URL
            rf_param = params.get("rf", [None])[0]
            rf_snap = None
            if rf_param:
                try:
                    rf_snap = json.loads(rf_param)
                except (json.JSONDecodeError, TypeError):
                    pass

            entry = log_symptom(symptom, note, rf_snap=rf_snap)
            if entry is None:
                # Duplicate within dedup window
                self.send_response(200)
                self.send_header("Access-Control-Allow-Origin", "*")
                self.end_headers()
                self.wfile.write(b'{"status":"dedup"}')
                return
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_header("Access-Control-Allow-Origin", "*")
            self.end_headers()
            self.wfile.write(json.dumps(entry).encode())
            print(f"  [TAG] {entry['timestamp']} — {symptom} {note}")

        else:
            self.send_response(404)
            self.end_headers()

    def do_GET(self):
        parsed = urlparse(self.path)

        if parsed.path == "/quick":
            # Mobile quick-tap page with all symptom buttons
            params = parse_qs(parsed.query)
            rf = params.get("rf", [""])[0]
            rf_esc = rf.replace("'", "\\'")
            buttons = [
                ("Speech", "speech", "#fa0", "#2a1800"),
                ("Headache", "headache", "#f44", "#2a0808"),
                ("Paresthesia", "paresthesia", "#4af", "#081828"),
                ("Tinnitus", "tinnitus", "#f8f", "#280828"),
                ("Nausea", "nausea", "#6d4", "#0a2808"),
                ("Pressure", "pressure", "#aaf", "#0a0a28"),
                ("Sleep", "sleep", "#88f", "#0a0828"),
                ("Clear", "clear", "#4a4", "#082808"),
            ]
            btns_html = ""
            for label, val, color, bg in buttons:
                btns_html += (
                    f'<button onclick="tag(\'{val}\')" '
                    f'style="background:{bg};color:{color};border:2px solid {color};'
                    f'padding:18px 0;font-size:18px;border-radius:8px;'
                    f'font-weight:bold;cursor:pointer;width:100%">'
                    f'{label}</button>\n'
                )
            page = f"""<!DOCTYPE html>
<html><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>ARTEMIS — Tag Symptom</title>
<style>
body {{ background:#08080d; color:#ccc; font-family:sans-serif; padding:16px; }}
h2 {{ color:#6af; font-size:14px; margin-bottom:12px; }}
.grid {{ display:grid; grid-template-columns:1fr 1fr; gap:10px; }}
.done {{ text-align:center; color:#4a4; font-size:16px; margin-top:16px; display:none; }}
</style></head><body>
<h2>ARTEMIS — Tag Symptom</h2>
<div class="grid">{btns_html}</div>
<div class="done" id="done">Logged.</div>
<script>
const rf = '{rf_esc}';
function tag(s) {{
  fetch('/tag?s=' + s + '&rf=' + encodeURIComponent(rf), {{method:'POST'}})
    .then(() => {{
      document.getElementById('done').style.display = 'block';
      setTimeout(() => {{ document.getElementById('done').style.display = 'none'; }}, 2000);
    }});
}}
</script></body></html>"""
            self.send_response(200)
            self.send_header("Content-Type", "text/html")
            self.end_headers()
            self.wfile.write(page.encode())

        elif parsed.path == "/tags":
            # Return recent tags
            try:
                with open(LOG_FILE) as f:
                    lines = f.readlines()
                entries = [json.loads(l) for l in lines[-50:]]
            except FileNotFoundError:
                entries = []
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_header("Access-Control-Allow-Origin", "*")
            self.end_headers()
            self.wfile.write(json.dumps(entries, indent=2).encode())

        elif parsed.path == "/health":
            self.send_response(200)
            self.end_headers()
            self.wfile.write(b"ok")

        else:
            self.send_response(404)
            self.end_headers()

    def do_OPTIONS(self):
        """Handle CORS preflight."""
        self.send_response(200)
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")
        self.end_headers()

    def log_message(self, format, *args):
        pass  # suppress default logging


def main():
    import argparse
    parser = argparse.ArgumentParser(description="ARTEMIS Symptom Tag Server")
    parser.add_argument("--host", type=str, default=None,
                       help="Bind address (default: auto-detect Tailscale IP)")
    parser.add_argument("--port", type=int, default=PORT)
    args = parser.parse_args()

    host = args.host or get_tailscale_ip()
    server = HTTPServer((host, args.port), TagHandler)
    print(f"ARTEMIS Tag Server — http://{host}:{args.port}")
    print(f"  POST /tag?s=speech    — log symptom")
    print(f"  GET  /tags            — view recent tags")
    print(f"  Log: {LOG_FILE}")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nShutting down.")
        server.server_close()


if __name__ == "__main__":
    main()
