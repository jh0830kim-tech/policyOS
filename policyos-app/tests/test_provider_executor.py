from datetime import UTC, datetime, timedelta
from uuid import uuid4

import pytest
from pydantic import ValidationError

from app.ai.privacy import DataClassification
from app.execution.domain import (
    EvidenceReference,
    ExecutionContext,
    ExecutionMetrics,
    ExecutionStatus,
    StepStatus,
)
from app.execution.executor import (
    DeterministicProviderExecutor,
    InvocationStatus,
    ProviderAdapterCatalog,
    ProviderInvocationOutcome,
)
from app.execution.executor_errors import (
    ExecutorIdentityMismatchError,
    ExecutorRevisionConflictError,
    ExecutorStepStateError,
    ProviderAdapterCapabilityError,
    ProviderResultMismatchError,
    UnknownProviderAdapterError,
)
from app.execution.provider_adapters import (
    KOREAN_LAW_LOGICAL_PROVIDER_ID,
    KoreanLawProviderAdapter,
)
from app.execution.provider_resolution import (
    DispatchBinding,
    ProviderCapability,
    ProviderCatalog,
    ProviderDescriptor,
    ProviderKind,
    korean_law_mcp_descriptor,
)
from app.execution.runtime import (
    DispatchRequest,
    ExecutionRuntimeState,
    ExecutionSession,
    RuntimeStepState,
    RuntimeStepStatus,
    SessionStatus,
)
from app.knowledge.providers.domain import KnowledgeEvidence, KnowledgeProviderType
from app.knowledge.providers.korean_law_runtime import (
    KoreanLawExecutionMetadata,
    KoreanLawExecutionStatus,
    KoreanLawProviderExecutionResult,
)
from app.knowledge.providers.korean_law_tools import KoreanLawMcpOperation

NOW = datetime(2026, 7, 26, 2, tzinfo=UTC)


class FixedClock:
    def __init__(self, *values):
        self.values = list(values or (NOW,))

    def now(self):
        return self.values.pop(0) if len(self.values) > 1 else self.values[0]


class FakeAdapter:
    provider_id = "knowledge.fake"
    provider_kind = ProviderKind.KNOWLEDGE
    supported_capabilities = ("knowledge.search",)

    def __init__(self, outcome=None, error=None):
        self.outcome = outcome
        self.error = error
        self.calls = []

    async def invoke(self, request, context):
        self.calls.append((request, context))
        if self.error:
            raise self.error
        return self.outcome or ProviderInvocationOutcome(
            provider_id=self.provider_id,
            capability_id=request.capability_id,
            step_id=request.step_id,
            attempt=request.attempt,
            status=InvocationStatus.SUCCEEDED,
            output={"answer": "safe"},
            evidence=(
                EvidenceReference(
                    source="fake",
                    record_id="record-1",
                    title="Evidence",
                    classification=request.classification,
                ),
            ),
            metrics=ExecutionMetrics(duration_ms=5, provider_calls=1),
            started_at=NOW,
            completed_at=NOW + timedelta(milliseconds=5),
        )


def descriptor(provider_id="knowledge.fake", capability="knowledge.search", **changes):
    values = dict(
        provider_id=provider_id,
        provider_kind=ProviderKind.KNOWLEDGE,
        capabilities=(ProviderCapability(capability_id=capability),),
    )
    values.update(changes)
    return ProviderDescriptor(**values)


@pytest.fixture
def scope():
    organization_id, actor_id, execution_id, session_id, plan_id = (uuid4() for _ in range(5))
    dispatch_id = uuid4()
    deadline = NOW + timedelta(minutes=1)
    dispatch = DispatchRequest(
        dispatch_id=dispatch_id,
        session_id=session_id,
        execution_id=execution_id,
        plan_id=plan_id,
        step_id="search",
        capability_id="knowledge.search",
        input={"query": "safe"},
        classification=DataClassification.INTERNAL,
        organization_id=organization_id,
        actor_id=actor_id,
        correlation_id="corr",
        attempt=1,
        timeout_seconds=60,
        deadline=deadline,
        issued_at=NOW,
    )
    binding = DispatchBinding(
        binding_id=uuid4(),
        dispatch_id=dispatch_id,
        session_id=session_id,
        execution_id=execution_id,
        plan_id=plan_id,
        step_id="search",
        capability_id="knowledge.search",
        provider_id="knowledge.fake",
        provider_kind=ProviderKind.KNOWLEDGE,
        policy_id="trusted.default",
        selection_version="1",
        idempotency_key="dispatch.search.1",
        bound_at=NOW,
        deadline=deadline,
        classification=DataClassification.INTERNAL,
        organization_id=organization_id,
    )
    session = ExecutionSession(
        session_id=session_id,
        execution_id=execution_id,
        plan_id=plan_id,
        organization_id=organization_id,
        actor_id=actor_id,
        correlation_id="corr",
        classification=DataClassification.INTERNAL,
        status=SessionStatus.RUNNING,
        created_at=NOW,
        started_at=NOW,
        updated_at=NOW,
        deadline=deadline,
        runtime_revision=1,
    )
    context = ExecutionContext(
        execution_id=execution_id,
        organization_id=organization_id,
        actor_id=actor_id,
        correlation_id="corr",
        classification=DataClassification.INTERNAL,
        deadline=deadline,
    )
    state = ExecutionRuntimeState(
        session_id=session_id,
        execution_id=execution_id,
        plan_id=plan_id,
        revision=1,
        status=ExecutionStatus.RUNNING,
        step_states=(
            RuntimeStepState(
                step_id="search",
                status=RuntimeStepStatus.RUNNING,
                attempt_count=1,
                dispatched_at=NOW,
                started_at=NOW,
                dispatch_id=dispatch_id,
            ),
        ),
        started_at=NOW,
        updated_at=NOW,
    )
    return binding, dispatch, session, context, state


def executor(adapter, clock=None, provider=None):
    return DeterministicProviderExecutor(
        ProviderAdapterCatalog.from_adapters([adapter]),
        ProviderCatalog.from_providers([provider or descriptor()]),
        clock or FixedClock(),
    )


def test_adapter_catalog_is_canonical_immutable_and_typed():
    beta = FakeAdapter()
    beta.provider_id = "knowledge.zed"
    catalog = ProviderAdapterCatalog.from_adapters([beta, FakeAdapter()])
    assert [item.provider_id for item in catalog.all()] == ["knowledge.fake", "knowledge.zed"]
    with pytest.raises(ValidationError):
        catalog.adapters = ()
    with pytest.raises(UnknownProviderAdapterError):
        catalog.require("knowledge.missing")


def test_adapter_catalog_rejects_duplicate_and_capability_mismatch():
    with pytest.raises(ValidationError, match="duplicate provider"):
        ProviderAdapterCatalog(adapters=(FakeAdapter(), FakeAdapter()))
    adapter = FakeAdapter()
    adapter.supported_capabilities = ("knowledge.other",)
    with pytest.raises(ProviderAdapterCapabilityError):
        ProviderAdapterCatalog.from_adapters([adapter]).validate_descriptors(
            ProviderCatalog.from_providers([descriptor()])
        )


@pytest.mark.asyncio
async def test_success_normalizes_output_evidence_metrics_and_calls_once(scope):
    adapter = FakeAdapter()
    binding, dispatch, session, context, state = scope
    before = state.model_dump()
    outcome = await executor(adapter).execute(
        binding=binding,
        dispatch=dispatch,
        session=session,
        context=context,
        runtime_state=state,
        expected_runtime_revision=1,
    )
    assert outcome.step_result.status is StepStatus.SUCCEEDED
    assert outcome.step_result.output == {"answer": "safe"}
    assert outcome.step_result.evidence[0].record_id == "record-1"
    assert outcome.step_result.metrics.provider_calls == 1
    assert len(adapter.calls) == 1
    assert state.model_dump() == before
    request, invocation_context = adapter.calls[0]
    assert request.idempotency_key == binding.idempotency_key
    assert invocation_context.binding_id == binding.binding_id
    assert not {"credential", "endpoint", "authorization"} & type(request).model_fields.keys()


@pytest.mark.asyncio
@pytest.mark.parametrize("field", ["dispatch_id", "execution_id", "organization_id"])
async def test_identity_mismatch_is_rejected(scope, field):
    binding, dispatch, session, context, state = scope
    dispatch = dispatch.model_copy(update={field: uuid4()})
    with pytest.raises(ExecutorIdentityMismatchError):
        await executor(FakeAdapter()).execute(
            binding=binding,
            dispatch=dispatch,
            session=session,
            context=context,
            runtime_state=state,
            expected_runtime_revision=1,
        )


@pytest.mark.asyncio
async def test_stale_revision_is_rejected(scope):
    binding, dispatch, session, context, state = scope
    with pytest.raises(ExecutorRevisionConflictError):
        await executor(FakeAdapter()).execute(
            binding=binding,
            dispatch=dispatch,
            session=session,
            context=context,
            runtime_state=state,
            expected_runtime_revision=0,
        )


@pytest.mark.asyncio
async def test_non_running_step_and_session_are_rejected(scope):
    binding, dispatch, session, context, state = scope
    ready = state.model_copy(
        update={
            "step_states": (RuntimeStepState(step_id="search", status=RuntimeStepStatus.READY),)
        }
    )
    with pytest.raises(ExecutorStepStateError):
        await executor(FakeAdapter()).execute(
            binding=binding,
            dispatch=dispatch,
            session=session,
            context=context,
            runtime_state=ready,
            expected_runtime_revision=1,
        )


@pytest.mark.asyncio
async def test_exact_deadline_returns_timeout_without_call(scope):
    binding, dispatch, session, context, state = scope
    adapter = FakeAdapter()
    outcome = await executor(adapter, FixedClock(binding.deadline)).execute(
        binding=binding,
        dispatch=dispatch,
        session=session,
        context=context,
        runtime_state=state,
        expected_runtime_revision=1,
    )
    assert outcome.step_result.status is StepStatus.TIMED_OUT
    assert outcome.step_result.output is None
    assert outcome.retryable
    assert not adapter.calls


@pytest.mark.asyncio
async def test_preflight_cancellation_returns_safe_result_without_call(scope):
    binding, dispatch, session, context, state = scope
    state = state.model_copy(update={"cancellation_requested": True})
    adapter = FakeAdapter()
    outcome = await executor(adapter).execute(
        binding=binding,
        dispatch=dispatch,
        session=session,
        context=context,
        runtime_state=state,
        expected_runtime_revision=1,
    )
    assert outcome.step_result.status is StepStatus.CANCELLED
    assert not adapter.calls


@pytest.mark.asyncio
async def test_late_success_is_timed_out_and_output_discarded(scope):
    binding, dispatch, session, context, state = scope
    adapter = FakeAdapter(
        ProviderInvocationOutcome(
            provider_id="knowledge.fake",
            capability_id="knowledge.search",
            step_id="search",
            attempt=1,
            status=InvocationStatus.SUCCEEDED,
            output={"late": True},
            started_at=NOW,
            completed_at=binding.deadline,
        )
    )
    outcome = await executor(adapter).execute(
        binding=binding,
        dispatch=dispatch,
        session=session,
        context=context,
        runtime_state=state,
        expected_runtime_revision=1,
    )
    assert outcome.step_result.status is StepStatus.TIMED_OUT
    assert outcome.step_result.output is None
    assert outcome.warnings == ("late_provider_result_discarded",)


@pytest.mark.asyncio
async def test_raw_adapter_exception_is_safely_normalized(scope):
    binding, dispatch, session, context, state = scope
    secret = "sensitive traceback material"
    outcome = await executor(FakeAdapter(error=RuntimeError(secret))).execute(
        binding=binding,
        dispatch=dispatch,
        session=session,
        context=context,
        runtime_state=state,
        expected_runtime_revision=1,
    )
    assert outcome.step_result.status is StepStatus.FAILED
    assert secret not in str(outcome.step_result.error)
    assert outcome.step_result.error.code == "provider_invocation_failed"


@pytest.mark.asyncio
async def test_provider_result_identity_mismatch_is_rejected(scope):
    binding, dispatch, session, context, state = scope
    bad = ProviderInvocationOutcome(
        provider_id="knowledge.other",
        capability_id="knowledge.search",
        step_id="search",
        attempt=1,
        status=InvocationStatus.SUCCEEDED,
        started_at=NOW,
        completed_at=NOW,
    )
    with pytest.raises(ProviderResultMismatchError):
        await executor(FakeAdapter(outcome=bad)).execute(
            binding=binding,
            dispatch=dispatch,
            session=session,
            context=context,
            runtime_state=state,
            expected_runtime_revision=1,
        )


def test_invocation_outcome_rejects_naive_time_and_unsafe_output():
    with pytest.raises(ValidationError):
        ProviderInvocationOutcome(
            provider_id="knowledge.fake",
            capability_id="knowledge.search",
            step_id="search",
            attempt=1,
            status=InvocationStatus.SUCCEEDED,
            output={"authorization": "Bearer hidden-value"},
            started_at=datetime(2026, 1, 1),
            completed_at=datetime(2026, 1, 1),
        )


class FakeKoreanBoundary:
    def __init__(self, result):
        self.result = result
        self.calls = []

    async def execute(self, request, context):
        self.calls.append((request, context))
        return self.result


class FakeKoreanFactory:
    def __init__(self, boundary):
        self.boundary = boundary
        self.organizations = []

    def for_organization(self, organization_id):
        self.organizations.append(organization_id)
        return self.boundary


def korean_result(organization_id):
    evidence = KnowledgeEvidence(
        source_type="law",
        title="법령",
        resource_id="law-1",
        provenance="mcp:korean-law-mcp",
        provider_name="korean-law-mcp",
        provider_type=KnowledgeProviderType.MCP,
        classification=DataClassification.INTERNAL,
    )
    metadata = KoreanLawExecutionMetadata(
        provider="korean-law-mcp",
        provider_type=KnowledgeProviderType.MCP,
        operation=KoreanLawMcpOperation.SEARCH_LAWS,
        source_types=("law",),
        status=KoreanLawExecutionStatus.SUCCESS,
        duration_ms=5,
        item_count=1,
        warning_codes=(),
        request_id=str(uuid4()),
        correlation_id="corr",
        organization_id=organization_id,
        retryable=False,
        fallback_attempted=False,
        query_hash="0" * 64,
        query_character_count=4,
        classification=DataClassification.INTERNAL,
    )
    return KoreanLawProviderExecutionResult(
        status=KoreanLawExecutionStatus.SUCCESS,
        evidence=(evidence,),
        requested_source_types=("law",),
        executed_operation=KoreanLawMcpOperation.SEARCH_LAWS,
        verified_capability=True,
        duration_ms=5,
        request_id=metadata.request_id,
        correlation_id="corr",
        metadata=metadata,
    )


@pytest.mark.asyncio
async def test_korean_law_adapter_maps_existing_contract_without_network(scope):
    binding, dispatch, session, context, state = scope
    binding = binding.model_copy(
        update={
            "provider_id": KOREAN_LAW_LOGICAL_PROVIDER_ID,
            "provider_kind": ProviderKind.MCP,
            "capability_id": "knowledge.legal_search",
        }
    )
    dispatch = dispatch.model_copy(
        update={
            "capability_id": "knowledge.legal_search",
            "input": {"query": "법령 검색", "source_types": ["law"]},
        }
    )
    boundary = FakeKoreanBoundary(korean_result(session.organization_id))
    adapter = KoreanLawProviderAdapter(
        FakeKoreanFactory(boundary), FixedClock(NOW, NOW + timedelta(milliseconds=5))
    )
    outcome = await executor(adapter, provider=korean_law_mcp_descriptor()).execute(
        binding=binding,
        dispatch=dispatch,
        session=session,
        context=context,
        runtime_state=state,
        expected_runtime_revision=1,
    )
    assert adapter.provider_id == korean_law_mcp_descriptor().provider_id
    assert outcome.step_result.status is StepStatus.SUCCEEDED
    assert outcome.step_result.evidence[0].record_id == "law-1"
    assert boundary.calls[0][0].query == "법령 검색"
    assert boundary.calls[0][1].organization_id == session.organization_id
