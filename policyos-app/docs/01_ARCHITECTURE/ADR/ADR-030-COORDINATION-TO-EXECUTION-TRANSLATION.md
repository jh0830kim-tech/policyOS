# ADR-030: Coordination-to-Execution Translation

## Status

Accepted for Sprint 10 Checkpoint 1.

## Context

ADR-019 through ADR-023 establish the Sprint 8 capability planner, immutable execution plan,
deterministic scheduler, provider-resolution boundary, provider executor, and result synthesis.
ADR-024 through ADR-029 establish the Sprint 9 intelligence contracts, specialist authority,
delegation, and Secretary coordination preparation. A prepared `CoordinationPlan` needs a governed,
reproducible bridge to Sprint 8 without making translation itself an execution mechanism.

## Decision

Add `app.orchestration`, depending on `app.intelligence` and `app.execution`; neither lower layer
depends on orchestration. The package owns frozen translation request, trusted context, fail-closed
policy, assignment execution intent, binding, gate, validation, result, and safe typed-error
contracts. The existing Sprint 8 `ExecutionStep`, `ExecutionPlan`, retry-disabled default, graph
validator, and deterministic topological ordering are reused directly.

The request references an already-prepared READY or PARTIAL plan and carries caller-supplied
translation identity, actor, tenant, correlation/causation lineage, classification, timestamps,
deadline, policy version, and schema version. Context repeats trusted identity and supplies the
translation timestamp, cancellation flag, expected versions, and bounded attempt. There is no
clock, generated UUID, random value, callback, configuration map, runtime object, or persistence
handle.

Each specialist coordination task maps to at most one execution step and exactly one prepared
assignment. Matching uses the delegation's role, exact capability tuple, exact expected-output
tuple, required flag, tenant, and classification. Assignment identity, agent-definition identity,
input-reference identities, outputs, deadline, and lineage remain in `AssignmentExecutionRequest`
and `AssignmentExecutionBinding`, avoiding intelligence-specific changes to Sprint 8 models.
Approved capabilities are copied exactly; translation cannot expand authority or let Secretary
impersonate a specialist.

Required specialist tasks must translate. An unassigned optional task is permitted only for a
PARTIAL plan under explicit policy and remains listed in the result. There is no task merge, split,
dynamic generation, implicit fallback, or semantic replanning.

Coordination dependencies are preserved. Dependencies that cross a non-executable boundary resolve
only to their existing executable ancestors; no synthetic work is introduced. The original DAG is
validated, step dependencies are bounded, and Sprint 8 constructs and topologically orders the final
plan deterministically by sequence and ID.

Secretary integration and quality-review tasks remain non-provider orchestration boundaries for
future checkpoints. Human review remains a blocking, non-executable gate. Gate contracts preserve
task identity, executable and gate dependencies, tenant, classification, safe reason, and deadline.
They contain no fake human agent, reviewer identity, approval mutation, or completion claim.

Tenant identity must match throughout. Classification is preserved exactly; references,
assignments, requests, bindings, gates, steps, and the execution plan cannot cross tenants or
downgrade classification. Deadlines cannot exceed the coordination deadline. Caller-supplied
`translated_at >= deadline` yields EXPIRED, and pre-translation cancellation yields CANCELLED; both
contain no execution plan.

READY and PARTIAL mean only that deterministic translation succeeded. They do not mean provider
resolution, dispatch, running, completion, result or evidence collection, work-product or artifact
creation, Secretary synthesis, human approval, or publication. Expected business failures return
bounded, canonically ordered safe issues; typed exceptions are reserved for contract and invariant
failures and never include objectives, prompts, provider bodies, credentials, endpoints, or raw
exceptions.

All models are frozen and extra-forbidden, all nested collections are tuples, and inputs are never
mutated. IDs derive canonically from caller-supplied translation/task identities. Serialization has
stable enums, ordering, timestamps, and no sets, bytes, arbitrary representations, callables,
providers, or agent instances. Policy bounds steps, dependencies, bindings, inputs, outputs,
capabilities, gates, issues, and attempts. Inputs are rejected rather than truncated; when issue
capacity is exceeded, deterministic issue order is retained with a final
`validation_issue_limit_reached` marker.

Task and assignment indices make matching and translation O(T + A); graph validation and ordering
are O(S + D), with bounded sorting. Translation performs zero provider calls, agent executions,
runtime dispatches, scheduler invocations, retries, fallbacks, or state mutations.

## Consequences and deferred work

Sprint 10 CP1 produces execution-ready metadata while preserving every execution and intelligence
authority boundary defined by ADR-019 through ADR-029. Runtime availability, capability-catalog
resolution, provider/model selection, provider binding, dispatch, result collection, Secretary
integration execution, approval workflow mutation, persistence, and publication remain deferred to
Sprint 10 CP2 and later checkpoints.
