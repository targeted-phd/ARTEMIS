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


def log_symptom(symptom, note="", alert_data=None):
    """Append symptom entry to JSONL log."""
    entry = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "symptom": symptom,
        "note": note,
        "reporter": "subject",
    }
    if alert_data:
        entry["alert_data"] = alert_data
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

            entry = log_symptom(symptom, note)
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

        if parsed.path == "/tags":
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
