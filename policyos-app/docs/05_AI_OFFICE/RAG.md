# RAG Architecture

## Pipeline
1. Ingest approved documents.
2. Extract text and metadata.
3. classify security and organization scope.
4. Chunk with stable identifiers.
5. Create embeddings.
6. Retrieve by authorized context.
7. Re-rank results.
8. Generate source-linked output.
9. Store citation lineage.

## Quality requirements
- source title and location
- retrieval timestamp
- chunk identifier
- confidence or evidence sufficiency
- no cross-organization leakage
## Ingestion input to RAG

Checkpoint 2 supplies normalized version text and structured page/section/sheet metadata. It does not create retrieval chunks or embeddings; deterministic chunk IDs, overlap, and citation locators remain Checkpoint 3. Normalization collapses incidental spacing and repeated blank lines while preserving source text, headings, page/sheet boundaries, formulas as visible text, and evidence-bearing content. Header/footer removal is an explicit hook and is disabled by default.
## Chunking contract

Given the same normalized document version and configuration, chunk order, zero-based indices, boundaries, SHA-256 hashes, and citation locators are deterministic. Overlap reuses whole source blocks where possible and records original block ranges; it never increases a chunk beyond the maximum. Small trailing chunks merge only with compatible locators and within the maximum.

`SimpleTokenEstimator` is a stable character heuristic for retrieval/context planning only. It is not a provider tokenizer and must never be used for billing. Reprocessing the same version/config hash is idempotent. A changed config produces a retained revision set and updates only the active config pointer; automatic retirement and cleanup of old sets are deferred to retention policy work.

## Sprint 6 Checkpoint 4: Embedding and vector retrieval

- Embeddings use a provider-independent gateway (`fake`, `disabled`, or explicitly configured `openai`).
- Model, dimension, chunking configuration, normalization strategy, provider, and policy version participate in immutable embedding revisions.
- The default fake provider is SHA-256 deterministic and performs no network I/O. OpenAI uses bounded application retries while SDK retries are disabled.
- External embedding follows provider transmission policy: restricted content is blocked and confidential content requires organization policy. Embedding records never duplicate source text or secrets.
- Current persistence stores validated vectors as JSON for PostgreSQL/SQLite compatibility. `VectorStore` isolates this detail; production pgvector indexing is planned and must fail clearly if the extension is unavailable.
- Retrieval enforces organization, model, dimension, classification, document/source, effective-date, top-k, and minimum-score filters. Cosine scores remain in the native [-1, 1] range.
- Usage records capture input count/tokens, batch/retry count, latency, provider request ID and nullable estimated cost; pricing is not hard-coded.
- Public embedding/search HTTP endpoints are deferred; application services are the authorization-ready boundary.
