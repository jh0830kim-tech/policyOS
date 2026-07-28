"""Validated normalized invocation boundary for one exact provider adapter."""

from datetime import datetime

from app.ai_models import (
    ModelCapabilityError,
    ModelNotFoundError,
    ModelNotSelectableError,
    ModelRegistrySnapshot,
    ProviderNotFoundError,
    get_registered_model,
    get_registered_provider,
    validate_model_is_selectable,
)
from app.ai_providers.domain import (
    NormalizedModelInvocationRequest,
    NormalizedModelInvocationResult,
    permit_lineage,
    request_lineage,
)
from app.ai_providers.errors import (
    InvocationRequestMismatchError,
    ModelProviderMismatchError,
    ProviderAdapterError,
    ProviderAdapterMismatchError,
    ProviderAdapterValidationError,
    ProviderInvocationFailedError,
    ProviderRegistryMismatchError,
    UnsupportedCapabilityError,
)
from app.ai_providers.registry import ProviderAdapterRegistry
from app.ai_selection import AuthorizedInvocationPermit
from app.execution.validation import require_aware


def invoke_normalized_model(
    *,
    permit: AuthorizedInvocationPermit,
    request: NormalizedModelInvocationRequest,
    model_registry: ModelRegistrySnapshot,
    adapter_registry: ProviderAdapterRegistry,
    invoked_at: datetime,
) -> NormalizedModelInvocationResult:
    """Validate every public contract before calling exactly one explicit adapter."""
    require_aware(invoked_at, "invoked_at")
    if not isinstance(permit, AuthorizedInvocationPermit):
        raise ProviderAdapterValidationError("authorized invocation permit is required")
    if request_lineage(request) != permit_lineage(permit):
        raise InvocationRequestMismatchError("request does not match invocation permit")
    if request.created_at > invoked_at or permit.issued_at > invoked_at:
        raise InvocationRequestMismatchError("invocation lineage is not yet effective")
    if permit.expires_at is not None and invoked_at >= permit.expires_at:
        raise InvocationRequestMismatchError("invocation permit has expired")
    if (model_registry.registry_id, model_registry.revision) != (
        request.registry_id,
        request.registry_revision,
    ):
        raise ProviderRegistryMismatchError("model registry does not match invocation request")

    try:
        provider = get_registered_provider(model_registry, request.provider_instance_id)
    except ProviderNotFoundError as exc:
        raise ProviderRegistryMismatchError("registered provider was not found") from exc
    try:
        model = get_registered_model(model_registry, request.model_id)
    except ModelNotFoundError as exc:
        raise ProviderRegistryMismatchError("registered model was not found") from exc
    if model.provider_instance_id != request.provider_instance_id:
        raise ModelProviderMismatchError("registered model belongs to another provider")
    if not set(request.requested_capabilities) <= set(model.capabilities):
        raise UnsupportedCapabilityError("registered model lacks a requested capability")
    try:
        validate_model_is_selectable(
            model_registry, request.model_id, request.requested_capabilities
        )
    except ModelCapabilityError as exc:
        raise UnsupportedCapabilityError("requested capabilities are not canonical") from exc
    except ModelNotSelectableError as exc:
        raise ProviderRegistryMismatchError(
            "registered model or provider is not selectable"
        ) from exc

    adapter = adapter_registry.get(request.adapter_id)
    identity = adapter.identity
    if identity.supported_invocation_kind is not request.invocation_kind:
        raise ProviderAdapterMismatchError("adapter invocation kind does not match request")
    if identity.provider_family != provider.provider_type:
        raise ProviderAdapterMismatchError("adapter provider family does not match registry")
    if (
        identity.provider_instance_id is not None
        and identity.provider_instance_id != request.provider_instance_id
    ):
        raise ProviderAdapterMismatchError("adapter provider instance does not match request")
    if not set(request.requested_capabilities) <= set(identity.supported_capabilities):
        raise UnsupportedCapabilityError("adapter lacks a requested capability")

    try:
        result = adapter.invoke(
            permit=permit,
            request=request,
            registry=model_registry,
            invoked_at=invoked_at,
        )
    except ProviderAdapterError:
        raise
    except Exception:
        raise ProviderInvocationFailedError("provider adapter invocation failed") from None

    expected_result = (
        request.invocation_id,
        request.permit_id,
        request.selection_request_id,
        request.authorization_decision_id,
        request.approval_id,
        request.registry_id,
        request.registry_revision,
        request.provider_instance_id,
        request.model_id,
        request.adapter_id,
    )
    actual_result = (
        result.invocation_id,
        result.permit_id,
        result.selection_request_id,
        result.authorization_decision_id,
        result.approval_id,
        result.registry_id,
        result.registry_revision,
        result.provider_instance_id,
        result.model_id,
        result.adapter_id,
    )
    if actual_result != expected_result:
        raise InvocationRequestMismatchError("adapter result lineage does not match request")
    if result.started_at < invoked_at:
        raise InvocationRequestMismatchError("adapter result predates invocation")
    return result
