# ADR-069: Immutable Execution Planning

## Status

Accepted for Sprint 15 CP0.

## Contracts

`app.runtime.planning` will define immutable `ExecutionPlan`, `ExecutionPlanVersion`,
`ExecutionPlanStep`, `ExecutionDependency`, `ExecutionInputBinding`, `ExecutionOutputBinding`,
`ExecutionRetryPolicy`, `ExecutionTimeoutPolicy`, `ExecutionCompensationReference`, and
`ExecutionPlanValidationRecord` contracts. These Sprint 15 names remain inside `app.runtime` and
do not replace similarly named public contracts in `app.execution`.

## Plan construction and binding

Planning consumes an admitted request and exact DecisionPipeline reference. It binds every step
to one action ID/version and immutable registry snapshot revision. Caller-supplied ordering,
dependencies, permitted parallelism, input/output references, classification, authority and
approval references, permit requirements, destination restrictions, retry/timeout policy,
compensation action, dry-run/validation/execution mode, and plan revision are explicit.

Steps and dependencies use canonical ordering. Cycles, missing dependencies, schema mismatches,
unbound outputs, unknown actions, classification downgrade, expanded authority, excessive retry,
and incompatible compensation fail closed. Planning cannot lower classification or expand
resource, action, purpose, destination, tenant, organization, risk, or attempt scope.

## Non-execution boundary

Plan is not execution. Plan validation is not authorization. Planning invokes no adapter, tool,
model, provider, MCP server, connector, filesystem, network, repository, or dynamic code. It makes
no hidden inference, performs no action discovery, issues no permit, and advances no runtime
state except through a separately authorized transition request.

Dry run performs no side effects. Validation-only mode validates contracts only. Execution mode
is intent metadata and does not execute. Dry-run success does not guarantee later admission,
authorization, permit validity, registry availability, or execution success.

## Consequences

Plans are reproducible intent bound to exact governance revisions. Runtime mapping from existing
`app.execution` plans, if used, requires a reviewed compatibility adapter rather than inheritance
or implicit conversion.
