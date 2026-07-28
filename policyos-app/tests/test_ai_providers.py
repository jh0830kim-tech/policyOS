from datetime import UTC, datetime, timedelta
from uuid import UUID

import pytest
from pydantic import ValidationError

from app.ai.privacy import DataClassification
from app.ai_models import (
    ModelCapability,
    ModelModality,
    RegisteredModel,
    RegisteredProvider,
    RegistryLifecycleStatus,
    create_model_registry_snapshot,
)
from app.ai_providers import (
    InvocationRequestMismatchError,
    ModelProviderMismatchError,
    NormalizedContentPart,
    NormalizedFinishReason,
    NormalizedGenerationParameters,
    NormalizedInvocationFailure,
    NormalizedInvocationKind,
    NormalizedInvocationOutput,
    NormalizedMessage,
    NormalizedMessageRole,
    NormalizedModelInvocationRequest,
    NormalizedModelInvocationResult,
    NormalizedOutputPart,
    NormalizedResultStatus,
    NormalizedTokenUsage,
    ProviderAdapterAmbiguousError,
    ProviderAdapterDuplicateError,
    ProviderAdapterIdentity,
    ProviderAdapterMismatchError,
    ProviderAdapterNotFoundError,
    ProviderAdapterRegistry,
    ProviderAdapterValidationError,
    ProviderInvocationFailedError,
    ProviderRegistryMismatchError,
    UnsupportedCapabilityError,
    create_provider_adapter_registry,
    create_provider_invocation_audit_record,
    invoke_normalized_model,
)
from app.ai_selection import (
    ModelSelectionContext,
    ResourceType,
    SelectionAction,
    SelectionPolicyFacts,
    SelectionRiskLevel,
    SelectionTargetType,
    TargetTrustBoundary,
    authorize_model_invocation,
    evaluate_model_selection_policy,
)

NOW = datetime(2026, 7, 29, 1, tzinfo=UTC)
TENANT = UUID("11111111-1111-1111-1111-111111111111")
REGISTRY_ID = UUID("22222222-2222-2222-2222-222222222222")
CAPABILITIES = (ModelCapability.REASONING, ModelCapability.TEXT_GENERATION)


def provider(provider_id="provider-a", **changes):
    values = dict(
        provider_instance_id=provider_id,
        provider_type="private",
        display_name=provider_id,
        status=RegistryLifecycleStatus.ACTIVE,
        supported_capabilities=CAPABILITIES,
        created_at=NOW,
        updated_at=NOW,
    )
    values.update(changes)
    return RegisteredProvider(**values)


def model(model_id="model-a", provider_id="provider-a", **changes):
    values = dict(
        model_id=model_id,
        provider_instance_id=provider_id,
        provider_model_name=model_id,
        display_name=model_id,
        version="1",
        revision="r1",
        status=RegistryLifecycleStatus.ACTIVE,
        capabilities=CAPABILITIES,
        supported_input_modalities=(ModelModality.TEXT,),
        supported_output_modalities=(ModelModality.TEXT,),
        created_at=NOW,
        updated_at=NOW,
    )
    values.update(changes)
    return RegisteredModel(**values)


def model_registry(*, providers=None, models=None, revision=7):
    return create_model_registry_snapshot(
        registry_id=REGISTRY_ID,
        revision=revision,
        providers=(provider(),) if providers is None else providers,
        models=(model(),) if models is None else models,
        created_at=NOW,
    )


def permit(**changes):
    ctx_values = dict(
        selection_request_id=UUID(int=3),
        tenant_id=TENANT,
        actor_id="actor-a",
        resource_id="document-a",
        resource_type=ResourceType.DOCUMENT,
        action=SelectionAction.INTERNAL_SUMMARY,
        purpose="policy-briefing",
        classification=DataClassification.CONFIDENTIAL,
        risk_level=SelectionRiskLevel.MODERATE,
        target_type=SelectionTargetType.MODEL,
        trust_boundary=TargetTrustBoundary.INTERNAL,
        registry_id=REGISTRY_ID,
        registry_revision=7,
        model_id="model-a",
        provider_instance_id="provider-a",
        requested_capabilities=(ModelCapability.TEXT_GENERATION,),
        external_transmission=False,
        created_at=NOW,
    )
    ctx_values.update(changes)
    ctx = ModelSelectionContext(**ctx_values)
    facts = SelectionPolicyFacts(
        policy_revision="policy-7",
        tenant_id=ctx.tenant_id,
        permitted_actions=(ctx.action,),
        permitted_purposes=(ctx.purpose,),
        permitted_resource_ids=(ctx.resource_id,),
        permitted_classifications=(ctx.classification,),
        permitted_model_ids=(ctx.model_id,),
        permitted_provider_instance_ids=(ctx.provider_instance_id,),
    )
    registry = model_registry()
    decision = evaluate_model_selection_policy(
        ctx, registry, facts, decision_id=UUID(int=4), decided_at=NOW
    )
    return authorize_model_invocation(
        ctx, decision, registry, permit_id=UUID(int=5), issued_at=NOW
    )


def request(auth=None, **changes):
    auth = auth or permit()
    values = dict(
        invocation_id=UUID(int=6),
        permit_id=auth.permit_id,
        selection_request_id=auth.selection_request_id,
        authorization_decision_id=auth.authorization_decision_id,
        approval_id=auth.approval_id,
        tenant_id=auth.tenant_id,
        resource_id=auth.resource_id,
        action=auth.action,
        purpose=auth.purpose,
        registry_id=auth.registry_id,
        registry_revision=auth.registry_revision,
        provider_instance_id=auth.provider_instance_id,
        model_id=auth.model_id,
        adapter_id="adapter-a",
        messages=(
            NormalizedMessage(
                role=NormalizedMessageRole.USER,
                content=(NormalizedContentPart(text="Summarize the policy"),),
            ),
        ),
        requested_capabilities=(ModelCapability.TEXT_GENERATION,),
        created_at=NOW,
    )
    values.update(changes)
    return NormalizedModelInvocationRequest(**values)


def identity(adapter_id="adapter-a", provider_id="provider-a", **changes):
    values = dict(
        adapter_id=adapter_id,
        provider_family="private",
        provider_instance_id=provider_id,
        adapter_version="1.0",
        supported_invocation_kind=NormalizedInvocationKind.TEXT_GENERATION,
        supported_capabilities=CAPABILITIES,
    )
    values.update(changes)
    return ProviderAdapterIdentity(**values)


def result(req=None, **changes):
    req = req or request()
    values = dict(
        invocation_id=req.invocation_id,
        permit_id=req.permit_id,
        selection_request_id=req.selection_request_id,
        authorization_decision_id=req.authorization_decision_id,
        approval_id=req.approval_id,
        registry_id=req.registry_id,
        registry_revision=req.registry_revision,
        provider_instance_id=req.provider_instance_id,
        model_id=req.model_id,
        adapter_id=req.adapter_id,
        status=NormalizedResultStatus.SUCCEEDED,
        output=NormalizedInvocationOutput(parts=(NormalizedOutputPart(text="Summary"),)),
        usage=NormalizedTokenUsage(input_tokens=10, output_tokens=4, total_tokens=14),
        finish_reason=NormalizedFinishReason.STOP,
        started_at=NOW,
        completed_at=NOW + timedelta(seconds=1),
        provider_request_id="provider-request-1",
    )
    values.update(changes)
    return NormalizedModelInvocationResult(**values)


class RecordingAdapter:
    def __init__(self, adapter_identity=None, configured_result=None, error=None):
        self._identity = adapter_identity or identity()
        self.configured_result = configured_result
        self.error = error
        self.calls = []

    @property
    def identity(self):
        return self._identity

    def invoke(self, *, permit, request, registry, invoked_at):
        self.calls.append((permit, request, registry, invoked_at))
        if self.error:
            raise self.error
        return self.configured_result or result(request)


def invoke(adapter=None, auth=None, req=None, registry=None, adapters=None):
    auth = auth or permit()
    req = req or request(auth)
    adapter = adapter or RecordingAdapter(configured_result=result(req))
    adapter_registry = adapters or create_provider_adapter_registry((adapter,))
    output = invoke_normalized_model(
        permit=auth,
        request=req,
        model_registry=registry or model_registry(),
        adapter_registry=adapter_registry,
        invoked_at=NOW,
    )
    return output, adapter


def test_request_contract_is_frozen_strict_bounded_and_aware():
    item = request()
    with pytest.raises(ValidationError):
        item.model_id = "other"
    with pytest.raises(ValidationError):
        request(raw_payload={})
    with pytest.raises(ValidationError):
        request(created_at=NOW.replace(tzinfo=None))
    with pytest.raises(ValidationError):
        request(resource_id="x" * 201)


def test_message_content_is_typed_ordered_and_bounded():
    message = NormalizedMessage(
        role=NormalizedMessageRole.SYSTEM,
        content=(NormalizedContentPart(text="first"), NormalizedContentPart(text="second")),
    )
    assert tuple(part.text for part in message.content) == ("first", "second")
    with pytest.raises(ValidationError):
        NormalizedContentPart(text=" ")


@pytest.mark.parametrize(
    "changes",
    [
        {"temperature": -0.1},
        {"temperature": 2.1},
        {"top_p": 0},
        {"max_output_tokens": 0},
        {"deterministic_seed": -1},
        {"stop_sequences": ("z", "a")},
    ],
)
def test_generation_parameter_bounds_and_canonical_stops(changes):
    with pytest.raises(ValidationError):
        NormalizedGenerationParameters(**changes)


def test_capabilities_are_canonical_and_extra_result_payload_is_rejected():
    with pytest.raises(ValidationError):
        request(requested_capabilities=tuple(reversed(CAPABILITIES)))
    with pytest.raises(ValidationError):
        result(raw_provider_response={})


def test_result_and_usage_contracts_are_exact_immutable_and_aware():
    item = result()
    assert item.usage.total_tokens == 14
    with pytest.raises(ValidationError):
        item.status = NormalizedResultStatus.FAILED
    with pytest.raises(ValidationError):
        NormalizedTokenUsage(input_tokens=-1, output_tokens=0, total_tokens=0)
    with pytest.raises(ValidationError):
        NormalizedTokenUsage(input_tokens=1, output_tokens=1, total_tokens=3)
    with pytest.raises(ValidationError):
        result(started_at=NOW.replace(tzinfo=None))
    with pytest.raises(ValidationError):
        result(provider_request_id="x" * 201)


def test_failed_result_is_typed_and_absent_usage_is_permitted():
    item = result(
        status=NormalizedResultStatus.FAILED,
        output=None,
        usage=None,
        finish_reason=NormalizedFinishReason.ERROR,
        failure=NormalizedInvocationFailure(code="provider_failed", message="Provider failed"),
    )
    assert item.usage is None
    assert item.failure.code == "provider_failed"


def test_adapter_registry_is_canonical_exact_and_immutable():
    second = RecordingAdapter(identity("adapter-b", "provider-b"))
    first = RecordingAdapter()
    registry = create_provider_adapter_registry((second, first))
    assert tuple(item.identity.adapter_id for item in registry.adapters) == (
        "adapter-a",
        "adapter-b",
    )
    assert registry.get("adapter-a") is first
    with pytest.raises(AttributeError):
        registry.adapters = ()


def test_adapter_registry_rejects_duplicate_unknown_and_ambiguous_lookup():
    with pytest.raises(ProviderAdapterDuplicateError):
        create_provider_adapter_registry((RecordingAdapter(), RecordingAdapter()))
    registry = create_provider_adapter_registry(
        (RecordingAdapter(), RecordingAdapter(identity("adapter-b")))
    )
    with pytest.raises(ProviderAdapterNotFoundError):
        registry.get("missing")
    with pytest.raises(ProviderAdapterAmbiguousError):
        registry.for_provider_instance("provider-a")
    with pytest.raises(ProviderAdapterValidationError):
        ProviderAdapterRegistry(tuple(reversed(registry.adapters)))


@pytest.mark.parametrize(
    "field,value",
    [
        ("permit_id", UUID(int=70)),
        ("selection_request_id", UUID(int=71)),
        ("authorization_decision_id", UUID(int=72)),
        ("approval_id", UUID(int=73)),
        ("tenant_id", UUID(int=74)),
        ("resource_id", "document-b"),
        ("action", SelectionAction.INTERNAL_ANALYSIS),
        ("purpose", "other-purpose"),
        ("registry_id", UUID(int=75)),
        ("registry_revision", 8),
        ("provider_instance_id", "provider-b"),
        ("model_id", "model-b"),
    ],
)
def test_request_permit_lineage_mismatch_produces_zero_calls(field, value):
    auth = permit()
    req = request(auth).model_copy(update={field: value})
    adapter = RecordingAdapter()
    with pytest.raises(InvocationRequestMismatchError):
        invoke(adapter=adapter, auth=auth, req=req)
    assert adapter.calls == []


def test_missing_or_expired_permit_produces_zero_calls():
    adapter = RecordingAdapter()
    with pytest.raises(ProviderAdapterValidationError):
        invoke_normalized_model(
            permit=None,
            request=request(),
            model_registry=model_registry(),
            adapter_registry=create_provider_adapter_registry((adapter,)),
            invoked_at=NOW,
        )
    expired = permit().model_copy(update={"expires_at": NOW})
    with pytest.raises(InvocationRequestMismatchError):
        invoke(adapter=adapter, auth=expired, req=request(expired))
    assert adapter.calls == []


@pytest.mark.parametrize(
    "registry",
    [
        model_registry(models=(model(status=RegistryLifecycleStatus.DISABLED),)),
        model_registry(providers=(provider(status=RegistryLifecycleStatus.DISABLED),)),
        model_registry(models=()),
        model_registry(providers=(), models=()),
    ],
)
def test_invalid_registry_model_or_provider_produces_zero_calls(registry):
    adapter = RecordingAdapter()
    with pytest.raises(ProviderRegistryMismatchError):
        invoke(adapter=adapter, registry=registry)
    assert adapter.calls == []


def test_registry_revision_model_provider_and_capability_fail_before_call():
    adapter = RecordingAdapter()
    with pytest.raises(ProviderRegistryMismatchError):
        invoke(adapter=adapter, registry=model_registry(revision=8))
    auth = permit().model_copy(update={"provider_instance_id": "provider-b"})
    req = request(auth)
    two = model_registry(providers=(provider(), provider("provider-b")))
    with pytest.raises(ModelProviderMismatchError):
        invoke(adapter=adapter, auth=auth, req=req, registry=two)
    with pytest.raises(UnsupportedCapabilityError):
        invoke(adapter=adapter, req=request(requested_capabilities=(ModelCapability.VISION,)))
    assert adapter.calls == []


def test_adapter_mismatch_unknown_and_ambiguous_lookup_produce_zero_calls():
    mismatch = RecordingAdapter(identity(provider_id="provider-b"))
    with pytest.raises(ProviderAdapterMismatchError):
        invoke(adapter=mismatch)
    valid = RecordingAdapter()
    with pytest.raises(ProviderAdapterNotFoundError):
        invoke(
            adapter=valid,
            req=request(adapter_id="missing"),
            adapters=create_provider_adapter_registry((valid,)),
        )
    ambiguous_registry = create_provider_adapter_registry(
        (valid, RecordingAdapter(identity("adapter-b")))
    )
    with pytest.raises(ProviderAdapterAmbiguousError):
        ambiguous_registry.for_provider_instance("provider-a")
    assert valid.calls == []
    assert mismatch.calls == []


def test_valid_request_calls_exact_adapter_once_and_retains_lineage():
    output, adapter = invoke()
    assert len(adapter.calls) == 1
    assert output.invocation_id == request().invocation_id
    assert output.adapter_id == "adapter-a"
    assert output.finish_reason is NormalizedFinishReason.STOP


def test_adapter_exception_is_typed_with_one_call_and_no_retry_or_fallback():
    failing = RecordingAdapter(error=RuntimeError("unsafe provider detail"))
    fallback = RecordingAdapter(identity("adapter-b"))
    registry = create_provider_adapter_registry((failing, fallback))
    with pytest.raises(ProviderInvocationFailedError) as raised:
        invoke(adapter=failing, adapters=registry)
    assert str(raised.value) == "provider adapter invocation failed"
    assert len(failing.calls) == 1
    assert fallback.calls == []


def test_mismatched_adapter_result_is_rejected_after_one_call():
    req = request()
    adapter = RecordingAdapter(configured_result=result(req, model_id="model-b"))
    with pytest.raises(InvocationRequestMismatchError):
        invoke(adapter=adapter, req=req)
    assert len(adapter.calls) == 1


def test_metadata_only_audit_is_deterministic_and_excludes_content():
    output = result()
    audit = create_provider_invocation_audit_record(
        output, audit_id=UUID(int=80), recorded_at=NOW
    )
    assert audit.model_id == output.model_id
    assert audit.usage == output.usage
    assert audit == create_provider_invocation_audit_record(
        output, audit_id=UUID(int=80), recorded_at=NOW
    )
    assert not {"messages", "output", "failure"} & set(type(audit).model_fields)


def test_public_boundary_has_no_sdk_payload_or_network_surface():
    import inspect

    import app.ai_providers as package
    import app.ai_providers.invocation as boundary

    assert " import *" not in inspect.getsource(package)
    public_names = set(package.__all__)
    assert not {"raw_payload", "credentials", "headers", "sdk_client"} & public_names
    source = inspect.getsource(boundary).lower()
    for forbidden in (
        "openai",
        "anthropic",
        "gemini",
        "ollama",
        "httpx",
        "requests",
        "datetime.now",
        "uuid4",
        "random",
        "fallback",
        "retry",
    ):
        assert forbidden not in source
