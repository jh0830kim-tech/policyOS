# Changelog

## Sprint 4 ??Operational AI Agents

- Added six governed operational agents and typed artifact contracts.
- Added deterministic policy, communication, presentation, and full-office workflows.
- Added organization-scoped work-package and artifact persistence with human review transitions.
- Added RBAC-protected work-package and artifact APIs.
- Added network-free full-office integration coverage.

## Unreleased ??Sprint 2 authentication and identity
- Added Argon2 password hashing and constant-work credential verification.
- Added short-lived signed JWT access tokens with minimal `sub`, `iat`, `exp`, and `jti` claims.
- Added `POST /api/v1/auth/login` and authenticated `GET /api/v1/auth/me` endpoints.
- Added active organization membership resolution with tenant-safe `404` behavior.
- Added exact organization-scoped RBAC checks through membership roles and atomic permissions.
- Added login success, login failure, and authorization-denial audit events without sensitive request data.
- Added production JWT secret validation and a safe `.env.example` placeholder.
- Documented the login rate-limit integration point and deferred refresh-token and revocation design.
- Added end-to-end authentication and authorization regression coverage.

## 0.2.0 ??Documentation architecture
- Added PolicyOS Constitution.
- Added architecture, security, API, database, AI Office, and development guides.
- Added specifications for authentication, AI Office, and knowledge/RAG.
- Added agent and system prompt templates.
- Added ADR records and sprint-ready Codex prompts.

## 0.1.0
- Initial project documentation scaffold.

## Sprint 5 ??Provider privacy controls

- Added four-level AI data classification and provider transmission policy enforcement.
- Added pre-transmission redaction for credentials, identity/contact patterns, and custom terms.
- Added conservative provider storage controls with test-environment storage disabled.
- Added privacy-safe provider audit metadata and organization-scoped retention cleanup.
- Added network-free privacy, cross-organization, redaction, audit, and retention tests.

## Sprint 5 — Production Office workflow integration

- Connected configured fake/OpenAI providers to all four governed Office Work Package routes.
- Added task, run, usage, provider-audit, package, and artifact persistence in one application flow.
- Added execution status lifecycle, cancellation persistence, partial/total failure handling, and
  organization-scoped idempotency keys.
- Connected the existing RBAC-protected Work Package endpoint to a thin application service.
- Added network-free fake and mocked OpenAI production integration tests.
## Sprint 5 — Production smoke test and release readiness

- Added a network-free release smoke suite covering login, mocked OpenAI and fake execution, orchestration, persistence, telemetry, audit, resilience, privacy, cancellation, and retention.
- Added an explicit opt-in live OpenAI structured-output connectivity command that prints metadata only.
- Added v0.3 release notes, deployment checklist, rollback guidance, known issues, and the AI provider runbook.
## Sprint 6 — Knowledge domain and persistence

- Added organization-scoped source, document, immutable version, chunk, ingestion job, access policy, and citation models.
- Added content-hash/version duplicate constraints, classification/status checks, lineage indexes, and composite tenant foreign keys.
- Added Alembic revision `20260720_0007` and knowledge model/migration tests.
## Sprint 6 — Secure document ingestion

- Added validated TXT, Markdown, PDF, DOCX, CSV, XLSX, and explicit unsupported HWP/HWPX parser adapters.
- Added SHA-256 duplicate handling, conservative normalization, malware scanner boundary, temporary-file cleanup, and metadata extraction.
- Added organization-scoped ingestion persistence, lifecycle states, parsed immutable version content, RBAC permission seeds, configuration, migration, and network-free tests.
## Sprint 6 — Deterministic chunking and citations

- Added versioned deterministic paragraph/page/section/table/list chunking with bounded overlap and SHA-256 identifiers.
- Added stable token-estimator contracts, source block ranges, structured locators, source-type citation labels, and completeness assessment.
- Added organization-scoped chunk/citation persistence, config-hash idempotency, retained chunk-set revisions, migration `20260720_0009`, and network-free tests.

- Added provider-independent deterministic embeddings, revisioned vector persistence, privacy enforcement, cosine retrieval, citation propagation, and migration 0010.

- Added deterministic lexical/vector hybrid fusion, explainable reranking, duplicate controls, evidence sufficiency, and privacy-safe retrieval telemetry.

- Added governed MCP registry, policy, validation, audit, health, cache, connector evidence mapping, and migration 0011.

- Added governed rules-based knowledge routing, evidence merge/ranking, conflict and gap detection, confidence evaluation, and privacy-safe route audit.

- Integrated governed RAG/MCP evidence packages into Office Agent context, citation propagation, review policy, Work Package metadata, and migration 0012.

- Added organization-scoped knowledge access/classification enforcement, query-time retrieval filtering, prompt-injection and DLP detection, append-only unified audit metadata, legal hold, retention dry-run, governed archive/delete/reclassification, rate limiting, cache invalidation, and incident hooks (Sprint 6 Checkpoint 9).

- Added Sprint 6 v0.4 synthetic E2E fixtures, network-free smoke/e2e/integration release gates, performance baseline metadata, release checklist, rollback guidance, and known-issue documentation (Sprint 6 v0.4 release preparation).
