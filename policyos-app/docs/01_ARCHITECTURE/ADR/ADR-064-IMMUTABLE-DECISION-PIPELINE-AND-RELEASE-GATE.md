# ADR-064: Immutable Decision Pipeline and Release Gate

## 1. Context

Sprint 14 CP5 needs a deterministic metadata assembly boundary after immutable Decision
Packages, while operational release behavior remains future work.

## 2. CP4 dependency

The domain consumes caller-supplied, validated `DecisionPackage` records without modifying CP4
or any lower contract.

## 3. Package placement

Contracts live in `app.decision_pipeline`. Dependency direction remains metrics to Judge to
decisions to decision pipeline to a future operational runtime.

## 4. Pipeline stages

Stages are closed caller-supplied metadata. No stage advances automatically and no transition
engine exists.

## 5. Pipeline lifecycle

Lifecycle statuses describe metadata assembly only. `COMPLETED` means metadata assembly
complete only.

## 6. Package binding

Bindings retain exact package identity, version, lifecycle, disposition, unresolved reviews,
governance declarations, revisions, scope, lineage, provenance, and timestamp facts.

## 7. Stage records

Stage records retain caller sequence and facts. Contiguous sequence validation performs no
work, scheduling, progression, or execution.

## 8. Release gate

Release-gate status is inert governance metadata. `BLOCKED` does not execute a stop.

## 9. Review versus approval versus authorization

Review state and approval or authorization requirement flags remain separate declarations.
DecisionPipeline is not approval or authorization and creates neither.

## 10. Release gate versus permission

ReleaseGate is not a permit. It grants no deployment, publication, or external-transmission
permission and triggers no action.

## 11. Lineage

Lineage references retain caller-supplied roots and local identities. No graph traversal,
digest generation, or lineage creation occurs.

## 12. Provenance

Provenance references are opaque metadata, not proof. No source retrieval, fingerprinting, or
hash generation occurs.

## 13. Classification

Every classification is explicit and downstream records cannot lower source classification.
There is no `PUBLIC` default.

## 14. Tenant and organization isolation

Tenant and organization identities match exactly across packages, bindings, stages, gates,
lineage, provenance, audit metadata, and pipelines.

## 15. Identity

All package, pipeline, stage, gate, actor, agent, user, and reference identifiers are caller
supplied and retained.

## 16. Canonical ordering

Stable tuple order is required and duplicates are rejected. Validation never silently sorts,
deduplicates, normalizes, or repairs caller data.

## 17. Versioning

Pipeline versions are caller supplied and independent of project versions, Sprint numbers, and
Git tags.

## 18. Audit metadata

Counts are caller supplied and checked exactly. No readiness, percentage, event, or operational
audit emission is produced.

## 19. Determinism and immutability

Contracts are strict, frozen, extra-forbidden, timezone-aware, deterministic, and free of
generated values, hidden clocks, randomness, mutation, and I/O.

## 20. Security and privacy

DecisionPipeline is metadata only. DecisionPipeline is not execution, deployment, publication,
transmission, approval, or authorization. No sensitive raw content is accepted.

## 21. Consequences

Callers provide explicit verbose governance facts. Pipeline possession and gate status confer no
authority or operational readiness.

## 22. Deferred scope

No runtime behavior, source retrieval, model/provider/MCP/connector call, persistence, API,
queue, worker, scheduler, telemetry, exporter, or dashboard is introduced.

## 23. Alternatives considered

Rejected alternatives were orchestration-runtime reuse, operational approval reuse, combining
release gates with authorization, derived readiness, automatic stage progression,
persistence-backed workflow, executable gate callbacks, automatic deployment stops, automatic
publication eligibility, and mutable pipelines.
