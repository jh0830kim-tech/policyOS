# Database Strategy

## Primary database
PostgreSQL is the system of record.

## ORM
SQLAlchemy 2.x async.

## Migration
Alembic migrations are required for schema changes.

## Conventions
- Primary keys: UUID preferred for externally exposed entities.
- Timestamps: UTC, timezone-aware.
- Soft deletion: use only where audit or recovery requirements justify it.
- Organization scope: explicit foreign key for organization-owned records.
- Sensitive fields: classify and protect according to security policy.

## Transaction rule
A business operation that must succeed or fail as a unit must run within one explicit transaction boundary.
## AI execution records
ai_tasks and agent_runs store ownership, status, review state, lineage, prompt/model metadata, timestamps, safe errors, and concise result or artifact references. Raw instructions, secrets, provider payloads, and hidden reasoning are excluded.
## Secure knowledge ingestion persistence

Ingestion creates an organization-scoped job before scanning and parsing. Job states are `pending`, `scanning`, `parsing`, `succeeded`, `failed`, `duplicate`, and `rejected`. Parsed normalized text is stored on the immutable document version; original file bytes are not stored. File and parser metadata, SHA-256, scan metadata, source lineage, classification, and optional official-document dates remain JSON metadata. Revision `20260720_0008` adds parsed content, ingestion states, and `knowledge.ingest`/`knowledge.read` permission seeds.
## Deterministic chunk sets and citations

Revision `20260720_0009` adds versioned chunk-set metadata and structured citation locators. A chunk set is identified by document version, chunking strategy/config hash, and organization. Unique constraints prevent duplicate indices and hashes within the same set. Changing configuration creates a new set without deleting prior chunks; the document version records the active config hash and `pending/running/succeeded/failed` chunking status. Citations retain source/document/version/chunk composite tenant lineage, page and section locators, heading, external source ID, content hash, and completeness metadata.

## Sprint 6 Checkpoint 4: Embedding and vector retrieval

- Embeddings use a provider-independent gateway (`fake`, `disabled`, or explicitly configured `openai`).
- Model, dimension, chunking configuration, normalization strategy, provider, and policy version participate in immutable embedding revisions.
- The default fake provider is SHA-256 deterministic and performs no network I/O. OpenAI uses bounded application retries while SDK retries are disabled.
- External embedding follows provider transmission policy: restricted content is blocked and confidential content requires organization policy. Embedding records never duplicate source text or secrets.
- Current persistence stores validated vectors as JSON for PostgreSQL/SQLite compatibility. `VectorStore` isolates this detail; production pgvector indexing is planned and must fail clearly if the extension is unavailable.
- Retrieval enforces organization, model, dimension, classification, document/source, effective-date, top-k, and minimum-score filters. Cosine scores remain in the native [-1, 1] range.
- Usage records capture input count/tokens, batch/retry count, latency, provider request ID and nullable estimated cost; pricing is not hard-coded.
- Public embedding/search HTTP endpoints are deferred; application services are the authorization-ready boundary.
