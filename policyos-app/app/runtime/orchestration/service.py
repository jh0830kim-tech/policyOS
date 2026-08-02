"""Explicit port-only coordination for runtime invocation and local commit."""

from app.runtime.orchestration.domain import (
    RuntimeOrchestrationCommitOutcome,
    RuntimeOrchestrationCommitRequest,
    RuntimeOrchestrationInvocationOutcome,
    RuntimeOrchestrationInvocationRequest,
)
from app.runtime.orchestration.errors import (
    RuntimeOrchestrationAdapterError,
    RuntimeOrchestrationCancellationError,
    RuntimeOrchestrationCredentialError,
    RuntimeOrchestrationTransactionError,
)
from app.runtime.orchestration.validation import (
    validate_runtime_orchestration_cancellation,
    validate_runtime_orchestration_clock_and_permits,
    validate_runtime_orchestration_commit_outcome,
    validate_runtime_orchestration_commit_request,
    validate_runtime_orchestration_credential_lease,
    validate_runtime_orchestration_invocation_outcome,
    validate_runtime_orchestration_invocation_request,
)
from app.runtime.ports import (
    RuntimeAdapterPort,
    RuntimeCancellationPort,
    RuntimeClockPort,
    RuntimeCredentialBrokerPort,
    RuntimeTransactionPort,
)


async def invoke_runtime_action(
    request: RuntimeOrchestrationInvocationRequest,
    *,
    adapter: RuntimeAdapterPort,
    clock: RuntimeClockPort,
    cancellation: RuntimeCancellationPort | None = None,
    credentials: RuntimeCredentialBrokerPort | None = None,
) -> RuntimeOrchestrationInvocationOutcome:
    """Invoke exactly one validated adapter port without creating policy or state."""

    validate_runtime_orchestration_invocation_request(request)
    envelope = request.envelope
    if (
        adapter.adapter_reference,
        adapter.adapter_contract_version,
        adapter.adapter_family,
    ) != (
        envelope.adapter_reference,
        envelope.adapter_contract_version,
        envelope.adapter_family,
    ):
        raise RuntimeOrchestrationAdapterError(
            "injected adapter differs from the governed invocation envelope"
        )

    cancellation_observation = None
    if request.cancellation_reference is None:
        if cancellation is not None:
            raise RuntimeOrchestrationCancellationError(
                "unused cancellation port was supplied"
            )
    else:
        if cancellation is None:
            raise RuntimeOrchestrationCancellationError(
                "cancellation observation port is required"
            )
        cancellation_observation = await cancellation.observe(
            request.cancellation_reference
        )
        validate_runtime_orchestration_cancellation(
            request, cancellation_observation
        )

    credential_lease = None
    if request.credential_lease_request is None:
        if credentials is not None:
            raise RuntimeOrchestrationCredentialError(
                "unused credential broker port was supplied"
            )
    else:
        if credentials is None:
            raise RuntimeOrchestrationCredentialError(
                "credential broker port is required"
            )
        lease_outcome = await credentials.acquire(request.credential_lease_request)
        credential_lease = validate_runtime_orchestration_credential_lease(
            request,
            request.credential_lease_request,
            lease_outcome,
        )

    reading = clock.read()
    validate_runtime_orchestration_clock_and_permits(
        request, reading, credential_lease
    )
    result = await adapter.invoke(envelope)
    outcome = RuntimeOrchestrationInvocationOutcome(
        runtime_orchestration_invocation_id=request.runtime_orchestration_invocation_id,
        contract_version=request.contract_version,
        invocation_request=request,
        clock_reading=reading,
        cancellation_observation=cancellation_observation,
        credential_lease_reference=credential_lease,
        result=result,
        completed_at=result.completed_at,
    )
    return validate_runtime_orchestration_invocation_outcome(outcome)


async def commit_runtime_action_outcome(
    request: RuntimeOrchestrationCommitRequest,
    *,
    transaction: RuntimeTransactionPort,
) -> RuntimeOrchestrationCommitOutcome:
    """Commit one caller-supplied atomic outcome without inventing runtime facts."""

    validate_runtime_orchestration_commit_request(request)
    try:
        receipt = await transaction.commit(request.write_set)
    except RuntimeOrchestrationTransactionError:
        raise
    except Exception as exc:
        raise RuntimeOrchestrationTransactionError(
            "runtime transaction port failed"
        ) from exc
    outcome = RuntimeOrchestrationCommitOutcome(
        runtime_orchestration_commit_id=request.runtime_orchestration_commit_id,
        contract_version=request.contract_version,
        transaction_receipt=receipt,
        committed_at=receipt.committed_at,
    )
    return validate_runtime_orchestration_commit_outcome(request, outcome)
