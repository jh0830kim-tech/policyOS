"""Test-only support for the CP8 PostgreSQL delivery acceptance gate."""

import os
from collections.abc import AsyncIterator

import pytest
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.runtime.ports import (
    RuntimeEffectDeliveryInvocation,
    RuntimeEffectReconciliationRequest,
)
from tests.runtime_delivery_persistence_test_support import runtime_delivery_session_factory


async def acceptance_session_factory() -> AsyncIterator[async_sessionmaker[AsyncSession]]:
    database_url = os.getenv("POLICYOS_TEST_DATABASE_URL")
    if not database_url:
        pytest.skip("POLICYOS_TEST_DATABASE_URL is required for CP8 acceptance")
    async with runtime_delivery_session_factory(database_url) as factory:
        yield factory


class DeterministicEffectDelivery:
    def __init__(self, invocation, result) -> None:
        self.adapter_reference = invocation.envelope.adapter_reference
        self.adapter_contract_version = invocation.envelope.adapter_contract_version
        self.adapter_family = invocation.envelope.adapter_family
        self.expected_invocation = invocation
        self.supplied_result = result
        self.calls: list[RuntimeEffectDeliveryInvocation] = []

    async def deliver(self, invocation):
        if invocation != self.expected_invocation:
            raise AssertionError("delivery invocation differs")
        self.calls.append(invocation)
        return self.supplied_result


class DeterministicEffectObservation:
    def __init__(self, request, observation) -> None:
        self.expected_request = request
        self.supplied_observation = observation
        self.calls: list[RuntimeEffectReconciliationRequest] = []

    async def observe(self, request):
        if request != self.expected_request:
            raise AssertionError("reconciliation request differs")
        self.calls.append(request)
        return self.supplied_observation


__all__ = (
    "DeterministicEffectDelivery",
    "DeterministicEffectObservation",
    "acceptance_session_factory",
)
