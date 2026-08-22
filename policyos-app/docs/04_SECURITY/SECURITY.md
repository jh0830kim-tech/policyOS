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

Organization membership alone cannot create Runtime tenant scope. The authoritative persisted binding is lifetime one-to-one: neither an organization nor a Runtime tenant can be rebound, and Organization ID is never reused as tenant ID. Tenant identity is never selected by transport input or created through hidden generation, migration backfill, or a production default. The binding supplies the immutable classification ceiling. Missing, inactive, or revoked bindings fail closed with non-disclosure. Superuser, system-role, admin-role, service-account, and break-glass bypasses do not exist; every principal requires active organization and membership checks plus the exact binding. Binding records store no raw credential, secret, or provider body. Self-contained migration `20260807_0018` enforces lifetime uniqueness and fails closed before downgrade when rows exist; PostgreSQL 16 verification covers explicit persistence. Production Runtime routes call only the trusted application boundary and do not directly access Runtime Persistence or Adapters.

All body, header, query, and path values are untrusted. HTTP callers cannot directly supply internal Authority, Plan, State, Lifecycle, Permit, Registry, Audit, Adapter, Persistence, credential, retry, dead-letter, timestamp, digest, or receipt facts. Exactly three thin routes in `app.api` validate strict transport contracts and call only the trusted application facade, which resolves server-side facts and invokes Runtime Orchestration. Direct ORM, Persistence, or Adapter access is prohibited.

Invocation mutations require transport idempotency persistence and a bounded ASCII `Idempotency-Key` scoped to tenant, organization, principal, operation, explicit command version, and canonical command digest. Body size, collection size, content type, headers, rate, timeout, cancellation, and public errors are bounded. No raw credential, body, provider response, internal exception, SQL detail, or cross-tenant existence is exposed.

Internal due, claim, lease, `DELIVERING`, lifecycle append, retry, and dead-letter operations are not public endpoints. External business-effect exactly-once is not guaranteed. CP9 production routes and combined acceptance are merged through PR #121. CP10's delivery-only Worker governance, contracts, production composition, ordering correction, and PostgreSQL acceptance are merged through PR #144. The migration graph has the single head `20260808_0024`; CP9 and CP10 are complete within their approved Sprint 15 boundaries. Real provider/MCP/connector Adapters, queue infrastructure, autonomous scheduling, and external business-effect exactly-once remain excluded.

Runtime permission definitions `runtime.read`, `runtime.invoke`, and `runtime.reconcile` are persisted by definition-only migration `20260807_0019`; a definition is not authority. Explicit `RolePermission` plus `MembershipRole`, active user/membership/binding, exact organization/tenant scope, and classification within the ceiling are required. No automatic grants, including admin/system grants, or existing role/membership backfill occurs. Wildcard and cross-organization substitution fail closed. Grant link deletion is visible on the next database resolution. Permission facts are not accepted from an HTTP body, and no raw bearer token, signing secret, or provider body is stored. Governed production grant/revoke provisioning and immutable evidence merged in PR #67; the later rate-policy management definition is added without automatic grants in migration `20260808_0024`. Trusted bootstrap assignment remains outside the Runtime API. CP9 Runtime API: Merged. CP10 Worker: Merged.
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

## Sprint 15 CP9 Runtime permission-fact resolution governance

ADR-089 requires the trusted application facade, not HTTP transport, to choose the exact Runtime
permission for each operation: `get_invocation` requires `runtime.read`, `submit_invocation`
requires `runtime.invoke`, and `request_reconciliation` requires `runtime.reconcile`. A client
cannot provide or override this mapping. Wildcard, prefix, substring, `rbac:manage`, and
`runtime.grant.manage` forms cannot substitute.

The production resolver will read the current `RolePermission` projection through an active user,
active membership, active organization, exact active Tenant-Organization binding, one or more
organization-scoped roles, and the exact permission definition. The append-only grant ledger is
provenance and history, not active authority. Multiple valid role paths do not broaden the fact,
and the public response discloses no role topology, grant history, tenant existence, or SQL detail.

Permission resolution occurs for every operation with no positive or negative cache. Resolution
and the bounded local application read or commit must share a database transaction and fixed lock
order. A revoke committed first denies; a request holding the active projection lock completes its
bounded local operation before revoke commits. Permission facts are ephemeral decision evidence,
never bearer capabilities or reusable session facts, and are neither returned to nor accepted
from transport.

Missing, inactive, revoked, mismatched, or cross-scope facts fail closed. Authentication remains a
generic `401`, trusted scope failures remain non-disclosing `404`, and missing permission maps to a
bounded `403` without membership, binding, role, grant, tenant, or database details. The governance
gate adds no production resolver, migration, facade, route, Worker, queue, polling loop, scheduler,
`app.runtime.api`, or `app.runtime.outbox`. The production permission-fact resolver now requires a
caller-owned transaction and locks active user, organization, membership, binding,
organization-scoped roles, exact permission, and `RolePermission` facts in fixed order. It neither
queries the grant ledger nor caches allow or deny outcomes. This resolver is implemented, pending
review; CP9 remains Planned / Blocked on the trusted facade and routes.

## Sprint 15 CP9 Transport Idempotency security boundary

ADR-090 governance merged in PR #71 and its contracts gate merged in PR #72.
`CP9-Gate-Transport-Idempotency-Atomic-Commit-Contract-Correction` merged in PR #73.
The caller-transaction-owned port must lock and resolve replay or conflict before invoking a bounded
local mutation. Replay and conflict invoke it zero times; a new identity awaits it exactly once and
stages a receipt only after success. Explicit receipt ID and committed time remain trusted inputs;
the port owns no commit or rollback and claims no external exactly-once. Production persistence
and migration `0021` are merged in PR #74. Facade and routes remain Planned / Blocked.
CP10 remains Planned.

ADR-090 permits a client to provide only a bounded ASCII `Idempotency-Key` for
`submit_invocation` and `request_reconciliation`. The server constructs the trusted scoped replay
identity from tenant, organization, principal, operation, explicit `command_version`, and the key,
then computes a canonical digest only after strict schema validation and current authentication,
scope, Tenant-Organization binding, and exact permission resolution. Those trust facts are
revalidated before every receipt lookup or replay, so revoked authority cannot reuse history.

An exact scoped identity and digest returns the original bounded safe result. Any identity,
operation, version, or digest mismatch raises a bounded typed conflict without disclosing receipt,
scope, or database detail. A caller-owned transaction and transaction-scoped stable PostgreSQL
advisory lock linearize the local mutation and immutable receipt. Receipts are append-only: UPDATE,
DELETE, cascade delete, expiry, and key reuse are prohibited during Sprint 15.

Receipts contain bounded structured facts only. Raw request or provider payload, bearer token,
secret, credential, arbitrary JSON, internal exception, and SQL/error detail are prohibited. A
receipt and local mutation commit or roll back together. This boundary does not guarantee external
business-effect exactly-once. The trusted facade, routes, `app.runtime.api`, outbox, Workers, and
CP10 remain unimplemented.

## Sprint 15 CP9 trusted application facade security boundary

ADR-091 governance merged in PR #75 and its contract amendment merged in PR #76, without
creating a production facade or route. ADR-091 requires routes to call only the trusted application facade and forbids routes from
constructing principal, scope, permission, replay identity, or digest facts. The facade owns the
single `AsyncSession` transaction spanning principal and scope resolution, exact permission, the
bounded local read or mutation, and idempotency lookup and staging. Permission locks remain held
through the operation; helpers do not commit or roll back. Replay and conflict perform zero local
mutations, while a new request performs exactly one after lock and lookup.

The server fixes `get_invocation → runtime.read`, `submit_invocation → runtime.invoke`, and
`request_reconciliation → runtime.reconcile`; neither the client nor dependency injection selects
the permission. Trusted identifiers, timestamps, tenant, principal, authority, permit,
classification, revision, and lineage are never client supplied. Canonical mutation digests are
computed after validation from fixed-order, length-prefixed UTF-8 facts and emitted as
`sha256:<64 lowercase hex>`; raw HTTP bytes, bearer tokens, whitespace, and provider responses are
excluded.

Current persisted orchestration facts must match tenant, organization, principal, classification,
revision, lineage, action, plan, state, registry, and permit exactly. Missing, ambiguous, stale,
revoked, or cross-scope facts fail closed, and the facade cannot infer Authority, Permit, admission,
Plan, State progression, Registry, or Audit. Errors remain bounded as generic `401`, non-disclosing
`404`, bounded `403`/other `4xx`, `429`, `503`, or generic `500`, with no secret, raw body, SQL,
topology, receipt internals, or chain-of-thought disclosure. Production facade, routes, CP10,
external effects, `app.runtime.api`, and `app.runtime.outbox` remain blocked.

The service-layer input contracts are strict, frozen, transport-safe, and independent of FastAPI or
HTTP objects. Verified claims, the organization selector, and explicit immutable server facts are
separate facade parameters. Inputs cannot select tenant, principal, membership, permission,
authority, digest, receipt identity, UUID, or timestamp. Server facts have no defaults, generated
identifiers, or hidden clocks. Pure digest builders use only the approved fixed-order,
length-prefixed UTF-8 submission or reconciliation fact set. Query operations have no mutation
digest. The remaining order is contract amendment, production facade, routes, PostgreSQL/HTTP
acceptance, CP9 closeout, then separately approved CP10.

The fact-binding contracts gate is merged in PR #77. A strict frozen
`RuntimeApiTrustedContextFacts` supplies authentication and validation references and aware
timestamps explicitly to all facade operations. The SQLAlchemy trusted-context resolver consumes
those facts exactly and has no clock dependency or implicit time read. Additive orchestration-binder
and local-operation Protocols receive resolved principal, scope, exact permission, outer input,
explicit facts, and canonical digest where applicable. They cannot commit, roll back, create UUIDs
or timestamps, infer governance facts, or invoke adapters, providers, MCP, queues, workers, or
external effects. Missing, stale, ambiguous, revoked, and cross-scope persisted facts fail closed.
The production facade is merged in PR #78 and owns the transaction across these
resolutions, exact binding, local operation, and idempotency receipt persistence. Concrete binder
and local-operation implementations and production routes remain Planned / Blocked. The required
order is ADR-092 governance (merged in PR #79), additive binding and active-transaction Persistence
contracts (merged in PR #80), Registry resolution/admission exactness (merged in PR #81), ADR-093
governance, Registry persistence and active-transaction integration, separate concrete local
integration, routes, combined PostgreSQL/HTTP acceptance, CP9 closeout, then separately approved
CP10.

The local fact-binding and active-transaction Persistence contracts gate merged in PR #80. Its
strict frozen contracts require exact persisted record IDs and expected revisions,
canonical permit facts, Registry snapshot and resolution identities, tenant, organization,
classification, lineage, and caller-supplied aware timestamps. The active-transaction Port exposes
only exact scoped reads and one bounded local write-set stage; it exposes no begin, commit,
rollback, close, session, or engine operation. It adds no Registry store, database model, migration,
concrete binder, local operation, route, or external effect. The remaining order is ADR-093
governance, Registry persistence and active-transaction integration, separate concrete local
integration, routes, combined PostgreSQL/HTTP acceptance, CP9 closeout, then separately approved
CP10.

The Registry Resolution and Admission Exactness Contract Correction Gate merged in PR #81. It
binds the approved persisted Registry snapshot and reference,
resolution request and decision, exact resolved action, and `ADMITTED` admission decision to the
same tenant, organization, classification, lineage, lineage digest, Registry revision, execution
request, and canonical permit facts. Missing, stale, substituted, revoked, cross-scope, or lineage
mismatches fail closed. All identifiers, revisions, digests, and aware times remain caller supplied;
the contracts generate none. The caller-owned active transaction and facade outer transaction
ownership remain unchanged: replay and conflict perform zero local mutations, while a new request
performs exactly one. This gate adds no Registry snapshot persistence, database model, migration,
concrete binder or local operation, production route, external effect, Worker, queue, retry, or
scheduler. CP9 Runtime API remains Planned / Blocked, and CP10 remains Planned.

ADR-093 requires a separate append-only Registry persistence schema owned by
`app.runtime.persistence`; immutable Registry meaning remains owned by `app.runtime.registry`, and
Authority remains the authoritative owner of admission and permit facts. Exact tenant,
organization, classification, lineage ID/digest, snapshot ID/revision/digest, resolution identity,
resolved entry/action, persisted admission revision, execution request, and canonical permit
ID/revision set must agree. Missing, stale, substituted, cross-scope, classification-, lineage-,
digest-, revision-, or action-mismatched facts fail closed without disclosing cross-scope existence.

Migration `20260808_0022` is required but is not created by this governance gate. It may create only
empty additive Registry tables and immutability enforcement. Existing data receives no inferred
backfill. A populated downgrade must fail before any destructive DDL and leave all state unchanged.
The facade remains the only owner of the active `AsyncSession` transaction; persistence, binder,
and local-operation helpers may not begin, commit, roll back, close, replace, or retain the session.
Replay and conflict invoke the local mutation zero times; a validated new request invokes it exactly
once and atomically stages its write set with the transport receipt. This creates no execution,
external effect, route, Worker, retry, queue, scheduler, credential flow, or CP10 capability.

ADR-092 fixes the next local integration boundary before production implementation. Opaque
references are not authority, and no binder or local operation may infer Authority, Permit,
admission, Plan, State progression, Registry, or Audit facts. Exact persisted identifiers,
revisions, lineage, tenant, organization, principal, and classification must be supplied by
approved infrastructure and validated fail closed. A `RuntimeActionRegistrySnapshot` may come only
from an approved Persistence/read boundary; the existing Registry cannot be used to reconstruct a
missing snapshot. The facade remains the sole transaction owner, while later additive Persistence
contracts participate in its active session without begin, commit, rollback, or session replacement.

ADR-094 rejects marker-only local staging. A mutation must carry exactly one closed existing
`RuntimeAtomicWriteSet` without outbox work or one `RuntimeEffectReconciliationRequest`, bound to
the exact tenant, organization, classification, lineage, Registry resolution, admitted decision,
and canonical permit facts. An application factory captures the exact caller `AsyncSession` and
root transaction inside the facade transaction; Persistence verifies object identity and active,
non-nested lifetime before every operation. The capability is one-shot, exposes no transaction
control, and cannot escape the facade call. Replay and conflict perform zero local work; a new
request stages exactly one closed write set and its receipt atomically. This governance adds no
production code, migration, route, external effect, credential flow, or CP10 capability.

### CP9 reconciliation-request persistence ownership

ADR-095 separates an authorized reconciliation request from its later observation, transport
receipt, and any outbox fact. The existing strict `RuntimeEffectReconciliationRequest` remains the
domain payload; `app.runtime.persistence` owns a dedicated append-only row and repository in
migration `20260808_0022`. Generic Runtime revisions, observation rows, stage markers, receipts,
outbox rows, and arbitrary JSON cannot become request authority.

The persisted request and its relational binding require exact tenant, organization,
classification, root lineage, Registry snapshot/revision/digest, resolution request/decision,
admission, execution request, canonical permits, idempotency linkage, and caller-supplied time.
UPDATE, DELETE, cascades, cross-scope substitution, hidden identifiers or clocks, raw payloads,
provider responses, credentials, and secrets are prohibited. Populated downgrade fails before any
destructive DDL.

The persistence checkpoint may prove only same-session/root-transaction staging, one-shot
lifecycle enforcement, and caller-rollback removal. Production replay/conflict callback ordering,
receipt coupling, and facade commit/rollback remain a separate concrete integration checkpoint.
Until that evidence exists, PolicyOS does not claim end-to-end Runtime API atomicity or completed
submission/reconciliation behavior.

### CP9 Registry and reconciliation persistence implementation

Migration `20260808_0022` adds seven append-only tables for Registry snapshots, canonical entries,
resolution requests and decisions, admission and permit bindings, and authorized reconciliation
requests. Exact tenant, organization, classification, lineage, revision, digest, resolution,
admission, execution-request, and canonical permit relationships are enforced by bounded columns,
unique constraints, restrictive foreign keys, and immutable ORM/PostgreSQL guards. The migration
performs no backfill, inference, normalization, deduplication, or deletion and refuses populated
downgrade before destructive DDL.

Typed serialization revalidates existing immutable Registry and reconciliation contracts. Reads
require exact scoped identities and never choose a latest or fallback revision. The one-shot
active-transaction capability captures the caller `AsyncSession` and root transaction objects and
rejects inactive, nested, replaced, or reused lifetimes before database work. It does not begin,
commit, roll back, close, or replace the transaction and exposes no reusable bearer capability.

This checkpoint proves persistence-level local staging and caller rollback only. Concrete binder,
local operation, facade callback/receipt composition, routes, external effects, Workers, retry,
scheduler behavior, end-to-end Runtime API atomicity, and CP9 completion remain unimplemented.

### CP9 explicit integration facts and request-scoped persistence binding

ADR-096 prohibits transaction and persistence authority from being synthesized by HTTP input,
routes, generic dependency injection, binders, repositories, ORM defaults, or latest-row lookup.
Required strict nested integration facts are prepared once per request from approved orchestration
outputs and are carried through the unchanged five-parameter facade boundary. They contain only
bounded opaque identifiers and governed closed payloads, never session objects, transaction
objects, raw content, model output, credentials, tokens, or arbitrary metadata.

The facade binds a one-shot capability to the exact caller `AsyncSession` and root transaction,
then re-reads or locks and exactly compares the persisted scope, Registry, admission, permit,
lineage, receipt, digest, and payload facts. Cross-request reuse, inactive or nested transactions,
scope substitution, stale facts, and mismatch fail closed before mutation. Replay and conflict do
no binding read or mutation; new mutations stage one closed payload and receipt atomically; the
query path is read-only. Public contract changes and concrete integration remain unimplemented, so
CP9 remains Planned / Blocked.

### CP9 explicit integration facts public-contract amendment

Required strict nested integration facts eliminate the remaining opaque-reference inference path.
Submission and reconciliation expose exactly one closed governed stage; invocation query facts
have no stage, receipt, write set, mutation digest, or reconciliation payload. Duplicate outer and
nested command, query, receipt, correlation, action, classification, and digest identities must
compare exactly. Missing, extra, stale, cross-scope, or substituted values fail closed.

The request-scoped integration-facts provider is an application Protocol, not an implementation or
authority resolver. It accepts no HTTP body, session, engine, repository, cache, or reusable
capability and may return only immutable caller-owned expected facts. Actual session and root
transaction identity remain confined to the approved one-shot Persistence factory. This contract
gate changes no facade behavior, route, database model, migration, repository, external effect, or
Worker boundary.

### CP9 authoritative result and query projection ownership

ADR-097 prohibits clients, integration facts, request-scoped providers, binders, facades, local
operations, and persistence adapters from inventing a safe result or query projection. A new
mutation receives its immutable safe result only from a separately contracted one-shot domain
operation callback. Exact replay returns the result already persisted in the transport receipt;
conflict invokes no callback or persistence-binding read.

The query path requires a separately contracted exact projection Port over persisted execution
state, result, and audit revisions. It binds tenant, organization, classification, lineage,
Registry, admission, permit, identity, revision, digest, action, invocation, and correlation facts
exactly and cannot select a latest row or infer authority from an opaque reference. The provider
assembles expected facts only and creates no UUID, time, revision, digest, reference, status,
result, or projection. No schema or migration change is approved; CP9 remains Planned / Blocked
and CP10 remains Planned.

### CP9 runtime lifecycle and public projection authority

ADR-098 makes public status projection a total domain-owned function and preserves cancellation,
timeout, partial completion, compensation, and invalidation as distinct public meanings. The
authoritative public `status_reference` is only the stored `record_digest_reference` of the exact
persisted execution-state logical record and expected revision. Audit digests protect audit-chain
integrity, result digests protect result content, and transport receipt digests protect replay;
none substitutes for execution-state status authority.

Only a server-owned, request-scoped locator may carry exact state, result, and audit identities and
revisions. HTTP callers cannot declare those facts, and the projection reader cannot choose a
current/latest revision, generate a digest, or synthesize a missing result. Missing, forbidden,
duplicate, stale, cross-scope, cross-lineage, or digest-inconsistent facts fail closed. Public
contracts, exact persistence reads, and application integration remain separate CP9 gates; CP10
remains Planned.

The public-domain contract gate implements ADR-098 as an immutable total mapping and strict
result-cardinality validator. It adds no persistence locator, stored digest exposure, database
read, hidden identifier or clock, facade parameter, binder behavior, schema, or migration. Unknown
states, invalid counts, forbidden results, and missing required results fail closed. Exact
state-revision digest reads and request-scoped locator implementation remain separately reviewed.

The persistence/read contract gate carries query-only execution request, state, audit, and
optional result identities with mandatory expected revisions. Result absence and presence are a
closed discriminator, and the exact state-revision read result returns the persisted
`record_digest_reference` unchanged. The contracts cannot select a current/latest revision,
accept an HTTP-supplied digest, mutate persistence, control a transaction, or generate identity,
time, revision, reference, status, result, or projection facts. Repository implementation,
schema, migration `20260808_0023`, concrete facade integration, routes, and CP10 remain blocked.

The authoritative domain-operation result contract binds exactly one immutable safe result and
the already approved closed local write-set stage as sibling output of one request-scoped
callback. The stage must equal the validated command integration stage, and invocation and
correlation identities must match the validated command. The callback contract grants no
transaction control and does not authorize the provider, binder, facade, or persistence adapter
to generate, infer, repair, or substitute a result or stage. Callback invocation, exact binding
read, one-shot stage, receipt coupling, facade composition, routes, and CP10 remain deferred.
For submission, the expected invocation reference is supplied only by the trusted request-scoped
preparation boundary and carried unchanged through integration facts and the validated command;
HTTP input, command references, and write-set contents cannot supply or derive it.

### CP9 logical execution-result identity authority

ADR-099 separates the API logical execution result from action-level adapter outcomes.
`RuntimeAdapterInvocationResult` lacks execution-request and root-lineage authority and may occur
multiple times within an attempt, so its generic persistence label cannot establish logical-result
identity or cardinality. Audit remains append-only evidence and cannot designate, recover, select,
or promote a logical result.

The logical result is bound to exact tenant, organization, classification, execution request,
attempt, root-lineage ID/digest, state revision, and audit revision facts. Missing, duplicate,
stale, substituted, cross-scope, cross-lineage, wrong-attempt, wrong-revision, or digest-mismatched
facts fail closed. A dedicated append-only store and migration `20260808_0023` must provide scoped
uniqueness, relational bindings, `ON DELETE RESTRICT`, and database-enforced immutability.

Existing adapter-result rows are never inferred, backfilled, promoted, normalized, deduplicated,
or deleted. The new store starts empty; populated downgrade fails before destructive DDL. This
governance gate changes no production code or schema. Logical-result contracts and persistence
must merge before Application Integration; CP9 remains Planned / Blocked and CP10 remains Planned.

The API `RuntimeApiSafeResult` is not logical-result authority. For submission, only the exact
post-operation state inside the closed local mutation bundle controls ADR-098 result cardinality,
and the domain operation must supply an explicit present or absent variant. Missing, forbidden,
duplicate, inferred, or substituted presence fails closed. One local mutation is one atomic
bundle and may contain multiple governed rows; it is not a row-count shortcut.

Reconciliation has no approved state mutation and cannot create or revise a logical result.
Contributing adapter-result identities are excluded until separately governed. Query locators
carry exact identity and expected revisions but never stored result digests or references as
caller authority; those remain exact-read outputs.

### CP9 logical execution-result contract boundary

The logical-result Port contract is strict, frozen, extra-forbidden, caller/domain-supplied, and
bound to exact tenant, organization, classification, execution request, attempt, root lineage,
resulting execution-state revision, and audit-trail revision. The submission mutation is a closed
present/absent union. ADR-098 cardinality is checked against the exact staged state; missing,
forbidden, duplicate, stale, substituted, cross-scope, cross-lineage, wrong-attempt, or
wrong-revision values fail closed.

Reconciliation cannot carry a logical-result mutation. Query locator input includes only exact
identity and expected revisions; the stored result reference, digest, payload-provenance reference,
and production time are returned from the exact persisted read. Until migration `20260808_0023`
and the append-only repository exist, result-present staging is rejected before database work.
No hidden identifier, clock, revision, digest, reference, latest-row selection, adapter-result
promotion, schema, backfill, facade behavior, route, or external effect is introduced.

### CP9 logical execution-result persistence boundary

Migration `20260808_0023` stores logical-result identity and revisions separately from action-level
adapter outcomes. Composite scope and revision constraints bind tenant, organization,
classification, execution request, root lineage, attempt, resulting state, and audit facts.
Restricted foreign keys, ORM guards, and PostgreSQL triggers reject deletion or mutation.

All identifiers, revisions, digests, references, provenance, and aware times remain caller/domain
supplied and are revalidated on serialization, append, replay, and exact read. Missing, stale,
substituted, cross-scope, cross-lineage, wrong-attempt, wrong-revision, or payload/column mismatch
fails closed. Existing rows are never promoted or backfilled, and populated downgrade stops before
DDL. The repository and active-transaction capability do not own transaction control; concrete
Application Integration and production routes remain blocked.

### CP9 concrete application integration boundary

The request-scoped integration-facts provider returns exactly one already-governed immutable
operation value and rejects cross-operation access or reuse. The pure binder carries only trusted
principal, scope, permission, request, digest, and integration facts; it performs no database,
clock, identifier, authority, or transaction work.

For a new mutation, the local operation exact-reads the expected Registry/admission binding,
invokes the domain callback once, validates its safe result and closed stage, and stages that
bundle once. The existing facade then stages one transport receipt in the same `AsyncSession` and
root transaction. Replay and conflict enter no local operation and therefore perform zero binding
reads, callbacks, local stages, or local repository mutations. A stage or receipt failure rolls
back every local row and receipt together.

Queries exact-read the named binding and execution-state revision and read the named logical-result
revision only for a result-present locator. Public status comes only from the total lifecycle
mapping, `status_reference` is the stored digest of the exact state revision, and observed time is
the caller-supplied locator/read time. Missing, stale, substituted, cross-scope, cross-lineage,
wrong-attempt, wrong-revision, or cardinality mismatch fails closed. The facade retains its five
public parameters and remains the only transaction owner. Routes, external effects, Workers,
queues, retries, schedulers, CP10, new schema, and migration `20260808_0024` remain excluded.

### CP9 Runtime route trusted preparation and production composition

ADR-100 prevents HTTP transport and framework wiring from becoming a Runtime-fact authority.
Mutation idempotency is accepted only through one bounded `Idempotency-Key` header and is absent
from mutation bodies. A server-owned request-scoped preparation source returns exactly one inert
already-governed operation package from approved command/orchestration preparation output. It
cannot generate, infer, select-current/latest, normalize, or repair UUIDs, times, revisions,
digests, references, write sets, logical results, Registry resolutions, admissions, permits,
State, Audit, classification, or lineage.

The facade activates that candidate only after exact current principal, tenant, organization,
permission, classification, lineage, Registry, admission, permit, revision, digest, and
transaction checks. Routes call one application entry boundary and cannot import or call ORM
models, Persistence, repositories, adapters, providers, MCP clients, connectors, Workers, or
transaction controls. Missing or ambiguous preparation fails closed as dependency unavailable;
no default fake or generated package is allowed in production.

Authentication failures remain generic `401`, scope failures non-disclosing `404`, permission
denials bounded `403`, exact conflicts `409`, strict input failures `422`, rate limiting
`429`, dependency absence `503`, and unexpected failures generic `500`. Responses and logs
contain no raw body, bearer material, secret, provider payload, SQL detail, cross-scope existence,
session, or transaction identity. ADR-100 adds no schema or migration `20260808_0024`; a need
for new durable preparation state requires a separate schema-governance stop.

### CP9 Runtime route transport and trusted preparation contracts

Mutation body schemas exclude `idempotency_key`; exactly one bounded ASCII `Idempotency-Key`
header is the only approved transport source. The internal application request retains the key so
the existing tenant-, organization-, principal-, operation-, version-, and digest-bound
idempotency identity remains exact. Missing, repeated, malformed, body-substituted, normalized,
truncated, or generated keys fail closed before facade invocation.

The trusted preparation source returns one frozen operation-specific package from an approved
server-owned output. Submission and reconciliation packages carry the existing immutable outer
facts and exact callback; query preparation carries no callback, stage, receipt, or mutation
capability. The package cannot supply authority and becomes usable only after the facade revalidates
the current principal, tenant, organization, permission, classification, lineage, Registry,
admission, permit, revision, digest, session, and root transaction. This contract gate creates no
default provider, route, global registry, durable preparation state, schema, or migration
`20260808_0024`.

### CP9 Runtime preparation provenance and operational capability boundary

The public-contract gate requires an immutable exact preparation provenance value on every
prepared operation package and exposes no default issuer or operational capability. Rate,
deadline, and disconnect requests bind the same explicit request scope and evaluated time;
malformed, stale, substituted, cross-operation, or mismatched results fail closed. Disconnect is
only transport observation and never proves Runtime cancellation or external-effect termination.
No bearer material, callback identity, session identity, hidden clock, generated identifier,
durable preparation state, or migration `20260808_0024` is introduced.

ADR-101 requires a mandatory server-owned issuer to create one preparation package inside the
same request call stack. Explicit immutable provenance binds preparation ID, request identity,
principal, tenant, organization, operation, canonical request and facts digests, correlation, and
caller-supplied validity times. The request-local source consumes the exact operation once.
Missing, stale, ambiguous, substituted, reused, cross-request, cross-operation, scope-, digest-, or
time-mismatched packages fail before facade work. Transport, dependency injection, persistence,
Audit, mutable registries, callback names, dynamic imports, current/latest lookup, and default
fakes are not preparation authority.

Rate admission, deadline budget, and disconnect observation are mandatory one-shot application
capabilities with exact request scope and explicit time inputs. No hidden clock or disabled
production limiter is allowed, and capability absence fails closed. Timeout or disconnect does not
create Runtime cancellation, retry, compensation, state, result, success, or proof that an external
effect stopped. Runtime authentication returns only issuer/audience/expiry-verified claims and
never downgrades to a legacy ORM user; the facade still resolves principal, membership, binding,
classification, and permission inside its transaction. `app.api` alone maps bounded non-disclosing
HTTP errors. Preparation is not durable, so no table, backfill, repository, schema, or migration
`20260808_0024` is approved.

ADR-102 assigns preparation production to an explicit request-scoped application Port and binds
all operational times to a trusted clock reference. Exact multi-process Runtime rate admission is
owned by PostgreSQL policy revisions and scoped atomic window counters in migration
`20260808_0024`. No default policy, inferred assignment, backfill, process-local limiter, disabled
fallback, hidden clock, persisted callback, or current/latest selection is allowed. Missing policy
or capability fails closed before package consumption and facade work.

The public contracts now require exact clock-reference/time equality across preparation and
operational requests, exact tenant/organization/principal/operation/classification policy scope,
and operation-specific preparation contexts. Query preparation cannot carry a mutation callback;
callbacks, clocks, policies, UUIDs, revisions, digests, references, and time values may not be
generated or inferred by producer, issuer, route, facade, or capability adapters.

ADR-103 requires an exact explicitly provisioned policy ID/revision/reference for every Runtime
rate evaluation. Unprovisioned, inactive, expired, revoked, stale, substituted, ambiguous, or
cross-scope policies fail closed before counter access. The trusted clock alone determines the UTC
epoch-aligned `[window_start, window_end)` interval. Every counter creation or one-step increment
requires trigger-level proof of the exact admitted decision in the same transaction; denial and
exact replay do not mutate counters, and failures leave no decision or counter residue. Migration
`20260808_0024` may create only the four governed append/serialized tables and may not insert,
backfill, normalize, deduplicate, infer, or default policy authority.
## Runtime rate-admission contract boundary

Rate-policy management requires `runtime.rate_policy.manage`. Policy, actor,
tenant, organization, principal, operation, classification, window, request,
clock, decision, and provenance facts bind exactly and fail closed. Contracts
do not create identifiers, revisions, digests, references, or time values.

## Runtime rate-policy management permission ownership

`runtime.rate_policy.manage` has fixed definition ID
`00000000-0000-0000-0000-000000001905`. Its migration definition creates no authority, grant,
role assignment, membership assignment, or default. Only an actor already holding exact
`runtime.grant.manage` in the same active tenant/organization scope may grant or revoke it through
the immutable ledger. Self-grant, same-transaction privilege activation, wildcard substitution,
cross-scope binding, collision, inferred bootstrap, and automatic administration fail closed.

## Runtime rate-admission persistence boundary

Migration `20260808_0024` creates only the fixed permission definition and four governed tables.
It grants no authority and performs no backfill. Policy management revalidates exact existing
authority in the caller-owned transaction. Immutable triggers reject policy, revocation, and
decision mutation; a counter trigger requires the exact admitted decision in the same transaction.
Replay, denial, collision, stale scope, and rollback leave counter mutation residue at zero.

## Runtime operational-preflight consumption boundary

ADR-105 requires one closed operation candidate from a request-scoped server-owned
preparation-context provider. Exact rate-admission, deadline, and disconnect requests bind to the
same preparation identity, request identity, tenant, organization, principal, operation,
classification, canonical digest, trusted clock, and evaluated time. Routes, sources, issuers,
facades, Persistence, configuration, and dependency injection cannot generate, infer, repair, or
select these facts.

Inspection changes `AVAILABLE` to `INSPECTED` without consumption. Denial, expiry, disconnect,
missing capability, malformed result, mismatch, substitution, cross-scope access, or reuse changes
the candidate to terminal `REJECTED`; package consumption and facade work remain zero. Only exact
success from rate admission, deadline, and disconnect permits one `CONSUMED` transition and one
facade entry. An admitted rate decision may remain durable after a later preflight rejection but
creates no Runtime approval, permit, execution, cancellation, state, result, or audit authority.
Preparation state remains request-local and no migration `20260808_0025` is permitted.

The public contracts require one strict operational-preflight value on every prepared candidate
and preparation context. Its rate-admission, deadline, and disconnect requests must share the
candidate's exact provenance and trusted clock. Only a server-owned request-scoped context provider
may supply the complete context. The source exposes distinct inspect, consume, and reject methods;
those Protocols do not implement state, generate facts, persist callbacks, or authorize facade
entry. Query candidates remain callback-, stage-, receipt-, and mutation-free. Production lifecycle
enforcement and bounded HTTP translation remain separate, and no migration `20260808_0025` is
introduced.

## Runtime production preparation injection boundary

ADR-106 requires an immutable production dependency bundle supplied explicitly to the application
factory. Each factory creates fresh request-scoped preparation upstream, provider, producer,
issuer, source, clock, rate, deadline, and disconnect capabilities. Mutable `app.state`, global
registries, service locators, environment-selected Python objects, callback names, dynamic imports,
production dependency overrides, and default fakes are prohibited. Missing composition fails
closed with a non-disclosing `503` before inspection.

The upstream capability is the sole owner of exact preparation facts and the one-shot callback.
The disconnect adapter observes only the current request and cannot generate its reference or
trusted time. Rate admission owns a fresh independent PostgreSQL session and root transaction; the
facade session remains separate and exclusively facade-owned. No error exposes package, policy,
provider, callback, database, session, transaction, bearer, body, or cross-scope facts.
Preparation remains non-durable and migration `20260808_0025` is prohibited.
### CP9 production dependency-bundle and observer security boundary

ADR-107 requires one immutable, complete production dependency bundle and one asynchronous
request-capability scope. Every upstream, callback, clock, rate, deadline, and disconnect object is
fresh, request-bound, non-reusable, and disposed exactly once. Missing, incomplete, stale,
substituted, cross-request, cross-operation, cross-tenant, cross-organization,
cross-classification, lineage-, digest-, clock-, policy-, callback-, or lifecycle-mismatched inputs
fail closed before preparation consumption or facade invocation.

Only `app.api` may bind FastAPI `Request` to the transport-neutral asynchronous disconnect signal.
The signal exposes one strict boolean and no body, bearer, reference, timestamp, or cancellation
authority. The public rate factory exposes no SQLAlchemy engine, session, sessionmaker, or
transaction. Missing approved composition maps to a generic bounded `503`; supplied partial
composition fails application construction. No mutable `app.state`, service locator, environment
selection, default fake, preparation persistence, or migration `20260808_0025` is permitted. CP9
remains Planned / Blocked and CP10 remains Planned.

### CP9 dependency-bundle lifecycle correction security boundary

The corrected ADR-107 bundle exposes only one immutable scope-factory field, preventing direct leaf
factory invocation outside the lifecycle coordinator. Six leaf factories are captured privately
and invoked exactly once. Only the disconnect factory receives the current request's
transport-neutral signal, and only the upstream factory receives the exact domain-operation and
trusted-clock instances already created for that scope.

The async scope yields a frozen six-field dependency set, returns false from exit, never suppresses
exceptions, and disposes partial or complete construction exactly once in reverse order. Re-entry,
duplicate exit, pre-enter or post-exit use, escape, cross-request reuse, mutable or partial bundle,
and non-boolean disconnect observations fail closed. Unavailable composition remains an `app.api`
production-only boundary returning generic `503`; it carries no public bundle variant or facts. No
preparation persistence or migration `20260808_0025` is permitted.

### CP9 dependency-bundle and upstream public-contract security boundary

The public bundle exposes exactly one scope-factory field. Its public structural contracts close
the six private leaf-factory signatures without exposing SQLAlchemy, FastAPI, sessions,
transactions, mutable configuration, metadata, or a service locator. The frozen six-field request
dependency set preserves the exact domain-operation, clock, rate, deadline, disconnect, and
preparation-upstream objects for one request only.

The disconnect signal returns only a strict asynchronous boolean, the upstream returns only the
matching operation-specific preparation context, and async scope exit suppresses no exception.
Missing, substituted, partial, reused, or cross-request dependencies fail closed in the later
production implementation. This contract gate creates no unavailable public variant, durable
preparation fact, schema, or migration; migration `20260808_0025` remains prohibited. CP9 remains
Planned / Blocked and CP10 remains Planned.

### CP9 managed request-capability lifetime security boundary

ADR-108 requires each private leaf factory to return one fresh single-use asynchronous managed
resource. Only the request scope may enter or exit those resources. It acquires them in the fixed
order and releases every acquired resource exactly once in reverse order on success, rejection,
exception, cancellation, or partial construction. Cleanup attempts continue after an exit failure
and never suppress or replace an active primary exception.

Guarded capability views reject pre-entry, exiting, post-exit, escaped, substituted, and
cross-request calls. Capability Protocols expose no public close, reset, retry, pool, session, or
transaction control. Rate admission closes its independent per-call session before returning;
scope cleanup cannot touch the facade transaction. Lifecycle state is request-local and carries no
authority, facts, credentials, or sensitive payload. No persistence or migration `20260808_0025`
is permitted. CP9 remains Planned / Blocked and CP10 remains Planned.

The public-contract gate exposes only the covariant managed-resource boundary and the six exact
factory return annotations. It adds no public cleanup method, lifecycle implementation, session or
transaction authority, mutable registry, credential path, persistence, or transport behavior.

### CP9 Runtime organization selector and operational rejection security boundary

ADR-109 confines organization selection to one required canonical `organization_id` query
parameter. It cannot be sourced from bearer claims, request bodies, headers, opaque Runtime
references, defaults, or current/latest database selection. Transport invalidity returns bounded
`422` without existence disclosure; tenant, organization, membership, classification, permission,
lineage, and persisted bindings remain facade-owned exact revalidation, with mismatch returning
generic `404`.

Deadline expiry, observed disconnect, capability failure, and missing preparation/composition use
the same generic `503` dependency-unavailable envelope. Responses and logs do not expose the
internal cause, deadline, observation, package, callback, policy, provider, database, session,
transaction, bearer, body, or cross-scope facts. Disconnect creates no second response attempt and
no Runtime cancellation or external-effect conclusion. Rate denial alone uses `429` and only the
exact persisted retry-after value. No schema or migration `20260808_0025` is permitted.

### CP9 Runtime required-audience configuration security boundary

ADR-110 assigns one mandatory immutable `runtime_api_required_audience` process setting as the
sole source for the production facade's exact audience. The value must be non-empty, trimmed,
bounded, and an exact member of the configured duplicate-free `jwt_audiences` tuple. Missing,
malformed, non-member, or mutable configuration fails before request-scope construction,
preparation inspection, rate admission, or facade work.

Allowlist order, bearer claims, request values, prepared facts, opaque references, dependency
objects, and persisted records cannot choose or replace the required audience. JWT verification
continues to accept the configured allowlist, while Runtime facade validation separately requires
the exact configured member. The one-field production dependency bundle, facade signatures, and
all tenant, organization, classification, lineage, permission, idempotency, and transaction
boundaries remain unchanged. No audience persistence, schema, or migration `20260808_0025` is
permitted.

### CP9 Runtime required-audience config-contract security boundary

The required-audience config-contract correction implements ADR-110 as one required, strict,
frozen scalar setting. Empty, whitespace-padded, oversized, non-string, and non-member values fail
closed, while exact `jwt_audiences` membership is mandatory. The example deployment and test
process specify the value explicitly; no tuple-order, bearer, request, prepared-fact, dependency,
or persistence selection is introduced.

JWT allowlist verification, the one-field production dependency bundle, Runtime public contracts,
facade signatures, and tenant, organization, classification, lineage, permission, idempotency, and
transaction boundaries remain unchanged. No audience persistence, schema, or migration
`20260808_0025` is permitted. CP9 remains Planned / Blocked and CP10 remains Planned.
### CP9 production Runtime composition and thin-route security boundary

Runtime endpoints use a dedicated verified-claims dependency and a canonical required
`organization_id` query selector; mutation idempotency is accepted only from `Idempotency-Key`.
The transport adapter cannot supply prepared facts, clocks, rate decisions, callbacks, or the
configured required audience. One immutable injected bundle creates six fresh request-local
capabilities, cleans partial construction in reverse order, preserves primary failures, and rejects
reuse. Preparation is inspected before rate, deadline, and disconnect evaluation and is consumed
exactly once only on admission. Missing dependencies, expired deadlines, and disconnects disclose
only the same bounded 503; denial alone returns bounded 429 plus exact `Retry-After`. No default
fake, mutable `app.state`, environment-selected dependency object, preparation persistence, or
migration `20260808_0025` is permitted.

### CP9 combined Runtime PostgreSQL and HTTP acceptance boundary

The acceptance gate proves that transport cannot manufacture preparation, clock, rate, binding,
stage, receipt, or result facts. A verified principal and canonical organization selector enter
one fresh managed request scope; preparation is inspected once, operational checks run in fixed
order, and the package is consumed once before the facade transaction. The rate decision commits
in its independent PostgreSQL transaction, while local mutation and transport receipt remain
atomic in the facade-owned transaction.

Exact replay performs no second callback or local mutation and preserves one counter mutation.
Failure paths retain bounded non-disclosing HTTP envelopes, reverse-order cleanup, and zero facade
rollback residue. The gate introduces no credential path, public authority, persistence owner,
schema, backfill, or migration `20260808_0025`.

### CP9 Runtime API closeout security boundary

CP9 Runtime API is complete after production composition and three thin Runtime routes merged in
PR #120 and combined PostgreSQL 16 and HTTP acceptance merged in PR #121. Verified claims, exact
tenant and organization binding, explicit permissions, header-only mutation idempotency, managed
preparation capabilities, operational preflight, independent rate admission, facade-owned atomic
local persistence, and bounded non-disclosing HTTP errors remain mandatory.

The closeout creates no new authority, credential path, public endpoint, model, repository,
schema, backfill, or migration `20260808_0025`. The single migration head remains
`20260808_0024`. Historical checkpoint status paragraphs remain evidence of their individual
gates; this closeout is authoritative for current security posture. CP10 Workers remain Planned
and require separate governance and explicit approval.

### CP10 Worker operating-model security boundary

ADR-111 makes Worker identity and assignment explicit immutable deployment provenance, never an
authority source. The Worker must use the configured service principal and revalidate tenant,
organization, classification, lineage, permission, admission, permit, claim, lease, and attempt
facts for every operation. It cannot scan unassigned scopes, select current/latest authority, infer
facts from hostnames, environment order, process identity, randomness, or wall-clock time, or
manufacture retry, dead-letter, reconciliation, success, or failure meaning.

The Worker remains outside `app.runtime` and calls one CP10 application service through
Orchestration and public Ports. Direct persistence, repository, adapter, credential, and HTTP
access is prohibited. PostgreSQL bounded polling is authoritative; a future queue or notification
can only wake the poller and cannot identify or authorize work. Short independent transactions
protect claim and lifecycle evidence and never span external work. Bounded graceful shutdown stops
new polling and claims before draining; it cannot declare an outcome without exact caller-supplied
evidence. Deployment configuration contains no credential, session, client, callback, or sensitive
payload. No Worker registry, heartbeat, assignment, schedule, process-session schema, migration
`20260808_0025`, backfill, normalization, deduplication, or rewrite is permitted by this gate.

### CP10 Worker contract-semantics security boundary

ADR-112 prevents infrastructure from broadening the Worker operation set. The initial Worker may
consume only exact scoped delivery candidates returned by the existing due Port. It cannot treat
ambiguous lifecycle, reconciliation requests or observations, audit events, provider failures, or
missing acknowledgements as pending work. Reconciliation remains an explicit authorized service
invocation.

Configuration identity is immutable for the process lifetime. Exact assignment, version, digest,
clock, and numeric bounds must match; live reload, latest-version selection, environment-derived
replacement, cross-process prepared facts, and partial substitution fail closed. Polling is
canonical fixed delay with no random jitter, hidden backoff, overlap, catch-up, or exception retry.

Shutdown observation is transport-neutral, single-use, caller-timed, and sticky. Once requested,
no new due selection, claim, preparation, or Adapter call may begin. The observation and drain
deadline cannot create or infer cancellation, retry, reconciliation, delivery outcome, dead
letter, or compensation. The contracts expose no OS signal object, event-loop handle, task,
thread, session, transaction, credential, payload, provider response, or traceback. No Worker or
reconciliation queue, registry, heartbeat, scheduler, shutdown table, schema, or migration
`20260808_0025` is permitted.

### CP10 Worker public-contract precision security boundary

ADR-113 prevents the public-contract implementation from selecting a hidden clock, generating
cycle identity, exposing mutable shutdown state, or turning infrastructure failures into Runtime
authority. The sole Worker clock is the synchronous public Runtime Ports clock. Every time,
configuration value, assignment, scope, classification, position, count, digest, and failure
reference is caller-supplied and checked exactly.

Shutdown observation and fixed wait are distinct asynchronous single-use capabilities. Their
process-lifetime factories share one private sticky source without exposing reset, close, task,
signal, thread, session, or transaction controls. Observation returns the bounded shutdown fact;
wait returns no fact. Closed operational results cannot authorize claim, delivery outcome, retry,
dead letter, cancellation, reconciliation, compensation, or audit mutation.

The public-contract correction adds no production service, prepared delivery authority,
credential, provider, route, repository, schema, backfill, or migration `20260808_0025`.

### CP10 Worker public-contract gate security boundary

The ADR-113 gate is Implemented / Validated, Pending Review. Worker contracts use the exact
synchronous Runtime Ports clock and preserve caller-supplied tenant, organization,
classification, configuration, position, time, request, digest, and bounded opaque-reference
facts without normalization or inference. Cross-scope, stale binding, substituted clock,
non-canonical assignment, invalid count, disposition, and deadline combinations fail closed.

Closed operational results grant no claim, delivery outcome, retry, reconciliation, audit, or
Runtime status authority. Public capability Protocols expose no mutable sticky state, reset,
credential, session, transaction, framework, signal, or environment API. Production CP10 remains
Planned, and migration `20260808_0025` remains prohibited.

### CP10 prepared-delivery ownership and sequencing security boundary

ADR-114 prevents a production Worker from deriving prepared facts from an opaque effect reference,
selecting a latest row, generating UUIDs or timestamps, or acquiring lifecycle authority. One
request-scoped single-use preparation capability is bound to the exact Worker configuration,
assignment, iteration, due request, selected candidate, scope, classification, lineage, current
lifecycle, authority, admission, permits, Registry, state, audit, clock, deadline, cancellation,
credential, revision, and digest facts.

The prepared package contains no guessed result. A distinct one-shot completion capability accepts
only the exact Adapter result for the prepared effect and attempt and returns the exact
caller-supplied lifecycle append. Claim and `DELIVERING` replay/conflict invoke neither Adapter nor
completion. Substituted or cross-scope packages and results fail before mutation.

Sticky shutdown after durable `DELIVERING` is not converted to cancellation, lease expiry, retry,
dead letter, reconciliation, failure, or success. The Adapter is not called and the durable state
is preserved for governed recovery. Transactions remain short and never span external invocation.
Prepared values are request-local, so no schema or migration `20260808_0025` is permitted.

### CP10 prepared-delivery public-contract security boundary

The prepared-delivery request and package are strict, caller-supplied, and operation-scoped.
Validation rejects missing, stale, substituted, cross-tenant, cross-organization,
cross-classification, cross-lineage, cross-effect, cross-attempt, cross-claim, and cross-envelope
facts before Adapter invocation or lifecycle mutation. The result-completion capability accepts
only the exact Adapter result and exact result append for the prepared effect and attempt.

Managed capability contracts guarantee request-local entry and exactly-once exit while exposing no
close, reset, retry, pool, session, or transaction authority. This gate creates no production
Worker, database owner, schema, or migration `20260808_0025`.

### CP10 Worker request-preparation ownership security boundary

Cycle, iteration, and candidate request preparation are separate request-scoped managed one-shot
capabilities. Missing, stale, consumed, substituted, digest-mismatched, ambiguous, or cross-scope
values fail closed before discovery, claim, Adapter invocation, or persistence mutation. The Worker
must not generate or infer UUIDs, contract versions, times, digests, references, tenant scope, or
lineage, and bounded diagnostics must not disclose their values.

### CP10 Worker request-preparation signature security boundary

ADR-116 keeps request provenance visible and immutable. Process-lifetime factories accept no
request facts. Fresh managed capability methods receive the exact configuration and binding,
cycle and assignment, or iteration and candidate facts needed for one output. Output substitution,
concurrent or repeated use, cross-request reuse, clock mismatch, digest mismatch, and cross-scope
binding fail closed before discovery, claim, lifecycle mutation, credential acquisition, Adapter
invocation, or completion.

No-argument preparation methods, closure-captured request values, mutable contexts, service
locators, latest-row selection, opaque-reference inference, and generated UUID/time/version/digest/
reference are prohibited. The gate introduces no credential exposure, production Worker, database
authority, schema, or migration `20260808_0025`.

### CP10 Worker request-preparation public-contract security boundary

The six additive Protocols preserve ADR-116's visible request provenance. Cycle, iteration, and
candidate preparation accept only their exact typed inputs; their zero-argument factories return
fresh managed one-shot capabilities and capture no request state. Runtime-checkable structural
contracts expose no reset, retry, close, pool, session, transaction, repository, framework,
credential, or environment API.

Existing strict request models and exact-binding validators remain authoritative. Missing,
substituted, cross-scope, stale, repeated, or post-exit use must fail before downstream work.
This contract gate creates no production Worker, durable authority, schema, or migration
`20260808_0025`.

### CP10 Worker production composition and operational-result security boundary

ADR-117 prevents the Worker loop from owning time, failure-reference generation, persistence, or
authority. Fresh managed operational-result producers accept only exact source requests, closed
dispositions, strict counts, and an allowlisted failure stage. They own the trusted completion clock
and bounded opaque failure reference. Raw exceptions, messages, tracebacks, payloads, credentials,
provider responses, SQL, and cross-tenant existence cannot enter results, logs, or metrics.

The frozen process bundle exposes typed factories only and contains no mutable service locator,
session, transaction, repository implementation, event loop, task, credential, or callback name.
Every candidate receives isolated managed capabilities. Shutdown stops new admission and drains
only already-admitted tasks to the exact sticky deadline without invented cancellation, retry, or
lifecycle evidence. No transaction spans an external effect, and no schema or migration
`20260808_0025` is introduced.

## Sprint 17 PostgreSQL connector evidence security proof

The acceptance path persists only the bounded `RuntimeEffectDeliveryResult` and lifecycle facts
after exact production HTTPS acknowledgement validation. Concurrent identical writes collapse to
one append plus one exact replay; credential bytes, Authorization headers, and raw provider bodies
are absent from every persisted revision. Existing tenant, organization, classification, lineage,
attempt, destination, idempotency, observation, conflict, and rollback checks remain fail closed.
No live credential, provider, schema, or migration `20260808_0025` is introduced.

## Sprint 17 local HTTPS acceptance security evidence

The test-only sandbox uses an ephemeral localhost key and certificate outside version control and
requires hostname verification and TLS 1.2 or newer through the production request-local client.
The wire request carries the exact idempotency key and a private Authorization value; assertions
observe only the test token and confirm its mutable source buffer is erased after use. Timeout,
disconnect, redirect, malformed response, and missing verified evidence never promote delivery and
never exceed one network call. No live secret, provider, ambient proxy, production trust root,
schema, or migration `20260808_0025` is introduced.

### CP10 Worker operational-result public-signature security boundary

ADR-118 places every producer input in a strict, frozen, extra-forbidden operation-specific model.
Only `OPERATIONAL_FAILURE` carries one closed failure stage; every other disposition carries none.
Completion time and the bounded opaque failure reference are trusted producer outputs. Raw
exceptions, messages, tracebacks, arbitrary metadata, credentials, provider responses, SQL, and
cross-scope identifiers cannot enter the request or result.

The frozen fourteen-field dependency bundle accepts typed factories only and exposes no mutable
container, session, transaction, repository, framework object, task, semaphore, clock callback,
credential, or environment selector. The application-service Protocol exposes only exact process
configuration and binding. This governance adds no schema or migration `20260808_0025`.

### CP10 Worker operational-result public-contract security boundary

Strict operation-specific production requests carry only caller-owned disposition, bounded counts,
and a closed failure stage. Managed producers remain the sole owners of completion time and bounded
failure references. The immutable dependency bundle exposes factories only and contains no engine,
session, transaction, credential, framework object, environment selector, or mutable service
locator. No schema or migration `20260808_0025` is introduced.

### CP10 Worker pre-invocation revalidation security boundary

ADR-119 makes one managed capability the sole owner of final trusted time and authoritative
revalidation. The Worker receives only a closed invokable, definitely-not-invoked, or
shutdown-blocked result and cannot read persistence, select a clock, expose authority facts, or
invent lifecycle evidence. Shutdown after `DELIVERING` remains durable ambiguity. No schema or
migration `20260808_0025` is introduced.

### CP10 Worker pre-invocation revalidation public-contract security boundary

The strict request binds one prepared package to one newly appended `DELIVERING` result. The closed
result exposes only trusted time, disposition, and optional exact caller-supplied append. Managed
one-shot lifetime, exact clock binding, and fifteen-field immutable composition prevent hidden
authority, mutable service location, or cross-request reuse.

### CP10 shutdown-observation trusted-time boundary

ADR-120 prohibits the Worker from sampling time or reusing stale cycle and due-selection clocks.
One fresh managed preparation capability binds the configured clock, immutable configuration,
configuration digest, and drain timeout before each observation. Missing, substituted, repeated,
cross-request, or post-exit use fails closed without an observation or Runtime mutation.

The merged public-contract implementation exposes only explicit configuration and binding inputs,
one strict shutdown request output, and managed one-shot lifetime. It adds no clock callback,
session, transaction, mutable request context, schema, or migration `20260808_0025`.
### CP10 Worker operational-failure and bounded-drain security boundary

ADR-121 prohibits broad exception translation and disclosure through operational results. Only
the closed `RuntimeWorkerOperationalCapabilityFailure` marker may be translated, its call-site
stage is bounded, and its failure reference remains producer-owned. Contract errors, programmer
defects, host cancellation, exception text, causes, tracebacks, SQL, provider responses,
credentials, payloads, and cross-scope facts are never copied. Deadline cleanup cancels only
application-admitted tasks, reaches residue zero, and creates no Runtime cancellation, retry,
reconciliation, or lifecycle authority. No migration `20260808_0025` is approved.
### CP10 Worker operational failure marker public-contract security boundary

The non-disclosing marker contract accepts no message, payload, failure reference, exception text,
credential, provider response, SQL, traceback, identity, scope, or authority fact. Only its exact
type may later be translated by production code; contract errors, programmer defects, and host
cancellation remain distinct. The marker changes no transaction, persistence, lifecycle,
classification, tenant, organization, or migration boundary.

### CP10 production Worker application-service security boundary

The service accepts only the immutable validated dependency bundle and exact configuration
binding. It never generates identity, time, revision, digest, reference, status, claim, attempt,
or authority; never catches broad exceptions; and never exposes backend detail. Exact replay and
shutdown preserve Adapter-call count zero. Each candidate owns fresh request capabilities, and
deadline cancellation is limited to application-admitted pending tasks with cleanup awaited to
zero residue. The service imports no SQLAlchemy or framework transport and creates no schema or
migration `20260808_0025`.

### Sprint 16 connector Worker materialization handoff boundary

An invokable pre-invocation result carries exactly one immutable, secret-free materialization
request. Every non-invokable disposition carries none. The Worker passes the request unchanged to
the managed delivery factory; mutable process state, lease reacquisition, endpoint selection, and
credential reconstruction remain prohibited.

Reconciliation uses a separate request with a fresh observation-specific lease whose request time
cannot predate the exact reconciliation request. Provisioning, destination, adapter contract,
scope, lineage, classification, permit, envelope, attempt, idempotency, and lease facts are
compared exactly before capability use. No secret, provider body, schema, or migration
`20260808_0025` is introduced.

### Sprint 16 connector provisioning and credential handoff

The production connector cannot select an endpoint, environment credential, global provider, or
mutable application state. One immutable injected provisioning entry owns the exact HTTPS
endpoint and non-reusable provisioning version reference. The injected broker issues the opaque
lease; a private source materializes secret bytes only after exact request, lease, provisioning,
scope, classification, permit, destination, attempt, envelope, and expiry validation.

Only an invokable pre-invocation result contains the strict secret-free materialization request.
Blocked results contain none, and replay/conflict performs no acquisition, materialization, or
external call. Reconciliation obtains a fresh observation-specific lease. Secret material never
crosses a public fact or survives exactly-once managed cleanup. This governance introduces no
durable provisioning, lease-use ledger, provider-operation aggregate, or migration
`20260808_0025`.

### Sprint 16 connector persistence sufficiency

Existing append-only Runtime records preserve only bounded, secret-free connector evidence.
Lifecycle `result_payload`, reconciliation `observation_payload`, and closed request
`request_payload` use strict allowlisted serialization and retain the exact acknowledgement pair,
destination, stable effect idempotency identity, classification, lineage, and relational scope.
The persisted revision `record_digest_reference` remains integrity evidence for its owning record;
it is never reinterpreted as a provider acknowledgement or external-operation identity.

Missing, stale, substituted, cross-tenant, cross-organization, cross-classification,
cross-lineage, cross-attempt, or mismatched acknowledgement facts fail closed. The system does not
choose a provider operation by recency, infer acknowledgement identity, persist credential secret
material, backfill connector evidence, or introduce a provider-operation table or migration
`20260808_0025` in this gate.

### CP10 and Sprint 15 closeout security boundary

CP10 is complete only within the governed delivery-only Worker boundary merged through PR #144.
The Worker consumes exact persisted due, claim, lease, attempt, lifecycle, receipt, and effect facts;
it does not derive authority, invent retry or reconciliation, or claim external exactly-once. The
combined regression preserves tenant, organization, classification, lineage, identity, revision,
digest, reference, replay, transaction, and rollback fail-closed boundaries across CP8, CP9, and
CP10 with Alembic single head `20260808_0024`.

Sprint 15 closeout adds no production code, public contract, permission, credential path, model,
repository, schema, migration `20260808_0025`, external adapter, queue, scheduler, automatic
redrive, tag, or release. Real provider execution and external business-effect exactly-once remain
outside the completed Sprint 15 scope.

### Sprint 16 production connector governance boundary

ADR-123 permits governance of only the `CONNECTOR` family and one explicitly provisioned HTTPS
destination class. Dynamic or caller-supplied URLs, redirects, wildcard hosts, fallback, mutable
service location, and environment-selected destinations are prohibited. Existing authority,
permit, admission, Registry, tenant, organization, classification, lineage, lease, deadline,
cancellation, and effect bindings remain mandatory immediately before invocation.

Credential material exists only inside a request-local managed connector capability bound to the
exact issued opaque lease. It is absent from envelopes, callback and domain results, persistence,
audit, logs, metrics, repr, serialization, errors, and test snapshots. The capability permits one
invocation and performs exactly-once cleanup; cross-request, substituted, stale, expired,
cross-scope, and post-exit use fails closed.

A stable provider-issued operation or resource identifier and validated bounded acknowledgement
evidence are both required for delivered certainty. HTTP `2xx`, response absence, locally invented
references, timeout, disconnect, redirect, or unknown destination state cannot establish success.
Only proof that no request bytes were transmitted permits definitely-not-delivered; uncertainty is
recorded as ambiguous and never retries blindly.

Provider-specific reconciliation is confined to the same connector and exact destination.
Missing records, lookup `404`, credential failure, unavailable observation, or provider error
never implies delivered or not delivered. This governance gate stores no secret or provider body,
creates no production adapter, and adds no schema or migration `20260808_0025`.

### Sprint 16 connector acknowledgement mapping and lease binding

ADR-124 confines the provider-issued operation or resource ID to the bounded acknowledgement
reference and binds its canonical validated evidence digest as the acknowledgement digest. The
logical connector result remains a separate pair. An ambiguous result may retain a complete
acknowledgement pair solely for exact provider-specific reconciliation; provider identity,
HTTP status, response absence, or lookup absence cannot establish delivery or non-delivery.

Opaque credential lease contracts must bind the exact tenant, organization, attempt, actor,
adapter contract, connector, destination, credential purpose, classification, permits, envelope,
effect idempotency identity, issuance, and expiry. They expose no secret material. Missing, stale,
substituted, cross-scope, cross-attempt, cross-destination, or changed-idempotency facts fail
closed. Cleanup after a validated outcome cannot rewrite certainty or disclose a secret; possible
transmission before validation remains ambiguous. Existing CP8 payload evidence is sufficient,
and no provider-operation table, backfill, or migration `20260808_0025` is approved.

### Sprint 16 managed connector contract boundary

Managed connector Ports expose only opaque exact references and bounded facts. Credential lease
requests and references bind the connector provisioning, destination, adapter contract, envelope,
stable effect idempotency identity, canonical permits, tenant, organization, execution request,
attempt, actor, classification, issuance, and expiry. Secret, token, password, authorization
header, provider body, raw client, session, transaction, and arbitrary metadata fields are absent.

The provider-issued operation identity is preserved only as the acknowledgement reference.
Ambiguity may retain its complete acknowledgement pair for authorized observation, but identity
presence never proves success. Definite non-delivery cannot carry acknowledgement evidence.
Observation requires exact connector, destination, idempotency, lineage, scope, classification,
authority, permits, and provider identity. The gate performs no production I/O and creates no
schema or migration `20260808_0025`.

### CP10 Worker PostgreSQL shutdown/crash-window acceptance

PostgreSQL 16 tests prove that concurrent Worker claims cannot create two authoritative revisions,
exact replay does not duplicate mutation, and durable `DELIVERING` evidence cannot be selected for
blind Adapter redelivery. Shutdown cleanup cancels only process-admitted tasks at the supplied
deadline, preserves committed lifecycle facts, and reaches task residue zero without inventing a
retry, cancellation, reconciliation, or outcome. The acceptance gate is test-only and adds no
schema or migration `20260808_0025`.

### CP10 Worker poll-result and shutdown-drain ordering security boundary

ADR-122 prevents candidate execution from rewriting synchronous poll facts. Iteration and cycle
results contain only governed discovery/admission outcomes and do not wait for Adapter completion.
Candidate marker failures produce no synthetic poll result, retry, cancellation, reconciliation,
dead letter, or lifecycle evidence; existing durable claim, lease, attempt, lifecycle, receipt,
and effect facts remain authoritative.

Sticky shutdown is observed while admitted tasks may still run. The service starts no new work
after shutdown, drains only its admitted task set to the exact caller-supplied deadline, and awaits
cleanup to zero residue without disclosing exceptions or backend detail. Cancellation and
credential capabilities remain composition inputs to pre-invocation revalidation and are not
independently entered by the Worker. No task persistence, schema, or migration
`20260808_0025` is approved.

### CP10 Worker poll-result and sticky-drain production correction

Candidate operational inability cannot rewrite discovery/admission facts or disclose a synthetic
poll failure. The Worker publishes the cycle result first, observes sticky shutdown while admitted
tasks may still run, then atomically closes its process-local admission gate before bounded drain.
Queued tasks cannot enter preparation, claim, or Adapter delivery after shutdown. Programmer
defects are retrieved and propagated after structured child cleanup; host cancellation preserves
its primary meaning. Cancellation and credential capabilities remain confined to authoritative
pre-invocation revalidation, with no independent Worker entry, hidden time, new persistence, or
migration `20260808_0025`.
## Sprint 16 connector wire and secret-material boundary

The first Runtime connector is a closed reference-notification protocol. It never dereferences or
transmits the underlying payload bytes, follows redirects, constructs destinations dynamically or
uses caller/environment fallback. Only the exact pre-provisioned HTTPS receiver and canonical
bounded request and evidence projections are permitted.

Credential material is obtained from the deployment-owned secret manager into a private mutable
request-local buffer. The managed capability overwrites and releases the buffer exactly once.
Secret material is forbidden from public models, representations, errors, logs, persistence,
audit, metrics, evidence and test snapshots. Once the network transport call begins, incomplete
or unverified evidence is always ambiguous; a transport signal cannot prove non-delivery.
## Sprint 16 connector authentication and canonical-wire boundary

The initial connector authenticates only with a request-local
`Authorization: Bearer <opaque-secret>` header assembled inside the private managed capability.
The entire header is excluded or redacted from logs, traces, errors, audit, metrics and tests, and
the mutable secret buffer is overwritten and released exactly once.

Only exact status `200` plus verified bounded evidence is authoritative. Strict UTF-8 JSON,
canonical typed digest inputs, response limits, TLS certificate and hostname verification,
redirect prohibition and trusted deadline binding prevent parser differentials, credential leaks,
destination substitution and transport-status inference.
### Sprint 16 connector canonical-wire public-contract boundary

Strict frozen delivery and observation wire values expose only reference identities and bounded
provider evidence. Canonical digest validation is deterministic and rejects non-UTC time,
duplicate or unknown fields, malformed UTF-8, BOM, non-finite values, identity substitution and
oversized bodies. The one-shot outcome-facts provider owns PolicyOS result identities, trusted
times and bounded references; provider evidence cannot manufacture them. Authorization headers,
bearer values, secret buffers, clients and sessions are absent from public contracts. This gate
performs no provider I/O and adds no migration `20260808_0025`.

### Sprint 16 connector production-composition security boundary

ADR-128 prohibits hidden materialization UUIDs, lease request IDs, provisioning selection,
credential references, clocks and expiry. One request-scoped server-owned facts provider supplies
those exact caller-owned values. Missing, repeated, stale, substituted, cross-attempt,
cross-destination, cross-tenant, cross-organization or cross-classification facts fail before
catalog lookup, credential acquisition, secret materialization or network I/O.

The immutable process bundle stores only a validated catalog and factories. It contains no secret,
Bearer header, mutable buffer, HTTP client, provider response, session, transaction or
request-local capability. Delivery and observation use separate facts and purpose-bound leases;
the delivery lease cannot be reused for reconciliation.

Private secret and transport resources are created only after exact request validation, cleaned up
exactly once in reverse order and never disclosed through public models, persistence, audit, logs,
metrics, exceptions or snapshots. No database transaction spans broker, secret, transport,
response or cleanup work. Cleanup cannot rewrite certainty, and possible transmission always
remains ambiguous. This governance gate adds no schema or migration `20260808_0025`.

### Sprint 16 connector materialization-facts and production-bundle signature boundary

ADR-129 prevents production from selecting provider methods, factory lifetimes or bundle fields.
Delivery and observation facts are separate strict values with caller-supplied identities,
credential and provisioning references, and exact request/expiry times. One covariant managed
provider permits one `facts()` call and one exit; leaf factories prevent operation substitution.

The immutable catalog rejects duplicate, disabled, aliased, partial, credential-only and latest
selection. The nine-field public bundle reuses the managed broker factory and excludes secret
buffers, Bearer values, private secret-source and HTTPS transport interfaces, clients, sessions
and responses. No transaction spans provider, broker, secret, transport, outcome or cleanup work,
and no migration `20260808_0025` is introduced.

### Sprint 16 connector materialization-facts public-contract boundary

The implemented contracts keep delivery and observation identities, lease requests and lifetimes
separate and caller supplied. Provisioning selection is pure and fails closed on catalog
cardinality, non-canonical HTTPS endpoints, scope, classification, destination, adapter,
provisioning or credential mismatch. The public bundle contains only nine secret-free factories
and values; private bearer material and HTTPS transport factories are not exported. This gate
adds no persistence, schema or migration `20260808_0025`.
### Sprint 16 production managed connector security boundary

The private production connector validates the exact materialization request and immutable
provisioning entry before secret materialization. Credential material exists only in mutable
request-local buffers, is never included in public contracts, persistence, logs, errors or
evidence, and is overwritten and released exactly once. Transport resources close exactly once in
reverse order while preserving the primary result or exception.

Only complete canonical acknowledgement evidence at exact HTTP `200` can establish delivery.
Local rejection before the governed call boundary is definitely not delivered; every possible
transmission with incomplete evidence is ambiguous. Observation uncertainty is unavailable. No
database transaction spans external I/O and no schema or migration `20260808_0025` is added.

## Sprint 16 connector operation-purpose isolation

One immutable connector provisioning entry carries two distinct server-owned purposes. Delivery
accepts only `connector.invoke`; observation accepts only a fresh `connector.observe` lease. Shared,
swapped, inferred, missing, stale, or cross-operation purpose binding fails closed before secret
materialization or network I/O. The delivery lease, capability, and secret buffer are never reused
for observation. This correction creates no credential storage, schema, migration
`20260808_0025`, provider call, or operator enablement.

The enforced public contract uses two literal fields rather than a generic purpose. Delivery and
observation selectors receive their concrete materialization request and compare only the matching
field. Model-bypass catalog validation repeats the exact-value check, while the observation
capability validates the observation request directly. A purpose mismatch therefore cannot reach
credential materialization, authorization-header construction, or HTTPS I/O.

## Sprint 16 connector provider acceptance

Provider-sandbox acceptance keeps credentials request-local, clears secret and Authorization
buffers, and closes the transport exactly once. Only verified bounded acknowledgement evidence at
the exact provisioned HTTPS destination can produce delivered certainty. Redirects, timeouts,
disconnects, missing or malformed evidence remain ambiguous after the send boundary; rejection
before transport construction is definitely not delivered. PostgreSQL stores only existing CP8
safe result and observation evidence and has no credential, bearer, provider-body, or secret
column. No live provider, operator credential, schema, or migration `20260808_0025` is enabled.

## Sprint 16 closeout security boundary

Sprint 16 is complete only within the merged, explicitly provisioned, single-destination connector
boundary from PR #146 through PR #161. Exact tenant, organization, classification, lineage, attempt,
adapter, destination, credential-lease, purpose, idempotency, acknowledgement, and observation
binding remains fail closed. Existing CP8 append-only lifecycle and reconciliation persistence stays
authoritative, with the single Alembic head `20260808_0024` and no migration `20260808_0025`.

The closeout does not expose or persist secret material, activate a live endpoint or production
credential, grant redirect authority, select a dynamic destination, claim external
business-effect exactly-once, deploy software, or create a tag or release. Operator enablement
remains separate from Sprint 16 completion.

## Sprint 17 operator-enablement security boundary

ADR-131 authorizes governance of one deployment-owned immutable, secret-free connector manifest;
it does not activate a live endpoint or credential. The deployment operator owns manifest
integrity, exact version selection, secret-manager configuration, credential creation, rotation,
revocation, controlled process replacement, rollback, and emergency disablement. A merge, startup,
request, Worker claim, successful sandbox test, or provider response is not enablement authority.

The manifest contains only bounded approved provisioning facts and opaque credential references.
It contains no bearer value, token, key, secret-manager payload, filesystem secret path, or
environment secret. Public contracts, persistence, audit, logs, errors, metrics, and provider
evidence remain secret-free. Request-local secret bytes are materialized only after exact binding,
held in one private mutable buffer, and overwritten and released exactly once.

Dynamic URLs, redirects, caller endpoints, environment-selected implementations, mutable
`app.state`, service locators, latest-row selection, and fallback are prohibited. Tenant,
organization, classification, lineage, attempt, destination, adapter, permit, envelope,
idempotency, provisioning, credential, operation purpose, and time mismatches fail closed before
secret materialization or network I/O. No PolicyOS provisioning registry, backfill, schema, or
migration `20260808_0025` is approved; the Alembic head remains `20260808_0024`.

The operator-manifest public-contract correction treats the existing one-entry provisioning
catalog as the only runtime manifest representation. Its provisioning reference remains the
immutable version identity. Construction requires the exact canonical HTTPS path
`/v1/runtime/connector` and rejects alternate paths, trailing slash, query, fragment, userinfo, or
non-HTTPS endpoints before credential acquisition or secret materialization. No second manifest
wrapper, manifest digest/signature authority, secret surface, schema, or migration
`20260808_0025` is added.

## Sprint 17 deployment-neutral private-backend security boundary

ADR-132 keeps secret-manager vendor, workload identity, credential provisioning, pinned-version
selection, rotation, revocation and backend audit outside PolicyOS authority. Production receives
one explicitly injected, version-pinned private accessor; environment variables, filesystem
secrets, unversioned latest aliases, mutable registries, service locators and fallback chains cannot
materialize connector credentials.

PolicyOS copies only the exact purpose-bound result into one private mutable request-local buffer
and overwrites and releases it exactly once on success, failure or cancellation. The hardened
`httpx` transport verifies TLS and hostname, sets `trust_env=False`, rejects redirects, retries,
alternate destinations and ambient proxies, performs at most one bounded call, and closes exactly
once. No secret, Authorization value, vendor response or internal failure detail enters contracts,
logs, metrics, traces, evidence or persistence. Post-call uncertainty remains ambiguous, CP8
evidence remains authoritative, and migration `20260808_0025` remains absent.

## Sprint 17 trusted deadline-clock security boundary

Connector deadline enforcement uses one explicitly injected request-scoped managed trusted UTC
clock with an exact expected reference. It is read once immediately before transport invocation;
the caller-supplied deadline minus the reading must be positive and is used unchanged for all HTTP
timeout phases. Ambient wall clocks, event-loop time conversion, client defaults, rounding,
clamping, refresh, fallback, and cross-request clock reuse are prohibited.

Missing, stale, substituted, wrong-reference, non-UTC, zero, or negative readings fail before the
network-call boundary and reveal no secret or backend detail. Once the call begins, timeout,
cancellation, disconnect, or missing verified evidence remains ambiguous for delivery or
unavailable for observation. Clock cleanup is exactly once and cannot rewrite outcome certainty.
The reading is not persisted and adds no schema or migration `20260808_0025`.

## Sprint 17 private backend signature and TLS trust boundary

The deployment-injected accessor returns secret material only with exact credential, operation
purpose, and provisioning echoes. PolicyOS rejects unbound, immutable, empty, stale, substituted,
cross-purpose, or cross-provisioning results before transport construction and overwrites received
and copied request-local buffers exactly once.

Each request receives a fresh managed clock and fresh explicit SSL context. TLS requires hostname
verification, `CERT_REQUIRED`, and TLS 1.2 or newer; environment/default trust, shared clients,
redirects, retries, alternate destinations, and fallback remain prohibited. The transport receives
only one exact positive duration and performs at most one call. Private signatures expose no secret
or SDK object and add no schema or migration `20260808_0025`.

## Sprint 17 private backend implementation security evidence

The implementation rejects accessor identity, purpose, provisioning, clock-reference, UTC, TLS,
hostname-verification, and deadline mismatches before the network-call boundary. Received, copied,
and Authorization buffers are overwritten and cleared, the managed clock and request-local client
exit exactly once, and post-call uncertainty cannot be promoted to delivered. No secret, raw
provider body, internal exception, ambient proxy, live credential, new schema, or migration
`20260808_0025` is introduced.

## Sprint 17 closeout security boundary

Sprint 17 closes with exact operator-manifest validation, request-local secret handling,
hostname-verifying TLS, one trusted deadline reading, bounded provider evidence, exact replay, and
credential-free PostgreSQL persistence validated through PR #163 to PR #170. No raw secret,
Authorization value, provider body, hidden endpoint, ambient proxy, or inferred identity becomes a
contract, log, audit fact, error, or stored record.

`COMPLETED WITH DEPLOYMENT DEFERRED` is not production enablement. Live credentials, workload
identity, secret-manager vendor, endpoint activation, provider traffic, process deployment,
operations drill, tag, and release require separate authorization. The closeout adds no authority,
schema, backfill, or migration `20260808_0025`; the single head remains `20260808_0024`.

## Sprint 17 atomic outbox-to-effect handoff security boundary

ADR-135 prohibits reconstructing a deliverable effect from an older generic outbox row. One
deliverable submission carries exact caller-supplied effect identity, envelope, lifecycle,
receipt, tenant, organization, classification, lineage, revision, digest, and time facts and
stages them with the base write set and transport receipt in the facade-owned transaction.

No dispatcher, consumption cursor, hidden UUID, hidden clock, digest generation, latest-row
selection, combined status, backfill, schema, or migration `20260808_0025` is authorized. Worker
access begins only from the committed lifecycle head; rollback leaves no partial residue.

## Sprint 17 closed submission-stage contract boundary

The Runtime API stage accepts only a local-only base write set with no outbox or a complete
caller-supplied effect atomic write set. A generic outbox without exact initial-effect facts is
rejected before persistence. The deliverable aggregate is validated by the existing CP8 binding
rules, and only its exact base state and audit facts are used for API logical-result validation.

No effect identity, envelope, lifecycle, receipt, tenant, organization, classification, lineage,
revision, digest, reference, or time is generated or inferred. This gate adds no persistence
behavior, schema, backfill, dispatcher, combined status, or migration `20260808_0025`.

## Sprint 17 active-session initial-effect persistence boundary

The transaction-neutral initial-effect staging helper receives only the validated caller-supplied
aggregate and approved stage time. It cannot read a clock, begin or nest a transaction, commit,
roll back, close, replace a session, select a latest row, or reconstruct an effect from outbox
evidence. The active-session adapter verifies the exact captured root transaction before use.

Base records, outbox, effect, lifecycle revision one, lifecycle head, logical result when present,
and transport receipt either commit in the facade-owned transaction or leave zero residue.
External readers and Workers cannot observe the initial lifecycle before commit. This boundary
adds no secret, authority, schema, backfill, dispatcher, or migration `20260808_0025`.

## Gemini provider evaluation security boundary

ADR-136 restricts initial Gemini evaluation to synthetic `public` data and exact deployment-owned
provider/model/credential configuration. Internal, confidential, and restricted inputs are denied
before client construction and network I/O. Ambient Google credential precedence, environment
proxy inheritance, provider/model fallback, stored interaction history, tools, files, and SDK retry
are prohibited.

The API key, prompt, context, raw response, hidden reasoning, provider error detail, and thought
signature cannot enter public contracts, persistence, audit, logs, errors, or snapshots. The
request-scoped async client closes exactly once on every exit. Safe audit reuses bounded generic
metadata; no schema, backfill, or migration `20260808_0025` is authorized.

Provider-specific immutable classification sets prevent the generic allowlist from silently
broadening Gemini transmission. A Gemini request classified internal, confidential, or restricted
fails before client construction with safe `deny_classification` semantics where applicable.
Neither organization confidential opt-in nor runtime configuration can widen that set.

### Gemini config/privacy contract security boundary

Gemini configuration has one explicit credential owner: the secret-wrapped `GEMINI_API_KEY`.
Settings representations and serialized dumps exclude the credential, and the ambient
`GOOGLE_API_KEY` alias is rejected. Model identity and resilience controls are explicit and
bounded; this checkpoint adds no adapter, network call, provider SDK, schema, backfill, or
migration `20260808_0025`.

The transmission policy copies provider-specific classification sets into an immutable mapping.
Gemini is limited to synthetic `public` data. Internal and confidential inputs fail with
`deny_classification`, restricted inputs retain `deny_restricted`, and no global opt-in can widen
the provider-specific ceiling.

## Gemini wire-revision and local-validation security boundary

ADR-137 prevents provider wire drift from weakening output validation. The adapter sends only the
pinned non-streaming REST profile with storage, background execution, tools, history, redirects,
environment proxy trust, and fallback disabled. It accepts exactly one typed model-output text
item and rejects legacy, unknown, multiple, or non-text output variants.

One bounded Draft 2020-12 schema is meta-validated and compiled before client construction. Remote
references, unsupported vocabularies, excessive depth or nodes, malformed output, non-object JSON,
and schema mismatch fail closed without exposing schema details or raw provider data. Provider
messages, raw bodies, credentials, prompts, hidden reasoning, and validation traces remain absent
from logs, errors, audit, snapshots, and persistence. No schema or migration `20260808_0025` is
introduced.

### Gemini Interactions adapter implementation security boundary

The implementation uses one fixed Google origin and path, an explicit API revision and API-key
header, `trust_env=False`, redirect denial, zero transport retry, and one request-local managed
client. Schema and public-classification failures occur before client construction. The adapter
never accepts a caller URL, API revision, credential alias, provider fallback, tool, file, history,
stream, stored interaction, background execution, or raw provider message.

Only one bounded typed text output is decoded. Exact model and response identity, strict known
transport fields, bounded integral usage, and authoritative local Draft 2020-12 validation are
required before a provider-neutral result is returned. Credentials, prompts, raw bodies, hidden
reasoning, provider messages, and validation traces remain outside persistence, audit, errors,
logs, and snapshots. Network-free tests use synthetic values only; no schema or migration
`20260808_0025` is introduced.

## Gemini optional response metadata and safe diagnostic security boundary

ADR-138 does not relax unknown-field rejection. It adds only documented bounded `service_tier`,
validates it against a closed enum, and discards it before provider-neutral result construction.
Missing optional cached, thought, or tool-use token counters remain unknown rather than being
inferred as zero; present values remain bounded and a non-zero tool-use count fails closed.

The public error remains `invalid_response`. A private bounded structural category may identify
only the validation stage and cannot contain provider values, prompt or response content, schema
fragments, credentials, hidden reasoning, arbitrary text, or stack traces. It is not persisted,
does not broaden audit, and cannot authorize retry, fallback, reclassification, or another live
call. No schema or migration `20260808_0025` is introduced.

## Gemini response wire correction security evidence

The implemented parser validates and discards `service_tier`, preserves missing optional usage as
unknown, and rejects malformed or non-zero tool usage before constructing a provider-neutral
result. Its private diagnostic is selected from a closed enum and contains no provider value,
prompt, response, credential, schema fragment, hidden reasoning, or arbitrary text.

The correction is credential-free and network-free. It changes no public error, classification,
audit, persistence, schema, retry, fallback, or migration boundary.

## Gemini request-rejection diagnostic and single-probe security boundary

ADR-139 keeps provider HTTP 400 and 422 non-retryable and publicly bounded to `invalid_request`,
except for the existing exact policy-block statuses. One private content-free category may encode
only the HTTP status and a closed allowlisted reason. Missing, malformed, oversized, differently
cased, or unknown provider status values collapse to `unclassified`.

Provider bodies, messages, details, field paths, prompts, structured context, schemas, credentials,
model input, raw responses, and arbitrary strings remain excluded from diagnostics, public errors,
logs, audit, persistence, and snapshots. The category cannot authorize retry, fallback, acceptance,
or another call.

The next network-free correction changes only `response_format` to one exact array element. A
separately approved probe keeps the fixed origin, `/v1beta/interactions`, revision header, model,
schema, public classification, retry zero, and fallback zero, and stops after one call regardless
of result. No schema or migration `20260808_0025` is introduced.
