# Embedding Strategy Specification

## Overview

Multi-tier embedding pipeline for the RF Monitor knowledge graph.
Converts 739 academic papers (36.3 MB body text) into semantic vectors
for natural-language search across the corpus.

## Model Selection

### Primary: `qwen3-embedding` (Qwen 3, 2026)
- **Parameters:** 0.6B (default), 4B, 8B available
- **Dimensions:** 2048
- **Context:** 32K tokens
- **Why:** Best-in-class 2026 embedding model, high MTEB scores, Ollama native
- **Hardware:** GTX 1080 (8GB VRAM) via Ollama with CUDA

### Fallback: `mxbai-embed-large` (already installed)
- **Parameters:** 334M
- **Dimensions:** 1024
- **Context:** 512 tokens
- **Why:** Already installed, fast (13ms/embedding), solid quality
- **When to use:** If qwen3-embedding pull fails or for rapid iteration

### Retired: `nomic-embed-text` (Phase 2 original)
- **Parameters:** 137M
- **Dimensions:** 768
- **Context:** 8K tokens
- **Why retired:** Lower dimensionality, older model, superseded by both above

## Embedding Tiers

### Tier 1: Paper-Level (739 vectors)

**What gets embedded:**
```
{title}. {abstract}. Topics: {topic_list}. Entities: {entity_names}.
```

**Enrichment:** Concatenate title + abstract + IN_TOPIC names + MENTIONS entity
names. This gives the embedding model semantic context beyond raw text — e.g.,
a paper that mentions "915 MHz" and "thermoelastic expansion" will embed closer
to queries about microwave auditory effect even if those exact words aren't in
the abstract.

**Storage:** `Paper.embedding` property (float array) in Neo4j.

**Use case:** Quick topic-level semantic search. "Find papers about directed
energy effects on the auditory system" → returns ranked paper list.

**Token budget:** ~500-2000 tokens per paper.

### Tier 2: Section-Level Chunks (~18,000 vectors)

**What gets embedded:** Body text chunked at ~2000 chars with 500 char overlap.
Each chunk prefixed with paper title for context.

```
Title: {paper_title}
Section: {section_name or "chunk N"}

{chunk_text}
```

**Storage:** New `(:Chunk)` nodes connected via `(:Paper)-[:HAS_CHUNK]->(:Chunk)`.
Each Chunk node has: `text`, `embedding`, `chunk_idx`, `start_char`, `end_char`.

**Use case:** Deep content search within papers. "What SAR threshold causes
auditory perception?" → returns specific paragraphs with the answer.

**Chunking strategy:**
- Split on paragraph boundaries (double newline) first
- If paragraph > 2000 chars, split on sentence boundaries (`. `)
- Minimum chunk size: 200 chars (merge small chunks with next)
- Maximum chunk size: 2500 chars
- Overlap: 500 chars (ensures no information falls on a boundary)

**Estimated count:** 36.3 MB / 2000 chars = ~18,150 chunks.

### Tier 3: Entity-Level (~1,700 vectors)

**What gets embedded:** Content entities (Frequency, Mechanism, HealthEffect,
Technology, Organization, Tissue, Modulation) with context from papers that
mention them.

```
{entity_type}: {entity_name}
Mentioned in {N} papers including: {top_3_paper_titles}
```

**Storage:** `embedding` property on entity nodes.

**Use case:** Concept-level search. "What concepts relate to bone conduction?"
→ returns related mechanisms, tissues, frequencies.

**Estimated count:** ~1,682 entities.

## Neo4j Vector Index

```cypher
-- Paper-level vector index
CREATE VECTOR INDEX paper_embedding IF NOT EXISTS
FOR (p:Paper)
ON (p.embedding)
OPTIONS {
  indexConfig: {
    `vector.dimensions`: 2048,  -- qwen3-embedding (or 1024 for mxbai)
    `vector.similarity_function`: 'cosine'
  }
}

-- Chunk-level vector index
CREATE VECTOR INDEX chunk_embedding IF NOT EXISTS
FOR (c:Chunk)
ON (c.embedding)
OPTIONS {
  indexConfig: {
    `vector.dimensions`: 2048,
    `vector.similarity_function`: 'cosine'
  }
}

-- Entity-level vector index
CREATE VECTOR INDEX entity_embedding IF NOT EXISTS
FOR (e:Entity)
ON (e.embedding)
OPTIONS {
  indexConfig: {
    `vector.dimensions`: 2048,
    `vector.similarity_function`: 'cosine'
  }
}
```

## Semantic Search API

### Query Flow

```
User query (natural language)
  → Embed query with same model
  → Vector similarity search (cosine) across appropriate tier
  → Re-rank by combining vector score + graph features
  → Return results with context
```

### Search Modes

1. **Paper search** (`--mode paper`): Search Tier 1. Returns top-N papers.
2. **Deep search** (`--mode deep`): Search Tier 2. Returns specific passages.
3. **Concept search** (`--mode concept`): Search Tier 3. Returns related entities.
4. **Combined** (`--mode all`): Search all tiers, merge and re-rank.

### Re-ranking Features (from graph structure)

- **Citation weight:** Papers cited by more in-collection papers rank higher
- **Entity overlap:** Papers sharing entities with the query's top matches
- **Recency:** Optional year-based decay
- **Topic coherence:** Papers in same topic cluster as top matches

### CLI Interface

```bash
# Semantic search
python kg_pipeline.py search "thermoelastic cochlea perception threshold"
python kg_pipeline.py search --mode deep "what SAR level causes auditory perception"
python kg_pipeline.py search --mode concept "directed energy weapon"

# With filters
python kg_pipeline.py search --topic microwave_auditory "pulse width optimization"
python kg_pipeline.py search --year-min 2010 "FDTD head simulation"
```

## Implementation Plan

### Step 1: Model Setup
- Pull `qwen3-embedding` via Ollama (or use `mxbai-embed-large` fallback)
- Test embedding dimensions and latency
- Update `EMBED_MODEL` and `EMBED_DIM` constants in `kg_pipeline.py`

### Step 2: Paper-Level Embeddings (Tier 1)
- Update `embed_papers()` to use enriched text (title + abstract + entities)
- Create Neo4j vector index
- Embed all 739 papers (~1 min with mxbai, ~5 min with qwen3)

### Step 3: Chunk-Level Embeddings (Tier 2)
- Add `chunk_body_text(paper)` function with overlap chunking
- Add `embed_chunks()` function
- Create `:Chunk` nodes and `:HAS_CHUNK` edges
- Embed ~18K chunks (~4 min with mxbai, ~30 min with qwen3)

### Step 4: Entity-Level Embeddings (Tier 3)
- Add `embed_entities()` function
- Embed ~1,700 entities (~30s with mxbai)

### Step 5: Search Interface
- Add `semantic_search(query, mode, top_k)` function
- Add `cmd_search()` CLI command
- Implement re-ranking with graph features

### Step 6: Integration with Detection Pipeline
- `forward_model.py`: Query KG for encoding parameters by semantic similarity
- `demod_pulses.py`: Look up detection thresholds from literature
- `pulse_detector.py`: Physical plausibility check via KG semantic search

## Performance Estimates

| Tier | Vectors | Model | Time | Storage |
|------|---------|-------|------|---------|
| Paper | 739 | qwen3-embedding | ~5 min | ~6 MB |
| Chunks | ~18,000 | qwen3-embedding | ~30 min | ~150 MB |
| Entities | ~1,700 | qwen3-embedding | ~2 min | ~14 MB |
| **Total** | **~20,400** | | **~37 min** | **~170 MB** |

With `mxbai-embed-large` (1024-dim, already installed):

| Tier | Vectors | Time | Storage |
|------|---------|------|---------|
| Paper | 739 | ~10 s | ~3 MB |
| Chunks | ~18,000 | ~4 min | ~75 MB |
| Entities | ~1,700 | ~22 s | ~7 MB |
| **Total** | **~20,400** | **~5 min** | **~85 MB** |

## Model-Agnostic Design

The pipeline stores `embedding_model` and `embedding_dim` metadata on each
embedded node. This allows:
- Mixing models (e.g., upgrade paper embeddings to qwen3 while keeping mxbai chunks)
- Re-embedding with a better model later without losing old data
- Validating that query embedding matches index dimensions

```cypher
-- Check embedding model consistency
MATCH (p:Paper) WHERE p.embedding IS NOT NULL
RETURN p.embedding_model, count(p), p.embedding_dim
```

## Notes

- GTX 1080 (sm_61) works with Ollama CUDA for inference
- For batch embedding, process in batches of 100 with progress logging
- Skip re-embedding if `embedding_model` matches current model
- Body text chunking is deterministic — same text always produces same chunks
