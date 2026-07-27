# ADR-034: Specialist Work Product Collection Boundary

## Status

Accepted for Sprint 10 Checkpoint 4.

## Context

CP1 defines exact specialist assignment output specifications, CP2 owns the immutable assignment
runtime lifecycle, and CP3 accepts dispatch before moving an assignment to RUNNING. CP4 must accept
one normalized completion and create one specialist work product without learning provider schemas
or performing Secretary synthesis. Sprint 8 ExecutionResult remains available, but its general JSON
output and execution metrics are broader than this boundary needs. Sprint 9 already owns
AgentWorkProduct, WorkProductType, source references, evidence and citation identities, and the
grounding, narrative, and reflection layers.

## Decision

Add a narrow immutable AssignmentExecutionCompletionInput and immutable collection
request, context, and result contracts in app.orchestration.collection. The completion carries exact
execution, request, assignment, task, step, dispatch, tenant, classification, specialist role,
work-product type, completion time, normalized text, and canonical typed references. It has no
provider or model identity, SDK object, raw response, exception, prompt, token or cost data, or
arbitrary metadata.

Reuse and minimally complete Sprint 9 AgentWorkProduct instead of defining a competing work product
or type enum. The product preserves assignment-request, task, execution, and immutable content
lineage in addition to its existing delegation, agent, role, type, status, references, source IDs,
tenant, classification, review requirement, and completion time. Grounding, narrative validation,
reflection, and quality decisions remain owned by Sprint 9. CP4 never fabricates grounded,
verified, reflected, approved, or publication-ready state.

Collection requires the exact CP1 output type and specialist role. Trusted context is checked
against the CP1 request and binding, CP2 RUNNING attempt-one record, runtime context, and accepted
CP3 receipt. Tenant and classification match exactly. References are canonical, bounded,
same-tenant, same-classification, and tied to the source execution. Human-review requirements are
preserved as NEEDS_HUMAN_REVIEW; otherwise the product is PREPARED. Secretary targets and rejected
dispatches cannot be collected.

Only after every validation and product construction succeeds does CP4 call CP2
succeed_assignment_execution. It never assigns runtime status directly. Validation rejection
constructs no product, does not mark success, does not fabricate failure, and leaves the immutable
RUNNING input unchanged. Explicit execution failure continues through CP2 fail_assignment_execution.
A later attempt against SUCCEEDED is rejected as a duplicate; there is no persistence registry.

All identifiers and timestamps are caller supplied. Ordering and validation are deterministic;
contracts are frozen and extra-forbidden. Completion and work-product construction remain separate
because transport completion and accepted governed specialist state are distinct.

## Consequences and limitations

CP4 collects exactly one product from one specialist assignment. It does not aggregate, synthesize
a Secretary answer, approve, publish, persist, retry, fall back, score, cross-validate, or emit
telemetry. Reference existence is bounded to typed source-execution lineage available at this
in-memory boundary; durable catalog validation remains outside CP4.

CP5 Secretary integration and CP6 human approval remain deferred. External publication is a
separate later boundary. Sprint 11 owns model and provider selection, Sprint 12 owns
cross-validation, and Sprint 13 owns evaluation and observability. ADR-032 remains reserved for the
proposed multi-model extension boundary.
