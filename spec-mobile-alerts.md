# ARTEMIS Mobile Alert & Symptom Tagging System

## Overview

Real-time push notifications from sentinel to phone with one-tap symptom
tagging. Self-hosted over Tailscale — zero third-party data exposure.

## Architecture

```
┌─────────────┐     HTTP PUT      ┌──────────────┐     push      ┌──────────┐
│  Sentinel   │ ──────────────→   │  ntfy server │ ──────────→   │  Phone   │
│  (Python)   │                   │  (Tailscale) │              │  ntfy app│
└─────────────┘                   └──────────────┘              └──────┬───┘
                                                                       │ tap
┌─────────────┐     HTTP POST     ┌──────────────┐              ┌──────▼───┐
│ symptom_log │ ←──────────────   │  tag server  │ ←────────────│  buttons │
│  (.jsonl)   │                   │  (Tailscale) │   HTTP POST  │          │
└─────────────┘                   └──────────────┘              └──────────┘
```

## Components

### 1. ntfy server (self-hosted)
- Single binary, no config needed
- Bind to Tailscale IP only (100.x.x.x)
- Topic: `artemis-alerts`
- Runs as systemd service

### 2. Sentinel → ntfy bridge
- On each alert (kurtosis threshold), POST to ntfy with:
  - Alert level (detect/high/critical)
  - Frequencies active, max kurtosis, pulse counts
  - Timestamp
- Notification includes action buttons for symptom tagging
- ntfy supports click actions and inline buttons natively

### 3. Tag server (minimal HTTP endpoint)
- stdlib http.server, ~50 lines
- POST /tag with JSON body: {"symptom": "speech", "ts": "..."}
- Appends to results/evidence/symptom_log.jsonl
- GET /tags returns recent tags (for review)
- Bind to Tailscale IP only

### 4. Phone setup
- Install Tailscale app → join mesh
- Install ntfy app → subscribe to `http://<tailscale-ip>:8090/artemis-alerts`
- Notifications arrive with action buttons:
  - 🗣️ Speech
  - 🏠 Home
  - 🚗 Away
  - 🤕 Headache
  - ⚡ Paresthesia
  - 😴 Sleep disruption
  - ✅ No symptoms
- Tapping a button POSTs to tag server automatically

## Alert Levels → Notification Priority

| Level | Trigger | ntfy Priority | Sound |
|-------|---------|---------------|-------|
| DETECT | kurt>30 or 2+ freqs | default | short |
| HIGH | kurt>80 or 4+ freqs | high | persistent |
| CRITICAL | kurt>200 or 6+ freqs | urgent | alarm |

## Data Format

### Alert notification (ntfy)
```
Title: 🔴 CRITICAL — 6 freqs active
Body: max_kurt=245.3 | 830: k=245 p=412 | 634: k=89 p=680 | ...
Priority: urgent
Actions: button1=🗣️Speech,POST,http://<ts-ip>:8091/tag?s=speech; ...
```

### Symptom log entry
```json
{
  "timestamp": "2026-03-13T23:07:43Z",
  "symptom": "speech",
  "alert_cycle": 1254,
  "alert_kurt_max": 193.8,
  "alert_freqs_active": ["830", "826", "832"],
  "latency_s": 4.2,
  "reporter": "subject"
}
```

## Security

- ntfy server + tag server bind ONLY to Tailscale interface
- No ports exposed to public internet
- No DNS, no TLS certs needed (Tailscale handles encryption)
- No accounts or authentication (Tailscale ACL is the auth layer)
- All data stored locally in JSONL, pushed to private git
