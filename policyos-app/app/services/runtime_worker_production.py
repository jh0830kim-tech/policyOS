"""Explicit production construction for the CP10 Runtime Worker."""

from app.services.runtime_worker import RuntimeWorkerService
from app.services.runtime_worker_protocols import (
    RuntimeWorkerApplicationService,
    RuntimeWorkerProductionDependencyBundle,
)


def create_runtime_worker_application_service(
    dependencies: RuntimeWorkerProductionDependencyBundle,
) -> RuntimeWorkerApplicationService:
    """Construct one Worker service from one validated immutable bundle."""

    return RuntimeWorkerService(dependencies=dependencies)


__all__ = ("create_runtime_worker_application_service",)
