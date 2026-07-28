# ADR-042: Secretary Integration and Cross-Validation Handoff Boundary

## Status

Accepted for Sprint 12 Checkpoint 4.

## Decision

A `ConsensusDecisionPackage` is handed to Secretary as immutable structural
metadata, not as a final answer. Exact package, assessment, plan, tenant,
resource, registry, candidate, conflict, review, and classification lineage is
preserved. Secretary cannot select a winner, remove conflict, complete review,
or reinterpret agreement as truth.

Sprint 10 integration is content-bearing and keyed to specialist work products.
It cannot represent CP4 lineage without loss. Those contracts remain unchanged;
legacy conversion fails closed. The lossless CP4 boundary remains downstream in
`app.cross_validation`, avoiding reverse imports and dependency cycles.

Structural integration, human approval, publication approval, and external
transmission authorization are separate. `AGREED` may permit internal structural
integration only with explicit caller policy. It never means approved,
publishable, externally transmissible, verified, or true. Unresolved conflict or
review makes publication ineligible. Internal integration may coexist with
external-transmission ineligibility. Classification cannot be downgraded.

CP4 performs no provider call, synthesis, publication, transmission, approval or
review execution, persistence, evaluation, or observability. Sprint 13 retains
evaluation and observability.
