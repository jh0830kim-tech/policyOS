# ADR-028: Multi-Agent Role and Delegation Contracts

## Status

Accepted for Sprint 9 Checkpoint 5.

## Context

ADR-024 through ADR-027 establish narrative, generation, grounding, and advisory reflection.
CP6 coordination needs immutable definitions of who may act, which capabilities are allowed,
what may be delegated, and how assignments and work products retain tenant, classification,
execution, evidence, citation, grounding, and reflection lineage.

## Decision

Add flat `agents.py`, `delegation.py`, and safe `agent_errors.py` contracts. Roles are a closed
AI Office matrix aligned with existing specialist agents. Capabilities are explicit bounded
business identifiers, never providers, models, prompts, tools, or implicit role grants.
Responsibilities and definitions contain capability whitelists, prohibited capabilities,
output types, delegation scope, human-review requirements, classification ceilings, and versions.

The immutable, explicitly constructed catalog rejects duplicate agent IDs and roles and provides
deterministic ID, role, and capability lookup. The default helper returns a new catalog; there is
no mutable singleton, dynamic registration, factory callback, live client, or import-time plugin.
The secretary has coordination capabilities and may delegate only to explicit specialist roles.
It has no specialist legal/budget/statistical authority. Specialists cannot redelegate. Legal work
requires human review and never represents final legal approval.

Delegation requests contain caller-supplied IDs/times, a bounded business objective, exact target
role and capabilities, expected product types, safe lineage references, tenant, actor, correlation,
classification, depth, and deadline. References contain identities only, not embedded execution,
narrative, grounding, reflection, artifact bodies, paths, URLs, credentials, or provider data.
Root/parent lineage is validated and cycles detectable from supplied IDs fail closed.

Delegation policy defaults to depth one, exact role, all capabilities, same tenant, equal
classification, and no specialist redelegation. Typed constraints are closed values rather than
callbacks or executable expressions. Validation checks requester authority, capability escalation,
role scope, enabled state, depth, deadline, cancellation, output type, tenant, classification, and
reference lineage. Eligible agents are canonical; selection succeeds only when exactly one agent
qualifies. There is no cross-role fallback or availability/load guess.

Assignments are created only from valid results and bind the exact approved capability subset,
role, tenant, actor, correlation, classification, output types, and deadline. They contain no live
agent/provider object and `prepared` does not imply execution. Work products are metadata and
references only: assignment/delegation/agent identity, governed type/status, source references,
existing evidence/citation IDs, tenant, classification, human-review state, and caller timestamp.
They embed no artifact body and cannot create evidence or citations. Delegation results report
prepared/rejected/cancelled/expired state without fabricating execution or products.

All contracts are frozen, extra-forbidden, bounded, canonically serialized, and use no hidden
clock, UUID generation, randomness, database, runtime mutation, provider invocation, agent
execution, scheduling, orchestration, recursion, retry, fallback, persistence, prompt, hidden
reasoning, tool use, browsing, or dynamic code. Validation is bounded `O(A + C + R + O)`; catalog
lookups are bounded over the fixed catalog and no full execution/narrative object is copied.

## Consequences and deferred work

CP6 Secretary coordination, runtime execution, scheduling, workload/availability selection,
artifact persistence, approval workflows, recursive execution, inter-agent chat, and memory remain
deferred. CP5 defines authority and traceability only. This extends ADR-019 through ADR-027 without
changing their objects or authorizing provider/runtime behavior.
