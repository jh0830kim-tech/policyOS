# ADR-036: Human Approval Boundary for Secretary Integration Results

## Status

Accepted for Sprint 10 Checkpoint 6.

## Context

ADR-035 creates immutable Secretary integration packages with READY, INCOMPLETE, and NEEDS_REVIEW
semantics. READY describes structural completeness only. It is not evidence of human intent and
must never become approval automatically. The repository's RBAC checks are owned by API and service
boundaries backed by memberships, roles, and permission keys; orchestration should not import those
persistence models.

## Decision

Add approval.py and approval_errors.py under app.orchestration. A request binds one approval request
to the exact integration, coordination, tenant, classification, integration status, integration
timestamp, and ordered source-product lineage. A trusted context carries an immutable authorization
evidence snapshot created by the RBAC-owning boundary, including actor identity, human actor kind,
tenant, classification, and the orchestration.secretary_integration.approve permission.

Only an explicitly supplied authorized human decision creates an approval record. APPROVED,
REJECTED, and CHANGES_REQUESTED are separate immutable decisions. Rejection and changes requested
require bounded rationale and do not mark execution or integration as technically failed, rewrite
content, dispatch revision work, or invoke any provider.

APPROVED requires an exact READY integration with no blocking conflicts, blocking gaps, or unresolved
mandatory review identities. INCOMPLETE and NEEDS_REVIEW cannot be approved directly. They may be
rejected or returned for changes. A later review-completion boundary would need to produce a newly
eligible integration state; CP6 does not reinterpret NEEDS_REVIEW.

Separation of duties is conservative: the approver must differ from the Secretary actor and approval
requester, must not be among the trusted specialist producer identities, must be human, and must
hold the required permission. This adds no organizational hierarchy or identity store.

Acknowledgements are canonical typed identities and must belong to the exact integration conflicts,
gaps, or review requirements. Duplicate record IDs, decision IDs, and repeat decisions for an
explicitly supplied prior request record are rejected. No hidden registry or persistence is used.

The CP5 integration result remains unchanged. Approval status belongs only to the immutable approval
record. Approval means an authorized human accepted the exact internal integration package; it does
not perform external release, transmission, filing, submission, or document generation.

## Consequences and limitations

The RBAC-owning caller is responsible for constructing trustworthy authorization evidence and for
supplying prior records when duplicate detection is required across calls. Durable decision
uniqueness and audit storage are outside this in-memory checkpoint.

CP6 performs no content generation, conflict resolution, automatic approval, redispatch, provider
or model invocation, persistence, notification, retry, fallback, telemetry, evaluation, or
cross-validation. External release remains a separate future boundary. Sprint 11 owns model
selection, Sprint 12 owns cross-validation, and Sprint 13 owns evaluation and observability.
ADR-032 remains reserved for the proposed multi-model extension.
