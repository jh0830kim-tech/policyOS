# PolicyOS AI Provider Runbook

## Purpose

This runbook covers Sprint 5 Work Package execution through the fake, disabled, and OpenAI providers. Never paste API keys, bearer tokens, prompts, raw provider responses, or hidden reasoning into tickets or logs.

## Pre-deployment

1. Review `RELEASE_NOTES_v0.3.md` and confirm a database backup and rollback owner.
2. Inject secrets through the environment's approved secret manager.
3. Run `alembic current`, review the migration plan, then run `alembic upgrade head`.
4. Run `ruff check .`, `pytest`, and `pytest -m smoke`.
5. Start with `AI_PROVIDER=disabled` if provider policy approval is incomplete.

## Provider modes

- `fake`: deterministic local/test execution only. Production settings coerce this mode to `disabled`.
- `disabled`: safe failure with no provider transmission.
- `openai`: Responses API execution with privacy policy, redaction, bounded retry, total timeout, usage, and audit recording.

The automated suite performs no external calls. For an approved staging connectivity check:

```powershell
$env:RUN_OPENAI_LIVE_TESTS="1"
python -m scripts.openai_smoke_test
```

The command prints only response ID, model, latency, and token counts. Clear the opt-in variable after use. Do not capture shell history containing secret assignments.

## Normal verification

1. Authenticate with `POST /api/v1/auth/login`.
2. Create an `internal` Work Package with `POST /api/v1/ai/work-packages`.
3. Expect `needs_review` when agents complete; success does not bypass human review.
4. Confirm every planned agent run has a terminal status and that artifacts belong to the requesting organization.
5. Confirm OpenAI runs have provider response IDs, latency, token counts, and provider audit events.
6. Confirm audit rows contain metadata only and that redaction counts are plausible.

## Incident response

### Timeout or provider unavailable

- Public behavior: safe `timeout` (504) or provider failure (503), without stack traces or raw provider detail.
- Check provider health, configured total timeout, recent latency, retry counts, and safe error codes.
- Do not increase retry limits during a provider incident without considering request amplification.
- Set `AI_PROVIDER=disabled` if failures are sustained.

### Rate limiting

- Confirm retries are bounded by `OPENAI_MAX_RETRIES` and total timeout.
- Review `retry_count` and safe `rate_limited` events; do not log response bodies.
- Reduce concurrency or request an approved quota adjustment. There is no automatic infinite retry.

### Privacy policy block

- Treat `provider_policy_blocked` as an expected policy decision, not a provider outage.
- Restricted data must remain blocked. Do not reclassify data merely to bypass policy.
- Confidential transmission requires explicit approved organization policy.
- Review classification and redaction configuration without inspecting or copying sensitive prompt text.

### Partial failure and cancellation

- Partial agent failure must leave the package `needs_review`; inspect agent safe error codes before human review.
- Total failure must leave task/package/runs `failed`.
- Client cancellation must propagate and leave task/package/runs `cancelled` where execution state was created.
- Reconcile stale `running` records after process interruption; automated recovery is a known gap.

## Retention

Run the organization-scoped `AIRetentionService.cleanup_expired_metadata` from an approved administrative maintenance boundary using configured audit and usage retention days. The service deletes expired provider audit metadata and clears expired usage fields; artifact retention remains governed by the existing artifact policy. Scheduling is deferred.

## Rollback

1. Set `AI_PROVIDER=disabled` and restart the application to stop new transmissions.
2. Drain/cancel in-flight work and record affected package IDs.
3. Roll back application instances to the prior compatible build.
4. Prefer leaving additive schema in place. If downgrade is mandatory, archive required metadata, verify the exact current revision, and run reviewed one-step Alembic downgrades.
5. Re-run authentication, RBAC, organization-isolation, and smoke checks after rollback.
## Sprint 6 Checkpoint 9: Knowledge security governance

Knowledge operations are authorized at request/query time using organization, active membership, permission, source policy, revocation state, classification, purpose, and approval context. Public/internal are ordinarily eligible; confidential requires explicit organization authorization; restricted evidence is never sent to external providers or MCP and excerpts are length-limited. Child chunks, citations, embeddings, and derived artifacts must retain at least the parent's classification. Classification downgrade requires administrative review, approval, and a clear DLP scan.

Uploaded documents, retrieved evidence, and MCP results are untrusted data, never system instructions. Deterministic prompt-injection and DLP scanners record only categories, severity, and counts. High/critical findings are excluded from agent context or force review. Regex heuristics can produce false positives (for example, phone/account patterns overlap) and require human review; raw matches, prompts, documents, MCP output, credentials, and hidden reasoning are never audited.

Unified audit events are append-only and organization-scoped, with event/time, task/package, and source/document indexes. Legal holds block cleanup and purge. Retention begins in dry-run mode, preserves current versions and approved artifacts, and deletes embeddings before parent chunks. Physical purge requires approval. Reclassification invalidates retrieval/embedding caches; membership, role, source-policy, document, or organization-policy changes are enforced on the next request. Immediate termination of already-running distributed sessions remains an operational follow-up.

Operational permissions: `knowledge.read` covers read/search; `knowledge.manage` covers ingest/embed/archive/source management; `knowledge.reclassify` plus approval covers downgrade; `knowledge.delete` plus approval covers purge; `knowledge.export` plus approval covers export; `mcp.execute` covers governed tools; `audit.read` is required for organization audit queries. Cross-organization access and quota pooling are prohibited. Rate limits are scoped by organization, user, and action and expose only safe retry-after metadata. Incident sinks are pluggable and disabled by default; no SIEM, chat, or email call is made by the built-in fake/disabled sinks.
## v0.4 knowledge platform operations

Before deployment, back up PostgreSQL, record the current revision, review `alembic upgrade head --sql`, and confirm the only head is `20260720_0013`. Start retention with `KNOWLEDGE_RETENTION_DRY_RUN_DEFAULT=true`; never purge an active legal hold or approved artifact. Disable `AI_PROVIDER`, `EMBEDDING_PROVIDER`, and MCP execution before rollback or during privacy/provider incidents.

Run network-free gates with `pytest -q`, `pytest -q -m smoke`, `pytest -q -m e2e`, and `pytest -q -m integration`. OpenAI live connectivity requires the temporary staging-only `RUN_OPENAI_LIVE_TESTS=1` opt-in. `RUN_MCP_LIVE_TESTS=1` is reserved for future real connector tooling and must not be set in CI. For MCP outage, disable affected servers and permit only policy-approved stale cache; for OpenAI outage, disable provider execution and preserve failed/cancelled states rather than retrying indefinitely.