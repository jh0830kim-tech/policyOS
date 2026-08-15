"""Combined PostgreSQL 16 and HTTP acceptance for the CP9 Runtime API."""

import os
import subprocess
import sys
from pathlib import Path

import httpx
import pytest
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from app.api.deps import get_runtime_verified_claims
from app.db.session import get_db
from app.main import create_app
from app.models.runtime_api_idempotency import RuntimeApiIdempotencyReceiptRecord
from app.models.runtime_rate_admission import (
    RuntimeRateAdmissionDecisionRecord,
    RuntimeRateWindowCounterRecord,
)
from app.models.runtime_registry import RuntimeReconciliationRequestRecord
from app.services.runtime_api_contracts import RuntimeApiOrganizationSelector
from tests.runtime_api_acceptance_test_support import (
    AUDIENCE,
    ORGANIZATION,
    AcceptanceFactories,
    reconciliation_case,
    seed_persistence,
)
from tests.test_runtime_api_facade_persistence import seed


@pytest.fixture(scope="module")
def database_url() -> str:
    value = os.getenv("POLICYOS_TEST_DATABASE_URL")
    if value is None:
        pytest.skip("POLICYOS_TEST_DATABASE_URL is required for CP9 acceptance")
    return value


@pytest.fixture(scope="module", autouse=True)
def migrated_database(database_url: str) -> None:
    environment = os.environ.copy()
    environment["DATABASE_URL"] = database_url
    subprocess.run(
        [sys.executable, "-m", "alembic", "upgrade", "head"],
        check=True,
        cwd=Path(__file__).resolve().parents[1],
        env=environment,
    )


@pytest.mark.asyncio
async def test_runtime_reconciliation_http_postgresql_replay_and_scope_cleanup(database_url):
    engine = create_async_engine(database_url)
    session_factory = async_sessionmaker(engine, expire_on_commit=False)
    request, facts, context, callback = reconciliation_case("acceptance-reconciliation-key")
    await seed_persistence(session_factory, facts, context)
    _, _, _, claims = await seed(session_factory)
    claims = claims.model_copy(update={"subject": str(context.provenance.principal_id)})
    events: list[str] = []
    bundle = AcceptanceFactories(
        session_factory=session_factory,
        context=context,
        callback=callback,
        events=events,
    ).bundle()
    application = create_app(bundle)

    async def verified_claims():
        return claims

    async def database_session():
        async with session_factory() as session:
            yield session

    application.dependency_overrides[get_runtime_verified_claims] = verified_claims
    application.dependency_overrides[get_db] = database_session
    transport = httpx.ASGITransport(app=application)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        payload = {
            "invocation_reference": request.invocation_reference,
            "reconciliation_reference": request.reconciliation_reference,
        }
        headers = {"Idempotency-Key": request.idempotency_key}
        params = {"organization_id": str(ORGANIZATION)}
        first = await client.post(
            "/api/v1/runtime/reconciliations",
            params=params,
            headers=headers,
            json=payload,
        )
        replay = await client.post(
            "/api/v1/runtime/reconciliations",
            params=params,
            headers=headers,
            json=payload,
        )

    assert first.status_code == 200, first.text
    assert replay.status_code == 200, replay.text
    assert first.json() == replay.json()
    assert callback.calls == 1
    expected_lifecycle = [
        "enter:domain",
        "enter:clock",
        "enter:rate",
        "enter:deadline",
        "enter:disconnect",
        "enter:upstream",
        "exit:upstream",
        "exit:disconnect",
        "exit:deadline",
        "exit:rate",
        "exit:clock",
        "exit:domain",
    ]
    assert events == expected_lifecycle * 2

    async with session_factory() as session:
        assert (
            await session.scalar(select(func.count()).select_from(RuntimeRateWindowCounterRecord))
            == 1
        )
        assert (
            await session.scalar(
                select(func.count()).select_from(RuntimeRateAdmissionDecisionRecord)
            )
            == 1
        )
        assert (
            await session.scalar(
                select(func.count())
                .select_from(RuntimeApiIdempotencyReceiptRecord)
                .where(RuntimeApiIdempotencyReceiptRecord.receipt_id == facts.receipt_id)
            )
            == 1
        )
        assert (
            await session.scalar(
                select(func.count())
                .select_from(RuntimeReconciliationRequestRecord)
                .where(
                    RuntimeReconciliationRequestRecord.runtime_effect_reconciliation_request_id
                    == (
                        facts.integration.stage.reconciliation_request.runtime_effect_reconciliation_request_id
                    )
                )
            )
            == 1
        )
    await engine.dispose()


def test_acceptance_keeps_canonical_organization_selector_contract():
    selector = RuntimeApiOrganizationSelector(organization_id=ORGANIZATION)
    assert str(selector.organization_id) == str(ORGANIZATION)
    assert AUDIENCE == "policyos-api-test"
