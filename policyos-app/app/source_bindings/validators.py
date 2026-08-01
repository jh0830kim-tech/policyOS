"""Pure focused validators for trusted bindings and immutable source families."""

from app.ai_providers import ProviderInvocationAuditRecord
from app.ai_selection import AuthorizedInvocationPermit
from app.cross_validation import (
    ConsensusDecisionPackage,
    CrossValidationPlan,
    CrossValidationRunCollection,
    CrossValidationSecretaryHandoff,
    ModelRunResult,
)
from app.evaluation import (
    EvaluationEvidenceBundle,
    EvaluationEvidenceValidationReport,
    EvaluationExecutionRecord,
    EvaluationPipelineRecord,
    EvaluationPlan,
)
from app.mcp_governance import (
    AuthorizedMcpToolInvocationPermit,
    McpToolAuthorizationDecision,
    McpToolRunResultReference,
)
from app.observability import ObservabilityBundle
from app.source_bindings._base import not_lower
from app.source_bindings.domain import (
    TrustedBindingAuthorityType,
    TrustedMetadataOrigin,
    TrustedSourceBinding,
    TrustedSourceBindingStatus,
    TrustedSourceType,
    TrustedSupplementalCategory,
)
from app.source_bindings.errors import (
    TrustedSourceAuthorityError,
    TrustedSourceBindingMismatchError,
    TrustedSourceIdentityError,
    TrustedSourceLineageError,
    TrustedSourceOrganizationError,
    TrustedSourceStatusError,
    TrustedSourceTenantError,
    TrustedSourceVersionError,
)
from app.zero_trust import QuarantineDecision, SecurityViolationEvent
from app.zero_trust.credentials import SecretAccessAuditRecord

_AUTHORITY_CATEGORIES = {
    TrustedBindingAuthorityType.SOURCE_DOMAIN: frozenset(),
    TrustedBindingAuthorityType.POLICY_ENGINE: frozenset(
        {
            TrustedSupplementalCategory.POLICY,
            TrustedSupplementalCategory.AUTHORIZATION,
        }
    ),
    TrustedBindingAuthorityType.SECURITY_GOVERNANCE: frozenset(
        {
            TrustedSupplementalCategory.ORGANIZATION,
            TrustedSupplementalCategory.CLASSIFICATION,
            TrustedSupplementalCategory.LINEAGE,
        }
    ),
    TrustedBindingAuthorityType.EVALUATION_GOVERNANCE: frozenset(
        {
            TrustedSupplementalCategory.TENANT,
            TrustedSupplementalCategory.ORGANIZATION,
            TrustedSupplementalCategory.CLASSIFICATION,
            TrustedSupplementalCategory.LINEAGE,
        }
    ),
    TrustedBindingAuthorityType.ORGANIZATION_REGISTRY: frozenset(
        {
            TrustedSupplementalCategory.ORGANIZATION,
        }
    ),
    TrustedBindingAuthorityType.TENANT_REGISTRY: frozenset(
        {
            TrustedSupplementalCategory.TENANT,
        }
    ),
    TrustedBindingAuthorityType.MIGRATION_AUTHORITY: frozenset(TrustedSupplementalCategory),
    TrustedBindingAuthorityType.MANUAL_REVIEW_AUTHORITY: frozenset(TrustedSupplementalCategory),
}


def validate_trusted_source_binding(
    binding: TrustedSourceBinding,
    *,
    expected_type: TrustedSourceType,
    expected_id,
    owner_package: str,
    required_supplemental: tuple[TrustedSupplementalCategory, ...],
    native_tenant=None,
    native_organization=None,
    native_classification=None,
    native_lineage_id=None,
    native_lineage_digest=None,
    native_version=None,
    native_revision=None,
    native_recorded_at=None,
) -> None:
    if binding.status is not TrustedSourceBindingStatus.ACTIVE:
        raise TrustedSourceStatusError("trusted source binding is not active")
    identity = binding.source_identity
    if (
        identity.source_type is not expected_type
        or identity.source_id != expected_id
        or identity.source_owner_package != owner_package
    ):
        raise TrustedSourceIdentityError("trusted source identity mismatch")
    if native_version is not None and identity.source_version != str(native_version):
        raise TrustedSourceVersionError("trusted source version mismatch")
    if native_revision is not None and identity.source_revision != native_revision:
        raise TrustedSourceVersionError("trusted source revision mismatch")
    governance = binding.governance_context
    lineage = binding.lineage_context
    if native_tenant is not None and governance.tenant_id != native_tenant:
        raise TrustedSourceTenantError("trusted source tenant mismatch")
    if native_organization is not None and governance.organization_id != native_organization:
        raise TrustedSourceOrganizationError("trusted source organization mismatch")
    if native_classification is not None:
        if TrustedSupplementalCategory.CLASSIFICATION in required_supplemental:
            not_lower(governance.classification, native_classification)
        elif governance.classification is not native_classification:
            raise TrustedSourceBindingMismatchError(
                "source-native classification cannot be overridden"
            )
    if native_lineage_id is not None and (
        lineage.lineage_id != native_lineage_id
        or lineage.lineage_digest_reference != native_lineage_digest
    ):
        raise TrustedSourceLineageError("trusted source lineage mismatch")
    if native_recorded_at is not None and lineage.source_recorded_at != native_recorded_at:
        raise TrustedSourceBindingMismatchError("trusted source timestamp mismatch")
    required = tuple(required_supplemental)
    if binding.supplemental_field_categories != required:
        raise TrustedSourceAuthorityError("trusted supplemental categories mismatch")
    if required:
        if binding.metadata_origin is TrustedMetadataOrigin.SOURCE_NATIVE:
            raise TrustedSourceAuthorityError("supplemental metadata requires authority origin")
        allowed = _AUTHORITY_CATEGORIES[binding.binding_authority.authority_type]
        if not set(required).issubset(allowed):
            raise TrustedSourceAuthorityError("binding authority exceeds allowed categories")
        migration = (
            binding.binding_authority.authority_type
            is TrustedBindingAuthorityType.MIGRATION_AUTHORITY
        )
        if migration != (binding.metadata_origin is TrustedMetadataOrigin.MIGRATION_SUPPLIED):
            raise TrustedSourceAuthorityError("migration metadata origin mismatch")
    elif (
        binding.metadata_origin is not TrustedMetadataOrigin.SOURCE_NATIVE
        or binding.binding_authority.authority_type is not TrustedBindingAuthorityType.SOURCE_DOMAIN
    ):
        raise TrustedSourceAuthorityError("source-complete binding requires source authority")


def validate_evaluation_source_binding(binding, source) -> None:
    if isinstance(source, EvaluationPlan):
        validate_trusted_source_binding(
            binding,
            expected_type=TrustedSourceType.EVALUATION_PLAN,
            expected_id=source.evaluation_plan_id,
            owner_package="app.evaluation",
            required_supplemental=(),
            native_tenant=source.tenant_id,
            native_organization=source.organization_id,
            native_classification=source.classification,
            native_lineage_id=source.delegation_lineage_id,
            native_lineage_digest=source.delegation_lineage_digest,
            native_revision=source.registry_revision,
            native_recorded_at=source.created_at,
        )
    elif isinstance(source, EvaluationExecutionRecord):
        context = source.execution_context
        validate_trusted_source_binding(
            binding,
            expected_type=TrustedSourceType.EVALUATION_EXECUTION_RECORD,
            expected_id=source.evaluation_execution_id,
            owner_package="app.evaluation",
            required_supplemental=(),
            native_tenant=context.tenant_id,
            native_organization=context.organization_id,
            native_classification=source.classification,
            native_lineage_id=context.delegation_lineage_id,
            native_lineage_digest=context.delegation_lineage_digest,
            native_recorded_at=source.created_at,
        )
    elif isinstance(source, EvaluationEvidenceBundle):
        validate_trusted_source_binding(
            binding,
            expected_type=TrustedSourceType.EVALUATION_EVIDENCE_BUNDLE,
            expected_id=source.evidence_bundle_id,
            owner_package="app.evaluation",
            required_supplemental=(),
            native_tenant=source.provenance.tenant_id,
            native_organization=source.provenance.organization_id,
            native_classification=source.classification,
            native_lineage_id=source.lineage.delegation_lineage_id,
            native_lineage_digest=source.lineage.delegation_lineage_digest,
            native_recorded_at=source.created_at,
        )
    elif isinstance(source, EvaluationPipelineRecord):
        validate_trusted_source_binding(
            binding,
            expected_type=TrustedSourceType.EVALUATION_PIPELINE_RECORD,
            expected_id=source.pipeline_id,
            owner_package="app.evaluation",
            required_supplemental=(),
            native_tenant=source.tenant_id,
            native_organization=source.organization_id,
            native_classification=source.classification,
            native_lineage_id=source.delegation_lineage_id,
            native_lineage_digest=source.delegation_lineage_digest,
            native_revision=source.registry_revision,
            native_recorded_at=source.created_at,
        )
    elif isinstance(source, EvaluationEvidenceValidationReport):
        validate_trusted_source_binding(
            binding,
            expected_type=TrustedSourceType.EVALUATION_VALIDATION_REPORT,
            expected_id=source.report_id,
            owner_package="app.evaluation",
            required_supplemental=(
                TrustedSupplementalCategory.TENANT,
                TrustedSupplementalCategory.ORGANIZATION,
                TrustedSupplementalCategory.LINEAGE,
            ),
            native_classification=source.classification,
            native_recorded_at=source.created_at,
        )
    else:
        raise TrustedSourceIdentityError("unsupported evaluation source type")


def _supplement(*categories):
    return tuple(sorted(categories, key=tuple(TrustedSupplementalCategory).index))


def validate_cross_validation_source_binding(binding, source) -> None:
    common = dict(owner_package="app.cross_validation")
    if isinstance(source, CrossValidationPlan):
        validate_trusted_source_binding(
            binding,
            expected_type=TrustedSourceType.CROSS_VALIDATION_PLAN,
            expected_id=source.plan_id,
            required_supplemental=_supplement(
                TrustedSupplementalCategory.ORGANIZATION,
                TrustedSupplementalCategory.LINEAGE,
            ),
            native_tenant=source.tenant_id,
            native_classification=source.classification,
            native_revision=source.registry_revision,
            native_recorded_at=source.created_at,
            **common,
        )
    elif isinstance(source, CrossValidationRunCollection):
        validate_trusted_source_binding(
            binding,
            expected_type=TrustedSourceType.CROSS_VALIDATION_RUN_COLLECTION,
            expected_id=source.collection_id,
            required_supplemental=_supplement(
                TrustedSupplementalCategory.ORGANIZATION,
                TrustedSupplementalCategory.CLASSIFICATION,
                TrustedSupplementalCategory.LINEAGE,
            ),
            native_tenant=source.tenant_id,
            native_revision=source.registry_revision,
            native_recorded_at=source.collected_at,
            **common,
        )
    elif isinstance(source, ModelRunResult):
        validate_trusted_source_binding(
            binding,
            expected_type=TrustedSourceType.MODEL_RUN_RESULT,
            expected_id=source.run_result_id,
            required_supplemental=_supplement(
                TrustedSupplementalCategory.ORGANIZATION,
                TrustedSupplementalCategory.CLASSIFICATION,
                TrustedSupplementalCategory.LINEAGE,
            ),
            native_tenant=source.tenant_id,
            native_revision=source.registry_revision,
            native_recorded_at=source.completed_at,
            **common,
        )
        if binding.governance_context.permit_id != source.permit_id:
            raise TrustedSourceBindingMismatchError("model run permit identity mismatch")
    elif isinstance(source, ConsensusDecisionPackage):
        specification = source.assessment_specification
        validate_trusted_source_binding(
            binding,
            expected_type=TrustedSourceType.CONSENSUS_PACKAGE,
            expected_id=source.package_id,
            required_supplemental=_supplement(
                TrustedSupplementalCategory.ORGANIZATION,
                TrustedSupplementalCategory.LINEAGE,
            ),
            native_tenant=specification.tenant_id,
            native_classification=source.effective_classification,
            native_revision=specification.registry_revision,
            native_recorded_at=source.created_at,
            **common,
        )
    else:
        raise TrustedSourceIdentityError("unsupported cross-validation source type")


def validate_model_provider_source_binding(binding, source) -> None:
    if isinstance(source, AuthorizedInvocationPermit):
        validate_trusted_source_binding(
            binding,
            expected_type=TrustedSourceType.MODEL_INVOCATION_PERMIT,
            expected_id=source.permit_id,
            owner_package="app.ai_selection",
            required_supplemental=_supplement(
                TrustedSupplementalCategory.ORGANIZATION,
                TrustedSupplementalCategory.LINEAGE,
            ),
            native_tenant=source.tenant_id,
            native_classification=source.classification,
            native_recorded_at=source.issued_at,
        )
        if binding.governance_context.authorization_decision_id != source.authorization_decision_id:
            raise TrustedSourceBindingMismatchError("model permit decision mismatch")
    elif isinstance(source, ProviderInvocationAuditRecord):
        validate_trusted_source_binding(
            binding,
            expected_type=TrustedSourceType.PROVIDER_INVOCATION_AUDIT,
            expected_id=source.audit_id,
            owner_package="app.ai_providers",
            required_supplemental=_supplement(
                TrustedSupplementalCategory.TENANT,
                TrustedSupplementalCategory.ORGANIZATION,
                TrustedSupplementalCategory.CLASSIFICATION,
                TrustedSupplementalCategory.LINEAGE,
            ),
            native_revision=source.registry_revision,
            native_recorded_at=source.recorded_at,
        )
        if (
            binding.governance_context.authorization_decision_id != source.decision_id
            or binding.governance_context.permit_id != source.permit_id
        ):
            raise TrustedSourceBindingMismatchError("provider authorization identity mismatch")
    elif isinstance(source, ModelRunResult):
        validate_cross_validation_source_binding(binding, source)
    else:
        raise TrustedSourceIdentityError("unsupported model/provider source type")


def validate_mcp_source_binding(binding, source) -> None:
    if isinstance(source, McpToolAuthorizationDecision):
        validate_trusted_source_binding(
            binding,
            expected_type=TrustedSourceType.MCP_AUTHORIZATION_DECISION,
            expected_id=source.decision_id,
            owner_package="app.mcp_governance",
            required_supplemental=_supplement(
                TrustedSupplementalCategory.ORGANIZATION,
                TrustedSupplementalCategory.LINEAGE,
            ),
            native_tenant=source.tenant_id,
            native_classification=source.classification,
            native_revision=source.mcp_registry_revision,
            native_recorded_at=source.decided_at,
        )
        if source.outcome.value != "allow":
            raise TrustedSourceStatusError("denied MCP decision cannot be an active binding")
    elif isinstance(source, AuthorizedMcpToolInvocationPermit):
        validate_trusted_source_binding(
            binding,
            expected_type=TrustedSourceType.MCP_INVOCATION_PERMIT,
            expected_id=source.permit_id,
            owner_package="app.mcp_governance",
            required_supplemental=_supplement(
                TrustedSupplementalCategory.ORGANIZATION,
                TrustedSupplementalCategory.LINEAGE,
            ),
            native_tenant=source.tenant_id,
            native_classification=source.classification,
            native_recorded_at=source.issued_at,
        )
        if binding.governance_context.authorization_decision_id != source.authorization_decision_id:
            raise TrustedSourceBindingMismatchError("MCP permit decision mismatch")
    elif isinstance(source, McpToolRunResultReference):
        validate_trusted_source_binding(
            binding,
            expected_type=TrustedSourceType.MCP_TOOL_RESULT,
            expected_id=source.tool_result_id,
            owner_package="app.mcp_governance",
            required_supplemental=_supplement(
                TrustedSupplementalCategory.TENANT,
                TrustedSupplementalCategory.ORGANIZATION,
                TrustedSupplementalCategory.LINEAGE,
            ),
            native_classification=source.classification,
            native_revision=source.tool_schema_revision,
            native_recorded_at=source.completed_at,
        )
        if binding.governance_context.permit_id != source.permit_id:
            raise TrustedSourceBindingMismatchError("MCP result permit mismatch")
    else:
        raise TrustedSourceIdentityError("unsupported MCP source type")


def validate_security_source_binding(binding, source) -> None:
    if isinstance(source, SecurityViolationEvent):
        validate_trusted_source_binding(
            binding,
            expected_type=TrustedSourceType.SECURITY_VIOLATION,
            expected_id=source.violation_event_id,
            owner_package="app.zero_trust",
            required_supplemental=(),
            native_tenant=source.tenant_id,
            native_organization=source.organization_id,
            native_classification=source.classification,
            native_lineage_id=source.lineage_id,
            native_lineage_digest=source.observed_lineage_digest,
            native_recorded_at=source.detected_at,
        )
        if not source.confirmed:
            raise TrustedSourceStatusError("unconfirmed security violation cannot be active")
    elif isinstance(source, QuarantineDecision):
        validate_trusted_source_binding(
            binding,
            expected_type=TrustedSourceType.QUARANTINE_DECISION,
            expected_id=source.quarantine_decision_id,
            owner_package="app.zero_trust",
            required_supplemental=_supplement(
                TrustedSupplementalCategory.ORGANIZATION,
                TrustedSupplementalCategory.CLASSIFICATION,
                TrustedSupplementalCategory.LINEAGE,
            ),
            native_tenant=source.tenant_scope,
            native_revision=source.registry_revision,
            native_recorded_at=source.decided_at,
        )
        if source.outcome.value not in {"quarantine", "extend_quarantine"}:
            raise TrustedSourceStatusError("inactive quarantine decision cannot be bound")
    elif isinstance(source, SecretAccessAuditRecord):
        validate_trusted_source_binding(
            binding,
            expected_type=TrustedSourceType.SECRET_ACCESS_AUDIT,
            expected_id=source.audit_id,
            owner_package="app.zero_trust",
            required_supplemental=_supplement(
                TrustedSupplementalCategory.CLASSIFICATION,
                TrustedSupplementalCategory.LINEAGE,
            ),
            native_tenant=source.tenant_id,
            native_organization=source.organization_id,
            native_revision=source.grant_revision,
            native_recorded_at=source.accessed_at,
        )
    else:
        raise TrustedSourceIdentityError("unsupported security source type")


def validate_secretary_source_binding(
    binding: TrustedSourceBinding, source: CrossValidationSecretaryHandoff
) -> None:
    validate_trusted_source_binding(
        binding,
        expected_type=TrustedSourceType.SECRETARY_HANDOFF,
        expected_id=source.handoff_id,
        owner_package="app.cross_validation",
        required_supplemental=_supplement(
            TrustedSupplementalCategory.ORGANIZATION,
            TrustedSupplementalCategory.LINEAGE,
        ),
        native_tenant=source.tenant_id,
        native_classification=source.effective_classification,
        native_revision=source.registry_revision,
        native_recorded_at=source.created_at,
    )


def validate_observability_source_binding(
    binding: TrustedSourceBinding, source: ObservabilityBundle
) -> None:
    context = source.correlation_context
    validate_trusted_source_binding(
        binding,
        expected_type=TrustedSourceType.OBSERVABILITY_BUNDLE,
        expected_id=source.observability_bundle_id,
        owner_package="app.observability",
        required_supplemental=(),
        native_tenant=context.tenant_id,
        native_organization=context.organization_id,
        native_classification=source.classification,
        native_lineage_id=context.delegation_lineage_id,
        native_lineage_digest=context.delegation_lineage_digest,
        native_recorded_at=source.created_at,
    )


def build_trusted_source_binding(binding: TrustedSourceBinding, source) -> TrustedSourceBinding:
    source_type = binding.source_identity.source_type
    if source_type.value.startswith("evaluation_"):
        validate_evaluation_source_binding(binding, source)
    elif source_type in {
        TrustedSourceType.CROSS_VALIDATION_PLAN,
        TrustedSourceType.CROSS_VALIDATION_RUN_COLLECTION,
        TrustedSourceType.CONSENSUS_PACKAGE,
    }:
        validate_cross_validation_source_binding(binding, source)
    elif source_type in {
        TrustedSourceType.MODEL_RUN_RESULT,
        TrustedSourceType.MODEL_INVOCATION_PERMIT,
        TrustedSourceType.PROVIDER_INVOCATION_AUDIT,
    }:
        validate_model_provider_source_binding(binding, source)
    elif source_type in {
        TrustedSourceType.MCP_AUTHORIZATION_DECISION,
        TrustedSourceType.MCP_INVOCATION_PERMIT,
        TrustedSourceType.MCP_TOOL_RESULT,
    }:
        validate_mcp_source_binding(binding, source)
    elif source_type in {
        TrustedSourceType.SECURITY_VIOLATION,
        TrustedSourceType.QUARANTINE_DECISION,
        TrustedSourceType.SECRET_ACCESS_AUDIT,
    }:
        validate_security_source_binding(binding, source)
    elif source_type is TrustedSourceType.SECRETARY_HANDOFF:
        validate_secretary_source_binding(binding, source)
    elif source_type is TrustedSourceType.OBSERVABILITY_BUNDLE:
        validate_observability_source_binding(binding, source)
    else:
        raise TrustedSourceIdentityError("unsupported trusted source type")
    return binding


def build_trusted_source_binding_bundle(bundle):
    from app.source_bindings.domain import validate_trusted_source_binding_bundle

    validate_trusted_source_binding_bundle(bundle)
    return bundle
