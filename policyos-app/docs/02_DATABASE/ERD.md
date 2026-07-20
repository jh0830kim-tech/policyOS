# Entity Relationship Overview

```mermaid
erDiagram
    ORGANIZATION ||--o{ MEMBERSHIP : has
    USER ||--o{ MEMBERSHIP : joins
    MEMBERSHIP ||--o{ MEMBERSHIP_ROLE : receives
    ROLE ||--o{ MEMBERSHIP_ROLE : assigned
    ROLE ||--o{ ROLE_PERMISSION : contains
    PERMISSION ||--o{ ROLE_PERMISSION : grants
    ORGANIZATION ||--o{ POLICY_CANDIDATE : owns
    USER ||--o{ AUDIT_EVENT : performs
    ORGANIZATION ||--o{ AUDIT_EVENT : scopes
```

The actual schema is authoritative. This diagram describes domain intent and must be updated when models change.
## Sprint 4 artifact lineage
```mermaid
erDiagram
    ORGANIZATIONS ||--o{ AI_WORK_PACKAGES : owns
    AI_TASKS ||--o{ AI_WORK_PACKAGES : produces
    AI_WORK_PACKAGES ||--o{ AI_ARTIFACTS : contains
    USERS ||--o{ AI_ARTIFACTS : creates
    USERS ||--o{ AI_ARTIFACTS : approves
```
Artifact payloads are limited to 64 KiB and exclude raw provider responses, secrets, and hidden reasoning.
## Knowledge chunk lineage

```text
KnowledgeSource (organization)
  └─ KnowledgeDocument
       └─ KnowledgeDocumentVersion
            ├─ KnowledgeChunk [config_hash, index, locator, content_hash]
            │    └─ CitationReference [source/document/version/chunk lineage]
            └─ active_chunking_config_hash
```

Every edge includes `organization_id` in its foreign key. Citation-to-chunk deletion remains restrictive so citation lineage cannot be silently orphaned.
