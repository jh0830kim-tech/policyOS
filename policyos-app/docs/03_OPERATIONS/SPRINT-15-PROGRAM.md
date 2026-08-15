 Sprint 15 Runtime Program

## 1. Purpose and authority

This document is the operational control plane for the Sprint 15 Runtime program. It sequences
checkpoint work, defines evidence required to enter and complete each checkpoint, and prevents a
later runtime layer from being implemented before its dependencies and governance decisions are
ready. It does not supersede `AGENTS.md`, the normative Sprint 15 Runtime Architecture Rules, or
ADR-065 through ADR-089. A conflict is recorded under Governance decisions and resolved
before implementation through the appropriate governance change.

Status terms are used precisely:

| Status | Meaning |
| --- | --- |
| Merged | Implemented, reviewed, merged to `main`, and present in the current baseline. |
| Planned | Sequenced but not implemented or approved as current runtime capability. |
| Deferred | Intentionally outside the current checkpoint or Sprint 15. |
| Blocked | Cannot start until a named dependency or decision is resolved. |
| Decision required | Governance must select and document an architecture before implementation. |

## 2. Program objective

Sprint 15 establishes a governed runtime from immutable intent and authority metadata to future
external execution. The program must keep authority, planning, state, registry, audit,
orchestration, adapters, persistence, delivery, API, and workers independently reviewable. Every
side effect must remain bounded by exact scope and an unexpired, unrevoked permit that is
revalidated immediately before the effect.

## 3. Invariants

- DecisionPipeline is not an execution command.
- ReleaseGate is not a permit.
- Request is not authority; review is not approval; approval is not authorization.
- Authorization is not a permit; permit is not admission; admission is not execution.
- ExecutionPlan is not execution; plan validation is not authorization.
- Execution state is not authority state; execution result is not a policy outcome.
- No checkpoint may infer approval, authorization, permit, admission, state progression, retry,
  cancellation, compensation, publication, transmission, deployment, or correctness.
- Runtime records must not contain raw prompts, chain-of-thought, raw model output,
  source-document bodies, credentials, tokens, secrets, or unrestricted provider payloads.
- Tenant, organization, classification, lineage, purpose, action, resource, destination, and
  policy/authorization/registry revisions propagate without fallback, inference, or downgrade.
- Runtime contract versions are explicit and independent of the project release version, Sprint
  number, database migration, Git commit, and Git tag.

## 4. Current baseline

The baseline is `main` after merged grant-provisioning closeout PR #68.

| Checkpoint | Status | Evidence |
| --- | --- | --- |
| CP0 Runtime Architecture | Merged | ADR-065 through ADR-072 and normative architecture rules. |
| CP1 Runtime Authority | Merged | `app.runtime.authority`, ADR-073, focused authority tests. |
| CP2 Execution Planning | Merged | `app.runtime.planning`, ADR-074, focused planning tests. |
| CP3 Execution State | Merged | `app.runtime.state`, ADR-075, PR #37, focused state tests. |
| CP4 Runtime Registry | Merged | `app.runtime.registry`, ADR-076, PR #39, focused registry tests. |
| CP5-Gate-Audit | Merged | `app.runtime.audit`, ADR-078, focused audit tests. |
| CP5-Gate-Ports | Merged | `app.runtime.ports`, ADR-079 and ADR-080, focused Ports tests. |
| CP5 Runtime Orchestration | Merged | `app.runtime.orchestration`, ADR-081, focused Orchestration tests. |
| CP6 Runtime Adapters | Merged | `app.runtime.adapters`, ADR-082, fake and dry-run tests. |
| CP7-Gate-Commit-Facts | Merged | Caller-supplied receipt, digest, and clock facts, ADR-083. |
| CP7 Runtime Persistence | Merged | `app.runtime.persistence`, ADR-084, PostgreSQL integration tests. |
| CP7 Runtime Acceptance | Merged | PR #48 PostgreSQL vertical acceptance, no production-code change. |
| CP8-Gate-Delivery-Contracts | Merged in PR #50 | ADR-085 effect delivery contracts; no storage or external delivery. |
| CP8-Gate-Delivery-Persistence-Contracts | Merged in PR #52 | ADR-086 additive persistence-boundary contracts. |
| CP8 PostgreSQL Delivery Persistence | Merged in PR #53 | Four-table PostgreSQL implementation and migration 0016. |
| CP8 Lifecycle Port conformance | Merged in PR #54 | Persistence implements `append(request)` exactly. |
| CP8 Runtime Delivery Orchestration | Merged in PR #55 | Port-only governed delivery and reconciliation coordination. |
| CP8 Alembic asyncpg blocker | Merged in PR #56 | Migration 0007 executes function and trigger commands separately. |
| CP8 Lifecycle projection cardinality blocker | Merged in PR #57 | Repeated claim, lease, attempt, and result projections use scoped lookup indexes. |
| CP8 Runtime Delivery Acceptance Gate | Merged in PR #58 | PostgreSQL crash-window evidence passed with green CI. |
| CP8 Runtime Delivery | Merged | Approved local delivery, ambiguity, and reconciliation boundary complete. |
| CP9 Governance / ADR-087 | Merged, PR #60 | Transport, principal, application-facade, threat, and error decisions. |
| CP9-Gate-API-Contracts | Merged, PR #61 | Immutable API/application contracts; no production implementation. |
| CP9-Gate-Auth-Claims | Merged, PR #62 | Required issuer/audience settings, issued trust claims, HS256-only zero-leeway verification, immutable verified claims, legacy-token rejection, generic bearer failures, and focused authentication regression. |
| CP9-Gate-Tenant-Organization-Binding-Governance | Merged, PR #63 | ADR-087 amendment fixes lifetime one-to-one binding and fail-closed provisioning, lifecycle, classification, bypass, and downgrade policy. |
| CP9-Gate-Tenant-Organization-Binding | Merged in PR #64 | Lifetime one-to-one model, explicit persistence, self-contained migration `20260807_0018`, fail-closed downgrade, trusted resolver, and PostgreSQL 16 verification. |
| CP9-Gate-Runtime-Permission-Definitions | Merged in PR #65 | Definition-only exact Runtime permissions. No automatic grants, wildcard, or existing role/membership backfill. |
| CP9-Gate-Runtime-Grant-Governance | Merged in PR #66 | ADR-088 fixes `runtime.grant.manage`, append-only evidence, replay, scope, bootstrap, and atomic transaction policy. |
| CP9-Gate-Runtime-Grant-Provisioning | Merged in PR #67 | Governed projection and ledger persistence, exact replay, scoped authority revalidation, fail-closed migration, concurrency, and PostgreSQL 16 evidence. |
| CP9-Gate-Runtime-Permission-Fact-Resolver-Governance | Merged, PR #69 | ADR-089 fixes exact server-owned permission mapping, live projection resolution, non-disclosure, transaction use, and revocation linearization. |
| CP9-Gate-Runtime-Permission-Fact-Resolver | Merged, PR #70 | Caller-owned transaction, fixed lock order, exact live `RolePermission`, no cache or ledger authority. |
| CP9-Gate-Transport-Idempotency-Governance | Merged, PR #71 | ADR-090 fixes mutation scope, trusted scoped replay identity, explicit command version, canonical digest, immutable receipt, and advisory-lock linearization. |
| CP9-Gate-Transport-Idempotency-Contracts | Merged, PR #72 | Bounded command version, explicit commit facts, atomic commit protocol, and exact replay equality; no production persistence. |
| CP9-Gate-Transport-Idempotency-Atomic-Commit-Contract-Correction | Merged, PR #73 | Lock and receipt resolution precede one bounded local mutation; replay and conflict invoke none. |
| CP9 Production Transport Idempotency | Merged, PR #74 | Immutable model, transaction-bound service, and migration `20260808_0021_runtime_api_idempotency.py` are merged. |
| CP9 Trusted Application Facade Governance | Merged, PR #75 | ADR-091 fixes facade transaction ownership, fact binding, digest construction, and error non-disclosure. |
| CP9 Trusted Application Facade Contracts | Merged, PR #76 | Adds transport-safe service inputs, explicit server facts, exact permissions, and canonical digest builders. |
| CP9 Trusted Application Facade Fact-Binding Contracts | Merged, PR #77 | Adds explicit trusted-context facts, clock-free resolver input, and bounded binder/local-operation Protocols. |
| CP9 Trusted Application Facade | Merged, PR #78 | Owns one SQLAlchemy transaction across trusted context, exact permission, fact binding, local operation, and transport idempotency. |
| CP9 Local Fact Binding and Transaction Integration Governance | Merged, PR #79 | ADR-092 fixes exact persisted fact provenance, Registry snapshot boundary analysis, and additive active-transaction Persistence contracts before concrete integration. |
| CP9 Local Fact Binding and Active-Transaction Persistence Contracts | Merged, PR #80 | Adds immutable exact persisted record, permit, Registry, scope, lineage, operation-binding, and active-transaction Port contracts without production integration. |
| CP9 Registry Resolution and Admission Exactness Contracts Gate | Merged, PR #81 | Binds persisted Registry snapshot/reference, resolution request/decision, and admission decision identities, revisions, scope, lineage, action resolution, and permit facts without production integration. |
| CP9 Registry Snapshot Persistence and Active-Transaction Integration Governance | Governed, pending review | ADR-093 requires a separate append-only Registry store, migration `20260808_0022`, exact admission/permit binding, fail-closed downgrade, and caller-owned session participation; production implementation remains deferred. |
| CP9 Active-Transaction Write-Set and Session Binding Governance | Governed, pending review | ADR-094 rejects marker staging, selects existing closed atomic/reconciliation payloads, and requires one-shot exact session/root-transaction binding before implementation. |
| CP9 Reconciliation Request Persistence Ownership and Atomic Integration Sequencing Governance | Governed, pending review | ADR-095 assigns authoritative request persistence to a dedicated append-only table in migration `0022` and separates persistence evidence from later concrete facade composition. |
| CP9 Registry/Reconciliation Persistence and One-Shot Active Transaction | Implemented, pending review | Adds migration `20260808_0022`, append-only Registry/reconciliation storage, deterministic serialization, exact repositories, and one-shot caller-session/root staging without concrete facade integration. |
| CP9 Authoritative Mutation Result and Query Projection Ownership Governance | Governed, validated, pending review | ADR-097 fixes domain-callback ownership for new mutation results, receipt ownership for replay, exact persisted-state query reads, and the separate bounded public-contract amendment required before concrete integration. |
| CP9 Runtime Lifecycle and Public Projection Domain Governance | Governed, validated, pending review | ADR-098 fixes all seventeen lifecycle projections, result cardinality, exact state-revision digest ownership, and the request-scoped locator boundary; public-domain, persistence-read, and integration gates remain. |
| CP9 Runtime Lifecycle Public Contracts | Merged, PR #91 | Adds the eight approved public statuses, immutable total lifecycle mapping, strict result-cardinality contract, and pure count validator; persistence/read and concrete integration remain blocked. |
| CP9 Exact Query Locator and State-Revision Read Contracts | Merged, PR #92 | Adds closed query-only state/result/audit locators, mandatory expected revisions, and an exact state-revision read result exposing only the stored digest; repository implementation and concrete integration remain blocked. |
| CP9 Authoritative Domain-Operation Result Contracts | Implemented, validated, pending review | Adds one strict sibling-output contract, request-scoped callback Protocol, and trusted expected submission invocation-reference carriage with pure exact command/stage/result binding; implementation remains blocked. |
| CP9 Application Integration | Merged, PR #98 | Composes the existing facade with a one-shot facts provider, pure binder, exact persistence reads, domain callback, local stage, and transport receipt in one caller-owned transaction; routes remain deferred. |
| CP9 Runtime Route Trusted Preparation and Production Composition Governance | Governed, pending review | ADR-100 fixes header-only mutation idempotency, one exact server-owned prepared-operation package, composition ownership, thin route placement, bounded errors, and the PostgreSQL/HTTP acceptance boundary; contracts and routes remain separate. |
| CP9 Managed Request-Capability Public Contracts | Implemented, validated, pending review | Adds one covariant structural managed-resource Protocol and exact managed return annotations for the six private request leaf factories; production lifecycle and routes remain blocked. |
| CP9 Runtime API | Planned / Blocked | The production facade and production routes remain ordered blockers. |
| CP10 Workers | Planned | Worker implementation is not present. |

The current runtime has immutable Authority, Planning, State, Registry, Audit, and Ports contracts;
governed CP7 Orchestration; deterministic fake and dry-run Adapters; and PostgreSQL Persistence.
CP8 delivery Persistence now includes lifecycle, claim, retry, dead-letter, and reconciliation
storage. Persistence PR #53, Lifecycle Port conformance PR #54, Governed Delivery Orchestration PR #55,
Alembic blocker PR #56, projection-cardinality blocker PR #57, and Runtime Delivery Acceptance
PR #58 are merged. Migration head is `20260808_0021`, and CP8 Runtime Delivery is complete. No real external adapter, runtime API, Worker, queue, polling
loop, scheduler, live credential resolution, or external side effect exists.

## 5. Program work structure

Program checkpoint numbers are fixed:

```text
CP0 Runtime Architecture
CP1 Runtime Authority
CP2 Execution Planning
CP3 Execution State
CP4 Runtime Registry
CP5 Runtime Orchestration
CP6 Runtime Adapters
CP7 Runtime Persistence
CP8 Runtime Outbox
CP9 Runtime API
CP10 Runtime Workers
Sprint 15 Final Review
```

Checkpoint numbering is a delivery sequence, not a statement that every dependency is delivered
in the immediately preceding numbered checkpoint. Runtime Audit contracts and Runtime Ports are
explicit CP5 prerequisite gates. They require approved package placement and ADR coverage before
CP5 orchestration implementation begins. ADR-077 fixes their review order as CP5-Gate-Audit
followed by CP5-Gate-Ports without renumbering CP5 through CP10.

## 6. Checkpoint controls

### CP0 - Runtime Architecture

- **Status:** Merged.
- **Purpose:** Freeze the runtime vocabulary, package boundaries, dependency direction, authority
  separation, state graph, registry model, audit/idempotency rules, persistence/outbox boundary,
  and adapter invocation architecture.
- **Entry conditions:** Sprint 14 immutable contracts complete; existing execution,
  orchestration, zero-trust, MCP, provider, and persistence capabilities inventoried.
- **Allowed outputs:** ADR-065 through ADR-072 and normative architecture rules only.
- **Allowed scope:** Architecture documentation and focused architecture guards.
- **Security gates:** Permit-before-effect, tenant and organization isolation, classification
  monotonicity, bounded selectors, credential exclusion, and sensitive-content prohibition.
- **Verification:** Architecture documents exist; frozen normative phrases are tested; Sprint 14
  packages have no reverse runtime imports.
- **Completion:** Architecture artifacts merged and no runtime production package created by CP0.
- **Handoff:** CP1 may implement authority metadata only.
- **Excluded:** Runtime models, services, adapters, repositories, migrations, API, workers,
  schedulers, credential resolution, and external calls.

### CP1 - Runtime Authority

- **Status:** Merged.
- **Purpose:** Represent requests, review/approval/authorization references, bounded permit
  references, admission decisions, revocations, and immutable authority bundles.
- **Entry conditions:** CP0 merged; ADR-073 approved; Sprint 14 contracts unchanged.
- **Allowed outputs:** `app.runtime.authority`, ADR-073, focused authority tests, narrow exports and
  architecture-guard updates.
- **Allowed scope:** Strict frozen metadata models and pure fail-closed validation.
- **Security gates:** Exact actor/agent/user separation; tenant/organization equality; permit
  ceilings and time bounds; classification monotonicity; no authority issuance.
- **Verification:** Strictness, canonical ordering, scope matching, permit bounds, denial and
  invalidation behavior, dependency and sensitive-data guards.
- **Completion:** Authority contracts validate caller-supplied facts and execute nothing.
- **Handoff:** CP2 may consume admitted immutable authority without modifying CP1 contracts.
- **Excluded:** Planning, state, registry runtime, orchestration, persistence, API, workers, I/O,
  permit minting, and live admission service behavior.

### CP2 - Execution Planning

- **Status:** Merged.
- **Purpose:** Record deterministic, metadata-only execution intent bound to admitted authority and
  an exact DecisionPipeline identity.
- **Entry conditions:** CP1 merged; admitted authority bundle available; ADR-074 approved.
- **Allowed outputs:** `app.runtime.planning`, ADR-074, focused planning tests and narrow exports.
- **Allowed scope:** Plans, steps, dependencies, reference-only input/output bindings, bounded
  retry/timeout metadata, compensation references, validation records, and audit metadata.
- **Security gates:** No action discovery, adapter invocation, payload storage, authority
  expansion, classification downgrade, implicit retry, or compensation authority.
- **Verification:** Exact authority/pipeline binding, acyclic canonical graph, selector and lineage
  propagation, bounded retries, strict immutable models, and no executable callbacks or I/O.
- **Completion:** A validated plan remains inert metadata and changes no state.
- **Handoff:** CP3 may consume validated plan metadata and admitted authority.
- **Excluded:** Registry lookup, state transition, orchestration, adapters, persistence, outbox,
  API, workers, scheduler, and side effects.

### CP3 - Execution State

- **Status:** Merged.
- **Evidence:** CP3 merged in PR #37.
- **Purpose:** Realize the closed ADR-067 lifecycle through explicit transition request, decision,
  append-only record, and immutable current-state contracts.
- **Entry conditions:** CP2 merged; ADR-075 approved; exact authority and optional plan references.
- **Allowed outputs:** `app.runtime.state`, ADR-075, focused state tests and narrow architecture
  guard updates.
- **Allowed scope:** Caller-supplied transitions, optimistic revisions, idempotency keys, attempt
  identity, history validation, terminal-state enforcement, and safe reason/error references.
- **Security gates:** Authority states excluded from execution state; scope and classification
  preserved; permits are references only; no automatic progress or hidden clock.
- **Verification:** Normal path requires explicit transitions; invalid edges and stale revisions
  fail closed; terminal states never reopen; history is contiguous and append-only.
- **Completion:** State metadata merged while orchestration, persistence, and execution remain
  absent.
- **Handoff:** CP4 may define immutable registry snapshots without changing CP1-CP3 contracts.
- **Excluded:** Operational transition service, retry execution, cancellation or compensation
  operation, audit transport, registry, ports, adapters, persistence, API, and workers.

### CP4 - Runtime Registry

- **Status:** Merged.
- **Purpose:** Define enumerable governed actions and immutable registry snapshots without
  executable dynamic discovery.
- **Entry conditions:** CP0-CP3 merged; ADR-068 requirements reconciled with the action identity,
  version, registry revision, schema reference, and selector shapes already recorded by CP2;
  registry package placement and contract-compatibility evidence approved.
- **Allowed outputs:** `app.runtime.registry`, an implementation ADR if required, immutable action
  definitions/versions/capabilities/schema references/risk profiles/side-effect levels/adapter
  references, snapshots and pure validation, focused tests, narrow exports and guard updates.
- **Allowed scope:** Registry metadata and snapshot resolution only. The production registry
  package imports neither Planning nor State. Existing CP2 plans retain their recorded action
  ID/version/revision semantics; CP4 defines independent contracts with structurally and
  semantically compatible fields.
- **Security gates:** No callback, dynamic import, credential, arbitrary payload, implicit action,
  runtime self-registration, policy decision, permit issuance, adapter call, or I/O.
- **Verification:** Unknown/disabled/substituted/revision-mismatched actions fail closed; immutable
  snapshots are canonical; side-effect requirements never confer authority; test-level
  structural and semantic compatibility proves that CP2 references can be checked downstream
  without a Registry-to-Planning production bridge.
- **Completion:** CP4 artifacts merge independently and CP0-CP3 regressions remain green.
- **Handoff:** Before CP5, Runtime Audit contracts and Runtime Ports must be designed, approved,
  and tested as explicit prerequisite gates.
- **Excluded:** Audit transport, orchestration, adapter implementation, repository implementation,
  outbox, API, workers, credentials, external invocation, and CP5+ behavior.

### CP5-Gate-Audit - Runtime Audit contracts

- **Status:** Merged.
- **Purpose:** Supply immutable append-only safe event contracts before any orchestrator can
  request or persist audit facts.
- **Entry conditions:** CP4 and ADR-077 merged; clean gate-specific branch; implementation ADR
  approved; CP1-CP4 public contracts unchanged.
- **Allowed outputs:** `app.runtime.audit`, implementation ADR, immutable safe events and pure
  validation, focused tests, narrow root exports and architecture-guard updates.
- **Dependency direction:** Audit may import stable public Authority, Planning, State, and Registry
  contracts. None of those packages imports Audit.
- **Security gates:** Audit is not authority or proof of correctness; metadata is allowlisted,
  bounded, tenant/organization-bound, classification-aware, revision-aware, and free of sensitive
  content.
- **Verification:** Append-only sequence and scope tests, event-field safety tests, dependency and
  infrastructure guards, CP0-CP4 regressions, Ruff, import smoke, and `git diff --check`.
- **Completion:** Audit contracts and implementation ADR merge independently with green CI.
- **Excluded:** Sink, logging, transport, repository, database, filesystem, network, queue,
  orchestration, adapter, credential, API, worker, and side effect.

### CP5-Gate-Ports - Runtime Port contracts

- **Status:** Merged.
- **Purpose:** Supply implementation-neutral protocols consumed by Orchestration and implemented
  only by later Adapters or Persistence checkpoints.
- **Entry conditions:** CP5-Gate-Audit merged; clean gate-specific branch; implementation ADR and
  exact port surface approved.
- **Allowed outputs:** `app.runtime.ports`, implementation ADR, immutable invocation/result/error
  envelopes, and Protocol contracts for adapters, repositories, transaction, outbox storage,
  clock, cancellation, and tenant-bound credential broker.
- **Dependency direction:** Ports may import stable runtime domain and Audit contracts; Ports must
  not import Orchestration or any implementation package.
- **Security gates:** Protocols contain no implementation, credentials, raw provider payloads,
  hidden clock, default provider, policy decision, permit issuance, or I/O.
- **Verification:** Protocol-only and envelope tests, dependency and sensitive-field guards,
  CP0 through Audit-gate regressions, Ruff, import smoke, and `git diff --check`.
- **Completion:** Ports contracts and implementation ADR merge independently with green CI.
- **Excluded:** Production test doubles, adapter/repository/transaction/outbox implementations,
  orchestration, database, filesystem, network, environment access, API, workers, and side effects.

### CP5 - Runtime Orchestration

- **Status:** Merged.
- **Purpose:** Purely coordinate validated authority, plan, registry, state, audit, and port
  contracts while requesting explicit decisions and transitions.
- **Entry conditions:** CP4 plus Audit and Ports gates complete; dependency direction approved;
  orchestration ADR approved if existing ADRs are insufficient.
- **Allowed outputs:** `app.runtime.orchestration`, pure application coordination contracts and
  services, focused fake-port tests, narrow exports and guard updates.
- **Allowed scope:** Deterministic coordination over supplied facts and port interfaces.
- **Security gates:** No direct external call, repository bypass, authority invention, automatic
  transition, retry, compensation, cancellation, or result correctness claim.
- **Verification:** Denied/missing/stale authority fails closed; exact registry/plan/state binding;
  requested audit facts; fake ports prove no infrastructure coupling.
- **Completion:** Pure orchestration is independently testable with no real adapter or storage.
- **Handoff:** CP6 may implement fake and dry-run adapters against approved ports first.
- **Excluded:** Real adapters, database, transaction, outbox delivery, API, worker, credential
  implementation, and live execution.

### CP6 - Runtime Adapters

- **Status:** Merged for deterministic fake and dry-run adapters.
- **Purpose:** Implement governed invocation ports, beginning with fake and dry-run adapters before
  any real model, provider, MCP, connector, or approved external/internal action adapter.
- **Entry conditions:** CP5 merged; adapter and credential-broker ports stable; invocation envelope
  and result/error references approved; permit revalidation boundary testable.
- **Allowed outputs:** Fake and dry-run adapters first; only then separately approved real adapters,
  adapter-specific tests and security reviews.
- **Allowed scope:** Execute only a validated invocation envelope through ports.
- **Security gates:** Immediate permit revalidation, exact destination, tenant-bound credential
  resolution, redirect/substitution rejection, no policy or permit decisions, bounded results.
- **Responsibility boundary:** Repository and transaction/outbox-storage port implementations
  belong to CP7 Persistence, not CP6. Adapters do not call repositories or bypass State, the
  application boundary, or policy.
- **Verification:** Fake/dry-run zero-side-effect tests; selector mismatch rejection; expired or
  revoked permit rejection; credential non-persistence; typed timeout/cancellation ambiguity.
- **Completion:** Required fake/dry-run evidence passes before any real adapter is enabled.
- **Handoff:** CP7 may implement repositories and local transaction boundaries.
- **Excluded:** Adapter self-registration, API responses, direct state mutation, unrestricted raw
  payloads, automatic retries, persistence, outbox delivery, API, and workers.

### CP7-Gate-Commit-Facts - Persistence receipt provenance

- **Status:** Merged.
- **Purpose:** Close the repository and transaction receipt-provenance gap before a production
  Persistence implementation can generate or infer hidden identifiers, digests, or time.
- **Entry conditions:** CP6 fake/dry-run adapters merged; Ports and Orchestration contracts stable;
  ADR-083 approved on a dedicated branch.
- **Allowed outputs:** Caller-supplied repository receipt identity, immutable typed transaction
  record receipt facts, transaction digest and clock references, pure validation, focused Ports
  and Orchestration tests, and ADR-083 documentation.
- **Allowed scope:** Amend the minimum CP5 Ports surface required for deterministic CP7 receipts
  while retaining `RuntimeTransactionPort.commit(write_set)`.
- **Security gates:** No hidden UUID, hash, clock, sorting, database, repository implementation,
  transaction implementation, migration, retention job, or Outbox delivery.
- **Verification:** Exact record-set binding, canonical receipt identities, substituted receipt
  rejection, injected-clock reference binding, CP0-CP6 regressions, Ruff, import smoke, and
  `git diff --check`.
- **Completion:** The gate merges independently with green CI before CP7 production code begins.
- **Excluded:** SQLAlchemy models, repository implementations, migrations, storage I/O, API,
  workers, releases, tags, and CP8 delivery behavior.

### CP7 - Runtime Persistence

- **Status:** Merged.
- **Purpose:** Implement approved repository ports and a local transaction boundary for validated
  runtime facts.
- **Entry conditions:** CP7-Gate-Commit-Facts merged; CP5 ports stable; CP6 boundaries reviewed;
  storage design and migrations approved; tenant partitioning and retention decisions recorded
  by ADR-083.
- **Allowed outputs:** `app.runtime.persistence`, repository implementations, transaction manager,
  migrations, optimistic revision and uniqueness enforcement, integration tests.
- **Allowed scope:** Store/retrieve validated authority, plan, state, audit, result, permit, and
  idempotency facts through ports.
- **Security gates:** Repositories make no policy decision, issue no permit, choose no action, and
  advance no state; tenant/classification isolation and sensitive-data exclusions apply.
- **Verification:** Repository contract tests, concurrency and uniqueness tests, transaction
  rollback, tenant isolation, migration upgrade/downgrade, and retention-policy guards.
- **Completion:** Local storage is consistent and cannot bypass orchestration/application rules.
- **Handoff:** CP8 may add transactional outbox and delivery/reconciliation machinery.
- **Excluded:** External atomicity claims, outbox dispatch, adapters called from repositories,
  API, workers, automatic lifecycle progression, and cross-tenant fallback.

### CP7 Runtime Acceptance Gate

- **Status:** Merged.
- **Purpose:** Prove the merged CP0-CP7 layers as one PostgreSQL-backed vertical slice before CP8.
- **Entry conditions:** CP7 merged; PostgreSQL 16 integration environment available; production
  Fake Adapter, Orchestration, repository, and transaction implementations unchanged.
- **Allowed outputs:** PostgreSQL acceptance tests, test-only fixtures, operational evidence, and
  narrow Program/Roadmap status updates.
- **Security gates:** Exact tenant and classification scope; explicit State and Audit revisions;
  no direct ORM seeding of governed heads in the success scenario; no external I/O; no hidden
  identifier, digest, clock, authority, or lifecycle generation.
- **Verification:** Request through Result read-back; wrong-tenant absence; exact injected-clock
  counts; mid-transaction conflict rollback; CP0-CP7 regressions; full clean CI.
- **Completion:** Both PostgreSQL acceptance tests pass without skip and the dedicated PR merges
  with green CI.
- **Excluded:** Production code changes, result atomicity claims, CP8 delivery, API, workers,
  provider/model/MCP/connector calls, tags, releases, and version changes.

### CP8-Gate-Delivery-Contracts

- **Status:** Merged in PR #50.
- **Purpose:** Implement the ADR-085 immutable contract surface required to distinguish one stable
  external effect from its claims and delivery attempts before CP8 storage or delivery behavior is
  introduced.
- **Entry conditions:** CP7 and CP7 Runtime Acceptance merged; ADR-085 accepted; existing Ports,
  Persistence, Orchestration, and Adapter public contracts inventoried; no CP8 implementation
  branch may be reused as the gate branch.
- **Package placement:** Extend `app.runtime.ports` with immutable effect, envelope, lifecycle,
  claim, lease, attempt, retry-decision, dead-letter, reconciliation, repository, observation, and
  delivery Protocol contracts. Add only narrowly additive request/outcome contracts and validation
  to the existing `app.runtime.orchestration` boundary. Do not create `app.runtime.outbox`.
- **Allowed outputs:** Strict frozen contracts, Protocols, pure validation, explicit tuple exports,
  focused contract tests, architecture guards, and narrow ADR, Roadmap, and Program corrections.
- **Allowed scope:** Stable effect identity across attempts; effect fingerprint validation;
  reference-only delivery envelope; closed append-only lifecycle; one active bounded claim;
  caller-supplied lease and attempt facts; bounded retry decisions; explicit ambiguity;
  dead-letter and reconciliation metadata.
- **Security gates:** Attempt identity is excluded from effect-level uniqueness; no authority,
  permit, credential, retry, success, lifecycle transition, identifier, digest, or timestamp is
  inferred or generated; no raw payload or secret crosses the contracts.
- **Verification:** Mismatched effect and idempotency reuse; lifecycle graph; active-claim conflict;
  definitely-not-delivered retry eligibility; ambiguous no-retry; exhausted and prohibited retry;
  terminal dead letter; bounded reconciliation outcomes; tenant, organization, classification,
  lineage, and dependency-direction guards.
- **Completion:** Merged independently with green CI and proved no database, migration, queue,
  Worker, API, network, adapter call, global clock, hidden UUID/hash, or retry loop exists.
- **Handoff:** CP8 may implement the approved Ports contracts in Persistence and extend the
  existing Orchestration application boundary without redefining the gate contracts.
- **Excluded:** SQLAlchemy models, Alembic migrations, PostgreSQL repositories, claim queries,
  dispatchers, schedulers, broker clients, credential resolution, real adapters, external effects,
  retry execution, Workers, API, tags, releases, and version changes.

### CP8-Gate-Delivery-Persistence-Contracts

- **Status:** Merged in PR #52.
- **Purpose:** Define narrow additive Ports facts for initial stable effect, complete envelope, and
  `ENQUEUED` lifecycle storage in the CP7 atomic transaction, plus bounded due selection,
  optimistic lifecycle append, claims, identical replay, and exact receipts.
- **Entry conditions:** The delivery-contract gate merged in PR #50 and ADR-086 merged; current
  Ports, Persistence, and Orchestration surfaces inventoried on a clean dedicated gate branch.
- **Allowed outputs:** Immutable additive Ports contracts and Protocols, pure validation, explicit
  tuple exports, focused contract tests, architecture guards, and narrow documentation updates.
- **Required semantics:** Caller-supplied facts; effect uniqueness without attempt identity; exact
  original-receipt replay for an identical fingerprint; typed conflict for a mismatched
  fingerprint; exact classification.
- **Completion:** Merged independently in PR #52 with green CI and no SQLAlchemy model, repository
  implementation, migration, Orchestration service, adapter call, Worker, queue, scheduler, API,
  retry loop, or sleep.
- **Handoff:** CP8 Persistence implementation began without redefining approved effect or
  persistence-boundary contracts; Orchestration remains a separate implementation step.
- **Excluded:** The gate itself added no production implementation, migration `0016`, PostgreSQL
  claim query, external call, polling, scheduling, automatic retry, tag, release, or version change.

### CP8 - Runtime Outbox

- **Status:** Merged. Contracts PR #50, persistence contracts PR #52, Persistence PR #53,
  conformance PR #54, Orchestration PR #55, blocker PRs #56 and #57, and Acceptance PR #58 all
  merged with green CI.
- **Package placement:** Resolved by ADR-085. Immutable contracts and Protocols belong to
  `app.runtime.ports`; PostgreSQL storage belongs to `app.runtime.persistence`; governed delivery
  coordination belongs to the existing `app.runtime.orchestration` application boundary; exact
  external effects remain Adapter Port implementations. `app.runtime.outbox` is prohibited.
- **Purpose:** Add transactional outbox, effect-level idempotency, bounded retry, dead-letter facts,
  and reconciliation without claiming external atomicity.
- **Entry conditions:** CP7 transaction boundary and Acceptance Gate merged; the delivery-contract
  gate merged in PR #50; ADR-086 merged; `CP8-Gate-Delivery-Persistence-Contracts` merged in PR
  #52 with green CI; effect, lifecycle, reconciliation, persistence-boundary, and receipt contracts
  stable; adapter result and observation references available.
- **Allowed outputs:** Outbox persistence and delivery contracts/implementation, bounded delivery
  attempts, dead-letter and reconciliation records, focused integration tests.
- **Allowed scope:** Atomically commit local state/audit/idempotency/outbox facts, then deliver
  governed work through the application/orchestration boundary and adapter ports without
  bypassing either boundary.
- **Security gates:** Revalidate time-sensitive authority and permits before every effect;
  preserve one stable effect identity across attempts; no unrestricted payload, credential,
  silent repeat, unbounded retry, blind ambiguous retry, hidden compensation, or invented success.
- **Persistence implementation:** PR #53; migration
  `20260805_0016_runtime_effect_delivery.py`; corrective migration `20260805_0017`; exactly four
  delivery tables; PostgreSQL 16 verified.
- **Verification:** Scenarios 12 passed; focused 2 passed; CP8 and CP7 PostgreSQL 22 passed; Ports,
  Delivery, and Architecture 46 passed; order A 177 passed with skip 0; order B 177 passed with
  skip 0; migration upgrade, downgrade, and parity passed.
- **Completion:** Complete. PR #50 and PRs #52 through #58 merged with green CI. PostgreSQL
  vertical Acceptance passed, satisfying the CP8 final completion condition. External uncertainty
  remains explicit and reconcilable; external business-effect exactly-once is not guaranteed.
- **Handoff:** CP9 may begin under separate entry conditions. Routes remain in `app.api`; no
  `app.runtime.api` package is approved. Authentication/RBAC mapping and the transport threat model
  must be reviewed first. CP10 Worker identity, queue, lease, and scheduling remain separate
  governance decisions.
- **Excluded:** Exactly-once business-effect claims, direct API/worker repository access, policy in
  delivery, distributed/two-phase commit, automatic destructive retry, dead-letter redrive, and API
  or Worker implementation.

### CP9 - Runtime API

- **Status:** Planned / Blocked. Governance is merged through PR #77. The production facade is implemented, pending review; concrete local binding, production routes, and combined acceptance remain blocked in that order.
- **Purpose:** Expose authenticated, organization-scoped transport schemas over the approved trusted application facade and Runtime Orchestration boundary.
- **Entry conditions:** The persisted lifetime binding, exact Runtime permissions, governed grant/revoke provisioning, live permission-fact resolver, and transport idempotency persistence are merged through PR #74. ADR-091 merged in PR #75 before this contract amendment; production facade, production routes, combined PostgreSQL/HTTP acceptance, and CP9 closeout follow in order.
- **Binding implementation acceptance:** Model/migration parity; PostgreSQL 16 fresh and existing upgrade; lifetime 1:1 uniqueness; concurrent provisioning conflict; missing, inactive, and revoked binding rejection; exact trusted-scope equality; cross-tenant and cross-organization non-disclosure; and no route, facade, or permission expansion.
- **Allowed outputs:** After the contracts gate, bounded routes in `app.api`, strict schemas in `app.schemas`, trusted application-facade integration, dependencies, and transport tests.
- **Package placement:** Routes belong in `app.api`, schemas in `app.schemas`, and the trusted facade sits between API and Runtime Orchestration. `app.runtime.api` is prohibited.
- **ADR-100 route gate:** Mutation idempotency is header-only. One server-owned request-scoped
  preparation source supplies an exact already-governed operation package; transport, routes,
  generic dependency injection, Persistence, and latest-row lookup cannot manufacture it. A
  narrow transport/preparation contract amendment must merge before production composition and
  the three Runtime routes.
- **Allowed scope:** Authenticate, validate untrusted transport, resolve trusted server-side facts, invoke only the application facade, and return bounded safe results.
- **Security gates:** Exact tenant, organization, principal, membership, actor, optional agent and represented-user binding; no client-supplied Authority, Permit, Plan, State, Registry, Audit, Adapter, or Persistence facts; explicit `Idempotency-Key`; bounded body, header, media type, rate, timeout, and error controls.
- **Excluded:** Direct ORM, Persistence, Adapter, provider, MCP, or connector calls; public due, claim, lease, `DELIVERING`, lifecycle append, retry, or dead-letter endpoints; external exactly-once guarantees; Worker, queue, polling loop, scheduler, and CP10 implementation.
### CP10 - Runtime Workers

- **Status:** Planned.
- **Purpose:** Process only persisted governed work through orchestration and ports while recording
  attempts, audit, delivery, and reconciliation facts.
- **Entry conditions:** CP8 delivery and CP9 application boundary stable; worker identity,
  lease/claim, shutdown, retry and incident rules approved.
- **Allowed outputs:** Governed workers, scheduling/queue integration where approved, operational
  metrics and runbooks, failure/recovery tests.
- **Package placement:** Workers are infrastructure/application entry points outside the
  `app.runtime` domain namespace. CP10 must not create `app.runtime.workers` without a separately
  approved superseding ADR. Queue, lease, identity, and concrete package placement are decided
  before implementation.
- **Allowed scope:** Claim authorized persisted work, revalidate scope and permit, call the runtime
  boundary, and record bounded attempts.
- **Security gates:** No inferred policy, tenant bypass, direct adapter shortcut, hidden retry,
  credential persistence, unbounded concurrency, or silent loss/duplication.
- **Verification:** Lease races, duplicate delivery, cancellation, shutdown, expired authority,
  dead-letter, reconciliation, tenant isolation, and least-privilege worker identity.
- **Completion:** Governed asynchronous processing is operationally reviewable and recoverable.
- **Handoff:** Sprint 15 Final Review evaluates the complete program; no automatic Sprint 16 work.
- **Excluded:** General-purpose arbitrary jobs, ungoverned schedules, cross-tenant batching,
  self-authorized effects, and release/tag actions.

## 7. Program change control

- Checkpoint scope changes require an explicit user-approved task and a clean checkpoint branch.
- A dependency or authority contradiction requires a superseding ADR before implementation.
- Existing accepted ADRs are not silently rewritten by program documentation.
- Each checkpoint updates only the architecture guards needed to allow its approved layer.
- Later packages remain prohibited until their checkpoint or approved prerequisite gate begins.
- New runtime versions are explicit contract facts; no version is inferred from Sprint or Git.
- Scope, risk, decision owner, evidence, and resolution are recorded before a blocked item resumes.

## 8. ADR management

ADR-065 through ADR-072 define the accepted CP0 architecture. ADR-073 through ADR-076 document
the implemented Authority, Planning, State, and Registry domains. ADR-077 fixes the CP5
prerequisite-gate review units and canonical dependency direction. Every new architecture domain
must cite these decisions and add an implementation ADR when package placement, dependency
direction, public contracts, or security behavior is not already sufficiently decided. A
contradiction requires a superseding ADR; roadmap prose alone cannot supersede an ADR. ADR-087
defines the CP9 transport/principal boundary, and accepted ADR-088 independently defines Runtime
grant/revoke authority, provenance, audit, idempotency, and bootstrap policy.

## 9. Git, PR, and CI policy

- Start from clean `main` with `HEAD == origin/main`; use one checkpoint-specific branch.
- Keep each commit independently reviewable and stage only intended checkpoint files.
- PRs state architecture boundaries, exact verification counts, exclusions, and known warnings.
- CI must pass focused checkpoint tests, direct upstream regressions, dependency/security guards,
  Ruff, import smoke where required, dependency checks where required, and `git diff --check`.
- Merge only after review and green CI. Do not tag or change the project version without a
  separate release-governance decision.
- Do not begin the next checkpoint automatically after merge.

## 10. Risk and decision log

| ID | Status | Risk or decision | Required evidence or owner action |
| --- | --- | --- | --- |
| R15-01 | Resolved by ADR-077 | CP5 needs Audit and Ports, but neither has a fixed program CP number. | Use separate CP5-Gate-Audit and CP5-Gate-Ports PRs without renumbering. |
| R15-02 | Resolved by ADR-077 | `AGENTS.md` placed registry/ports after orchestration, contrary to ADR-065. | Correct the operating rule; ADR-065 remains authoritative. |
| R15-03 | Resolved by ADR-076 and CP4 | CP2 records opaque registry references before the registry implementation exists. | Field-level compatibility tests preserve CP2 semantics. |
| R15-04 | Resolved for CP7 by ADR-083 | Physical partitioning and retention schedules were unspecified. | Use logical tenant partitioning and preservation-only retention; require a later approved operational schedule before any purge. |
| R15-05 | Deferred | Real adapter families, credential broker, destination redirect policy, and provider enablement are not selected. | Separate CP6 adapter approvals and threat reviews. |
| R15-06 | Deferred | Worker identity, queue or polling, scheduling, shutdown, and incident model are unspecified. | Decide before CP10 implementation; ADR-085 effect claims do not select a Worker model. |
| R15-07 | Resolved by ADR-085 | CP8 package placement and ownership were unspecified. | Extend Ports, Persistence, and Orchestration in their existing directions; do not create `app.runtime.outbox`. |
| R15-08 | Resolved by ADR-083 | Repository and transaction outputs required receipt IDs, digest, and time that were absent from their inputs. | Carry exact caller-supplied receipt and digest facts in the Ports contracts and bind commit time to an injected clock reference. |
| R15-09 | Resolved by ADR-084 | Sampling the injected clock only after commit could not persist the same timestamp atomically and could report failure after durable storage. | Validate and persist one injected-clock reading at the commit boundary; publish the receipt only after the database commit succeeds. |
| R15-10 | Resolved by Persistence and Acceptance evidence | CP7 attempt-bound idempotency cannot prove one external effect across retries. | Scoped effect-key uniqueness excludes `attempt_id`; identical fingerprint replay returns the original receipt and mismatch fails closed. |
| R15-11 | Resolved by Orchestration and crash-window Acceptance evidence | PostgreSQL cannot atomically prove an arbitrary external business effect or acknowledgement. | Guarantee local atomicity only; preserve acknowledgement ambiguity, prohibit blind retry, and require bounded authorized reconciliation. |

## 11. Security and privacy baseline

All checkpoints use bounded identifiers and opaque references. Raw prompts, chain-of-thought, raw
model output, source-document bodies, credentials, passwords, bearer tokens, API keys, private
keys, unrestricted provider payloads, and arbitrary metadata dictionaries are prohibited in
runtime contracts, logs, errors, audit facts, state, results, and outbox records. Credentials may
be resolved only at the execution boundary through a tenant-scoped broker and must not be stored
in immutable records.

## 12. Isolation and provenance baseline

Tenant and organization must match exactly at every boundary. Classification may remain equal or
become more restrictive, never lower. Actor, agent, represented user, resource, action, purpose,
risk, destination, model/provider/tool/connector identifiers, policy revision, authorization
revision, registry revision, lineage, and provenance remain explicit. No global fallback identity,
substitute lineage, implicit selector, or inferred revision is allowed.

## 13. Sprint 15 Final Review

Final Review requires CP0-CP10 artifacts merged, all architecture and checkpoint suites green,
dependency and sensitive-data guards passing, migrations and operational recovery verified,
security and privacy review complete, unresolved external effects reconcilable, documentation and
runbooks current, and every open decision either resolved or explicitly deferred outside release.
It must confirm that runtime results are not presented as policy outcomes and that no transport,
worker, repository, adapter, or audit component owns authority.

## 14. Definition of Sprint 15 completion

Sprint 15 is complete only after Final Review approval, green CI for the integrated runtime,
reviewed operational evidence, explicit release/version decision, and merge to `main`. Completion
does not imply a Git tag, release publication, production enablement, or Sprint 16 start.

## 15. CP5 prerequisite-gate entry checklist

- CP0 through CP4 and PR #39 are merged on `main`.
- ADR-077 and the corrected `AGENTS.md` dependency direction are merged before production gate
  packages begin.
- CP5-Gate-Audit starts first on its own clean branch with a dedicated implementation ADR.
- CP5-Gate-Ports starts only after Audit merges and has its own clean branch and implementation
  ADR.
- Audit imports only stable public runtime contracts and provides no sink, transport, repository,
  I/O, authority, or correctness decision.
- Ports imports only stable runtime and Audit contracts and provides no implementation or
  Orchestration dependency.
- Each gate has explicit tuple exports, focused dependency/security tests, architecture-guard
  updates, direct upstream regressions, import smoke, and diff checks.
- CP5 Orchestration remains absent until both prerequisite gates merge independently.

## 16. Governance decisions

1. ADR-065 describes Planning as binding Registry contracts, while the fixed program sequence
   implemented Planning and State before CP4 Registry. CP4 therefore defines independent
   registry contracts whose action identity, version, revision, schema references, and selectors
   are structurally and semantically compatible with existing CP2 references. Registry production
   code imports neither Planning nor State and does not validate `ExecutionPlan` objects. Actual
   plan-to-registry binding validation belongs downstream in an approved application/orchestration
   boundary. Changing Planning to import Registry requires separately approved scope and regression
   review; CP2 and CP3 public contracts remain unchanged.
2. ADR-077 resolves the `AGENTS.md` ordering error by making ADR-065 the canonical source and
   correcting the operating-rule summary. Registry, Audit, and Ports are upstream inputs to
   Orchestration. Planning and Registry remain independent under ADR-076.
3. Audit and Ports are required dependencies for CP5 but have no dedicated number in the fixed
   CP0-CP10 program. ADR-077 resolves their review structure as separate CP5-Gate-Audit and
   CP5-Gate-Ports PRs, in that order, without renumbering.
4. ADR-085 resolves the fixed CP8 delivery-stage package decision. Ports own immutable effect and
   delivery contracts, Persistence owns PostgreSQL storage and claim concurrency, Orchestration
   owns governed delivery coordination, Adapters own exact external effects, and no
   `app.runtime.outbox` package is approved. `CP8-Gate-Delivery-Contracts` merged in PR #50.
5. CP8 permits one accepted local enqueue per stable effect identity and enforces effect-level
   deduplication; it does not guarantee exactly-once external business effects. Ambiguous
   acknowledgement is explicit, does not retry blindly, and requires bounded authorized
   reconciliation evidence.
6. ADR-086 fixes the four-table PostgreSQL baseline, optimistic lifecycle head, append-only
   history, bounded due selection, invocation crash boundary, and destructive `0016` downgrade
   gate. PR #52 through PR #58 completed Persistence, Orchestration, corrective migration `0017`,
   and PostgreSQL Acceptance. CP8 is complete without an external exactly-once guarantee.

## 17. Open decisions

- Define the exact immutable Runtime Audit event and append-only validation contracts in its
  implementation ADR.
- Define the exact Runtime Ports protocol and immutable envelope surface in its implementation
  ADR after Audit merges.
- Define the runtime application boundary public contract before orchestration or API work.
- Select credential-broker, destination policy, and real-adapter enablement rules before CP6.
- Implement the ADR-083 PostgreSQL mapping, explicit transaction ownership, logical tenant
  partitioning, and preservation-only retention in CP7; approve any destructive retention
  schedule separately before purge is enabled.
- Treat the ADR-085 stable effect identity, lifecycle, claim, lease, retry, dead-letter, and
  reconciliation contract action as completed by PR #50.
- Treat the ADR-086 additive persistence-boundary contract gate as completed by PR #52.
- Treat CP8 Runtime Delivery as completed by merged PR #58 and preserve its local-atomicity,
  ambiguity, reconciliation, and no-blind-retry boundaries.
- Confirm CP9 routes remain in `app.api`; creating `app.runtime.api` requires a superseding ADR.
- Define API authentication/RBAC mapping before CP9.
- Review the CP9 transport threat model before implementation.
- Decide real-adapter enablement and credential-broker rules before external effects are activated.
- Decide CP10 worker package placement, queue, lease, identity, and scheduling model; workers
  remain outside the `app.runtime` domain unless a superseding ADR approves otherwise.

PR #65 merged the definition-only Runtime permission gate. PR #66 accepted ADR-088 governance and
PR #67 merged the contracts, `runtime_permission_grant_events` ledger, service, model, migration
`20260808_0020_runtime_permission_grant_governance.py`, and PostgreSQL acceptance. The current
migration `20260808_0020` is preserved below the current `20260808_0021` head. `runtime.grant.manage` remains definition-only with automatic
grant 0; the migration infers no actor/provenance backfill and fails closed for existing managed
grants and populated downgrade.

Initial `runtime.grant.manage` authority is provisioned only by a separately trusted
bootstrap/operator procedure outside the public Runtime API. Production routes remain blocked
until the production Runtime permission fact resolver, transport idempotency persistence, and the
trusted application facade are complete. CP9 Runtime API: Planned / Blocked.
CP10: Planned.

### CP9 Runtime transport idempotency governance

ADR-090 governance merged in PR #71. The contracts gate adds an immutable bounded command version,
explicit caller-supplied receipt ID and committed time, a single atomic commit protocol, and exact
replay equality. It creates no model, service, migration, facade, or route.

The contracts gate merged in PR #72. Its atomic commit contract correction supplies a bounded local
mutation to the caller-transaction-owned port. Lock and receipt lookup occur first; exact replay or
conflict invokes no mutation, while a new identity awaits it once and stages a receipt only after
success. The port owns neither commit nor rollback and makes no external exactly-once guarantee.

ADR-090 applies only to `submit_invocation` and `request_reconciliation`; read/status queries do
not use the mutation idempotency gate. The client supplies only a bounded ASCII `Idempotency-Key`.
The trusted application layer constructs the tenant, organization, principal, operation, explicit
command version, idempotency key identity and canonical digest after transport validation and
current authentication, scope, binding, and exact permission resolution.

Every replay revalidates those trust facts before receipt lookup. Exact scoped identity and digest
return the original bounded safe result; any mismatch is a non-disclosing typed conflict. A
caller-owned transaction and transaction-scoped stable PostgreSQL advisory lock serialize the
mutation and immutable receipt write. Receipts are append-only, have no expiry or cascade delete,
and store no raw payload, token, secret, credential, provider body, arbitrary JSON, exception, or
SQL detail. This does not promise external business-effect exactly-once.

Production transport idempotency and migration `20260808_0021_runtime_api_idempotency.py` are
merged in PR #74. The trusted facade and routes remain Planned / Blocked; no Worker,
queue, scheduler, `app.runtime.api`, `app.runtime.outbox`, or CP10 implementation is created.

### CP9 trusted application facade governance

ADR-091 makes the facade the outer application boundary for transport-safe input, immutable
verified claims, the organization selector, and explicit trusted server facts. Routes call only the
facade and cannot construct trusted principal, scope, permission, identity, or digest facts. The
facade owns one `AsyncSession` transaction across principal and scope resolution, exact permission,
the bounded local operation, and idempotency staging; helpers never commit or roll back.

The exact server mapping is `get_invocation → runtime.read`, `submit_invocation → runtime.invoke`,
and `request_reconciliation → runtime.reconcile`. Canonical mutation digests use fixed-order,
length-prefixed UTF-8 fields and `sha256:<64 lowercase hex>`. Replay or conflict invokes no local
mutation; a new request invokes it exactly once after lock and lookup. Missing, stale, revoked,
ambiguous, or cross-scope persisted facts fail closed without inference or disclosure.

ADR-091 governance merged in PR #75 and its facade contract amendment merged in PR #76. The
fact-binding amendment adds explicit strict trusted-context facts to every facade fact contract,
removes implicit clock reads from trusted-context resolution, and defines additive bounded
orchestration-binder and local-operation Protocols. It adds no concrete binder or operation service.

The merged facade contracts add strict transport-safe immutable
service inputs, verified claims and organization-selector facade parameters, explicit immutable
server facts, exact server-owned permission mapping, and pure canonical digest builders. It remains
free of HTTP, ORM, transaction, persistence, and external-effect behavior.

The remaining required order is ADR-093 governance, Registry snapshot persistence and
active-transaction integration, concrete binder/local-operation integration in a separate
checkpoint, production routes, combined CP9 PostgreSQL/HTTP acceptance, CP9 closeout, then
separately approved CP10. CP9 remains Planned / Blocked and CP10 remains Planned.

ADR-093 requires a separate `app.runtime.persistence` Registry store because generic Runtime
record JSON cannot enforce the authoritative snapshot, entry, resolution, and admission-binding
identity graph. Migration `20260808_0022` is required and must add only empty append-only tables:
no existing-data backfill, deduplication, normalization, deletion, inferred identity, or generated
time is allowed. Populated downgrade fails before destructive DDL; an empty schema may downgrade
atomically. Registry remains the domain owner, Authority remains the admission/permit owner, Ports
retain the active-transaction protocol, and Persistence owns the SQLAlchemy schema and
implementation. The facade alone owns begin/commit/rollback/close; helpers use the exact active
caller session without replacement. Registry persistence implementation and concrete
binder/local-operation implementation are separate future checkpoints.

### CP9 Runtime permission-fact resolver governance

ADR-089 fixes `get_invocation → runtime.read`, `submit_invocation → runtime.invoke`, and
`request_reconciliation → runtime.reconcile` as server-owned mappings. Resolution uses the live
`RolePermission` projection through an active membership, organization-scoped role, and exact
permission definition inside the trusted principal, organization, tenant, membership, and binding
scope. The append-only grant ledger is history and cannot substitute for active authority.

Positive and negative permission results are not cached. Resolution and the bounded local
application read or commit share one database transaction so grant/revoke races linearize without
a stale permission fact crossing requests. Missing, inactive, revoked, cross-scope, wildcard,
prefix, substring, and permission-substitution cases fail closed without role, grant, tenant, or
SQL disclosure. The production resolver implements this governance without adding a migration,
facade, route, Worker, queue, cache, or transaction ownership. It remains pending review.

### CP9 governed Runtime permission provisioning

Production provisioning preserves `RolePermission` as the active projection and records every
committed grant or revoke in the append-only `runtime_permission_grant_events` ledger in the same
transaction. `runtime.grant.manage` is definition-only with zero automatic grants; only
`runtime.read`, `runtime.invoke`, and `runtime.reconcile` are eligible targets. Exact replay is
receipt-stable, conflicting replay and concurrent state changes fail closed, and transport,
permission-fact resolution, application facade/routes, outbox, and CP10 remain deferred.

### CP9 explicit integration facts and request-scoped persistence binding

ADR-096 is governed and validated, pending review. It preserves the facade's exact five-parameter
public signatures and requires submission, reconciliation, and invocation-query facts to carry
strict nested operation-specific integration facts. A trusted server-owned preparation boundary
supplies immutable expected candidates once per request; HTTP input, routes, generic dependency
injection, binders, local operations, and Persistence cannot generate or select them.

The pure binder carries those facts into the command or query before idempotency. Replay and
conflict perform zero callbacks, persistence-binding reads, stages, or repository mutations. A new
mutation request re-reads the exact persisted binding inside the facade-owned transaction, then
stages one closed payload and one transport receipt using the same captured session and root
transaction. `get_invocation` performs only the exact read-only verification. The required public
contract amendment, concrete integration, routes, acceptance, and closeout remain separate gates;
CP9 remains Planned / Blocked and CP10 remains Planned.

ADR-103 governs the next rate-admission sequence. Policy revisions and revocations are immutable
and explicitly provisioned; windows are UTC epoch-aligned and half open; exact replay mutates no
counter; admitted new requests append one decision and mutate one exact counter; denied requests
append one decision and mutate no counter. PostgreSQL row serialization plus decision-first
trigger proof must preserve the threshold under concurrency and leave rollback residue zero.
Migration `20260808_0024` has four new tables, no data-writing upgrade, empty-only atomic
downgrade, and populated fail-closed downgrade. This governance does not start contracts,
persistence, routes, CP10, or release work.

### CP9 preparation producer and operational backend ownership

ADR-102 binds preparation and callbacks to explicit application inputs and all operational times
to a trusted clock reference. Exact multi-process rate admission uses PostgreSQL policy revisions
and scoped window counters in migration `20260808_0024`. The migration creates no default policy
and performs no backfill; unprovisioned scope fails closed. Preparation remains non-durable, and
contracts, persistence, production routes, acceptance, and closeout remain separate checkpoints.

The public-contract correction is implemented and validated, pending review. Explicit trusted
clock readings, exact scoped rate-policy selections, operation-specific preparation contexts,
the preparation producer Protocol, and the operation-bound callback capability are now closed
contracts. Backend persistence, production composition, routes, and migration `20260808_0024`
remain blocked behind separate checkpoints.

### CP9 explicit integration facts public contracts

The ADR-096 public-contract amendment is implemented and validated, pending review. Existing
submission, query, and reconciliation facts now require strict nested operation integration facts;
the trusted command or query carries the same validated value to the local-operation boundary.
The public facade methods remain exactly five parameters and existing binder signatures continue
to consume the outer facts value without a separate authority-bearing parameter.

Submission and reconciliation contracts carry exact expected Persistence binding, caller-owned
active-transaction context, closed stage payload, caller-supplied identities, digest, and time.
The query contract carries only exact read identity, expected binding, and transaction context.
Pure validators reject operation, payload, scope, Registry, admission, permit, revision, receipt,
digest, action, and duplicate-identity substitution with bounded conflicts. The request-scoped
provider is a structural Protocol only: no provider, binder, local operation, facade behavior,
route, model, migration, repository, or external effect is implemented by this gate.

### CP9 logical execution-result ownership governance

ADR-099 is governed and validated, pending review. It distinguishes the API logical execution
result from `RuntimeAdapterInvocationResult`, which remains an action-level adapter outcome.
Neither the generic `EXECUTION_RESULT` label nor an audit outcome reference supplies missing
execution-request, attempt, or root-lineage authority. Current/latest selection and promotion of
historical adapter results are prohibited.

The approved persistence direction is a dedicated append-only logical-result revision store in
migration `20260808_0023`, preceded by a separate immutable domain/Port contract gate. The store
must enforce one logical-result ID per exact execution-request and attempt tuple, scoped revision
uniqueness, relational execution-request/state/audit bindings, `ON DELETE RESTRICT`, and
UPDATE/DELETE rejection. Existing rows receive no backfill, normalization, deduplication, or
meaning change. Application Integration remains blocked until both contract and persistence gates
merge; CP9 remains Planned / Blocked and CP10 remains Planned.

The logical-result mutation governance correction requires the submission callback to stage one
closed atomic mutation bundle whose exact state record governs an explicit result-present or
result-absent sibling. `RuntimeApiSafeResult` and reconciliation recovery responses are not the
logical result. Reconciliation cannot create or revise one, and adapter-result contribution
linkage remains outside the approved contract. Production contracts, migration `0023`,
persistence, and Application Integration remain separate checkpoints.

### CP9 logical execution-result public domain and Port contracts

The contract gate implements ADR-099's strict logical-result identity, closed submission
present/absent mutation, and exact result-revision read contract. Exact staged state controls
ADR-098 cardinality; reconciliation can only carry the absent variant. Query locators contain
identity and expected revisions but no caller-authoritative stored result digest/reference.

The existing active-transaction implementation rejects result-present staging before database
work until the dedicated migration `20260808_0023` and repository gate is implemented. The gate
adds no schema, backfill, persistence row, facade behavior, route, external effect, or CP10 work;
CP9 remains Planned / Blocked.

### CP9 logical execution-result persistence and exact-read implementation

Migration `20260808_0023` and the dedicated logical-result repository implement ADR-099's exact
identity and append-only revision ownership. The migration performs no INSERT, inference,
normalization, deduplication, or adapter-result promotion. A populated downgrade fails before any
destructive DDL; an empty schema may downgrade dependency-safely to `20260808_0022`.

The same-session active-transaction capability stages the existing closed atomic write set before
the optional logical-result revision, without opening, committing, rolling back, closing, or
replacing the caller-owned session or root transaction. Result-absent and reconciliation paths add
no logical-result mutation. Exact reads use caller-supplied record IDs and revisions and return
stored provenance unchanged. Concrete provider, binder, local operation, facade composition,
routes, external effects, and CP10 remain deferred.

### CP9 Runtime route transport and trusted preparation contract gate

This gate is implemented and validated, pending review. Mutation transport bodies no longer carry
`idempotency_key`; the future routes must obtain exactly one bounded `Idempotency-Key` header and
pass it explicitly into the unchanged internal submission or reconciliation input. Query transport
has no idempotency identity.

Frozen submission, query, and reconciliation prepared packages close the request-scoped output of
the server-owned trusted preparation source. Mutation packages carry the existing exact outer facts
and domain callback, while the query package contains read-only facts and no mutation capability.
The prepared application-entry Protocol is the only route-facing application boundary. Concrete
preparation, composition, routes, HTTP acceptance, schema, migration `20260808_0024`, Worker, and
CP10 work remain separate checkpoints; CP9 remains Planned / Blocked and CP10 remains Planned.

### CP9 Runtime preparation provenance and operational capabilities

The public-contract gate implements ADR-101 with strict immutable preparation provenance and
closed request/result contracts for rate admission, deadline evaluation, and disconnect
observation. Prepared operation packages require exact provenance, while structural Protocols
define server-owned issuance and request-scoped capability calls. Values remain explicit
application inputs; no clock, UUID, digest, reference, authority, cancellation, or external-effect
outcome is generated. Production implementations, FastAPI dependencies, composition, routes,
schema, migration `20260808_0024`, Workers, and CP10 remain deferred.

ADR-101 governs a same-request, mandatory server-owned preparation issuer. It emits one immutable
operation-specific package to a request-local source whose exact method consumes the package once.
The package carries explicit preparation, request, principal, tenant, organization, operation,
digest, correlation, and validity provenance. It cannot be produced or repaired by transport,
FastAPI dependency injection, facade, binder, Persistence, current/latest lookup, global registry,
callback name, or default fake. Missing, stale, ambiguous, substituted, reused, cross-request, or
cross-operation packages fail closed before facade entry.

The follow-up public-contract gate must define rate admission, deadline budget, and disconnect
observation as strict one-shot application capabilities with explicit scope and time inputs. Their
absence fails closed; timeout or disconnect creates no Runtime cancellation, retry, compensation,
success, or external-effect authority. A dedicated Runtime verified-claims dependency remains
separate from the legacy ORM-user dependency, and only `app.api` owns bounded HTTP translation.
No preparation persistence, model, repository, backfill, schema, or migration `20260808_0024` is
approved. Contract, production route, PostgreSQL/HTTP acceptance, and closeout remain separate;
CP9 remains Planned / Blocked and CP10 remains Planned.
## CP9 rate-admission contract gate

Status: Implemented / Validated, Pending Review. Public immutable contracts
only; persistence, routes, production composition, and CP10 remain blocked.

## CP9 rate-policy permission governance correction

Status: Governed / Validated, Pending Review. ADR-104 separates the immutable permission
definition from active authority, prohibits automatic grants and backfill, and requires exact
transactional grant/revoke evidence. PR #106 remains blocked pending the separated correction and
persistence gates. CP10 remains Planned.

## CP9 rate-admission persistence gate

Status: Implemented / Validated, Pending Review. Migration `20260808_0024` creates the fixed
permission definition with zero grants and exactly four governed persistence tables. Exact replay
and denial mutate no counter; an admitted decision permits one counter mutation in the same caller
transaction. Production backend composition, facade/routes, and CP10 remain blocked.

## CP9 operational preflight and preparation consumption governance

Status: Governed / Validated, Pending Review. ADR-105 assigns exact operational inputs to one
request-scoped server-owned preparation-context provider and requires closed operation candidates.
Candidate inspection is non-consuming. Rate admission, deadline, and disconnect run in fixed order;
all three successes permit one consumption, while denial, expiry, disconnect, mismatch, absence,
or failure terminally rejects the candidate with consumption and facade work zero. Independent
admitted rate evidence remains durable if a later check rejects the request. Public contracts,
production routes, combined PostgreSQL/HTTP acceptance, and CP9 closeout remain separate. No
preparation schema or migration `20260808_0025` is approved. CP10 remains Planned.

## CP9 operational preflight and preparation consumption public contracts

Status: Implemented / Validated, Pending Review. One strict frozen operational-preflight value
closes the exact rate-admission, deadline, and disconnect requests over the same preparation and
trusted clock. Operation-specific candidates and preparation contexts require that value. A
server-owned context-provider Protocol supplies complete inputs, and the request-local source now
separates non-consuming inspection from exact consumption and terminal rejection. Production
source state, capabilities, composition, routes, PostgreSQL/HTTP acceptance, and CP9 closeout
remain separate; migration `20260808_0025` remains prohibited and CP10 remains Planned.

## CP9 production preparation-context injection and composition governance

Status: Governed / Validated, Pending Review. ADR-106 requires one immutable dependency bundle at
application construction and fresh request-scoped preparation and operational capabilities.
Missing composition returns bounded `503` before inspection. Mutable `app.state`, service
locators, environment-selected objects, dynamic imports, callback names, production dependency
overrides, and default fakes are prohibited. Rate admission owns an independent PostgreSQL session
and transaction; the facade remains sole owner of its application transaction. No preparation
persistence or migration `20260808_0025` is introduced. Public contracts, production routes,
combined acceptance, and closeout remain separate; CP9 remains Planned / Blocked and CP10 remains
Planned.
### CP9 production dependency-bundle factory graph governance

ADR-107 fixes one frozen production dependency bundle containing the authoritative preparation
upstream, domain-operation, trusted-clock, independent rate, deadline, disconnect, and asynchronous
request-scope factories. The upstream returns exactly one existing operation-specific preparation
context. The application constructs provider, producer, issuer, source, and prepared entry in that
order, and the async scope disposes every request object exactly once in reverse order.

FastAPI `Request` remains inside `app.api`; application contracts see only a transport-neutral
asynchronous strict-boolean disconnect signal. The public rate factory is SQLAlchemy-free. Missing
composition returns bounded `503` before inspection, while an incomplete supplied bundle fails
application construction. Facade five-parameter signatures and query non-mutation remain intact.
Preparation remains request-local, migration `20260808_0025` is prohibited, CP9 remains Planned /
Blocked, and CP10 remains Planned.

### CP9 dependency-bundle factory-signature correction

The corrected ADR-107 bundle exposes exactly one request-capability-scope factory. It privately
captures the domain-operation, clock, independent rate, deadline, disconnect, and preparation-
upstream leaf factories and invokes each exactly once. The scope accepts only the current request's
transport-neutral disconnect signal, constructs the upstream last from the exact callback and
clock capabilities, and yields one frozen six-field dependency set.

Async exit returns false, suppresses no exception, and disposes complete or partial construction
exactly once in reverse order. Missing-bundle unavailability is an `app.api` production-only entry;
a supplied partial bundle fails application construction. The correction changes no public Python,
production composition, persistence, or migration `20260808_0025`. CP9 remains Planned / Blocked
and CP10 remains Planned.

### CP9 dependency-bundle and upstream public contracts

This gate adds ADR-107's closed public Protocols and immutable values only: exactly one
scope-factory field, six private leaf-factory signatures, an authoritative operation-specific
upstream, a transport-neutral disconnect signal, one async request scope, and one frozen
six-field request dependency set. The bundle exposes no leaf factory directly and the scope exit
suppresses no exception.

Production factories, lifecycle enforcement, preparation source/backend, FastAPI composition,
routes, PostgreSQL/HTTP acceptance, and closeout remain separate. Preparation persistence and
migration `20260808_0025` remain prohibited. CP9 remains Planned / Blocked and CP10 remains
Planned.

### CP9 managed request-capability resource lifetime governance

Status: Governed / Validated, Pending Review. ADR-108 requires each private leaf factory to return
one single-use asynchronous managed resource. The request scope is the sole coordinator, enters
resources in fixed order, exits acquired resources exactly once in reverse order, handles partial
construction, preserves active exceptions, and rejects escape or reuse. Rate admission retains
independent per-call session ownership and facade transaction ownership is unchanged. Public
contracts, production composition/routes, combined PostgreSQL/HTTP acceptance, and closeout remain
separate. No migration `20260808_0025` is approved; CP9 remains Planned / Blocked and CP10 remains
Planned.

The follow-up public-contract gate adds only the governed managed-resource Protocol and six exact
factory return annotations. It does not implement acquisition, guarded views, disposal, production
composition, routes, persistence, or transaction control.

### CP9 Runtime organization transport and operational rejection governance

Status: Governed / Validated, Pending Review. ADR-109 requires exactly one canonical lowercase
hyphenated UUID `organization_id` query parameter on each fixed Runtime endpoint. Missing,
duplicate, aliased, malformed, or non-canonical selectors fail `422` before preparation work;
facade-revalidated scope mismatch remains non-disclosing `404`. Deadline expiry, disconnect,
capability failure, and missing preparation/composition share a generic `503`
dependency-unavailable envelope and create no cancellation, retry, compensation, success, or
effect-termination authority. Rate denial alone remains `429` with exact persisted retry-after.
Production Python, HTTP acceptance, migration `20260808_0025`, CP10, tag, and release remain
deferred.

### CP9 Runtime required-audience configuration ownership

Status: Governed / Validated, Pending Review. ADR-110 makes the mandatory immutable
`runtime_api_required_audience` process setting the sole owner of the production facade's exact
audience. It must be a non-empty, trimmed, bounded exact member of `jwt_audiences`; missing,
malformed, or non-member configuration fails application construction. Selecting the first
allowlisted audience or deriving one from token claims, prepared facts, request values,
dependencies, or persistence is prohibited.

The production dependency bundle retains exactly one request-scope-factory field, facade public
signatures remain unchanged, and no schema or migration `20260808_0025` is approved. A separate
config-contract correction, production composition/routes, PostgreSQL/HTTP acceptance, regression,
and closeout remain blocked. CP9 remains Planned / Blocked and CP10 remains Planned.
