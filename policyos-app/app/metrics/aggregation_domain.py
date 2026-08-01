"""Immutable metadata-only contracts for caller-supplied metric aggregation."""

from datetime import datetime
from enum import StrEnum
from uuid import UUID

from pydantic import Field, field_validator, model_validator

from app.ai.privacy import DataClassification
from app.metrics._base import MetricsModel, aware, canonical
from app.metrics.aggregation_audit import MetricAggregationAuditMetadata
from app.metrics.domain import (
    MetricAggregationMethod,
    MetricAggregationPolicy,
    MetricDefinitionVersion,
    MetricMissingValuePolicy,
    MetricResult,
    MetricResultBundle,
    MetricResultStatus,
    MetricValue,
    MetricValueType,
    validate_metric_aggregation_policy,
    validate_metric_result_bundle,
)
from app.metrics.errors import (
    DuplicateMetricAggregationError,
    MetricAggregationAuditError,
    MetricAggregationBundleError,
    MetricAggregationClassificationError,
    MetricAggregationGroupingError,
    MetricAggregationInputError,
    MetricAggregationLineageError,
    MetricAggregationOrderingError,
    MetricAggregationProvenanceError,
    MetricAggregationRecordError,
    MetricAggregationRequestError,
    MetricAggregationWindowError,
)


class MetricAggregationScope(StrEnum):
    SINGLE_DEFINITION = "single_definition"
    MULTIPLE_DEFINITIONS = "multiple_definitions"
    SINGLE_SOURCE = "single_source"
    MULTIPLE_SOURCES = "multiple_sources"
    SINGLE_EVALUATION_PIPELINE = "single_evaluation_pipeline"
    MULTIPLE_EVALUATION_PIPELINES = "multiple_evaluation_pipelines"
    SINGLE_CROSS_VALIDATION_PLAN = "single_cross_validation_plan"
    MULTIPLE_CROSS_VALIDATION_RUNS = "multiple_cross_validation_runs"
    SINGLE_MODEL = "single_model"
    MULTIPLE_MODELS = "multiple_models"
    SINGLE_PROVIDER = "single_provider"
    MULTIPLE_PROVIDERS = "multiple_providers"
    TENANT_SUMMARY = "tenant_summary"
    ORGANIZATION_SUMMARY = "organization_summary"


class MetricAggregationWindowType(StrEnum):
    EXPLICIT_RESULT_SET = "explicit_result_set"
    EXPLICIT_TIME_RANGE = "explicit_time_range"
    EVALUATION_PIPELINE = "evaluation_pipeline"
    EVALUATION_RUN = "evaluation_run"
    CROSS_VALIDATION_PLAN = "cross_validation_plan"
    CROSS_VALIDATION_RUN_SET = "cross_validation_run_set"
    POLICY_REVISION = "policy_revision"
    REGISTRY_REVISION = "registry_revision"
    DATASET_MANIFEST = "dataset_manifest"
    DATASET_SPLIT = "dataset_split"


class MetricAggregationGroupingDimension(StrEnum):
    METRIC_DEFINITION = "metric_definition"
    METRIC_CATEGORY = "metric_category"
    METRIC_SCOPE = "metric_scope"
    TRUSTED_SOURCE_TYPE = "trusted_source_type"
    SOURCE_ID = "source_id"
    EVALUATION_PIPELINE = "evaluation_pipeline"
    CROSS_VALIDATION_PLAN = "cross_validation_plan"
    CROSS_VALIDATION_RUN = "cross_validation_run"
    MODEL = "model"
    PROVIDER = "provider"
    MCP_SERVER = "mcp_server"
    MCP_TOOL = "mcp_tool"
    POLICY_REVISION = "policy_revision"
    REGISTRY_REVISION = "registry_revision"
    DATASET_MANIFEST = "dataset_manifest"
    DATASET_SPLIT = "dataset_split"
    TENANT = "tenant"
    ORGANIZATION = "organization"
    CLASSIFICATION = "classification"
    LINEAGE_ROOT = "lineage_root"


class MetricAggregationRecordStatus(StrEnum):
    RECORDED = "recorded"
    UNAVAILABLE = "unavailable"
    NOT_APPLICABLE = "not_applicable"
    INVALIDATED = "invalidated"


class MetricAggregationRequestVersion(MetricsModel):
    aggregation_request_version: str = Field(min_length=1, max_length=100)
    aggregation_request_contract_version: str = Field(min_length=1, max_length=100)
    aggregation_request_schema_version: str = Field(
        pattern=r"^metric-aggregation-request-schema-v1$"
    )


class MetricAggregationRecordVersion(MetricsModel):
    aggregation_record_version: str = Field(min_length=1, max_length=100)
    aggregation_record_contract_version: str = Field(min_length=1, max_length=100)
    aggregation_record_schema_version: str = Field(pattern=r"^metric-aggregation-record-schema-v1$")


class MetricAggregationBundleVersion(MetricsModel):
    metric_aggregation_bundle_version: str = Field(min_length=1, max_length=100)
    aggregation_bundle_contract_version: str = Field(min_length=1, max_length=100)
    aggregation_bundle_schema_version: str = Field(pattern=r"^metric-aggregation-bundle-schema-v1$")


class MetricAggregationWindow(MetricsModel):
    aggregation_window_id: UUID
    window_type: MetricAggregationWindowType
    start_at: datetime | None = None
    end_at: datetime | None = None
    evaluation_pipeline_id: UUID | None = None
    evaluation_run_request_id: UUID | None = None
    cross_validation_plan_id: UUID | None = None
    cross_validation_run_ids: tuple[UUID, ...] = ()
    policy_revision: int | None = Field(default=None, ge=1)
    registry_revision: int | None = Field(default=None, ge=1)
    dataset_manifest_reference_id: UUID | None = None
    dataset_split_reference_id: UUID | None = None
    created_at: datetime

    @field_validator("start_at", "end_at", "created_at")
    @classmethod
    def aware_times(cls, value, info):
        return None if value is None else aware(value, info.field_name)

    @field_validator("cross_validation_run_ids")
    @classmethod
    def canonical_runs(cls, value):
        return canonical(value, "cross_validation_run_ids", key=str)

    @model_validator(mode="after")
    def valid_contract(self):
        validate_metric_aggregation_window(self)
        return self


class MetricAggregationGroupingSpecification(MetricsModel):
    grouping_specification_id: UUID
    dimensions: tuple[MetricAggregationGroupingDimension, ...] = Field(min_length=1)
    grouping_key_references: tuple[str, ...] = Field(min_length=1)
    tenant_id: UUID
    organization_id: UUID
    classification: DataClassification
    created_at: datetime

    @field_validator("dimensions")
    @classmethod
    def canonical_dimensions(cls, value):
        return canonical(
            value, "dimensions", key=lambda x: tuple(MetricAggregationGroupingDimension).index(x)
        )

    @field_validator("grouping_key_references")
    @classmethod
    def canonical_keys(cls, value):
        return canonical(value, "grouping_key_references")

    @field_validator("created_at")
    @classmethod
    def aware_created(cls, value):
        return aware(value, "created_at")


class MetricAggregationInputReference(MetricsModel):
    aggregation_input_reference_id: UUID
    metric_result_id: UUID
    metric_result_version: str = Field(min_length=1, max_length=100)
    metric_definition_id: UUID
    metric_definition_version: MetricDefinitionVersion
    metric_observation_id: UUID
    trusted_source_binding_id: UUID
    metric_result_bundle_id: UUID
    input_ordinal: int = Field(ge=1)
    tenant_id: UUID
    organization_id: UUID
    classification: DataClassification
    lineage_id: UUID
    lineage_digest_reference: str = Field(min_length=1, max_length=300)
    recorded_at: datetime

    @field_validator("recorded_at")
    @classmethod
    def aware_recorded(cls, value):
        return aware(value, "recorded_at")


class MetricAggregationLineageReference(MetricsModel):
    aggregation_lineage_reference_id: UUID
    root_lineage_id: UUID
    root_lineage_digest_reference: str = Field(min_length=1, max_length=300)
    metric_result_bundle_id: UUID
    metric_result_ids: tuple[UUID, ...] = Field(min_length=1)
    aggregation_policy_id: UUID
    aggregation_window_id: UUID
    grouping_specification_id: UUID | None = None
    parent_aggregation_record_ids: tuple[UUID, ...] = ()
    lineage_schema_version: str = Field(pattern=r"^metric-aggregation-lineage-schema-v1$")
    created_at: datetime

    @field_validator("metric_result_ids", "parent_aggregation_record_ids")
    @classmethod
    def canonical_ids(cls, value, info):
        return canonical(value, info.field_name, key=str)

    @field_validator("created_at")
    @classmethod
    def aware_created(cls, value):
        return aware(value, "created_at")


class MetricAggregationProvenanceReference(MetricsModel):
    aggregation_provenance_reference_id: UUID
    metric_result_bundle_id: UUID
    metric_result_bundle_version: str = Field(min_length=1, max_length=100)
    metric_definition_ids: tuple[UUID, ...] = Field(min_length=1)
    metric_result_ids: tuple[UUID, ...] = Field(min_length=1)
    trusted_source_binding_ids: tuple[UUID, ...] = Field(min_length=1)
    aggregation_policy_id: UUID
    aggregation_policy_version: str = Field(min_length=1, max_length=100)
    aggregation_window_id: UUID
    grouping_specification_id: UUID | None = None
    policy_revision: int = Field(ge=1)
    registry_revision: int | None = Field(default=None, ge=1)
    dataset_manifest_reference_ids: tuple[UUID, ...] = ()
    dataset_split_reference_ids: tuple[UUID, ...] = ()
    evaluation_pipeline_ids: tuple[UUID, ...] = ()
    cross_validation_plan_ids: tuple[UUID, ...] = ()
    recorded_at: datetime

    @field_validator(
        "metric_definition_ids",
        "metric_result_ids",
        "trusted_source_binding_ids",
        "dataset_manifest_reference_ids",
        "dataset_split_reference_ids",
        "evaluation_pipeline_ids",
        "cross_validation_plan_ids",
    )
    @classmethod
    def canonical_ids(cls, value, info):
        return canonical(value, info.field_name, key=str)

    @field_validator("recorded_at")
    @classmethod
    def aware_recorded(cls, value):
        return aware(value, "recorded_at")


class MetricAggregationRequest(MetricsModel):
    metric_aggregation_request_id: UUID
    request_version: MetricAggregationRequestVersion
    metric_result_bundle_id: UUID
    metric_result_bundle_version: str = Field(min_length=1, max_length=100)
    metric_definition_ids: tuple[UUID, ...] = Field(min_length=1)
    aggregation_policy_id: UUID
    aggregation_policy_version: str = Field(min_length=1, max_length=100)
    aggregation_scope: MetricAggregationScope
    aggregation_window: MetricAggregationWindow
    grouping_specification: MetricAggregationGroupingSpecification | None = None
    input_references: tuple[MetricAggregationInputReference, ...] = Field(min_length=1)
    lineage_reference: MetricAggregationLineageReference
    provenance_reference: MetricAggregationProvenanceReference
    authorization_decision_id: UUID | None = None
    authorization_revision: int | None = Field(default=None, ge=1)
    policy_revision: int = Field(ge=1)
    registry_revision: int | None = Field(default=None, ge=1)
    tenant_id: UUID
    organization_id: UUID
    actor_id: UUID
    agent_instance_id: UUID | None = None
    on_behalf_of_user_id: UUID | None = None
    classification: DataClassification
    requested_at: datetime

    @field_validator("metric_definition_ids")
    @classmethod
    def canonical_definitions(cls, value):
        return canonical(value, "metric_definition_ids", key=str)

    @field_validator("input_references")
    @classmethod
    def canonical_inputs(cls, value):
        expected = tuple(
            sorted(value, key=lambda x: (x.input_ordinal, str(x.aggregation_input_reference_id)))
        )
        ordinals = tuple(x.input_ordinal for x in value)
        if value != expected or ordinals != tuple(range(1, len(value) + 1)):
            raise MetricAggregationOrderingError("input references must have canonical ordinals")
        if len({x.aggregation_input_reference_id for x in value}) != len(value):
            raise DuplicateMetricAggregationError("duplicate aggregation input reference")
        return value

    @field_validator("requested_at")
    @classmethod
    def aware_requested(cls, value):
        return aware(value, "requested_at")


class MetricAggregationRecord(MetricsModel):
    metric_aggregation_record_id: UUID
    record_version: MetricAggregationRecordVersion
    metric_aggregation_request_id: UUID
    metric_result_bundle_id: UUID
    aggregation_policy_id: UUID
    aggregation_method: MetricAggregationMethod
    aggregation_scope: MetricAggregationScope
    aggregation_window_id: UUID
    grouping_specification_id: UUID | None = None
    input_reference_ids: tuple[UUID, ...] = Field(min_length=1)
    output_value_type: MetricValueType
    aggregate_value: MetricValue | None = None
    status: MetricAggregationRecordStatus
    reason_codes: tuple[str, ...]
    original_aggregation_record_id: UUID | None = None
    invalidation_reference: str | None = Field(default=None, max_length=300)
    lineage_reference: MetricAggregationLineageReference
    provenance_reference: MetricAggregationProvenanceReference
    policy_revision: int = Field(ge=1)
    authorization_revision: int | None = Field(default=None, ge=1)
    registry_revision: int | None = Field(default=None, ge=1)
    tenant_id: UUID
    organization_id: UUID
    actor_id: UUID
    agent_instance_id: UUID | None = None
    classification: DataClassification
    recorded_at: datetime

    @field_validator("input_reference_ids")
    @classmethod
    def canonical_inputs(cls, value):
        return canonical(value, "input_reference_ids", key=str)

    @field_validator("reason_codes")
    @classmethod
    def canonical_reasons(cls, value):
        if any(not x or len(x) > 100 or not x.replace("_", "").isalnum() for x in value):
            raise MetricAggregationRecordError("aggregation reason code is invalid")
        return canonical(value, "reason_codes")

    @field_validator("recorded_at")
    @classmethod
    def aware_recorded(cls, value):
        return aware(value, "recorded_at")

    @model_validator(mode="after")
    def valid_status(self):
        recorded = self.status is MetricAggregationRecordStatus.RECORDED
        if recorded != (self.aggregate_value is not None) or (recorded and self.reason_codes):
            raise MetricAggregationRecordError("aggregation status and supplied value mismatch")
        if self.status is MetricAggregationRecordStatus.UNAVAILABLE and not self.reason_codes:
            raise MetricAggregationRecordError("unavailable aggregation requires reason")
        invalidated = self.status is MetricAggregationRecordStatus.INVALIDATED
        metadata = (
            self.original_aggregation_record_id is not None
            and self.invalidation_reference is not None
        )
        if (
            invalidated != metadata
            or self.original_aggregation_record_id == self.metric_aggregation_record_id
        ):
            raise MetricAggregationRecordError("aggregation invalidation metadata mismatch")
        if (
            self.aggregate_value is not None
            and self.aggregate_value.value_type is not self.output_value_type
        ):
            raise MetricAggregationRecordError("aggregate value type mismatch")
        return self


class MetricAggregationBundle(MetricsModel):
    metric_aggregation_bundle_id: UUID
    bundle_version: MetricAggregationBundleVersion
    metric_result_bundle_id: UUID
    aggregation_requests: tuple[MetricAggregationRequest, ...] = Field(min_length=1)
    aggregation_records: tuple[MetricAggregationRecord, ...] = Field(min_length=1)
    aggregation_windows: tuple[MetricAggregationWindow, ...] = Field(min_length=1)
    grouping_specifications: tuple[MetricAggregationGroupingSpecification, ...] = ()
    lineage_references: tuple[MetricAggregationLineageReference, ...] = Field(min_length=1)
    provenance_references: tuple[MetricAggregationProvenanceReference, ...] = Field(min_length=1)
    tenant_id: UUID
    organization_id: UUID
    classification: DataClassification
    root_lineage_id: UUID
    root_lineage_digest_reference: str = Field(min_length=1, max_length=300)
    audit_metadata: MetricAggregationAuditMetadata | None = None
    created_at: datetime

    @field_validator("created_at")
    @classmethod
    def aware_created(cls, value):
        return aware(value, "created_at")


class MetricAggregationBundleRequest(MetricsModel):
    metric_result_bundle: MetricResultBundle
    aggregation_policies: tuple[MetricAggregationPolicy, ...] = Field(min_length=1)
    aggregation_requests: tuple[MetricAggregationRequest, ...] = Field(min_length=1)
    aggregation_records: tuple[MetricAggregationRecord, ...] = Field(min_length=1)
    aggregation_windows: tuple[MetricAggregationWindow, ...] = Field(min_length=1)
    grouping_specifications: tuple[MetricAggregationGroupingSpecification, ...] = ()
    lineage_references: tuple[MetricAggregationLineageReference, ...] = Field(min_length=1)
    provenance_references: tuple[MetricAggregationProvenanceReference, ...] = Field(min_length=1)
    metric_aggregation_bundle_id: UUID
    bundle_version: MetricAggregationBundleVersion
    audit_metadata: MetricAggregationAuditMetadata | None = None
    tenant_id: UUID
    organization_id: UUID
    classification: DataClassification
    root_lineage_id: UUID
    root_lineage_digest_reference: str = Field(min_length=1, max_length=300)
    created_at: datetime

    @field_validator("created_at")
    @classmethod
    def aware_created(cls, value):
        return aware(value, "created_at")


def _not_lower(actual: DataClassification, *required: DataClassification) -> None:
    order = tuple(DataClassification)
    if any(order.index(actual) < order.index(item) for item in required):
        raise MetricAggregationClassificationError("metric aggregation classification downgrade")


def validate_metric_aggregation_window(window: MetricAggregationWindow) -> None:
    markers = (
        window.start_at is not None or window.end_at is not None,
        window.evaluation_pipeline_id is not None,
        window.evaluation_run_request_id is not None,
        window.cross_validation_plan_id is not None,
        bool(window.cross_validation_run_ids),
        window.policy_revision is not None,
        window.registry_revision is not None,
        window.dataset_manifest_reference_id is not None,
        window.dataset_split_reference_id is not None,
    )
    required = {
        MetricAggregationWindowType.EXPLICIT_RESULT_SET: True,
        MetricAggregationWindowType.EXPLICIT_TIME_RANGE: window.start_at is not None
        and window.end_at is not None,
        MetricAggregationWindowType.EVALUATION_PIPELINE: window.evaluation_pipeline_id is not None,
        MetricAggregationWindowType.EVALUATION_RUN: window.evaluation_run_request_id is not None,
        MetricAggregationWindowType.CROSS_VALIDATION_PLAN: window.cross_validation_plan_id
        is not None,
        MetricAggregationWindowType.CROSS_VALIDATION_RUN_SET: bool(window.cross_validation_run_ids),
        MetricAggregationWindowType.POLICY_REVISION: window.policy_revision is not None,
        MetricAggregationWindowType.REGISTRY_REVISION: window.registry_revision is not None,
        MetricAggregationWindowType.DATASET_MANIFEST: window.dataset_manifest_reference_id
        is not None,
        MetricAggregationWindowType.DATASET_SPLIT: window.dataset_split_reference_id is not None,
    }
    expected = 0 if window.window_type is MetricAggregationWindowType.EXPLICIT_RESULT_SET else 1
    if not required[window.window_type] or sum(markers) != expected:
        raise MetricAggregationWindowError("window fields do not match window type")
    if window.start_at is not None and window.start_at > window.end_at:
        raise MetricAggregationWindowError("window time range is reversed")


def validate_metric_aggregation_grouping(
    grouping: MetricAggregationGroupingSpecification,
    *,
    tenant_id: UUID,
    organization_id: UUID,
    classification: DataClassification,
) -> None:
    if (grouping.tenant_id, grouping.organization_id) != (tenant_id, organization_id):
        raise MetricAggregationGroupingError("grouping scope mismatch")
    _not_lower(classification, grouping.classification)


def validate_metric_aggregation_input_reference(
    reference: MetricAggregationInputReference, result: MetricResult, bundle: MetricResultBundle
) -> None:
    actual = (
        reference.metric_result_id,
        reference.metric_result_version,
        reference.metric_definition_id,
        reference.metric_definition_version,
        reference.metric_observation_id,
        reference.trusted_source_binding_id,
        reference.metric_result_bundle_id,
        reference.tenant_id,
        reference.organization_id,
        reference.lineage_id,
        reference.lineage_digest_reference,
        reference.recorded_at,
    )
    expected = (
        result.metric_result_id,
        result.result_version.metric_result_version,
        result.metric_definition_id,
        result.metric_definition_version,
        result.metric_observation_id,
        result.trusted_source_binding_id,
        bundle.metric_result_bundle_id,
        result.tenant_id,
        result.organization_id,
        result.lineage_id,
        result.lineage_digest_reference,
        result.recorded_at,
    )
    if actual != expected:
        raise MetricAggregationInputError("aggregation input binding mismatch")
    _not_lower(reference.classification, result.classification)


def validate_metric_aggregation_lineage_reference(
    reference: MetricAggregationLineageReference,
    *,
    bundle: MetricResultBundle,
    policy: MetricAggregationPolicy,
    window_id: UUID,
    grouping_id: UUID | None,
    result_ids: tuple[UUID, ...],
    record_id: UUID | None = None,
) -> None:
    expected = (
        bundle.lineage_id,
        bundle.lineage_digest_reference,
        bundle.metric_result_bundle_id,
        tuple(sorted(result_ids, key=str)),
        policy.aggregation_policy_id,
        window_id,
        grouping_id,
    )
    actual = (
        reference.root_lineage_id,
        reference.root_lineage_digest_reference,
        reference.metric_result_bundle_id,
        reference.metric_result_ids,
        reference.aggregation_policy_id,
        reference.aggregation_window_id,
        reference.grouping_specification_id,
    )
    if actual != expected or record_id in reference.parent_aggregation_record_ids:
        raise MetricAggregationLineageError("aggregation lineage binding mismatch")


def validate_metric_aggregation_provenance_reference(
    reference: MetricAggregationProvenanceReference,
    *,
    bundle: MetricResultBundle,
    policy: MetricAggregationPolicy,
    window_id: UUID,
    grouping_id: UUID | None,
    result_ids: tuple[UUID, ...],
) -> None:
    selected = tuple(x for x in bundle.results if x.metric_result_id in result_ids)
    expected = (
        bundle.metric_result_bundle_id,
        bundle.bundle_version.metric_result_bundle_version,
        tuple(sorted({x.metric_definition_id for x in selected}, key=str)),
        tuple(sorted(result_ids, key=str)),
        tuple(sorted({x.trusted_source_binding_id for x in selected}, key=str)),
        policy.aggregation_policy_id,
        policy.policy_version,
        window_id,
        grouping_id,
        policy.policy_revision,
    )
    actual = (
        reference.metric_result_bundle_id,
        reference.metric_result_bundle_version,
        reference.metric_definition_ids,
        reference.metric_result_ids,
        reference.trusted_source_binding_ids,
        reference.aggregation_policy_id,
        reference.aggregation_policy_version,
        reference.aggregation_window_id,
        reference.grouping_specification_id,
        reference.policy_revision,
    )
    if actual != expected:
        raise MetricAggregationProvenanceError("aggregation provenance binding mismatch")


def validate_metric_aggregation_request(
    request: MetricAggregationRequest, bundle: MetricResultBundle, policy: MetricAggregationPolicy
) -> None:
    validate_metric_result_bundle(bundle)
    definition = next(
        (x for x in bundle.definitions if x.metric_definition_id == policy.metric_definition_id),
        None,
    )
    if definition is None:
        raise MetricAggregationRequestError("aggregation policy definition is absent")
    validate_metric_aggregation_policy(policy, definition)
    binding = (
        request.metric_result_bundle_id,
        request.metric_result_bundle_version,
        request.aggregation_policy_id,
        request.aggregation_policy_version,
        request.policy_revision,
        request.tenant_id,
        request.organization_id,
    )
    expected = (
        bundle.metric_result_bundle_id,
        bundle.bundle_version.metric_result_bundle_version,
        policy.aggregation_policy_id,
        policy.policy_version,
        policy.policy_revision,
        bundle.tenant_id,
        bundle.organization_id,
    )
    if binding != expected:
        raise MetricAggregationRequestError("aggregation request binding mismatch")
    if (
        max(bundle.created_at, policy.created_at, request.aggregation_window.created_at)
        > request.requested_at
    ):
        raise MetricAggregationRequestError("aggregation request precedes source metadata")
    grouping_id = None
    if request.grouping_specification is not None:
        grouping = request.grouping_specification
        grouping_id = grouping.grouping_specification_id
        validate_metric_aggregation_grouping(
            grouping,
            tenant_id=request.tenant_id,
            organization_id=request.organization_id,
            classification=request.classification,
        )
        if (
            grouping.created_at > request.requested_at
            or grouping.grouping_key_references != policy.grouping_key_references
        ):
            raise MetricAggregationGroupingError("grouping and policy mismatch")
    elif policy.grouping_key_references:
        raise MetricAggregationGroupingError("aggregation policy requires grouping")
    result_map = {x.metric_result_id: x for x in bundle.results}
    selected = []
    for reference in request.input_references:
        result = result_map.get(reference.metric_result_id)
        if result is None:
            raise MetricAggregationInputError("aggregation input result is absent")
        validate_metric_aggregation_input_reference(reference, result, bundle)
        if (
            result.metric_definition_id != policy.metric_definition_id
            or result.value_type is not policy.input_value_type
        ):
            raise MetricAggregationInputError("aggregation input policy mismatch")
        selected.append(result)
    if len(selected) < policy.minimum_result_count:
        raise MetricAggregationInputError("aggregation input count below policy minimum")
    if any(x.recorded_at > request.requested_at for x in selected):
        raise MetricAggregationInputError("aggregation input follows request")
    nonrecorded = any(x.status is not MetricResultStatus.RECORDED for x in selected)
    if nonrecorded and policy.missing_value_policy in (
        MetricMissingValuePolicy.REJECT_MISSING,
        MetricMissingValuePolicy.REQUIRE_ALL_RECORDED,
    ):
        raise MetricAggregationInputError("aggregation policy rejects unavailable input")
    result_ids = tuple(x.metric_result_id for x in selected)
    definitions = tuple(sorted({x.metric_definition_id for x in selected}, key=str))
    if request.metric_definition_ids != definitions:
        raise MetricAggregationRequestError("aggregation definition set mismatch")
    validate_metric_aggregation_lineage_reference(
        request.lineage_reference,
        bundle=bundle,
        policy=policy,
        window_id=request.aggregation_window.aggregation_window_id,
        grouping_id=grouping_id,
        result_ids=result_ids,
    )
    validate_metric_aggregation_provenance_reference(
        request.provenance_reference,
        bundle=bundle,
        policy=policy,
        window_id=request.aggregation_window.aggregation_window_id,
        grouping_id=grouping_id,
        result_ids=result_ids,
    )
    _not_lower(
        request.classification,
        bundle.classification,
        policy.classification,
        *(x.classification for x in selected),
    )


def validate_metric_aggregation_record(
    record: MetricAggregationRecord,
    request: MetricAggregationRequest,
    policy: MetricAggregationPolicy,
) -> None:
    grouping_id = (
        None
        if request.grouping_specification is None
        else request.grouping_specification.grouping_specification_id
    )
    actual = (
        record.metric_aggregation_request_id,
        record.metric_result_bundle_id,
        record.aggregation_policy_id,
        record.aggregation_method,
        record.aggregation_scope,
        record.aggregation_window_id,
        record.grouping_specification_id,
        record.input_reference_ids,
        record.output_value_type,
        record.tenant_id,
        record.organization_id,
    )
    expected = (
        request.metric_aggregation_request_id,
        request.metric_result_bundle_id,
        policy.aggregation_policy_id,
        policy.aggregation_method,
        request.aggregation_scope,
        request.aggregation_window.aggregation_window_id,
        grouping_id,
        tuple(
            sorted((x.aggregation_input_reference_id for x in request.input_references), key=str)
        ),
        policy.output_value_type,
        request.tenant_id,
        request.organization_id,
    )
    if actual != expected:
        raise MetricAggregationRecordError("aggregation record binding mismatch")
    if record.recorded_at < request.requested_at:
        raise MetricAggregationRecordError("aggregation record precedes request")
    if (
        record.lineage_reference != request.lineage_reference
        or record.provenance_reference != request.provenance_reference
    ):
        raise MetricAggregationRecordError("record lineage or provenance mismatch")
    _not_lower(record.classification, request.classification, policy.classification)


def _ordered(items: tuple, key, name: str) -> None:
    if items != tuple(sorted(items, key=key)):
        raise MetricAggregationOrderingError(f"{name} must be in canonical caller order")


def validate_metric_aggregation_bundle(
    bundle: MetricAggregationBundle,
    source_bundle: MetricResultBundle,
    policies: tuple[MetricAggregationPolicy, ...],
) -> None:
    source = (
        source_bundle.metric_result_bundle_id,
        source_bundle.tenant_id,
        source_bundle.organization_id,
        source_bundle.lineage_id,
        source_bundle.lineage_digest_reference,
    )
    target = (
        bundle.metric_result_bundle_id,
        bundle.tenant_id,
        bundle.organization_id,
        bundle.root_lineage_id,
        bundle.root_lineage_digest_reference,
    )
    if source != target:
        raise MetricAggregationBundleError("aggregation source bundle mismatch")
    collections = (
        (
            bundle.aggregation_windows,
            lambda x: (
                tuple(MetricAggregationWindowType).index(x.window_type),
                str(x.aggregation_window_id),
            ),
            "windows",
            lambda x: x.aggregation_window_id,
        ),
        (
            bundle.grouping_specifications,
            lambda x: str(x.grouping_specification_id),
            "groupings",
            lambda x: x.grouping_specification_id,
        ),
        (
            bundle.aggregation_requests,
            lambda x: (x.requested_at, str(x.metric_aggregation_request_id)),
            "requests",
            lambda x: x.metric_aggregation_request_id,
        ),
        (
            bundle.aggregation_records,
            lambda x: (x.recorded_at, str(x.metric_aggregation_record_id)),
            "records",
            lambda x: x.metric_aggregation_record_id,
        ),
        (
            bundle.lineage_references,
            lambda x: str(x.aggregation_lineage_reference_id),
            "lineages",
            lambda x: x.aggregation_lineage_reference_id,
        ),
        (
            bundle.provenance_references,
            lambda x: str(x.aggregation_provenance_reference_id),
            "provenances",
            lambda x: x.aggregation_provenance_reference_id,
        ),
    )
    for items, order, name, identity in collections:
        _ordered(items, order, name)
        if len({identity(x) for x in items}) != len(items):
            raise DuplicateMetricAggregationError(f"duplicate aggregation {name}")
    policy_map = {x.aggregation_policy_id: x for x in policies}
    request_map = {x.metric_aggregation_request_id: x for x in bundle.aggregation_requests}
    windows = {x.aggregation_window_id for x in bundle.aggregation_windows}
    groups = {x.grouping_specification_id for x in bundle.grouping_specifications}
    lineages = {x.aggregation_lineage_reference_id for x in bundle.lineage_references}
    provenances = {x.aggregation_provenance_reference_id for x in bundle.provenance_references}
    for request in bundle.aggregation_requests:
        policy = policy_map.get(request.aggregation_policy_id)
        grouping = request.grouping_specification
        if (
            policy is None
            or request.aggregation_window.aggregation_window_id not in windows
            or (grouping is not None and grouping.grouping_specification_id not in groups)
            or request.lineage_reference.aggregation_lineage_reference_id not in lineages
            or request.provenance_reference.aggregation_provenance_reference_id not in provenances
        ):
            raise MetricAggregationBundleError("aggregation request has orphan reference")
        validate_metric_aggregation_request(request, source_bundle, policy)
    for record in bundle.aggregation_records:
        request = request_map.get(record.metric_aggregation_request_id)
        if request is None:
            raise MetricAggregationBundleError("aggregation record is orphaned")
        validate_metric_aggregation_record(
            record, request, policy_map[record.aggregation_policy_id]
        )
        if record.recorded_at > bundle.created_at:
            raise MetricAggregationBundleError("aggregation record follows bundle")
    _not_lower(
        bundle.classification,
        source_bundle.classification,
        *(x.classification for x in bundle.aggregation_records),
    )
    if bundle.audit_metadata is not None:
        audit = bundle.audit_metadata
        statuses = [x.status for x in bundle.aggregation_records]
        actual = (
            audit.metric_aggregation_bundle_id,
            audit.bundle_version,
            audit.request_count,
            audit.record_count,
            audit.recorded_count,
            audit.unavailable_count,
            audit.not_applicable_count,
            audit.invalidated_count,
            audit.input_reference_count,
            audit.grouping_specification_count,
            audit.window_count,
            audit.tenant_id,
            audit.organization_id,
            audit.created_at,
        )
        expected = (
            bundle.metric_aggregation_bundle_id,
            bundle.bundle_version.metric_aggregation_bundle_version,
            len(bundle.aggregation_requests),
            len(bundle.aggregation_records),
            statuses.count(MetricAggregationRecordStatus.RECORDED),
            statuses.count(MetricAggregationRecordStatus.UNAVAILABLE),
            statuses.count(MetricAggregationRecordStatus.NOT_APPLICABLE),
            statuses.count(MetricAggregationRecordStatus.INVALIDATED),
            len(
                {
                    x.aggregation_input_reference_id
                    for r in bundle.aggregation_requests
                    for x in r.input_references
                }
            ),
            len(bundle.grouping_specifications),
            len(bundle.aggregation_windows),
            bundle.tenant_id,
            bundle.organization_id,
            bundle.created_at,
        )
        if actual != expected:
            raise MetricAggregationAuditError("aggregation audit metadata mismatch")
        _not_lower(audit.classification, bundle.classification)


def build_metric_aggregation_bundle(
    request: MetricAggregationBundleRequest,
) -> MetricAggregationBundle:
    validate_metric_result_bundle(request.metric_result_bundle)
    bundle = MetricAggregationBundle(
        metric_aggregation_bundle_id=request.metric_aggregation_bundle_id,
        bundle_version=request.bundle_version,
        metric_result_bundle_id=request.metric_result_bundle.metric_result_bundle_id,
        aggregation_requests=request.aggregation_requests,
        aggregation_records=request.aggregation_records,
        aggregation_windows=request.aggregation_windows,
        grouping_specifications=request.grouping_specifications,
        lineage_references=request.lineage_references,
        provenance_references=request.provenance_references,
        tenant_id=request.tenant_id,
        organization_id=request.organization_id,
        classification=request.classification,
        root_lineage_id=request.root_lineage_id,
        root_lineage_digest_reference=request.root_lineage_digest_reference,
        audit_metadata=request.audit_metadata,
        created_at=request.created_at,
    )
    validate_metric_aggregation_bundle(
        bundle, request.metric_result_bundle, request.aggregation_policies
    )
    return bundle
