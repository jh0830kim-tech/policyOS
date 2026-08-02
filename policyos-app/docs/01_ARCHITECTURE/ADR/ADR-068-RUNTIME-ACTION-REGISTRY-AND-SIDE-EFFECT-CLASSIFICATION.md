# ADR-068: Runtime Action Registry and Side-Effect Classification

## Status

Accepted for Sprint 15 CP0.

## Contracts and ownership

`app.runtime.registry` will define `RuntimeActionDefinition`, `RuntimeActionVersion`,
`RuntimeActionCapability`, `RuntimeActionInputSchemaReference`,
`RuntimeActionOutputSchemaReference`, `RuntimeActionRiskProfile`,
`RuntimeActionSideEffectLevel`, and `RuntimeActionAdapterReference`. Actions have closed stable
identity, explicit version, immutable registry snapshot/revision, exact schema references,
capabilities, risk profile, permit rules, destination rules, idempotency requirements, retry and
compensation eligibility, and an adapter binding.

The side-effect levels are `NONE`, `READ_ONLY`, `INTERNAL_WRITE`, `EXTERNAL_WRITE`, `PUBLICATION`,
`EXTERNAL_TRANSMISSION`, `DEPLOYMENT`, `DESTRUCTIVE`, `SECURITY_CONTROL`, and
`QUARANTINE_ACTION`. Side-effect level controls required governance but does not itself grant a
permit.

## Resolution and safety

Planning binds an exact action ID/version and snapshot revision. Orchestration resolves only that
binding and verifies capability, schemas, destination, risk, authority, and permit requirements.
Unknown, disabled, substituted, or revision-mismatched actions fail closed. The registry declares
actions but executes nothing. Adapter selection does not authorize execution.

Registrations contain no arbitrary callback or executable import path. Dynamic Python import
execution is prohibited. Adapters cannot self-register at runtime without a separately governed,
versioned registry change. Registry records contain references rather than credentials or raw
schemas.

## Consequences

All executable behavior is enumerable and reviewable. Adding or rebinding an action is a governed
registry revision, not a deployment-time discovery side effect.
