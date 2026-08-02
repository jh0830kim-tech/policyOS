# ADR-073: Immutable Runtime Authority Domain

## 1. Context

Sprint 15 CP1 needs exact authority metadata between Sprint 14 DecisionPipeline records and future
runtime planning. DecisionPipeline possession grants no authority, and ReleaseGate grants no
permit.

## 2. CP0 dependency

This decision implements ADR-065 layering and ADR-066 authority separation without weakening
ADR-067 through ADR-072 or the normative Sprint 15 architecture rules.

## 3. Package placement

Contracts live in `app.runtime.authority`. `app.runtime` exposes only this namespace in CP1.
Dependency direction remains Sprint 14 immutable domains to runtime authority to future planning,
state, orchestration, ports, and adapters. No lower package imports runtime.

## 4. Existing zero-trust and MCP compatibility

Existing replay-protected repository permits and one-request MCP permits remain authoritative at
their own boundaries. Runtime stores an immutable bounded snapshot/reference with source type and
external permit identity. Runtime references do not broaden those permits, replace their guards,
or reproduce their credential or invocation implementation.

## 5. Request versus authority

An execution request is caller intent only. It creates no permission, decision, permit, state, or
side effect.

## 6. Review versus approval

Review status retains external review facts. Review is not approval; completion and waiver confer
no authority.

## 7. Approval versus authorization

Approval retains a human decision reference. Approval is not authorization and does not evaluate
policy.

## 8. Authorization versus permit

Authorization retains an external policy decision and exact revision. Authorization is not a
permit, and CP1 never mints exercisable authority.

## 9. Permit versus admission

A permit reference records caller-supplied bounded authority facts. It does not admit a request.
Admission separately verifies that supplied references match the request.

## 10. Admission versus execution

Admission is not execution. An admitted decision contains no execution lifecycle, dispatch,
callback, or result and invokes nothing.

## 11. Execution subject

`RuntimeExecutionSubject` supports DecisionPipeline, DecisionPackage, and internal opaque resource
references. It binds exact version, tenant, organization, classification, lineage, and creation
time without loading or mutating the subject.

## 12. Execution request

`RuntimeExecutionRequest` binds the subject, requester, optional agent and represented user,
resource, action, purpose, risk, classification, environment, optional model/provider/tool/
connector/destination selectors, limits, revisions, lineage, and timestamp. It contains no
payload, prompt, output, token, secret, or arbitrary metadata map.

## 13. Authority context

`RuntimeAuthorityContext` repeats the exact request scope for fail-closed comparison. It cannot
broaden identity, selectors, revisions, lineage, destination, or classification.

## 14. Review references

Required, requested, completed, waived, and cancelled review states have explicit external
request, result, or waiver requirements. CP1 issues no approvals.

## 15. Approval references

Required, requested, granted, denied, revoked, and expired states retain external facts with
explicit validity and revocation metadata. CP1 issues no approvals.

## 16. Authorization references

Authorization references retain external requests/decisions, policy decision identity, policy and
authorization revisions, validity, expiry, and revocation. CP1 issues no authorizations.

## 17. Bounded permit references

Permit snapshots bind source, external ID, actor/agent, resource, action, purpose, risk,
classification ceiling, environment, optional destinations and provider selectors, validity,
invocation/attempt limits, revisions, and lineage. CP1 issues no permits.

## 18. Revocation references

Revocations are immutable metadata tied to an exact approval, authorization, or permit reference.
No revocation operation or cancellation occurs.

## 19. Admission decisions

ADMITTED, DENIED, NOT_APPLICABLE, and INVALIDATED decisions retain exact references and bounded
reasons. ADMITTED requires compatible active permit metadata and no denial reasons. DENIED
requires reasons. Invalidation preserves a distinct original identity. CP1 performs no admission
service runtime.

## 20. Authority bundles

Bundles bind one exact request, context, canonical reference sets, decision, revisions, lineage,
classification, audit metadata, and creation time. Pure validation returns the caller-supplied
immutable bundle unchanged.

## 21. Classification

`DataClassification` is reused. Every classification is explicit; there is no PUBLIC default.
Request, context, references, decision, bundle, and audit metadata cannot downgrade their source.
A permit ceiling must cover the request classification.

## 22. Tenant, organization, actor, and agent isolation

Exact tenant and organization identities apply throughout. Requester actor, optional agent, and
represented user remain distinct. Cross-scope substitution fails closed.

## 23. Selectors and bounded scope

Resource, action, purpose, risk, environment, destination, model, provider, tool, and connector
selectors are bounded typed fields, never arbitrary dictionaries. Omitted optional selectors
cannot later be inferred.

## 24. Invocation and attempt limits

Requested and permitted counts use strict bounded integers; booleans are rejected. Remaining
counts cannot exceed maxima and must cover an admitted request.

## 25. Time windows and expiry

All timestamps are caller supplied and timezone aware. CP1 accepts no pre-existing authority:
references and permit validity cannot predate the request. Validity and expiry ordering is checked
without a current-time lookup. ACTIVE is a caller-supplied evaluated status, not a hidden-clock
calculation.

## 26. Lineage and revisions

Root lineage identity/digest and policy, authorization, and registry revisions propagate exactly.
No digest, lineage, revision, or identifier is generated or normalized.

## 27. Canonical ordering

Review, approval, authorization, permit, revocation, decision-reference, and denial-reason tuples
must already be unique and sorted by their documented identity/value. Validation never sorts,
deduplicates, repairs, or silently drops input.

## 28. Audit metadata

Audit metadata contains caller-supplied exact counts and scope only. Validators compare counts
without emitting an event, persisting a record, or computing statistics.

## 29. Determinism and immutability

Models are strict, frozen, and extra-forbidden. IDs, timestamps, versions, status, bounds, and
facts are caller supplied. There are no defaults that generate identity, hidden clocks,
randomness, hashes, mutable globals, I/O, or arbitrary metadata maps.

## 30. Security and privacy

No credentials, tokens, secrets, raw prompts, model outputs, source content, provider payloads,
or chain-of-thought are stored. CP1 executes nothing and makes no model, provider, MCP, connector,
network, filesystem, database, environment, or credential-broker call.

## 31. Consequences

Callers must provide verbose, internally consistent authority facts. Future planning gains an
inspectable admission boundary without receiving authority issuance or execution behavior.

## 32. Deferred CP2+ scope

Planning, execution state, orchestration, adapters, permit revalidation services, persistence,
migrations, API, queue, worker, scheduler, outbox, telemetry, dashboard, credential resolution,
and external invocation are deferred. No persistence, API, queue, worker, scheduler, or external
call exists in CP1.

## 33. Alternatives considered

Importing concrete MCP/zero-trust permits was rejected because their specialized boundaries must
remain authoritative. Copying token material was rejected. Generating admission from policy was
rejected because CP1 is metadata-only. Reusing `app.execution` was rejected due its existing
runtime semantics. Arbitrary selector dictionaries, inferred classification, pre-existing
authority, mutable bundles, auto-sorting, hidden time evaluation, and Sprint 14 modification were
also rejected.

CP1 issues no approvals. CP1 issues no authorizations. CP1 issues no permits. CP1 performs no
admission service runtime. CP1 executes nothing. Review is not approval. Approval is not
authorization. Authorization is not permit. Permit is not execution. Admission is not execution.
