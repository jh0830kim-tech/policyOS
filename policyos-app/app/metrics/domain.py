"""Immutable, metadata-only evaluation metric contracts and pure validation."""

from datetime import datetime
from decimal import Decimal
from enum import StrEnum
from types import MappingProxyType
from typing import Annotated, Literal
from uuid import UUID

from pydantic import Field, field_validator, model_validator

from app.ai.privacy import DataClassification
from app.metrics._base import MetricsModel, aware, canonical, not_lower
from app.metrics.errors import (
    DuplicateMetricError,
    MetricAggregationPolicyError,
    MetricAuditMetadataError,
    MetricBindingMismatchError,
    MetricBundleError,
    MetricDefinitionError,
    MetricLineageError,
    MetricObservationError,
    MetricResultError,
    MetricValueError,
    MetricVersionError,
)
from app.source_bindings import (
    TrustedSourceBinding,
    TrustedSourceBindingStatus,
    TrustedSourceType,
)


class MetricCategory(StrEnum):
    QUALITY = "quality"
    GROUNDEDNESS = "groundedness"
    FACTUALITY = "factuality"
    CITATION = "citation"
    POLICY_COMPLIANCE = "policy_compliance"
    SECURITY = "security"
    PRIVACY = "privacy"
    SAFETY = "safety"
    COMPLETENESS = "completeness"
    CONSISTENCY = "consistency"
    RELEVANCE = "relevance"
    LATENCY = "latency"
    COST = "cost"
    RESOURCE_USAGE = "resource_usage"
    RELIABILITY = "reliability"
    AVAILABILITY = "availability"
    CUSTOM_GOVERNED = "custom_governed"


class MetricValueType(StrEnum):
    INTEGER = "integer"
    DECIMAL = "decimal"
    BOOLEAN = "boolean"
    DURATION = "duration"
    CURRENCY = "currency"
    COUNT = "count"
    RATIO = "ratio"
    PERCENTAGE = "percentage"
    ENUM_REFERENCE = "enum_reference"
    TEXT_REFERENCE = "text_reference"


class MetricDirection(StrEnum):
    HIGHER_IS_PREFERRED = "higher_is_preferred"
    LOWER_IS_PREFERRED = "lower_is_preferred"
    TARGET_IS_PREFERRED = "target_is_preferred"
    DESCRIPTIVE_ONLY = "descriptive_only"


class MetricMeasurementUnit(StrEnum):
    NONE = "none"
    COUNT = "count"
    RATIO = "ratio"
    PERCENT = "percent"
    MILLISECONDS = "milliseconds"
    SECONDS = "seconds"
    TOKENS = "tokens"
    BYTES = "bytes"
    CURRENCY_REFERENCE = "currency_reference"
    BOOLEAN = "boolean"
    ENUM_REFERENCE = "enum_reference"
    TEXT_REFERENCE = "text_reference"


class MetricScope(StrEnum):
    EVALUATION_PLAN = "evaluation_plan"
    EVALUATION_EXECUTION = "evaluation_execution"
    EVIDENCE_BUNDLE = "evidence_bundle"
    VALIDATION_REPORT = "validation_report"
    EVALUATION_PIPELINE = "evaluation_pipeline"
    CROSS_VALIDATION_PLAN = "cross_validation_plan"
    CROSS_VALIDATION_RESULT = "cross_validation_result"
    CONSENSUS_PACKAGE = "consensus_package"
    MODEL_INVOCATION = "model_invocation"
    PROVIDER_INVOCATION = "provider_invocation"
    MCP_OPERATION = "mcp_operation"
    CROSS_VALIDATION_RUN = "cross_validation_run"
    SECRETARY_HANDOFF = "secretary_handoff"
    SECURITY_EVENT = "security_event"
    QUARANTINE_DECISION = "quarantine_decision"
    OBSERVABILITY_BUNDLE = "observability_bundle"


_SOURCE_SCOPE = MappingProxyType(
    {
        TrustedSourceType.EVALUATION_PLAN: MetricScope.EVALUATION_PLAN,
        TrustedSourceType.EVALUATION_EXECUTION_RECORD: MetricScope.EVALUATION_EXECUTION,
        TrustedSourceType.EVALUATION_EVIDENCE_BUNDLE: MetricScope.EVIDENCE_BUNDLE,
        TrustedSourceType.EVALUATION_VALIDATION_REPORT: MetricScope.VALIDATION_REPORT,
        TrustedSourceType.EVALUATION_PIPELINE_RECORD: MetricScope.EVALUATION_PIPELINE,
        TrustedSourceType.CROSS_VALIDATION_PLAN: MetricScope.CROSS_VALIDATION_PLAN,
        TrustedSourceType.CROSS_VALIDATION_RUN_COLLECTION: MetricScope.CROSS_VALIDATION_RUN,
        TrustedSourceType.CONSENSUS_PACKAGE: MetricScope.CONSENSUS_PACKAGE,
        TrustedSourceType.SECRETARY_HANDOFF: MetricScope.SECRETARY_HANDOFF,
        TrustedSourceType.MODEL_RUN_RESULT: MetricScope.CROSS_VALIDATION_RESULT,
        TrustedSourceType.MODEL_INVOCATION_PERMIT: MetricScope.MODEL_INVOCATION,
        TrustedSourceType.PROVIDER_INVOCATION_AUDIT: MetricScope.PROVIDER_INVOCATION,
        TrustedSourceType.MCP_AUTHORIZATION_DECISION: MetricScope.MCP_OPERATION,
        TrustedSourceType.MCP_INVOCATION_PERMIT: MetricScope.MCP_OPERATION,
        TrustedSourceType.MCP_TOOL_RESULT: MetricScope.MCP_OPERATION,
        TrustedSourceType.SECURITY_VIOLATION: MetricScope.SECURITY_EVENT,
        TrustedSourceType.QUARANTINE_DECISION: MetricScope.QUARANTINE_DECISION,
        TrustedSourceType.SECRET_ACCESS_AUDIT: MetricScope.SECURITY_EVENT,
        TrustedSourceType.OBSERVABILITY_BUNDLE: MetricScope.OBSERVABILITY_BUNDLE,
    }
)

_VALUE_UNITS = MappingProxyType(
    {
        MetricValueType.INTEGER: frozenset({MetricMeasurementUnit.NONE}),
        MetricValueType.DECIMAL: frozenset(
            {
                MetricMeasurementUnit.NONE,
                MetricMeasurementUnit.RATIO,
            }
        ),
        MetricValueType.BOOLEAN: frozenset({MetricMeasurementUnit.BOOLEAN}),
        MetricValueType.DURATION: frozenset(
            {
                MetricMeasurementUnit.MILLISECONDS,
                MetricMeasurementUnit.SECONDS,
            }
        ),
        MetricValueType.CURRENCY: frozenset({MetricMeasurementUnit.CURRENCY_REFERENCE}),
        MetricValueType.COUNT: frozenset(
            {
                MetricMeasurementUnit.COUNT,
                MetricMeasurementUnit.TOKENS,
                MetricMeasurementUnit.BYTES,
            }
        ),
        MetricValueType.RATIO: frozenset({MetricMeasurementUnit.RATIO}),
        MetricValueType.PERCENTAGE: frozenset({MetricMeasurementUnit.PERCENT}),
        MetricValueType.ENUM_REFERENCE: frozenset({MetricMeasurementUnit.ENUM_REFERENCE}),
        MetricValueType.TEXT_REFERENCE: frozenset({MetricMeasurementUnit.TEXT_REFERENCE}),
    }
)


class MetricResultStatus(StrEnum):
    RECORDED = "recorded"
    UNAVAILABLE = "unavailable"
    NOT_APPLICABLE = "not_applicable"
    INVALIDATED = "invalidated"


class MetricAggregationMethod(StrEnum):
    NONE = "none"
    COUNT = "count"
    SUM = "sum"
    MEAN = "mean"
    MEDIAN = "median"
    MINIMUM = "minimum"
    MAXIMUM = "maximum"
    WEIGHTED_MEAN = "weighted_mean"
    PERCENTILE = "percentile"
    LATEST = "latest"
    FIRST = "first"
    ALL_VALUES_REFERENCE = "all_values_reference"


class MetricMissingValuePolicy(StrEnum):
    REJECT_MISSING = "reject_missing"
    EXCLUDE_UNAVAILABLE = "exclude_unavailable"
    REQUIRE_ALL_RECORDED = "require_all_recorded"
    PROPAGATE_UNAVAILABLE = "propagate_unavailable"


class MetricDefinitionVersion(MetricsModel):
    metric_definition_version: str = Field(min_length=1, max_length=100)
    metric_contract_version: str = Field(min_length=1, max_length=100)
    metric_schema_version: str = Field(pattern=r"^metric-definition-schema-v1$")


class MetricResultVersion(MetricsModel):
    metric_result_version: str = Field(min_length=1, max_length=100)
    metric_result_contract_version: str = Field(min_length=1, max_length=100)
    metric_result_schema_version: str = Field(pattern=r"^metric-result-schema-v1$")


class MetricResultBundleVersion(MetricsModel):
    metric_result_bundle_version: str = Field(min_length=1, max_length=100)
    metric_bundle_contract_version: str = Field(min_length=1, max_length=100)
    metric_bundle_schema_version: str = Field(pattern=r"^metric-bundle-schema-v1$")


class MetricDefinition(MetricsModel):
    metric_definition_id: UUID
    metric_key: str = Field(pattern=r"^[a-z][a-z0-9_.-]{0,99}$")
    display_name_reference: str = Field(min_length=1, max_length=300)
    category: MetricCategory
    value_type: MetricValueType
    measurement_unit: MetricMeasurementUnit
    direction: MetricDirection
    supported_scopes: tuple[MetricScope, ...] = Field(min_length=1)
    definition_version: MetricDefinitionVersion
    owner_reference: str = Field(min_length=1, max_length=300)
    purpose: str = Field(pattern=r"^[a-z][a-z0-9_.-]{0,99}$")
    classification: DataClassification
    tenant_id: UUID
    organization_id: UUID
    policy_revision: int = Field(ge=1)
    registry_revision: int | None = Field(default=None, ge=1)
    definition_document_reference: str = Field(min_length=1, max_length=300)
    allowed_enum_value_references: tuple[str, ...] = ()
    created_at: datetime

    @field_validator("supported_scopes")
    @classmethod
    def canonical_scopes(cls, value):
        return canonical(value, "supported_scopes", key=lambda item: tuple(MetricScope).index(item))

    @field_validator("allowed_enum_value_references")
    @classmethod
    def canonical_enum_references(cls, value):
        return canonical(value, "allowed_enum_value_references")

    @field_validator("created_at")
    @classmethod
    def aware_created(cls, value):
        return aware(value, "created_at")

    @model_validator(mode="after")
    def valid_enum_contract(self):
        if bool(self.allowed_enum_value_references) != (
            self.value_type is MetricValueType.ENUM_REFERENCE
        ):
            raise MetricDefinitionError("enum references and metric value type mismatch")
        return self


class MetricObservation(MetricsModel):
    metric_observation_id: UUID
    metric_definition_id: UUID
    metric_definition_version: MetricDefinitionVersion
    trusted_source_binding_id: UUID
    trusted_source_type: TrustedSourceType
    metric_scope: MetricScope
    evaluation_plan_id: UUID | None = None
    evaluation_execution_id: UUID | None = None
    evidence_bundle_id: UUID | None = None
    validation_report_id: UUID | None = None
    evaluation_pipeline_id: UUID | None = None
    cross_validation_plan_id: UUID | None = None
    cross_validation_run_id: UUID | None = None
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
    lineage_id: UUID
    lineage_digest_reference: str = Field(min_length=1, max_length=300)
    observed_at: datetime

    @field_validator("observed_at")
    @classmethod
    def aware_observed(cls, value):
        return aware(value, "observed_at")


class IntegerMetricValue(MetricsModel):
    value_type: Literal[MetricValueType.INTEGER]
    value: int


class DecimalMetricValue(MetricsModel):
    value_type: Literal[MetricValueType.DECIMAL]
    value: Decimal

    @field_validator("value")
    @classmethod
    def finite(cls, value):
        if not value.is_finite():
            raise MetricValueError("decimal value must be finite")
        return value


class BooleanMetricValue(MetricsModel):
    value_type: Literal[MetricValueType.BOOLEAN]
    value: bool


class DurationMetricValue(MetricsModel):
    value_type: Literal[MetricValueType.DURATION]
    value: Decimal = Field(ge=0)
    unit: Literal[MetricMeasurementUnit.MILLISECONDS, MetricMeasurementUnit.SECONDS]


class CurrencyMetricValue(MetricsModel):
    value_type: Literal[MetricValueType.CURRENCY]
    value: Decimal
    currency_code_reference: str = Field(pattern=r"^[A-Z]{3}$")


class CountMetricValue(MetricsModel):
    value_type: Literal[MetricValueType.COUNT]
    value: int = Field(ge=0)


class RatioMetricValue(MetricsModel):
    value_type: Literal[MetricValueType.RATIO]
    value: Decimal
    ratio_basis_reference: str = Field(min_length=1, max_length=300)


class PercentageMetricValue(MetricsModel):
    value_type: Literal[MetricValueType.PERCENTAGE]
    value: Decimal = Field(ge=0, le=100)


class EnumReferenceMetricValue(MetricsModel):
    value_type: Literal[MetricValueType.ENUM_REFERENCE]
    value_reference: str = Field(min_length=1, max_length=300)


class TextReferenceMetricValue(MetricsModel):
    value_type: Literal[MetricValueType.TEXT_REFERENCE]
    value_reference: str = Field(min_length=1, max_length=300)


MetricValue = Annotated[
    IntegerMetricValue
    | DecimalMetricValue
    | BooleanMetricValue
    | DurationMetricValue
    | CurrencyMetricValue
    | CountMetricValue
    | RatioMetricValue
    | PercentageMetricValue
    | EnumReferenceMetricValue
    | TextReferenceMetricValue,
    Field(discriminator="value_type"),
]


class MetricResult(MetricsModel):
    metric_result_id: UUID
    metric_definition_id: UUID
    metric_definition_version: MetricDefinitionVersion
    metric_observation_id: UUID
    trusted_source_binding_id: UUID
    value_type: MetricValueType
    value: MetricValue | None = None
    status: MetricResultStatus
    reason_codes: tuple[str, ...]
    original_result_reference: UUID | None = None
    invalidation_reference: str | None = Field(default=None, max_length=300)
    result_version: MetricResultVersion
    policy_revision: int = Field(ge=1)
    authorization_revision: int | None = Field(default=None, ge=1)
    registry_revision: int | None = Field(default=None, ge=1)
    tenant_id: UUID
    organization_id: UUID
    actor_id: UUID
    agent_instance_id: UUID | None = None
    classification: DataClassification
    lineage_id: UUID
    lineage_digest_reference: str = Field(min_length=1, max_length=300)
    recorded_at: datetime

    @field_validator("reason_codes")
    @classmethod
    def canonical_reasons(cls, value):
        for item in value:
            if not item or len(item) > 100 or not item.replace("_", "").isalnum():
                raise MetricResultError("metric result reason code is invalid")
        return canonical(value, "reason_codes")

    @field_validator("recorded_at")
    @classmethod
    def aware_recorded(cls, value):
        return aware(value, "recorded_at")

    @model_validator(mode="after")
    def valid_status(self):
        if self.status is MetricResultStatus.RECORDED:
            if self.value is None or self.reason_codes:
                raise MetricResultError("recorded metric result requires only a value")
        elif self.value is not None:
            raise MetricResultError("non-recorded metric result cannot contain a value")
        if self.status is MetricResultStatus.UNAVAILABLE and not self.reason_codes:
            raise MetricResultError("unavailable metric result requires a reason")
        invalidated = self.status is MetricResultStatus.INVALIDATED
        complete = (
            self.original_result_reference is not None and self.invalidation_reference is not None
        )
        if invalidated != complete:
            raise MetricResultError("invalidated metric result metadata mismatch")
        if self.value is not None and self.value.value_type is not self.value_type:
            raise MetricValueError("metric result value type mismatch")
        return self


class MetricAggregationPolicy(MetricsModel):
    aggregation_policy_id: UUID
    metric_definition_id: UUID
    metric_definition_version: MetricDefinitionVersion
    aggregation_method: MetricAggregationMethod
    input_value_type: MetricValueType
    output_value_type: MetricValueType
    minimum_result_count: int = Field(ge=1)
    percentile_reference: str | None = Field(default=None, max_length=300)
    weight_policy_reference: str | None = Field(default=None, max_length=300)
    grouping_key_references: tuple[str, ...]
    missing_value_policy: MetricMissingValuePolicy
    policy_version: str = Field(min_length=1, max_length=100)
    policy_revision: int = Field(ge=1)
    tenant_id: UUID
    organization_id: UUID
    classification: DataClassification
    created_at: datetime

    @field_validator("grouping_key_references")
    @classmethod
    def canonical_groups(cls, value):
        return canonical(value, "grouping_key_references")

    @field_validator("created_at")
    @classmethod
    def aware_created(cls, value):
        return aware(value, "created_at")

    @model_validator(mode="after")
    def method_metadata(self):
        percentile = self.aggregation_method is MetricAggregationMethod.PERCENTILE
        weighted = self.aggregation_method is MetricAggregationMethod.WEIGHTED_MEAN
        if percentile != (self.percentile_reference is not None):
            raise MetricAggregationPolicyError("percentile policy metadata mismatch")
        if weighted != (self.weight_policy_reference is not None):
            raise MetricAggregationPolicyError("weight policy metadata mismatch")
        return self


class MetricResultBundleAuditMetadata(MetricsModel):
    metric_result_bundle_id: UUID
    bundle_version: str = Field(min_length=1, max_length=100)
    definition_count: int = Field(ge=1)
    observation_count: int = Field(ge=1)
    result_count: int = Field(ge=1)
    recorded_result_count: int = Field(ge=0)
    unavailable_result_count: int = Field(ge=0)
    not_applicable_result_count: int = Field(ge=0)
    invalidated_result_count: int = Field(ge=0)
    trusted_binding_count: int = Field(ge=1)
    tenant_id: UUID
    organization_id: UUID
    classification: DataClassification
    policy_revision: int = Field(ge=1)
    registry_revision: int | None = Field(default=None, ge=1)
    created_at: datetime

    @field_validator("created_at")
    @classmethod
    def aware_created(cls, value):
        return aware(value, "created_at")


class MetricResultBundle(MetricsModel):
    metric_result_bundle_id: UUID
    bundle_version: MetricResultBundleVersion
    definitions: tuple[MetricDefinition, ...] = Field(min_length=1)
    trusted_source_bindings: tuple[TrustedSourceBinding, ...] = Field(min_length=1)
    observations: tuple[MetricObservation, ...] = Field(min_length=1)
    results: tuple[MetricResult, ...] = Field(min_length=1)
    aggregation_policies: tuple[MetricAggregationPolicy, ...]
    evaluation_pipeline_id: UUID | None = None
    tenant_id: UUID
    organization_id: UUID
    classification: DataClassification
    lineage_id: UUID
    lineage_digest_reference: str = Field(min_length=1, max_length=300)
    audit_metadata: MetricResultBundleAuditMetadata | None = None
    created_at: datetime

    @field_validator("created_at")
    @classmethod
    def aware_created(cls, value):
        return aware(value, "created_at")

    @model_validator(mode="after")
    def valid_bundle(self):
        validate_metric_result_bundle(self)
        return self


class MetricResultBundleRequest(MetricsModel):
    metric_result_bundle_id: UUID
    bundle_version: MetricResultBundleVersion
    definitions: tuple[MetricDefinition, ...] = Field(min_length=1)
    trusted_source_bindings: tuple[TrustedSourceBinding, ...] = Field(min_length=1)
    observations: tuple[MetricObservation, ...] = Field(min_length=1)
    results: tuple[MetricResult, ...] = Field(min_length=1)
    aggregation_policies: tuple[MetricAggregationPolicy, ...]
    evaluation_pipeline_id: UUID | None = None
    audit_metadata: MetricResultBundleAuditMetadata | None = None
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


def validate_metric_definition(definition: MetricDefinition) -> None:
    if definition.definition_version.metric_schema_version != "metric-definition-schema-v1":
        raise MetricVersionError("unsupported metric definition schema")
    if definition.measurement_unit not in _VALUE_UNITS[definition.value_type]:
        raise MetricDefinitionError("metric definition value type and unit mismatch")


def validate_metric_value(value: MetricValue, definition: MetricDefinition) -> None:
    if value.value_type is not definition.value_type:
        raise MetricValueError("metric value and definition type mismatch")
    if isinstance(value, EnumReferenceMetricValue) and (
        value.value_reference not in definition.allowed_enum_value_references
    ):
        raise MetricValueError("metric enum reference is not allowed")


def validate_metric_observation(
    observation: MetricObservation,
    definition: MetricDefinition,
    binding: TrustedSourceBinding,
) -> None:
    if (
        observation.metric_definition_id != definition.metric_definition_id
        or observation.metric_definition_version != definition.definition_version
    ):
        raise MetricBindingMismatchError("metric observation definition mismatch")
    if binding.status is not TrustedSourceBindingStatus.ACTIVE:
        raise MetricObservationError("metric observation requires active trusted binding")
    mapped_scope = _SOURCE_SCOPE.get(binding.source_identity.source_type)
    if (
        mapped_scope is None
        or observation.metric_scope is not mapped_scope
        or observation.metric_scope not in definition.supported_scopes
        or observation.trusted_source_type is not binding.source_identity.source_type
        or observation.trusted_source_binding_id != binding.trusted_source_binding_id
    ):
        raise MetricObservationError("metric observation scope is unsupported")
    expected_scope = (definition.tenant_id, definition.organization_id)
    if (observation.tenant_id, observation.organization_id) != expected_scope or (
        binding.governance_context.tenant_id,
        binding.governance_context.organization_id,
    ) != expected_scope:
        raise MetricBindingMismatchError("metric observation tenant or organization mismatch")
    if (
        observation.lineage_id != binding.lineage_context.lineage_id
        or observation.lineage_digest_reference != binding.lineage_context.lineage_digest_reference
    ):
        raise MetricLineageError("metric observation lineage mismatch")
    if (
        definition.created_at > observation.observed_at
        or binding.created_at > observation.observed_at
    ):
        raise MetricObservationError("metric observation precedes its source")
    governance = binding.governance_context
    if (
        observation.authorization_decision_id is not None
        and observation.authorization_decision_id != governance.authorization_decision_id
    ):
        raise MetricBindingMismatchError("metric observation authorization mismatch")
    not_lower(
        observation.classification,
        definition.classification,
        governance.classification,
    )


def validate_metric_result(
    result: MetricResult,
    observation: MetricObservation,
    definition: MetricDefinition,
    binding: TrustedSourceBinding,
) -> None:
    if (
        result.metric_definition_id != definition.metric_definition_id
        or result.metric_definition_version != definition.definition_version
        or result.metric_observation_id != observation.metric_observation_id
        or result.trusted_source_binding_id != observation.trusted_source_binding_id
        or result.trusted_source_binding_id != binding.trusted_source_binding_id
    ):
        raise MetricBindingMismatchError("metric result binding mismatch")
    if result.value_type is not definition.value_type:
        raise MetricValueError("metric result definition value type mismatch")
    if result.value is not None:
        validate_metric_value(result.value, definition)
    if (result.tenant_id, result.organization_id, result.actor_id) != (
        observation.tenant_id,
        observation.organization_id,
        observation.actor_id,
    ):
        raise MetricBindingMismatchError("metric result scope or actor mismatch")
    if (
        result.lineage_id != observation.lineage_id
        or result.lineage_digest_reference != observation.lineage_digest_reference
    ):
        raise MetricLineageError("metric result lineage mismatch")
    if observation.observed_at > result.recorded_at:
        raise MetricResultError("metric result precedes observation")
    not_lower(
        result.classification,
        definition.classification,
        binding.governance_context.classification,
        observation.classification,
    )


def validate_metric_aggregation_policy(
    policy: MetricAggregationPolicy, definition: MetricDefinition
) -> None:
    if (
        policy.metric_definition_id != definition.metric_definition_id
        or policy.metric_definition_version != definition.definition_version
        or policy.input_value_type is not definition.value_type
        or (policy.tenant_id, policy.organization_id)
        != (definition.tenant_id, definition.organization_id)
    ):
        raise MetricAggregationPolicyError("metric aggregation policy binding mismatch")
    if (
        policy.aggregation_method
        in {
            MetricAggregationMethod.NONE,
            MetricAggregationMethod.LATEST,
            MetricAggregationMethod.FIRST,
            MetricAggregationMethod.ALL_VALUES_REFERENCE,
        }
        and policy.output_value_type is not policy.input_value_type
    ):
        raise MetricAggregationPolicyError("aggregation metadata value types mismatch")
    if (
        policy.aggregation_method is MetricAggregationMethod.COUNT
        and policy.output_value_type is not MetricValueType.COUNT
    ):
        raise MetricAggregationPolicyError("count aggregation metadata requires count output")
    not_lower(policy.classification, definition.classification)


def validate_metric_result_bundle(bundle: MetricResultBundle) -> None:
    if bundle.definitions != tuple(
        sorted(bundle.definitions, key=lambda item: (item.metric_key, item.metric_definition_id))
    ):
        raise MetricBundleError("metric definitions are not canonical")
    if bundle.trusted_source_bindings != tuple(
        sorted(
            bundle.trusted_source_bindings,
            key=lambda item: (
                item.source_identity.source_type.value,
                str(item.source_identity.source_id),
                str(item.trusted_source_binding_id),
            ),
        )
    ):
        raise MetricBundleError("metric trusted bindings are not canonical")
    if bundle.observations != tuple(
        sorted(bundle.observations, key=lambda item: (item.observed_at, item.metric_observation_id))
    ):
        raise MetricBundleError("metric observations are not canonical")
    if bundle.results != tuple(
        sorted(bundle.results, key=lambda item: (item.recorded_at, item.metric_result_id))
    ):
        raise MetricBundleError("metric results are not canonical")
    if bundle.aggregation_policies != tuple(
        sorted(bundle.aggregation_policies, key=lambda item: item.aggregation_policy_id)
    ):
        raise MetricBundleError("metric aggregation policies are not canonical")
    identities = (
        tuple(item.metric_definition_id for item in bundle.definitions),
        tuple(item.trusted_source_binding_id for item in bundle.trusted_source_bindings),
        tuple(item.metric_observation_id for item in bundle.observations),
        tuple(item.metric_result_id for item in bundle.results),
        tuple(item.aggregation_policy_id for item in bundle.aggregation_policies),
    )
    if any(len(values) != len(set(values)) for values in identities):
        raise DuplicateMetricError("metric bundle contains duplicate identity")
    definitions = {item.metric_definition_id: item for item in bundle.definitions}
    bindings = {item.trusted_source_binding_id: item for item in bundle.trusted_source_bindings}
    observations = {item.metric_observation_id: item for item in bundle.observations}
    for definition in bundle.definitions:
        validate_metric_definition(definition)
    for observation in bundle.observations:
        definition = definitions.get(observation.metric_definition_id)
        binding = bindings.get(observation.trusted_source_binding_id)
        if definition is None or binding is None:
            raise MetricBundleError("metric observation is orphaned")
        validate_metric_observation(observation, definition, binding)
    for result in bundle.results:
        definition = definitions.get(result.metric_definition_id)
        observation = observations.get(result.metric_observation_id)
        binding = bindings.get(result.trusted_source_binding_id)
        if definition is None or observation is None or binding is None:
            raise MetricBundleError("metric result is orphaned")
        validate_metric_result(result, observation, definition, binding)
        if result.recorded_at > bundle.created_at:
            raise MetricBundleError("metric result follows bundle creation")
    for policy in bundle.aggregation_policies:
        definition = definitions.get(policy.metric_definition_id)
        if definition is None:
            raise MetricBundleError("metric aggregation policy is orphaned")
        validate_metric_aggregation_policy(policy, definition)
    entries = (
        *bundle.definitions,
        *bundle.observations,
        *bundle.results,
        *bundle.aggregation_policies,
    )
    for item in entries:
        if (item.tenant_id, item.organization_id) != (bundle.tenant_id, bundle.organization_id):
            raise MetricBindingMismatchError("metric bundle scope mismatch")
        not_lower(bundle.classification, item.classification)
    used_bindings = {item.trusted_source_binding_id for item in bundle.observations}
    if used_bindings != set(bindings):
        raise MetricBundleError("metric bundle contains orphan trusted binding")
    for binding in bundle.trusted_source_bindings:
        governance = binding.governance_context
        if binding.status is not TrustedSourceBindingStatus.ACTIVE:
            raise MetricBundleError("metric bundle requires active trusted bindings")
        if (governance.tenant_id, governance.organization_id) != (
            bundle.tenant_id,
            bundle.organization_id,
        ):
            raise MetricBindingMismatchError("metric binding scope mismatch")
        not_lower(bundle.classification, governance.classification)
    for item in (*bundle.observations, *bundle.results):
        if (
            item.lineage_id != bundle.lineage_id
            or item.lineage_digest_reference != bundle.lineage_digest_reference
        ):
            raise MetricLineageError("metric bundle lineage mismatch")
    _validate_metric_audit(bundle)


def _validate_metric_audit(bundle: MetricResultBundle) -> None:
    audit = bundle.audit_metadata
    if audit is None:
        return
    counts = {status: 0 for status in MetricResultStatus}
    for result in bundle.results:
        counts[result.status] += 1
    actual = (
        audit.metric_result_bundle_id,
        audit.bundle_version,
        audit.definition_count,
        audit.observation_count,
        audit.result_count,
        audit.recorded_result_count,
        audit.unavailable_result_count,
        audit.not_applicable_result_count,
        audit.invalidated_result_count,
        audit.trusted_binding_count,
        audit.tenant_id,
        audit.organization_id,
    )
    expected = (
        bundle.metric_result_bundle_id,
        bundle.bundle_version.metric_result_bundle_version,
        len(bundle.definitions),
        len(bundle.observations),
        len(bundle.results),
        counts[MetricResultStatus.RECORDED],
        counts[MetricResultStatus.UNAVAILABLE],
        counts[MetricResultStatus.NOT_APPLICABLE],
        counts[MetricResultStatus.INVALIDATED],
        len(bundle.trusted_source_bindings),
        bundle.tenant_id,
        bundle.organization_id,
    )
    if actual != expected or audit.created_at != bundle.created_at:
        raise MetricAuditMetadataError("metric bundle audit metadata mismatch")
    not_lower(audit.classification, bundle.classification)


def build_metric_result_bundle(request: MetricResultBundleRequest) -> MetricResultBundle:
    return MetricResultBundle(
        metric_result_bundle_id=request.metric_result_bundle_id,
        bundle_version=request.bundle_version,
        definitions=request.definitions,
        trusted_source_bindings=request.trusted_source_bindings,
        observations=request.observations,
        results=request.results,
        aggregation_policies=request.aggregation_policies,
        evaluation_pipeline_id=request.evaluation_pipeline_id,
        tenant_id=request.tenant_id,
        organization_id=request.organization_id,
        classification=request.classification,
        lineage_id=request.root_lineage_id,
        lineage_digest_reference=request.root_lineage_digest_reference,
        audit_metadata=request.audit_metadata,
        created_at=request.created_at,
    )
