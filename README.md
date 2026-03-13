# RF Monitor

Forensic RF signal analysis toolkit for investigating anomalous pulsed signals in the cellular band. Uses statistical detection methods that reveal low-duty-cycle pulses invisible to conventional spectrum analyzers, backed by a knowledge graph of 739 academic papers spanning RF dosimetry, microwave auditory effect, acoustics, neuroscience, directed energy, and signal processing.

## Project Phases

### Phase 1: SDR Signal Collection & Detection (Complete)
Basic signal detection with RTL-SDR Blog V4 and whip antenna. Kurtosis-based pulse detection, 24h sentinel monitoring, cross-frequency correlation, and LTE comparison analysis.

### Phase 2: Knowledge Graph (Complete)
739 academic papers, books, and reports extracted and loaded into a Neo4j knowledge graph with 38,700+ edges. Three-tier extraction pipeline: GROBID (structured metadata), PyMuPDF (fallback text), Tesseract OCR (scanned documents). Content-level entity extraction identifies frequencies, power levels, mechanisms, health effects, technologies, and organizations mentioned in each paper. Cleaned dataset (`papers_grobid_clean.json`) with manual per-paper review: structured `body_sections`, recovered metadata via GROBID re-extraction of 251 fallback papers, quality scoring (mean 0.88), and schema normalization across all 739 records.

### Phase 3: Signal Correlation & Encoding Analysis (Next)
Forward modeling pipeline: known speech → encoding transforms → simulated RTL-SDR capture → compare with real observations. Tests four published encoding methods from the literature:
- AM envelope (pulse amplitude = speech waveform)
- PRF modulation (pulse rate = audio frequency)
- Lin/MEDUSA time-derivative (perceived sound ∝ dP/dt)
- Full thermoelastic inverse (desired acoustic pressure → required SAR)

### Phase 4+: Hardware Expansion (Future)
- Directional antenna + LNA for improved sensitivity
- GPS-tagged portable monitoring for spatial mapping
- Infrasound/ultrasound microphone array
- Higher-bandwidth SDR (HackRF/USRP, ~100 MSPS to resolve individual µs pulses)
- Real-time classification pipeline

## Knowledge Graph

### Stats
| Metric | Count |
|--------|-------|
| Papers/books/reports | 739 |
| Authors | 1,502 |
| Cited references | 14,953 |
| Institutions | 444 |
| Content entities | 1,682 |
| Total edges | 38,721 |

### Node Types
- **Paper** — title, authors, abstract, full body text, year, DOI, sections, figures, quality_score, extraction_method, quality_flags
- **Author** — name, email
- **Institution** — affiliation name
- **Reference** — cited work (title, journal, year, DOI)
- **Topic** — category classification (9 topics) + keyword tags
- **Frequency** — specific frequencies mentioned (e.g., "915 MHz", "2.45 GHz")
- **Power** — power/SAR levels (e.g., "1.6 kW/kg", "10 mW/cm²")
- **Mechanism** — physical mechanisms (thermoelastic expansion, Frey effect, bone conduction, etc.)
- **HealthEffect** — health outcomes (hearing loss, tinnitus, Havana syndrome, BBB disruption, etc.)
- **Technology** — devices/systems (FDTD, phased array, V2K, MEDUSA, RTL-SDR, etc.)
- **Organization** — agencies (DARPA, ICNIRP, FCC, NATO, etc.)
- **Tissue** — biological targets (brain tissue, cochlea, skull bone, etc.)
- **Modulation** — signal types (pulse modulation, AM envelope, UWB, frequency hopping, etc.)

### Edge Types
| Edge | Meaning | Count |
|------|---------|-------|
| CITES | Paper → Reference | 15,767 |
| SHARED_ENTITIES | Papers sharing 3+ content entities | 7,740 |
| MENTIONS | Paper → content entity | 6,431 |
| HAS_FIGURE | Paper → figure caption | 3,561 |
| AUTHORED | Author → Paper | 1,643 |
| TAGGED | Paper → keyword topic | 1,160 |
| AFFILIATED_WITH | Author → Institution | 1,032 |
| IN_TOPIC | Paper → category topic | 865 |
| SHARED_AUTHOR | Papers by same author | 230 |
| CO_CITES | Papers citing 2+ same refs | 201 |
| CITES_INTERNAL | Paper → Paper (in-collection citation) | 91 |

### Topic Distribution
| Topic | Papers |
|-------|--------|
| Acoustics / infrasound / ultrasound | 160 |
| Weapons / surveillance / DEW | 69 |
| Medical / clinical / health effects | 62 |
| Signal processing / UWB / modulation | 55 |
| Neuroscience / brain stimulation | 52 |
| RF dosimetry / SAR / FDTD | 50 |
| Microwave auditory effect / Frey | 22 |
| Electromagnetic theory / propagation | 16 |
| Other | 379 |

### Neo4j Connection
```
URL:      bolt://localhost:7687
Browser:  http://localhost:7474
User:     neo4j
Password: rfmonitor2026
```

### Example Cypher Queries

```cypher
-- Find all papers about the microwave auditory effect
MATCH (p:Paper)-[:IN_TOPIC]->(t:Topic {name: 'microwave_auditory'})
RETURN p.title, p.year, p.quality_score ORDER BY p.year

-- Find high-quality papers only (score >= 0.8)
MATCH (p:Paper) WHERE p.quality_score >= 0.8
RETURN p.title, p.year, p.quality_score, p.extraction_method
ORDER BY p.quality_score DESC LIMIT 20

-- Find papers mentioning a specific frequency
MATCH (p:Paper)-[:MENTIONS]->(f:Frequency {name: '915 MHz'})
RETURN p.title, p.year

-- Find health effects connected to RF dosimetry papers
MATCH (p:Paper)-[:IN_TOPIC]->(t:Topic {name: 'rf_dosimetry'})
MATCH (p)-[:MENTIONS]->(h:HealthEffect)
RETURN h.name, count(p) as papers ORDER BY papers DESC

-- Find papers that share the most content entities
MATCH (p1:Paper)-[s:SHARED_ENTITIES]->(p2:Paper)
RETURN p1.title, p2.title, s.count ORDER BY s.count DESC LIMIT 20

-- Find the citation network around a specific author
MATCH (a:Author {name: 'James Lin'})-[:AUTHORED]->(p:Paper)-[:CITES]->(r:Reference)
RETURN p.title, collect(r.title) as citations

-- Which mechanisms are discussed alongside which health effects?
MATCH (p:Paper)-[:MENTIONS]->(m:Mechanism)
MATCH (p)-[:MENTIONS]->(h:HealthEffect)
RETURN m.name, h.name, count(p) as papers ORDER BY papers DESC

-- Find all papers about a specific technology
MATCH (p:Paper)-[:MENTIONS]->(tech:Technology {name: 'directed energy weapon'})
RETURN p.title, p.year, p.abstract ORDER BY p.year

-- Full-text search across all papers
CALL db.index.fulltext.queryNodes('paper_search', 'thermoelastic cochlea')
YIELD node, score
RETURN node.title, score ORDER BY score DESC LIMIT 10
```

## Architecture

```
Phase 1 — Signal Detection
  pulse_detector.py      Calibrated band scanner — two-pass (baseline + detect)
  sentinel.py            24h hardened stare + sweep monitor with migration detection
  pulse_monitor.py       Single-freq watch + cross-band correlator
  demod_pulses.py        Pulse demodulation & speech pattern detection
  analyze_scan.py        Within-band anomaly detection
  analyze_pulses.py      Pulse timing: PRIs, width distributions, cross-freq sync
  plot_timeseries.py     Time-series visualization
  generate_report.py     Comprehensive text report with LTE comparison
  known_bands.py         US RF allocation database (400-1766 MHz)

Phase 2 — Knowledge Graph
  kg_pipeline.py         Main pipeline: extract → build → embed
                           GROBID for metadata, PyMuPDF fallback, Tesseract OCR
                           Content entity extraction (freq, power, mechanisms, etc.)
                           Neo4j graph population with 11 edge types
                           Section-aware chunking from body_sections
                           Prefers papers_grobid_clean.json (normalized dataset)

Phase 3 — Forward Model
  forward_model.py       Speech → encoding → simulated SDR → compare with real data
```

## Quick Start

```bash
# Environment
python -m venv .venv && source .venv/bin/activate
pip install numpy scipy matplotlib pymupdf grobid-client-python neo4j pytesseract requests

# Docker services
docker run -d --name grobid -p 8070:8070 -e JAVA_OPTS="-Xms4g -Xmx12g" --memory=16g lfoppiano/grobid:0.8.2
docker run -d --name neo4j -p 7474:7474 -p 7687:7687 -e NEO4J_AUTH=neo4j/rfmonitor2026 neo4j:community
docker run -d --name ollama -p 11434:11434 ollama/ollama
docker exec ollama ollama pull nomic-embed-text

# Phase 1 — Signal collection
python sentinel.py --targets 826,828,830,832,834,878 --duration 86400

# Phase 1 — Analysis
python demod_pulses.py batch --top 100 --concat 5
python forward_model.py test

# Phase 2 — Knowledge graph (full pipeline)
python kg_pipeline.py extract    # GROBID + PyMuPDF fallback + OCR → papers_grobid.json
python kg_pipeline.py build      # Populate Neo4j (uses papers_grobid_clean.json if present)
python kg_pipeline.py embed      # Generate embeddings via Ollama (section-aware chunking)
python kg_pipeline.py status     # Check pipeline status
# Then open http://localhost:7474 for Neo4j Browser
```

## Detection Method

Standard spectrum analyzers average power over time, burying low-duty-cycle pulses. A 10 µs pulse in a 10s integration window is attenuated by -60 dB — invisible.

This toolkit captures raw IQ and computes:
- **Kurtosis**: Gaussian noise ≈ 3.0 (RTL-SDR baseline ~8-10 due to 8-bit ADC). Impulsive signals push higher.
- **PAPR**: Peak-to-average power ratio. Gaussian ≈ 10-12 dB. Pulses push higher.
- **Spectral flatness**: 1.0 = white noise. Tonal/narrowband content reduces it.

Two-pass calibration establishes per-band baseline statistics, then flags channels that deviate using robust median + MAD estimators.

## Hardware

- RTL-SDR Blog V4 (R828D tuner, 24 MHz - 1.766 GHz)
- Whip antenna (included with SDR)
- Ubuntu on WSL2

## Key Findings

- **826-834 MHz uplink cluster**: Consistent POSSIBLE SPEECH scores (0.59-0.64) across all channels, high modulation ratios, formant-like structure, but no pitch — uniform signature argues against speech, likely protocol feature
- **878 MHz downlink**: Different behavior — 5-10x more bursts, lower scores, consistent with LTE downlink patterns
- **Forward model**: Lin/MEDUSA encoding ranked #1 (0.878 similarity to real data), confirming it produces the closest match to observed signal characteristics
- **Knowledge graph**: 739 papers processed into 38,700+ edge graph with content-level entity extraction across 9 topic domains
