# Pg_Graph

Production-ready Python application for building graph data from Quality Management tables stored in a local DuckDB database.

This project now supports a single unified pipeline:

- Node sync into `graph_nodes`
- Node lookup refresh into `node_lookup`
- Edge sync into `graph_edges`
- Semantic chunk + embedding sync into `vector_chunks`

The edge pipeline only creates relationships. It never creates nodes.

## Technology

- Python 3.12+
- DuckDB (single embedded database file, no server)
- logging
- pytest

## Project Structure

- `app/storage/duckdb_store.py`
  - `DuckDBStore`: opens the DuckDB file, bootstraps tables, and runs queries
  - Path from `DUCKDB_PATH` (default `data/graph_store.duckdb`)
- `app/models.py`
  - Shared helpers for key normalization and JSON-safe property shaping
  - Graph node model and utilities
- `app/edge_models.py`
  - Graph edge model and helpers
  - `create_edge()` and source-ref merge logic
- `app/repositories.py`
  - Node repository used by node builder
- `app/edge_repository.py`
  - `EdgeRepository` for source reads and bulk edge UPSERT
- `app/node_lookup_service.py`
  - `NodeLookupService` with cached `lookup_node()` by `(node_type, business_key)`
- `app/processors.py`
  - Node generation processors
- `app/relationship_builder.py`
  - `RelationshipBuilder` with:
    - `process_qe()`
    - `process_psp()`
    - `process_capa()`
    - `process_containment()`
    - `process_batch()`
    - `process_event()`
    - `process_evaluation()`
- `app/graph_builder.py`
  - Node sync orchestration
- `app/graph_edge_service.py`
  - Edge orchestration and batch UPSERT
  - `sync_edges()`
- `app/graph_edge_builder.py`
  - Edge builder facade
- `app/main.py`
  - Unified CLI entrypoint for nodes, node lookup, edges, and chunks
- `app/chunk_sync/config.py`
  - Environment/config loading for chunk pipeline
- `app/chunk_sync/models.py`
  - Chunk dataclasses and per-table chunk mapping specs
- `app/chunk_sync/repositories.py`
  - Batched source record readers
- `app/chunk_sync/node_lookup_service.py`
  - Cached node lookup using `node_lookup` (+ graph node validation)
- `app/chunk_sync/text_cleaner.py`
  - Whitespace normalization and null/empty filtering
- `app/chunk_sync/embedding_service.py`
  - Local sentence-transformers embedding generator
- `app/chunk_sync/chunk_builder.py`
  - Per-table chunk extraction, metadata shaping, and embedding generation
- `app/chunk_sync/chunk_repository.py`
  - Bulk UPSERT to `vector_chunks`
- `app/chunk_sync/service.py`
  - Chunk sync service orchestration
- `tests/*`
  - pytest coverage for helper behavior and relationship logic
  - chunk pipeline unit tests (cleaning, chunk building, embeddings, lookup, UPSERT)

## Graph Edge Rules Implemented

- Never creates nodes
- Looks up existing nodes using `(node_type, business_key)`
- Skips edges when either endpoint node is missing
- Logs missing node warnings
- Uses UPSERT on unique key:
  - `(from_node_uuid, to_node_uuid, relationship)`
- Stores `source_refs` as JSON array with:
  - `table`
  - `parent_pk`
  - `child_pk`
  - `relationship_source`
- Leaves `properties` as `{}` by default, but accepts metadata payloads for future extension

## Setup

Install dependencies:

```powershell
python -m pip install -r requirements.txt
```

Environment file expected at:

- `virtual_env/.env`

Optional keys:

- `DUCKDB_PATH` (default: `data/graph_store.duckdb`)

DuckDB allows only one writer at a time. Stop any running pipeline, seed script, or Streamlit app that holds the file before running a write job.

Seed the source tables before the first pipeline run:

```powershell
python Database/seed_all.py
```

Chunk pipeline optional knobs:

- `EMBEDDING_MODEL_NAME` (default: `sentence-transformers/all-mpnet-base-v2`)
- `EMBEDDING_MODEL_SHORT_NAME` (default: `all-mpnet-base-v2`)
- `EMBEDDING_DIMENSIONS` (default: `768`)
- `EMBEDDING_MODEL_VERSION` (default: `1`)
- `SOURCE_BATCH_SIZE` (default: `2000`)
- `UPSERT_BATCH_SIZE` (default: `1000`)
- `LOG_LEVEL` (default: `INFO`)

## Run

Run full unified sync:

```powershell
python -m app.main --log-level INFO
```

Optional first-run reset (drops and recreates the 4 output tables before processing):

```powershell
python -m app.main --first-run --log-level INFO
```

## Semantic Chunk Pipeline

### What it does

- Reads source tables in batches (`qe`, `psp`, `capa`, `containment_actions`, `qe_events`, `initial_evaluations`)
- Resolves `node_uuid` strictly via `node_lookup`
- Cleans text fields (trim + collapse whitespace)
- Generates normalized embeddings locally with `sentence-transformers/all-mpnet-base-v2`
- UPSERTs records into `vector_chunks`
- Prevents duplicates via unique key: `(node_uuid, source_column, chunk_order)`

### Processing flow

1. Build graph nodes
2. Refresh `node_lookup` from node source references
3. Run edge sync and chunk embedding sync in parallel
4. Chunk sync internals:
  - Read source record
  - Lookup `node_uuid` from `node_lookup`
  - Extract mapped text fields
  - Clean text
  - Build chunk metadata
  - Generate embedding
  - Bulk UPSERT into `vector_chunks`

### Design notes

- Embedding model loads once at startup in `EmbeddingService`
- Chunk and persistence contracts are dataclass-driven
- Source reading, node lookup, chunk building, and persistence are separated for SOLID-friendly extensibility
- To switch embedding models, update only `EmbeddingService` configuration/implementation

## Testing

```powershell
python -m pytest -q
```

## Performance Notes

- Uses a single DuckDB connection per process (columnar, in-process)
- Caches graph node lookup map in memory
- Uses bulk UPSERT in batches for high-volume edge loads
- Deduplicates generated edges before writing
