import inspect

import app.orchestration as orchestration


def test_orchestration_public_surface_has_no_wildcard_or_leaked_base_error():
    source = inspect.getsource(orchestration)
    assert " import *" not in source
    assert "ExecutionDomainError" not in orchestration.__dict__
    for name in (
        "ExecutionTranslationError",
        "AssignmentRuntimeError",
        "AssignmentDispatchError",
        "WorkProductCollectionError",
        "SecretaryIntegrationError",
        "ApprovalError",
    ):
        assert name in orchestration.__all__
