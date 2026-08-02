# Sprint 15 Runtime Architecture Rules

This document is normative. `MUST`, `MUST NOT`, `SHOULD`, and `MAY` have their ordinary
requirements meaning. ADR-065 through ADR-072 provide the rationale.

## 1. Dependency direction

Runtime MUST remain downstream of Sprint 14. Sprint 14, evaluation, observability, zero-trust,
and MCP-governance packages MUST NOT import `app.runtime`. Runtime domain contracts MUST NOT
import infrastructure implementations.

## 2. Authority separation

Review, approval, authorization, permit, admission, execution state, and result MUST remain
distinct. Runtime MUST NOT combine approval, authorization, permit, and execution state.

## 3. Permit requirements

Runtime MUST NOT execute from DecisionPipeline possession alone. Runtime MUST NOT treat ReleaseGate as a permit. Every side effect MUST have an exact bounded, unexpired, unrevoked permit,
and runtime MUST validate permit immediately before side effects. Specialized MCP and repository
permits MUST be reused and MUST NOT be replaced by broader runtime permits.

## 4. Action registry requirements

Runtime MUST use registry-defined actions bound to an immutable action version and registry
revision. Unknown actions and revisions MUST fail closed. Registries MUST NOT contain arbitrary
callbacks or executable dynamic imports and execute nothing.

## 5. Adapter restrictions

Adapters MUST NOT decide policy, issue permits, widen scope, mutate Sprint 14 records, or own API
responses. Adapters MAY execute only a validated invocation envelope. Fake and dry-run adapters
MUST precede real external adapters.

## 6. Orchestrator restrictions

The orchestrator MUST NOT call external systems directly. It MUST request explicit authority and
state decisions, use ports, and MUST NOT invent approvals, authorizations, permits, transitions,
retries, or results.

## 7. State-machine rules

State changes MUST use explicit transition requests, decisions, and append-only records with
optimistic revisions. No state progresses automatically. Execution state MUST NOT include
APPROVED, AUTHORIZED, or PERMITTED. Terminal history MUST be preserved.

## 8. Planning rules

Plans MUST bind exact admitted request, DecisionPipeline reference, actions, registry revision,
schemas, dependencies, destinations, authority scope, retries, timeouts, and compensation.
Planning MUST NOT perform I/O, call tools, issue permits, or expand authority.

## 9. Dry-run rules

Dry run MUST perform no side effects and MUST NOT create authority. Dry-run success MUST NOT be
treated as later admission, permit validity, or execution success.

## 10. Idempotency rules

Writes MUST require tenant-, organization-, action-, request-, step-, and revision-scoped
idempotency. Successful effects MUST NOT be silently repeated. Mismatched key reuse MUST fail
closed.

## 11. Retry rules

Retries MUST be bounded, explicit, and limited to registered retryable errors and eligible
actions. Each attempt MUST revalidate authority and permit. Publication, deployment, destructive,
quarantine, and security-control actions MUST NOT retry automatically.

## 12. Cancellation rules

Cancellation MUST be a distinct registered action and state transition. Cancellation is not
rollback and MUST NOT erase completed effects or audit.

## 13. Compensation rules

Compensation MUST be a separately registered action with its own authorization and permit.
Compensation is not guaranteed rollback; its failure MUST be recorded independently. Runtime MUST
treat cancellation and compensation separately.

## 14. Audit restrictions

Runtime MUST audit every side effect and authority-relevant transition using append-only safe
metadata. Audit MUST NOT issue authority or claim correctness.

## 15. Persistence restrictions

Repositories MUST NOT make policy decisions, issue permits, choose actions, or advance states.
State, audit, idempotency, and outbox changes SHOULD be locally atomic. External effects MUST be
reconciled rather than claimed transactionally atomic with storage.

## 16. API restrictions

APIs MUST authenticate callers, validate transport schemas, and call the runtime application
boundary. APIs MUST NOT own authority, call adapters, mutate state directly, or expose secrets and
unrestricted provider payloads.

## 17. Worker restrictions

Workers MUST consume only persisted governed work, revalidate scope and permit, use the
orchestrator/ports boundary, and record attempts. Workers MUST NOT infer missing policy or bypass
tenant isolation.

## 18. Classification propagation

Runtime MUST NOT lower classification. Plans, transitions, audit, outbox, invocations, and results
MUST retain an equal or more restrictive classification than every source.

## 19. Tenant and organization isolation

Every request, decision, permit, plan, state, action, adapter invocation, audit event, repository
operation, and result MUST bind exact tenant and organization. Runtime MUST NOT cross tenant or organization boundaries or use global fallback identity.

## 20. Lineage and provenance preservation

Runtime MUST preserve caller-supplied Sprint 14 lineage and provenance references exactly. It
MUST NOT generate substitute lineage, dereference provenance without authority, or treat either
as proof of correctness.

## 21. Credential handling

Credentials MUST resolve only at the execution boundary from tenant-scoped broker references.
Runtime MUST NOT persist secrets, raw tokens, credentials, or credential-derived identifiers.

## 22. Sensitive-content restrictions

Domain, plan, state, audit, permit, result, and outbox records MUST NOT contain raw prompts, raw
model outputs, source-document bodies, provider payloads, secrets, tokens, or chain-of-thought.

## 23. Runtime versioning

Runtime action, registry, plan, schema, policy, adapter, and permit versions MUST be explicit and
independent of the project release version, Sprint number, migration revision, and Git tag. No
runtime version MAY be inferred automatically.

## 24. Sprint 14 compatibility

Runtime MUST preserve Sprint 14 contracts unchanged. DecisionPipeline remains metadata, and
ReleaseGate remains inert governance metadata. Compatibility bridges MUST live downstream and
MUST fail closed on unsupported versions.

## 25. ADR compliance

Future Sprint 15 checkpoints MUST cite ADR-065 through ADR-072, keep their public changes within
the selected layer, and add focused dependency and security tests. A contradictory design requires
a superseding ADR before implementation.

## 26. Stop conditions for future checkpoints

Implementation MUST stop for a required Sprint 14 contract change, reverse dependency, combined
authority/state model, unbounded permit or retry, adapter policy decision, unclear tenant scope,
classification downgrade, secret persistence, arbitrary action execution, missing idempotency for
writes, non-reconcilable external effect, or architecture that cannot be decided without silently
granting authority.


