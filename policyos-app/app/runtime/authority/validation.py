"""Pure fail-closed validation for Runtime Authority contracts."""

from collections.abc import Iterable

from app.runtime.authority._base import canonical, not_lower
from app.runtime.authority.domain import (
    RuntimeApprovalReference,
    RuntimeApprovalStatus,
    RuntimeAuthorityContext,
    RuntimeAuthorizationReference,
    RuntimeAuthorizationStatus,
    RuntimeExecutionRequest,
    RuntimeExecutionSubject,
    RuntimePermitStatus,
    RuntimeReviewReference,
)
from app.runtime.authority.errors import (
    DuplicateRuntimeAuthorityReferenceError,
    OrphanRuntimeAuthorityReferenceError,
    RuntimeAdmissionDecisionError,
    RuntimeApprovalReferenceError,
    RuntimeAuthorityAuditMetadataError,
    RuntimeAuthorityBundleError,
    RuntimeAuthorityClassificationError,
    RuntimeAuthorityContextError,
    RuntimeAuthorityOrderingError,
    RuntimeAuthorityOrganizationError,
    RuntimeAuthorityRevocationError,
    RuntimeAuthorityScopeError,
    RuntimeAuthorityTenantError,
    RuntimeAuthorityTimestampError,
    RuntimeAuthorizationReferenceError,
    RuntimeExecutionSubjectError,
    RuntimePermitReferenceError,
)
from app.runtime.authority.references import (
    RuntimeAdmissionDecision,
    RuntimeAuthorityAuditMetadata,
    RuntimeAuthorityBundle,
    RuntimeAuthorityReferenceType,
    RuntimeAuthorityRevocationReference,
    RuntimePermitReference,
)


def validate_runtime_execution_subject(
    subject: RuntimeExecutionSubject,
) -> RuntimeExecutionSubject:
    if subject.tenant_id == subject.organization_id:
        raise RuntimeExecutionSubjectError("subject tenant and organization identities must differ")
    return subject


def validate_runtime_execution_request(
    request: RuntimeExecutionRequest,
) -> RuntimeExecutionRequest:
    subject = validate_runtime_execution_subject(request.execution_subject)
    if request.tenant_id != subject.tenant_id:
        raise RuntimeAuthorityTenantError("execution request tenant does not match subject")
    if request.organization_id != subject.organization_id:
        raise RuntimeAuthorityOrganizationError(
            "execution request organization does not match subject"
        )
    if not not_lower(request.classification, subject.classification):
        raise RuntimeAuthorityClassificationError("execution request classification is too low")
    if request.requested_at < subject.created_at:
        raise RuntimeAuthorityTimestampError("execution request predates subject")
    return request


def validate_runtime_authority_context(
    context: RuntimeAuthorityContext,
    request: RuntimeExecutionRequest,
) -> RuntimeAuthorityContext:
    validate_runtime_execution_request(request)
    expected = _request_scope(request)
    actual = _context_scope(context)
    if actual != expected:
        raise RuntimeAuthorityContextError("authority context does not match exact request scope")
    if context.runtime_execution_request_id != request.runtime_execution_request_id:
        raise RuntimeAuthorityContextError("authority context request identity mismatch")
    if context.created_at < request.requested_at:
        raise RuntimeAuthorityTimestampError("authority context predates request")
    if not not_lower(context.classification, request.classification):
        raise RuntimeAuthorityClassificationError("authority context classification is too low")
    return context


def validate_runtime_review_reference(
    reference: RuntimeReviewReference,
    request: RuntimeExecutionRequest,
) -> RuntimeReviewReference:
    _validate_common_reference(reference, request, "review")
    return reference


def validate_runtime_approval_reference(
    reference: RuntimeApprovalReference,
    request: RuntimeExecutionRequest,
) -> RuntimeApprovalReference:
    _validate_common_reference(reference, request, "approval")
    if reference.approval_status is RuntimeApprovalStatus.GRANTED and reference.valid_from is None:
        raise RuntimeApprovalReferenceError("granted approval requires valid_from")
    return reference


def validate_runtime_authorization_reference(
    reference: RuntimeAuthorizationReference,
    request: RuntimeExecutionRequest,
) -> RuntimeAuthorizationReference:
    _validate_common_reference(reference, request, "authorization")
    if reference.authorization_revision != request.authorization_revision:
        raise RuntimeAuthorizationReferenceError("authorization revision mismatch")
    if (
        reference.authorization_status is RuntimeAuthorizationStatus.GRANTED
        and reference.valid_from is None
    ):
        raise RuntimeAuthorizationReferenceError("granted authorization requires valid_from")
    return reference


def validate_runtime_permit_reference(
    reference: RuntimePermitReference,
    request: RuntimeExecutionRequest,
) -> RuntimePermitReference:
    _validate_common_reference(reference, request, "permit")
    expected = (
        request.requester_actor_id,
        request.requester_agent_instance_id,
        request.resource_reference,
        request.action,
        request.purpose,
        request.risk_level,
        request.execution_environment,
        request.model_id,
        request.provider_id,
        request.tool_id,
        request.connector_id,
        request.destination_reference,
        request.policy_revision,
        request.authorization_revision,
        request.registry_revision,
        request.lineage_id,
        request.lineage_digest_reference,
    )
    actual = (
        reference.actor_id,
        reference.agent_instance_id,
        reference.resource_reference,
        reference.action,
        reference.purpose,
        reference.risk_level,
        reference.execution_environment,
        reference.model_id,
        reference.provider_id,
        reference.tool_id,
        reference.connector_id,
        reference.destination_reference,
        reference.policy_revision,
        reference.authorization_revision,
        reference.registry_revision,
        reference.permit_lineage_id,
        reference.permit_lineage_digest_reference,
    )
    if actual != expected:
        raise RuntimePermitReferenceError("permit does not match exact request scope")
    if not not_lower(reference.classification_ceiling, request.classification):
        raise RuntimeAuthorityClassificationError("permit classification ceiling is too low")
    if reference.valid_from < request.requested_at or reference.created_at < request.requested_at:
        raise RuntimeAuthorityTimestampError("permit predates request")
    if reference.maximum_invocations < request.requested_invocation_count:
        raise RuntimePermitReferenceError("permit invocation limit is insufficient")
    if reference.maximum_attempts < request.requested_attempt_count:
        raise RuntimePermitReferenceError("permit attempt limit is insufficient")
    if reference.remaining_invocations < request.requested_invocation_count:
        raise RuntimePermitReferenceError("remaining permit invocations are insufficient")
    if reference.remaining_attempts < request.requested_attempt_count:
        raise RuntimePermitReferenceError("remaining permit attempts are insufficient")
    return reference


def validate_runtime_authority_revocation_reference(
    reference: RuntimeAuthorityRevocationReference,
    request: RuntimeExecutionRequest,
) -> RuntimeAuthorityRevocationReference:
    if reference.tenant_id != request.tenant_id:
        raise RuntimeAuthorityTenantError("revocation tenant mismatch")
    if reference.organization_id != request.organization_id:
        raise RuntimeAuthorityOrganizationError("revocation organization mismatch")
    if reference.policy_revision != request.policy_revision:
        raise RuntimeAuthorityRevocationError("revocation policy revision mismatch")
    if not not_lower(reference.classification, request.classification):
        raise RuntimeAuthorityClassificationError("revocation classification is too low")
    if reference.revoked_at < request.requested_at:
        raise RuntimeAuthorityTimestampError("revocation predates request")
    return reference


def validate_runtime_admission_decision(
    decision: RuntimeAdmissionDecision,
    request: RuntimeExecutionRequest,
    context: RuntimeAuthorityContext,
    reviews: tuple[RuntimeReviewReference, ...] = (),
    approvals: tuple[RuntimeApprovalReference, ...] = (),
    authorizations: tuple[RuntimeAuthorizationReference, ...] = (),
    permits: tuple[RuntimePermitReference, ...] = (),
) -> RuntimeAdmissionDecision:
    validate_runtime_authority_context(context, request)
    if decision.runtime_execution_request_id != request.runtime_execution_request_id:
        raise RuntimeAdmissionDecisionError("admission request identity mismatch")
    if decision.runtime_authority_context_id != context.runtime_authority_context_id:
        raise RuntimeAdmissionDecisionError("admission context identity mismatch")
    expected = (
        request.requester_actor_id,
        request.requester_agent_instance_id,
        request.tenant_id,
        request.organization_id,
        request.policy_revision,
        request.authorization_revision,
        request.registry_revision,
        request.lineage_id,
        request.lineage_digest_reference,
    )
    actual = (
        decision.actor_id,
        decision.agent_instance_id,
        decision.tenant_id,
        decision.organization_id,
        decision.policy_revision,
        decision.authorization_revision,
        decision.registry_revision,
        decision.root_lineage_id,
        decision.root_lineage_digest_reference,
    )
    if actual != expected:
        raise RuntimeAdmissionDecisionError("admission scope does not match request")
    if not not_lower(decision.classification, request.classification):
        raise RuntimeAuthorityClassificationError("admission classification is too low")
    if decision.decided_at < request.requested_at:
        raise RuntimeAuthorityTimestampError("admission predates request")
    supplied = (
        (decision.review_reference_ids, tuple(x.runtime_review_reference_id for x in reviews)),
        (
            decision.approval_reference_ids,
            tuple(x.runtime_approval_reference_id for x in approvals),
        ),
        (
            decision.authorization_reference_ids,
            tuple(x.runtime_authorization_reference_id for x in authorizations),
        ),
        (decision.permit_reference_ids, tuple(x.runtime_permit_reference_id for x in permits)),
    )
    if any(recorded != actual_ids for recorded, actual_ids in supplied):
        raise OrphanRuntimeAuthorityReferenceError("admission reference set mismatch")
    if decision.decision_status.value == "admitted":
        if any(item.permit_status is not RuntimePermitStatus.ACTIVE for item in permits):
            raise RuntimeAdmissionDecisionError("admission requires active permit references")
        for item in permits:
            validate_runtime_permit_reference(item, request)
    return decision


def validate_runtime_authority_audit_metadata(
    metadata: RuntimeAuthorityAuditMetadata,
    bundle: RuntimeAuthorityBundle,
) -> RuntimeAuthorityAuditMetadata:
    permits = bundle.permit_references
    expected = (
        bundle.runtime_authority_bundle_id,
        len(bundle.review_references),
        len(bundle.approval_references),
        len(bundle.authorization_references),
        len(permits),
        len([item for item in permits if item.permit_status is RuntimePermitStatus.ACTIVE]),
        len([item for item in permits if item.permit_status is RuntimePermitStatus.REVOKED]),
        len([item for item in permits if item.permit_status is RuntimePermitStatus.EXPIRED]),
        len(bundle.admission_decision.denial_reason_codes),
        len(bundle.revocation_references),
        bundle.tenant_id,
        bundle.organization_id,
        bundle.policy_revision,
        bundle.registry_revision,
    )
    actual = (
        metadata.runtime_authority_bundle_id,
        metadata.review_reference_count,
        metadata.approval_reference_count,
        metadata.authorization_reference_count,
        metadata.permit_reference_count,
        metadata.active_permit_count,
        metadata.revoked_permit_count,
        metadata.expired_permit_count,
        metadata.denial_reason_count,
        metadata.revocation_reference_count,
        metadata.tenant_id,
        metadata.organization_id,
        metadata.policy_revision,
        metadata.registry_revision,
    )
    if actual != expected:
        raise RuntimeAuthorityAuditMetadataError("authority audit metadata does not match bundle")
    if not not_lower(metadata.classification, bundle.classification):
        raise RuntimeAuthorityClassificationError("audit classification is too low")
    if metadata.created_at < bundle.created_at:
        raise RuntimeAuthorityTimestampError("audit metadata predates bundle")
    return metadata


def validate_runtime_authority_bundle(bundle: RuntimeAuthorityBundle) -> RuntimeAuthorityBundle:
    request = validate_runtime_execution_request(bundle.execution_request)
    validate_runtime_authority_context(bundle.authority_context, request)
    _validate_bundle_ordering(bundle)
    for item in bundle.review_references:
        validate_runtime_review_reference(item, request)
    for item in bundle.approval_references:
        validate_runtime_approval_reference(item, request)
    for item in bundle.authorization_references:
        validate_runtime_authorization_reference(item, request)
    for item in bundle.permit_references:
        validate_runtime_permit_reference(item, request)
    for item in bundle.revocation_references:
        validate_runtime_authority_revocation_reference(item, request)
    validate_runtime_admission_decision(
        bundle.admission_decision,
        request,
        bundle.authority_context,
        bundle.review_references,
        bundle.approval_references,
        bundle.authorization_references,
        bundle.permit_references,
    )
    expected = (
        request.tenant_id,
        request.organization_id,
        request.policy_revision,
        request.authorization_revision,
        request.registry_revision,
        request.lineage_id,
        request.lineage_digest_reference,
    )
    actual = (
        bundle.tenant_id,
        bundle.organization_id,
        bundle.policy_revision,
        bundle.authorization_revision,
        bundle.registry_revision,
        bundle.root_lineage_id,
        bundle.root_lineage_digest_reference,
    )
    if actual != expected:
        raise RuntimeAuthorityBundleError("bundle scope does not match request")
    nested_classifications = (
        request.classification,
        bundle.authority_context.classification,
        bundle.admission_decision.classification,
        *(item.classification for item in bundle.review_references),
        *(item.classification for item in bundle.approval_references),
        *(item.classification for item in bundle.authorization_references),
        *(item.classification_ceiling for item in bundle.permit_references),
        *(item.classification for item in bundle.revocation_references),
    )
    if any(not not_lower(bundle.classification, item) for item in nested_classifications):
        raise RuntimeAuthorityClassificationError("bundle classification is too low")
    nested_times = (
        request.requested_at,
        bundle.authority_context.created_at,
        bundle.admission_decision.decided_at,
        *(item.created_at for item in bundle.review_references),
        *(item.created_at for item in bundle.approval_references),
        *(item.created_at for item in bundle.authorization_references),
        *(item.created_at for item in bundle.permit_references),
        *(item.revoked_at for item in bundle.revocation_references),
    )
    if any(bundle.created_at < item for item in nested_times):
        raise RuntimeAuthorityTimestampError("bundle predates a nested record")
    _validate_revocation_targets(bundle)
    if bundle.audit_metadata is not None:
        validate_runtime_authority_audit_metadata(bundle.audit_metadata, bundle)
    return bundle


def build_runtime_authority_bundle(bundle: RuntimeAuthorityBundle) -> RuntimeAuthorityBundle:
    """Validate and return the caller-supplied immutable bundle unchanged."""
    return validate_runtime_authority_bundle(bundle)


def _validate_common_reference(reference, request, kind: str) -> None:
    if reference.runtime_execution_request_id != request.runtime_execution_request_id:
        raise RuntimeAuthorityScopeError(f"{kind} request identity mismatch")
    if reference.tenant_id != request.tenant_id:
        raise RuntimeAuthorityTenantError(f"{kind} tenant mismatch")
    if reference.organization_id != request.organization_id:
        raise RuntimeAuthorityOrganizationError(f"{kind} organization mismatch")
    if reference.policy_revision != request.policy_revision:
        raise RuntimeAuthorityScopeError(f"{kind} policy revision mismatch")
    classification = getattr(reference, "classification", None)
    if classification is not None and not not_lower(classification, request.classification):
        raise RuntimeAuthorityClassificationError(f"{kind} classification is too low")
    if reference.created_at < request.requested_at:
        raise RuntimeAuthorityTimestampError(f"{kind} reference predates request")


def _request_scope(request: RuntimeExecutionRequest) -> tuple:
    return (
        request.tenant_id,
        request.organization_id,
        request.requester_actor_id,
        request.requester_agent_instance_id,
        request.on_behalf_of_user_id,
        request.resource_reference,
        request.action,
        request.purpose,
        request.risk_level,
        request.execution_environment,
        request.model_id,
        request.provider_id,
        request.tool_id,
        request.connector_id,
        request.destination_reference,
        request.policy_revision,
        request.authorization_revision,
        request.registry_revision,
        request.lineage_id,
        request.lineage_digest_reference,
    )


def _context_scope(context: RuntimeAuthorityContext) -> tuple:
    return (
        context.tenant_id,
        context.organization_id,
        context.actor_id,
        context.agent_instance_id,
        context.on_behalf_of_user_id,
        context.resource_reference,
        context.action,
        context.purpose,
        context.risk_level,
        context.execution_environment,
        context.model_id,
        context.provider_id,
        context.tool_id,
        context.connector_id,
        context.destination_reference,
        context.policy_revision,
        context.authorization_revision,
        context.registry_revision,
        context.context_lineage_id,
        context.context_lineage_digest_reference,
    )


def _validate_bundle_ordering(bundle: RuntimeAuthorityBundle) -> None:
    groups: tuple[tuple[Iterable, str], ...] = (
        (bundle.review_references, "runtime_review_reference_id"),
        (bundle.approval_references, "runtime_approval_reference_id"),
        (bundle.authorization_references, "runtime_authorization_reference_id"),
        (bundle.permit_references, "runtime_permit_reference_id"),
        (bundle.revocation_references, "runtime_authority_revocation_reference_id"),
    )
    for items, field in groups:
        values = tuple(items)
        ids = tuple(getattr(item, field) for item in values)
        if len(ids) != len(set(ids)):
            raise DuplicateRuntimeAuthorityReferenceError("duplicate runtime authority reference")
        if not canonical(ids):
            raise RuntimeAuthorityOrderingError("runtime authority references are not canonical")


def _validate_revocation_targets(bundle: RuntimeAuthorityBundle) -> None:
    targets = {
        RuntimeAuthorityReferenceType.APPROVAL: {
            item.runtime_approval_reference_id for item in bundle.approval_references
        },
        RuntimeAuthorityReferenceType.AUTHORIZATION: {
            item.runtime_authorization_reference_id for item in bundle.authorization_references
        },
        RuntimeAuthorityReferenceType.PERMIT: {
            item.runtime_permit_reference_id for item in bundle.permit_references
        },
    }
    for reference in bundle.revocation_references:
        if reference.authority_reference_id not in targets[reference.authority_reference_type]:
            raise OrphanRuntimeAuthorityReferenceError("revocation target is not in bundle")
