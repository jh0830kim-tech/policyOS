"""Focused tests for deterministic CP6 fake and dry-run Runtime Adapters."""

from dataclasses import FrozenInstanceError, fields
from datetime import UTC, datetime, timedelta
from pathlib import Path
from uuid import UUID

import pytest

from app.ai.privacy import DataClassification
from app.runtime import adapters
from app.runtime.adapters import (
    DryRunRuntimeAdapter,
    FakeRuntimeAdapter,
    RuntimeAdapterBindingError,
    RuntimeAdapterModeError,
    RuntimeAdapterResultError,
    validate_runtime_adapter_exact_envelope,
    validate_runtime_adapter_supplied_result,
    validate_runtime_dry_run_envelope,
)
from app.runtime.authority import RuntimeExecutionEnvironment, RuntimeRiskLevel
from app.runtime.planning import ExecutionPlanMode
from app.runtime.ports import (
    RuntimeAdapterFamily,
    RuntimeAdapterInvocationEnvelope,
    RuntimeAdapterInvocationResult,
    RuntimeAdapterPort,
    RuntimeInvocationPolicyBinding,
    RuntimeInvocationStatus,
    RuntimePortContractVersion,
    RuntimePortErrorCode,
    RuntimePortFailure,
    RuntimePortScope,
)
from app.runtime.registry import RuntimeActionSideEffectLevel
from app.runtime.state import RuntimeExecutionState

ROOT = Path(__file__).resolve().parents[1]
NOW = datetime(2026, 8, 3, 1, 0, tzinfo=UTC)


def uid(value: int) -> UUID:
    return UUID(int=value)


def contract() -> RuntimePortContractVersion:
    return RuntimePortContractVersion(
        runtime_ports_version="ports-v1",
        runtime_ports_contract_version="contract-v1",
        runtime_ports_schema_version="schema-v1",
    )


def scope() -> RuntimePortScope:
    return RuntimePortScope(
        runtime_execution_request_id=uid(1),
        runtime_authority_bundle_id=uid(2),
        runtime_admission_decision_id=uid(3),
        execution_plan_id=uid(4),
        execution_plan_step_id=uid(5),
        attempt_id=uid(6),
        actor_id=uid(7),
        agent_instance_id=uid(8),
        on_behalf_of_user_id=uid(9),
        tenant_id=uid(10),
        organization_id=uid(11),
        classification=DataClassification.CONFIDENTIAL,
        root_lineage_id=uid(12),
        root_lineage_digest_reference="lineage-digest",
        provenance_reference_ids=(uid(13),),
        policy_revision=2,
        authorization_revision=3,
        registry_revision=4,
        state_revision=5,
    )


def envelope(
    *,
    family: RuntimeAdapterFamily = RuntimeAdapterFamily.PROVIDER,
    dry_run: bool = True,
) -> RuntimeAdapterInvocationEnvelope:
    return RuntimeAdapterInvocationEnvelope(
        runtime_adapter_invocation_id=uid(20),
        contract_version=contract(),
        adapter_family=family,
        adapter_reference=f"adapter.{family.value}",
        adapter_contract_version="adapter-v1",
        action_definition_id="action-definition",
        action="governed-action",
        action_version="action-v1",
        runtime_registry_snapshot_id=uid(21),
        runtime_action_resolution_decision_id=uid(22),
        runtime_registry_snapshot_entry_id=uid(23),
        permit_reference_ids=(uid(24),),
        input_schema_reference="schema.input",
        input_reference="input-reference",
        input_digest_reference="input-digest",
        output_schema_reference="schema.output",
        policy_binding=RuntimeInvocationPolicyBinding(
            resource_reference="resource-reference",
            purpose="approved-purpose",
            risk_level=RuntimeRiskLevel.MODERATE,
            execution_environment=(
                RuntimeExecutionEnvironment.DRY_RUN
                if dry_run
                else RuntimeExecutionEnvironment.INTERNAL
            ),
            plan_mode=(ExecutionPlanMode.DRY_RUN if dry_run else ExecutionPlanMode.EXECUTION),
            side_effect_level=RuntimeActionSideEffectLevel.READ_ONLY,
            side_effect_level_reference="side-effect-reference",
            model_id="model-reference",
            provider_id="provider-reference",
            tool_id="tool-reference",
            connector_id="connector-reference",
            retry_eligible=False,
            maximum_attempt_count=1,
        ),
        destination_reference="destination-reference",
        idempotency_key="idempotency-key",
        required_state=RuntimeExecutionState.RUNNING,
        scope=scope(),
        requested_at=NOW,
        deadline=NOW + timedelta(seconds=30),
    )


def result(
    item: RuntimeAdapterInvocationEnvelope,
    *,
    status: RuntimeInvocationStatus = RuntimeInvocationStatus.SUCCEEDED,
) -> RuntimeAdapterInvocationResult:
    succeeded = status is RuntimeInvocationStatus.SUCCEEDED
    failure = None
    if not succeeded:
        failure = RuntimePortFailure(
            runtime_port_failure_id=uid(30),
            error_code={
                RuntimeInvocationStatus.FAILED: RuntimePortErrorCode.ADAPTER_REJECTED,
                RuntimeInvocationStatus.TIMED_OUT: RuntimePortErrorCode.TIMEOUT,
                RuntimeInvocationStatus.CANCELLED: RuntimePortErrorCode.CANCELLED,
                RuntimeInvocationStatus.AMBIGUOUS: RuntimePortErrorCode.CALLER_SUPPLIED,
            }[status],
            error_reference=f"failure.{status.value}",
            classification=item.scope.classification,
            occurred_at=NOW + timedelta(seconds=2),
        )
    return RuntimeAdapterInvocationResult(
        runtime_adapter_invocation_result_id=uid(31),
        runtime_adapter_invocation_id=item.runtime_adapter_invocation_id,
        contract_version=item.contract_version,
        status=status,
        adapter_reference=item.adapter_reference,
        adapter_contract_version=item.adapter_contract_version,
        action_definition_id=item.action_definition_id,
        action=item.action,
        action_version=item.action_version,
        attempt_id=item.scope.attempt_id,
        tenant_id=item.scope.tenant_id,
        organization_id=item.scope.organization_id,
        classification=item.scope.classification,
        result_reference="result-reference" if succeeded else None,
        result_digest_reference="result-digest" if succeeded else None,
        failure=failure,
        started_at=NOW + timedelta(seconds=1),
        completed_at=NOW + timedelta(seconds=2),
    )


@pytest.mark.parametrize("family", tuple(RuntimeAdapterFamily))
@pytest.mark.asyncio
async def test_fake_adapter_covers_each_closed_family_exactly(
    family: RuntimeAdapterFamily,
) -> None:
    expected = envelope(family=family)
    supplied = result(expected)
    adapter = FakeRuntimeAdapter(expected, supplied)

    assert isinstance(adapter, RuntimeAdapterPort)
    assert adapter.adapter_family is family
    assert adapter.adapter_reference == expected.adapter_reference
    assert adapter.adapter_contract_version == expected.adapter_contract_version
    assert await adapter.invoke(expected) is supplied


@pytest.mark.parametrize("family", tuple(RuntimeAdapterFamily))
@pytest.mark.asyncio
async def test_dry_run_adapter_has_no_family_specific_escape(
    family: RuntimeAdapterFamily,
) -> None:
    expected = envelope(family=family)
    supplied = result(expected)
    adapter = DryRunRuntimeAdapter(expected, supplied)

    assert validate_runtime_dry_run_envelope(expected) is expected
    assert await adapter.invoke(expected) is supplied


@pytest.mark.parametrize(
    "change",
    (
        {"action": "substituted-action"},
        {"destination_reference": "destination.substituted"},
        {"input_digest_reference": "digest.substituted"},
        {"permit_reference_ids": (uid(99),)},
        {"scope": scope().model_copy(update={"tenant_id": uid(99)})},
    ),
)
@pytest.mark.asyncio
async def test_fake_rejects_every_envelope_substitution(change: dict[str, object]) -> None:
    expected = envelope()
    adapter = FakeRuntimeAdapter(expected, result(expected))
    substituted = expected.model_copy(update=change)

    with pytest.raises(RuntimeAdapterBindingError):
        await adapter.invoke(substituted)


def test_policy_selector_substitution_fails_closed() -> None:
    expected = envelope()
    substituted = expected.model_copy(
        update={
            "policy_binding": expected.policy_binding.model_copy(
                update={"resource_reference": "resource.substituted"}
            )
        }
    )
    with pytest.raises(RuntimeAdapterBindingError):
        validate_runtime_adapter_exact_envelope(expected, substituted)


def test_dry_run_adapter_rejects_execution_mode_at_construction() -> None:
    expected = envelope(dry_run=False)
    with pytest.raises(RuntimeAdapterModeError):
        DryRunRuntimeAdapter(expected, result(expected))


def test_fake_can_simulate_execution_without_creating_an_external_effect() -> None:
    expected = envelope(dry_run=False)
    adapter = FakeRuntimeAdapter(expected, result(expected))
    assert adapter.expected_envelope.policy_binding.plan_mode is ExecutionPlanMode.EXECUTION


@pytest.mark.parametrize(
    "status",
    (
        RuntimeInvocationStatus.FAILED,
        RuntimeInvocationStatus.TIMED_OUT,
        RuntimeInvocationStatus.CANCELLED,
        RuntimeInvocationStatus.AMBIGUOUS,
    ),
)
@pytest.mark.asyncio
async def test_typed_non_success_results_remain_explicit(
    status: RuntimeInvocationStatus,
) -> None:
    expected = envelope()
    supplied = result(expected, status=status)
    adapter = FakeRuntimeAdapter(expected, supplied)

    observed = await adapter.invoke(expected)
    assert observed is supplied
    assert observed.status is status
    assert observed.failure is not None
    assert observed.result_reference is None


def test_substituted_result_fails_before_adapter_use() -> None:
    expected = envelope()
    substituted = result(expected).model_copy(update={"action": "substituted-action"})

    with pytest.raises(RuntimeAdapterResultError):
        FakeRuntimeAdapter(expected, substituted)
    with pytest.raises(RuntimeAdapterResultError):
        validate_runtime_adapter_supplied_result(expected, substituted)


def test_adapter_configuration_is_frozen_and_reference_only() -> None:
    expected = envelope()
    adapter = FakeRuntimeAdapter(expected, result(expected))

    with pytest.raises(FrozenInstanceError):
        adapter.expected_envelope = envelope(family=RuntimeAdapterFamily.MODEL)
    assert tuple(item.name for item in fields(adapter)) == (
        "expected_envelope",
        "supplied_result",
    )
    assert not hasattr(adapter, "calls")
    assert not hasattr(adapter, "client")
    assert not hasattr(adapter, "credentials")


def test_public_exports_are_explicit_and_immutable() -> None:
    assert isinstance(adapters.__all__, tuple)
    assert adapters.__all__ == (
        "DryRunRuntimeAdapter",
        "FakeRuntimeAdapter",
        "RuntimeAdapterBindingError",
        "RuntimeAdapterImplementationError",
        "RuntimeAdapterModeError",
        "RuntimeAdapterResultError",
        "validate_runtime_adapter_exact_envelope",
        "validate_runtime_adapter_supplied_result",
        "validate_runtime_dry_run_envelope",
    )


def test_adapter_implementation_has_no_external_or_sensitive_dependency() -> None:
    root = ROOT / "app" / "runtime" / "adapters"
    sources = "\n".join(path.read_text(encoding="utf-8") for path in root.rglob("*.py"))
    forbidden = (
        "app.ai_providers",
        "app.connectors",
        "app.execution",
        "app.knowledge",
        "app.mcp",
        "httpx",
        "requests",
        "socket",
        "sqlalchemy",
        "Redis",
        "subprocess",
        "importlib",
        "os.environ",
        "datetime.now",
        "uuid4",
        "hashlib",
        "callback",
        "client",
        "secret",
        "password",
        "api_key",
        "raw_prompt",
        "raw_output",
    )
    assert all(term not in sources for term in forbidden)
