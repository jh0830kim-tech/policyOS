"""Explicit production construction for the CP10 Runtime Worker."""

from app.services.runtime_worker import RuntimeWorkerService
from app.services.runtime_worker_protocols import (
    RuntimeConnectorProductionDependencyBundle,
    RuntimeWorkerApplicationService,
    RuntimeWorkerProductionDependencyBundle,
)


def bind_runtime_connector_dependencies(
    worker: RuntimeWorkerProductionDependencyBundle,
    connector: RuntimeConnectorProductionDependencyBundle,
) -> RuntimeWorkerProductionDependencyBundle:
    """Bind the exact connector factories into a fresh immutable Worker bundle."""

    return RuntimeWorkerProductionDependencyBundle(
        poll_cycle_request_preparation_factory=worker.poll_cycle_request_preparation_factory,
        poll_iteration_request_preparation_factory=(
            worker.poll_iteration_request_preparation_factory
        ),
        prepared_delivery_request_preparation_factory=(
            worker.prepared_delivery_request_preparation_factory
        ),
        due_selection_factory=worker.due_selection_factory,
        prepared_delivery_factory=worker.prepared_delivery_factory,
        claim_factory=worker.claim_factory,
        lifecycle_append_factory=worker.lifecycle_append_factory,
        delivery_factory=connector.delivery_factory,
        cancellation_factory=worker.cancellation_factory,
        credential_factory=connector.credential_broker_factory,
        shutdown_observation_request_preparation_factory=(
            worker.shutdown_observation_request_preparation_factory
        ),
        shutdown_observation_factory=worker.shutdown_observation_factory,
        interruptible_wait_factory=worker.interruptible_wait_factory,
        poll_iteration_result_production_factory=(worker.poll_iteration_result_production_factory),
        poll_cycle_result_production_factory=worker.poll_cycle_result_production_factory,
        pre_invocation_revalidation_factory=connector.pre_invocation_revalidation_factory,
    )


def create_runtime_worker_application_service(
    dependencies: RuntimeWorkerProductionDependencyBundle,
) -> RuntimeWorkerApplicationService:
    """Construct one Worker service from one validated immutable bundle."""

    return RuntimeWorkerService(dependencies=dependencies)


__all__ = (
    "bind_runtime_connector_dependencies",
    "create_runtime_worker_application_service",
)
