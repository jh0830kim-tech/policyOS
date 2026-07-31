# ADR-054: Deterministic Evidence Validation

## Status

Accepted for Sprint 13 CP2-4.

## Context

ADR-053 introduced immutable metadata-only evidence bundles. PolicyOS needs a
deterministic layer that verifies their structural and governance integrity
without crossing into evidence content, evaluation semantics, or runtime work.

The following boundaries are explicit:

- Validation is not evidence retrieval.
- Validation is not evidence interpretation.
- Validation is not an evaluation result.
- Validation is not metrics.
- Validation is not a judge.

## Decision

PolicyOS introduces closed validation rule, category, and status enums plus
strict frozen finding, summary, report, and request contracts. Validation composes
the authoritative CP2-3 bundle validator and verifies a complete canonically
ordered set of caller-supplied finding metadata.

Each finding contains only a caller-supplied identity, rule, category, status,
opaque reason reference, and aware timestamp. CP2-4 generates no finding
identity, message, reason, or timestamp.

## Rules and categories

The closed rule set covers canonical order, uniqueness, plan and execution
binding, provenance, lineage, authorization, policy, dataset, registry, schema,
audit metadata, and lifecycle eligibility.

Categories group rules as structural, binding, governance, compatibility, or
lifecycle checks. The category for each rule is fixed and validated exactly.
Duplicate findings, duplicate rules, missing rules, and noncanonical order fail
closed.

## Status and report derivation

Finding status is one of PASSED, FAILED, SKIPPED, or NOT_APPLICABLE. UNKNOWN is
not represented. Optional audit metadata produces NOT_APPLICABLE when absent;
all applicable CP2-3 structural checks must pass.

Summaries contain counts only. They contain no percentages, weights, confidence,
quality measure, score, or threshold.

Report overall status has only two valid derived outcomes:

- If any finding is FAILED, overall status is FAILED.
- Otherwise, overall status is PASSED.

There is no weighted or interpretive logic.

## Exact bindings and fail-closed validation

The validator reuses CP2-3 exact bundle validation against the directly supplied
plan and execution record. Cross-plan, cross-execution, provenance, lineage,
authorization revision, policy revision, registry revision, schema, and lifecycle
mismatches are rejected. Existing contracts remain authoritative; CP2-4 neither
duplicates nor weakens their semantics.

## Immutability and determinism

The bundle, plan, execution record, findings, and request remain unchanged.
Report identity, finding identities, opaque reasons, and timestamps are all
caller supplied. Counts and overall status are derived solely from the supplied
validated findings. There is no clock, UUID generation, randomness, sorting,
deduplication, environment state, or mutable registry.

## Security and privacy

Validation examines metadata contracts only. Evidence references remain opaque
and are never dereferenced. No prompt, output, dataset item, provider response,
credential, token, secret, payload, or raw authorization object is stored in a
finding or report.

No filesystem, network, provider, model, MCP, connector, tool, policy-engine,
database, queue, scheduler, worker, telemetry, or tracing operation occurs.

## Consequences

Callers must provide one canonical finding for every closed rule, including
opaque reasons and timestamps. Invalid bundle governance prevents report
construction. Valid reports provide deterministic structural validation metadata
but do not establish evidence truth, content validity, evaluation correctness, or
quality.

## Deferred scope

Evidence retrieval and content validation remain outside CP2-4. Evaluation
pipeline execution, metrics, scoring, thresholds, judging, ranking, aggregation,
interpretation, persistence, APIs, background processing, telemetry, and tracing
remain deferred.

## Alternatives considered

- Retrieving evidence during validation was rejected because references are not
  retrieval authority and validation must perform no I/O.
- Inspecting prompts, outputs, or dataset contents was rejected because CP2-4 is
  metadata-only.
- Generating finding IDs, reasons, messages, or timestamps was rejected because
  it would introduce hidden state or interpretation.
- Weighted findings and quality percentages were rejected because they are
  scoring semantics.
- AI or model-based validation was rejected because deterministic governance
  checks require no judge.
- Persisted or event-emitting reports were rejected because storage and runtime
  integration are later concerns.
