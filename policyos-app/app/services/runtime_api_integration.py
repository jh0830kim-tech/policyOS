"""Concrete CP9 Runtime API application integration without transaction ownership."""

from collections.abc import Callable
from typing import TypeVar

from sqlalchemy.ext.asyncio import AsyncSession

from app.runtime.ports import (
    RuntimeApiActiveTransactionContext,
    RuntimeApiExactExecutionStateRevisionReader,
    RuntimeApiExactLogicalExecutionResultRevisionReader,
    RuntimeApiLocalWriteSetStage,
    RuntimeApiPersistenceBindingRead,
    RuntimeApiQueryResultPresentLocator,
)
from app.services.runtime_api_contracts import (
    BoundedDigest,
    RuntimeApiCommandIdentity,
    RuntimeApiInvocationQuery,
    RuntimeApiInvocationQueryFacts,
    RuntimeApiInvocationQueryInput,
    RuntimeApiInvocationQueryIntegrationFacts,
    RuntimeApiOperation,
    RuntimeApiPermissionFact,
    RuntimeApiReconciliationCommand,
    RuntimeApiReconciliationFacts,
    RuntimeApiReconciliationInput,
    RuntimeApiReconciliationIntegrationFacts,
    RuntimeApiSafeResult,
    RuntimeApiStatusProjection,
    RuntimeApiSubmissionCommand,
    RuntimeApiSubmissionFacts,
    RuntimeApiSubmissionInput,
    RuntimeApiSubmissionIntegrationFacts,
    RuntimeApiTrustedPrincipal,
    RuntimeApiTrustedScope,
)
from app.services.runtime_api_protocols import (
    RuntimeApiActiveTransactionPersistenceFactory,
    RuntimeApiDomainOperationCallback,
)
from app.services.runtime_api_validation import (
    runtime_api_public_status_for_execution_state,
    validate_runtime_api_domain_operation_result,
    validate_runtime_api_persistence_binding,
    validate_runtime_api_persistence_resolution,
    validate_runtime_api_registry_resolution_admission,
    validate_runtime_api_result_count,
)

IntegrationFacts = (
    RuntimeApiSubmissionIntegrationFacts
    | RuntimeApiInvocationQueryIntegrationFacts
    | RuntimeApiReconciliationIntegrationFacts
)
IntegrationFactsT = TypeVar("IntegrationFactsT", bound=IntegrationFacts)
ReaderFactory = Callable[
    [AsyncSession, RuntimeApiActiveTransactionContext],
    RuntimeApiExactExecutionStateRevisionReader
    | RuntimeApiExactLogicalExecutionResultRevisionReader,
]


class RuntimeApiIntegrationError(RuntimeError):
    """A bounded application-integration failure."""


class OneShotRuntimeApiIntegrationFactsProvider:
    """Return one already-governed integration-facts value for one request."""

    def __init__(self, facts: IntegrationFacts) -> None:
        self._facts = facts
        self._used = False

    def _take(self, expected: type[IntegrationFactsT]) -> IntegrationFactsT:
        if self._used:
            raise RuntimeApiIntegrationError("integration facts provider is one-shot")
        self._used = True
        if not isinstance(self._facts, expected):
            raise RuntimeApiIntegrationError("integration facts operation differs")
        return self._facts

    async def provide_submission(self) -> RuntimeApiSubmissionIntegrationFacts:
        return self._take(RuntimeApiSubmissionIntegrationFacts)

    async def provide_query(self) -> RuntimeApiInvocationQueryIntegrationFacts:
        return self._take(RuntimeApiInvocationQueryIntegrationFacts)

    async def provide_reconciliation(self) -> RuntimeApiReconciliationIntegrationFacts:
        return self._take(RuntimeApiReconciliationIntegrationFacts)


class RuntimeApiExactOrchestrationFactBinder:
    """Purely bind trusted facade inputs without database access or fact generation."""

    def __init__(self, _session: AsyncSession) -> None:
        pass

    async def bind_submission(
        self,
        principal: RuntimeApiTrustedPrincipal,
        scope: RuntimeApiTrustedScope,
        permission: RuntimeApiPermissionFact,
        request: RuntimeApiSubmissionInput,
        facts: RuntimeApiSubmissionFacts,
        command_digest: BoundedDigest,
    ) -> RuntimeApiSubmissionCommand:
        return RuntimeApiSubmissionCommand(
            identity=RuntimeApiCommandIdentity(
                command_id=facts.command_id,
                operation=RuntimeApiOperation.SUBMIT_INVOCATION,
                tenant_id=scope.tenant_id,
                organization_id=scope.organization_id,
                principal_id=principal.principal_id,
                command_version=facts.command_version,
                idempotency_key=request.idempotency_key,
                command_digest=command_digest,
                correlation_reference=facts.correlation_reference,
            ),
            principal=principal,
            scope=scope,
            permission=permission,
            action_reference=request.action_reference,
            command_reference=request.command_reference,
            invocation_reference=facts.integration.invocation_reference,
            input_reference=request.input_reference,
            classification=request.classification,
            integration=facts.integration,
        )

    async def bind_query(
        self,
        principal: RuntimeApiTrustedPrincipal,
        scope: RuntimeApiTrustedScope,
        permission: RuntimeApiPermissionFact,
        request: RuntimeApiInvocationQueryInput,
        facts: RuntimeApiInvocationQueryFacts,
    ) -> RuntimeApiInvocationQuery:
        return RuntimeApiInvocationQuery(
            query_id=facts.query_id,
            principal=principal,
            scope=scope,
            permission=permission,
            invocation_reference=request.invocation_reference,
            correlation_reference=facts.correlation_reference,
            integration=facts.integration,
        )

    async def bind_reconciliation(
        self,
        principal: RuntimeApiTrustedPrincipal,
        scope: RuntimeApiTrustedScope,
        permission: RuntimeApiPermissionFact,
        request: RuntimeApiReconciliationInput,
        facts: RuntimeApiReconciliationFacts,
        command_digest: BoundedDigest,
    ) -> RuntimeApiReconciliationCommand:
        return RuntimeApiReconciliationCommand(
            identity=RuntimeApiCommandIdentity(
                command_id=facts.command_id,
                operation=RuntimeApiOperation.REQUEST_RECONCILIATION,
                tenant_id=scope.tenant_id,
                organization_id=scope.organization_id,
                principal_id=principal.principal_id,
                command_version=facts.command_version,
                idempotency_key=request.idempotency_key,
                command_digest=command_digest,
                correlation_reference=facts.correlation_reference,
            ),
            principal=principal,
            scope=scope,
            permission=permission,
            invocation_reference=request.invocation_reference,
            reconciliation_reference=request.reconciliation_reference,
            integration=facts.integration,
        )


class RuntimeApiActiveTransactionLocalOperation:
    """Verify, execute, and stage one operation in the facade-owned transaction."""

    def __init__(
        self,
        session: AsyncSession,
        *,
        persistence_factory: RuntimeApiActiveTransactionPersistenceFactory,
        state_reader_factory: ReaderFactory,
        logical_result_reader_factory: ReaderFactory,
        domain_callback: RuntimeApiDomainOperationCallback,
    ) -> None:
        self._session = session
        self._persistence_factory = persistence_factory
        self._state_reader_factory = state_reader_factory
        self._logical_result_reader_factory = logical_result_reader_factory
        self._domain_callback = domain_callback

    async def _resolve_binding(
        self,
        context: RuntimeApiActiveTransactionContext,
        expected: RuntimeApiPersistenceBindingRead,
    ) -> RuntimeApiPersistenceBindingRead:
        resolved = await self._persistence_factory(self._session, context).read_exact(
            context,
            expected,
        )
        resolved = validate_runtime_api_persistence_resolution(expected, resolved)
        validate_runtime_api_persistence_binding(
            resolved,
            tenant_id=expected.scope.tenant_id,
            organization_id=expected.scope.organization_id,
            classification=expected.scope.classification,
            root_lineage_id=expected.scope.root_lineage_id,
            root_lineage_digest_reference=expected.scope.root_lineage_digest_reference,
        )
        validate_runtime_api_registry_resolution_admission(resolved)
        return resolved

    async def _mutate(
        self,
        command: RuntimeApiSubmissionCommand | RuntimeApiReconciliationCommand,
    ) -> RuntimeApiSafeResult:
        integration = command.integration
        await self._resolve_binding(
            integration.active_transaction,
            integration.binding.persistence,
        )
        result = validate_runtime_api_domain_operation_result(
            command,
            await self._domain_callback(command),
        )
        staged = await self._persistence_factory(
            self._session,
            integration.active_transaction,
        ).stage_local_write_set(
            integration.active_transaction,
            result.stage,
        )
        self._validate_stage_result(result.stage, staged)
        return result.safe_result

    @staticmethod
    def _validate_stage_result(stage: RuntimeApiLocalWriteSetStage, staged) -> None:
        if (
            staged.local_write_set_id,
            staged.transport_receipt_id,
            staged.operation,
            staged.write_set_digest_reference,
            staged.staged_mutation_count,
        ) != (
            stage.local_write_set_id,
            stage.transport_receipt_id,
            stage.operation,
            stage.write_set_digest_reference,
            1,
        ):
            raise RuntimeApiIntegrationError("local stage receipt differs")

    async def submit_invocation(
        self,
        command: RuntimeApiSubmissionCommand,
    ) -> RuntimeApiSafeResult:
        return await self._mutate(command)

    async def request_reconciliation(
        self,
        command: RuntimeApiReconciliationCommand,
    ) -> RuntimeApiSafeResult:
        return await self._mutate(command)

    async def get_invocation(
        self,
        query: RuntimeApiInvocationQuery,
    ) -> RuntimeApiStatusProjection:
        integration = query.integration
        context = integration.active_transaction
        locator = integration.locator
        await self._resolve_binding(context, integration.binding.persistence)
        state_reader = self._state_reader_factory(self._session, context)
        if not isinstance(state_reader, RuntimeApiExactExecutionStateRevisionReader):
            raise RuntimeApiIntegrationError("exact state reader capability differs")
        state_read = await state_reader.read_exact_state_revision(context, locator)
        result_count = int(isinstance(locator.result, RuntimeApiQueryResultPresentLocator))
        validate_runtime_api_result_count(state_read.state, result_count)
        if isinstance(locator.result, RuntimeApiQueryResultPresentLocator):
            result_reader = self._logical_result_reader_factory(self._session, context)
            if not isinstance(
                result_reader,
                RuntimeApiExactLogicalExecutionResultRevisionReader,
            ):
                raise RuntimeApiIntegrationError("exact logical-result reader capability differs")
            result_read = await result_reader.read_exact_logical_execution_result_revision(
                context,
                locator,
            )
            logical_result = result_read.logical_execution_result
            if (
                result_read.locator != locator
                or logical_result.runtime_logical_execution_result_id
                != locator.result.logical_execution_result.record_id
                or logical_result.result_revision
                != locator.result.logical_execution_result.expected_revision
                or logical_result.execution_request != locator.execution_request
                or logical_result.execution_state != locator.execution_state
                or logical_result.audit_trail != locator.audit_trail
                or logical_result.attempt_id != locator.attempt_id
                or logical_result.scope != locator.scope
            ):
                raise RuntimeApiIntegrationError("logical-result read differs")
        return RuntimeApiStatusProjection(
            invocation_reference=query.invocation_reference,
            status=runtime_api_public_status_for_execution_state(state_read.state),
            status_reference=state_read.record_digest_reference,
            correlation_reference=query.correlation_reference,
            observed_at=state_read.observed_at,
        )


__all__ = (
    "OneShotRuntimeApiIntegrationFactsProvider",
    "RuntimeApiActiveTransactionLocalOperation",
    "RuntimeApiExactOrchestrationFactBinder",
    "RuntimeApiIntegrationError",
)
