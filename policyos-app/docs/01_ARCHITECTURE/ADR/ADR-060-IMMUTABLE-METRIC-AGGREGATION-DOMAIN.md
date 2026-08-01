# ADR-060: Immutable Metric Aggregation Domain

## 1. Context
PolicyOS needs reproducible selection, grouping, policy-binding, and
caller-supplied aggregate-fact contracts without calculation or judgment.

## 2. CP1-A and CP1-B dependencies
ADR-058 supplies trusted-source governance bindings. ADR-059 supplies
definitions, observations, results, bundles, typed values, and policy metadata.
CP2 consumes those public contracts unchanged.

## 3. Package placement
Contracts live in app.metrics.aggregation_domain and audit metadata in
app.metrics.aggregation_audit. Direction remains source bindings to metrics to
aggregation contracts to future runtime to future Judge.

## 4. Aggregation scope
Closed scope metadata states intended boundaries. Multiple scopes do not rank,
compare, or authorize cross-tenant aggregation.

## 5. Window model
One explicit shape identifies a result set, range, pipeline, run,
cross-validation context, revision, or dataset. No rolling/current-time lookup
or result discovery occurs.

## 6. Grouping specification
Closed dimensions and canonical opaque references replace arbitrary
expressions, SQL, JSONPath, callbacks, and dynamic access. Grouping does not
select a winner.

## 7. Input references
Each input exactly binds a result, definition version, observation, trusted
binding, bundle, ordinal, scope, classification, and lineage without loading a
source.

## 8. Lineage reference
Lineage retains root, digest reference, result set, policy, window, grouping,
and optional parents. Self-parenting and re-rooting fail closed.

## 9. Provenance reference
Canonical reproducibility references are metadata, not proof. No digest,
fingerprint, retrieval, or source content is generated.

## 10. Aggregation request
An immutable request binds exact inputs and governance metadata.
AggregationRequest is not an executable command.

## 11. Record lifecycle status
RECORDED requires a supplied value. UNAVAILABLE requires a bounded reason.
NOT_APPLICABLE carries no value. INVALIDATED references a prior record without
mutation.

## 12. Caller-supplied aggregate values
Values reuse CP1-B discriminated types and are retained exactly. They are never
interpreted, normalized, rounded, clipped, compared, or calculated.
AggregationRecord is not Score and is not PASS/FAIL.

## 13. Policy compatibility
Validators require exact method, types, definition/version, minimum count,
grouping metadata, special references, scope, classification, and versions.

## 14. Missing-value handling
Lifecycle status is checked structurally against the closed policy. No missing
input or value is inferred.

## 15. Aggregation bundle
Canonical nonempty requests and records reject duplicate identities, orphans,
mixed scope, downgrade, re-rooting, and timestamp regression.

## 16. Tenant and organization isolation
All identities compare exactly. Scope metadata grants no cross-tenant or
cross-organization authority.

## 17. Classification
A local pure helper reuses DataClassification ordering. Downstream contracts
must dominate sources; PUBLIC is neither inferred nor defaulted.

## 18. Authorization
Contracts retain references but create no authorization, approval, permit,
publication authority, or transmission authority.

## 19. Lineage and reproducibility
References remain opaque. No graph traversal, content retrieval, derivation,
or claim of proven reproducibility occurs.

## 20. Canonical ordering
Stable caller tuple order is required. Validation never silently sorts or
deduplicates.

## 21. Versioning
Contract versions are caller supplied. Project release version and Git tags
are independent of aggregation versions.

## 22. Audit metadata
Optional exact counts are caller supplied and validated. No event, percentage,
rate, or quality score is emitted or calculated.

## 23. Determinism and security
Contracts are strict, frozen, extra-forbidden, timezone-aware, and contain no
clock, generated ID, randomness, hashing, mutable registry, arbitrary mapping,
I/O, sensitive content, or runtime call.

## 24. Consequences
Callers provide explicit references and values. CP2 remains deterministic,
fail-closed, auditable, and decoupled from execution and judgment.

## 25. Deferred scope
No aggregation computation occurs. No mean, median, sum, percentile, or
weighted calculation occurs. Aggregate values are caller supplied. No
thresholds or Judge exist. No source retrieval, provider/model/MCP/connector
call, persistence, API, worker, scheduler, telemetry, or dashboard exists.

## 26. Alternatives considered
- CP2 calculations, Python statistics, and NumPy were rejected.
- Embedded arrays and mutable accumulation were rejected.
- Arbitrary group-by, SQL/JSONPath, and dynamic plug-ins were rejected.
- Thresholds, combined aggregation/Judge, ranking, and winners were rejected.
- Persistence-backed jobs and automatic provenance were rejected.
