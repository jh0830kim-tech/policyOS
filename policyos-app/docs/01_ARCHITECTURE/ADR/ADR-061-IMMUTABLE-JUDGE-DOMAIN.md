# ADR-061: Immutable Judge Domain

## 1. Context

Sprint 14 CP3-0 repairs the preserved Judge draft before the full Judge domain is built.
The domain consumes merged CP2 metric-aggregation metadata but performs no judgment.

## 2. Draft defects discovered

The draft coupled criterion semantics to bundle-wide UUID order, incompletely validated
assessment bundles, collided when two policies referenced one aggregation record, and could
call `max()` on an empty assessment selection.

## 3. Decision

Adopt strict, frozen, caller-supplied metadata contracts and pure typed validators. All result
and decision facts remain caller supplied. Decision lifecycle status is not policy outcome.

## 4. Package placement

`app.judge` depends on `app.metrics`; no lower-layer package depends on `app.judge`.

## 5. Policy-owned criterion order

Criterion order belongs to `JudgePolicy`. Each policy owns immutable criterion references with
caller-supplied contiguous sequences beginning at one. UUID ordering does not define policy
semantics, and validators reject rather than reorder input.

## 6. Criterion reuse

A criterion is structural metadata without policy-specific executable meaning. Multiple
policies may reference a compatible criterion through separate policy-owned references whose
versions, scope, and classification match.

## 7. Multi-policy aggregation reuse

One aggregation record may be used by multiple policies through distinct
`JudgeInputReference` records. Identity includes policy, aggregation record, aggregation bundle,
and lineage; the aggregation record is never mutated.

## 8. JudgeInputReference

The input reference retains exact CP2 record version, bundle, aggregation policy and method,
scope, tenant, organization, classification, revisions, lineage, and timestamp metadata.

## 9. Assessment scope and bundle rules

Assessment bundles are single-policy structures. They validate policy-owned ordering, exact
input bindings, required criterion/input pairs, duplicates, orphans, identity, revisions,
classification, lineage, and timestamp monotonicity. Missing assessments are never generated.

## 10. Decision lifecycle

`RECORDED` requires a complete assessment bundle and opaque caller outcome reference.
`UNAVAILABLE` and `NOT_APPLICABLE` carry bounded reasons without an outcome or bundle.
`INVALIDATED` retains original-record and invalidation references without mutation.

## 11. Empty-assessment fail-closed handling

Empty bundles and missing required combinations raise typed Judge errors. Empty collections
never reach generic aggregate functions.

## 12. Tenant and organization isolation

Tenant and organization identifiers match exactly throughout policy, criterion, input,
assessment, bundle, and decision metadata. There is no global fallback.

## 13. Classification

Every classification is explicit. Existing `DataClassification` ordering prevents downgrade:
policy covers criteria; inputs cover aggregation records; assessments and enclosing records
cover all sources. There is no `PUBLIC` default.

## 14. Authorization

Authorization revisions are retained and verified only. A Judge record grants no publication,
transmission, execution, or external-action authority.

## 15. Lineage

Lineage identifiers and digest references must exactly match CP2 metadata. The domain creates no
lineage, digest, provenance, source binding, metric result, or aggregation result.

## 16. Canonical ordering

Policy references use criterion sequence. Inputs use policy, aggregation record, and reference
identity. Assessments use policy sequence, input reference, and assessment identity. Nothing is
silently sorted or deduplicated.

## 17. Versioning

Policy, criterion, assessment-bundle, decision, aggregation-record, and revision metadata are
explicit and checked at binding boundaries.

## 18. Determinism and immutability

Models are strict, frozen, and extra-forbidden. There are no dynamic defaults, clocks, generated
identifiers, randomness, mutation, I/O, or inferred facts.

## 19. Security and privacy

Errors expose bounded contract context only. The package contains no prompts, raw outputs,
evidence content, credentials, tokens, providers, connectors, MCP calls, network calls, storage,
logging, or telemetry.

## 20. Consequences

Callers provide complete governed metadata and receive deterministic validation. More verbose
contracts avoid ambiguous identity and preserve auditability for future layers.

## 21. Deferred scope

No runtime judgment, threshold comparison, LLM Judge, score, PASS/FAIL calculation, ranking,
winner, approval, or publication permission exists. Persistence, API, queue, worker, scheduler,
telemetry, dashboard, and the CP4 Decision Package are deferred.

## 22. Alternatives considered

Rejected alternatives were bundle-wide UUID criterion ordering, a one-policy-per-aggregation
restriction, automatic assessment generation, deriving decisions from assessment collections,
free-form executable criteria, thresholds in criteria, generic exceptions, mutable decision
state, and runtime Judge execution in CP3-0.
