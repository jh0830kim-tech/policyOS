# PolicyOS v0.3 Release Notes

Release candidate: Sprint 5 OpenAI Provider Integration

## Highlights

- Added a provider-neutral OpenAI Responses API adapter with strict Structured Outputs.
- Connected authenticated Work Package requests to Chief Secretary orchestration and reviewable artifacts.
- Persisted organization-scoped usage telemetry and privacy-safe provider audit metadata.
- Added bounded timeout/retry behavior, cancellation propagation, safe provider error mapping, and privacy transmission controls.
- Added a network-free Sprint 5 release smoke suite and an explicit opt-in live connectivity command.

## Release checklist

### Required environment

- [ ] `APP_ENV` is set to the target environment.
- [ ] `SECRET_KEY` is unique, secret-managed, and at least 32 bytes.
- [ ] `DATABASE_URL` and `REDIS_URL` target the correct environment.
- [ ] `AI_PROVIDER` is explicitly `openai` or `disabled` in production; `fake` is rejected to `disabled`.
- [ ] For OpenAI: `OPENAI_API_KEY`, `OPENAI_MODEL`, `OPENAI_TIMEOUT_SECONDS`, `OPENAI_MAX_RETRIES`, and `OPENAI_RETRY_BACKOFF_SECONDS` are reviewed.
- [ ] `OPENAI_STORE_RESPONSES=false` unless an approved retention decision permits storage.
- [ ] Classification, confidential transmission, redaction, audit retention, and usage retention settings are approved.

### Migration and validation

- [ ] Back up the production database and record the current Alembic revision.
- [ ] Review migrations `20260720_0003` through `20260720_0006` and run `alembic upgrade head`.
- [ ] Confirm `alembic heads` reports only `20260720_0006`.
- [ ] Run `ruff check .`, `pytest`, and `pytest -m smoke` without live network access.
- [ ] In an approved staging environment only, optionally run `python -m scripts.openai_smoke_test` with `RUN_OPENAI_LIVE_TESTS=1`.
- [ ] Verify health, login, Work Package creation, review status, telemetry, and audit metadata.

### OpenAI safety checks

- [ ] The key is injected by the approved secret manager and is absent from logs and database records.
- [ ] The configured model supports Responses API Structured Outputs.
- [ ] SDK retries remain disabled; application retry limits and total timeout match the runbook.
- [ ] Restricted data is blocked and confidential data requires explicit policy approval.
- [ ] Provider request storage matches the organization's approved data policy.

### Rollback

- [ ] Set `AI_PROVIDER=disabled` first to stop new external transmissions.
- [ ] Drain or cancel in-flight requests and preserve their final status records.
- [ ] Roll back the application release before downgrading schema.
- [ ] If schema rollback is required, archive needed telemetry/audit data and downgrade one reviewed migration at a time to the recorded revision.
- [ ] Restore the database only as a last resort and validate organization isolation afterward.

## Known issues

- Work Package execution is synchronous in the HTTP request; a durable background queue is not yet implemented.
- A process crash after the initial `running` commit requires operational reconciliation.
- Concurrent requests using the same idempotency key can race at the unique constraint; automatic replay after a conflict is pending.
- Pricing is intentionally not hard-coded, so `estimated_cost` remains null until versioned pricing configuration exists.
- Retention cleanup is a manual service boundary; scheduling is not included.
- Live OpenAI validation depends on provider availability and is never part of automated pytest runs.
- Starlette TestClient currently emits one upstream httpx deprecation warning.

## Sprint 6 candidates

- RAG and organization-scoped knowledge retrieval with citation provenance.
- Durable background execution, recovery, and idempotency conflict replay.
- Versioned model pricing configuration and cost reporting.
- Scheduled retention cleanup and operational metrics/alerts.
- Provider fallback/circuit breaker evaluation without weakening privacy policy.