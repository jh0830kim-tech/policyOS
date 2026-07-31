# ADR-050: Immutable Evaluation Domain and Reproducibility Records

- Status: Accepted
- Date: 2026-07-31

## Context

PolicyOS needs reproducible evaluation records without changing model outputs,
cross-validation outcomes, or Secretary decisions. Evaluation inputs, reference
material, hidden labels, and expected outputs have different visibility rules.
The evaluated model and evaluator must have independently identifiable actors,
agents, models, policies, and versions. Evaluation records reference existing
immutable artifacts rather than copying prompts, documents, outputs, or labels.

## Decision

PolicyOS defines a provider-neutral `app.evaluation` domain containing strict,
frozen, extra-forbidden contracts for definitions, targets, datasets, splits,
policies, evaluators, run requests, access plans, lifecycle events, runs, items,
artifacts, reproducibility, integrity, authorization, invalidation, audit,
registry snapshots, and cross-validation bindings.

All evaluations use `OFFLINE_EVALUATION`. Tenant, organization, represented user,
service actor, agent, task, and immutable delegation lineage are mandatory run
context. Model, provider adapter, MCP protocol, tool schema, dataset, split,
evaluation policy, evaluator, authorization engine, and authorization rule-set
versions are retained as opaque metadata references. Caller-supplied identifiers
and aware timestamps keep construction deterministic.

CP1 calculates no scores or metrics and defines no pass/fail thresholds or
rankings. It does not invoke evaluators, providers, models, MCP servers, tools, or
connectors.

## Data visibility and authorization

Evaluated agents may receive authorized input and public reference identifiers.
Hidden-label and expected-output identifiers are never visible to the evaluated
agent. Evaluator access requires an exact `ALLOW` decision bound to the run,
access context, evaluator actor and agent, tenant, organization, data type,
artifact reference, offline tier, policy revision, and delegation lineage.

Authorization validation is a pure guard. It performs no artifact retrieval.
Denied or mismatched protected-data access therefore cannot initiate retrieval.
Existing zero-trust policy maps unauthorized protected-data access to the
`EVALUATION_DATA_ACCESS_ATTEMPT` quarantine trigger. Audit records contain only
safe metadata and reference identifiers.

## Reproducibility and integrity

Reproducibility records retain exact immutable version references for the target,
dataset and split, evaluator and policy, authorization engine and rule set,
execution environment, dependency manifest, and delegation lineage. Integrity
records hash only canonical public metadata references. They never hash raw
prompts, documents, outputs, hidden labels, expected outputs, or secrets.

Evaluation reproducibility SHALL include an immutable Evaluation Registry Snapshot
Reference and Dataset Manifest Reference. Registry and manifest digest references
are opaque identifiers only. Digest generation is outside the Evaluation Domain;
a future Registry Service may own digest generation. The Evaluation Domain only
stores and validates immutable references and never calculates or cryptographically
validates registry or manifest digests.

Cross-validation evaluation bindings preserve the source plan, distinct run
identities, tenant and organization, and protected root lineage. Consensus and
Secretary handoff references are immutable identifiers; evaluation cannot alter
their source records.

## Lifecycle and invalidation

Lifecycle changes are represented by new immutable state records and validated by
pure transition logic. A completed evaluation may be invalidated only through an
explicit reviewed invalidation decision and a new `INVALIDATED` state record. The
completed run record remains unchanged. Reviewer actor and agent identities are
compared only with corresponding evaluated identity domains.

## Consequences and limitations

CP1 establishes contracts and pure validation only. Runtime artifact retrieval,
dataset loading, evaluator execution, persistence, APIs, queues, workers,
telemetry, tracing, dashboards, alerting, and metric engines remain deferred.
Cross-validation validation consumes immutable plan and root-lineage contracts;
consensus and Secretary records remain opaque immutable references to avoid a
reverse dependency or runtime coupling.
