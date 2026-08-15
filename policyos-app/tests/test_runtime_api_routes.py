from datetime import UTC, datetime, timedelta
from types import SimpleNamespace
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient

from app.api.deps import get_runtime_verified_claims
from app.core.auth_claims import VerifiedAccessTokenClaims
from app.db.session import get_db
from app.main import create_app
from app.services import runtime_api_production as production_module
from app.services.runtime_api_contracts import RuntimeApiPublicStatus, RuntimeApiStatusProjection
from app.services.runtime_api_idempotency import RuntimeApiIdempotencyPersistenceError
from app.services.runtime_api_production import RuntimeApiRateLimited
from app.services.runtime_api_protocols import RuntimeApiProductionDependencyBundle
from app.services.runtime_permission_facts import RuntimePermissionFactError
from app.services.runtime_tenant_binding import RuntimeTenantBindingError


async def _claims():
    now = datetime.now(UTC)
    return VerifiedAccessTokenClaims(
        subject=str(uuid4()),
        jti_reference="jti:runtime-route",
        verified_issuer="policyos-tests",
        verified_audiences=("policyos-runtime",),
        issued_at=now,
        expires_at=now + timedelta(minutes=5),
    )


async def _db():
    yield None


def _client() -> TestClient:
    application = create_app()
    application.dependency_overrides[get_runtime_verified_claims] = _claims
    application.dependency_overrides[get_db] = _db
    return TestClient(application)


class _Scope:
    def __init__(self, events):
        self.events = events

    async def __aenter__(self):
        self.events.append("enter")
        return object()

    async def __aexit__(self, exc_type, exc, traceback):
        self.events.append("exit")
        return False


class _Entry:
    def __init__(self, mode="success"):
        self.mode = mode
        self.calls = []

    async def _result(self, operation, request):
        self.calls.append(operation)
        if self.mode == "rate":
            raise RuntimeApiRateLimited(17)
        if self.mode == "permission":
            raise RuntimePermissionFactError("secret permission detail")
        if self.mode == "scope":
            raise RuntimeTenantBindingError("secret scope detail")
        if self.mode == "conflict":
            raise RuntimeApiIdempotencyPersistenceError("secret replay detail")
        if self.mode == "internal":
            raise RuntimeError("secret internal detail")
        projection = RuntimeApiStatusProjection(
            invocation_reference=request.invocation_reference
            if hasattr(request, "invocation_reference")
            else "invocation:created",
            status=RuntimeApiPublicStatus.ACCEPTED,
            status_reference="state:digest",
            correlation_reference="correlation:route",
            observed_at=datetime.now(UTC),
        )
        if operation == "query":
            return projection
        return SimpleNamespace(
            idempotency=SimpleNamespace(safe_result=SimpleNamespace(projection=projection))
        )

    async def submit_invocation(self, request, claims, organization):
        return await self._result("submit", request)

    async def get_invocation(self, request, claims, organization):
        return await self._result("query", request)

    async def request_reconciliation(self, request, claims, organization):
        return await self._result("reconcile", request)


def _composed_client(monkeypatch, entry):
    events = []
    bundle = RuntimeApiProductionDependencyBundle(
        request_capability_scope_factory=lambda signal: _Scope(events)
    )
    monkeypatch.setattr(production_module, "build_runtime_api_entry", lambda *a, **k: entry)
    import app.api.routes.runtime as route_module

    monkeypatch.setattr(route_module, "build_runtime_api_entry", lambda *a, **k: entry)
    application = create_app(bundle)
    application.dependency_overrides[get_runtime_verified_claims] = _claims
    application.dependency_overrides[get_db] = _db
    return TestClient(application), events


def test_runtime_routes_are_exact_and_missing_bundle_is_generic_503():
    organization_id = str(uuid4())
    with _client() as client:
        response = client.post(
            "/api/v1/runtime/invocations",
            params={"organization_id": organization_id},
            headers={"Idempotency-Key": "idem-route-1"},
            json={
                "action_reference": "action:one",
                "command_reference": "command:one",
                "input_reference": None,
                "classification": "internal",
            },
        )
    assert response.status_code == 503, response.text
    assert response.json()["detail"] == {
        "code": "runtime_dependency_unavailable",
        "message": "Runtime operation unavailable",
        "retryable": True,
        "correlation_reference": None,
    }


def test_runtime_mutation_requires_header_only_idempotency_key():
    with _client() as client:
        response = client.post(
            "/api/v1/runtime/invocations",
            params={"organization_id": str(uuid4())},
            json={
                "action_reference": "action:one",
                "command_reference": "command:one",
                "classification": "internal",
            },
        )
    assert response.status_code == 422


def test_runtime_organization_selector_rejects_noncanonical_or_duplicate_values():
    organization_id = str(uuid4())
    with _client() as client:
        uppercase = client.get(
            "/api/v1/runtime/invocations/invocation:one",
            params={"organization_id": organization_id.upper()},
        )
        duplicate = client.get(
            f"/api/v1/runtime/invocations/invocation:one"
            f"?organization_id={organization_id}&organization_id={organization_id}"
        )
    assert uppercase.status_code == 422
    assert duplicate.status_code == 422


def test_runtime_routes_use_dedicated_verified_claims_dependency():
    application = create_app()
    with TestClient(application) as client:
        response = client.get(
            "/api/v1/runtime/invocations/invocation:one",
            params={"organization_id": str(uuid4())},
        )
    assert response.status_code == 401


def test_runtime_routes_accept_exact_selector_and_header_and_cleanup(monkeypatch):
    entry = _Entry()
    client, events = _composed_client(monkeypatch, entry)
    organization_id = str(uuid4())
    with client:
        submit = client.post(
            "/api/v1/runtime/invocations",
            params={"organization_id": organization_id},
            headers={"Idempotency-Key": "idem-route-success"},
            json={
                "action_reference": "action:one",
                "command_reference": "command:one",
                "classification": "internal",
            },
        )
        query = client.get(
            "/api/v1/runtime/invocations/invocation:one",
            params={"organization_id": organization_id},
        )
        reconciliation = client.post(
            "/api/v1/runtime/reconciliations",
            params={"organization_id": organization_id},
            headers={"Idempotency-Key": "idem-route-reconcile"},
            json={
                "invocation_reference": "invocation:one",
                "reconciliation_reference": "reconciliation:one",
            },
        )
    assert [submit.status_code, query.status_code, reconciliation.status_code] == [200, 200, 200]
    assert entry.calls == ["submit", "query", "reconcile"]
    assert events == ["enter", "exit", "enter", "exit", "enter", "exit"]


def test_runtime_rate_denial_preserves_exact_retry_after(monkeypatch):
    client, events = _composed_client(monkeypatch, _Entry("rate"))
    with client:
        response = client.get(
            "/api/v1/runtime/invocations/invocation:one",
            params={"organization_id": str(uuid4())},
        )
    assert response.status_code == 429
    assert response.headers["Retry-After"] == "17"
    assert response.json()["detail"]["code"] == "runtime_rate_limited"
    assert events == ["enter", "exit"]


@pytest.mark.parametrize(
    ("mode", "expected_status", "expected_code"),
    (
        ("permission", 403, "runtime_permission_denied"),
        ("scope", 404, "runtime_scope_not_found"),
        ("conflict", 409, "runtime_idempotency_conflict"),
        ("internal", 500, "runtime_internal_failure"),
    ),
)
def test_runtime_error_mapping_is_bounded_and_non_disclosing(
    monkeypatch, mode, expected_status, expected_code
):
    client, events = _composed_client(monkeypatch, _Entry(mode))
    with client:
        response = client.get(
            "/api/v1/runtime/invocations/invocation:one",
            params={"organization_id": str(uuid4())},
        )
    assert response.status_code == expected_status
    assert response.json()["detail"]["code"] == expected_code
    assert "secret" not in response.text
    assert events == ["enter", "exit"]
