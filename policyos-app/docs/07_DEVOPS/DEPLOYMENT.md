# Deployment

Environments:
- local
- test
- staging
- production

Each environment must have separate credentials and databases. Production deployment requires migration review, rollback plan, health verification, and release notes.
## AI provider release and rollback

Sprint 5 deployments must apply Alembic through revision `20260720_0006`, validate the network-free smoke suite, and enable OpenAI only after privacy and secret-management approval. During rollback, first switch `AI_PROVIDER=disabled`, drain in-flight work, roll back application instances, and downgrade additive migrations only when operationally necessary and after metadata archival. The full checklist and incident procedures are in `RELEASE_NOTES_v0.3.md` and `RUNBOOK.md`.

## Sprint 6 Checkpoint 6: Governed MCP gateway

MCP is an untrusted integration boundary governed by explicit server and tool allowlists. Five disabled-by-configuration connector definitions cover law, minutes, finance, internal documents, and public data. Fake clients are the test default; remote networking and local process execution require explicit opt-in and are not implemented as implicit fallbacks.

Every call validates active membership, RBAC permission, organization scope, classification, read/write consequences, human approval, JSON schemas, paths, URLs, result size, and suspicious prompt/script markers. Restricted data cannot leave PolicyOS; confidential external transmission needs organization policy. Cancellation propagates, retries are bounded to transient failures, and stale cache usage is disclosed.

Audit records contain identifiers, policy decisions, timing, retry/result counts and status only—never arguments, results, credentials, tokens, or document text. Cache keys are organization/classification scoped and hash normalized parameters. Connector outputs become untrusted `EvidenceCandidate` records with provenance and incomplete-citation warnings. Real national law, meeting, budget MCP connections, distributed cache, and management/execution HTTP APIs remain follow-up work.
