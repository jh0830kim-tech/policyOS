"""Immutable caller-supplied Decision package contracts."""

from datetime import datetime
from enum import StrEnum
from uuid import UUID

from pydantic import Field, field_validator, model_validator

from app.ai.privacy import DataClassification
from app.decisions._base import DecisionModel, aware, require_canonical
from app.decisions.errors import DecisionPackageError
from app.judge import JudgeDecisionBundleVersion


class DecisionPackageStatus(StrEnum):
    RECORDED = "recorded"
    UNAVAILABLE = "unavailable"
    NOT_APPLICABLE = "not_applicable"
    INVALIDATED = "invalidated"


class DecisionDispositionType(StrEnum):
    PROCEED_TO_REVIEW = "proceed_to_review"
    HOLD_FOR_REVIEW = "hold_for_review"
    REQUIRE_ADDITIONAL_EVIDENCE = "require_additional_evidence"
    REQUIRE_POLICY_REVIEW = "require_policy_review"
    REQUIRE_SECURITY_REVIEW = "require_security_review"
    REQUIRE_LEGAL_REVIEW = "require_legal_review"
    REQUIRE_HUMAN_REVIEW = "require_human_review"
    DEFER = "defer"
    ESCALATE = "escalate"
    RECORD_ONLY = "record_only"
    NOT_APPLICABLE = "not_applicable"


class DecisionSubjectType(StrEnum):
    EVALUATION_PIPELINE = "evaluation_pipeline"
    METRIC_RESULT_BUNDLE = "metric_result_bundle"
    METRIC_AGGREGATION_BUNDLE = "metric_aggregation_bundle"
    JUDGE_DECISION_BUNDLE = "judge_decision_bundle"
    CROSS_VALIDATION_RUN = "cross_validation_run"
    CONSENSUS_PACKAGE = "consensus_package"
    MODEL_INVOCATION = "model_invocation"
    MCP_OPERATION = "mcp_operation"
    SECURITY_EVENT = "security_event"
    QUARANTINE_DECISION = "quarantine_decision"
    SECRETARY_HANDOFF = "secretary_handoff"


class DecisionReasonCode(StrEnum):
    CALLER_SUPPLIED = "caller_supplied"
    INPUT_UNAVAILABLE = "input_unavailable"
    POLICY_NOT_APPLICABLE = "policy_not_applicable"
    PACKAGE_INVALIDATED = "package_invalidated"


class DecisionPackageVersion(DecisionModel):
    decision_package_version: str = Field(min_length=1, max_length=100)
    decision_package_contract_version: str = Field(min_length=1, max_length=100)
    decision_package_schema_version: str = Field(
    pattern=r"^decision-package-schema-v1$"
)
provenance_schema_version: str = Field(
    pattern=r"^decision-package-provenance-schema-v1$"
)

class DecisionPackageAuditMetadata(DecisionModel):
    decision_package_id: UUID
    package_version: DecisionPackageVersion
    subject_reference_count: int = Field(ge=0)
    judge_bundle_binding_count: int = Field(ge=0)
    judge_policy_count: int = Field(ge=0)
    judge_decision_record_count: int = Field(ge=0)
    review_requirement_count: int = Field(ge=0)
    unresolved_review_count: int = Field(ge=0)
    lineage_reference_count: int = Field(ge=0)
    provenance_reference_count: int = Field(ge=0)
    disposition_count: int = Field(ge=0)
    tenant_id: UUID
    organization_id: UUID
    classification: DataClassification
    policy_revision: int = Field(ge=1)
    registry_revision: int | None = Field(default=None, ge=1)
    created_at: datetime

    @field_validator("created_at")
    @classmethod
    def aware_created(cls, value: datetime) -> datetime:
        return aware(value, "created_at")    


class DecisionSubjectReference(DecisionModel):
    decision_subject_reference_id: UUID
    subject_type: DecisionSubjectType
    subject_id: UUID
    subject_version: str | None = Field(default=None, min_length=1, max_length=100)
    resource_reference: str = Field(min_length=1, max_length=300)
    action: str = Field(min_length=1, max_length=100)
    purpose: str = Field(min_length=1, max_length=200)
    risk_level: str = Field(min_length=1, max_length=100)
    tenant_id: UUID
    organization_id: UUID
    classification: DataClassification
    lineage_id: UUID
    lineage_digest_reference: str = Field(min_length=1, max_length=300)
    created_at: datetime

    @field_validator("created_at")
    @classmethod
    def aware_created(cls, value):
        return aware(value, "created_at")


class DecisionJudgeBundleBinding(DecisionModel):
    decision_judge_bundle_binding_id: UUID
    judge_decision_bundle_id: UUID
    judge_decision_bundle_version: JudgeDecisionBundleVersion
    judge_policy_ids: tuple[UUID, ...] = Field(min_length=1)
    judge_decision_record_ids: tuple[UUID, ...] = Field(min_length=1)
    unresolved_review_requirement_ids: tuple[UUID, ...] = ()
    lineage_reference_ids: tuple[UUID, ...] = Field(min_length=1)
    provenance_reference_ids: tuple[UUID, ...] = Field(min_length=1)
    tenant_id: UUID
    organization_id: UUID
    classification: DataClassification
    policy_revision: int = Field(ge=1)
    authorization_revision: int | None = Field(default=None, ge=1)
    registry_revision: int | None = Field(default=None, ge=1)
    bound_at: datetime

    @field_validator(
        "judge_policy_ids",
        "judge_decision_record_ids",
        "unresolved_review_requirement_ids",
        "lineage_reference_ids",
        "provenance_reference_ids",
    )
    @classmethod
    def canonical_ids(cls, value, info):
        return require_canonical(value, info.field_name, key=str)

    @field_validator("bound_at")
    @classmethod
    def aware_bound(cls, value):
        return aware(value, "bound_at")


class DecisionReviewSummary(DecisionModel):
    decision_review_summary_id: UUID
    required_review_requirement_ids: tuple[UUID, ...] = ()
    requested_review_requirement_ids: tuple[UUID, ...] = ()
    completed_review_requirement_ids: tuple[UUID, ...] = ()
    waived_review_requirement_ids: tuple[UUID, ...] = ()
    cancelled_review_requirement_ids: tuple[UUID, ...] = ()
    unresolved_review_requirement_ids: tuple[UUID, ...] = ()
    separate_approval_required: bool
    external_authorization_required: bool
    publication_authorization_required: bool
    external_transmission_authorization_required: bool
    tenant_id: UUID
    organization_id: UUID
    classification: DataClassification
    lineage_id: UUID
    lineage_digest_reference: str = Field(min_length=1, max_length=300)
    created_at: datetime

    @field_validator(
        "required_review_requirement_ids",
        "requested_review_requirement_ids",
        "completed_review_requirement_ids",
        "waived_review_requirement_ids",
        "cancelled_review_requirement_ids",
        "unresolved_review_requirement_ids",
    )
    @classmethod
    def canonical_ids(cls, value, info):
        return require_canonical(value, info.field_name, key=str)

    @field_validator("created_at")
    @classmethod
    def aware_created(cls, value):
        return aware(value, "created_at")


class DecisionPackageLineageReference(DecisionModel):
    decision_package_lineage_reference_id: UUID
    root_lineage_id: UUID
    root_lineage_digest_reference: str = Field(min_length=1, max_length=300)
    decision_package_id: UUID
    judge_decision_bundle_ids: tuple[UUID, ...] = Field(min_length=1)
    judge_decision_record_ids: tuple[UUID, ...] = Field(min_length=1)
    parent_decision_package_ids: tuple[UUID, ...] = ()
    subject_reference_ids: tuple[UUID, ...] = Field(min_length=1)
    lineage_schema_version: str = Field(pattern=r"^decision-package-lineage-schema-v1$")
    created_at: datetime

    @field_validator(
        "judge_decision_bundle_ids",
        "judge_decision_record_ids",
        "parent_decision_package_ids",
        "subject_reference_ids",
    )
    @classmethod
    def canonical_ids(cls, value, info):
        return require_canonical(value, info.field_name, key=str)

    @field_validator("created_at")
    @classmethod
    def aware_created(cls, value):
        return aware(value, "created_at")


class DecisionPackageProvenanceReference(DecisionModel):
    decision_package_provenance_reference_id: UUID
    decision_package_id: UUID
    judge_decision_bundle_ids: tuple[UUID, ...] = Field(min_length=1)
    judge_policy_ids: tuple[UUID, ...] = Field(min_length=1)
    judge_decision_record_ids: tuple[UUID, ...] = Field(min_length=1)
    judge_assessment_bundle_ids: tuple[UUID, ...] = ()
    metric_aggregation_bundle_ids: tuple[UUID, ...] = Field(min_length=1)
    metric_aggregation_record_ids: tuple[UUID, ...] = Field(min_length=1)
    metric_result_bundle_ids: tuple[UUID, ...] = ()
    trusted_source_binding_ids: tuple[UUID, ...] = ()
    evaluation_pipeline_ids: tuple[UUID, ...] = ()
    dataset_manifest_reference_ids: tuple[UUID, ...] = ()
    dataset_split_reference_ids: tuple[UUID, ...] = ()
    policy_revision: int = Field(ge=1)
    authorization_revision: int | None = Field(default=None, ge=1)
    registry_revision: int | None = Field(default=None, ge=1)
    provenance_schema_version: str = Field(pattern=r"^decision-package-provenance-schema-v1$")
    recorded_at: datetime

    @field_validator(
        "judge_decision_bundle_ids",
        "judge_policy_ids",
        "judge_decision_record_ids",
        "judge_assessment_bundle_ids",
        "metric_aggregation_bundle_ids",
        "metric_aggregation_record_ids",
        "metric_result_bundle_ids",
        "trusted_source_binding_ids",
        "evaluation_pipeline_ids",
        "dataset_manifest_reference_ids",
        "dataset_split_reference_ids",
    )
    @classmethod
    def canonical_ids(cls, value, info):
        return require_canonical(value, info.field_name, key=str)

    @field_validator("recorded_at")
    @classmethod
    def aware_recorded(cls, value):
        return aware(value, "recorded_at")


class DecisionPackage(DecisionModel):
    decision_package_id: UUID
    package_version: DecisionPackageVersion
    package_status: DecisionPackageStatus
    disposition_type: DecisionDispositionType | None = None
    disposition_reference: str | None = Field(default=None, min_length=1, max_length=300)
    subject_references: tuple[DecisionSubjectReference, ...]
    judge_bundle_bindings: tuple[DecisionJudgeBundleBinding, ...]
    review_summary: DecisionReviewSummary | None = None
    lineage_references: tuple[DecisionPackageLineageReference, ...]
    provenance_references: tuple[DecisionPackageProvenanceReference, ...]
    reason_codes: tuple[DecisionReasonCode, ...] = ()
    original_decision_package_id: UUID | None = None
    invalidation_reference: str | None = Field(default=None, min_length=1, max_length=300)
    actor_id: UUID
    agent_instance_id: UUID | None = None
    on_behalf_of_user_id: UUID | None = None
    tenant_id: UUID
    organization_id: UUID
    classification: DataClassification
    root_lineage_id: UUID
    root_lineage_digest_reference: str = Field(min_length=1, max_length=300)
    policy_revision: int = Field(ge=1)
    authorization_revision: int | None = Field(default=None, ge=1)
    registry_revision: int | None = Field(default=None, ge=1)
    audit_metadata: DecisionPackageAuditMetadata | None = None
    recorded_at: datetime

    @field_validator("reason_codes")
    @classmethod
    def canonical_reasons(cls, value):
        return require_canonical(value, "reason_codes", key=str)

    @field_validator("recorded_at")
    @classmethod
    def aware_recorded(cls, value):
        return aware(value, "recorded_at")

    @model_validator(mode="after")
    def valid_lifecycle(self):
        disposition = self.disposition_type is not None
        invalidation = (
            self.original_decision_package_id is not None
            and self.invalidation_reference is not None
        )
        if self.package_status is DecisionPackageStatus.RECORDED:
            valid = (
                disposition
                and bool(self.subject_references)
                and bool(self.judge_bundle_bindings)
            )
            valid = (
                valid
                and bool(self.lineage_references)
                and bool(self.provenance_references)
            )
            valid = valid and not invalidation
        elif self.package_status is DecisionPackageStatus.UNAVAILABLE:
            valid = (
                not disposition
                and self.disposition_reference is None
                and not invalidation
                and DecisionReasonCode.INPUT_UNAVAILABLE in self.reason_codes
            )
        elif self.package_status is DecisionPackageStatus.NOT_APPLICABLE:
            valid = (
                not disposition
                and self.disposition_reference is None
                and not invalidation
                and DecisionReasonCode.POLICY_NOT_APPLICABLE in self.reason_codes
            )
        else:
            valid = (
                not disposition
                and self.disposition_reference is None
                and invalidation
                and self.original_decision_package_id != self.decision_package_id
                and DecisionReasonCode.PACKAGE_INVALIDATED in self.reason_codes
            )
        if not valid:
            raise DecisionPackageError("decision package lifecycle metadata mismatch")
        return self


class DecisionPackageRequest(DecisionModel):
    package: DecisionPackage
    judge_decision_bundles: tuple["JudgeDecisionBundle", ...]


from app.judge import JudgeDecisionBundle  # noqa: E402

DecisionPackageRequest.model_rebuild()


