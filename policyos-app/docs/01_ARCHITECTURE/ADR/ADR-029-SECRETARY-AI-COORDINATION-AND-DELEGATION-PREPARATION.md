# ADR-029: Secretary AI Coordination and Delegation Preparation

## Status

Accepted for Sprint 9 Checkpoint 6.

## Context

ADR-028 defines immutable AI Office roles, capability boundaries, delegation validation, and
assignment preparation. PolicyOS now needs a deterministic way for the Secretary role to decompose
a trusted business request into bounded specialist work without executing agents or crossing those
authority boundaries.

## Decision

Add flat `coordination.py` and `coordination_errors.py` contracts under `app.intelligence`. A frozen
request and trusted context preserve caller-supplied identity, tenant, classification, lineage,
timestamps, deadline, requested outputs, and review requirements. Closed purposes select fixed,
bounded templates; objective text is never interpreted as a prompt or used for dynamic planning.

Each template produces immutable tasks with stable template IDs, one closed role/capability mapping,
expected work-product types, explicit dependencies, and propagated input-reference identities. A
deterministic Kahn topological sort rejects duplicate, missing, self, and cyclic dependencies. The
Secretary owns only integration and quality-review planning tasks. These tasks are not specialist
conclusions and receive no specialist assignment. Human-review gates receive no AI assignment and
cannot approve or publish anything.

Assignable specialist tasks become CP5 `DelegationRequest` objects using caller-supplied delegation
IDs. CP6 calls the CP5 validator exactly once per assignable task and calls the CP5 assignment builder
only for a uniquely valid result. It performs no cross-role or capability fallback. A missing required
assignment rejects preparation; an optional miss may yield a traced partial plan. Cancellation and
expiry return no plan. Prepared plans remain metadata for future execution, not execution authority.

All contracts are frozen and extra-forbidden. Collections, text, depth, tasks, dependencies, and
assignments are bounded and canonically ordered. There is no hidden clock, UUID generation,
randomness, mutable registry, provider/model selection, prompt, tool, network or file access,
database, persistence, runtime dispatch, agent invocation, scheduler, retry, fallback, artifact
creation, automatic approval, or publication. Template and mapping lookup are constant-time; task
construction and sorting are bounded, with DAG validation proportional to tasks plus dependencies.

## Consequences and deferred work

CP6 makes Secretary coordination auditable and reproducible while retaining CP5 as the authority for
delegation eligibility. Agent execution, result collection and integration, CP3/CP4 result inspection,
artifact generation, persistence, scheduling, approval workflows, publication, replanning, memory,
and cross-plan coordination remain deferred. The intelligence layer may reference execution contracts;
the execution layer must not depend on intelligence coordination contracts.
