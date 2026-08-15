"""Thin FastAPI transport adapters for the trusted Runtime application entry."""

from __future__ import annotations

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Header, HTTPException, Query, Request, status
from pydantic import ValidationError
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_runtime_verified_claims
from app.core.auth_claims import VerifiedAccessTokenClaims
from app.db.session import get_db
from app.schemas.runtime_api import (
    RuntimeInvocationSubmitRequest,
    RuntimePublicErrorEnvelope,
    RuntimeReconciliationRequest,
    RuntimeReconciliationResponse,
    RuntimeStatusResponse,
)
from app.services.runtime_api_contracts import (
    RuntimeApiErrorCode,
    RuntimeApiInvocationQueryInput,
    RuntimeApiOrganizationSelector,
    RuntimeApiReconciliationInput,
    RuntimeApiSubmissionInput,
)
from app.services.runtime_api_idempotency import RuntimeApiIdempotencyPersistenceError
from app.services.runtime_api_production import (
    RuntimeApiDependencyUnavailable,
    RuntimeApiRateLimited,
    RuntimeApiRequestScopeCoordinator,
    build_runtime_api_entry,
)
from app.services.runtime_api_protocols import (
    RuntimeApiDisconnectSignal,
    RuntimeApiProductionDependencyBundle,
)
from app.services.runtime_permission_facts import RuntimePermissionFactError
from app.services.runtime_tenant_binding import RuntimeTenantBindingError


class FastApiRuntimeDisconnectSignal:
    """Confine Starlette request disconnect observation to app.api."""

    def __init__(self, request: Request) -> None:
        self._request = request

    async def is_disconnected(self) -> bool:
        return bool(await self._request.is_disconnected())


def _error(
    status_code: int,
    code: RuntimeApiErrorCode,
    message: str,
    *,
    retryable: bool = False,
    headers: dict[str, str] | None = None,
) -> HTTPException:
    envelope = RuntimePublicErrorEnvelope(
        code=code,
        message=message,
        retryable=retryable,
        correlation_reference=None,
    )
    return HTTPException(
        status_code=status_code,
        detail=envelope.model_dump(mode="json"),
        headers=headers,
    )


def _organization(request: Request, raw: str) -> RuntimeApiOrganizationSelector:
    if len(request.query_params.getlist("organization_id")) != 1:
        raise _error(422, RuntimeApiErrorCode.INVALID_REQUEST, "Invalid request")
    try:
        value = UUID(raw)
    except ValueError:
        raise _error(422, RuntimeApiErrorCode.INVALID_REQUEST, "Invalid request") from None
    if value.int == 0 or str(value) != raw:
        raise _error(422, RuntimeApiErrorCode.INVALID_REQUEST, "Invalid request")
    return RuntimeApiOrganizationSelector(organization_id=value)


def _idempotency(request: Request, value: str | None) -> str:
    values = request.headers.getlist("idempotency-key")
    if value is None or len(values) != 1 or not value or value != value.strip():
        raise _error(422, RuntimeApiErrorCode.INVALID_REQUEST, "Invalid request")
    return value


async def _submit_body(request: Request) -> RuntimeInvocationSubmitRequest:
    try:
        return RuntimeInvocationSubmitRequest.model_validate_json(await request.body())
    except ValidationError:
        raise _error(422, RuntimeApiErrorCode.INVALID_REQUEST, "Invalid request") from None


async def _reconciliation_body(request: Request) -> RuntimeReconciliationRequest:
    try:
        return RuntimeReconciliationRequest.model_validate_json(await request.body())
    except ValidationError:
        raise _error(422, RuntimeApiErrorCode.INVALID_REQUEST, "Invalid request") from None


def create_runtime_router(
    bundle: RuntimeApiProductionDependencyBundle | None,
    *,
    required_audience: str,
) -> APIRouter:
    router = APIRouter(prefix="/runtime", tags=["runtime"])

    async def execute(request, claims, organization, db, transport, operation):
        if bundle is None:
            raise _error(
                status.HTTP_503_SERVICE_UNAVAILABLE,
                RuntimeApiErrorCode.DEPENDENCY_UNAVAILABLE,
                "Runtime operation unavailable",
                retryable=True,
            )
        signal: RuntimeApiDisconnectSignal = FastApiRuntimeDisconnectSignal(transport)
        try:
            async with RuntimeApiRequestScopeCoordinator(bundle, signal) as dependencies:
                entry = build_runtime_api_entry(
                    dependencies,
                    session=db,
                    required_audience=required_audience,
                )
                return await operation(entry, request, claims, organization)
        except RuntimeApiRateLimited as exc:
            raise _error(
                429,
                RuntimeApiErrorCode.RATE_LIMITED,
                "Rate limit exceeded",
                retryable=True,
                headers={"Retry-After": str(exc.retry_after_seconds)},
            ) from None
        except RuntimeApiDependencyUnavailable:
            raise _error(
                503,
                RuntimeApiErrorCode.DEPENDENCY_UNAVAILABLE,
                "Runtime operation unavailable",
                retryable=True,
            ) from None
        except RuntimePermissionFactError:
            raise _error(
                403,
                RuntimeApiErrorCode.PERMISSION_DENIED,
                "Permission denied",
            ) from None
        except RuntimeTenantBindingError:
            raise _error(
                404,
                RuntimeApiErrorCode.SCOPE_NOT_FOUND,
                "Runtime scope not found",
            ) from None
        except RuntimeApiIdempotencyPersistenceError:
            raise _error(
                409,
                RuntimeApiErrorCode.IDEMPOTENCY_CONFLICT,
                "Runtime conflict",
            ) from None
        except HTTPException:
            raise
        except ValueError:
            raise _error(409, RuntimeApiErrorCode.STATE_CONFLICT, "Runtime conflict") from None
        except Exception:
            raise _error(
                500,
                RuntimeApiErrorCode.INTERNAL_FAILURE,
                "Runtime operation failed",
            ) from None

    @router.post("/invocations", response_model=RuntimeStatusResponse)
    async def submit_invocation(
        body: Annotated[RuntimeInvocationSubmitRequest, Depends(_submit_body)],
        transport: Request,
        claims: Annotated[VerifiedAccessTokenClaims, Depends(get_runtime_verified_claims)],
        organization_id: Annotated[str, Query(min_length=36, max_length=36)],
        db: Annotated[AsyncSession, Depends(get_db)],
        idempotency_key: Annotated[str | None, Header(alias="Idempotency-Key")] = None,
    ) -> RuntimeStatusResponse:
        organization = _organization(transport, organization_id)
        request = RuntimeApiSubmissionInput(
            **body.model_dump(),
            idempotency_key=_idempotency(transport, idempotency_key),
        )
        result = await execute(
            request,
            claims,
            organization,
            db,
            transport,
            lambda entry, req, token, org: entry.submit_invocation(req, token, org),
        )
        projection = result.idempotency.safe_result.projection
        return RuntimeStatusResponse(**projection.model_dump(exclude={"observed_at"}))

    @router.get("/invocations/{invocation_reference}", response_model=RuntimeStatusResponse)
    async def get_invocation(
        invocation_reference: str,
        transport: Request,
        claims: Annotated[VerifiedAccessTokenClaims, Depends(get_runtime_verified_claims)],
        organization_id: Annotated[str, Query(min_length=36, max_length=36)],
        db: Annotated[AsyncSession, Depends(get_db)],
    ) -> RuntimeStatusResponse:
        organization = _organization(transport, organization_id)
        request = RuntimeApiInvocationQueryInput(invocation_reference=invocation_reference)
        projection = await execute(
            request,
            claims,
            organization,
            db,
            transport,
            lambda entry, req, token, org: entry.get_invocation(req, token, org),
        )
        return RuntimeStatusResponse(**projection.model_dump(exclude={"observed_at"}))

    @router.post("/reconciliations", response_model=RuntimeReconciliationResponse)
    async def request_reconciliation(
        body: Annotated[RuntimeReconciliationRequest, Depends(_reconciliation_body)],
        transport: Request,
        claims: Annotated[VerifiedAccessTokenClaims, Depends(get_runtime_verified_claims)],
        organization_id: Annotated[str, Query(min_length=36, max_length=36)],
        db: Annotated[AsyncSession, Depends(get_db)],
        idempotency_key: Annotated[str | None, Header(alias="Idempotency-Key")] = None,
    ) -> RuntimeReconciliationResponse:
        organization = _organization(transport, organization_id)
        request = RuntimeApiReconciliationInput(
            **body.model_dump(),
            idempotency_key=_idempotency(transport, idempotency_key),
        )
        result = await execute(
            request,
            claims,
            organization,
            db,
            transport,
            lambda entry, req, token, org: entry.request_reconciliation(req, token, org),
        )
        projection = result.idempotency.safe_result.projection
        return RuntimeReconciliationResponse(
            invocation_reference=projection.invocation_reference,
            status=projection.status,
            reconciliation_reference=request.reconciliation_reference,
            correlation_reference=projection.correlation_reference,
        )

    return router


__all__ = ("FastApiRuntimeDisconnectSignal", "create_runtime_router")
