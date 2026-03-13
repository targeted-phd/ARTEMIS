#!/usr/bin/env python3
"""
Knowledge Graph Pipeline — GROBID + Docling + Neo4j + Ollama

Processes academic PDFs through industrial-grade extraction, builds a rich
knowledge graph in Neo4j, and generates vector embeddings for semantic search.

Services required (all Docker):
  docker run -d --name grobid  -p 8070:8070 lfoppiano/grobid:0.8.2
  docker run -d --name neo4j   -p 7474:7474 -p 7687:7687 -e NEO4J_AUTH=neo4j/rfmonitor2026 neo4j:community
  docker run -d --name ollama  -p 11434:11434 ollama/ollama
  docker exec ollama ollama pull nomic-embed-text

Usage:
  python kg_pipeline.py extract [--limit N]     # GROBID + Docling on PDFs
  python kg_pipeline.py build                   # Populate Neo4j from extractions
  python kg_pipeline.py embed                   # Generate embeddings via Ollama (3 tiers)
  python kg_pipeline.py search "query"          # Semantic search across knowledge graph
  python kg_pipeline.py status                  # Show pipeline status
  python kg_pipeline.py all [--limit N]         # Full pipeline
"""

import os
import sys
import json
import re
import glob
import time
import argparse
import hashlib
import xml.etree.ElementTree as ET
from pathlib import Path
from datetime import datetime
from concurrent.futures import ThreadPoolExecutor, as_completed

import requests

# ─── Config ───────────────────────────────────────────────────────────────────

PDF_ROOT = "/home/tyler/projects/targeted-knowledge-graph"
OUTPUT_DIR = "results/knowledge_graph_v2"
GROBID_URL = "http://localhost:8070"
NEO4J_URL = "bolt://localhost:7687"
NEO4J_AUTH = ("neo4j", "rfmonitor2026")
OLLAMA_URL = "http://localhost:11434"
# Embedding model priority: qwen3-embedding (2048d) > mxbai-embed-large (1024d) > nomic-embed-text (768d)
EMBED_MODEL = "mxbai-embed-large"     # Upgrade to qwen3-embedding when available
EMBED_DIM = 1024                       # Must match model output dimensions
CHUNK_SIZE = 2000                      # Characters per chunk for Tier 2
CHUNK_OVERLAP = 500                    # Overlap between chunks

TEI_NS = {"tei": "http://www.tei-c.org/ns/1.0"}

os.makedirs(OUTPUT_DIR, exist_ok=True)
os.makedirs(f"{OUTPUT_DIR}/grobid", exist_ok=True)
os.makedirs(f"{OUTPUT_DIR}/docling", exist_ok=True)
os.makedirs(f"{OUTPUT_DIR}/embeddings", exist_ok=True)


# ─── Helpers ──────────────────────────────────────────────────────────────────

def find_all_pdfs():
    """Find all PDFs under PDF_ROOT, sorted by size (smallest first for fast progress)."""
    pdfs = glob.glob(f"{PDF_ROOT}/**/*.pdf", recursive=True)
    pdfs += glob.glob(f"{PDF_ROOT}/*.pdf")
    # Dedup by filename
    seen = {}
    for p in pdfs:
        name = os.path.basename(p)
        if name not in seen:
            seen[name] = p
    # Sort by size (small first — process fast ones first, big ones last)
    result = sorted(seen.values(), key=lambda p: os.path.getsize(p))
    return result


def timeout_for_pdf(pdf_path):
    """Scale GROBID timeout by file size: 60s base + 60s per 10MB."""
    size_mb = os.path.getsize(pdf_path) / 1e6
    return int(60 + (size_mb / 10) * 60)


def pdf_id(path):
    """Stable ID for a PDF based on filename."""
    name = os.path.basename(path)
    return hashlib.md5(name.encode()).hexdigest()[:12]


def check_services():
    """Verify all Docker services are running."""
    status = {}
    try:
        r = requests.get(f"{GROBID_URL}/api/isalive", timeout=5)
        status["grobid"] = r.text.strip() == "true"
    except Exception:
        status["grobid"] = False

    try:
        r = requests.get(f"{OLLAMA_URL}/api/tags", timeout=5)
        models = [m["name"] for m in r.json().get("models", [])]
        status["ollama"] = EMBED_MODEL in " ".join(models)
    except Exception:
        status["ollama"] = False

    try:
        from neo4j import GraphDatabase
        driver = GraphDatabase.driver(NEO4J_URL, auth=NEO4J_AUTH)
        driver.verify_connectivity()
        driver.close()
        status["neo4j"] = True
    except Exception:
        status["neo4j"] = False

    return status


# ─── GROBID Extraction ───────────────────────────────────────────────────────

def extract_grobid(pdf_path, retries=3):
    """Extract structured metadata from a PDF via GROBID."""
    pid = pdf_id(pdf_path)
    out_path = f"{OUTPUT_DIR}/grobid/{pid}.json"

    if os.path.exists(out_path):
        with open(out_path) as f:
            return json.load(f)

    pdf_timeout = timeout_for_pdf(pdf_path)
    for attempt in range(retries):
        try:
            with open(pdf_path, "rb") as f:
                r = requests.post(
                    f"{GROBID_URL}/api/processFulltextDocument",
                    files={"input": f},
                    data={
                        "consolidateHeader": "0",
                        "consolidateCitations": "0",
                        "includeRawCitations": "1",
                        "includeRawAffiliations": "1",
                    },
                    timeout=pdf_timeout,
                )
            if r.status_code == 503 and attempt < retries - 1:
                time.sleep(2 * (attempt + 1))
                continue
            break
        except requests.exceptions.RequestException:
            if attempt < retries - 1:
                time.sleep(2 * (attempt + 1))
                continue
            return {"error": "Connection failed after retries", "pdf": pdf_path}

    if r.status_code != 200:
        return {"error": f"GROBID returned {r.status_code}", "pdf": pdf_path}

    tei_xml = r.text
    result = parse_tei(tei_xml, pdf_path)
    result["_pdf_id"] = pid
    result["_pdf_path"] = pdf_path
    result["_pdf_name"] = os.path.basename(pdf_path)

    with open(out_path, "w") as f:
        json.dump(result, f, indent=2)

    return result


def parse_tei(xml_str, pdf_path=""):
    """Parse GROBID TEI XML into structured dict."""
    try:
        root = ET.fromstring(xml_str)
    except ET.ParseError:
        return {"error": "XML parse failed", "pdf": pdf_path}

    # Title — first main title in titleStmt
    title_el = root.find(".//tei:titleStmt/tei:title[@type='main']", TEI_NS)
    if title_el is None:
        title_el = root.find(".//tei:titleStmt/tei:title", TEI_NS)
    title = (title_el.text or "").strip() if title_el is not None else ""

    # Authors
    authors = []
    for author_el in root.findall(".//tei:sourceDesc//tei:author", TEI_NS):
        persname = author_el.find(".//tei:persName", TEI_NS)
        if persname is None:
            continue
        fn = persname.find("tei:forename", TEI_NS)
        sn = persname.find("tei:surname", TEI_NS)
        first = (fn.text or "").strip() if fn is not None else ""
        last = (sn.text or "").strip() if sn is not None else ""
        name = f"{first} {last}".strip()
        if not name:
            continue

        # Affiliation
        aff_el = author_el.find(".//tei:affiliation", TEI_NS)
        affiliation = ""
        if aff_el is not None:
            org_parts = []
            for org in aff_el.findall("tei:orgName", TEI_NS):
                if org.text:
                    org_parts.append(org.text.strip())
            affiliation = ", ".join(org_parts)

        # Email
        email_el = author_el.find(".//tei:email", TEI_NS)
        email = (email_el.text or "").strip() if email_el is not None else ""

        authors.append({
            "name": name,
            "first": first,
            "last": last,
            "affiliation": affiliation,
            "email": email,
        })

    # Abstract
    abstract_el = root.find(".//tei:profileDesc/tei:abstract", TEI_NS)
    abstract = ""
    if abstract_el is not None:
        abstract = ET.tostring(abstract_el, encoding="unicode", method="text").strip()

    # Date
    date_el = root.find(".//tei:sourceDesc//tei:date[@type='published']", TEI_NS)
    if date_el is None:
        date_el = root.find(".//tei:sourceDesc//tei:date", TEI_NS)
    date_str = ""
    year = None
    if date_el is not None:
        date_str = date_el.get("when", "") or (date_el.text or "").strip()
        # Extract year
        m = re.search(r"(19|20)\d{2}", date_str)
        if m:
            year = int(m.group())

    # DOI
    doi_el = root.find(".//tei:idno[@type='DOI']", TEI_NS)
    doi = (doi_el.text or "").strip() if doi_el is not None else ""

    # Keywords
    keywords = []
    for kw_el in root.findall(".//tei:profileDesc//tei:keywords//tei:term", TEI_NS):
        if kw_el.text:
            keywords.append(kw_el.text.strip())

    # Full body text
    body_el = root.find(".//tei:body", TEI_NS)
    body_text = ""
    if body_el is not None:
        body_text = ET.tostring(body_el, encoding="unicode", method="text").strip()

    # Section headers
    sections = []
    for head_el in root.findall(".//tei:body//tei:head", TEI_NS):
        if head_el.text:
            sections.append(head_el.text.strip())

    # References
    references = []
    for bib in root.findall(".//tei:listBibl/tei:biblStruct", TEI_NS):
        ref = {}
        # Title
        ref_title = bib.find(".//tei:title[@level='a']", TEI_NS)
        if ref_title is not None and ref_title.text:
            ref["title"] = ref_title.text.strip()
        # Journal
        ref_journal = bib.find(".//tei:title[@level='j']", TEI_NS)
        if ref_journal is not None and ref_journal.text:
            ref["journal"] = ref_journal.text.strip()
        # Book/proceedings
        ref_book = bib.find(".//tei:title[@level='m']", TEI_NS)
        if ref_book is not None and ref_book.text:
            ref["book"] = ref_book.text.strip()
        # Authors
        ref_authors = []
        for ra in bib.findall(".//tei:author", TEI_NS):
            pn = ra.find("tei:persName", TEI_NS)
            if pn is None:
                continue
            rfn = pn.find("tei:forename", TEI_NS)
            rsn = pn.find("tei:surname", TEI_NS)
            first = (rfn.text or "").strip() if rfn is not None else ""
            last = (rsn.text or "").strip() if rsn is not None else ""
            rname = f"{first} {last}".strip()
            if rname:
                ref_authors.append(rname)
        ref["authors"] = ref_authors
        # Year
        ref_date = bib.find(".//tei:date", TEI_NS)
        if ref_date is not None:
            ref_year_str = ref_date.get("when", "") or (ref_date.text or "")
            m = re.search(r"(19|20)\d{2}", ref_year_str)
            if m:
                ref["year"] = int(m.group())
        # DOI
        ref_doi = bib.find(".//tei:idno[@type='DOI']", TEI_NS)
        if ref_doi is not None and ref_doi.text:
            ref["doi"] = ref_doi.text.strip()

        if ref.get("title") or ref.get("book"):
            references.append(ref)

    # Figure/table captions
    figures = []
    for fig_el in root.findall(".//tei:figure", TEI_NS):
        fig_head = fig_el.find("tei:head", TEI_NS)
        fig_desc = fig_el.find("tei:figDesc", TEI_NS)
        fig_label = fig_el.find("tei:label", TEI_NS)
        fig = {}
        if fig_head is not None and fig_head.text:
            fig["head"] = fig_head.text.strip()
        if fig_desc is not None and fig_desc.text:
            fig["description"] = fig_desc.text.strip()
        if fig_label is not None and fig_label.text:
            fig["label"] = fig_label.text.strip()
        fig["type"] = fig_el.get("type", "figure")
        if fig:
            figures.append(fig)

    return {
        "title": title,
        "authors": authors,
        "abstract": abstract,
        "year": year,
        "date": date_str,
        "doi": doi,
        "keywords": keywords,
        "sections": sections,
        "body_text": body_text,
        "references": references,
        "figures": figures,
    }


# ─── Docling Extraction ──────────────────────────────────────────────────────

def extract_docling(pdf_path):
    """Extract full text as markdown via Docling."""
    pid = pdf_id(pdf_path)
    out_path = f"{OUTPUT_DIR}/docling/{pid}.md"

    if os.path.exists(out_path):
        with open(out_path) as f:
            return f.read()

    try:
        # Force CPU to avoid CUDA compatibility issues
        os.environ["CUDA_VISIBLE_DEVICES"] = ""
        from docling.document_converter import DocumentConverter
        conv = DocumentConverter()
        result = conv.convert(pdf_path)
        md = result.document.export_to_markdown()

        with open(out_path, "w") as f:
            f.write(md)

        return md
    except Exception as e:
        error_msg = f"Docling failed: {e}"
        with open(out_path, "w") as f:
            f.write(f"<!-- {error_msg} -->")
        return error_msg


# ─── Neo4j Graph Building ────────────────────────────────────────────────────

def get_neo4j_driver():
    from neo4j import GraphDatabase
    return GraphDatabase.driver(NEO4J_URL, auth=NEO4J_AUTH)


def create_schema(driver):
    """Create indexes and constraints in Neo4j."""
    queries = [
        "CREATE CONSTRAINT paper_id IF NOT EXISTS FOR (p:Paper) REQUIRE p.pdf_id IS UNIQUE",
        "CREATE CONSTRAINT author_name IF NOT EXISTS FOR (a:Author) REQUIRE a.name IS UNIQUE",
        "CREATE CONSTRAINT institution_name IF NOT EXISTS FOR (i:Institution) REQUIRE i.name IS UNIQUE",
        "CREATE CONSTRAINT topic_name IF NOT EXISTS FOR (t:Topic) REQUIRE t.name IS UNIQUE",
        "CREATE INDEX paper_title IF NOT EXISTS FOR (p:Paper) ON (p.title)",
        "CREATE INDEX paper_year IF NOT EXISTS FOR (p:Paper) ON (p.year)",
        "CREATE INDEX ref_title IF NOT EXISTS FOR (r:Reference) ON (r.title)",
        "CREATE FULLTEXT INDEX paper_search IF NOT EXISTS FOR (p:Paper) ON EACH [p.title, p.abstract, p.body_text]",
    ]
    with driver.session() as session:
        for q in queries:
            try:
                session.run(q)
            except Exception:
                pass  # Index may already exist


def populate_graph(driver, papers_data):
    """Load all extracted paper data into Neo4j."""
    with driver.session() as session:
        for i, paper in enumerate(papers_data):
            if "error" in paper:
                continue

            pid = paper.get("_pdf_id", "")
            title = paper.get("title", "") or paper.get("_pdf_name", "")

            # Create Paper node
            # Body text: store full for search, Neo4j handles large string props fine
            body = paper.get("body_text", "") or ""
            session.run("""
                MERGE (p:Paper {pdf_id: $pid})
                SET p.title = $title,
                    p.year = $year,
                    p.abstract = $abstract,
                    p.doi = $doi,
                    p.pdf_name = $pdf_name,
                    p.pdf_path = $pdf_path,
                    p.date = $date,
                    p.n_references = $n_refs,
                    p.n_figures = $n_figs,
                    p.n_chars = $n_chars,
                    p.sections = $sections,
                    p.body_text = $body_text
            """, pid=pid, title=title, year=paper.get("year"),
                abstract=paper.get("abstract", "")[:5000],
                doi=paper.get("doi", ""),
                pdf_name=paper.get("_pdf_name", ""),
                pdf_path=paper.get("_pdf_path", ""),
                date=paper.get("date", ""),
                n_refs=len(paper.get("references", [])),
                n_figs=len(paper.get("figures", [])),
                n_chars=len(body),
                sections=paper.get("sections", []),
                body_text=body)

            # Authors + affiliations
            for author in paper.get("authors", []):
                name = author["name"]
                session.run("""
                    MERGE (a:Author {name: $name})
                    WITH a
                    MATCH (p:Paper {pdf_id: $pid})
                    MERGE (a)-[:AUTHORED]->(p)
                """, name=name, pid=pid)

                if author.get("affiliation"):
                    session.run("""
                        MERGE (i:Institution {name: $inst})
                        WITH i
                        MATCH (a:Author {name: $name})
                        MERGE (a)-[:AFFILIATED_WITH]->(i)
                    """, inst=author["affiliation"], name=name)

            # Keywords as Topic nodes
            for kw in paper.get("keywords", []):
                session.run("""
                    MERGE (t:Topic {name: $kw})
                    WITH t
                    MATCH (p:Paper {pdf_id: $pid})
                    MERGE (p)-[:TAGGED]->(t)
                """, kw=kw.lower(), pid=pid)

            # References as nodes + CITES edges
            for ref in paper.get("references", []):
                ref_title = ref.get("title", ref.get("book", ""))
                if not ref_title or len(ref_title) > 500:
                    continue  # Skip empty or badly-parsed references
                session.run("""
                    MERGE (r:Reference {title: $title})
                    SET r.journal = $journal,
                        r.year = $year,
                        r.doi = $doi
                    WITH r
                    MATCH (p:Paper {pdf_id: $pid})
                    MERGE (p)-[:CITES]->(r)
                """, title=ref_title, journal=ref.get("journal", ""),
                    year=ref.get("year"), doi=ref.get("doi", ""), pid=pid)

                # If reference matches another paper in our collection, link them
                session.run("""
                    MATCH (p:Paper {pdf_id: $pid})
                    MATCH (cited:Paper)
                    WHERE cited.pdf_id <> $pid
                      AND toLower(cited.title) CONTAINS toLower($ref_title_prefix)
                      AND size($ref_title_prefix) > 15
                    MERGE (p)-[:CITES_INTERNAL]->(cited)
                """, pid=pid, ref_title_prefix=ref_title[:40])

            # Figure captions
            for fig in paper.get("figures", []):
                desc = fig.get("description", "")
                if desc and len(desc) > 20:
                    session.run("""
                        MATCH (p:Paper {pdf_id: $pid})
                        CREATE (f:Figure {
                            label: $label,
                            description: $desc,
                            type: $type
                        })
                        CREATE (p)-[:HAS_FIGURE]->(f)
                    """, pid=pid, label=fig.get("label", ""),
                        desc=desc[:500], type=fig.get("type", "figure"))

            if (i + 1) % 50 == 0:
                print(f"    Loaded {i+1}/{len(papers_data)} papers into Neo4j")

    # Build co-citation edges (papers citing same reference)
    with driver.session() as session:
        print("  Building co-citation edges...")
        session.run("""
            MATCH (p1:Paper)-[:CITES]->(r:Reference)<-[:CITES]-(p2:Paper)
            WHERE id(p1) < id(p2)
            WITH p1, p2, count(r) as shared_refs
            WHERE shared_refs >= 2
            MERGE (p1)-[c:CO_CITES]->(p2)
            SET c.shared_refs = shared_refs
        """)

        # Shared author edges
        print("  Building shared-author edges...")
        session.run("""
            MATCH (p1:Paper)<-[:AUTHORED]-(a:Author)-[:AUTHORED]->(p2:Paper)
            WHERE id(p1) < id(p2)
            WITH p1, p2, collect(a.name) as shared_authors
            MERGE (p1)-[s:SHARED_AUTHOR]->(p2)
            SET s.authors = shared_authors
        """)


# ─── Embeddings ───────────────────────────────────────────────────────────────

def detect_embed_model():
    """Auto-detect the best available embedding model."""
    try:
        r = requests.get(f"{OLLAMA_URL}/api/tags", timeout=5)
        models = [m["name"].split(":")[0] for m in r.json().get("models", [])]
        for preferred in ["qwen3-embedding", "mxbai-embed-large", "nomic-embed-text"]:
            if preferred in models:
                return preferred
    except Exception:
        pass
    return EMBED_MODEL


def generate_embedding(text, model=None):
    """Get embedding from Ollama."""
    model = model or EMBED_MODEL
    try:
        r = requests.post(f"{OLLAMA_URL}/api/embeddings", json={
            "model": model,
            "prompt": text[:8000],
        }, timeout=60)
        if r.status_code == 200:
            return r.json().get("embedding")
    except Exception:
        pass
    return None


def chunk_text(text, chunk_size=CHUNK_SIZE, overlap=CHUNK_OVERLAP):
    """
    Split text into overlapping chunks at paragraph/sentence boundaries.
    See spec-embedding-strategy.md for chunking strategy.
    """
    if len(text) <= chunk_size:
        return [text]

    chunks = []
    start = 0
    while start < len(text):
        end = start + chunk_size

        if end >= len(text):
            chunks.append(text[start:])
            break

        # Try to break at paragraph boundary
        para_break = text.rfind("\n\n", start + chunk_size // 2, end)
        if para_break > start:
            end = para_break + 2
        else:
            # Try sentence boundary
            sent_break = text.rfind(". ", start + chunk_size // 2, end)
            if sent_break > start:
                end = sent_break + 2

        chunk = text[start:end].strip()
        if len(chunk) >= 200:  # Skip tiny fragments
            chunks.append(chunk)

        # Advance with overlap
        start = max(start + 1, end - overlap)

    return chunks


def embed_papers(driver):
    """Tier 1: Embed papers with enriched context (title + abstract + entities)."""
    model = detect_embed_model()
    print(f"  Using model: {model}")

    with driver.session() as session:
        # Get papers that need embedding (or have wrong model)
        papers = session.run("""
            MATCH (p:Paper)
            WHERE p.embedding IS NULL OR p.embedding_model <> $model
            OPTIONAL MATCH (p)-[:MENTIONS]->(e)
            WITH p, collect(DISTINCT labels(e)[0] + ': ' + e.name) as entities
            OPTIONAL MATCH (p)-[:IN_TOPIC]->(t:Topic)
            WITH p, entities, collect(t.name) as topics
            RETURN p.pdf_id as pid, p.title as title, p.abstract as abstract,
                   entities, topics
        """, model=model).data()

    if not papers:
        print("  All papers already embedded with current model.")
        return

    print(f"  Embedding {len(papers)} papers (Tier 1)...")

    # Warmup
    generate_embedding("warmup", model)

    embedded = 0
    t0 = time.time()
    for i, paper in enumerate(papers):
        # Enriched text: title + abstract + topics + entity names
        parts = [paper['title'] or '']
        if paper.get('abstract'):
            parts.append(paper['abstract'])
        if paper.get('topics'):
            parts.append("Topics: " + ", ".join(paper['topics']))
        if paper.get('entities'):
            parts.append("Mentions: " + ", ".join(paper['entities'][:30]))

        text = ". ".join(parts)
        if len(text.strip()) < 10:
            continue

        embedding = generate_embedding(text, model)
        if embedding:
            with driver.session() as session:
                session.run("""
                    MATCH (p:Paper {pdf_id: $pid})
                    SET p.embedding = $embedding,
                        p.embedding_model = $model,
                        p.embedding_dim = $dim
                """, pid=paper["pid"], embedding=embedding,
                     model=model, dim=len(embedding))
            embedded += 1

        if (i + 1) % 100 == 0:
            elapsed = time.time() - t0
            rate = (i + 1) / elapsed
            eta = (len(papers) - i - 1) / rate
            print(f"    [{i+1}/{len(papers)}] {rate:.1f}/s, ETA {eta:.0f}s")

    elapsed = time.time() - t0
    print(f"  Tier 1 done: {embedded} papers in {elapsed:.1f}s")


def embed_chunks(driver):
    """Tier 2: Chunk body text and embed for deep search."""
    model = detect_embed_model()
    print(f"  Using model: {model}")

    # Create vector index if not exists
    with driver.session() as session:
        try:
            session.run("""
                CREATE VECTOR INDEX chunk_embedding IF NOT EXISTS
                FOR (c:Chunk) ON (c.embedding)
                OPTIONS {indexConfig: {
                    `vector.dimensions`: $dim,
                    `vector.similarity_function`: 'cosine'
                }}
            """, dim=EMBED_DIM)
        except Exception:
            pass  # Index may already exist or Neo4j version doesn't support

    # Get papers with body text that don't have chunks yet
    with driver.session() as session:
        papers = session.run("""
            MATCH (p:Paper)
            WHERE p.body_text IS NOT NULL AND size(p.body_text) > 200
            AND NOT (p)-[:HAS_CHUNK]->()
            RETURN p.pdf_id as pid, p.title as title, p.body_text as body
            ORDER BY size(p.body_text) ASC
        """).data()

    if not papers:
        print("  All papers already chunked.")
        return

    print(f"  Chunking {len(papers)} papers (Tier 2)...")
    generate_embedding("warmup", model)

    total_chunks = 0
    t0 = time.time()

    for i, paper in enumerate(papers):
        title = paper['title'] or 'Untitled'
        body = paper['body'] or ''
        chunks = chunk_text(body)

        for idx, chunk in enumerate(chunks):
            # Prefix with title for context
            embed_text = f"Title: {title}\n\n{chunk}"
            embedding = generate_embedding(embed_text, model)

            if embedding:
                with driver.session() as session:
                    session.run("""
                        MATCH (p:Paper {pdf_id: $pid})
                        CREATE (c:Chunk {
                            text: $text,
                            chunk_idx: $idx,
                            start_char: $start,
                            n_chars: $n_chars,
                            embedding: $embedding,
                            embedding_model: $model,
                            embedding_dim: $dim
                        })
                        CREATE (p)-[:HAS_CHUNK]->(c)
                    """, pid=paper["pid"], text=chunk, idx=idx,
                         start=idx * (CHUNK_SIZE - CHUNK_OVERLAP),
                         n_chars=len(chunk), embedding=embedding,
                         model=model, dim=len(embedding))
                total_chunks += 1

        if (i + 1) % 50 == 0:
            elapsed = time.time() - t0
            rate = total_chunks / elapsed if elapsed > 0 else 0
            eta = (len(papers) - i - 1) * (elapsed / (i + 1))
            print(f"    [{i+1}/{len(papers)}] {total_chunks} chunks, "
                  f"{rate:.1f} chunks/s, ETA {eta:.0f}s")

    elapsed = time.time() - t0
    print(f"  Tier 2 done: {total_chunks} chunks from {len(papers)} papers "
          f"in {elapsed:.1f}s")


def embed_entities(driver):
    """Tier 3: Embed content entities with paper context."""
    model = detect_embed_model()
    print(f"  Using model: {model}")

    with driver.session() as session:
        entities = session.run("""
            MATCH (e)<-[:MENTIONS]-(p:Paper)
            WHERE e.embedding IS NULL OR e.embedding_model <> $model
            WITH e, labels(e)[0] as type, collect(p.title)[..3] as papers, count(p) as n
            RETURN elementId(e) as eid, type, e.name as name, papers, n
        """, model=model).data()

    if not entities:
        print("  All entities already embedded.")
        return

    print(f"  Embedding {len(entities)} entities (Tier 3)...")
    generate_embedding("warmup", model)

    embedded = 0
    t0 = time.time()
    for i, ent in enumerate(entities):
        text = (f"{ent['type']}: {ent['name']}. "
                f"Mentioned in {ent['n']} papers including: "
                f"{'; '.join(p for p in ent['papers'] if p)}")

        embedding = generate_embedding(text, model)
        if embedding:
            with driver.session() as session:
                session.run("""
                    MATCH (e) WHERE elementId(e) = $eid
                    SET e.embedding = $embedding,
                        e.embedding_model = $model,
                        e.embedding_dim = $dim
                """, eid=ent["eid"], embedding=embedding,
                     model=model, dim=len(embedding))
            embedded += 1

        if (i + 1) % 200 == 0:
            elapsed = time.time() - t0
            print(f"    [{i+1}/{len(entities)}]")

    elapsed = time.time() - t0
    print(f"  Tier 3 done: {embedded} entities in {elapsed:.1f}s")


def semantic_search(driver, query, mode="paper", top_k=10):
    """
    Semantic search across the knowledge graph.
    Modes: paper (Tier 1), deep (Tier 2), concept (Tier 3), all.
    """
    model = detect_embed_model()
    query_embedding = generate_embedding(query, model)
    if not query_embedding:
        print("  Error: could not generate query embedding")
        return []

    results = []

    with driver.session() as session:
        if mode in ("paper", "all"):
            # Tier 1: Paper-level search
            try:
                papers = session.run("""
                    CALL db.index.vector.queryNodes('paper_embedding', $k, $emb)
                    YIELD node, score
                    RETURN node.title as title, node.year as year,
                           node.pdf_name as pdf, score
                    ORDER BY score DESC
                """, k=top_k, emb=query_embedding).data()
                for p in papers:
                    results.append({"type": "paper", "score": p["score"],
                                   "title": p["title"], "year": p["year"]})
            except Exception:
                # Fallback: brute-force cosine similarity
                papers = session.run("""
                    MATCH (p:Paper)
                    WHERE p.embedding IS NOT NULL
                    WITH p, gds.similarity.cosine(p.embedding, $emb) as score
                    ORDER BY score DESC LIMIT $k
                    RETURN p.title as title, p.year as year, score
                """, emb=query_embedding, k=top_k).data()
                for p in papers:
                    results.append({"type": "paper", "score": p["score"],
                                   "title": p["title"], "year": p["year"]})

        if mode in ("deep", "all"):
            # Tier 2: Chunk-level search
            try:
                chunks = session.run("""
                    CALL db.index.vector.queryNodes('chunk_embedding', $k, $emb)
                    YIELD node, score
                    MATCH (p:Paper)-[:HAS_CHUNK]->(node)
                    RETURN p.title as paper_title, node.text as text,
                           node.chunk_idx as chunk_idx, score
                    ORDER BY score DESC
                """, k=top_k, emb=query_embedding).data()
                for c in chunks:
                    results.append({"type": "chunk", "score": c["score"],
                                   "paper_title": c["paper_title"],
                                   "text": c["text"][:300],
                                   "chunk_idx": c["chunk_idx"]})
            except Exception:
                pass

        if mode in ("concept", "all"):
            # Tier 3: Entity-level search
            try:
                entities = session.run("""
                    MATCH (e)
                    WHERE e.embedding IS NOT NULL
                      AND (e:Frequency OR e:Mechanism OR e:HealthEffect
                           OR e:Technology OR e:Organization OR e:Tissue
                           OR e:Modulation)
                    WITH e, gds.similarity.cosine(e.embedding, $emb) as score
                    ORDER BY score DESC LIMIT $k
                    RETURN labels(e)[0] as type, e.name as name, score
                """, emb=query_embedding, k=top_k).data()
                for e in entities:
                    results.append({"type": "entity", "score": e["score"],
                                   "entity_type": e["type"], "name": e["name"]})
            except Exception:
                pass

    # Sort all results by score
    results.sort(key=lambda x: x.get("score", 0), reverse=True)
    return results[:top_k]


# ─── Topic Classification ────────────────────────────────────────────────────

TOPIC_PATTERNS = {
    "microwave_auditory": [
        r"microwave\s+audit", r"frey\s+effect", r"microwave\s+hearing",
        r"thermoelastic\s+expansion", r"pulsed\s+microwave.*hear",
        r"cochlea.*microwave", r"rf\s+hearing", r"havana\s+syndrome",
    ],
    "rf_dosimetry": [
        r"\bsar\b", r"specific\s+absorption\s+rate", r"fdtd",
        r"dosimetr", r"rf\s+exposure", r"electromagnetic\s+exposure",
        r"tissue\s+heating", r"dielectric\s+propert",
    ],
    "acoustics": [
        r"acoustic", r"infrasound", r"ultrasound", r"sound\s+pressure",
        r"noise\s+annoy", r"auditory\s+threshold", r"hearing\s+loss",
    ],
    "neuroscience": [
        r"neurosci", r"brain\s+stimulat", r"neural", r"eeg\b",
        r"cognitive", r"blood.brain\s+barrier", r"transcranial",
    ],
    "electromagnetic_theory": [
        r"maxwell", r"electromagnetic\s+wave", r"antenna\s+design",
        r"propagation\s+model", r"rf\s+shielding", r"radar\s+cross",
    ],
    "weapons_surveillance": [
        r"directed\s+energy", r"non.lethal\s+weapon", r"electronic\s+warfare",
        r"surveillance", r"counter.?intelligence", r"weapon",
    ],
    "signal_processing": [
        r"signal\s+process", r"uwb\b", r"ultra.?wideband", r"modulation",
        r"beamform", r"radar\s+signal", r"compressed\s+sensing",
    ],
    "medical": [
        r"clinical\s+trial", r"patient", r"diagnos", r"therap",
        r"medical\s+imaging", r"biomedical", r"health\s+effect",
    ],
}


def classify_paper(paper):
    """Classify a paper into topics based on text content."""
    text = f"{paper.get('title', '')} {paper.get('abstract', '')} {' '.join(paper.get('keywords', []))}".lower()
    topics = []
    for topic, patterns in TOPIC_PATTERNS.items():
        for pat in patterns:
            if re.search(pat, text):
                topics.append(topic)
                break
    return topics or ["other"]


def apply_topics(driver, papers_data):
    """Apply topic classification to papers in Neo4j."""
    with driver.session() as session:
        for paper in papers_data:
            if "error" in paper:
                continue
            topics = classify_paper(paper)
            for topic in topics:
                session.run("""
                    MERGE (t:Topic {name: $topic})
                    SET t.is_category = true
                    WITH t
                    MATCH (p:Paper {pdf_id: $pid})
                    MERGE (p)-[:IN_TOPIC]->(t)
                """, topic=topic, pid=paper.get("_pdf_id", ""))


# ─── Content Entity Extraction ──────────────────────────────────────────────

# Quantitative patterns — extract specific values with units
QUANTITY_PATTERNS = {
    "Frequency": [
        (r"(\d+(?:\.\d+)?)\s*(?:GHz)", lambda m: f"{m.group(1)} GHz"),
        (r"(\d+(?:\.\d+)?)\s*(?:MHz)", lambda m: f"{m.group(1)} MHz"),
        (r"(\d+(?:\.\d+)?)\s*(?:kHz)", lambda m: f"{m.group(1)} kHz"),
        (r"(\d+(?:\.\d+)?)\s*(?:Hz)(?!\w)", lambda m: f"{m.group(1)} Hz"),
    ],
    "Power": [
        (r"(\d+(?:\.\d+)?)\s*(?:mW/cm\s*[²2]|mW/cm2)", lambda m: f"{m.group(1)} mW/cm²"),
        (r"(\d+(?:\.\d+)?)\s*(?:W/cm\s*[²2]|W/cm2)", lambda m: f"{m.group(1)} W/cm²"),
        (r"(\d+(?:\.\d+)?)\s*(?:kW/kg)", lambda m: f"{m.group(1)} kW/kg"),
        (r"(\d+(?:\.\d+)?)\s*(?:W/kg)", lambda m: f"{m.group(1)} W/kg"),
        (r"(\d+(?:\.\d+)?)\s*(?:dBm)\b", lambda m: f"{m.group(1)} dBm"),
        (r"(\d+(?:\.\d+)?)\s*(?:dB\s*SPL)", lambda m: f"{m.group(1)} dB SPL"),
    ],
    "Temperature": [
        (r"(\d+(?:\.\d+)?)\s*°C\b", lambda m: f"{m.group(1)} °C"),
    ],
    "Duration": [
        (r"(\d+(?:\.\d+)?)\s*(?:µs|μs)\b", lambda m: f"{m.group(1)} µs"),
        (r"(\d+(?:\.\d+)?)\s*ms\b", lambda m: f"{m.group(1)} ms"),
    ],
}

# Qualitative concept patterns — tag with domain concepts
CONCEPT_PATTERNS = {
    # Mechanisms
    "Mechanism": {
        "thermoelastic expansion": [r"thermoelastic\s+expansion", r"thermoelastic\s+effect"],
        "Frey effect": [r"frey\s+effect", r"microwave\s+auditory\s+effect", r"\bmae\b.*auditory"],
        "inverse piezoelectric": [r"inverse\s+piezoelectric", r"piezoelectric\s+effect"],
        "dielectric heating": [r"dielectric\s+heating", r"dielectric\s+absorption"],
        "blood-brain barrier disruption": [r"blood.brain\s+barrier", r"\bbbb\b.*disrupt", r"\bbbb\b.*permeab"],
        "acoustic cavitation": [r"acoustic\s+cavitation", r"cavitation\s+effect"],
        "bone conduction": [r"bone\s+conduction"],
        "cochlear stimulation": [r"cochlea\w*\s+stimul", r"cochlear\s+response"],
        "neural entrainment": [r"neural\s+entrainment", r"brain\s+entrainment", r"brainwave\s+entrain"],
        "skull resonance": [r"skull\s+resonan", r"cranial\s+resonan"],
    },
    # Health effects
    "HealthEffect": {
        "hearing loss": [r"hearing\s+loss", r"sensorineural\s+hearing", r"noise.induced\s+hearing"],
        "tinnitus": [r"\btinnitus\b"],
        "vertigo/dizziness": [r"\bvertigo\b", r"\bdizziness\b", r"vestibular\s+dysfunction"],
        "headache": [r"\bheadache\b", r"\bcephalgia\b"],
        "cognitive impairment": [r"cognitive\s+impair", r"cognitive\s+deficit", r"memory\s+loss"],
        "nausea": [r"\bnausea\b"],
        "brain lesions": [r"brain\s+lesion", r"white\s+matter\s+tract", r"cerebral\s+lesion"],
        "thermal injury": [r"thermal\s+injury", r"tissue\s+burn", r"thermal\s+damage"],
        "cancer risk": [r"cancer\s+risk", r"carcinogen", r"tumor\s+promot"],
        "sleep disruption": [r"sleep\s+disrupt", r"insomnia.*rf", r"sleep\s+disturb"],
        "Havana syndrome": [r"havana\s+syndrome", r"anomalous\s+health\s+incident", r"\bahi\b.*diplomat"],
    },
    # Technologies / devices
    "Technology": {
        "RTL-SDR": [r"\brtl.sdr\b"],
        "FDTD simulation": [r"\bfdtd\b"],
        "phased array": [r"phased\s+array"],
        "directed energy weapon": [r"directed\s+energy\s+weapon", r"\bdew\b.*weapon", r"\bdew\b.*direct"],
        "voice-to-skull (V2K)": [r"voice.to.skull", r"\bv2k\b"],
        "MEDUSA": [r"\bmedusa\b.*audio", r"\bmedusa\b.*deter"],
        "radar": [r"\bradar\b"],
        "LTE/cellular": [r"\blte\b", r"cellular\s+network", r"cellular\s+band"],
        "ultrasound transducer": [r"ultrasound\s+transduc", r"ultrasonic\s+transduc"],
        "infrasound generator": [r"infrasound\s+generat", r"infrasonic\s+source"],
        "EEG": [r"\beeg\b", r"electroencephalogra"],
        "MRI/fMRI": [r"\bmri\b", r"\bfmri\b", r"magnetic\s+resonance\s+imag"],
        "microphone array": [r"microphone\s+array", r"acoustic\s+array"],
        "beamforming": [r"\bbeamform"],
    },
    # Organizations
    "Organization": {
        "DARPA": [r"\bdarpa\b"],
        "ICNIRP": [r"\bicnirp\b"],
        "FCC": [r"\bfcc\b.*regulat", r"\bfcc\b.*limit", r"\bfcc\b.*standard"],
        "IEEE": [r"\bieee\b.*standard", r"\bieee\b.*limit"],
        "WHO": [r"\bwho\b.*health", r"world\s+health\s+org"],
        "NATO": [r"\bnato\b"],
        "NSA": [r"\bnsa\b"],
        "FBI": [r"\bfbi\b"],
        "CIA": [r"\bcia\b.*program", r"\bcia\b.*project"],
        "DOD": [r"\bdod\b", r"department\s+of\s+defense"],
    },
    # Biological targets / tissues
    "Tissue": {
        "brain tissue": [r"brain\s+tissue", r"cerebral\s+tissue", r"grey\s+matter", r"white\s+matter"],
        "cochlea": [r"\bcochlea\b"],
        "skull bone": [r"skull\s+bone", r"cranial\s+bone", r"temporal\s+bone"],
        "skin tissue": [r"skin\s+tissue", r"cutaneous", r"dermal\s+absorption"],
        "eye/retina": [r"\bretina\b", r"ocular\s+tissue", r"lens.*eye"],
    },
    # Signal/modulation types
    "Modulation": {
        "AM envelope": [r"amplitude\s+modula", r"\bam\b.*envelope", r"am\s+modulat"],
        "PRF modulation": [r"pulse\s+repetition\s+freq", r"\bprf\b.*modulat"],
        "pulse modulation": [r"pulse\s+modulat", r"pulsed\s+rf\b", r"pulsed\s+microwave"],
        "UWB": [r"ultra.?wideband", r"\buwb\b"],
        "OFDM": [r"\bofdm\b"],
        "frequency hopping": [r"frequency\s+hopping", r"spread\s+spectrum"],
    },
}


def extract_entities(paper):
    """Extract content entities from paper text."""
    text = f"{paper.get('title', '')} {paper.get('abstract', '')} {paper.get('body_text', '')}"
    text_lower = text.lower()
    entities = {}  # (type, name) -> count

    # Quantitative entities
    for entity_type, patterns in QUANTITY_PATTERNS.items():
        for pat, formatter in patterns:
            for m in re.finditer(pat, text):
                val = formatter(m)
                key = (entity_type, val)
                entities[key] = entities.get(key, 0) + 1

    # Qualitative concepts
    for entity_type, concepts in CONCEPT_PATTERNS.items():
        for concept_name, patterns in concepts.items():
            for pat in patterns:
                if re.search(pat, text_lower):
                    key = (entity_type, concept_name)
                    entities[key] = entities.get(key, 0) + 1
                    break  # one match per concept is enough

    return entities


def apply_content_entities(driver, papers_data):
    """Extract content entities and create nodes + MENTIONS edges in Neo4j."""
    # Create indexes for entity types
    with driver.session() as session:
        for etype in ["Frequency", "Power", "Temperature", "Duration",
                      "Mechanism", "HealthEffect", "Technology",
                      "Organization", "Tissue", "Modulation"]:
            try:
                session.run(f"CREATE CONSTRAINT {etype.lower()}_name IF NOT EXISTS "
                           f"FOR (e:{etype}) REQUIRE e.name IS UNIQUE")
            except Exception:
                pass

    total_entities = 0
    total_mentions = 0

    with driver.session() as session:
        for i, paper in enumerate(papers_data):
            if "error" in paper:
                continue
            pid = paper.get("_pdf_id", "")
            entities = extract_entities(paper)

            for (etype, name), count in entities.items():
                session.run(f"""
                    MERGE (e:{etype} {{name: $name}})
                    WITH e
                    MATCH (p:Paper {{pdf_id: $pid}})
                    MERGE (p)-[m:MENTIONS]->(e)
                    SET m.count = $count
                """, name=name, pid=pid, count=count)
                total_mentions += 1

            total_entities = len(set(
                name for (_, name) in entities
            ))

            if (i + 1) % 100 == 0:
                print(f"    Entities: {i+1}/{len(papers_data)} papers processed")

    # Count unique entities
    with driver.session() as session:
        result = session.run("""
            MATCH (p:Paper)-[m:MENTIONS]->(e)
            WITH labels(e)[0] as type, count(DISTINCT e) as entities, count(m) as mentions
            RETURN type, entities, mentions
            ORDER BY mentions DESC
        """).data()

        print(f"\n  Content Entity Stats:")
        total_e = 0
        total_m = 0
        for row in result:
            print(f"    {row['type']:20s}  {row['entities']:5d} entities  {row['mentions']:6d} mentions")
            total_e += row['entities']
            total_m += row['mentions']
        print(f"    {'TOTAL':20s}  {total_e:5d} entities  {total_m:6d} mentions")

    # Build SHARED_ENTITY edges between papers that mention the same entities
    with driver.session() as session:
        print("  Building shared-entity edges...")
        session.run("""
            MATCH (p1:Paper)-[:MENTIONS]->(e)<-[:MENTIONS]-(p2:Paper)
            WHERE id(p1) < id(p2)
            WITH p1, p2, collect(DISTINCT e.name) as shared, count(DISTINCT e) as n_shared
            WHERE n_shared >= 3
            MERGE (p1)-[s:SHARED_ENTITIES]->(p2)
            SET s.count = n_shared, s.entities = shared[..20]
        """)
        shared = session.run("MATCH ()-[s:SHARED_ENTITIES]->() RETURN count(s) as c").single()["c"]
        print(f"    Shared-entity edges (>=3 common): {shared}")


# ─── Commands ─────────────────────────────────────────────────────────────────

def cmd_extract(args):
    """Extract all PDFs via GROBID (+ Docling for full text)."""
    pdfs = find_all_pdfs()
    limit = args.limit or len(pdfs)
    pdfs = pdfs[:limit]

    print(f"\n  Found {len(pdfs)} PDFs (processing {limit})")
    print(f"  Output: {OUTPUT_DIR}/\n")

    # GROBID extraction (sequential — engine pool is limited)
    print("  ── GROBID Extraction ──")
    results = []
    errors = 0
    for i, pdf_path in enumerate(pdfs):
        size_mb = os.path.getsize(pdf_path) / 1e6
        tout = timeout_for_pdf(pdf_path)
        if size_mb > 10:
            print(f"    Large file ({size_mb:.0f} MB, timeout {tout}s): {os.path.basename(pdf_path)}")
        try:
            result = extract_grobid(pdf_path)
            results.append(result)
            if "error" in result:
                errors += 1
        except Exception as e:
            errors += 1
            results.append({"error": str(e), "_pdf_path": pdf_path})

        if (i + 1) % 25 == 0 or i + 1 == len(pdfs):
            print(f"    GROBID: {i+1}/{len(pdfs)} ({errors} errors)")

    # Save combined results
    combined_path = f"{OUTPUT_DIR}/papers_grobid.json"
    with open(combined_path, "w") as f:
        json.dump(results, f, indent=2)
    print(f"  Saved: {combined_path}")

    # Summary
    n_with_title = sum(1 for r in results if r.get("title"))
    n_with_authors = sum(1 for r in results if r.get("authors"))
    n_with_refs = sum(1 for r in results if r.get("references"))
    total_refs = sum(len(r.get("references", [])) for r in results)
    n_with_abstract = sum(1 for r in results if r.get("abstract"))

    print(f"\n  GROBID Results:")
    print(f"    Papers with title:    {n_with_title}/{len(results)}")
    print(f"    Papers with authors:  {n_with_authors}/{len(results)}")
    print(f"    Papers with abstract: {n_with_abstract}/{len(results)}")
    print(f"    Papers with refs:     {n_with_refs}/{len(results)}")
    print(f"    Total references:     {total_refs}")
    print(f"    Errors:               {errors}")

    # Docling extraction (sequential — heavier, CPU-bound)
    if not args.skip_docling:
        print("\n  ── Docling Extraction ──")
        print("  (This takes ~30s per paper on CPU. Use --skip-docling to skip.)")
        os.environ["CUDA_VISIBLE_DEVICES"] = ""

        for i, pdf_path in enumerate(pdfs):
            pid = pdf_id(pdf_path)
            out_path = f"{OUTPUT_DIR}/docling/{pid}.md"
            if os.path.exists(out_path):
                if (i + 1) % 100 == 0:
                    print(f"    Docling: {i+1}/{len(pdfs)} (cached)")
                continue

            extract_docling(pdf_path)

            if (i + 1) % 10 == 0 or i + 1 == len(pdfs):
                print(f"    Docling: {i+1}/{len(pdfs)}")
    else:
        print("\n  Skipping Docling (--skip-docling)")

    return results


def cmd_build(args):
    """Build Neo4j graph from extracted data."""
    combined_path = f"{OUTPUT_DIR}/papers_grobid.json"
    if not os.path.exists(combined_path):
        print(f"  Error: Run 'extract' first. Missing {combined_path}")
        sys.exit(1)

    with open(combined_path) as f:
        papers_data = json.load(f)

    print(f"\n  Loading {len(papers_data)} papers into Neo4j...")

    driver = get_neo4j_driver()

    print("  Creating schema...")
    create_schema(driver)

    print("  Populating graph...")
    populate_graph(driver, papers_data)

    print("  Applying topic classification...")
    apply_topics(driver, papers_data)

    print("  Extracting content entities...")
    apply_content_entities(driver, papers_data)

    # Stats
    with driver.session() as session:
        stats = session.run("""
            MATCH (p:Paper) WITH count(p) as papers
            MATCH (a:Author) WITH papers, count(a) as authors
            MATCH (r:Reference) WITH papers, authors, count(r) as refs
            MATCH (i:Institution) WITH papers, authors, refs, count(i) as insts
            MATCH ()-[c:CITES]->() WITH papers, authors, refs, insts, count(c) as cites
            MATCH ()-[ci:CITES_INTERNAL]->() WITH papers, authors, refs, insts, cites, count(ci) as internal
            MATCH ()-[cc:CO_CITES]->() WITH papers, authors, refs, insts, cites, internal, count(cc) as cocites
            MATCH ()-[sa:SHARED_AUTHOR]->() WITH papers, authors, refs, insts, cites, internal, cocites, count(sa) as shared_auth
            MATCH ()-[m:MENTIONS]->() WITH papers, authors, refs, insts, cites, internal, cocites, shared_auth, count(m) as mentions
            MATCH ()-[se:SHARED_ENTITIES]->()
            RETURN papers, authors, refs, insts, cites, internal, cocites, shared_auth, mentions, count(se) as shared_ent
        """).single()

        print(f"\n  Neo4j Graph Stats:")
        print(f"    Papers:              {stats['papers']}")
        print(f"    Authors:             {stats['authors']}")
        print(f"    References:          {stats['refs']}")
        print(f"    Institutions:        {stats['insts']}")
        print(f"    CITES edges:         {stats['cites']}")
        print(f"    Internal citations:  {stats['internal']}")
        print(f"    Co-citation edges:   {stats['cocites']}")
        print(f"    Shared author edges: {stats['shared_auth']}")
        print(f"    MENTIONS edges:      {stats['mentions']}")
        print(f"    Shared entity edges: {stats['shared_ent']}")
        total_edges = stats['cites'] + stats['internal'] + stats['cocites'] + stats['shared_auth'] + stats['mentions'] + stats['shared_ent']
        print(f"    TOTAL edges:         {total_edges}")

    driver.close()
    print(f"\n  Neo4j Browser: http://localhost:7474")
    print(f"  Login: neo4j / rfmonitor2026")


def cmd_embed(args):
    """Generate embeddings for all 3 tiers."""
    driver = get_neo4j_driver()

    # Create paper-level vector index
    with driver.session() as session:
        try:
            session.run("""
                CREATE VECTOR INDEX paper_embedding IF NOT EXISTS
                FOR (p:Paper) ON (p.embedding)
                OPTIONS {indexConfig: {
                    `vector.dimensions`: $dim,
                    `vector.similarity_function`: 'cosine'
                }}
            """, dim=EMBED_DIM)
        except Exception:
            pass

    print("\n  ── Tier 1: Paper-Level Embeddings ──")
    embed_papers(driver)

    print("\n  ── Tier 2: Section-Level Chunk Embeddings ──")
    embed_chunks(driver)

    print("\n  ── Tier 3: Entity-Level Embeddings ──")
    embed_entities(driver)

    # Create entity vector index
    with driver.session() as session:
        try:
            session.run("""
                CREATE VECTOR INDEX entity_embedding IF NOT EXISTS
                FOR (e:Entity) ON (e.embedding)
                OPTIONS {indexConfig: {
                    `vector.dimensions`: $dim,
                    `vector.similarity_function`: 'cosine'
                }}
            """, dim=EMBED_DIM)
        except Exception:
            pass

    driver.close()
    print("  All tiers complete.\n")


def cmd_search(args):
    """Semantic search across the knowledge graph."""
    driver = get_neo4j_driver()
    query = " ".join(args.query)
    mode = args.mode
    top_k = args.top_k

    print(f"\n  ── Semantic Search ──")
    print(f"  Query: \"{query}\"")
    print(f"  Mode:  {mode}  |  Top: {top_k}\n")

    results = semantic_search(driver, query, mode=mode, top_k=top_k)

    if not results:
        print("  No results found.")
    else:
        for i, r in enumerate(results):
            score = r.get("score", 0)
            if r["type"] == "paper":
                year = r.get("year", "?")
                print(f"  {i+1:2d}. [{score:.4f}] PAPER ({year}): {r['title']}")
            elif r["type"] == "chunk":
                print(f"  {i+1:2d}. [{score:.4f}] CHUNK from: {r['paper_title']}")
                text_preview = r.get("text", "")[:200].replace("\n", " ")
                print(f"      \"{text_preview}...\"")
            elif r["type"] == "entity":
                print(f"  {i+1:2d}. [{score:.4f}] {r['entity_type']}: {r['name']}")

    print()
    driver.close()


def cmd_status(args):
    """Show pipeline status."""
    print("\n  ── Pipeline Status ──\n")

    # Services
    status = check_services()
    for svc, ok in status.items():
        icon = "UP" if ok else "DOWN"
        print(f"    {svc:10s} {icon}")

    # Files
    grobid_files = glob.glob(f"{OUTPUT_DIR}/grobid/*.json")
    docling_files = glob.glob(f"{OUTPUT_DIR}/docling/*.md")
    pdfs = find_all_pdfs()

    print(f"\n    PDFs found:         {len(pdfs)}")
    print(f"    GROBID extracted:   {len(grobid_files)}")
    print(f"    Docling extracted:  {len(docling_files)}")

    # Neo4j stats
    if status.get("neo4j"):
        try:
            driver = get_neo4j_driver()
            with driver.session() as session:
                papers = session.run("MATCH (p:Paper) RETURN count(p) as c").single()["c"]
                edges = session.run("MATCH ()-[r]->() RETURN count(r) as c").single()["c"]
                print(f"    Neo4j papers:       {papers}")
                print(f"    Neo4j total edges:  {edges}")
            driver.close()
        except Exception:
            pass

    # Embeddings
    if status.get("neo4j"):
        try:
            driver = get_neo4j_driver()
            with driver.session() as session:
                embedded = session.run("MATCH (p:Paper) WHERE p.embedding IS NOT NULL RETURN count(p) as c").single()["c"]
                chunks = session.run("MATCH (c:Chunk) RETURN count(c) as c").single()["c"]
                ent_emb = session.run("MATCH (e) WHERE e.embedding IS NOT NULL AND NOT e:Paper AND NOT e:Chunk RETURN count(e) as c").single()["c"]
                model_info = session.run("MATCH (p:Paper) WHERE p.embedding_model IS NOT NULL RETURN p.embedding_model as m, count(p) as c LIMIT 1").data()
                model_str = model_info[0]["m"] if model_info else "none"
                print(f"    Papers w/ embedding: {embedded}  (model: {model_str})")
                print(f"    Chunks:              {chunks}")
                print(f"    Entities w/ embed:   {ent_emb}")
            driver.close()
        except Exception:
            pass
    print()


def cmd_all(args):
    """Run full pipeline."""
    print("=" * 60)
    print("  KNOWLEDGE GRAPH PIPELINE — FULL RUN")
    print("=" * 60)

    status = check_services()
    missing = [s for s, ok in status.items() if not ok]
    if missing:
        print(f"\n  ERROR: Services not running: {', '.join(missing)}")
        print("  Start them with:")
        if "grobid" in missing:
            print("    docker start grobid")
        if "neo4j" in missing:
            print("    docker start neo4j")
        if "ollama" in missing:
            print("    docker start ollama")
        sys.exit(1)

    t0 = time.time()

    print("\n  Step 1: Extract PDFs")
    papers = cmd_extract(args)

    print("\n  Step 2: Build Neo4j Graph")
    cmd_build(args)

    print("\n  Step 3: Generate Embeddings")
    cmd_embed(args)

    elapsed = time.time() - t0
    print(f"\n  Pipeline complete in {elapsed/60:.1f} minutes")
    print(f"  Neo4j Browser: http://localhost:7474")
    print(f"  Login: neo4j / rfmonitor2026\n")


# ─── Main ─────────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(
        description="Knowledge Graph Pipeline — GROBID + Docling + Neo4j + Ollama",
        formatter_class=argparse.RawDescriptionHelpFormatter)

    sub = parser.add_subparsers(dest="command")

    p = sub.add_parser("extract", help="Extract PDFs via GROBID + Docling")
    p.add_argument("--limit", type=int, default=None, help="Max PDFs to process")
    p.add_argument("--skip-docling", action="store_true", help="Skip Docling (slow)")

    sub.add_parser("build", help="Build Neo4j graph from extractions")
    sub.add_parser("embed", help="Generate embeddings via Ollama (all 3 tiers)")
    sub.add_parser("status", help="Show pipeline status")

    p = sub.add_parser("search", help="Semantic search across the knowledge graph")
    p.add_argument("query", nargs="+", help="Search query (natural language)")
    p.add_argument("--mode", choices=["paper", "deep", "concept", "all"],
                   default="paper", help="Search mode (default: paper)")
    p.add_argument("--top-k", type=int, default=10, help="Number of results")

    p = sub.add_parser("all", help="Run full pipeline")
    p.add_argument("--limit", type=int, default=None)
    p.add_argument("--skip-docling", action="store_true")

    args = parser.parse_args()

    if args.command == "extract":
        cmd_extract(args)
    elif args.command == "build":
        cmd_build(args)
    elif args.command == "embed":
        cmd_embed(args)
    elif args.command == "search":
        cmd_search(args)
    elif args.command == "status":
        cmd_status(args)
    elif args.command == "all":
        cmd_all(args)
    else:
        parser.print_help()


if __name__ == "__main__":
    main()
