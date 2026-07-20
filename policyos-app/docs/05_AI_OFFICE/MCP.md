# MCP Integration

MCP servers may expose approved tools and data sources to agents.

## Requirements
- explicit server allowlist
- tool-level permissions
- organization-scoped credentials
- input and output validation
- timeout and retry policy
- audit logging
- human approval for consequential write actions

MCP is an integration boundary, not a trust boundary.

## Sprint 6 Checkpoint 6: Governed MCP gateway

MCP is an untrusted integration boundary governed by explicit server and tool allowlists. Five disabled-by-configuration connector definitions cover law, minutes, finance, internal documents, and public data. Fake clients are the test default; remote networking and local process execution require explicit opt-in and are not implemented as implicit fallbacks.

Every call validates active membership, RBAC permission, organization scope, classification, read/write consequences, human approval, JSON schemas, paths, URLs, result size, and suspicious prompt/script markers. Restricted data cannot leave PolicyOS; confidential external transmission needs organization policy. Cancellation propagates, retries are bounded to transient failures, and stale cache usage is disclosed.

Audit records contain identifiers, policy decisions, timing, retry/result counts and status only—never arguments, results, credentials, tokens, or document text. Cache keys are organization/classification scoped and hash normalized parameters. Connector outputs become untrusted `EvidenceCandidate` records with provenance and incomplete-citation warnings. Real national law, meeting, budget MCP connections, distributed cache, and management/execution HTTP APIs remain follow-up work.

## Sprint 6 Checkpoint 7: Governed knowledge routing

The Knowledge Router uses deterministic rules—not an LLM planner—to classify policy, legal, ordinance, minutes, budget, statistics, internal-document, speech, press, combined, and unknown queries. Its route matrix selects organization-scoped Hybrid RAG and allowlisted MCP connectors, runs independent sources concurrently within one timeout budget, preserves partial results, and records denied or failed sources instead of reporting false success.

Evidence is normalized into one contract, deduplicated by stable external/citation/content identity, capped per source/document, and ranked with retrieval relevance, official-source category, citation completeness, freshness and stable identifiers. Different institutions remain distinct. Legal effective-date and budget fiscal-year conflicts are surfaced without silently choosing a winner. Type-specific gaps lower confidence and material/critical gaps require human review.

Fallback provenance, stale warnings, source failures, permissions and review requirements remain visible. Restricted data cannot use external routes, and MCP receives only connector-specific parameters and opaque request metadata. Router audit stores query hashes, selected/executed/denied sources, counts, status, confidence and latency—never query text, evidence text, credentials, raw MCP results or reasoning. Real connector wiring and `/api/v1/knowledge/query` remain follow-up application-container work.

## Sprint 6 Checkpoint 8: Evidence-aware AI Office

The production Office application service can receive an injected governed Knowledge Router before specialist execution. It builds one organization-scoped query, rejects wholly unavailable evidence, converts the router result to a minimized `OfficeEvidencePackage`, and stores only query/route identifiers plus counts, confidence, sufficiency, failures, and fallback status on the Work Package.

`AgentContext` carries the optional package. The Chief Secretary workflow deterministically selects legal evidence for Legal Review, budget evidence for Budget Analysis, statistical evidence for Statistics, and approved cited facts for public-facing agents. Safe excerpts, classifications, stable evidence IDs and existing citation IDs propagate through AgentResult and artifact structured payloads; agents cannot create substitute citations. All approved prompt files instruct agents to use supplied evidence only and expose conflicts, gaps, stale sources and unsupported claims.

Partial/insufficient evidence, material gaps, unresolved conflicts, incomplete or stale citations, public-facing artifacts, unsupported claims, or partial Agent failures require review. Approval is never automatic. Evidence-unavailable execution stops before provider calls. Existing timeout, cancellation, privacy, provider telemetry and artifact review controls remain authoritative. API request schemas accept legal/budget/minutes workflows and source/date/fiscal context; production router/executor composition in the HTTP dependency container remains follow-up work.

## Sprint 6 Checkpoint 9: Knowledge security governance

Knowledge operations are authorized at request/query time using organization, active membership, permission, source policy, revocation state, classification, purpose, and approval context. Public/internal are ordinarily eligible; confidential requires explicit organization authorization; restricted evidence is never sent to external providers or MCP and excerpts are length-limited. Child chunks, citations, embeddings, and derived artifacts must retain at least the parent's classification. Classification downgrade requires administrative review, approval, and a clear DLP scan.

Uploaded documents, retrieved evidence, and MCP results are untrusted data, never system instructions. Deterministic prompt-injection and DLP scanners record only categories, severity, and counts. High/critical findings are excluded from agent context or force review. Regex heuristics can produce false positives (for example, phone/account patterns overlap) and require human review; raw matches, prompts, documents, MCP output, credentials, and hidden reasoning are never audited.

Unified audit events are append-only and organization-scoped, with event/time, task/package, and source/document indexes. Legal holds block cleanup and purge. Retention begins in dry-run mode, preserves current versions and approved artifacts, and deletes embeddings before parent chunks. Physical purge requires approval. Reclassification invalidates retrieval/embedding caches; membership, role, source-policy, document, or organization-policy changes are enforced on the next request. Immediate termination of already-running distributed sessions remains an operational follow-up.

Operational permissions: `knowledge.read` covers read/search; `knowledge.manage` covers ingest/embed/archive/source management; `knowledge.reclassify` plus approval covers downgrade; `knowledge.delete` plus approval covers purge; `knowledge.export` plus approval covers export; `mcp.execute` covers governed tools; `audit.read` is required for organization audit queries. Cross-organization access and quota pooling are prohibited. Rate limits are scoped by organization, user, and action and expose only safe retry-after metadata. Incident sinks are pluggable and disabled by default; no SIEM, chat, or email call is made by the built-in fake/disabled sinks.
## Sprint 6 v0.4 release candidate

The governed Knowledge Platform release candidate is covered by a synthetic, network-free E2E flow from login and organization RBAC through combined internal RAG/fake MCP routing, cited evidence merge, conflict/gap and confidence assessment, eight-agent Chief Secretary orchestration, reviewable Work Package/artifact persistence, and safe API output. All fixture facts are explicitly fictional. Default CI forbids real OpenAI, remote MCP, and subprocess MCP calls.

Release operation requires Alembic head `20260720_0013`, reviewed environment settings, backup/rollback, retention dry-run, legal-hold protection, privacy incident handling, and provider/MCP outage procedures. See `RELEASE_NOTES_v0.4.md` and `RUNBOOK.md`. Production pgvector/ANN, real government connectors, workers, Redis coordination, scheduled cleanup, SIEM integrations, and live staging verification remain deferred.