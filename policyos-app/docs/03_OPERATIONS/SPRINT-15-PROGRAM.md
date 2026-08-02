# Sprint 15 Runtime Program

## 1. Purpose and authority

This document is the operational control plane for the Sprint 15 Runtime program. It sequences
checkpoint work, defines evidence required to enter and complete each checkpoint, and prevents a
later runtime layer from being implemented before its dependencies and governance decisions are
ready. It does not supersede `AGENTS.md`, the normative Sprint 15 Runtime Architecture Rules, or
ADR-065 through ADR-075. A conflict is recorded under Governance inconsistencies and resolved
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

The baseline is `main` after merged PR #37.

| Checkpoint | Status | Evidence |
| --- | --- | --- |
| CP0 Runtime Architecture | Merged | ADR-065 through ADR-072 and normative architecture rules. |
| CP1 Runtime Authority | Merged | `app.runtime.authority`, ADR-073, focused authority tests. |
| CP2 Execution Planning | Merged | `app.runtime.planning`, ADR-074, focused planning tests. |
| CP3 Execution State | Merged | `app.runtime.state`, ADR-075, PR #37, focused state tests. |
| CP4 through CP10 | Planned | No corresponding runtime implementation is present. |

The current runtime is immutable metadata and pure validation only. It has no registry package,
audit package, ports, orchestration, adapter, persistence, outbox, runtime API, worker, live
provider invocation, credential resolution, or external side effect.

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
CP5 orchestration implementation begins.

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

- **Status:** Planned.
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

### CP5 prerequisite gates - Runtime Audit and Runtime Ports

- **Status:** Decision required.
- **Blocker:** Package placement and ADR treatment must be approved before CP5 may enter.
- **Purpose:** Supply the stable contracts that ADR-065 says orchestration imports and uses.
- **Entry conditions:** CP4 merged; governance inconsistency resolved; no change to fixed CP
  numbering without explicit approval.
- **Allowed outputs:** Approved ADR or superseding ADR, `app.runtime.audit` safe append-only event
  contracts, and `app.runtime.ports` protocols for adapters, repositories, outbox, clock and
  tenant-bound credential broker. Whether these are preparatory changes or separately reviewed
  sub-checkpoints is an open decision.
- **Security gates:** Audit is not authority; ports contain no implementation; event and envelope
  metadata are allowlisted and bounded; no credentials or provider payloads.
- **Verification:** Dependency guards, protocol-only tests, safe-event field tests, no I/O or
  infrastructure imports, and CP0-CP4 regression tests.
- **Completion:** CP5 cannot enter until both contract surfaces are approved and merged.
- **Excluded:** Orchestration logic, real clocks/brokers/repositories, adapters, persistence,
  outbox delivery, API, workers, and side effects.

### CP5 - Runtime Orchestration

- **Status:** Blocked.
- **Planned scope:** Pure orchestration after the prerequisite gates are resolved.
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

- **Status:** Planned.
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

### CP7 - Runtime Persistence

- **Status:** Planned.
- **Purpose:** Implement approved repository ports and a local transaction boundary for validated
  runtime facts.
- **Entry conditions:** CP5 ports stable; CP6 boundaries reviewed; storage design and migrations
  approved; tenant partitioning and retention decisions recorded where required.
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

### CP8 - Runtime Outbox

- **Status:** Planned.
- **Package placement:** Decision required. CP8 is a fixed program stage, but accepted ADRs do not
  approve an `app.runtime.outbox` package. An implementation ADR must decide whether CP8 extends
  `app.runtime.ports` and `app.runtime.persistence` or uses a separately named package. CP8 must
  not create `app.runtime.outbox` without that approval.
- **Purpose:** Add transactional outbox, effect-level idempotency, bounded retry, dead-letter facts,
  and reconciliation without claiming external atomicity.
- **Entry conditions:** CP7 transaction boundary merged; outbox port stable; idempotency and
  delivery state machine approved; adapter result references available.
- **Allowed outputs:** Outbox persistence and delivery contracts/implementation, bounded delivery
  attempts, dead-letter and reconciliation records, focused integration tests.
- **Allowed scope:** Atomically commit local state/audit/idempotency/outbox facts, then deliver
  governed work through the application/orchestration boundary and adapter ports without
  bypassing either boundary.
- **Security gates:** Revalidate time-sensitive authority before effects; no unrestricted payload,
  credential, silent repeat, unbounded retry, hidden compensation, or invented success.
- **Verification:** Duplicate and mismatched idempotency, crash/replay, ambiguous acknowledgement,
  retry eligibility, dead-letter, reconciliation, and tenant partition tests.
- **Completion:** External uncertainty remains explicit and reconcilable.
- **Handoff:** CP9 may expose authenticated transport over the runtime application boundary.
- **Excluded:** Exactly-once business-effect claims, direct API/worker repository access, policy in
  delivery, automatic destructive retry, and API or worker implementation.

### CP9 - Runtime API

- **Status:** Planned.
- **Purpose:** Expose authenticated, organization-scoped transport schemas over the approved
  runtime application/orchestration boundary.
- **Entry conditions:** CP8 merged; authentication/RBAC and transport threat model reviewed;
  stable application commands/results; audit and error mapping approved.
- **Allowed outputs:** Runtime API routes, request/response schemas, dependencies, authorization and
  transport tests.
- **Package placement:** Routes belong in the existing `app.api` layer. CP9 must not create
  `app.runtime.api` without a separately approved superseding ADR.
- **Allowed scope:** Authenticate, validate transport, invoke the application boundary, and return
  bounded safe references/status.
- **Security gates:** API owns no authority, state, action selection, repository mutation, adapter
  invocation, credential, provider payload, or cross-tenant fallback.
- **Verification:** Authentication/RBAC, tenant isolation, schema strictness, safe error mapping,
  replay/idempotency handling, rate/size controls, and no direct infrastructure bypass.
- **Completion:** API is a thin governed transport with all decisions downstream.
- **Handoff:** CP10 may consume persisted governed work through the same boundary.
- **Excluded:** Anonymous runtime access, direct adapter/repository calls, raw secrets or outputs,
  worker behavior, and policy decisions in routes.

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

ADR-065 through ADR-072 define the accepted CP0 architecture. ADR-073 through ADR-075 document
the implemented authority, planning, and state domains. CP4 and every new architecture domain
must cite these decisions and add an implementation ADR when package placement, dependency
direction, public contracts, or security behavior is not already sufficiently decided. A
contradiction requires a superseding ADR; roadmap prose alone cannot supersede an ADR.

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
| R15-01 | Decision required | CP5 needs Audit and Ports, but neither has a fixed program CP number. | Approve package placement and review unit before CP5. |
| R15-02 | Decision required | `AGENTS.md` summary ordering places registry/ports after orchestration, while ADR-065 makes orchestration depend on them. | Superseding ADR or operating-rule correction before CP5. |
| R15-03 | Planned | CP2 records opaque registry references before the registry implementation exists. | CP4 compatibility tests must preserve existing plan semantics. |
| R15-04 | Deferred | Physical partitioning and retention schedules are unspecified. | Decide before CP7 production persistence. |
| R15-05 | Deferred | Real adapter families, credential broker, destination redirect policy, and provider enablement are not selected. | Separate CP6 adapter approvals and threat reviews. |
| R15-06 | Deferred | Queue, lease, scheduling, and worker operational model are unspecified. | Decide before CP10 implementation. |
| R15-07 | Decision required | CP8 is a fixed program stage, but no accepted ADR approves a dedicated outbox package. | Decide whether CP8 extends Ports/Persistence or uses a separately approved package before implementation. |

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

## 15. CP4 entry checklist

- CP0-CP3 and PR #37 are merged on `main`.
- Working tree and checkpoint branch preconditions pass.
- ADR-068 and ADR-074 field-level compatibility is reviewed without changing CP2 contracts.
- Registry production code imports neither Planning nor State; compatibility evidence is
  structural and semantic at the test boundary.
- Actual plan-to-registry binding validation remains downstream of Registry, Planning, and State
  in an approved application/orchestration boundary.
- CP4 scope is registry metadata and immutable snapshots only.
- Action identity/version, schemas, capabilities, risk, side-effect, permit, destination,
  idempotency, retry/compensation eligibility, and adapter reference fields are decided.
- Unknown, disabled, substituted, and revision-mismatched actions fail closed.
- No callback, executable import, dynamic registration, credential, adapter call, I/O, or CP5+
  implementation is included.
- Focused dependency, security, immutability, canonical-ordering, and regression tests are planned.
- R15-01 and R15-02 are acknowledged as CP5 blockers, not silently solved inside CP4.

## 16. Governance inconsistencies

1. ADR-065 describes Planning as binding Registry contracts, while the fixed program sequence
   implemented Planning and State before CP4 Registry. CP4 therefore defines independent
   registry contracts whose action identity, version, revision, schema references, and selectors
   are structurally and semantically compatible with existing CP2 references. Registry production
   code imports neither Planning nor State and does not validate `ExecutionPlan` objects. Actual
   plan-to-registry binding validation belongs downstream in an approved application/orchestration
   boundary. Changing Planning to import Registry requires separately approved scope and regression
   review; CP2 and CP3 public contracts remain unchanged.
2. The `AGENTS.md` dependency summary shows Orchestration before Registry and Ports, while ADR-065
   and the normative orchestrator rules require orchestration to use registry-defined actions and
   ports. ADR-065 is the architecture source for dependency direction; implementation must not
   proceed through this conflict without a superseding ADR or operating-rule correction.
3. Audit and Ports are required dependencies for CP5 but have no dedicated number in the fixed
   CP0-CP10 program. They are therefore explicit CP5 prerequisite gates, not implicit CP5
   implementation. Their review/merge structure remains a decision.
4. CP8 is a fixed delivery stage, but ADR-065 and ADR-071 assign outbox protocols to Ports and
   storage implementation to Persistence without approving a dedicated outbox package. Package
   placement requires an implementation ADR before CP8 begins.

## 17. Open decisions

- Decide whether Runtime Audit and Runtime Ports are separate preparatory PRs, named CP5 gates, or
  governed sub-checkpoints without renumbering CP4-CP10.
- Decide and document the corrected canonical dependency ordering before CP5.
- Decide whether CP4 requires a new implementation ADR beyond ADR-068.
- Define the runtime application boundary public contract before orchestration or API work.
- Select credential-broker, destination policy, and real-adapter enablement rules before CP6.
- Select persistence engine mapping, transaction ownership, partitioning, and retention before
  CP7 migrations.
- Define outbox delivery, dead-letter, and reconciliation state contracts before CP8.
- Decide whether CP8 extends `app.runtime.ports` and `app.runtime.persistence` or receives a
  separately approved package; do not create `app.runtime.outbox` implicitly.
- Confirm CP9 routes remain in `app.api`; creating `app.runtime.api` requires a superseding ADR.
- Define API authentication/RBAC mapping before CP9.
- Decide CP10 worker package placement, queue, lease, identity, and scheduling model; workers
  remain outside the `app.runtime` domain unless a superseding ADR approves otherwise.
