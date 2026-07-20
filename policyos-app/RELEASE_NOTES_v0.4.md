# PolicyOS v0.4 Release Notes

Release candidate: Sprint 6 Governed Knowledge Platform

## Highlights

- Added organization-scoped knowledge sources, immutable document versions, secure ingestion, deterministic chunking and stable citations.
- Added provider-neutral embeddings, hybrid retrieval, governed MCP gateway contracts, evidence routing, conflict/gap assessment, and evidence-aware AI Office execution.
- Added classification enforcement, prompt-injection/DLP detection, unified audit metadata, legal hold, retention planning, reclassification, rate limiting, and incident hooks.
- Added a deterministic network-free E2E scenario covering login, RBAC, combined internal/MCP evidence, Chief Secretary orchestration, Work Package and artifact persistence.

## Release readiness checklist

### Required environment

- [ ] Set `APP_ENV`, secret-managed `SECRET_KEY`, `DATABASE_URL`, and `REDIS_URL`.
- [ ] Select `AI_PROVIDER` and `EMBEDDING_PROVIDER`; production must not use fake providers.
- [ ] For OpenAI, review key/model, timeout, retries, backoff, response storage, redaction, classification, and audit retention settings.
- [ ] Review knowledge ingestion, chunking, embedding, hybrid search, MCP allowlists/timeouts/cache, DLP, prompt-injection, rate-limit, legal-hold, and retention settings in `.env.example`.
- [ ] Keep remote/local-process MCP disabled until each connector and credential scope is approved.

### Database and migration

- [ ] Back up PostgreSQL and record the deployed Alembic revision.
- [ ] Review revisions through `20260720_0013`; verify one head and generate upgrade SQL before deployment.
- [ ] Validate migrations against a production-compatible PostgreSQL staging database.
- [ ] Plan pgvector storage and ANN indexes before replacing the current JSON/in-memory vector boundary.

### Operations and security

- [ ] Confirm organization isolation, active membership, RBAC, restricted transmission blocks, and audit query permissions.
- [ ] Start retention in dry-run mode; approve legal-hold, purge, archive, and restore procedures.
- [ ] Validate backup restoration and audit preservation before enabling cleanup.
- [ ] Exercise privacy incident, OpenAI outage, MCP outage, cancellation, stale-cache, and rollback runbooks.
- [ ] Confirm prompts are present in the deployment artifact and that test fixtures are excluded from production knowledge ingestion.

### Network-free validation

Run `ruff check .`, `pytest -q`, and the `smoke`, `e2e`, and `integration` marker suites. These tests must not call OpenAI, remote MCP, or subprocess MCP.

Live checks are staging-only and explicit: `RUN_OPENAI_LIVE_TESTS=1` enables the existing OpenAI smoke command. `RUN_MCP_LIVE_TESTS=1` is reserved for Sprint 7 connector smoke tooling and currently performs no automated call.

## Deterministic E2E scenario

The synthetic transit-assistance scenario authenticates an active member, creates a combined legal/minutes/budget/policy query, executes internal RAG plus fake law, minutes, finance, and public-data routes, merges five cited evidence items, calculates confidence/sufficiency and review status, runs the full eight-agent Office workflow, and persists one task, eight runs, one Work Package, and eight reviewable artifacts. Fixture titles, citations, dates, and amounts are explicitly fictional.

Failure coverage maps existing tests and the release integration suite to law unavailable, minutes timeout, stale finance fallback, restricted transmission, incomplete citation, conflicting law/budget versions, wrong fiscal year, partial/total provider failure, timeout, cancellation, and evidence unavailable. No failure is reported as success.

## Test-environment performance baseline

Observed metadata is diagnostic, not an SLA: fixture source latency is 1 ms per fake response; Router records total latency, evidence count, citation count, fallback count, conflicts, and gaps; the HTTP E2E test records end-to-end elapsed time and completed under one second in the release workstation run. Ingestion, chunking, fake embedding, hybrid retrieval, Router, and Agent tests remain deterministic and network-free. Production targets require staging measurement with PostgreSQL, Redis, pgvector, real document sizes, and approved providers.

## Rollback

1. Disable external AI, embeddings, and remote/local MCP execution.
2. Stop new Work Package and ingestion requests; drain or cancel in-flight work.
3. Preserve audit, legal-hold, artifact, and telemetry records and take a database backup.
4. Roll back application code before schema. Downgrade only one reviewed revision at a time from the recorded revision.
5. Restore the database only as a last resort, then verify migration head, organization isolation, citations, artifacts, audit, and retention dry-run.

## Known issues and deferred work

- Real national-law, council-minutes, and budget MCP connectors are not connected.
- pgvector production adapter/ANN indexes and production-compatible PostgreSQL migration CI are pending.
- Durable background workers/queues, distributed cache, Redis rate limiter, and scheduled retention cleanup are pending.
- Live OpenAI/MCP staging validation is operational opt-in and not part of CI.
- Starlette TestClient emits an upstream httpx deprecation warning.
- Korean morphology ranking, OCR, HWP/HWPX production adapters, SIEM/notification adapters, and immediate distributed-session revocation are pending.
- Prompt files are included by the Docker deployment context but not configured as Python wheel package-data.
- Unified audit hooks and the new governance management API routes are not yet wired into every production flow.
- Dashboard/metaverse presentation work remains outside this release.

## Sprint 7 direction

Implement approved real MCP connectors and credential management, PostgreSQL/pgvector production search, background execution, distributed cache/rate limiting, scheduled retention, staging live tests, operational telemetry, and remaining security/audit API wiring.