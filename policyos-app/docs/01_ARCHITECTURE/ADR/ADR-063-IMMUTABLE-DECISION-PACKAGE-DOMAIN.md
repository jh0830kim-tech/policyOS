# ADR-063: Immutable Decision Package Domain

## 1. Context

Sprint 14 CP4 needs a governed package of caller-supplied decision facts after the immutable
Judge decision-bundle boundary. Operational decision pipelines remain future work.

## 2. CP3-B dependency

The domain consumes validated `JudgeDecisionBundle` contracts without changing Judge, metric,
aggregation, evaluation, or trusted-source contracts.

## 3. Package placement

Contracts live in `app.decisions`. Dependency direction is metrics to Judge to decisions to a
future decision pipeline. No lower package imports `app.decisions`.

## 4. Decision package lifecycle

The closed lifecycle is `RECORDED`, `UNAVAILABLE`, `NOT_APPLICABLE`, and `INVALIDATED`.
Lifecycle is metadata and does not represent operational success or permission.

## 5. Disposition metadata

Disposition is caller-supplied metadata. It is not derived, recommended, executed, or used to
override policy.

## 6. Subject references

Typed subject references bind an exact governed subject, scope, classification, lineage, and
timestamp. There is no arbitrary subject dictionary or subject loading.

## 7. Judge bundle bindings

Bindings retain exact Judge bundle versions, policies, decisions, unresolved reviews, lineage,
provenance, revisions, scope, classification, and time. Multiple bundles remain explicit and
policy semantics are not flattened.

## 8. Review summary

Review summaries retain caller-supplied lifecycle groups and unresolved requirements. They do
not repair, infer, execute, or complete reviews.

## 9. Review versus approval versus authorization

DecisionPackage is not approval. DecisionPackage is not authorization. Review completion or
waiver is not approval. Separate approval and authorization flags are declarations only and no
approval, permit, or authorization object is created.

## 10. Lineage

Lineage references preserve exact roots and local identities. They create no graph, digest, or
new lineage and perform no unbounded traversal.

## 11. Provenance

Provenance consists of opaque caller references. Lineage and provenance references are not
proof of correctness or reproducibility. No source retrieval, hash, or fingerprint occurs.

## 12. Classification

Every classification is explicit. Downstream metadata must be equally or more restrictive than
all sources; `PUBLIC` is never inferred or defaulted.

## 13. Tenant and organization isolation

Tenant and organization identifiers match exactly throughout subjects, Judge bindings, review
summaries, lineage, provenance, audit metadata, and packages. There is no global fallback.

## 14. Identity

Package, subject, actor, agent, user, Judge, policy, decision, and reference identifiers are
caller supplied and retained without generation or substitution.

## 15. Canonical ordering

Caller tuples follow explicit stable keys. Duplicate and noncanonical input is rejected rather
than silently sorted, deduplicated, normalized, or repaired.

## 16. Versioning

Package and referenced contract versions are caller supplied. Project version and Git tags are
independent of Decision contract versions.

## 17. Audit metadata

Optional exact counts are caller supplied and validated. The domain emits no audit event and
calculates no percentage, rate, readiness state, or quality measure.

## 18. Determinism and immutability

Contracts are strict, frozen, extra-forbidden, timezone-aware, and free of generated IDs,
hidden clocks, randomness, mutation, and I/O. No runtime behavior is introduced.

## 19. Security and privacy

DecisionPackage is not publication or transmission permission. DecisionPackage is not
execution. It contains no raw prompts, model outputs, evidence content, credentials, tokens,
secrets, or arbitrary payloads. No model, provider, MCP, or connector call occurs.

## 20. Consequences

Callers provide verbose governed metadata and receive deterministic validation. A package may
retain unresolved review requirements without implying readiness or authority.

## 21. Deferred scope

DecisionPackage is not recommendation generation. Operational pipelines, approvals,
authorizations, publication, external transmission, deployment, persistence, APIs, queues,
workers, schedulers, telemetry, exporters, and dashboards are deferred.

## 22. Alternatives considered

Rejected alternatives were operational approval reuse, combining review and authorization,
automatic readiness derivation, raw Judge outcomes, executable disposition callbacks,
arbitrary subject dictionaries, a CP4 runtime pipeline, persistence-backed workflow,
automatic publication eligibility, and mutable decision packages.
