"""Focused construction and architecture tests for the production Worker."""

import inspect
from pathlib import Path

from app.services.runtime_worker import RuntimeWorkerService
from app.services.runtime_worker_production import create_runtime_worker_application_service
from app.services.runtime_worker_protocols import RuntimeWorkerApplicationService


def test_production_factory_returns_the_public_application_service():
    assert callable(create_runtime_worker_application_service)
    assert inspect.signature(RuntimeWorkerService.run) == inspect.signature(
        RuntimeWorkerApplicationService.run
    )
    assert inspect.signature(create_runtime_worker_application_service).return_annotation is (
        RuntimeWorkerApplicationService
    )


def test_worker_translates_only_the_closed_operational_marker():
    source = (Path(__file__).parents[1] / "app/services/runtime_worker.py").read_text(
        encoding="utf-8"
    )
    assert "except RuntimeWorkerOperationalCapabilityFailure:" in source
    assert "except Exception" not in source
    assert "datetime.now" not in source
    assert "uuid4" not in source
    assert "commit(" not in source
    assert "rollback(" not in source
    assert "RuntimeWorkerOperationalFailureStage.DUE_SELECTION" in source


def test_worker_production_exports_are_explicit_immutable_tuples():
    import app.services.runtime_worker as worker
    import app.services.runtime_worker_production as production

    assert worker.__all__ == ("RuntimeWorkerService",)
    assert production.__all__ == ("create_runtime_worker_application_service",)
