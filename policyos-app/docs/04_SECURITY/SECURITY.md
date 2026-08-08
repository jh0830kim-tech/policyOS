 Security Baseline

## Security goals
- Protect credentials and personal data.
- Enforce organization isolation.
- Prevent unauthorized agent and tool access.
- Maintain reliable audit trails.
- Support incident response.

## Minimum controls
- Argon2 password hashing
- signed JWT access tokens
- short token lifetime
- RBAC authorization
- secret management through environment or secret store
- input validation
- rate limiting for authentication endpoints
- audit logging for privileged actions
- dependency and vulnerability monitoring

## Prohibited
- plain-text passwords
- secrets in source control
- authorization based only on UI visibility
- agent access to unrestricted organization data

## Login rate-limiting integration point
Login rate limiting must run before credential verification, preferably at the API gateway or as a dedicated FastAPI dependency on `POST /api/v1/auth/login`. The limiter should key conservatively on source network and a privacy-preserving account identifier, return `429` without revealing account existence, and emit operational metrics. Redis-backed limiting is deferred until PolicyOS establishes a shared rate-limit subsystem; individual routes must not create ad hoc Redis policies.
## Operational artifact controls
External-facing drafts remain `needs_review` until an authorized user with `artifact.review` approves or rejects them. All artifact and package reads are organization-scoped. Raw provider responses, secrets, and hidden reasoning are prohibited from persistence and API responses.

## External AI provider controls

Every real-provider request carries organization, user, task, and data-classification context.
Restricted data is denied. Confidential data requires an explicit organization policy or scoped
approval; public and internal data may proceed only when the organization allows the provider,
the caller has `agent.execute`, the tenant context matches, and the provider is approved. Policy
denials use the safe `provider_policy_blocked` code and do not expose provider or policy internals.
Provider audit APIs are not exposed to ordinary users. Any future audit read endpoint must require
an audit/admin permission and enforce organization scoping.

## Production workflow authorization

The Work Package router delegates execution only after authentication, active-membership resolution,
and exact `agent.execute` authorization. The application service receives the resolved organization
and user identifiers and uses them for every task, run, package, artifact, audit, and provider
transmission context. Read/review routes retain organization predicates. Provider failures are mapped
to allowlisted codes and messages without exposing SDK exceptions or stack traces.
## Secure document ingestion

Uploads are checked for allowed extension and MIME pairing, configured byte limit, empty content, normalized filename, traversal, executable/script suffixes, executable signatures, and extension/content magic before parsing. SHA-256 duplicate detection is scoped to organization and source. Malware scanning is an injected protocol and always runs before parser execution; production ingestion fails closed until a real scanner adapter is configured. HWP/HWPX are explicitly unsupported, encrypted or textless PDFs fail safely, embedded DOCX objects are rejected, spreadsheet formulas are never executed, and row/column limits constrain tabular parsers. Temporary files use a configured private directory and are removed on success or failure.
## Chunk and citation isolation

Chunk organization and classification are inherited only from the persisted document version; callers cannot downgrade them. Version, document, source, chunk, and citation queries include organization predicates and composite tenant foreign keys. Restricted chunks remain local and are not transmitted to providers. Chunk hashes, strategy/config hashes, and source block ranges make overlap and repeated processing auditable without inventing source pages, sections, or dates.

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

## Connector security

HTTPS, normalized-origin allowlisting, and rejection of URL userinfo, fragments, query secrets, and CR/LF headers protect requests. Every DNS answer must be globally routable. The connector network backend pins each socket to an IP validated during that connection while retaining the original hostname for TLS SNI and certificate verification; mixed, empty, malformed, or non-global answers fail closed. Redirects and environment proxies are disabled, and callers cannot substitute a production transport or disable private-network protection. Secrets resolve only at call time. Audit metadata recursively blocks secret and raw-response fields.

## Knowledge provider trust boundary
Provider selection is organization-scoped and capability allowlisted. Restricted data cannot use external providers; confidential external transmission requires explicit authorization. API callers cannot choose adapter classes, MCP servers/tools, commands, endpoints, or transports. Provider instructions are treated as untrusted data.
## Sprint 15 CP9 Runtime API transport

JWT signature verification alone does not establish trust. Issuer, audience, temporal, and bounded reference claims are required and validated before verified claims create a trusted principal. Every Runtime request must then bind that principal, an active user or service principal, active membership, exact organization, and persisted/configured `Tenant-Organization` relationship. Exact `runtime.read`, `runtime.invoke`, or `runtime.reconcile` permission is also required. `CP9-Gate-Tenant-Organization-Binding` merged in PR #64 with explicit persistence and a trusted resolver; Runtime permission definitions and governed grant/revoke provisioning merged through PR #67. Organization ID is never inferred to be tenant ID.

Organization membership alone cannot create Runtime tenant scope. The authoritative persisted binding is lifetime one-to-one: neither an organization nor a Runtime tenant can be rebound, and Organization ID is never reused as tenant ID. Tenant identity is never selected by transport input or created through hidden generation, migration backfill, or a production default. The binding supplies the immutable classification ceiling. Missing, inactive, or revoked bindings fail closed with non-disclosure. Superuser, system-role, admin-role, service-account, and break-glass bypasses do not exist; every principal requires active organization and membership checks plus the exact binding. Binding records store no raw credential, secret, or provider body. Self-contained migration `20260807_0018` enforces lifetime uniqueness and fails closed before downgrade when rows exist; PostgreSQL 16 verification covers explicit persistence. Routes must not directly access Runtime Persistence or Adapters, and no production Runtime route exists yet.

All body, header, query, and path values are untrusted. HTTP callers cannot directly supply internal Authority, Plan, State, Lifecycle, Permit, Registry, Audit, Adapter, Persistence, credential, retry, dead-letter, timestamp, digest, or receipt facts. Future routes in `app.api` will validate strict `app.schemas` contracts and call only the trusted application facade, which resolves server-side facts and invokes Runtime Orchestration. Direct ORM, Persistence, or Adapter access is prohibited. The trusted application facade remains a blocker, and no production Runtime route exists yet.

Invocation mutations will require transport idempotency persistence and a bounded `Idempotency-Key` scoped to tenant, organization, principal, operation, and command version; that persistence remains a separate blocker. Body size, collection size, content type, headers, rate, timeout, cancellation, and public errors are bounded. No raw credential, body, provider response, internal exception, SQL detail, or cross-tenant existence is exposed.

Internal due, claim, lease, `DELIVERING`, lifecycle append, retry, and dead-letter operations are not public endpoints. External business-effect exactly-once is not guaranteed. Real provider/MCP/connector Adapters and Worker, queue, polling loop, and scheduler behavior remain excluded; Workers are CP10 scope. `CP9-Gate-API-Contracts` is merged in PR #61, the Auth Claims Gate in PR #62, Tenant-Organization Binding Governance in PR #63, and the binding implementation in PR #64. Production Runtime routes remain Planned / Blocked on the separate blockers above.

Runtime permission definitions `runtime.read`, `runtime.invoke`, and `runtime.reconcile` are persisted by definition-only migration `20260807_0019`; a definition is not authority. Explicit `RolePermission` plus `MembershipRole`, active user/membership/binding, exact organization/tenant scope, and classification within the ceiling are required. No automatic grants, including admin/system grants, or existing role/membership backfill occurs. Wildcard and cross-organization substitution fail closed. Grant link deletion is visible on the next database resolution. Permission facts are not accepted from an HTTP body, and no raw bearer token, signing secret, or provider body is stored. Governed production grant/revoke provisioning and immutable evidence merged in PR #67 with migration head `20260808_0020`; trusted bootstrap assignment remains outside the Runtime API. CP9 Runtime API: Planned / Blocked. CP10: Planned.
## Sprint 15 CP9 Runtime permission grant/revoke governance

ADR-088 defines exact `runtime.grant.manage` authority as definition-only with automatic grant 0;
broad `rbac:manage`, wildcard, prefix, and substring forms cannot substitute for it. The service
may target only `runtime.read`, `runtime.invoke`, and `runtime.reconcile` and cannot grant its own
management permission. Self-escalation and automatic admin/system grants are prohibited. Initial
management authority belongs to a separately trusted bootstrap/operator procedure outside the
public Runtime API; no break-glass path is introduced.

The transaction revalidates the active actor, user, membership, exact organization, active
Tenant-Organization binding, exact tenant, exact management authority, organization-scoped target
role, and permission ID/key pair before storage. Inactive/revoked actors, memberships, or bindings
and cross-scope substitution fail closed. The classification ceiling is evidence and never expands
authority. HTTP values cannot supply trusted actor, authority, permission, tenant, binding, digest,
timestamp, or receipt facts.

Existing `RolePermission` remains the active projection. Migration `20260808_0020` adds immutable
append-only `runtime_permission_grant_events` evidence for provenance, receipt, history, request
digest, exact replay, and monotonic revision. Same-request identical facts return the original
receipt; changed facts, digest, or operation conflict. Fixed lock order, expected revision,
projection uniqueness, and scoped request uniqueness linearize concurrent grant, revoke, and
authority-revocation races. Projection and evidence commit atomically.

No inferred existing-grant backfill, hidden UUID/time generation, arbitrary JSON authority fact,
raw token, signing secret, credential, or provider body is permitted. Generic audit retention
cannot delete authoritative grant evidence. Grant governance merged in PR #66 and production
provisioning in PR #67. The permission-fact resolver, transport idempotency persistence, facade,
and routes remain unimplemented. Production Runtime routes and CP10 worker/queue/polling/scheduler
behavior are outside this governance gate.

### CP9 governed Runtime permission provisioning

Production provisioning preserves `RolePermission` as the active projection and records every
committed grant or revoke in the append-only `runtime_permission_grant_events` ledger in the same
transaction. `runtime.grant.manage` is definition-only with zero automatic grants; only
`runtime.read`, `runtime.invoke`, and `runtime.reconcile` are eligible targets. Exact replay is
receipt-stable, conflicting replay and concurrent state changes fail closed, and transport,
permission-fact resolution, application facade/routes, outbox, and CP10 remain deferred.
Production grant/revoke provisioning merged in PR #67; bootstrap authority remains external.
