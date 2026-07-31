# ADR-048: Execution Tiers and Tenant-Isolated Worker Boundaries

## Status

Accepted for Sprint 13 CP0.5.

## Decision

Execution scheduling intent is classified as immediate interactive, immediate
legal review, deferred background, scheduled batch, or offline evaluation.
The tier never grants resource authorization.

Deferred, batch, and offline work must stop after completion. Completion
requires agent termination and grant invalidation; retries require a new task
attempt, agent instance, and credentials.

Every tenant has a distinct security-boundary identity, worker-pool identity,
and encryption-key reference. Shared infrastructure may exist, but tenants do
not share one worker security boundary for cost savings.

## Development environment note

On Windows, the managed sandbox can create protected
`tests/.knowledge_tmp/policyos-ingest-*` directories that it cannot later
write or remove. This is an external ACL condition, not a product cleanup or
parser-handle defect. Production or test behavior must not be weakened to
accommodate it; outside-sandbox validation is authoritative for that test.

## Consequences

- Offline evaluation access is tenant- and classification-scoped and hidden
  labels or expected outputs require exact authorization.
- CP0.5 provisions no queue, worker, process, container, or Kubernetes
  infrastructure.
