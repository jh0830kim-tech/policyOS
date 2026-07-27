# ADR-033: Assignment Execution Dispatch Boundary

## Status

Accepted for Sprint 10 Checkpoint 3.

## Context

ADR-030 translates Sprint 9 coordination into immutable assignment execution requests, bindings,
and Sprint 8 execution plans. ADR-031 adds the assignment-level PREPARED, CLAIMED, and RUNNING
lifecycle with an immutable claim lease. CP3 needs to authorize the handoff of one claimed
assignment to an execution boundary without choosing a provider or model and without marking work
RUNNING before that boundary accepts it.

Sprint 8 already defines a provider-neutral `DispatchRequest` containing plan, execution, session,
step, capability, safe input, tenant, actor, classification, lineage, attempt, deadline, timeout, and
issue time. That contract is reused. Sprint 8's `create_dispatch_request` operation is not reused
because it also changes the Sprint 8 step state to RUNNING before an external acceptance decision.
CP3 instead builds the same immutable contract after orchestration validation and delegates only the
acceptance decision through a small synchronous `ExecutionDispatchBoundary` protocol.

## Decision

Add `dispatch.py` and `dispatch_errors.py` to `app.orchestration`. The orchestration layer continues
to depend on CP1, CP2, and Sprint 8; no reverse dependency is introduced.

An immutable `AssignmentExecutionDispatchRequest` carries only caller-supplied dispatch, session,
execution, plan, assignment-request, binding, dispatcher, and timestamp identities. A trusted
context carries tenant, actor, classification, correlation/causation lineage, dispatcher identity,
and a canonical tuple of dependency step IDs already known to have succeeded. It has no arbitrary
metadata, prompt, source body, credential, provider, or model field.

Dispatch requires an existing CP2 CLAIMED record. CP3 never claims a PREPARED record. It validates,
in deterministic order, tenant and classification; dispatcher, execution, plan, request, binding,
assignment, task, step, actor, and runtime-context identities; attempt one; claim lease ownership;
assignment deadline and lease activity at the explicit dispatch timestamp; gate protection; plan
membership; step scope; and dependency satisfaction. Satisfied dependency IDs must belong to the
plan and every bound step dependency must be present.

Human-review gates, non-executable orchestration gates, and Secretary impersonation are rejected
before the boundary is called. No fake human, Secretary specialist, or provider work is created.

The boundary receives the existing Sprint 8 `DispatchRequest` and returns a normalized immutable
receipt containing only dispatch, execution, plan, and step identities, acceptance/rejection,
acceptance time, and bounded safe rejection information. Provider SDK objects, provider responses,
outputs, tokens, costs, exceptions, and arbitrary metadata cannot cross this boundary.

An accepted receipt must match the request identities. Only then does CP3 call CP2
`start_assignment_execution`, which returns a new RUNNING record and enforces the exact lease owner,
lease activity, deadline, and timestamp ordering. CP3 never directly assigns runtime status. A
rejected receipt returns a normalized REJECTED dispatch result containing the original CLAIMED
record. Rejection means execution did not start and therefore does not fabricate a FAILED record.
Boundary exceptions become one stable safe typed error without exposing the raw exception.

All contracts are frozen and extra-forbidden. IDs and timestamps are caller supplied. There is no
clock, UUID generation, randomness, mutation, global state, persistence, queue, worker, background
execution, provider resolution, provider/model selection, retry, fallback, output collection,
work-product creation, Secretary integration, approval, publication, metrics, or telemetry.

## Consequences and limitations

CP3 creates an auditable claim-before-dispatch authorization boundary and preserves CP1/CP2 and
Sprint 8 semantics. The boundary is an in-process protocol, not a queue or delivery guarantee.
Dependency success is supplied as trusted typed identity state; durable runtime coordination remains
outside CP3. Execution completion and output handling remain future checkpoints.

Provider/model registry and manual selection remain deferred to Sprint 11, independent
cross-validation to Sprint 12, and evaluation/observability to Sprint 13. ADR-032 remains reserved as
the recommended number for the separate future multi-model extension proposal; CP3 implements none
of that proposal.
