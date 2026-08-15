# ADR-107: CP9 Runtime Production Dependency-Bundle Factory Graph and Transport-Neutral Observer Ownership

- **Status:** Accepted
- **Date:** 2026-08-14
- **Depends on:** ADR-102, ADR-105, ADR-106, and migration `20260808_0024`

## Context

ADR-106 requires one immutable production dependency bundle and fresh request-scoped Runtime
capabilities, but it does not fix the exact factory graph, the boundary between the authoritative
preparation upstream and the domain-operation capability, or the disposal and transport-neutral
disconnect contracts. Those meanings must be closed before public Protocols or production routes
can be added.

## Decision

### Exact upstream input and output

The request-scoped preparation upstream receives verified access-token claims, one validated
organization selector, and exactly one strict operation-specific transport input. It exposes three
closed methods for submission, query, and reconciliation. Each call returns exactly the matching
existing `RuntimeApiSubmissionPreparationContext`, `RuntimeApiInvocationQueryPreparationContext`,
or `RuntimeApiReconciliationPreparationContext`.

The upstream is the sole owner of that complete context. It may obtain one approved
command/orchestration preparation output from the same request call stack, but it cannot select a
current or latest record, retry for an alternative, generate an identity, revision, digest,
reference, classification, lineage, timestamp, policy fact, callback, or result, or accept them
from HTTP input. Missing, incomplete, stale, ambiguous, substituted, or cross-scope output fails
closed before preparation-source inspection.

### Callback ownership

The injected request-scoped domain-operation capability is the sole callback factory. The upstream
asks it exactly once for the operation-bound submission or reconciliation callback and carries the
returned callback unchanged in the matching preparation context. Query preparation asks for and
carries no callback. Provider, producer, issuer, source, route, facade, and persistence never
create, select, name, replace, serialize, or invoke a callback while preparing a candidate.

### Immutable bundle and factory graph

The application factory receives one frozen, slots-based, keyword-only production dependency
bundle. The bundle contains exactly these request-scoped factories:

- preparation upstream factory;
- domain-operation capability factory;
- trusted-clock factory;
- independent rate-admission capability factory;
- deadline-budget capability factory;
- disconnect-observation capability factory; and
- request-capability-scope factory.

The request-capability-scope factory is the single lifetime coordinator. It captures the six
capability factories and, for one request only, constructs fresh domain-operation, clock, rate,
deadline, disconnect, and upstream objects. It yields one immutable request dependency set. The
application layer then constructs the existing provider, producer, issuer, source, and prepared
application entry in that exact order. Those deterministic application components are not
replaceable bundle fields and cannot become service locators.

The construction graph is:

```text
application factory
-> immutable production dependency bundle
-> request-capability-scope factory
-> fresh domain-operation, clock, rate, deadline, disconnect capabilities
-> fresh authoritative preparation upstream
-> preparation-context provider
-> preparation producer
-> preparation issuer
-> request-local preparation source
-> prepared application entry
-> thin Runtime route
```

### Request lifetime and disposal

The request-capability scope is an asynchronous context manager. Entering it once returns the one
immutable request dependency set. Exiting it disposes every created request object exactly once in
reverse construction order on success, rejection, exception, or cancellation. Re-entry,
cross-request use, use after exit, duplicate exit, partial construction, or an object escaping the
scope fails closed. No separate public `close`, mutable reset, retry, or reusable pool contract is
permitted. Disposal is cleanup only and creates no authority or Runtime state transition.

### Transport-neutral disconnect signal

The public disconnect signal exposes exactly one asynchronous operation:

```text
is_disconnected() -> bool
```

`app.api` owns the adapter that binds this signal to the current FastAPI `Request`. FastAPI types
never cross into application or Runtime public contracts. The signal returns only a strict boolean;
it cannot create the observation reference or time. The disconnect capability binds that boolean
to the request already carried by the preparation context and its trusted preflight clock. It
cannot infer cancellation, retry, compensation, failure, or success.

### Independent rate capability factory

The public rate-admission factory is SQLAlchemy-free and creates one request-scoped
`RuntimeApiRateAdmissionCapability` without exposing an engine, session, sessionmaker, or
transaction. Its concrete persistence factory privately captures the approved session factory.
Each capability owns one fresh session and root transaction and completes its commit or rollback
and close before the facade transaction begins. It is never the facade session.

### Missing and partial composition

The application factory may install either one complete validated production bundle or an explicit
closed unavailable Runtime composition. A missing bundle therefore permits the process and
non-Runtime endpoints to start, but every Runtime endpoint returns one bounded generic `503`
before preparation inspection. This unavailable composition is not a fake and carries no facts or
capabilities.

A supplied but incomplete bundle, a non-conforming factory, duplicate field, mutable dependency,
or partially constructed request scope fails application construction. It cannot be downgraded to
the unavailable composition. HTTP mapping remains owned only by `app.api` and discloses no package,
policy, provider, database, session, callback, bearer, body, or cross-scope detail.

### Preserved boundaries

The facade's three public methods keep their existing five parameters. Query preparation and
execution remain read-only: no callback, local write set, receipt, stage, counter mutation, or
facade-owned mutation is permitted. Provider, producer, issuer, source, and prepared entry retain
their existing authority boundaries and one-shot semantics.

Preparation and capability lifecycle state remains request-local. No durable preparation table,
cache, callback name, backfill, normalization, deduplication, schema change, or migration
`20260808_0025` is required or permitted. Migration `20260808_0024` remains the single head.

## Follow-up gates

1. Add only the closed dependency-bundle, upstream, factory, request-scope, request-dependency-set,
   and disconnect-signal public contracts.
2. Implement the concrete producer, source, operational capabilities, application factory,
   verified-claims dependency, composition, and thin Runtime routes in a separate gate.
3. Run PostgreSQL 16 and HTTP acceptance before CP9 closeout.
4. Keep CP10 separately approved and blocked until CP9 closeout.

## Validation matrix

- Governance: exact factory fields and graph, upstream/context ownership, callback separation,
  async context-manager disposal, bounded unavailable composition, and migration prohibition.
- Public contracts: frozen immutable bundle and dependency set; exact Protocol method signatures;
  one enter and one exit; cross-request, re-entry, duplicate-exit, and use-after-exit rejection.
- Dependency direction: no FastAPI, SQLAlchemy, sessionmaker, engine, mutable registry, environment
  selection, service locator, or default fake in public Runtime contracts.
- Preparation: submission and reconciliation request one callback; query requests zero callbacks;
  provider, producer, issuer, and source preserve exact values without inference.
- Disconnect: strict asynchronous boolean signal, framework adapter confinement, and exact
  observation-reference/time binding.
- Rate: factory hides SQLAlchemy and every capability owns a separate request-local transaction.
- Facade/query: three five-parameter signatures remain unchanged and query mutation stays zero.
- HTTP acceptance: missing bundle returns generic `503` before inspection; invalid supplied bundle
  fails construction; successful requests dispose once after one prepared entry invocation.

## Alternatives rejected

- Let the provider or route create preparation facts: duplicates authoritative upstream ownership.
- Put FastAPI `Request` in application contracts: reverses the dependency boundary.
- Expose an `AsyncSession` or sessionmaker through the rate factory: leaks persistence ownership.
- Use synchronous disposal or optional `close`: cannot prove exceptional-path lifetime completion.
- Store factories in mutable `app.state` or a service locator: permits runtime substitution.
- Persist preparation or callback lifecycle: executable request-local values have no durable owner.

## Consequences

The production factory graph and request lifetime are now deterministic and independently
reviewable. This governance gate changes no production/public Python, route, model, repository,
schema, or migration. CP9 remains Planned / Blocked until its separate public-contract,
production, acceptance, and closeout gates merge. CP10 remains Planned.

## Factory-signature and request-scope lifecycle correction

This section supersedes the earlier statement that the bundle exposes the six leaf factories and
the request-scope factory as seven peer fields. Exposing both is redundant and permits composition
to bypass the lifecycle coordinator.

### Exact public bundle and private leaf factories

`RuntimeApiProductionDependencyBundle` is one frozen, slots-based, keyword-only dataclass with
exactly one field:

```text
request_capability_scope_factory: RuntimeApiRequestCapabilityScopeFactory
```

The bundle has no optional fields, mapping, metadata, unavailable discriminator, prepared facts,
or direct leaf-factory fields. `RuntimeApiRequestCapabilityScopeFactory` is configured once at
process assembly and privately, immutably captures exactly these six leaf factories:

- `RuntimeApiDomainOperationCapabilityFactory`
- `RuntimeClockFactory`
- `RuntimeApiRateAdmissionCapabilityFactory`
- `RuntimeApiDeadlineBudgetCapabilityFactory`
- `RuntimeApiDisconnectObservationCapabilityFactory`
- `RuntimeApiPreparationContextUpstreamFactory`

The leaf factories remain additive public structural Protocols so composition can be type-checked
and tested, but they are not separately reachable through the bundle. The scope factory is the
only bundle entry point and the only owner allowed to invoke them.

### Exact leaf-factory signatures and construction order

The signatures are closed as follows:

```text
RuntimeApiDomainOperationCapabilityFactory.__call__()
    -> RuntimeApiDomainOperationCapability
RuntimeClockFactory.__call__()
    -> RuntimeClockPort
RuntimeApiRateAdmissionCapabilityFactory.__call__()
    -> RuntimeApiRateAdmissionCapability
RuntimeApiDeadlineBudgetCapabilityFactory.__call__()
    -> RuntimeApiDeadlineBudgetCapability
RuntimeApiDisconnectObservationCapabilityFactory.__call__(
    signal: RuntimeApiDisconnectSignal,
) -> RuntimeApiDisconnectObservationCapability
RuntimeApiPreparationContextUpstreamFactory.__call__(
    domain_operation: RuntimeApiDomainOperationCapability,
    clock: RuntimeClockPort,
) -> RuntimeApiPreparationContextUpstream
```

The scope factory invokes them exactly once and only in this order: domain operation, clock, rate
admission, deadline budget, disconnect observation, and preparation upstream. The upstream is
created last from the exact domain-operation and clock objects already present in the scope. It
cannot construct or replace either dependency.

### Exact upstream Protocol

`RuntimeApiPreparationContextUpstream` exposes exactly three asynchronous methods. Their inputs
and outputs are:

```text
prepare_submission(
    claims: VerifiedAccessTokenClaims,
    organization: RuntimeApiOrganizationSelector,
    request: RuntimeApiSubmissionInput,
) -> RuntimeApiSubmissionPreparationContext
prepare_query(
    claims: VerifiedAccessTokenClaims,
    organization: RuntimeApiOrganizationSelector,
    request: RuntimeApiInvocationQueryInput,
) -> RuntimeApiInvocationQueryPreparationContext
prepare_reconciliation(
    claims: VerifiedAccessTokenClaims,
    organization: RuntimeApiOrganizationSelector,
    request: RuntimeApiReconciliationInput,
) -> RuntimeApiReconciliationPreparationContext
```

Submission and reconciliation obtain exactly one callback from the injected domain-operation
capability. Query obtains zero callbacks and carries no mutation field. All three use the injected
clock only to exact-read the caller-approved clock reference already present in the authoritative
preparation output; the clock cannot select a reference or generate hidden time.

### Exact disconnect and request-scope signatures

`RuntimeApiDisconnectSignal` exposes only:

```text
async is_disconnected() -> bool
```

The signal is the sole argument to
`RuntimeApiRequestCapabilityScopeFactory.__call__(signal)`. The scope factory passes that same
object identity exactly once to `RuntimeApiDisconnectObservationCapabilityFactory`; no other leaf
factory receives it. The concrete observer must reject a non-`bool` result. The signal supplies no
reference, timestamp, body, bearer, cancellation, retry, compensation, or Runtime state fact.

The scope factory returns one `RuntimeApiRequestCapabilityScope`. That Protocol is an asynchronous
context manager with exact methods:

```text
async __aenter__() -> RuntimeApiRequestDependencies
async __aexit__(
    exc_type: type[BaseException] | None,
    exc: BaseException | None,
    traceback: TracebackType | None,
) -> Literal[False]
```

Returning `False` is mandatory: cleanup never suppresses an exception. Enter may succeed exactly
once and exit may complete exactly once. Re-entry, duplicate exit, use before enter, use after
exit, cross-request reuse, or partial construction fails closed. If construction fails, every
already-created object is disposed exactly once in reverse order and no dependency set is yielded.

`RuntimeApiRequestDependencies` is one frozen, slots-based, keyword-only dataclass with exactly
these fields in construction order:

```text
domain_operation: RuntimeApiDomainOperationCapability
clock: RuntimeClockPort
rate_admission: RuntimeApiRateAdmissionCapability
deadline_budget: RuntimeApiDeadlineBudgetCapability
disconnect_observation: RuntimeApiDisconnectObservationCapability
preparation_upstream: RuntimeApiPreparationContextUpstream
```

It contains no request, claims, organization selector, prepared facts, database object, mutable
mapping, close callback, or transport type. The dependency set borrows the scope lifetime and
cannot escape or be reused.

### Unavailable composition ownership

Unavailable composition is production-only and is not a Runtime public contract, bundle variant,
or sentinel field. `app.api` owns one closed unavailable prepared-entry implementation used only
when no bundle was supplied at application construction. It returns generic bounded `503` before
creating a request scope or inspecting a candidate. Supplying a bundle that is incomplete,
mutable, duplicated, or structurally invalid fails application construction and cannot select the
unavailable entry.

### Corrected follow-up scope

The next public-contract gate may add the bundle and dependency-set dataclasses plus the upstream,
disconnect-signal, six leaf-factory, request-scope-factory, and request-scope Protocols only in
`app.services.runtime_api_protocols`. It may update its focused structural tests and bounded
architecture/document status. It cannot implement a factory, lifecycle, FastAPI adapter, route,
SQLAlchemy session owner, unavailable entry, or migration `20260808_0025`.

## ADR-108 managed-resource correction

ADR-108 supersedes only the raw leaf-factory return values. Each of the six factories returns one
fresh single-use asynchronous managed resource, and entry yields the exact capability named by the
existing signature. Construction order and factory inputs are unchanged. The request scope alone
enters resources and exits every acquired resource exactly once in reverse acquisition order.

Partial construction yields no dependency set. Cleanup continues after an exit failure and never
suppresses or replaces an active primary exception. The frozen dependency set is a borrowed view;
concrete guarded capability views reject calls before entry, during exit, after exit, or from a
different request scope. Capability Protocols expose no public close, reset, retry, or reuse API.
Lifecycle state remains request-local, so persistence and migration `20260808_0025` are prohibited.

## ADR-110 required-audience correction

`RuntimeApiProductionDependencyBundle` continues to expose exactly one field,
`request_capability_scope_factory`. Required-audience configuration is not a seventh capability,
prepared fact, request dependency, or bundle field. The application factory privately captures the
validated `runtime_api_required_audience` scalar beside the bundle and supplies it when constructing
the facade. Allowlist ordering, token claims, and request-local objects cannot select it. No public
factory signature, request-scope lifecycle, facade signature, persistence owner, or migration
`20260808_0025` changes.
