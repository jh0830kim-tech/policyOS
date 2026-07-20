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
