"""Test-only support for CP10 PostgreSQL Worker acceptance."""

import os
from collections.abc import AsyncIterator
from types import SimpleNamespace

import pytest
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from tests.runtime_delivery_persistence_test_support import (
    runtime_delivery_session_factory,
)


async def worker_acceptance_session_factory() -> AsyncIterator[async_sessionmaker[AsyncSession]]:
    database_url = os.getenv("POLICYOS_TEST_DATABASE_URL")
    if not database_url:
        pytest.skip("POLICYOS_TEST_DATABASE_URL is required for CP10 Worker acceptance")
    async with runtime_delivery_session_factory(database_url) as factory:
        yield factory


def zero_budget_shutdown(observed_at):
    return SimpleNamespace(
        observed_clock_reading=SimpleNamespace(observed_at=observed_at),
        drain_deadline=observed_at,
    )


__all__ = ("worker_acceptance_session_factory", "zero_budget_shutdown")
