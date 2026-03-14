# ARTEMIS — Anomalous RF Tracking, Evidence Mining & Intelligence System

Open-source forensic RF investigation toolkit. Continuous monitoring, real-time alerting, spectral analysis, exposure quantification, and symptom correlation for investigating anomalous pulsed signals across multiple frequency bands.

**Repository:** [github.com/targeted-phd/ARTEMIS](https://github.com/targeted-phd/ARTEMIS)

## What This Does

ARTEMIS monitors the RF spectrum 24/7 with an RTL-SDR, detects anomalous pulsed signals that standard spectrum analyzers miss, quantifies exposure using a dimensionless Buckingham Pi index, correlates RF activity with reported symptoms via mobile push notifications, and generates forensic evidence reports.

### Key Capabilities

- **24/7 Sentinel Monitoring** — 13 target frequencies across two bands, frequency jitter for broadband detection, auto-restart on failure
- **Exposure Index (EI)** — Dimensionless power-time-impulsiveness metric: `EI = Σ_f [P_linear × Σ(pulse_width_μs) × (kurtosis / k_noise)]`
- **Mobile Alerts** — Self-hosted ntfy over Tailscale mesh, push notifications with symptom tagging (7 symptoms × 4 severity levels)
- **Live Dashboard** — Real-time browser UI with timeline charts, frequency heatmap, zone power bars, symptom overlay
- **Spectrum Painter** — Waterfall spectrograms, pulse envelope analysis, instantaneous frequency (modulation fingerprint), pulse statistics
- **Evidence Reports** — Automated forensic reports with hardware identification, temporal correlation, spectral analysis
- **Knowledge Graph** — 739 academic papers in Neo4j with content-level entity extraction

## Architecture

```
┌──────────────────────────────────────────────────────────────────────┐
│                         ARTEMIS SYSTEM                               │
│                                                                      │
│  RTL-SDR ──→ sentinel.py (systemd, 24/7)                            │
│               ├── 13 target freqs (Zone A 622-636 + Zone B 824-834) │
│               ├── ±1.5 MHz jitter per capture                       │
│               ├── Exposure Index (EI) per cycle                     │
│               ├── Audible alerts (local speaker)                    │
│               ├── ntfy push (Tailscale) ──→ Phone app               │
│               │                              └── Tag Symptoms page  │
│               └── JSONL logs (hourly rotation)                      │
│                        │                                             │
│                        ▼                                             │
│  dashboard.py (localhost:8080) ◄── reads logs every 5s              │
│  ├── EI / Kurtosis / Pulses / Active Freqs                         │
│  ├── Zone A/B/UL power timeline (independent scaling)               │
│  ├── Frequency × Time heatmap with symptom markers                  │
│  └── Recent symptoms list                                            │
│                                                                      │
│  tag_server.py (Tailscale:8091) ◄── phone button presses           │
│  ├── /quick — multi-symptom severity page                           │
│  ├── /tag — log symptom with RF context (self-contained nonce)      │
│  └── symptom_log.jsonl                                               │
│                                                                      │
│  rebuild_ml_dataset.sh (cron, every 30 min)                         │
│  └── ml_master_dataset.json — unified ML-ready dataset              │
│                                                                      │
│  autopush.sh (cron, hourly)                                         │
│  └── git commit + push to GitHub via SSH deploy key                  │
│                                                                      │
│  spectrum_painter.py — IQ → waterfall + pulse + modulation analysis │
│  kg_pipeline.py — GROBID → Neo4j knowledge graph + embeddings      │
│  forward_model.py — speech → encoding → simulated SDR comparison    │
└──────────────────────────────────────────────────────────────────────┘
```

## Monitored Frequency Zones

| Zone | Frequency Range | Band Allocation | Role |
|------|----------------|-----------------|------|
| **Zone A** | 622–636 MHz | UHF-TV / 600 MHz 5G transition | Primary exposure (highest EI) |
| **Zone B** | 824–834 MHz | Cellular downlink (B5/B26) | Secondary / targeting |
| **UL** | 878 MHz | Cellular uplink | Possible tracking/feedback |

## Exposure Index

The Buckingham Pi Exposure Index quantifies total RF exposure without calibrated equipment:

```
EI = Σ across all active frequencies [
    P_linear                    (received power, uncalibrated but consistent)
  × Σ pulse_width_μs           (total pulse duration, extrapolated from sampled widths)
  × (kurtosis / k_noise)       (impulsiveness relative to noise floor)
]
```

- **EI < 5**: Quiet / noise floor
- **EI 20–200**: Low activity (typical daytime)
- **EI 200–1000**: Moderate activity
- **EI 1000–2000**: High activity
- **EI > 2000**: Extreme (headache/tinnitus onset observed above this threshold)

Decomposed per zone: `ei_zone_a`, `ei_zone_b` — reveals power allocation shifts between bands.

## Symptom Tagging

Mobile push notifications via self-hosted ntfy over Tailscale. Each notification links to a symptom tagging page with:

| Symptom | Color | Description |
|---------|-------|-------------|
| Speech | Gold | Perceived speech / voice-to-skull |
| Headache | Red | Head pain |
| Tinnitus | Pink | Ringing / high-pitched tone |
| Paresthesia | Blue | Tingling / goosebumps without cold |
| Nausea | Green | Nausea / dizziness |
| Pressure | Light blue | Head/ear pressure |
| Sleep disruption | Purple | Disrupted sleep |

Each symptom has severity 0–3 (none / mild / moderate / severe). Multiple symptoms can be tagged per alert. Each tag carries the alert's unique nonce (alert_id) and RF snapshot so it maps to the exact signal event, regardless of response delay.

## ML Dataset

`results/ml_master_dataset.json` — rebuilt every 30 minutes. Contains:

| Section | Description |
|---------|-------------|
| `timeline` | Per-cycle rows with EI, kurtosis, pulse counts, widths, symptom labels, severity. All CST. |
| `symptoms` | Raw symptom reports with alert RF context and response delay |
| `iq_captures` | 2,896 raw IQ file index with timestamps and frequencies |
| `spectrograms` | 37 spectrogram analyses with PRF, duty cycle, bandwidths |
| `wideband_survey` | 872-channel survey (24–1766 MHz) |

### Timeline Row Features

| Feature | Type | Description |
|---------|------|-------------|
| `cst` | string | Timestamp in CST |
| `hour`, `minute` | int | For time-of-day analysis |
| `day_of_week` | string | For weekly patterns |
| `is_night` | bool | 9 PM – 6 AM |
| `type` | string | ACTIVE / QUIET / GAP_NO_DATA |
| `has_zone_a` | bool | False before Zone A was added to monitoring |
| `ei_total` | float | Total Exposure Index |
| `ei_zone_a` | float | Zone A EI (None if not monitored) |
| `ei_zone_b` | float | Zone B EI |
| `max_kurt` | float | Peak kurtosis across all readings |
| `max_kurt_zone_a/b/ul` | float | Per-zone peak kurtosis |
| `n_active_targets` | int | Number of 13 nominal targets active (kurt > 20) |
| `total_pulses` | int | Total pulse count |
| `mean_pulse_width_us` | float | Average pulse width in microseconds |
| `total_pulse_duration_us` | float | Integrated pulse-on time |
| `sym_speech`, `sym_headache`, etc. | int (0/1) | Binary symptom indicators |
| `sev_speech`, `sev_headache`, etc. | int (0–3) | Max severity per symptom |
| `max_severity` | int (0–3) | Worst symptom severity this cycle |
| `any_symptom` | int (0/1) | Any symptom reported |

**Important:** `GAP_NO_DATA` means the sentinel was not running — do not treat as quiet. `has_zone_a=False` means Zone A was not monitored — `ei_zone_a` will be None.

## Services (systemd)

| Service | Port | Binding | Purpose |
|---------|------|---------|---------|
| `rf-sentinel` | — | — | 24/7 RF monitoring, alerts |
| `artemis-dash` | 8080 | localhost | Live dashboard |
| `artemis-tags` | 8091 | Tailscale IP | Symptom tag server |
| `ntfy` | 8090 | Tailscale IP | Push notification server |

```bash
# Status
systemctl --user status rf-sentinel
systemctl --user status artemis-dash
systemctl --user status artemis-tags
sudo systemctl status ntfy

# Restart
systemctl --user restart rf-sentinel
```

## Cron Jobs

| Schedule | Script | Purpose |
|----------|--------|---------|
| Every hour at :00 | `autopush.sh` | Git commit + push to GitHub |
| Every 30 min | `rebuild_ml_dataset.sh` | Rebuild ML master dataset |

## Evidence Reports

All reports in `results/evidence/`:

| Report | Date | Content |
|--------|------|---------|
| `incident_report_20260313.md` | Mar 12–13 | Initial incident: nocturnal intensification, frequency hopping, symptom correlation |
| `spectrum_analysis_report_20260313.md` | Mar 13 | Waterfall spectrograms, hardware fingerprint, legitimate sources ruled out |
| `wideband_survey_report_20260313.md` | Mar 13 | Full spectrum 24–1766 MHz, three active zones identified |
| `transmitter_identification_report_20260313.md` | Mar 13–14 | Hardware ID: USRP X310, dual-band, $9–14K system |
| `escalation_report_20260314_0028.md` | Mar 14 | Sustained 374 kurtosis, headache + tinnitus, dose-response |
| `live_activity_report_20260313_1654.md` | Mar 13 | Live capture during active event, 136.4 kurtosis |

## Signal Characteristics (Summary)

| Parameter | Zone A (622–636 MHz) | Zone B (824–834 MHz) |
|-----------|---------------------|---------------------|
| Peak kurtosis | 369 | 374 |
| PRF (intra-burst) | Not yet characterized | 150,000–253,000 Hz |
| Pulse width | Not yet characterized | 2.1–7.2 μs |
| Duty cycle | Not yet characterized | 0.27–1.78% |
| Intra-pulse bandwidth | Not yet characterized | 300–1,500 kHz |
| Received power | -17 to -28 dB | -38 to -44 dB |
| Channel spacing | 2 MHz | 2 MHz |

Zone co-activation: 79% of cycles show both zones active simultaneously. Zone A never activates alone.

## Knowledge Graph

739 papers in Neo4j with 38,700+ edges across 13 node types and 11 edge types. Content-level entity extraction for frequencies, power levels, mechanisms, health effects, technologies, and organizations.

```
Neo4j:    bolt://localhost:7687  (neo4j / rfmonitor2026)
Browser:  http://localhost:7474
```

Pipeline: `python kg_pipeline.py extract → build → embed → search "query"`

## Quick Start

```bash
# Clone
git clone https://github.com/targeted-phd/ARTEMIS.git
cd ARTEMIS

# Environment
python -m venv .venv && source .venv/bin/activate
pip install numpy scipy matplotlib requests

# Start monitoring
python sentinel.py --duration 999999999

# Dashboard (separate terminal)
python dashboard.py
# Open http://127.0.0.1:8080

# Spectrum analysis on captured IQ
python spectrum_painter.py --batch

# Rebuild ML dataset
bash rebuild_ml_dataset.sh
```

## Hardware

**Monitoring station:**
- RTL-SDR Blog V4 (R828D tuner, 24 MHz – 1.766 GHz)
- Omnidirectional whip antenna
- Ubuntu on WSL2, GTX 1080 desktop

**Identified transmitter (from signal analysis):**
- Ettus Research USRP X310 with dual UBX-160 daughterboards
- External wideband power amplifiers (622 MHz + 826 MHz)
- Log-periodic dipole array (LPDA) antenna, 500–900 MHz
- Pre-programmed GNU Radio / UHD application
- Estimated system cost: $9,000–14,000
- Fixed installation, AC powered, estimated range 100–500 meters

## Detection Method

Standard spectrum analyzers average power over time, burying low-duty-cycle pulses. A 10 μs pulse in a 10s integration window is attenuated by -60 dB — invisible.

ARTEMIS captures raw IQ and computes per-capture:
- **Kurtosis**: Gaussian noise ≈ 3.0 (RTL-SDR baseline ~8.5). Impulsive signals: 20–374.
- **PAPR**: Peak-to-average power ratio. Gaussian ≈ 10–12 dB. Pulses: 17–30 dB.
- **Pulse detection**: 4σ amplitude threshold, minimum 3 samples. Measures width, SNR, timing.
- **Exposure Index**: Integrates power × pulse duration × impulsiveness across all frequencies.

## Security

- Dashboard binds to `127.0.0.1` only — not network accessible
- ntfy and tag server bind to Tailscale IP only — encrypted mesh, no public internet
- SSH deploy key for GitHub push — scoped to ARTEMIS repo only
- Pseudonymous GitHub account — no personal identity in commits or repo
- All data stays on local machine + Tailscale mesh + GitHub

## License

Research use. This toolkit is designed for defensive RF forensics and academic investigation.
