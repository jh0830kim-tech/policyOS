# ADR-066: Runtime Authority, Approval, Authorization, and Permit Model

## Status

Accepted for Sprint 15 CP0.

## Decision

`app.runtime.authority` will separate the execution requester, execution subject, actor, agent
instance, and optional on-behalf-of user. Review is evidence evaluation; human approval records a
human decision; policy authorization evaluates exact policy; a bounded permit carries exercisable
authority; runtime admission accepts one exact execution request. Denial, expiry, revocation, and
consumption are explicit immutable facts.

Request is not authority. Review is not approval. Approval is not authorization. Authorization is
not permit. Permit is not execution. Admission is not an execution result. No step implicitly
creates the next.

## Required selectors and binding

Every authority evaluation binds tenant, organization, actor, agent instance, resource, action,
purpose, risk level, classification, execution environment, a time window, and maximum attempts.
It also binds model ID, provider ID, tool ID, connector ID, and destination when applicable.
On-behalf-of identity, policy and registry revisions, request/plan revisions, lineage, and
provenance references are retained. Missing applicable selectors fail closed.

A permit is action-, resource-, purpose-, destination-, tenant-, organization-, environment-,
risk-, classification-, invocation-, attempt-, and time-bounded. It is revocable, expirable, and
validated immediately before a side effect. A permit cannot broaden its authorization decision.
Existing replay-protected repository permits and one-request MCP permits remain authoritative for
their boundaries; runtime retains and composes their IDs rather than issuing substitutes.

High-risk side effects require explicit permits. Publication, external transmission, deployment,
destructive action, quarantine, cancellation, retry, compensation, and release are distinct
registered actions with distinct authorization and permit decisions. Authorization success does
not automatically mint a permit, and permit possession does not guarantee success.

## Ownership

Runtime authority owns admission decisions and runtime permit references. The human-approval
system owns approval records; runtime stores exact opaque approval references and validates scope.
Policy engines own authorization decisions. Zero-trust and MCP governance own their specialized
permits. Orchestration requests decisions but owns none of them.

## Consequences

Callers provide verbose exact identity and scope. Revocation, expiry, destination changes, retry,
and compensation can be evaluated independently without conflating execution state.
