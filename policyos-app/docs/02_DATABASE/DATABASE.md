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
