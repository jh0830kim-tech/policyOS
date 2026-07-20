# Environment Variables

Expected categories:
- application settings
- database URL
- Redis URL
- JWT secret and algorithm
- token expiration
- AI provider credentials
- logging and monitoring

Provide `.env.example` with placeholders only.

## OpenAI provider resilience

`OPENAI_TIMEOUT_SECONDS` caps the complete provider operation, including retry waits.
`OPENAI_MAX_RETRIES` is the number of retries after the initial attempt.
`OPENAI_RETRY_BACKOFF_SECONDS` is the base for exponential delays (`base * 2^retry_count`).
The OpenAI SDK retry count is fixed at zero so SDK and application retries never overlap.
Rate limits, server failures, and connection failures are retryable. Authentication,
permission, invalid request, schema/output validation, incomplete output, and refusal are not.
Provider errors expose only PolicyOS-safe codes; raw responses, credentials, and prompts are
never written to telemetry.

## AI privacy configuration

- `OPENAI_STORE_RESPONSES=false`: provider response storage; always false in test environments.
- `AI_DEFAULT_DATA_CLASSIFICATION=internal`: default classification for new AI contexts.
- `AI_ALLOW_CONFIDENTIAL_EXTERNAL_PROVIDER=false`: organization-level confidential-data opt-in.
- `AI_PROVIDER_AUDIT_RETENTION_DAYS=365`: provider audit metadata retention.
- `AI_USAGE_RETENTION_DAYS=365`: usage telemetry retention before fields are cleared.
- `AI_REDACTION_ENABLED=true`: enable the transmission redaction hook.
- `AI_REDACTION_CUSTOM_TERMS=`: comma-separated organization-specific terms to mask.

Custom terms are policy configuration, not a secret store. Do not place credentials in this value.

## Production workflow provider selection

Local and test environments default to `AI_PROVIDER=fake`. Production deployments explicitly set
`AI_PROVIDER=openai` and supply `OPENAI_API_KEY` through the approved secret mechanism, or select
`disabled` to fail safely. The composition root applies the configured model, store, timeout,
application retry, redaction, classification, confidential-data policy, and audit retention settings.
No live provider call is made by the automated test suite.
## Sprint 5 release gates

Before enabling `AI_PROVIDER=openai`, complete the environment and migration checklist in `RELEASE_NOTES_v0.3.md`, run `ruff check .`, `pytest`, and `pytest -m smoke`, and verify the configured retention/privacy values. `RUN_OPENAI_LIVE_TESTS` is intentionally absent from `.env.example`; set it temporarily to `1` only for an approved staging invocation of `python -m scripts.openai_smoke_test`. Automated tests never make external provider calls.
## Knowledge ingestion configuration

- `KNOWLEDGE_MAX_UPLOAD_BYTES=25000000`: hard pre-parse byte limit.
- `KNOWLEDGE_ALLOWED_EXTENSIONS=.txt,.md,.pdf,.docx,.csv,.xlsx,.hwp,.hwpx`: allowlist; HWP/HWPX still return unsupported until an adapter exists.
- `KNOWLEDGE_TEMP_DIRECTORY=`: private temporary root; empty uses the OS temporary directory.
- `KNOWLEDGE_INGESTION_TIMEOUT_SECONDS=30`: total parser timeout.

NoOp malware scanning is local/test only. Production currently fails closed through `DisabledMalwareScanner` until an approved real scanner is injected. The temporary root must be writable only by the application identity and monitored for cleanup failures.

## Sprint 6 Checkpoint 4: Embedding and vector retrieval

- Embeddings use a provider-independent gateway (`fake`, `disabled`, or explicitly configured `openai`).
- Model, dimension, chunking configuration, normalization strategy, provider, and policy version participate in immutable embedding revisions.
- The default fake provider is SHA-256 deterministic and performs no network I/O. OpenAI uses bounded application retries while SDK retries are disabled.
- External embedding follows provider transmission policy: restricted content is blocked and confidential content requires organization policy. Embedding records never duplicate source text or secrets.
- Current persistence stores validated vectors as JSON for PostgreSQL/SQLite compatibility. `VectorStore` isolates this detail; production pgvector indexing is planned and must fail clearly if the extension is unavailable.
- Retrieval enforces organization, model, dimension, classification, document/source, effective-date, top-k, and minimum-score filters. Cosine scores remain in the native [-1, 1] range.
- Usage records capture input count/tokens, batch/retry count, latency, provider request ID and nullable estimated cost; pricing is not hard-coded.
- Public embedding/search HTTP endpoints are deferred; application services are the authorization-ready boundary.

## Sprint 6 Checkpoint 5: Hybrid retrieval and reranking

Hybrid retrieval normalizes Unicode with NFKC, preserves quoted phrases, removes forbidden controls, and uses a conservative Korean-aware tokenizer. The tokenizer only strips a small configured suffix set; it does not invent synonyms, and a future morphological adapter can replace it.

Lexical retrieval uses deterministic BM25-like term-frequency/IDF scoring with phrase, title, heading, and section boosts. Vector candidates reuse the provider-independent vector boundary, while production PostgreSQL full-text search remains behind an adapter protocol. Weighted max-normalized lexical scores and cosine-normalized vector scores are combined with reciprocal-rank fusion; stable chunk IDs break ties.

Deterministic reranking exposes authority, freshness, citation, and duplicate adjustments without hidden reasoning. Authority categories are configurable and never replace relevance. Exact duplicates within one source are collapsed, neighboring document results receive a penalty, and per-document/source caps preserve diversity. Evidence is sufficient, partial, or insufficient based on score, citation quality, official-source presence, freshness, and question-specific legal/budget needs.

Search telemetry stores a salted organization-scoped query hash, counts, filters, latency, provider/model, reranker, warnings, and evidence status. It never stores query or result text. Public `/knowledge/search/hybrid` routing is deferred until the application container can inject organization-scoped lexical/vector repositories; the service already enforces permissions and safe bounded contracts.

## Sprint 6 Checkpoint 6: Governed MCP gateway

MCP is an untrusted integration boundary governed by explicit server and tool allowlists. Five disabled-by-configuration connector definitions cover law, minutes, finance, internal documents, and public data. Fake clients are the test default; remote networking and local process execution require explicit opt-in and are not implemented as implicit fallbacks.

Every call validates active membership, RBAC permission, organization scope, classification, read/write consequences, human approval, JSON schemas, paths, URLs, result size, and suspicious prompt/script markers. Restricted data cannot leave PolicyOS; confidential external transmission needs organization policy. Cancellation propagates, retries are bounded to transient failures, and stale cache usage is disclosed.

Audit records contain identifiers, policy decisions, timing, retry/result counts and status only—never arguments, results, credentials, tokens, or document text. Cache keys are organization/classification scoped and hash normalized parameters. Connector outputs become untrusted `EvidenceCandidate` records with provenance and incomplete-citation warnings. Real national law, meeting, budget MCP connections, distributed cache, and management/execution HTTP APIs remain follow-up work.

## Sprint 6 Checkpoint 7: Governed knowledge routing

The Knowledge Router uses deterministic rules—not an LLM planner—to classify policy, legal, ordinance, minutes, budget, statistics, internal-document, speech, press, combined, and unknown queries. Its route matrix selects organization-scoped Hybrid RAG and allowlisted MCP connectors, runs independent sources concurrently within one timeout budget, preserves partial results, and records denied or failed sources instead of reporting false success.

Evidence is normalized into one contract, deduplicated by stable external/citation/content identity, capped per source/document, and ranked with retrieval relevance, official-source category, citation completeness, freshness and stable identifiers. Different institutions remain distinct. Legal effective-date and budget fiscal-year conflicts are surfaced without silently choosing a winner. Type-specific gaps lower confidence and material/critical gaps require human review.

Fallback provenance, stale warnings, source failures, permissions and review requirements remain visible. Restricted data cannot use external routes, and MCP receives only connector-specific parameters and opaque request metadata. Router audit stores query hashes, selected/executed/denied sources, counts, status, confidence and latency—never query text, evidence text, credentials, raw MCP results or reasoning. Real connector wiring and `/api/v1/knowledge/query` remain follow-up application-container work.

## Sprint 6 Checkpoint 9: Knowledge security governance

Knowledge operations are authorized at request/query time using organization, active membership, permission, source policy, revocation state, classification, purpose, and approval context. Public/internal are ordinarily eligible; confidential requires explicit organization authorization; restricted evidence is never sent to external providers or MCP and excerpts are length-limited. Child chunks, citations, embeddings, and derived artifacts must retain at least the parent's classification. Classification downgrade requires administrative review, approval, and a clear DLP scan.

Uploaded documents, retrieved evidence, and MCP results are untrusted data, never system instructions. Deterministic prompt-injection and DLP scanners record only categories, severity, and counts. High/critical findings are excluded from agent context or force review. Regex heuristics can produce false positives (for example, phone/account patterns overlap) and require human review; raw matches, prompts, documents, MCP output, credentials, and hidden reasoning are never audited.

Unified audit events are append-only and organization-scoped, with event/time, task/package, and source/document indexes. Legal holds block cleanup and purge. Retention begins in dry-run mode, preserves current versions and approved artifacts, and deletes embeddings before parent chunks. Physical purge requires approval. Reclassification invalidates retrieval/embedding caches; membership, role, source-policy, document, or organization-policy changes are enforced on the next request. Immediate termination of already-running distributed sessions remains an operational follow-up.

Operational permissions: `knowledge.read` covers read/search; `knowledge.manage` covers ingest/embed/archive/source management; `knowledge.reclassify` plus approval covers downgrade; `knowledge.delete` plus approval covers purge; `knowledge.export` plus approval covers export; `mcp.execute` covers governed tools; `audit.read` is required for organization audit queries. Cross-organization access and quota pooling are prohibited. Rate limits are scoped by organization, user, and action and expose only safe retry-after metadata. Incident sinks are pluggable and disabled by default; no SIEM, chat, or email call is made by the built-in fake/disabled sinks.
## Sprint 6 v0.4 release candidate

The governed Knowledge Platform release candidate is covered by a synthetic, network-free E2E flow from login and organization RBAC through combined internal RAG/fake MCP routing, cited evidence merge, conflict/gap and confidence assessment, eight-agent Chief Secretary orchestration, reviewable Work Package/artifact persistence, and safe API output. All fixture facts are explicitly fictional. Default CI forbids real OpenAI, remote MCP, and subprocess MCP calls.

Release operation requires Alembic head `20260720_0013`, reviewed environment settings, backup/rollback, retention dry-run, legal-hold protection, privacy incident handling, and provider/MCP outage procedures. See `RELEASE_NOTES_v0.4.md` and `RUNBOOK.md`. Production pgvector/ANN, real government connectors, workers, Redis coordination, scheduled cleanup, SIEM integrations, and live staging verification remain deferred.