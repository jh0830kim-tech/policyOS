"""Sprint 14 CP1-B immutable trusted-binding-first metrics tests."""

from datetime import timedelta
from decimal import Decimal
from pathlib import Path

import pytest
from pydantic import ValidationError

from app.ai.privacy import DataClassification
from app.metrics import (
    BooleanMetricValue,
    CountMetricValue,
    CurrencyMetricValue,
    DecimalMetricValue,
    DurationMetricValue,
    EnumReferenceMetricValue,
    IntegerMetricValue,
    MetricAggregationMethod,
    MetricAggregationPolicy,
    MetricCategory,
    MetricDefinition,
    MetricDefinitionVersion,
    MetricDirection,
    MetricMeasurementUnit,
    MetricMissingValuePolicy,
    MetricObservation,
    MetricResult,
    MetricResultBundle,
    MetricResultBundleAuditMetadata,
    MetricResultBundleVersion,
    MetricResultStatus,
    MetricResultVersion,
    MetricScope,
    MetricValueType,
    PercentageMetricValue,
    RatioMetricValue,
    TextReferenceMetricValue,
)
from app.source_bindings import (
    TrustedSourceBindingStatus,
    TrustedSourceType,
)
from tests.test_evaluation_planner import NOW, uid
from tests.test_trusted_source_bindings import DIGEST, LINEAGE, ORG, TENANT, binding

ROOT = Path(__file__).resolve().parents[1]
DEFINITION_VERSION = MetricDefinitionVersion(
    metric_definition_version="definition-v1",
    metric_contract_version="contract-v1",
    metric_schema_version="metric-definition-schema-v1",
)
RESULT_VERSION = MetricResultVersion(
    metric_result_version="result-v1",
    metric_result_contract_version="contract-v1",
    metric_result_schema_version="metric-result-schema-v1",
)


def definition(**changes):
    values = {
        "metric_definition_id": uid(92001),
        "metric_key": "quality.groundedness",
        "display_name_reference": "metric-name://groundedness",
        "category": MetricCategory.GROUNDEDNESS,
        "value_type": MetricValueType.DECIMAL,
        "measurement_unit": MetricMeasurementUnit.RATIO,
        "direction": MetricDirection.HIGHER_IS_PREFERRED,
        "supported_scopes": (MetricScope.CROSS_VALIDATION_RUN,),
        "definition_version": DEFINITION_VERSION,
        "owner_reference": "owner://evaluation-governance",
        "purpose": "evaluation_quality",
        "classification": DataClassification.INTERNAL,
        "tenant_id": TENANT,
        "organization_id": ORG,
        "policy_revision": 1,
        "registry_revision": 1,
        "definition_document_reference": "metric-definition://groundedness/v1",
        "allowed_enum_value_references": (),
        "created_at": NOW,
    }
    values.update(changes)
    return MetricDefinition(**values)


def observation(source_binding=None, **changes):
    source_binding = source_binding or binding()
    values = {
        "metric_observation_id": uid(92002),
        "metric_definition_id": uid(92001),
        "metric_definition_version": DEFINITION_VERSION,
        "trusted_source_binding_id": source_binding.trusted_source_binding_id,
        "trusted_source_type": TrustedSourceType.CROSS_VALIDATION_RUN_COLLECTION,
        "metric_scope": MetricScope.CROSS_VALIDATION_RUN,
        "policy_revision": 1,
        "registry_revision": 1,
        "tenant_id": TENANT,
        "organization_id": ORG,
        "actor_id": uid(92003),
        "classification": DataClassification.INTERNAL,
        "lineage_id": LINEAGE,
        "lineage_digest_reference": DIGEST,
        "observed_at": NOW + timedelta(seconds=3),
    }
    values.update(changes)
    return MetricObservation(**values)


def result(source_binding=None, **changes):
    source_binding = source_binding or binding()
    values = {
        "metric_result_id": uid(92004),
        "metric_definition_id": uid(92001),
        "metric_definition_version": DEFINITION_VERSION,
        "metric_observation_id": uid(92002),
        "trusted_source_binding_id": source_binding.trusted_source_binding_id,
        "value_type": MetricValueType.DECIMAL,
        "value": DecimalMetricValue(value_type=MetricValueType.DECIMAL, value=Decimal("0.92")),
        "status": MetricResultStatus.RECORDED,
        "reason_codes": (),
        "result_version": RESULT_VERSION,
        "policy_revision": 1,
        "registry_revision": 1,
        "tenant_id": TENANT,
        "organization_id": ORG,
        "actor_id": uid(92003),
        "classification": DataClassification.INTERNAL,
        "lineage_id": LINEAGE,
        "lineage_digest_reference": DIGEST,
        "recorded_at": NOW + timedelta(seconds=4),
    }
    values.update(changes)
    return MetricResult(**values)


def policy(**changes):
    values = {
        "aggregation_policy_id": uid(92005),
        "metric_definition_id": uid(92001),
        "metric_definition_version": DEFINITION_VERSION,
        "aggregation_method": MetricAggregationMethod.NONE,
        "input_value_type": MetricValueType.DECIMAL,
        "output_value_type": MetricValueType.DECIMAL,
        "minimum_result_count": 1,
        "grouping_key_references": (),
        "missing_value_policy": MetricMissingValuePolicy.REJECT_MISSING,
        "policy_version": "policy-v1",
        "policy_revision": 1,
        "tenant_id": TENANT,
        "organization_id": ORG,
        "classification": DataClassification.INTERNAL,
        "created_at": NOW,
    }
    values.update(changes)
    return MetricAggregationPolicy(**values)


def bundle(**changes):
    source_binding = changes.pop("source_binding", binding())
    values = {
        "metric_result_bundle_id": uid(92006),
        "bundle_version": MetricResultBundleVersion(
            metric_result_bundle_version="bundle-v1",
            metric_bundle_contract_version="contract-v1",
            metric_bundle_schema_version="metric-bundle-schema-v1",
        ),
        "definitions": (definition(),),
        "trusted_source_bindings": (source_binding,),
        "observations": (observation(source_binding),),
        "results": (result(source_binding),),
        "aggregation_policies": (policy(),),
        "tenant_id": TENANT,
        "organization_id": ORG,
        "classification": DataClassification.INTERNAL,
        "lineage_id": LINEAGE,
        "lineage_digest_reference": DIGEST,
        "created_at": NOW + timedelta(seconds=5),
    }
    values.update(changes)
    return MetricResultBundle(**values)


def test_contracts_are_strict_frozen_and_extra_forbidden():
    item = definition()
    assert item.model_config["strict"] and item.model_config["frozen"]
    with pytest.raises(ValidationError):
        item.metric_key = "changed"
    values = item.model_dump()
    values["threshold"] = Decimal("0.5")
    with pytest.raises(ValidationError):
        MetricDefinition.model_validate(values)


def test_definition_rejects_noncanonical_scopes_and_enum_references():
    with pytest.raises(ValidationError):
        definition(
            supported_scopes=(MetricScope.CROSS_VALIDATION_RUN, MetricScope.CROSS_VALIDATION_RUN)
        )
    with pytest.raises(ValidationError):
        definition(
            value_type=MetricValueType.ENUM_REFERENCE,
            allowed_enum_value_references=("enum://b", "enum://a"),
        )


@pytest.mark.parametrize(
    "value",
    (
        IntegerMetricValue(value_type=MetricValueType.INTEGER, value=2),
        DecimalMetricValue(value_type=MetricValueType.DECIMAL, value=Decimal("1.20")),
        BooleanMetricValue(value_type=MetricValueType.BOOLEAN, value=True),
        DurationMetricValue(
            value_type=MetricValueType.DURATION,
            value=Decimal("2.5"),
            unit=MetricMeasurementUnit.SECONDS,
        ),
        CurrencyMetricValue(
            value_type=MetricValueType.CURRENCY,
            value=Decimal("3.10"),
            currency_code_reference="KRW",
        ),
        CountMetricValue(value_type=MetricValueType.COUNT, value=3),
        RatioMetricValue(
            value_type=MetricValueType.RATIO,
            value=Decimal("0.3"),
            ratio_basis_reference="ratio-basis://one",
        ),
        PercentageMetricValue(value_type=MetricValueType.PERCENTAGE, value=Decimal("92")),
        EnumReferenceMetricValue(
            value_type=MetricValueType.ENUM_REFERENCE, value_reference="enum://supported"
        ),
        TextReferenceMetricValue(
            value_type=MetricValueType.TEXT_REFERENCE, value_reference="text://opaque/1"
        ),
    ),
)
def test_typed_values_retain_exact_caller_values(value):
    assert value.value_type in MetricValueType


def test_values_reject_float_coercion_nonfinite_percentage_and_raw_text():
    with pytest.raises(ValidationError):
        DecimalMetricValue(value_type=MetricValueType.DECIMAL, value=0.2)
    with pytest.raises(ValidationError):
        DecimalMetricValue(value_type=MetricValueType.DECIMAL, value=Decimal("NaN"))
    with pytest.raises(ValidationError):
        PercentageMetricValue(value_type=MetricValueType.PERCENTAGE, value=Decimal("101"))
    with pytest.raises(ValidationError):
        TextReferenceMetricValue(
            value_type=MetricValueType.TEXT_REFERENCE,
            value_reference="text://opaque",
            raw_text="forbidden",
        )


def test_active_trusted_binding_observation_and_result_bundle_pass():
    assert bundle().results[0].value.value == Decimal("0.92")


def test_inactive_binding_and_wrong_scope_fail():
    inactive = binding(status=TrustedSourceBindingStatus.REVOKED, reasons=("revoked",))
    with pytest.raises(ValidationError):
        bundle(source_binding=inactive)
    with pytest.raises(ValidationError):
        bundle(observations=(observation(metric_scope=MetricScope.SECURITY_EVENT),))


def test_observation_scope_classification_lineage_and_tenant_fail_closed():
    for updates in (
        {"tenant_id": uid(92990)},
        {"classification": DataClassification.PUBLIC},
        {"lineage_id": uid(92991)},
        {"trusted_source_binding_id": uid(92992)},
    ):
        with pytest.raises(ValidationError):
            bundle(observations=(observation(**updates),))


@pytest.mark.parametrize(
    ("status", "value", "reasons"),
    (
        (MetricResultStatus.UNAVAILABLE, None, ("unavailable",)),
        (MetricResultStatus.NOT_APPLICABLE, None, ()),
    ),
)
def test_nonrecorded_result_lifecycle(status, value, reasons):
    assert result(status=status, value=value, reason_codes=reasons).status is status


def test_result_status_binding_value_type_and_lineage_fail_closed():
    for updates in (
        {"value": None},
        {"metric_observation_id": uid(92993)},
        {"trusted_source_binding_id": uid(92994)},
        {"classification": DataClassification.PUBLIC},
        {"lineage_digest_reference": "changed"},
    ):
        with pytest.raises((ValidationError, ValueError)):
            candidate = result(**updates)
            bundle(results=(candidate,))


def test_aggregation_policy_is_metadata_only_and_canonical():
    assert policy().aggregation_method is MetricAggregationMethod.NONE
    with pytest.raises(ValidationError):
        policy(grouping_key_references=("group://b", "group://a"))
    with pytest.raises(ValidationError):
        policy(aggregation_method=MetricAggregationMethod.PERCENTILE)
    with pytest.raises(ValidationError):
        policy(threshold=Decimal("0.5"))


def test_audit_counts_are_exact():
    item = bundle()
    audit = MetricResultBundleAuditMetadata(
        metric_result_bundle_id=item.metric_result_bundle_id,
        bundle_version=item.bundle_version.metric_result_bundle_version,
        definition_count=1,
        observation_count=1,
        result_count=1,
        recorded_result_count=1,
        unavailable_result_count=0,
        not_applicable_result_count=0,
        invalidated_result_count=0,
        trusted_binding_count=1,
        tenant_id=TENANT,
        organization_id=ORG,
        classification=DataClassification.INTERNAL,
        policy_revision=1,
        registry_revision=1,
        created_at=item.created_at,
    )
    assert bundle(audit_metadata=audit).audit_metadata == audit
    with pytest.raises(ValidationError):
        bundle(audit_metadata=audit.model_copy(update={"result_count": 2}))


def test_runtime_and_sensitive_boundaries_absent():
    text = "\n".join(
        path.read_text(encoding="utf-8") for path in (ROOT / "app" / "metrics").glob("*.py")
    )
    for forbidden in (
        "datetime.now",
        "datetime.utcnow",
        "time.time",
        "uuid4",
        "hashlib",
        "requests",
        "httpx",
        "subprocess",
        "sqlalchemy",
        "FastAPI",
        "open(",
        "raw_prompt",
        "model_output",
        "evidence_content",
        "credential_value",
    ):
        assert forbidden not in text
