from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.responses import JSONResponse

from app.ai.model_gateway import ModelConfigurationError
from app.ai.production import (
    AIOfficeProductionDependencyBundle,
    bind_ai_office_production,
)
from app.api.routes.ai_tasks import router as ai_tasks_router
from app.api.routes.artifacts import create_artifacts_router
from app.api.routes.auth import router as auth_router
from app.api.routes.connectors import router as connectors_router
from app.api.routes.health import router as health_router
from app.api.routes.policy_candidates import router as policy_candidates_router
from app.api.routes.providers import router as providers_router
from app.api.routes.runtime import create_runtime_router
from app.core.config import get_settings
from app.services.runtime_api_protocols import RuntimeApiProductionDependencyBundle
from app.version import get_version


@asynccontextmanager
async def lifespan(_: FastAPI) -> AsyncIterator[None]:
    # Schema lifecycle is managed exclusively by Alembic.
    yield


def create_app(
    runtime_dependencies: RuntimeApiProductionDependencyBundle | None = None,
    *,
    ai_office_dependencies: AIOfficeProductionDependencyBundle | None = None,
) -> FastAPI:
    if runtime_dependencies is not None and not isinstance(
        runtime_dependencies, RuntimeApiProductionDependencyBundle
    ):
        raise TypeError("Runtime production dependency bundle differs")
    settings = get_settings()
    ai_office_production = bind_ai_office_production(settings, ai_office_dependencies)
    application = FastAPI(
        title=settings.app_name,
        version=get_version(),
        description="PolicyOS MVP API",
        lifespan=lifespan,
    )

    @application.exception_handler(ModelConfigurationError)
    async def configuration_error(_request, _error):
        # Scope acquisition errors must not expose deployment/accessor internals.
        return JSONResponse(
            status_code=503,
            content={
                "detail": {
                    "code": "configuration_error",
                    "message": "AI provider is not configured",
                }
            },
        )

    application.include_router(health_router)
    application.include_router(auth_router, prefix="/api/v1")
    application.include_router(connectors_router, prefix="/api/v1")
    application.include_router(create_artifacts_router(ai_office_production), prefix="/api/v1")
    application.include_router(ai_tasks_router, prefix="/api/v1")
    application.include_router(policy_candidates_router, prefix="/api/v1")
    application.include_router(providers_router, prefix="/api/v1")
    application.include_router(
        create_runtime_router(
            runtime_dependencies,
            required_audience=settings.runtime_api_required_audience,
        ),
        prefix="/api/v1",
    )
    return application


__all__ = ("create_app", "lifespan")
