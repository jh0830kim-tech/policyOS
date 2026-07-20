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
## Sprint 5 release verification

The release smoke path starts with authentication and organization-scoped `agent.execute`, executes the configured provider through the Chief Secretary, and verifies terminal task/run/package states, reviewable artifacts, usage telemetry, and provider audit metadata. Run `pytest -m smoke` for the network-free suite. Live provider connectivity is a separate, explicit staging-only operation documented in `RUNBOOK.md`.

## Sprint 6 Checkpoint 8: Evidence-aware AI Office

The production Office application service can receive an injected governed Knowledge Router before specialist execution. It builds one organization-scoped query, rejects wholly unavailable evidence, converts the router result to a minimized `OfficeEvidencePackage`, and stores only query/route identifiers plus counts, confidence, sufficiency, failures, and fallback status on the Work Package.

`AgentContext` carries the optional package. The Chief Secretary workflow deterministically selects legal evidence for Legal Review, budget evidence for Budget Analysis, statistical evidence for Statistics, and approved cited facts for public-facing agents. Safe excerpts, classifications, stable evidence IDs and existing citation IDs propagate through AgentResult and artifact structured payloads; agents cannot create substitute citations. All approved prompt files instruct agents to use supplied evidence only and expose conflicts, gaps, stale sources and unsupported claims.

Partial/insufficient evidence, material gaps, unresolved conflicts, incomplete or stale citations, public-facing artifacts, unsupported claims, or partial Agent failures require review. Approval is never automatic. Evidence-unavailable execution stops before provider calls. Existing timeout, cancellation, privacy, provider telemetry and artifact review controls remain authoritative. API request schemas accept legal/budget/minutes workflows and source/date/fiscal context; production router/executor composition in the HTTP dependency container remains follow-up work.
