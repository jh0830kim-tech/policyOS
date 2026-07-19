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
