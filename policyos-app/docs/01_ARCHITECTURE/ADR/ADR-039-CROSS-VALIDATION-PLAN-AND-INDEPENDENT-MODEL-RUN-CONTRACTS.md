# ADR-039: Cross-Validation Plan and Independent Model Run Contracts

## Status

Accepted for Sprint 12 Checkpoint 1.

## Context

Sprint 11 provides immutable model identity, action-specific selection authorization, exact
approval and permit lineage, and normalized provider invocation. Cross-validation requires several
model outputs for one objective without weakening those boundaries or treating a plan as a shared
authorization unit.

## Decision

Add app.cross_validation downstream of the Sprint 11 packages. A cross-validation plan contains
two to eight canonically ordered planned runs. Every run has distinct run, selection-request, and
invocation identities and an exact model, provider, adapter, and registry revision. Duplicate exact
model/provider pairs are rejected; repeated sampling is not automatic.

Planning and authorization are separate phases. Binding a planned run requires its exact selection
context, authorization decision, run-specific approval when required, and unique invocation permit.
There is no plan-level approval or permit. A decision, approval, or permit for one run cannot bind
another because selection identity and complete model lineage must match.

Normalized provider results are bound to exactly one authorized run and retain plan, run, permit,
invocation, decision, approval, registry, provider, model, and adapter lineage. Collections report
structure only. COMPLETE means all required runs are terminal and successful runs meet the plan
minimum. FAILED means all required runs are terminal but the minimum is not met. All other states,
including an empty collection, are PARTIAL.

Audit records contain metadata lineage only. They exclude prompts, documents, provider payloads,
and model output. Existing evidence contracts are not reused because their semantics do not yet
represent comparison evidence; evidence comparison is deferred to Sprint 12 CP2.

## Consequences and limitations

Provider execution remains delegated to Sprint 11 adapters. CP1 performs no provider invocation,
parallel scheduling, semantic comparison, evidence extraction, claim matching, scoring, ranking,
majority voting, consensus, synthesis, persistence, evaluation, or observability. Semantic
comparison and consensus remain deferred to later Sprint 12 checkpoints.
