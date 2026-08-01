# ADR-056: Immutable Observability Domain

## Context

PolicyOS has immutable execution, authorization, model/provider, MCP,
cross-validation, zero-trust, audit, quarantine, and evaluation records. It
needs a shared metadata vocabulary without introducing telemetry runtime.

## Decision

Create a top-level app.observability package that depends one-way on existing
immutable contracts. It defines strict frozen events, correlation, subjects,
redaction declarations, completeness facts, deployment-stop signals, bundles,
and pure exact source-binding validators.

## Observation categories and types

Closed categories cover identity, authorization, execution, model/provider,
MCP/connector, cross-validation/Secretary, zero-trust/credentials/quarantine,
evaluation, audit, and governance. Closed event types exclude infrastructure
measurements. Severity and outcome are explicit caller-supplied metadata.

## Correlation and causation references

Correlation contexts retain caller-supplied correlation, optional trace,
parent, root, causation, scope, actor, task, resource, risk, classification,
delegation lineage, and optional source identities. They perform no propagation
or graph traversal. Self-reference, unknown local parents, and bounded local
cycles fail closed.

## Subject and source bindings

Subjects are opaque typed references, never embedded source objects. Focused
validators bind events exactly to evaluation, security, quarantine, MCP,
model/provider, cross-validation, consensus, Secretary, and secret-audit
records. Source references use explicit opaque schemes and are never loaded.

## Metadata-only events

Events contain identities, bounded reasons, classifications, references,
outcomes, and aware timestamps only. Occurrence cannot follow recording.
Category/type compatibility and tenant/organization scope are validated.

## Redaction declarations

Redaction policy references contain no policy content or executable rules.
Declarations list canonically ordered excluded-data categories. Redaction
declarations are metadata only; no content inspection or redaction occurs.

## Completeness requirements and assessments

Requirements describe expected categories and event types. Assessments use
caller-supplied observed and missing facts. COMPLETE has no missing facts;
INCOMPLETE has at least one. No event store is queried and no percentage is
calculated.

## Deployment-stop signals

Signals retain exact execution-combination, tenant/global scope, trigger,
security, quarantine, reason, policy, and separate clearing-decision
references. Deployment-stop signals do not perform deployment actions.

## Security and quarantine linkage

Incomplete audit metadata, confirmed security violations, quarantine decisions,
and deployment signals remain separate caller-supplied records. Security
observations do not automatically create quarantine decisions. Existing
zero-trust first-event quarantine semantics remain authoritative.

## Canonical ordering

Events are supplied by occurred_at and observation_event_id ascending.
All bounded ID, reason, category, and type tuples are canonical and unique.
Order is validated, not silently repaired.

## Tenant and classification isolation

Every event, subject, assessment, and bundle is tenant and organization bound.
Existing DataClassification ordering prevents downgrades. Tenant-scoped
deployment signals cannot become global; global scope is explicit.

## Immutable observability bundle

A bundle contains a non-empty canonical event tuple plus declarations,
assessments, and signals. It validates exact correlation, root lineage, scope,
classification, references, timestamps, uniqueness, and local parent linkage.
It emits and persists nothing.

## Audit metadata

Optional audit metadata exactly matches bundle identity/version, correlation,
scope, classification, event/category/critical counts, incomplete assessments,
deployment signals, and creation time. It emits no audit event.

## Determinism

All IDs, timestamps, versions, outcomes, reasons, and references are caller
supplied. There are no clocks, generated IDs, randomness, sampling, sorting,
deduplication, enrichment, or environment-derived values.

## Fail-closed validation

Invalid order, scope, classification, correlation, parent, source, audit,
completeness, redaction, quarantine, or deployment linkage is rejected.

## Security and privacy

Observations contain no prompts, documents, model outputs, hidden labels,
expected outputs, secrets, tokens, credentials, authorization headers,
chain-of-thought, arbitrary metadata dictionaries, or raw payloads.

## Consequences

Callers carry the burden of supplying complete, canonical metadata. Observation
presence does not prove completeness, completeness does not prove correctness,
and critical severity triggers no runtime behavior.

## Deferred scope

Observability Domain is not a telemetry runtime. No logs are emitted, traces
exported, metrics calculated, events persisted, dashboards created, alerts
delivered, sampling executed, or content redaction executed. Exporters, stores,
retention, queries, visualization, and runtime propagation remain future work.

## Alternatives considered

- Direct logging calls in domain modules were rejected to preserve purity.
- OpenTelemetry integration was rejected as future runtime infrastructure.
- Database-backed event storage was rejected because CP3 has no persistence.
- Automatic trace ID generation was rejected because IDs are caller supplied.
- Free-form metadata dictionaries and raw payload logging were rejected for
  determinism, privacy, and schema safety.
- Automatic redaction was rejected because declarations contain no content.
- Automatic completeness discovery was rejected because facts are supplied.
- Automatic alerting was rejected because signals do not execute actions.
- Direct model quarantine from observations was rejected because existing
  zero-trust decisions remain authoritative.
- Cross-tenant shared bundles were rejected to preserve isolation.
