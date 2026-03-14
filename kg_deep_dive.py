#!/usr/bin/env python3
"""Exhaustive KG search for ML findings — all 18 topics, 10 results each, full text."""
import json, requests, sys
from neo4j import GraphDatabase

DRIVER = GraphDatabase.driver("bolt://localhost:7687", auth=("neo4j", "rfmonitor2026"))
OLLAMA = "http://localhost:11434"

def embed(text):
    r = requests.post(f"{OLLAMA}/api/embeddings",
                      json={"model": "mxbai-embed-large", "prompt": text}, timeout=60)
    return r.json().get("embedding", [0]*1024)

def search(query, k=10):
    vec = embed(query)
    with DRIVER.session() as s:
        results = s.run("""
            CALL db.index.vector.queryNodes('chunk_embedding', $k, $vec)
            YIELD node, score
            MATCH (p:Paper)-[:HAS_CHUNK]->(node)
            RETURN p.title AS title, p.year AS year, node.text AS text, score
            ORDER BY score DESC LIMIT $k
        """, k=k, vec=vec).data()
    return results

QUERIES = {
    "1_speech_zone_b": [
        "microwave auditory effect speech encoding pulsed radiation hearing perception",
        "Frey effect speech intelligibility modulated microwave pulse",
        "830 MHz pulsed microwave auditory perception thermoelastic expansion",
        "voice to skull technology microwave hearing speech communication",
    ],
    "2_tinnitus_zone_a": [
        "tinnitus microwave RF exposure auditory perception ringing",
        "600 MHz bioeffects frequency dependent auditory nervous system",
        "electromagnetic tinnitus chronic exposure cochlear auditory nerve",
        "pulsed RF tinnitus perception mechanism frequency",
    ],
    "3_paresthesia_peripheral": [
        "paresthesia RF exposure peripheral nerve stimulation electromagnetic",
        "skin sensation tingling microwave radiation biological effect",
        "peripheral nerve electromagnetic stimulation cutaneous sensation",
        "RF induced paresthesia nerve conduction velocity extremities",
    ],
    "4_sleep_disruption": [
        "sleep disruption microwave RF exposure circadian rhythm",
        "melatonin suppression electromagnetic radiation sleep quality",
        "nocturnal RF exposure insomnia sleep architecture EEG",
        "directed energy sleep interference biological rhythm disruption",
    ],
    "5_headache_cumulative": [
        "headache cumulative RF exposure dose response microwave",
        "chronic microwave syndrome headache occupational exposure",
        "thermal dose RF headache power density duration",
        "radiofrequency headache mechanism intracranial pressure vasodilation",
    ],
    "6_pressure_nocturnal": [
        "intracranial pressure microwave RF exposure head pressure",
        "nocturnal symptoms electromagnetic exposure nighttime",
        "head pressure pulsed microwave thermoelastic mechanism",
        "cranial pressure RF radiation biological effect",
    ],
    "7_uplink_band_anomaly": [
        "cellular uplink band 824 849 MHz surveillance concealment",
        "spread spectrum signal disguise cellular frequency allocation",
        "anomalous RF signal cellular band unauthorized transmission",
        "800 MHz band signal concealment detection technique",
    ],
    "8_frequency_hopping": [
        "frequency hopping spread spectrum electronic warfare agile",
        "adaptive frequency targeting directed energy weapon",
        "frequency agile signal detection characterization",
        "hopping pattern analysis electronic countermeasure",
    ],
    "9_dual_band": [
        "multi frequency directed energy dual band exposure bioeffects",
        "frequency specific biological effects RF multiple frequencies",
        "simultaneous multi band RF exposure health effects",
        "dual frequency microwave interaction tissue biological",
    ],
    "10_pulse_width": [
        "pulse width microsecond microwave biological effect tissue absorption",
        "short pulse RF biological response pulse duration threshold",
        "pulse repetition frequency PRF biological effect microwave",
        "ultrashort pulse microwave thermoelastic tissue response",
    ],
    "11_diurnal_pattern": [
        "nocturnal electromagnetic exposure pattern nighttime targeting",
        "diurnal RF exposure variation sleep time monitoring surveillance",
        "nighttime directed energy activation pattern operational",
        "circadian vulnerability electromagnetic radiation exposure timing",
    ],
    "12_body_resonance": [
        "body resonance frequency RF antenna human limb absorption",
        "half wave dipole resonance 830 MHz forearm biological antenna",
        "specific absorption rate SAR body part frequency dependent",
        "limb resonance electromagnetic field coupling tissue",
    ],
    "13_detection_methods": [
        "RF signal detection measurement technique spectrum analysis monitoring",
        "pulsed microwave detection kurtosis statistical anomaly method",
        "directed energy weapon detection identification countermeasure",
        "electromagnetic surveillance detection technical sweep equipment",
    ],
    "14_legal_regulatory": [
        "RF harassment legal framework regulatory protection electromagnetic",
        "FCC complaint unauthorized RF transmission enforcement",
        "electromagnetic weapon regulation international law prohibition",
        "RF exposure limits safety standards protection guidelines",
    ],
    "15_prior_cases": [
        "anomalous health incidents Havana syndrome embassy directed energy",
        "documented cases RF exposure health effects occupational military",
        "microwave weapon deployment documented incident report",
        "electromagnetic attack case study evidence investigation",
    ],
    "16_power_thresholds": [
        "power density threshold biological effect symptom onset microwave",
        "SAR specific absorption rate threshold health effect frequency",
        "minimum power microwave auditory effect Frey threshold",
        "RF exposure level symptom correlation dose power density",
    ],
    "17_concealment_techniques": [
        "spread spectrum concealment technique RF signal hiding",
        "silent sound spread spectrum SSSS covert communication",
        "low probability intercept signal design surveillance",
        "signal masking cellular band concealment technique",
    ],
    "18_ew_characteristics": [
        "electronic warfare signal characteristics modulation pattern",
        "directed energy weapon waveform pulse structure signature",
        "military RF weapon signal parameters frequency power",
        "non lethal weapon microwave signal specification operational",
    ],
}

results = {}
total = sum(len(v) for v in QUERIES.values())
done = 0

for topic, queries in QUERIES.items():
    print(f"\n{'='*60}")
    print(f"  TOPIC: {topic}")
    print(f"{'='*60}")
    topic_results = []
    seen_texts = set()

    for q in queries:
        done += 1
        print(f"  [{done}/{total}] {q[:60]}...")
        try:
            hits = search(q, k=10)
            for h in hits:
                # Deduplicate by text prefix
                key = (h.get("text", "")[:100], h.get("title", ""))
                if key not in seen_texts:
                    seen_texts.add(key)
                    topic_results.append({
                        "query": q,
                        "title": h.get("title", ""),
                        "year": h.get("year"),
                        "text": h.get("text", ""),
                        "score": round(float(h.get("score", 0)), 4),
                    })
                    if h.get("score", 0) > 0.85:
                        print(f"    [{h['score']:.3f}] {h['title'][:55]}")
        except Exception as e:
            print(f"    ERROR: {e}")

    results[topic] = topic_results
    print(f"  -> {len(topic_results)} unique chunks")

# Save
outpath = "results/ml_v2/kg_deep_dive.json"
with open(outpath, "w") as f:
    json.dump(results, f, indent=2, default=str)

total_chunks = sum(len(v) for v in results.values())
print(f"\n{'='*60}")
print(f"  KG DEEP DIVE COMPLETE")
print(f"  {total_chunks} unique chunks across {len(results)} topics")
print(f"  Saved to {outpath}")
print(f"{'='*60}")

DRIVER.close()
