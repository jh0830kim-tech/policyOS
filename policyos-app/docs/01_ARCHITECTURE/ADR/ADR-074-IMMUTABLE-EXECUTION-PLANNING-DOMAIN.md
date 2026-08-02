# ADR-074: Immutable Execution Planning Domain

## 1. Context

Sprint 15 CP2 requires an immutable, metadata-only plan between admitted runtime authority and future execution state. A plan must never execute work.

## 2. CP0 and CP1 dependencies

This decision implements ADR-065 through ADR-072 and consumes ADR-073 authority contracts unchanged.

## 3. Package placement

Contracts live in `app.runtime.planning`. Sprint 14 packages and `app.runtime.authority` do not import planning.

## 4. Existing planning compatibility

`app.execution.plan` remains a separate existing concern and is not modified or reinterpreted by CP2.

## 5. DecisionPipeline binding

Every recorded plan binds the exact caller-supplied `DecisionPipeline` identity and version represented by the authority subject.

## 6. Authority binding

Every recorded plan binds one exact immutable `RuntimeAuthorityBundle`, execution request, and admission decision.

## 7. Admission requirement

Recorded and validated plans require admitted authority. Possession of a DecisionPipeline or ReleaseGate is insufficient.

## 8. Plan modes

Validation-only, dry-run, and execution modes are explicit metadata. None performs execution.

## 9. Plan lifecycle

Draft, recorded, validated, unavailable, cancelled, and invalidated states are immutable records, not mutable transitions.

## 10. Step lifecycle

Declared, unavailable, cancelled, and invalidated step states are explicit and non-executable.

## 11. Action references

Actions are opaque governed references with exact version, registry revision, schemas, selectors, risk, and side-effect classification reference.

## 12. No action registry runtime

CP2 creates no registry package, lookup service, dynamic loader, callable resolution, or action implementation.

## 13. No adapters

Adapter identifiers are opaque strings. CP2 imports or invokes no adapter, connector, provider, model, tool, or external system.

## 14. Steps

Steps bind one action reference, exact authority references, ordered metadata references, scope, lineage, revisions, and recording time.

## 15. Dependencies

Dependencies are immutable directed metadata edges. Self, orphaned, duplicate, reversed, and cyclic relationships fail closed.

## 16. Input bindings

Inputs are references only. Prior-step inputs must identify an earlier known step and contain no payload.

## 17. Output bindings

Outputs are schema and destination references only. They store no result and broaden no authorized destination.

## 18. Retry policy

Retries are bounded metadata. Attempt counts cannot exceed admitted authority, and high-risk retries require explicit external governance.

## 19. Timeout policy

Timeouts are local bounded durations or opaque external-policy references. CP2 starts no timer or cancellation process.

## 20. Compensation

Compensation is none, manual metadata, or a separately governed action reference with explicit permit and authorization references.

## 21. No implicit compensation authority

Original action authority never authorizes compensation implicitly. CP2 invokes no compensating work.

## 22. Validation records

Validation is an immutable record. A valid record covers the exact plan component sets and exact authority bundle.

## 23. Audit metadata

Audit metadata contains bounded counts, scope, revisions, classification, and time. It contains no event transport or persistence behavior.

## 24. Tenant and organization isolation

Plan and component tenant and organization values must exactly match authority; cross-boundary planning fails closed.

## 25. Classification monotonicity

Plans and components may retain or raise classification but must never lower it.

## 26. Lineage

Plan, pipeline, authority, steps, bindings, validation, and audit preserve exact root lineage and digest references where applicable.

## 27. Revision pinning

Policy, authorization, and registry revisions remain caller-supplied and exact; CP2 performs no policy or registry evaluation.

## 28. Time ordering

Plans cannot predate their pipeline or authority. Components cannot postdate plan recording, and validation cannot predate the plan.

## 29. Determinism

Sequences and reference collections are canonical, unique, and caller supplied. CP2 performs no hidden discovery or enrichment.

## 30. Immutability and strictness

All contracts are frozen, reject unknown fields, reject coercive invalid values, and expose pure validation/build functions.

## 31. Explicit exclusions

CP2 adds no state machine, orchestration, dispatch, persistence, transaction, outbox, API, worker, scheduler, callback, credential, network, filesystem, or side effect.

## 32. Consequences

Future CP3+ layers may consume only validated immutable plan metadata and must separately revalidate authority immediately before side effects. Sprint 14 and CP1 contracts remain unchanged.
