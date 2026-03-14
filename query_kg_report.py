#!/usr/bin/env python3
"""Query Neo4j KG for all evidence relevant to the hypothesis report."""

import json
import sys
from neo4j import GraphDatabase

NEO4J_URL = "bolt://localhost:7687"
NEO4J_AUTH = ("neo4j", "rfmonitor2026")

driver = GraphDatabase.driver(NEO4J_URL, auth=NEO4J_AUTH)

results = {}

def run_query(name, cypher, **params):
    """Run a Cypher query and store results."""
    try:
        with driver.session() as session:
            data = session.run(cypher, **params).data()
            results[name] = data
            print(f"  {name}: {len(data)} results")
            return data
    except Exception as e:
        print(f"  {name}: ERROR - {e}")
        results[name] = []
        return []

# ── 0. Schema overview ──
print("=== SCHEMA ===")
run_query("node_labels", "CALL db.labels() YIELD label RETURN label ORDER BY label")
run_query("rel_types", "CALL db.relationshipTypes() YIELD relationshipType RETURN relationshipType ORDER BY relationshipType")
run_query("node_counts", """
    CALL db.labels() YIELD label
    CALL apoc.cypher.run('MATCH (n:' + label + ') RETURN count(n) as cnt', {}) YIELD value
    RETURN label, value.cnt as count
""")

# Try simpler count approach if apoc not available
run_query("paper_count", "MATCH (p:Paper) RETURN count(p) as count")
run_query("author_count", "MATCH (a:Author) RETURN count(a) as count")
run_query("chunk_count", "MATCH (c:Chunk) RETURN count(c) as count")

# ── 1. Microwave auditory effect / Frey effect papers ──
print("\n=== MICROWAVE AUDITORY / FREY EFFECT ===")
run_query("frey_fulltext", """
    CALL db.index.fulltext.queryNodes('paper_search', 'microwave auditory effect OR Frey effect OR RF hearing OR microwave hearing')
    YIELD node, score
    RETURN node.title as title, node.year as year, node.abstract as abstract, node.pdf_name as pdf, score
    ORDER BY score DESC
    LIMIT 40
""")

run_query("frey_title", """
    MATCH (p:Paper)
    WHERE toLower(p.title) CONTAINS 'microwave' AND (
        toLower(p.title) CONTAINS 'auditory' OR
        toLower(p.title) CONTAINS 'hearing' OR
        toLower(p.title) CONTAINS 'frey' OR
        toLower(p.title) CONTAINS 'rf hearing'
    )
    RETURN p.title as title, p.year as year, p.abstract as abstract, p.pdf_name as pdf
    ORDER BY p.year
""")

run_query("thermoelastic", """
    CALL db.index.fulltext.queryNodes('paper_search', 'thermoelastic expansion cochlea skull bone conduction microwave')
    YIELD node, score
    RETURN node.title as title, node.year as year, node.abstract as abstract, score
    ORDER BY score DESC
    LIMIT 20
""")

# ── 2. Directed energy weapons ──
print("\n=== DIRECTED ENERGY WEAPONS ===")
run_query("dew_papers", """
    CALL db.index.fulltext.queryNodes('paper_search', 'directed energy weapon OR DEW OR non-lethal weapon OR active denial')
    YIELD node, score
    RETURN node.title as title, node.year as year, node.abstract as abstract, score
    ORDER BY score DESC
    LIMIT 30
""")

run_query("medusa_v2k", """
    CALL db.index.fulltext.queryNodes('paper_search', 'MEDUSA OR voice skull OR V2K OR silent audio OR sonic weapon')
    YIELD node, score
    RETURN node.title as title, node.year as year, node.abstract as abstract, score
    ORDER BY score DESC
    LIMIT 20
""")

# ── 3. Specific frequencies near 622 and 826 MHz ──
print("\n=== FREQUENCY-SPECIFIC ===")
run_query("freq_622_826", """
    CALL db.index.fulltext.queryNodes('paper_search', '622 MHz OR 626 MHz OR 630 MHz OR 826 MHz OR 828 MHz OR 830 MHz OR 832 MHz OR 834 MHz OR UHF microwave')
    YIELD node, score
    RETURN node.title as title, node.year as year, node.abstract as abstract, score
    ORDER BY score DESC
    LIMIT 20
""")

run_query("uhf_frequency", """
    CALL db.index.fulltext.queryNodes('paper_search', 'UHF frequency 200 MHz OR 400 MHz OR 600 MHz OR 800 MHz OR 900 MHz OR 1 GHz pulsed')
    YIELD node, score
    RETURN node.title as title, node.year as year, node.abstract as abstract, score
    ORDER BY score DESC
    LIMIT 30
""")

# ── 4. Pulse modulation / encoding for microwave hearing ──
print("\n=== PULSE MODULATION / ENCODING ===")
run_query("pulse_modulation", """
    CALL db.index.fulltext.queryNodes('paper_search', 'pulse modulation microwave OR pulsed microwave OR pulse width OR pulse repetition frequency')
    YIELD node, score
    RETURN node.title as title, node.year as year, node.abstract as abstract, score
    ORDER BY score DESC
    LIMIT 30
""")

run_query("speech_encoding", """
    CALL db.index.fulltext.queryNodes('paper_search', 'speech encoding microwave OR voice modulation OR audio modulation microwave OR intelligible speech')
    YIELD node, score
    RETURN node.title as title, node.year as year, node.abstract as abstract, score
    ORDER BY score DESC
    LIMIT 20
""")

# ── 5. Health effects ──
print("\n=== HEALTH EFFECTS ===")
run_query("headache_tinnitus", """
    CALL db.index.fulltext.queryNodes('paper_search', 'headache OR tinnitus OR paresthesia OR microwave syndrome OR radiofrequency health effect')
    YIELD node, score
    RETURN node.title as title, node.year as year, node.abstract as abstract, score
    ORDER BY score DESC
    LIMIT 30
""")

run_query("havana_syndrome", """
    CALL db.index.fulltext.queryNodes('paper_search', 'Havana syndrome OR anomalous health incident OR embassy OR diplomats')
    YIELD node, score
    RETURN node.title as title, node.year as year, node.abstract as abstract, score
    ORDER BY score DESC
    LIMIT 20
""")

run_query("sar_dosimetry", """
    CALL db.index.fulltext.queryNodes('paper_search', 'SAR specific absorption rate OR dosimetry OR power density threshold OR exposure limit')
    YIELD node, score
    RETURN node.title as title, node.year as year, node.abstract as abstract, score
    ORDER BY score DESC
    LIMIT 30
""")

run_query("biological_effects", """
    CALL db.index.fulltext.queryNodes('paper_search', 'biological effect microwave OR RF bioeffect OR neural effect OR blood brain barrier')
    YIELD node, score
    RETURN node.title as title, node.year as year, node.abstract as abstract, score
    ORDER BY score DESC
    LIMIT 30
""")

# ── 6. Detection / measurement methods ──
print("\n=== DETECTION / MEASUREMENT ===")
run_query("detection_methods", """
    CALL db.index.fulltext.queryNodes('paper_search', 'RF measurement OR direction finding OR spectrum monitoring OR signal detection pulsed')
    YIELD node, score
    RETURN node.title as title, node.year as year, node.abstract as abstract, score
    ORDER BY score DESC
    LIMIT 20
""")

run_query("sdr_usrp", """
    CALL db.index.fulltext.queryNodes('paper_search', 'USRP OR software defined radio OR SDR OR RTL-SDR OR signal generator')
    YIELD node, score
    RETURN node.title as title, node.year as year, node.abstract as abstract, score
    ORDER BY score DESC
    LIMIT 20
""")

# ── 7. Shielding / countermeasures ──
print("\n=== COUNTERMEASURES / SHIELDING ===")
run_query("shielding", """
    CALL db.index.fulltext.queryNodes('paper_search', 'shielding effectiveness OR electromagnetic shielding OR RF protection OR Faraday OR countermeasure')
    YIELD node, score
    RETURN node.title as title, node.year as year, node.abstract as abstract, score
    ORDER BY score DESC
    LIMIT 20
""")

# ── 8. Historical programs ──
print("\n=== HISTORICAL PROGRAMS ===")
run_query("historical", """
    CALL db.index.fulltext.queryNodes('paper_search', 'MKULTRA OR Pandora project OR Moscow signal OR military research microwave OR DARPA')
    YIELD node, score
    RETURN node.title as title, node.year as year, node.abstract as abstract, score
    ORDER BY score DESC
    LIMIT 20
""")

# ── 9. Key authors and institutions ──
print("\n=== KEY AUTHORS ===")
run_query("prolific_authors", """
    MATCH (a:Author)-[:AUTHORED]->(p:Paper)
    WITH a, count(p) as paper_count, collect(p.title) as titles
    WHERE paper_count >= 3
    RETURN a.name as name, paper_count, titles
    ORDER BY paper_count DESC
    LIMIT 50
""")

run_query("institutions", """
    MATCH (i:Institution)<-[:AFFILIATED_WITH]-(a:Author)-[:AUTHORED]->(p:Paper)
    WITH i, count(DISTINCT p) as paper_count, collect(DISTINCT a.name) as authors
    WHERE paper_count >= 2
    RETURN i.name as institution, paper_count, authors
    ORDER BY paper_count DESC
    LIMIT 40
""")

# ── 10. Specific key authors in the field ──
print("\n=== SPECIFIC AUTHORS ===")
for author_name in ['Frey', 'Lin', 'Guy', 'Chou', 'Foster', 'Elder', 'Watanabe', 'Adair']:
    run_query(f"author_{author_name}", f"""
        MATCH (a:Author)-[:AUTHORED]->(p:Paper)
        WHERE toLower(a.name) CONTAINS toLower('{author_name}')
        RETURN a.name as name, p.title as title, p.year as year, p.abstract as abstract
        ORDER BY p.year
    """)

# ── 11. Cross-reference: papers on BOTH mechanism AND health effects ──
print("\n=== CROSS-REFERENCES ===")
run_query("mechanism_health_cross", """
    CALL db.index.fulltext.queryNodes('paper_search', 'microwave auditory thermoelastic pulsed RF hearing')
    YIELD node, score
    WITH node as p, score
    WHERE toLower(p.abstract) CONTAINS 'health' OR
          toLower(p.abstract) CONTAINS 'headache' OR
          toLower(p.abstract) CONTAINS 'tinnitus' OR
          toLower(p.abstract) CONTAINS 'safety' OR
          toLower(p.abstract) CONTAINS 'threshold'
    RETURN p.title as title, p.year as year, p.abstract as abstract, score
    ORDER BY score DESC
    LIMIT 20
""")

# ── 12. Deep chunk search for specific parameters ──
print("\n=== CHUNK-LEVEL DEEP SEARCH ===")

# Search for specific numerical parameters in body text
for search_term in [
    'microsecond pulse width microwave auditory',
    'power density threshold auditory perception mW',
    'pulse repetition frequency hearing effect',
    'thermoelastic mechanism cochlea',
    'MEDUSA mob excess deterrent',
    'voice to skull V2K',
    'Havana syndrome pulsed microwave',
    'shielding effectiveness 800 MHz',
    'Frey effect threshold',
    'specific absorption rate head brain SAR'
]:
    run_query(f"chunk_{search_term[:30]}", f"""
        CALL db.index.fulltext.queryNodes('paper_search', '{search_term}')
        YIELD node, score
        WHERE score > 1.0
        RETURN node.title as title, node.year as year,
               left(node.body_text, 3000) as body_excerpt, score
        ORDER BY score DESC
        LIMIT 5
    """)

# ── 13. Papers with body text mentioning specific frequencies ──
print("\n=== BODY TEXT FREQUENCY MENTIONS ===")
run_query("body_915mhz", """
    MATCH (p:Paper)
    WHERE p.body_text CONTAINS '915 MHz' OR p.body_text CONTAINS '915MHz'
    RETURN p.title as title, p.year as year, p.abstract as abstract
""")

run_query("body_2450mhz", """
    MATCH (p:Paper)
    WHERE p.body_text CONTAINS '2450 MHz' OR p.body_text CONTAINS '2.45 GHz'
    RETURN p.title as title, p.year as year, p.abstract as abstract
""")

run_query("body_pulsed_params", """
    MATCH (p:Paper)
    WHERE (p.body_text CONTAINS 'pulse width' OR p.body_text CONTAINS 'pulse duration')
    AND (p.body_text CONTAINS 'microwave' OR p.body_text CONTAINS 'RF')
    AND (p.body_text CONTAINS 'auditory' OR p.body_text CONTAINS 'hearing' OR p.body_text CONTAINS 'Frey')
    RETURN p.title as title, p.year as year, p.abstract as abstract,
           left(p.body_text, 5000) as body_excerpt
""")

# ── 14. Foster 2021 and other key papers ──
print("\n=== KEY PAPERS ===")
run_query("foster_paper", """
    MATCH (p:Paper)
    WHERE toLower(p.title) CONTAINS 'foster' OR
          (p.year >= 2020 AND p.year <= 2022 AND toLower(p.abstract) CONTAINS 'microwave' AND toLower(p.abstract) CONTAINS 'auditory')
    RETURN p.title as title, p.year as year, p.abstract as abstract
""")

run_query("chou_guy", """
    MATCH (p:Paper)
    WHERE (toLower(p.title) CONTAINS 'chou' AND toLower(p.title) CONTAINS 'guy') OR
          (p.year = 1979 AND toLower(p.abstract) CONTAINS 'microwave' AND toLower(p.abstract) CONTAINS 'auditory')
    RETURN p.title as title, p.year as year, p.abstract as abstract
""")

# ── 15. Entity nodes if they exist ──
print("\n=== ENTITIES ===")
run_query("entity_labels", """
    MATCH (p:Paper)-[:MENTIONS]->(e)
    WITH labels(e) as types, e.name as name, count(p) as papers
    RETURN types, name, papers
    ORDER BY papers DESC
    LIMIT 50
""")

# ── 16. Co-citation clusters ──
print("\n=== CO-CITATION CLUSTERS ===")
run_query("cocitation", """
    MATCH (p1:Paper)-[c:CO_CITES]->(p2:Paper)
    WHERE c.shared_refs >= 3
    RETURN p1.title as paper1, p2.title as paper2, c.shared_refs as shared_refs
    ORDER BY c.shared_refs DESC
    LIMIT 30
""")

# ── 17. Internal citations ──
print("\n=== INTERNAL CITATION NETWORK ===")
run_query("internal_cites", """
    MATCH (p1:Paper)-[:CITES_INTERNAL]->(p2:Paper)
    RETURN p1.title as citing, p1.year as citing_year,
           p2.title as cited, p2.year as cited_year
    ORDER BY p2.year
    LIMIT 50
""")

# ── 18. Specific body text searches for parameters ──
print("\n=== PARAMETER EXTRACTION ===")
run_query("power_density_values", """
    MATCH (p:Paper)
    WHERE (p.body_text CONTAINS 'mW/cm' OR p.body_text CONTAINS 'W/m' OR p.body_text CONTAINS 'power density')
    AND (p.body_text CONTAINS 'auditory' OR p.body_text CONTAINS 'hearing' OR p.body_text CONTAINS 'threshold')
    RETURN p.title as title, p.year as year, p.abstract as abstract,
           left(p.body_text, 8000) as body_excerpt
    LIMIT 15
""")

run_query("pulse_params_body", """
    MATCH (p:Paper)
    WHERE p.body_text CONTAINS 'microsecond' OR p.body_text CONTAINS 'μs'
    AND (p.body_text CONTAINS 'auditory' OR p.body_text CONTAINS 'hearing')
    RETURN p.title as title, p.year as year, p.abstract as abstract
""")

# ── 19. Lin's papers specifically (key researcher) ──
print("\n=== LIN PAPERS ===")
run_query("lin_papers_all", """
    MATCH (a:Author)-[:AUTHORED]->(p:Paper)
    WHERE toLower(a.name) CONTAINS 'lin' AND
          (toLower(p.title) CONTAINS 'microwave' OR toLower(p.abstract) CONTAINS 'microwave' OR
           toLower(p.title) CONTAINS 'electromagnetic' OR toLower(p.abstract) CONTAINS 'electromagnetic')
    RETURN a.name as author, p.title as title, p.year as year, p.abstract as abstract
    ORDER BY p.year
""")

# ── 20. References that are cited most often ──
print("\n=== MOST CITED REFERENCES ===")
run_query("most_cited_refs", """
    MATCH (p:Paper)-[:CITES]->(r:Reference)
    WITH r, count(p) as citations, collect(p.title) as citing_papers
    WHERE citations >= 3
    RETURN r.title as reference, r.year as year, citations, citing_papers
    ORDER BY citations DESC
    LIMIT 30
""")

# ── 21. Papers specifically on Maxwell stress / radiation force ──
print("\n=== MECHANISM SPECIFIC ===")
run_query("maxwell_stress", """
    CALL db.index.fulltext.queryNodes('paper_search', 'Maxwell stress OR radiation pressure OR field-induced force OR dielectric interface')
    YIELD node, score
    RETURN node.title as title, node.year as year, node.abstract as abstract, score
    ORDER BY score DESC
    LIMIT 10
""")

run_query("bone_conduction", """
    CALL db.index.fulltext.queryNodes('paper_search', 'bone conduction OR skull vibration OR cochlear response OR auditory brainstem')
    YIELD node, score
    RETURN node.title as title, node.year as year, node.abstract as abstract, score
    ORDER BY score DESC
    LIMIT 15
""")

# ── 22. Keyword/Topic analysis ──
print("\n=== TOPICS ===")
run_query("topics", """
    MATCH (t:Topic)<-[:TAGGED]-(p:Paper)
    WITH t, count(p) as papers
    RETURN t.name as topic, papers
    ORDER BY papers DESC
    LIMIT 50
""")

# ── Save all results ──
output_path = "results/evidence/kg_query_results.json"
with open(output_path, "w") as f:
    json.dump(results, f, indent=2, default=str)

print(f"\n=== DONE: {len(results)} queries, results saved to {output_path} ===")
driver.close()
