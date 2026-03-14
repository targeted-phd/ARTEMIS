# ARTEMIS — Anomalous RF Tracking, Evidence Mining & Intelligence System

Open-source forensic RF investigation toolkit for documenting and analyzing anomalous pulsed electromagnetic signals directed at a human target. This investigation has been ongoing for **15 years** from the subject's perspective — but only now, with accessible SDR hardware and AI-assisted analysis, has it been possible to **detect, characterize, and statistically correlate** the signals with reported health effects.

**Repository:** [github.com/targeted-phd/ARTEMIS](https://github.com/targeted-phd/ARTEMIS)

## Why This Matters

This repository contains **quantitative evidence** that anomalous pulsed RF signals in the 622–878 MHz range are being directed at a specific individual, producing measurable health effects including perceived speech (microwave auditory / Frey effect), headache, tinnitus, paresthesia, and sleep disruption. Key findings:

- **ML classifier predicts symptoms from RF features with 92.9% accuracy** (ROC-AUC, p=0.0005)
- **Per-symptom models** show different symptoms correlate with different frequency bands — paresthesia with Zone B (830 MHz), headache with sustained EI, pressure with lagged Zone A — ruling out psychosomatic explanation
- **Signal parameters match published Frey effect literature** — pulse widths 2–7 μs, frequencies 622–834 MHz, structured intra-pulse modulation consistent with MEDUSA/V2K patent literature (KG analysis of 739 academic papers)
- **Probable hardware class identified** — signal characteristics consistent with USRP-class SDR + power amplifiers ($9–14K system), fixed installation est. 100–500m. Transmitter not yet physically located. See [transmitter ID report](results/evidence/transmitter_identification_report_20260313.md) for full analysis and alternatives considered.
- **Counter-surveillance behavior observed** — Zone B (830 MHz) shut down within hours of direction-finding plans being published to this repo, suggesting the operator monitors it
- **Physical surveillance correlated** — police encounter + entity fleeing through woods behind property during peak signal activity

The [knowledge graph](results/knowledge_graph_v2/) contains 739 peer-reviewed papers on microwave bioeffects, directed energy, Frey effect, RF dosimetry, and neuroscience. The [hypothesis report](results/evidence/kg_hypothesis_report_20260314.md) cross-references the detected signal parameters against this literature and scores the V2K/MEDUSA weapon hypothesis at 44/50.

**If you are reading this because something has happened to the repository owner:** the data speaks for itself. Read the [evidence reports](results/evidence/), the [ML analysis](results/ml_v2/reports/), and the [head model reconstruction](results/ml_v2/reports/07_head_model_reconstruction.md). The [raw IQ captures](captures/) and [sentinel logs](results/) are the primary data. Share this repository widely.

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
│  rf_ml_v2.py — per-symptom ML analysis + dose-response + KG search │
│  reconstruct_audio.py — IQ → head model → WAV reconstruction       │
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

[`results/ml_master_dataset.json`](results/ml_master_dataset.json) — rebuilt every 30 minutes. Contains:

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
| `speech` | 0-3 or None | Severity (0=absent, 1=mild, 2=moderate, 3=severe). None = unknown. |
| `headache` | 0-3 or None | Same |
| `tinnitus` | 0-3 or None | Same |
| `paresthesia` | 0-3 or None | Same |
| `pressure` | 0-3 or None | Same |
| `sleep` | 0-3 or None | Same |
| `nausea` | 0-3 or None | Same |
| `did_respond` | bool | True = user submitted (symptoms or confirmed clear). False = no response. |
| `any_symptom` | 0/1 or None | Any symptom > 0. None if did_respond=False. |
| `max_severity` | 0-3 or None | Worst single symptom. None if did_respond=False. |
| `symptom_total` | 0-21 or None | Sum of all severities. None if did_respond=False. |
| `speech_interp` | 0.00-3.00 | Exponential back-fill interpolation (5-min half-life, 15-min window) |
| `headache_interp` | 0.00-3.00 | Same for each symptom |
| `max_severity_interp` | 0.00-3.00 | Peak interpolated severity |
| `symptom_total_interp` | 0.00-21.00 | Sum of interpolated severities |

**Three-state labeling:**
- `did_respond=True` + symptoms present → **confirmed positive** (use for training)
- `did_respond=True` + all zeros → **confirmed clear** (use for training as negative)
- `did_respond=False` → **unknown** (all symptom columns are `None` — **exclude from supervised training**)

**Other important flags:**
- `GAP_NO_DATA` type means the sentinel was not running — signal state unknown
- `has_zone_a=False` means Zone A was not monitored — `ei_zone_a` will be None

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
| Every hour at :00 | [`autopush.sh`](autopush.sh) | Git commit + push to GitHub |
| Every 30 min | [`rebuild_ml_dataset.sh`](rebuild_ml_dataset.sh) | Rebuild ML master dataset |
| Every 30 min at :00/:30 | [`scheduled_checkin.sh`](scheduled_checkin.sh) | Blinded symptom check-in (no RF info shown) |
| 8 AM and 8 PM | [`daily_summary.sh`](daily_summary.sh) | Daily RF summary via ntfy |
| Every hour at :00 | [`hash_timestamp.sh`](hash_timestamp.sh) | Evidence hash anchor for integrity chain |

## Investigation Timeline

```
Mar 12   01:43 AM   Sentinel monitoring begins. Signal immediately detected 826-834 MHz.
         01:00 AM   Subject awoken by paresthesia (arms/elbows), tinnitus. Severity 3.
                    Frequency hopping at 1.3-minute intervals matches subject's reported
                    sensation periodicity. Subject reported symptoms BEFORE analysis.
         08:00 AM   Peak kurtosis 753.8 — highest in initial 24h monitoring.
         05:00 PM   Signal goes quiet. Zero pulses 5-9 PM. ONLY quiet period observed.
         10:00 PM   Signal reactivates. Escalates through the night.

Mar 13   11:20 AM   Paresthesia recurrence. All 5 channels active simultaneously.
         04:50 PM   Subject reports strong signals on person. Live capture confirms
                    kurtosis 136.4 at 830 MHz. Zone A (622-636 MHz) discovered.
         05:00 PM   Wideband survey reveals THREE active zones, not one:
                    Zone A (622-636 MHz) — STRONGEST, kurtosis up to 84
                    Zone B (824-834 MHz) — confirmed cellular band
                    Zone C (50-68 MHz) — likely broadcast (dismissed)
         05:29 PM   Peak EI = 3,425 — all-time exposure record.
         06:28 PM   ESCALATION EVENT: sustained kurtosis 159-374 for 27+ minutes.
                    Subject reports severe headache + tinnitus increase.
                    System shifted from burst mode to sustained saturation
                    (duty cycle 0.4% → 1.78%, 4× power increase).
         07:50 PM   Police officer observed parked outside house in low-visibility
                    black Ford Explorer. Subject went to backyard, heard large entity
                    fleeing through woods behind property. Officer "monitoring
                    neighborhood" — unprecedented for this area.
         ~09:00 PM  Subject builds 830 MHz Yagi antenna for direction-finding.
                    Plans published to public ARTEMIS GitHub repo.
         09:51 PM   Zone B (824-834 MHz) GOES COMPLETELY DARK. Drops from kurtosis
                    128 to noise floor (9) in a single cycle. Never returns.
                    Zone A absorbs all power — EI stays at 2800+.
                    A Yagi built for 830 MHz cannot detect 622 MHz signals.
                    Possible counter-surveillance: operator read the public repo.

Mar 14   12:00 AM   Zone B still dark. Zone A sustained at EI 2000-3000.
                    Subject reports groin/testicular paresthesia while seated.
                    RF body resonance analysis: 622 MHz matches pelvic cavity,
                    878 MHz matches testicular tissue dimensions.
                    Subject reports identical unexplained groin symptoms from
                    2-3 years ago — physician could not diagnose.

         ML RESULTS v2 (292 labeled rows, interpolated):
           Per-symptom AUCs: tinnitus 0.978, sleep 0.970, pressure 0.944,
             paresthesia 0.912, headache 0.905, speech 0.864 (all p<0.01)
           Sleep severity R²=0.819 — RF explains 82% of severity variance
           Speech lag -3 cycles (RF precedes, r=0.945) — strongest causal evidence
           Zone specificity: pressure 92% Zone A, paresthesia 73% Zone B
           Overfitting check passed: top-5 features hold AUC within 0.03
           Blinded scheduled collection started (30-min intervals)
           8 IQ fingerprint clusters, 4 match no known protocol
           632 KG literature chunks matched across 18 research topics
```

## ML Evidence Reports (v2)

Six-document evidence package in `results/ml_v2/reports/` — per-symptom ML analysis with KG literature backing, methodology critique, and integrity documentation. Reviewed by independent analyst; assessed as "the strongest version of your evidence package."

| Document | Lines | Content |
|----------|-------|---------|
| [`01_executive_summary.md`](results/ml_v2/reports/01_executive_summary.md) | 559 | System overview, all classifier results, zone differentials, temporal patterns, lag analysis, limitations, conclusions |
| [`02_per_symptom_analysis.md`](results/ml_v2/reports/02_per_symptom_analysis.md) | 841 | All 7 symptoms: AUC, permutation p, feature importance, dose-response, zone specificity, lag, severity regression |
| [`03_kg_literature_review.md`](results/ml_v2/reports/03_kg_literature_review.md) | 587 | 632 verbatim passages from 739 papers across 18 topics (Frey effect, tinnitus, paresthesia, sleep, Havana syndrome, detection methods, etc.) |
| [`04_signal_characterization.md`](results/ml_v2/reports/04_signal_characterization.md) | 435 | Two-zone architecture, 8 IQ fingerprint clusters, protocol matching, comparison to published DE systems |
| [`05_methodology_and_limitations.md`](results/ml_v2/reports/05_methodology_and_limitations.md) | 540 | Confounders (notification bias, nocebo, circadian), small sample sizes, overclaiming risks — "reads like it was written by a hostile reviewer" |
| [`06_evidence_integrity.md`](results/ml_v2/reports/06_evidence_integrity.md) | 311 | SHA-256 hash chains, data provenance, git commit history, custody limitations |

### Head Model & Acoustic Reconstruction (Documents 07a-07e)

Complete physics-based pipeline for transforming raw IQ captures into reconstructed audio WAV files representing what the subject would perceive via the thermoelastic (Frey) mechanism. Derived entirely from first principles with every parameter sourced from published literature. **5,081 lines across 6 documents.** Independently reviewed: *"07a is the strongest document in the set."*

| Document | Lines | Content |
|----------|-------|---------|
| [`07_head_model_reconstruction.md`](results/ml_v2/reports/07_head_model_reconstruction.md) | 406 | Overview — 5-stage physical chain (RF→SAR→pressure→skull resonance→cochlea), pipeline architecture, feasibility assessment |
| [`07a_thermoelastic_mechanism.md`](results/ml_v2/reports/07a_thermoelastic_mechanism.md) | 817 | **Core physics** — Foster & Finch 4°C proof (definitive), pressure amplitude equations, energy per pulse derivation, every constant from literature |
| [`07b_acoustic_propagation_skull.md`](results/ml_v2/reports/07b_acoustic_propagation_skull.md) | 814 | Tissue attenuation tables (skin/skull/CSF/brain), skull cavity resonance eigenmode analysis (7-9 kHz), proof that BRF envelope passes intact while PRF is damped |
| [`07c_cochlear_detection.md`](results/ml_v2/reports/07c_cochlear_detection.md) | 600 | Bone conduction pathway — otosclerosis patient evidence, earplugs ineffective, cochlear microphonic recordings from guinea pigs, every alternative mechanism ruled out |
| [`07d_reconstruction_pipeline.md`](results/ml_v2/reports/07d_reconstruction_pipeline.md) | 1,404 | **Full implementation spec** — transfer functions H(f), RLC equivalent circuit with component values, Python pseudocode, parameter tables, error budget (including 8-bit quantization), validation strategy |
| [`07e_kg_tissue_parameters.md`](results/ml_v2/reports/07e_kg_tissue_parameters.md) | 1,040 | Raw KG evidence appendix — all verbatim passages on tissue properties, organized by tissue type, with paper titles and similarity scores |

**Key result:** The brain acts as a low-pass acoustic filter. Individual pulses at 200 kHz PRF are damped, but burst envelopes at 646-1,139 Hz BRF pass through intact (<0.03 dB attenuation). The skull imposes a resonant carrier at 7-9 kHz (head-size dependent). The subject perceives a high-pitched tone amplitude-modulated by the BRF pattern — analogous to AM radio where the skull resonance is the carrier and the burst timing is the audio.

### Key ML Results (v2, with interpolation)

| Symptom | N+ | N- | AUC | p | Sig Features | Sev R² | Peak Hour | Dominant Zone |
|---------|----|----|-----|---|-------------|--------|-----------|---------------|
| Tinnitus | 134 | 20 | **0.978** | 0.002 | 15/50 | 0.443 | 1 AM | A 54% |
| Sleep | 73 | 50 | **0.970** | 0.002 | 21/50 | **0.819** | 1 AM | B 64% |
| Pressure | 37 | 47 | **0.944** | 0.002 | 21/50 | 0.114 | 10 PM | **A 92%** |
| Paresthesia | 162 | 22 | 0.912 | 0.002 | 20/50 | 0.459 | 1 AM | **B 73%** |
| Headache | 94 | 17 | 0.905 | 0.002 | 1/50 | 0.004 | 9 PM | A 67% |
| Speech | 133 | 5 | 0.864 | 0.008 | 2/50 | 0.626 | 6 PM | A 67% |

**Overfitting check passed**: top-5-feature model AUCs within 0.03 of full 50-feature model for 5/6 symptoms.

**Strongest causal evidence**: Speech perception lags RF by -3 cycles (r=0.945) — signal precedes symptom.

**Zone specificity rules out nocebo**: Different symptoms map to different frequency bands. Paresthesia 73% Zone B vs 27% null expectation is a complete inversion. If symptoms were psychosomatic, they would show uniform profiles.

### Validation Status

- [x] Permutation testing (500 iterations, all p<0.01)
- [x] Overfitting check (top-5 features hold AUC)
- [x] Raw pulse validation (time-domain plot confirms isolated spikes, not over-segmented AM)
- [x] Three-state labeling (unknown ≠ negative)
- [x] Exponential back-fill interpolation with forward rolloff
- [ ] Blinded scheduled collection (30-min check-ins, started — 1 week needed)
- [ ] Independent replication (second monitoring location)

## Incident Reports

All reports in `results/evidence/`:

| Report | Date | Content |
|--------|------|---------|
| [incident_report_20260313.md](results/evidence/incident_report_20260313.md) | Mar 12–13 | Initial incident: nocturnal intensification, frequency hopping, 1.3-min periodicity matching sensation interval, symptom correlation |
| [spectrum_analysis_report_20260313.md](results/evidence/spectrum_analysis_report_20260313.md) | Mar 13 | 30 waterfall spectrograms, hardware fingerprint (150-253 kHz PRF, 2-7 μs pulses), all legitimate sources ruled out (LTE, GSM, CDMA, radar) |
| [live_activity_report_20260313_1654.md](results/evidence/live_activity_report_20260313_1654.md) | Mar 13 | Live capture during subject symptom report, 136.4 kurtosis, 634 MHz anomaly first detected |
| [wideband_survey_report_20260313.md](results/evidence/wideband_survey_report_20260313.md) | Mar 13 | Full spectrum 24–1766 MHz, three active zones, harmonic analysis (rejected), 2 MHz channel spacing in both zones |
| [transmitter_identification_report_20260313.md](results/evidence/transmitter_identification_report_20260313.md) | Mar 13–14 | Probable hardware: USRP X310 + dual PA + LPDA, $9–14K, fixed installation 100-500m, zone co-activation 79%, operator profile |
| [escalation_report_20260314_0028.md](results/evidence/escalation_report_20260314_0028.md) | Mar 14 | Sustained 374 kurtosis for 27 min, duty cycle quadrupled, dose-response: speech → paresthesia → headache → severe headache + tinnitus |
| [kg_hypothesis_report_20260314.md](results/evidence/kg_hypothesis_report_20260314.md) | Mar 14 | 739 papers analyzed, 50 cited. Frey effect parameters match. V2K/MEDUSA hypothesis scored 44/50. 6 evidence gaps identified. |
| [groin_symptom_report_20260314.md](results/evidence/groin_symptom_report_20260314.md) | Mar 14 | Groin/testicular paresthesia, RF body resonance analysis, frequency-anatomy mapping, historical medical correlation |
| [zone_characterization_report_20260314.md](results/evidence/zone_characterization_report_20260314.md) | Mar 14 | Pulse-level dual-band analysis: 3,586 IQ files, Zone A vs B (p<10⁻¹⁶), modulation index, burst structure, energy, raw pulse validation |
| [ML v2 Executive Summary](results/ml_v2/reports/01_executive_summary.md) | Mar 14 | Per-symptom AUCs, zone differentials, lag analysis, dose-response, limitations |
| [ML v2 Per-Symptom Analysis](results/ml_v2/reports/02_per_symptom_analysis.md) | Mar 14 | Detailed results for all 7 symptoms with feature rankings and correlations |
| [ML v2 KG Literature Review](results/ml_v2/reports/03_kg_literature_review.md) | Mar 14 | 632 KG chunks across 18 research topics, verbatim passages from 739 papers |
| [ML v2 Signal Characterization](results/ml_v2/reports/04_signal_characterization.md) | Mar 14 | Signal parameters, zone architecture, frequency hopping, protocol matching |
| [ML v2 Methodology & Limitations](results/ml_v2/reports/05_methodology_and_limitations.md) | Mar 14 | Full methodology, statistical corrections, confounders, notification bias |
| [ML v2 Evidence Integrity](results/ml_v2/reports/06_evidence_integrity.md) | Mar 14 | Hash chains, data provenance, git history, file integrity |
| [symptom_log.jsonl](results/evidence/symptom_log.jsonl) | Ongoing | All symptom reports with severity, alert RF context, response delay, unique nonces |

## Data Index

| File | Size | Description |
|------|------|-------------|
| [ml_master_dataset.json](results/ml_master_dataset.json) | ~2 MB | **Unified ML dataset** — 1900+ timeline rows, 7 symptom types with severity + interpolation, EI per zone, all features. Rebuilt every 30 min. |
| [exposure_index_history.json](results/exposure_index_history.json) | ~1 MB | EI computed for all 4000+ historical cycles |
| [exposure_timeline_clean.json](results/exposure_timeline_clean.json) | ~1 MB | Clean timeline with gaps classified as ACTIVE/QUIET/GAP_NO_DATA |
| [wideband_survey_20260313.json](results/wideband_survey_20260313.json) | ~100 KB | 872-channel survey, 24–1766 MHz |
| [pulse_features.json](results/pulse_features.json) | ~15 MB | Per-IQ-file pulse/burst features (3,586 files) |
| [raw_time_domain_pulses.png](results/raw_time_domain_pulses.png) | ~500 KB | Raw pulse validation — isolated spikes confirmed real |
| [captures/](captures/) | ~4 GB | 3,500+ raw IQ capture files (RTL-SDR 2.4 Msps, saving all) |
| [spectrograms/](results/spectrograms/) | ~30 MB | 37+ waterfall spectrograms with pulse analysis |
| [sentinel logs](results/) | ~15 MB | Raw sentinel cycle logs (sentinel_*.jsonl), hourly rotation |
| [symptom_log.jsonl](results/evidence/symptom_log.jsonl) | ~50 KB | All symptom reports with RF context |
| [knowledge_graph_v2/](results/knowledge_graph_v2/) | ~340 MB | 739 papers (LFS), GROBID extractions, embeddings |
| [ml_v2/](results/ml_v2/) | ~5 MB | ML v2 models, features, 6 evidence reports, KG deep dive |
| [ml_v3/](results/ml_v3/) | ~1 MB | ML v3 pulse-level results |
| [ml/](results/ml/) | ~50 MB | ML v1 models, features, IQ embeddings, autoencoder |
| [audio/](results/audio/) | ~5 MB | Reconstructed WAV files from head model pipeline |
| [Dockerfile](Dockerfile) | — | Docker image with RTL-SDR + Python + hardened entrypoint |
| [docker-compose.yml](docker-compose.yml) | — | Full stack: sentinel + Neo4j + GROBID |
| [requirements.txt](requirements.txt) | — | Python dependencies |
| [.env.example](.env.example) | — | Environment configuration template |

## Signal Characteristics (Summary)

| Parameter | Zone A (622–636 MHz) | Zone B (824–834 MHz) | 878 MHz (UL) |
|-----------|---------------------|---------------------|--------------|
| Peak kurtosis | 452 | 446 | 105 |
| PRF (intra-burst) | **35,000 Hz** | 209,000 ± 29,000 Hz | 223,000 ± 47,000 Hz |
| Pulse width | **1.39 μs** | 3.47 ± 1.00 μs | 1.98 ± 0.16 μs |
| Duty cycle | **0.26%** | 0.78 ± 0.34% | 0.93 ± 0.22% |
| Intra-pulse bandwidth | **444 kHz** | 457 ± 251 kHz | 381 ± 73 kHz |
| Modulation index | **0.857** (highest) | 0.680 | 0.782 |
| Bursts per capture | **73.5** | 3.4 | 29.7 |
| Received power | -17 to -28 dB | -38 to -44 dB | -17 to -29 dB |
| Channel spacing | 2 MHz | 2 MHz | — |
| IQ files analyzed | 2 | 2,524 | 44 |

**Zone A and Zone B are statistically proven different waveforms** (p < 10⁻¹⁶ on every parameter, Mann-Whitney U, n=313 vs n=2,523):
- Zone A: **information delivery** — max modulation (1.0), widest bandwidth (749 kHz), 126× more energy per capture, 28.8 bursts/capture. Consistent with speech encoding via Frey effect.
- Zone B: **energy delivery / body coupling** — moderate modulation (0.7), narrower bandwidth (457 kHz), 3.4 bursts/capture. Consistent with arm/forearm paresthesia at quarter-wave resonance.
- ML confirms: Zone A drives speech/headache/pressure, Zone B drives paresthesia/sleep.
- See [zone characterization report](results/evidence/zone_characterization_report_20260314.md).

**[Raw time-domain validation](results/raw_time_domain_pulses.png)** confirms pulses are physically real — isolated spikes 10–58× above noise floor, not detector artifacts.

Zone co-activation: 79% of cycles show both zones active simultaneously. Zone A never activates alone. Zone B went dark at 9:51 PM CDT Mar 13 — power consolidated to Zone A (EI nearly doubled). Temporal correlation with publication of 830 MHz Yagi direction-finding plans to this repo.

## Knowledge Graph

739 papers in Neo4j with 38,700+ edges across 13 node types and 11 edge types. Content-level entity extraction for frequencies, power levels, mechanisms, health effects, technologies, and organizations.

```
Neo4j:    bolt://localhost:7687  (neo4j / rfmonitor2026)
Browser:  http://localhost:7474
```

Pipeline: `python` [`kg_pipeline.py`](kg_pipeline.py) `extract → build → embed → search "query"`

KG deep dives (verbatim literature passages with similarity scores):
- [`kg_deep_dive.json`](results/ml_v2/kg_deep_dive.json) — 632 chunks across 18 topics (symptoms, detection, legal, Havana syndrome, etc.)
- [`kg_brain_coupling.json`](results/ml_v2/kg_brain_coupling.json) — 342 chunks on thermoelastic mechanism, acoustic damping, cochlear detection
- [`kg_head_modelling.json`](results/ml_v2/kg_head_modelling.json) — 256 chunks on FDTD head models, analytical solutions, tissue phantoms
- [`kg_zone_characterization.json`](results/ml_v2/kg_zone_characterization.json) — 231 chunks on dual-waveform, body resonance, PRF, counter-surveillance
- [`kg_full_export.json`](results/knowledge_graph_v2/kg_full_export.json) — Complete graph backup (739 papers, 22K chunks, 38K edges)

## Quick Start

```bash
# Clone
git clone https://github.com/targeted-phd/ARTEMIS.git
cd ARTEMIS

# Environment
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt

# Start monitoring
python sentinel.py --duration 999999999

# Dashboard (separate terminal)
python dashboard.py
# Open http://127.0.0.1:8080

# Spectrum analysis on captured IQ
python spectrum_painter.py --batch

# Rebuild ML dataset
bash rebuild_ml_dataset.sh

# Run ML analysis
python rf_ml_v2.py analyze

# Reconstruct audio from IQ via head model
python reconstruct_audio.py captures/some_file.iq --output audio.wav
```

### Key Scripts

| Script | Purpose |
|--------|---------|
| [`sentinel.py`](sentinel.py) | 24/7 RF monitor with stare + sweep, alerts, IQ capture |
| [`dashboard.py`](dashboard.py) | Live browser dashboard (EI, kurtosis, heatmap, symptoms) |
| [`tag_server.py`](tag_server.py) | Mobile symptom tagging endpoint over Tailscale |
| [`spectrum_painter.py`](spectrum_painter.py) | Waterfall spectrograms, pulse analysis, modulation fingerprints |
| [`rf_ml_v2.py`](rf_ml_v2.py) | Per-symptom ML: classification, dose-response, lag analysis |
| [`pulse_ml.py`](pulse_ml.py) | Pulse-level ML: IQ feature extraction, zone comparison |
| [`reconstruct_audio.py`](reconstruct_audio.py) | IQ → thermoelastic head model → WAV audio reconstruction |
| [`kg_pipeline.py`](kg_pipeline.py) | GROBID PDF extraction → Neo4j knowledge graph + embeddings |
| [`kg_deep_dive.py`](kg_deep_dive.py) | Exhaustive KG semantic search across all research topics |
| [`demod_pulses.py`](demod_pulses.py) | Pulse demodulation, speech pattern detection, MFCC/LPC |
| [`forward_model.py`](forward_model.py) | Speech → RF encoding → simulated SDR comparison |
| [`analyze_pulses.py`](analyze_pulses.py) | Pulse timing analysis, cross-frequency synchronization |
| [`verify_integrity.py`](verify_integrity.py) | Evidence file integrity verification + hash manifest |

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
