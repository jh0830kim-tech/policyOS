# ADR-108: CP9 Runtime Managed Request-Capability Resource Lifetime

## Status

Accepted for the CP9 managed request-capability lifetime governance gate. This decision changes no
production Python, public Protocol, route, model, repository, schema, migration, or PostgreSQL
data. CP9 remains Planned / Blocked and CP10 remains Planned.

## Context

ADR-107 makes one asynchronous request-capability scope the sole lifecycle coordinator and
requires every partially or completely constructed request object to be disposed exactly once in
reverse order. The merged leaf factories, however, return raw capabilities. A raw capability has
no approved asynchronous acquisition or release boundary, so the scope cannot prove cleanup after
partial construction, prevent use after exit, or preserve exception semantics without inventing a
private `close`, optional duck typing, or reference-drop convention.

Disposal is request-local resource management. It is not approval, authorization, permit,
admission, execution, Runtime state, result, audit evidence, retry, cancellation, compensation, or
persistence authority.

## Decision

### Managed leaf resource

Each of the six leaf factories returns one fresh single-use asynchronous managed resource rather
than a raw capability. Its acquired value is exactly the capability previously returned by that
factory:

1. domain-operation capability;
2. trusted clock;
3. independent rate-admission capability;
4. deadline-budget capability;
5. disconnect-observation capability; and
6. preparation-context upstream.

The managed resource exposes only asynchronous context-manager entry and exit. Entry yields the
typed capability. Exit returns `False`, performs cleanup, and never suppresses the active
exception. Capability Protocols do not gain public `close`, `aclose`, reset, retry, pool, or reuse
methods. The scope coordinator is the only caller permitted to enter or exit a leaf resource.

The preparation-upstream factory still receives the exact acquired domain-operation and clock
object identities. The disconnect factory still receives only the exact current-request
transport-neutral disconnect signal. Managed wrapping cannot substitute, recreate, or broaden a
capability.

The additive public contract is named `RuntimeApiManagedRequestCapability`. It is a structural,
runtime-checkable Protocol generic over one covariant `CapabilityT_co` and exposes exactly:

```text
async __aenter__() -> CapabilityT_co
async __aexit__(
    exc_type: type[BaseException] | None,
    exc: BaseException | None,
    traceback: TracebackType | None,
) -> Literal[False]
```

The six factory return annotations become, respectively:

```text
RuntimeApiManagedRequestCapability[RuntimeApiDomainOperationCapability]
RuntimeApiManagedRequestCapability[RuntimeClockPort]
RuntimeApiManagedRequestCapability[RuntimeApiRateAdmissionCapability]
RuntimeApiManagedRequestCapability[RuntimeApiDeadlineBudgetCapability]
RuntimeApiManagedRequestCapability[RuntimeApiDisconnectObservationCapability]
RuntimeApiManagedRequestCapability[RuntimeApiPreparationContextUpstream]
```

Factory inputs, invocation order, capability methods, the dependency-set fields, the scope-factory
signature, and the outer request-scope signature remain unchanged.

### Construction and partial failure

The request scope obtains and enters resources exactly once in ADR-107 construction order. A
resource is considered acquired only after its entry completes successfully. If factory creation
or entry fails at any position, the scope yields no dependency set and exits every previously
acquired resource exactly once in reverse acquisition order.

A failing exit does not stop later reverse-order cleanup. The scope retains the first cleanup
failure as bounded lifecycle evidence while attempting all remaining exits. If an operation,
rejection, or construction exception is already active, cleanup never replaces or suppresses that
primary exception. If no primary exception exists, the first cleanup failure propagates only after
all cleanup attempts finish. Cleanup errors disclose no capability, package, policy, request,
tenant, organization, classification, lineage, clock, session, transaction, bearer, or body fact.

### Closed state machine

The scope and every managed resource follow the closed states `NEW`, `ENTERED`, `EXITING`, and
`EXITED`. Only `NEW -> ENTERED -> EXITING -> EXITED` is valid. Failed entry transitions directly
to terminal `EXITED` without yielding a capability. Re-entry, duplicate exit, use before enter,
use while exiting, use after exit, cross-request reuse, and cross-scope substitution fail closed.

`RuntimeApiRequestDependencies` is a frozen borrowed view over the six acquired capabilities. A
concrete scope must yield scope-local guarded capability views whose methods validate the active
scope identity before delegating. Retaining the dataclass or any field after exit therefore cannot
invoke the underlying capability. The dependency set contains no lifecycle token, close callback,
mutable state, request object, session, transaction, or metadata field.

### Rate transaction separation

The rate-admission managed resource owns only request-scope capability lifetime. Each `admit` call
continues to create, commit or roll back, and close its own independent PostgreSQL session and root
transaction before returning. Request-scope exit neither owns nor reuses an admit transaction and
cannot begin, commit, roll back, close, or replace the facade session. Facade transaction ownership
and five-parameter public methods remain unchanged.

### Persistence and migration

Managed-resource state is in-memory, request-local, and non-authoritative. It must not be persisted
or reconstructed. No preparation table, lifecycle row, backfill, normalization, deduplication, or
migration `20260808_0025` is permitted.

## Follow-up gates

1. A public-contract correction may add `RuntimeApiManagedRequestCapability`, its covariant type
   parameter, and only the six governed leaf-factory return annotations. It may add structural
   tests and bounded architecture/document status changes.
2. A production gate may implement the guarded resources, scope coordinator, upstream,
   capabilities, composition, unavailable entry, and thin routes.
3. PostgreSQL 16 and HTTP acceptance must prove rate-session separation, cleanup ordering, failure
   non-disclosure, facade transaction ownership, and zero rollback residue before CP9 closeout.
4. CP10 remains blocked until CP9 production, acceptance, and closeout merge.

## Validation requirements

- six resources are created and entered exactly once in the fixed order;
- complete and partial construction exit exactly once in reverse acquisition order;
- success, rejection, exception, and cancellation all complete cleanup;
- re-entry, duplicate exit, use-before-enter, use-after-exit, and cross-request reuse fail closed;
- cleanup failure attempts all remaining exits and preserves the primary exception;
- escaped dependency fields cannot invoke an underlying capability after scope exit;
- rate admission owns a distinct per-call session and request-scope exit touches no facade session;
- query remains read-only and facade public signatures remain five parameters; and
- Alembic retains the single head `20260808_0024` with no migration `20260808_0025`.

## Alternatives rejected

- Add optional `close` or `aclose` to capabilities: optional cleanup cannot prove completion.
- Discover a private close method by duck typing: hidden lifecycle meaning is not a contract.
- Drop references on exit: garbage collection is not deterministic disposal or use-after-exit
  enforcement.
- Expose leaf factories directly through the bundle: bypasses the sole lifecycle coordinator.
- Persist lifecycle tokens: request-local executable resources have no durable authority owner.

## Consequences

The resource owner, acquisition order, reverse cleanup, exception precedence, escape prevention,
and rate-session separation are deterministic before production implementation. The public
contract must be amended before concrete composition can claim ADR-107 lifecycle compliance.
There is no schema or migration `20260808_0025`.
