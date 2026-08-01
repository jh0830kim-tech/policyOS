"""Sprint 14 CP2 immutable metric aggregation contract tests."""

from datetime import timedelta
from decimal import Decimal
from pathlib import Path

import pytest
from pydantic import ValidationError

from app.ai.privacy import DataClassification
from app.metrics import (
    DecimalMetricValue,
    MetricAggregationBundleRequest,
    MetricAggregationBundleVersion,
    MetricAggregationInputReference,
    MetricAggregationLineageReference,
    MetricAggregationProvenanceReference,
    MetricAggregationRecord,
    MetricAggregationRecordStatus,
    MetricAggregationRecordVersion,
    MetricAggregationRequest,
    MetricAggregationRequestVersion,
    MetricAggregationScope,
    MetricAggregationWindow,
    MetricAggregationWindowType,
    MetricValueType,
    build_metric_aggregation_bundle,
    validate_metric_aggregation_request,
)
from tests.test_evaluation_planner import NOW, uid
from tests.test_metrics_domain import ORG, TENANT, bundle

ROOT = Path(__file__).resolve().parents[1]


def contracts():
    source = bundle()
    result = source.results[0]
    policy = source.aggregation_policies[0]
    window = MetricAggregationWindow(
        aggregation_window_id=uid(93001),
        window_type=MetricAggregationWindowType.EXPLICIT_RESULT_SET,
        created_at=source.created_at,
    )
    input_ref = MetricAggregationInputReference(
        aggregation_input_reference_id=uid(93002),
        metric_result_id=result.metric_result_id,
        metric_result_version=result.result_version.metric_result_version,
        metric_definition_id=result.metric_definition_id,
        metric_definition_version=result.metric_definition_version,
        metric_observation_id=result.metric_observation_id,
        trusted_source_binding_id=result.trusted_source_binding_id,
        metric_result_bundle_id=source.metric_result_bundle_id,
        input_ordinal=1,
        tenant_id=TENANT,
        organization_id=ORG,
        classification=DataClassification.INTERNAL,
        lineage_id=result.lineage_id,
        lineage_digest_reference=result.lineage_digest_reference,
        recorded_at=result.recorded_at,
    )
    lineage = MetricAggregationLineageReference(
        aggregation_lineage_reference_id=uid(93003),
        root_lineage_id=source.lineage_id,
        root_lineage_digest_reference=source.lineage_digest_reference,
        metric_result_bundle_id=source.metric_result_bundle_id,
        metric_result_ids=(result.metric_result_id,),
        aggregation_policy_id=policy.aggregation_policy_id,
        aggregation_window_id=window.aggregation_window_id,
        lineage_schema_version="metric-aggregation-lineage-schema-v1",
        created_at=source.created_at,
    )
    provenance = MetricAggregationProvenanceReference(
        aggregation_provenance_reference_id=uid(93004),
        metric_result_bundle_id=source.metric_result_bundle_id,
        metric_result_bundle_version=source.bundle_version.metric_result_bundle_version,
        metric_definition_ids=(result.metric_definition_id,),
        metric_result_ids=(result.metric_result_id,),
        trusted_source_binding_ids=(result.trusted_source_binding_id,),
        aggregation_policy_id=policy.aggregation_policy_id,
        aggregation_policy_version=policy.policy_version,
        aggregation_window_id=window.aggregation_window_id,
        policy_revision=policy.policy_revision,
        recorded_at=source.created_at,
    )
    request = MetricAggregationRequest(
        metric_aggregation_request_id=uid(93005),
        request_version=MetricAggregationRequestVersion(
            aggregation_request_version="request-v1",
            aggregation_request_contract_version="contract-v1",
            aggregation_request_schema_version="metric-aggregation-request-schema-v1",
        ),
        metric_result_bundle_id=source.metric_result_bundle_id,
        metric_result_bundle_version=source.bundle_version.metric_result_bundle_version,
        metric_definition_ids=(result.metric_definition_id,),
        aggregation_policy_id=policy.aggregation_policy_id,
        aggregation_policy_version=policy.policy_version,
        aggregation_scope=MetricAggregationScope.SINGLE_DEFINITION,
        aggregation_window=window,
        input_references=(input_ref,),
        lineage_reference=lineage,
        provenance_reference=provenance,
        policy_revision=policy.policy_revision,
        tenant_id=TENANT,
        organization_id=ORG,
        actor_id=uid(92003),
        classification=DataClassification.INTERNAL,
        requested_at=source.created_at + timedelta(seconds=1),
    )
    record = MetricAggregationRecord(
        metric_aggregation_record_id=uid(93006),
        record_version=MetricAggregationRecordVersion(
            aggregation_record_version="record-v1",
            aggregation_record_contract_version="contract-v1",
            aggregation_record_schema_version="metric-aggregation-record-schema-v1",
        ),
        metric_aggregation_request_id=request.metric_aggregation_request_id,
        metric_result_bundle_id=source.metric_result_bundle_id,
        aggregation_policy_id=policy.aggregation_policy_id,
        aggregation_method=policy.aggregation_method,
        aggregation_scope=request.aggregation_scope,
        aggregation_window_id=window.aggregation_window_id,
        input_reference_ids=(input_ref.aggregation_input_reference_id,),
        output_value_type=MetricValueType.DECIMAL,
        aggregate_value=DecimalMetricValue(
            value_type=MetricValueType.DECIMAL, value=Decimal("0.92")
        ),
        status=MetricAggregationRecordStatus.RECORDED,
        reason_codes=(),
        lineage_reference=lineage,
        provenance_reference=provenance,
        policy_revision=policy.policy_revision,
        tenant_id=TENANT,
        organization_id=ORG,
        actor_id=uid(92003),
        classification=DataClassification.INTERNAL,
        recorded_at=request.requested_at + timedelta(seconds=1),
    )
    return source, policy, window, request, record


def test_valid_request_and_caller_supplied_record_build_immutable_bundle():
    source, policy, window, request, record = contracts()
    built = build_metric_aggregation_bundle(
        MetricAggregationBundleRequest(
            metric_result_bundle=source,
            aggregation_policies=(policy,),
            aggregation_requests=(request,),
            aggregation_records=(record,),
            aggregation_windows=(window,),
            lineage_references=(request.lineage_reference,),
            provenance_references=(request.provenance_reference,),
            metric_aggregation_bundle_id=uid(93007),
            bundle_version=MetricAggregationBundleVersion(
                metric_aggregation_bundle_version="bundle-v1",
                aggregation_bundle_contract_version="contract-v1",
                aggregation_bundle_schema_version="metric-aggregation-bundle-schema-v1",
            ),
            tenant_id=TENANT,
            organization_id=ORG,
            classification=DataClassification.INTERNAL,
            root_lineage_id=source.lineage_id,
            root_lineage_digest_reference=source.lineage_digest_reference,
            created_at=record.recorded_at + timedelta(seconds=1),
        )
    )
    assert built.aggregation_records[0].aggregate_value.value == Decimal("0.92")
    with pytest.raises(ValidationError):
        built.classification = DataClassification.PUBLIC


def test_window_contract_is_explicit_strict_and_timezone_aware():
    with pytest.raises(ValidationError):
        MetricAggregationWindow(
            aggregation_window_id=uid(93101),
            window_type=MetricAggregationWindowType.EXPLICIT_RESULT_SET,
            policy_revision=1,
            created_at=NOW,
        )
    with pytest.raises(ValidationError):
        MetricAggregationWindow(
            aggregation_window_id=uid(93102),
            window_type=MetricAggregationWindowType.EXPLICIT_TIME_RANGE,
            start_at=NOW + timedelta(seconds=1),
            end_at=NOW,
            created_at=NOW,
        )
    with pytest.raises(ValidationError):
        MetricAggregationWindow(
            aggregation_window_id=uid(93103),
            window_type=MetricAggregationWindowType.EXPLICIT_RESULT_SET,
            created_at=NOW.replace(tzinfo=None),
        )


def test_input_substitution_classification_and_policy_binding_fail_closed():
    source, policy, _, request, _ = contracts()
    bad = request.input_references[0].model_copy(update={"metric_result_id": uid(93991)})
    with pytest.raises(ValueError):
        validate_metric_aggregation_request(
            request.model_copy(update={"input_references": (bad,)}), source, policy
        )
    with pytest.raises(ValueError):
        validate_metric_aggregation_request(
            request.model_copy(update={"classification": DataClassification.PUBLIC}), source, policy
        )
    with pytest.raises(ValueError):
        validate_metric_aggregation_request(
            request.model_copy(update={"aggregation_policy_version": "wrong"}), source, policy
        )


def test_record_lifecycle_rejects_implicit_or_mismatched_values():
    _, _, _, _, record = contracts()
    with pytest.raises(ValidationError):
        MetricAggregationRecord.model_validate(record.model_dump() | {"aggregate_value": None})
    with pytest.raises(ValidationError):
        MetricAggregationRecord.model_validate(
            record.model_dump()
            | {
                "status": MetricAggregationRecordStatus.UNAVAILABLE,
                "reason_codes": ("missing",),
            }
        )
    with pytest.raises(ValidationError):
        MetricAggregationRecord.model_validate(record.model_dump() | {"score": 1})


def test_scope_boundaries_are_absent():
    text = "\n".join(
        path.read_text(encoding="utf-8")
        for path in (ROOT / "app" / "metrics").glob("aggregation_*.py")
    )
    for forbidden in (
        "datetime.now",
        "datetime.utcnow",
        "time.time",
        "uuid4",
        "random.",
        "hashlib",
        "numpy",
        "statistics.",
        "subprocess",
        "sqlalchemy",
        "FastAPI",
        "requests.",
        "httpx",
        "open(",
        "threshold",
        "winner",
        "raw_prompt",
        "model_output",
        "evidence_content",
        "credential_value",
    ):
        assert forbidden not in text
