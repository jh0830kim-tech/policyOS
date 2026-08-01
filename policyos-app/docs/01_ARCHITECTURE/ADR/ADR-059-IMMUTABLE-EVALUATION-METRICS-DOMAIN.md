# ADR-059: Immutable Evaluation Metrics Domain

## Context and CP1-A dependency

Evaluation metrics require complete tenant, organization, classification,
lineage, authorization, and source identity metadata. ADR-058 introduced
immutable trusted source bindings for source records that do not carry every
governance field. Metrics consumes validated ACTIVE `TrustedSourceBinding`
records and does not modify or directly enrich upstream source contracts.

## Decision and package placement

Create `app.metrics` downstream of `app.source_bindings` and upstream of
future collection, aggregation, and Judge packages. Lower packages do not
import Metrics. The package contains strict immutable metadata contracts and
pure structural validators only.

## Categories, scopes, and definitions

Metric categories are descriptive governance metadata. Closed metric scopes
map from closed trusted source types through an internal immutable
`MappingProxyType`; no dynamic registry exists. A definition declares its
typed value, compatible unit, direction, supported scopes, versions, owner,
purpose, opaque document reference, tenant, organization, classification, and
revisions. Metric Direction does not judge. No threshold, formula, callback,
prompt, executable code, or weight exists.

## Typed values

Values use a discriminated union for exact integer, Decimal, Boolean, duration,
currency, count, ratio, percentage, enum-reference, and text-reference facts.
Decimal values reject float coercion, NaN, and infinity. Percentage uses the
explicit inclusive 0–100 range. Ratio uses an exact Decimal plus a governed
basis reference; it is not normalized. Currency retains an exact amount and
three-letter currency-code reference. Text is an opaque reference, never raw
text. No conversion, clipping, or rounding occurs.

## Trusted-source observations

A `MetricObservation` binds one definition to one ACTIVE trusted binding,
its exact source type and mapped scope, tenant, organization, classification,
lineage, policy, registry, actor, and optional authorization references.
Definition and binding creation precede the caller-supplied observation time.
A MetricObservation is not retrieval authority and performs no source access.

## Metric results and lifecycle

A result binds exactly one definition, observation, trusted binding, value
type, version, scope, actor, classification, and lineage. RECORDED requires a
typed value. UNAVAILABLE requires a bounded reason. NOT_APPLICABLE carries no
value. INVALIDATED retains original and invalidation references without
mutating the original. Metric is not Score. Metric Result is not PASS/FAIL and
does not authorize publication or transmission.

## Aggregation policy metadata

Closed aggregation and missing-value enums describe possible future behavior.
Policies retain type compatibility, minimum count, opaque percentile/weight
references, canonical grouping references, scope, classification, and version.
AggregationPolicy does not aggregate. No aggregation execution occurs.

## Bundles and audit metadata

A result bundle canonically groups definitions, ACTIVE trusted bindings,
observations, results, and policies. It rejects duplicates, orphans, unsupported
scope, mixed tenant or organization, classification downgrade, lineage
substitution, timestamp regression, and noncanonical caller ordering. Optional
audit metadata contains exact lifecycle and trusted-binding counts and emits
nothing.

## Authorization, classification, isolation, and lineage

Metrics retains existing authorization references but creates no authorization,
approval, permit, lineage, authority, or source binding. Observation
classification dominates definition and binding. Result classification
dominates definition, observation, and binding. Policy dominates definition;
bundle dominates every nested contract; audit dominates bundle. Missing values
never default to PUBLIC. Tenant, organization, actor, and opaque lineage facts
compare exactly.

## Ordering, versioning, determinism, and privacy

Definitions order by key and ID, bindings by source type/source ID/binding ID,
observations and results by caller timestamps and IDs, and policies by ID.
Reason/reference tuples are canonical and unique. Inputs are rejected rather
than silently sorted or deduplicated.

Metric contract versions are caller supplied and independent of Sprint numbers
and the project release version. Contracts are strict, frozen, extra-forbidden,
timezone-aware, serializable, and free of clocks, generated IDs, randomness,
hashing, I/O, runtime state, arbitrary dictionaries, and sensitive content.

## Compatibility and consequences

No Sprint 11–13 public contract changes. Trusted bindings add a required
governance boundary for incomplete sources. This increases explicit metadata
but preserves deterministic validation and tenant isolation.

## Deferred scope

No metric is calculated. No thresholds exist. No Judge, score, PASS/FAIL,
ranking, winner, model selection, collection, aggregation execution, source
retrieval, provider/model/MCP/connector call, persistence, API, queue, worker,
scheduler, telemetry, exporter, or dashboard exists in CP1-B.

## Alternatives considered

- Direct incomplete-source dependency and modifying Sprint 11–13 contracts:
  rejected in favor of ADR-058 bindings.
- Arbitrary JSON values or all-float values: rejected as untyped, lossy, and
  provider-coupled.
- Thresholds in definitions or combined metric/Judge results: rejected because
  measurement and judgment are separate boundaries.
- Runtime aggregation: rejected as deferred executable behavior.
- Raw evidence or output storage: rejected for privacy and boundary safety.
- Telemetry libraries: rejected because operational telemetry is not the
  evaluation metrics domain.
- Mutable result collections: rejected as nondeterministic.
- Dynamic source-to-scope registration: rejected in favor of a bounded closed
  mapping.
