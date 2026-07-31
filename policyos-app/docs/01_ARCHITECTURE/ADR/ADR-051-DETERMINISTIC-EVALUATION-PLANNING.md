# ADR-051: Deterministic Evaluation Planning

- Status: Accepted
- Date: 2026-08-01

## Context

Sprint 13 CP1 established immutable evaluation definitions, references, run
requests, authorization metadata, lineage, reproducibility, and integrity records.
PolicyOS now needs a provider-neutral way to translate an already-authorized run
request into explicit execution intent without executing evaluation work.

Planning must be reproducible and fail closed across tenant, organization, policy,
dataset provenance, registry snapshot, evaluator independence, authorization, and
delegation lineage boundaries. It must not infer missing permission or silently
repair malformed task order.

## Decision

PolicyOS introduces `app.evaluation.planning` with strict immutable contracts for:

- `EvaluationStage` and `EvaluationTaskType`, both closed canonical enums;
- `EvaluationTask`, containing metadata-only task intent and dependencies;
- `EvaluationPlan`, containing exact immutable bindings and canonical tasks;
- `EvaluationPlanningAuthorizationBinding`, which references an existing access
  decision without creating or broadening authorization;
- `EvaluationPlanningRequest`, which holds typed CP1 contracts; and
- `build_evaluation_plan`, a stateless pure planner.

Plans may additionally retain caller-supplied `EvaluationPlanVersion`,
`PlanningFingerprintReference`, and `PlanAuditMetadata` contracts. Plan versions
contain immutable planning, contract, and schema versions and are never inferred or
auto-incremented. A planning fingerprint is an opaque immutable external reference,
not a digest or hash; no hashing or fingerprint generation occurs in the planner.

Plan audit metadata exposes immutable plan ID, version, task and stage counts, and
authorization, policy, and registry revisions for a future Audit Service. The
planner validates and returns metadata only. A future Audit Service owns audit event
generation; CP2-1 performs no logging, emission, or persistence.

CP2-1 creates immutable execution intent, not runtime execution. All identifiers
and aware timestamps are caller-supplied and retained exactly. The planner never
generates UUIDs, clocks, hashes, decisions, or mutable status.

## Determinism, immutability, and canonical ordering

All contracts extend the existing strict, frozen, extra-forbidden
`EvaluationModel`. Plans store immutable tuples. Tasks must use unique,
contiguous sequence numbers beginning at one. Stages and task types must appear in
their complete canonical sequence. Dependencies and artifact identifiers must be
sorted and unique; dependencies must be known, same-plan, and earlier than the
dependent task. Malformed ordering is rejected rather than normalized.

## Security implications

`OFFLINE_EVALUATION` is mandatory. The planner verifies an existing exact `ALLOW`
decision and binds its context to the run request, actor, agent, tenant,
organization, target, dataset, manifest, split, evaluator, policy revision,
registry snapshot, execution context, and delegation lineage. It creates no
authorization, fallback, or implied permission.

Evaluator independence reuses the CP1 like-for-like actor, agent, and model
identity validator. Dataset, manifest, and split provenance and manifest revision
are validated from supplied immutable contracts. Registry snapshot identity,
revision, and schema are validated without lookup. Target and run lineage must
match the supplied verified delegation lineage. Opaque digest references remain
unchanged and are never generated or interpreted.

Planning is metadata-only. Tasks contain no prompt, output, dataset item, hidden
label, expected-output content, secret, provider payload, score, metric, or result.

## Alternatives considered

- A mutable planner service was rejected because hidden state would undermine
  reproducibility.
- Runtime registry, dataset, or repository lookup was rejected because CP2-1 is a
  contract-first planning checkpoint.
- Automatically sorting malformed tasks was rejected because it would conceal
  caller errors and weaken fail-closed validation.
- Creating a new authorization decision was rejected because planning may verify
  but must not authorize execution.

## Consequences

Callers must provide complete immutable contracts, identifiers, timestamps,
authorization metadata, and canonically ordered task specifications. Valid plans
can be reproduced and inspected without infrastructure access. Invalid bindings
fail before any runtime operation can occur.

The following remain explicitly deferred: task execution; model, provider, MCP,
or connector calls; dataset loading; artifact retrieval; evidence collection or
validation; metrics; scoring; ranking; thresholds; aggregation; persistence;
APIs; queues; workers; telemetry; tracing; dashboards; publication; and deployment
gates.
