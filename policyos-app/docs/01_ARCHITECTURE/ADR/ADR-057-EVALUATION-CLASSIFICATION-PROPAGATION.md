# ADR-057: Evaluation Classification Propagation and Non-Downgrade Boundary

## Context

Sprint 13 RC1 proved that a PUBLIC observation could bind to a pipeline derived
from classified evaluation inputs. Evaluation definition, target, dataset,
policy, and evaluator references carried classification, but plan, execution,
evidence, validation, and pipeline records did not.

## Decision

Use the existing `DataClassification` ordering and carry an explicit required
classification through planning, execution, evidence provenance and lineage,
evidence bundles, validation reports, pipelines, and observation source
bindings. The effective source classification is the most restrictive of the
explicit typed inputs. A downstream classification may be equal or more
restrictive, never less restrictive.

Classification is caller supplied at the planning boundary and checked against
the deterministic effective source classification. Later builders and pure
validators check their exact bound predecessors. They perform no content
classification, lookup, inference, generation, or mutation.

Observation source validators compare the event, subject, and correlation
classifications with the exact source record classification. Observability
bundles remain at least as restrictive as every event. Deployment-stop signals
remain at least as restrictive as their triggering observations. Redaction is
metadata-only and never lowers classification. The same principle applies to
quarantine metadata; neither signal performs an action.

## Compatibility and migration

The new fields are required and constitute coordinated schema revisions. Old
serialized evaluation and deployment-stop records cannot be safely treated as
PUBLIC and will fail validation when classification is absent. A persistence
owner must migrate legacy metadata by supplying an explicit classification
from a trusted historical source before deserialization. No default, implicit
upgrade, persistence migration, or runtime compatibility lookup is provided.

For serialized contracts that already carry caller-supplied contract, schema,
record, or bundle version metadata, producers must publish a new major contract
or schema identifier (conventionally `v2`) when writing the classification-aware
shape. Existing `v1` identifiers describe the pre-classification shape and must
not be reused. PolicyOS does not generate or increment these values: producers
and migration owners supply them explicitly, and consumers must negotiate their
compatibility out of band. Contracts without an explicit version field gain no
invented version field in this correction.

Migration requires a trusted historical classification recorded by the system
that owned the original evaluation source. Tenant, organization, actor, URI,
resource, reference, and payload content are not classification sources. If no
trusted historical classification exists, the record cannot be migrated safely
and remains rejected. A legacy record may not reach observability source
validation until its migration metadata is complete.

## Consequences

- Missing classification fails closed.
- PUBLIC-only flows remain representable when every source is explicitly PUBLIC.
- More restrictive downstream handling is allowed.
- Existing records need explicit metadata migration before reuse.
- Runtime evaluation, telemetry, quarantine, and deployment actions remain deferred.
