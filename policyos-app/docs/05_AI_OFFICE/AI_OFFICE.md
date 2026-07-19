# AI Office Blueprint

## Purpose
The AI Office coordinates specialist agents around public-policy workflows while preserving human authority and evidence traceability.

## Core components
- Chief Secretary orchestrator
- Specialist agent registry
- Task and workflow engine
- Knowledge retrieval
- Tool gateway
- Prompt/version registry
- Human review and approval
- Execution and audit logs

## Standard lifecycle
1. User submits a task.
2. Authorization and data scope are checked.
3. Chief Secretary classifies the task.
4. Specialist agents receive scoped subtasks.
5. Agents retrieve authorized evidence.
6. Structured results are returned.
7. Chief Secretary consolidates results.
8. Human reviewer approves, revises, or rejects.
9. Final output and lineage are stored.
## Sprint 3 MVP implementation
Provider-independent contracts, registries, path-safe prompt versioning, network-free model fakes, two specialist agents, deterministic routing, evidence preservation, review state, and safe errors are implemented. Hidden reasoning is neither requested nor stored.
## Sprint 4 operational agents
Budget, Statistics, Speech, Press/PR, SNS, and PPT Designer agents now produce typed, evidence-aware, review-governed artifacts. Work packages preserve deterministic execution order, partial failures, warnings, evidence lineage, and human approval requirements.

## Sprint 5 provider privacy boundary

Agent context supports `public`, `internal`, `confidential`, and `restricted` classification. The
provider boundary evaluates tenant, permission, provider allowlist, and classification before any
network operation, then redacts permitted text immediately before transmission. A dedicated audit
record stores only provider/model identifiers, tenant and task lineage, classification, redaction
counts, store policy, time, outcome, policy decision, and safe error code. Prompt text, credentials,
raw provider responses, and hidden reasoning are excluded by schema.
