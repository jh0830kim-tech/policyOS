from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI

from app.api.routes.health import router as health_router
from app.api.routes.policy_candidates import router as policy_candidates_router
from app.core.config import get_settings

settings = get_settings()


@asynccontextmanager
async def lifespan(_: FastAPI) -> AsyncIterator[None]:
    # Schema lifecycle is managed exclusively by Alembic.
    yield


app = FastAPI(
    title=settings.app_name,
    version="0.2.0",
    description="PolicyOS MVP API",
    lifespan=lifespan,
)
app.include_router(health_router)
app.include_router(policy_candidates_router, prefix="/api/v1")
