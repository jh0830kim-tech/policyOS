"""Transaction-owning CP9 trusted Runtime API application facade."""

from collections.abc import Callable

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.auth_claims import VerifiedAccessTokenClaims
from app.services.runtime_api_contracts import (
    RuntimeApiContractConflict,
    RuntimeApiIdempotencyCommitFacts,
    RuntimeApiInvocationQueryFacts,
    RuntimeApiInvocationQueryInput,
    RuntimeApiOperation,
    RuntimeApiOrganizationSelector,
    RuntimeApiReconciliationFacts,
    RuntimeApiReconciliationInput,
    RuntimeApiReconciliationResult,
    RuntimeApiStatusProjection,
    RuntimeApiSubmissionFacts,
    RuntimeApiSubmissionInput,
    RuntimeApiSubmissionResult,
)
from app.services.runtime_api_idempotency import (
    RuntimeApiIdempotencyPersistenceError,
    SQLAlchemyRuntimeApiIdempotencyTransaction,
)
from app.services.runtime_api_protocols import (
    RuntimeApiLocalOperationPort,
    RuntimeApiOrchestrationFactBinder,
)
from app.services.runtime_api_validation import (
    build_runtime_api_reconciliation_digest,
    build_runtime_api_submission_digest,
    required_runtime_api_permission,
    validate_runtime_api_commit_result,
    validate_runtime_api_invocation_query_binding,
    validate_runtime_api_projection_binding,
    validate_runtime_api_reconciliation_binding,
    validate_runtime_api_submission_binding,
)
from app.services.runtime_permission_facts import (
    RuntimePermissionFactError,
    SQLAlchemyRuntimeApiPermissionFactResolver,
)
from app.services.runtime_tenant_binding import (
    RuntimeTenantBindingError,
    SQLAlchemyRuntimeApiTrustedContextResolver,
)

RuntimeApiOrchestrationFactBinderFactory = Callable[
    [AsyncSession], RuntimeApiOrchestrationFactBinder
]
RuntimeApiLocalOperationPortFactory = Callable[[AsyncSession], RuntimeApiLocalOperationPort]


class RuntimeApiFacadeError(RuntimeError):
    """A generic non-disclosing facade dependency failure."""


class RuntimeApiFacadeTransactionRequiredError(RuntimeApiFacadeError):
    """The facade requires ownership of a new caller transaction."""


class SQLAlchemyRuntimeApiApplicationFacade:
    def __init__(
        self,
        session: AsyncSession,
        *,
        required_audience: str,
        binder_factory: RuntimeApiOrchestrationFactBinderFactory,
        local_operation_factory: RuntimeApiLocalOperationPortFactory,
    ) -> None:
        self._session = session
        self._required_audience = required_audience
        self._binder_factory = binder_factory
        self._local_operation_factory = local_operation_factory

    def _require_transaction_ownership(self) -> None:
        if self._session.in_transaction():
            raise RuntimeApiFacadeTransactionRequiredError(
                "facade requires ownership of a new transaction"
            )

    async def submit_invocation(
        self,
        request: RuntimeApiSubmissionInput,
        claims: VerifiedAccessTokenClaims,
        organization: RuntimeApiOrganizationSelector,
        facts: RuntimeApiSubmissionFacts,
    ) -> RuntimeApiSubmissionResult:
        self._require_transaction_ownership()
        try:
            async with self._session.begin():
                resolver = SQLAlchemyRuntimeApiTrustedContextResolver(
                    self._session,
                    claims=claims,
                    organization_id=organization.organization_id,
                    facts=facts.context,
                )
                principal = await resolver.resolve_principal()
                scope = await resolver.resolve_scope(principal)
                permission = await SQLAlchemyRuntimeApiPermissionFactResolver(
                    self._session
                ).resolve_permission_fact(
                    principal,
                    scope,
                    required_runtime_api_permission(RuntimeApiOperation.SUBMIT_INVOCATION),
                )
                digest = build_runtime_api_submission_digest(request, facts=facts)
                command = await self._binder_factory(self._session).bind_submission(
                    principal,
                    scope,
                    permission,
                    request,
                    facts,
                    digest,
                )
                command = validate_runtime_api_submission_binding(
                    command,
                    request=request,
                    facts=facts,
                    principal=principal,
                    scope=scope,
                    permission=permission,
                    command_digest=digest,
                    required_audience=self._required_audience,
                )
                local_operation = self._local_operation_factory(self._session)

                async def mutation():
                    return await local_operation.submit_invocation(command)

                result = await SQLAlchemyRuntimeApiIdempotencyTransaction(self._session).commit(
                    command.identity,
                    RuntimeApiIdempotencyCommitFacts(
                        receipt_id=facts.receipt_id,
                        committed_at=facts.committed_at,
                    ),
                    mutation,
                )
                return RuntimeApiSubmissionResult(
                    idempotency=validate_runtime_api_commit_result(result)
                )
        except (
            RuntimeApiContractConflict,
            RuntimeTenantBindingError,
            RuntimePermissionFactError,
            RuntimeApiIdempotencyPersistenceError,
        ):
            raise
        except Exception:
            raise RuntimeApiFacadeError("runtime facade operation failed") from None

    async def get_invocation(
        self,
        request: RuntimeApiInvocationQueryInput,
        claims: VerifiedAccessTokenClaims,
        organization: RuntimeApiOrganizationSelector,
        facts: RuntimeApiInvocationQueryFacts,
    ) -> RuntimeApiStatusProjection:
        self._require_transaction_ownership()
        try:
            async with self._session.begin():
                resolver = SQLAlchemyRuntimeApiTrustedContextResolver(
                    self._session,
                    claims=claims,
                    organization_id=organization.organization_id,
                    facts=facts.context,
                )
                principal = await resolver.resolve_principal()
                scope = await resolver.resolve_scope(principal)
                permission = await SQLAlchemyRuntimeApiPermissionFactResolver(
                    self._session
                ).resolve_permission_fact(
                    principal,
                    scope,
                    required_runtime_api_permission(RuntimeApiOperation.GET_INVOCATION),
                )
                query = await self._binder_factory(self._session).bind_query(
                    principal,
                    scope,
                    permission,
                    request,
                    facts,
                )
                query = validate_runtime_api_invocation_query_binding(
                    query,
                    request=request,
                    facts=facts,
                    principal=principal,
                    scope=scope,
                    permission=permission,
                    required_audience=self._required_audience,
                )
                projection = await self._local_operation_factory(self._session).get_invocation(
                    query
                )
                return validate_runtime_api_projection_binding(
                    projection,
                    request=request,
                    facts=facts,
                )
        except (
            RuntimeApiContractConflict,
            RuntimeTenantBindingError,
            RuntimePermissionFactError,
            RuntimeApiIdempotencyPersistenceError,
        ):
            raise
        except Exception:
            raise RuntimeApiFacadeError("runtime facade operation failed") from None

    async def request_reconciliation(
        self,
        request: RuntimeApiReconciliationInput,
        claims: VerifiedAccessTokenClaims,
        organization: RuntimeApiOrganizationSelector,
        facts: RuntimeApiReconciliationFacts,
    ) -> RuntimeApiReconciliationResult:
        self._require_transaction_ownership()
        try:
            async with self._session.begin():
                resolver = SQLAlchemyRuntimeApiTrustedContextResolver(
                    self._session,
                    claims=claims,
                    organization_id=organization.organization_id,
                    facts=facts.context,
                )
                principal = await resolver.resolve_principal()
                scope = await resolver.resolve_scope(principal)
                permission = await SQLAlchemyRuntimeApiPermissionFactResolver(
                    self._session
                ).resolve_permission_fact(
                    principal,
                    scope,
                    required_runtime_api_permission(RuntimeApiOperation.REQUEST_RECONCILIATION),
                )
                digest = build_runtime_api_reconciliation_digest(request, facts=facts)
                command = await self._binder_factory(self._session).bind_reconciliation(
                    principal,
                    scope,
                    permission,
                    request,
                    facts,
                    digest,
                )
                command = validate_runtime_api_reconciliation_binding(
                    command,
                    request=request,
                    facts=facts,
                    principal=principal,
                    scope=scope,
                    permission=permission,
                    command_digest=digest,
                    required_audience=self._required_audience,
                )
                local_operation = self._local_operation_factory(self._session)

                async def mutation():
                    return await local_operation.request_reconciliation(command)

                result = await SQLAlchemyRuntimeApiIdempotencyTransaction(self._session).commit(
                    command.identity,
                    RuntimeApiIdempotencyCommitFacts(
                        receipt_id=facts.receipt_id,
                        committed_at=facts.committed_at,
                    ),
                    mutation,
                )
                return RuntimeApiReconciliationResult(
                    idempotency=validate_runtime_api_commit_result(result)
                )
        except (
            RuntimeApiContractConflict,
            RuntimeTenantBindingError,
            RuntimePermissionFactError,
            RuntimeApiIdempotencyPersistenceError,
        ):
            raise
        except Exception:
            raise RuntimeApiFacadeError("runtime facade operation failed") from None


__all__ = (
    "RuntimeApiFacadeError",
    "RuntimeApiFacadeTransactionRequiredError",
    "RuntimeApiLocalOperationPortFactory",
    "RuntimeApiOrchestrationFactBinderFactory",
    "SQLAlchemyRuntimeApiApplicationFacade",
)
