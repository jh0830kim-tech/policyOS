# ADR-035: Secretary Work Product Integration Boundary

## Status

Accepted for Sprint 10 Checkpoint 5.

## Context

CP1 translates a Sprint 9 CoordinationPlan into exact specialist assignments. CP4 collects one
immutable AgentWorkProduct from each successful assignment execution. CP5 needs to arrange those
products into one internal integration package without turning the Secretary role into a provider,
model, specialist, reviewer, or publisher.

Sprint 9 NarrativeDraft models generated narrative claims and citation uses and is therefore not
reused as the CP5 result. CP5 performs structural composition only. Existing coordination,
work-product, evidence, citation, tenant, classification, and review contracts remain authoritative.

## Decision

Add integration.py and integration_errors.py under app.orchestration. SecretaryIntegrationRequest
consumes CP4 collection results and optional explicit typed conflict declarations. A trusted context
binds the integration and coordination identities, tenant, exact classification, purpose,
authorized Secretary actor, and caller-supplied integration timestamp.

The Secretary is an orchestration role, not a provider or model. Integration verifies every CP4
runtime is SUCCEEDED and validates product, assignment-request, execution, task, role, output type,
tenant, classification, reference, and coordination lineage. Secretary products, unsupported
tasks, duplicate work-product identities, and multiple products for one assignment are rejected.

Products are ordered by the CoordinationPlan topological task order. Each section preserves source
content verbatim and carries its product, assignment, task, specialist role, evidence, citation,
and review lineage. No facts, transitions, conclusions, recommendations, evidence, or citations are
generated.

Missing required products and unresolved dependencies are blocking structural gaps and yield
INCOMPLETE. Allowed optional omissions are recorded without placeholders and are non-blocking.
Preserved human-review requirements and explicit supported conflicts yield NEEDS_REVIEW. A result
is READY only when required coverage is complete and no review or conflict remains. READY means
structurally ready for the next internal boundary, not approved or publishable.

Conflicts are accepted only as explicit typed declarations tied to known source products. CP5 does
not perform semantic similarity, contradiction detection, truth selection, or adjudication.
Structural gaps do not redispatch work. All contracts are frozen, extra-forbidden, bounded, and
deterministic, and all identifiers and timestamps are supplied by the caller.

## Consequences and limitations

The integration package is an internal manifest, not a final policy document. CP5 does not invoke a
provider or model, execute new research, approve, publish, persist, retry, fall back, score,
cross-validate, or emit telemetry. Conflicts require upstream typed declarations because free-text
semantic comparison is deliberately outside this deterministic boundary.

CP6 owns human approval and publication. Sprint 11 owns model selection, Sprint 12 owns independent
cross-validation, and Sprint 13 owns evaluation and observability. ADR-032 remains reserved for the
proposed multi-model extension.
