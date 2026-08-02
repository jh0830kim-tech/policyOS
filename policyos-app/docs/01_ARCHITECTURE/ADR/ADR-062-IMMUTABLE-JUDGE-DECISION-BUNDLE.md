# ADR-062: Immutable Judge Decision Bundle

## 1. Context

Sprint 14 CP3-B needs a governed, immutable bundle of caller-supplied Judge decision facts
after the CP3-0 Judge domain foundation. The bundle must preserve policy-specific decisions,
review requirements, and governance metadata without calculating an outcome or granting
operational authority.

## 2. CP3-0 dependency

The domain consumes the validated Judge policies, criteria, input references, assessments,
assessment bundles, and decisions defined under ADR-061. It does not modify Judge, metric,
aggregation, evaluation, or trusted-source contracts.

## 3. Package placement

Decision-bundle contracts live in `app.judge`. Dependency direction remains trusted source
bindings to metrics to metric aggregation to Judge. The bundle introduces no dependency on
decisions, the decision pipeline, APIs, persistence, or runtime infrastructure.

## 4. Bundle contents

A `JudgeDecisionBundle` binds an exact bundle version, policies, policy-specific decisions,
review requirements, lineage references, provenance references, audit metadata, scope,
tenant, organization, classification, root lineage, and creation time. All identities and
facts are caller supplied and retained without generation, enrichment, or substitution.

## 5. Multi-policy reuse

One validated Judge input or aggregation record may be referenced by multiple policies, but
each policy keeps its own criteria, assessments, decision, review requirements, and binding
identity. Reuse never flattens policy semantics, merges outcomes, mutates the shared input, or
allows one policy's review state to satisfy another policy's requirements.

## 6. Review requirements and lifecycle

Review records retain an explicit policy and decision binding plus caller-supplied lifecycle
metadata. The closed review lifecycle distinguishes `NOT_REQUIRED`, `PENDING`, `COMPLETED`,
and `WAIVED`. Each status has exact reference requirements: pending review retains its request,
completed review retains its request and result, waived review retains its request and waiver,
and review references are absent when review is not required. Validators reject inconsistent,
duplicate, cross-policy, or substituted review facts.

Review lifecycle is metadata only. `COMPLETED` does not mean approved, correct, publishable,
or authorized. `WAIVED` does not create approval or permission. The bundle does not request,
perform, complete, or waive a review.

## 7. Decision lifecycle semantics

Judge decision lifecycle values remain caller-supplied metadata under ADR-061. They describe
record state and do not represent a winning policy, recommendation, execution result,
publication eligibility, approval, or authorization. The bundle preserves current lifecycle
facts exactly and derives no readiness or aggregate outcome from them.

## 8. Review versus approval versus authorization

Review, approval, and authorization are separate boundaries. A review requirement or review
result is not an approval. Approval is not authorization. `JudgeDecisionBundle` creates no
approval, authorization decision, permit, credential, permission, or executable capability.
References to those concepts, where present in governed source metadata, remain opaque facts
and cannot be broadened or exercised by the bundle.

## 9. Lineage

Lineage references retain exact caller-supplied local reference identity, root lineage identity,
root digest reference, policy and decision bindings, parent identity where applicable, schema
version, and timestamps. Roots must agree across the bundle, self-parenting and substitutions
are rejected, and duplicate reference identities are forbidden. Validation performs no graph
construction, unbounded traversal, digest generation, lineage creation, or source lookup.

## 10. Provenance

Provenance is represented by bounded, opaque caller-supplied references tied to the exact Judge
facts they describe. Provenance and lineage are distinct: neither proves correctness, authority,
or reproducibility. The bundle performs no retrieval, hashing, fingerprinting, attestation, or
external verification.

## 11. Classification and isolation

Every classification is explicit and downstream bundle metadata cannot be less restrictive
than its sources. `PUBLIC` is never inferred or used as a fallback. Tenant and organization
identities must match exactly across policies, decisions, reviews, lineage, provenance, audit
metadata, and the bundle. No cross-tenant or cross-organization reuse is authorized.

## 12. Canonical ordering and identity

Policy decisions, reviews, lineage, and provenance use explicit stable ordering keys. Duplicate
or noncanonical tuples are rejected rather than sorted, deduplicated, repaired, or normalized.
Bundle, policy, decision, review, actor, and reference identities remain caller supplied.

## 13. Versioning and audit metadata

Bundle, contract, schema, policy, decision, lineage, and provenance versions are explicit
caller facts. They are independent of Sprint numbers, the project release version, and Git
tags. Optional audit metadata retains exact counts and governance facts; it emits no audit event
and computes no score, rate, recommendation, or readiness state.

## 14. Determinism, immutability, and security

Contracts are strict, frozen, extra-forbidden, timezone-aware, deterministic, and free of
generated identifiers, hidden clocks, randomness, mutation, and I/O. The bundle accepts no raw
prompts, model outputs, evidence bodies, credentials, tokens, secrets, or arbitrary payloads.
It invokes no model, provider, MCP server, connector, permission service, or workflow.

## 15. Consequences and deferred scope

Callers must provide verbose, internally consistent governance metadata. In return they receive
a deterministic package that preserves multi-policy Judge facts and unresolved review state
without implying authority. Recommendation selection, approval, authorization, publication,
external transmission, deployment, persistence, APIs, queues, workers, schedulers, telemetry,
exporters, and dashboards are deferred.

## 16. Alternatives considered

Rejected alternatives were flattening multiple policies into one outcome, treating completed or
waived review as approval, deriving readiness from lifecycle state, generating lineage or
provenance, accepting raw Judge or evidence payloads, mutating shared aggregation records, and
introducing an operational workflow or persistence-backed bundle.
