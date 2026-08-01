# ADR-055: Deterministic Evaluation Pipeline Contract

## Status

Accepted for Sprint 13 CP2-5.

## Context

CP1 through CP2-4 provide immutable domain, plan, execution-state, evidence,
and evidence-validation contracts. A final metadata contract must bind them
without becoming runtime infrastructure or an evaluation result.

## Decision

PolicyOS adds a strict, frozen, caller-supplied pipeline request and record.
Construction validates exact bindings and returns an immutable record.

## Pipeline boundary

Pipeline is not runtime, an executor, or a workflow engine. Construction does
not create a plan, transition execution state, collect evidence, or validate
evidence. CP2-4 reports are referenced and verified, not recreated. Records
contain metadata and references only and convey neither execution nor retrieval
authority.

## Pipeline stages

The closed order is PLANNING, EXECUTION, EVIDENCE, VALIDATION, COMPLETED.
It describes contractual coverage, not activity. Invalid order is rejected,
never sorted or repaired.

## Pipeline lifecycle states

| Pipeline state | Required execution state | Validation | Current stage |
|---|---|---|---|
| ASSEMBLED | IN_PROGRESS, COMPLETED, FAILED, or CANCELLED | PASSED or FAILED | VALIDATION |
| ACTIVE | IN_PROGRESS | PASSED or FAILED | VALIDATION |
| COMPLETED | COMPLETED | PASSED | COMPLETED |
| FAILED | FAILED, or any eligible execution with FAILED validation | FAILED unless execution failed | VALIDATION |
| CANCELLED | CANCELLED | PASSED or FAILED | VALIDATION |

No automatic transition occurs. Pipeline completion does not imply evaluation
correctness, and validation PASSED does not imply model-output correctness.

## Canonical component order

Five caller-supplied references use contiguous ordinals starting at one.
PLANNING binds the plan; EXECUTION the execution record; EVIDENCE the bundle;
VALIDATION the report; COMPLETED uses an explicit terminal reference to the
pipeline identity. IDs, versions, schema versions, timestamps, and order are
retained exactly. Duplicates and omissions fail closed.

## Exact cross-layer binding

Validation binds plan/version, run request, definition, target, execution,
bundle, report, dataset/manifest/split, evaluator, registry identity/revision/
schema, planning fingerprint, policy, authorization, actor/agent, tenant/
organization, offline tier, and delegation lineage identity/digest.
Cross-plan and cross-execution combinations fail closed.

## Validation-report binding

The supplied CP2-4 report is revalidated as its authoritative immutable
contract. Findings, summaries, statuses, and reasons are not generated,
modified, or reinterpreted.

## Authorization boundary

Exact decision, revision, policy, scope, actor, agent, and lineage metadata is
verified. A pipeline record cannot authorize evidence or dataset retrieval,
model/provider/MCP/connector/tool access, or external transmission. Broad
authorization payloads and credentials are excluded.

## Reproducibility

The record retains existing plan/version, run, definition, target, dataset,
manifest, split, evaluator, registry, fingerprint, policy, authorization, and
lineage references. It generates no fingerprint, digest, checksum, or claim
that reproducibility or correctness was proven.

## Audit metadata

Optional audit metadata is immutable and exactly matches pipeline/component
identities, revisions, state, stage, count, version, and creation time. It emits
no audit event and is not persisted.

## Timestamp behavior

All aware timestamps are caller supplied. Pipeline creation cannot predate the
execution update, bundle, or report, and component references cannot postdate
the pipeline. No clock is consulted.

## Immutability

Every contract uses the existing strict frozen evaluation base. Collections
are tuples; there are no dynamic defaults, caches, callbacks, or registries.

## Fail-closed behavior

Unsupported versions, contradictory state/stage combinations, missing,
duplicate, reordered, cross-scope, or timestamp-inconsistent metadata is
rejected. Nothing is inferred, upgraded, deduplicated, sorted, or repaired.

## Security and privacy

No evidence content, prompt text, model output, provider response, policy
document, raw claim, token, credential, secret, or authorization payload is
stored. No provider, model, MCP, connector, tool, filesystem, network,
database, queue, worker, scheduler, telemetry, or tracing operation occurs.

## Consequences

Callers must supply every identity, timestamp, version, state, stage, and
reference consistently. The record proves deterministic contract binding only.

## Deferred scope

Execution, orchestration, planning, evidence retrieval/collection/validation,
dataset or prompt loading, metrics, scoring, ranking, judging, thresholds,
production gates, persistence, APIs, jobs, telemetry, and tracing remain
deferred.

## Alternatives considered

- Executable pipeline orchestration and event-driven orchestration were
  rejected because CP2-5 is a binding contract.
- Automatic stage transitions and mutable pipeline state were rejected because
  state is caller supplied and immutable.
- Invoking CP2-4 to create a report was rejected because an existing report is
  authoritative and construction must not validate evidence.
- Loading components from persistence and database-backed workflow state were
  rejected because construction performs no I/O.
- Automatic component sorting was rejected because invalid input must remain
  observable and fail closed.
- Dynamic plug-in stages were rejected in favor of a closed canonical order.
- Embedding evidence or findings was rejected in favor of metadata references.
- Generating pipeline fingerprints was rejected because no value is generated.
- Treating validation PASSED as an evaluation result was rejected because
  structural validity is not model-output correctness.
