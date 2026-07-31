# ADR-052: Deterministic Offline Execution State Machine

## Status

Accepted for Sprint 13 CP2-2.

## Context

ADR-050 established immutable evaluation-domain and reproducibility records. ADR-051
added deterministic planning. PolicyOS next needs a representation of an evaluation
plan's lifecycle without crossing into execution, evidence, or result semantics.

CP2-2 is a lifecycle state machine. It is not an evaluation executor. IN_PROGRESS
is governance metadata recording acceptance at a future executor boundary, not proof
that work occurred. COMPLETED is a lifecycle status, not proof of evidence,
correctness, or quality.

## Decision

PolicyOS will represent one plan-level lifecycle with strict, frozen contracts:
EvaluationExecutionContext, EvaluationExecutionAuthorizationBinding,
EvaluationExecutionTransition, and EvaluationExecutionRecord. Pure validation and
application functions accept the bound plan and an existing authorization decision
directly. Task-level state is omitted.

## Canonical state graph

The success path is PLANNED -> VALIDATED -> READY -> IN_PROGRESS -> COMPLETED.
Every non-terminal state may instead transition to FAILED or CANCELLED.
Success-path steps cannot be skipped, reversed, or repeated.

## Terminal-state rules

COMPLETED, FAILED, and CANCELLED are terminal and cannot be reopened. A state cannot
transition to itself. Failed and cancelled transitions require opaque outcome
metadata; other transitions cannot carry failure or cancellation references.

## Authorization verification

Authorization is referenced and verified, never created. An existing
EvaluationDataAccessDecision must be ALLOW and match the caller-supplied decision and
request identities. A separate narrow immutable binding must exactly match actor,
optional agent, tenant, organization, policy identity and revisions, purpose, plan
resource, exact state edge, offline tier, lineage, and OFFLINE_STATE_TRANSITION
capability. This records scope without embedding or broadening the authorization
object. Missing or ambiguous scope fails closed.

## Exact plan binding

The execution context binds the exact plan and optional version, run request,
definition, target, tenant, organization, policy, offline tier, lineage, dataset,
manifest, split, evaluator, registry snapshot and revision, planning fingerprint,
and compatible audit authorization revision. The state machine neither replans nor
changes plan tasks.

## Immutable transition history

The tuple of caller-supplied transitions is the authoritative lifecycle history.
Sequence numbers begin at one and are contiguous; transition identities are unique;
execution and plan identities remain exact; from_state follows the preceding result;
and timestamps are non-decreasing. Invalid order is rejected rather than silently
sorted, repaired, or deduplicated.

## Deterministic transition application

Application validates the plan, record, next sequence, graph edge, timestamp, and
authorization, then returns a new record with exactly one appended transition. The
prior record remains unchanged. current_state and updated_at derive only from the
supplied transition.

## Offline-only enforcement

Both context and authorization binding require OFFLINE_EVALUATION. The only accepted
capability is offline state-transition governance. No model, provider, MCP,
connector, or tool invocation occurs. No persistence or event emission occurs.

## Caller-supplied identifiers and timestamps

All execution, transition, authorization-binding, and reference identifiers are
caller supplied. All timestamps and sequence numbers are caller supplied. CP2-2
contains no clock, UUID generation, hash generation, randomness, automatic
transition creation, or automatic sequence allocation.

## Fail-closed validation

Strict contracts reject unknown fields and coercion. Any binding, authorization,
sequence, timestamp, metadata, or graph mismatch raises a specific evaluation-domain
error. Terminal states cannot be reopened.

## Security considerations

The execution record contains opaque identifiers and references, not credentials,
tokens, raw provider payloads, evidence, unrestricted authorization objects, or
exception stack traces. Exact tenant, organization, actor, agent, policy, lineage,
tier, resource, action, purpose, and capability matching prevents scope widening.

## Reproducibility and lineage

The lifecycle remains bound to the exact immutable plan, plan version, planning
fingerprint, dataset provenance, evaluator, registry snapshot, policy and
authorization revisions, and delegation lineage. CP2-2 calculates no fingerprint,
creates no lineage, and resolves no external reference.

## Consequences

Callers must construct explicit transition intent and retain the matching
authorization decisions when validating history. The model is easy to inspect and
replay deterministically, but deliberately provides no orchestration, durability,
or proof that evaluation work occurred.

## Deferred scope

Evidence ownership belongs to a later checkpoint. Metrics and scoring also belong
to a later checkpoint. Execution, dataset loading, retrieval, evidence collection
and validation, result interpretation, persistence, APIs, queues, workers,
scheduling, retries, telemetry, tracing, and task-level runtime state are deferred.

## Alternatives considered

- Mutable execution object: rejected because state could diverge from history.
- Database-backed state machine: rejected because persistence is outside CP2-2.
- Event-emitting state machine: rejected because event delivery introduces a runtime
  side effect and does not belong in pure domain governance.
- Automatic timestamp generation: rejected because a hidden clock breaks
  deterministic caller-controlled records.
- Automatic transition or sequence generation: rejected because it hides intent and
  can silently repair invalid input.
- Permissive skipped transitions: rejected because eligibility and responsibility
  governance must remain explicit.
- Combining evidence collection with state management: rejected because lifecycle
  status is not evidence, quality, scoring, or proof of execution.
