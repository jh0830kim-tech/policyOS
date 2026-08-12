"""Focused CP9 concrete Runtime API application-integration tests."""

import runpy
from pathlib import Path

import pytest

from app.runtime.ports import (
    RuntimeApiExecutionStateRevisionReadResult,
    RuntimeApiLocalWriteSetStageResult,
)
from app.runtime.state import RuntimeExecutionState
from app.services.runtime_api_contracts import (
    RuntimeApiDomainOperationResult,
    RuntimeApiInvocationQuery,
    RuntimeApiPermission,
    RuntimeApiSubmissionFacts,
    RuntimeApiSubmissionInput,
)
from app.services.runtime_api_integration import (
    OneShotRuntimeApiIntegrationFactsProvider,
    RuntimeApiActiveTransactionLocalOperation,
    RuntimeApiExactOrchestrationFactBinder,
    RuntimeApiIntegrationError,
)
from app.services.runtime_api_validation import build_runtime_api_submission_digest

_CONTRACTS = runpy.run_path(str(Path(__file__).with_name("test_runtime_api_contracts.py")))
_BINDING = runpy.run_path(str(Path(__file__).with_name("test_runtime_api_binding_contracts.py")))
NOW = _BINDING["NOW"]
command = _CONTRACTS["command"]
context_facts = _CONTRACTS["context_facts"]
permission = _CONTRACTS["permission"]
principal = _CONTRACTS["principal"]
safe_result = _CONTRACTS["safe_result"]
scope = _CONTRACTS["scope"]
query_integration_facts = _BINDING["query_integration_facts"]
submission_integration_facts = _BINDING["submission_integration_facts"]


class DomainCallback:
    def __init__(self, result) -> None:
        self.result = result
        self.calls = 0

    async def __call__(self, _command):
        self.calls += 1
        return self.result


class Capability:
    def __init__(self, events: list[str], *, resolved=None) -> None:
        self.events = events
        self.resolved = resolved

    async def read_exact(self, _context, expected):
        self.events.append("binding.read")
        return expected if self.resolved is None else self.resolved

    async def stage_local_write_set(self, _context, stage):
        self.events.append("local.stage")
        return RuntimeApiLocalWriteSetStageResult(
            local_write_set_id=stage.local_write_set_id,
            transport_receipt_id=stage.transport_receipt_id,
            operation=stage.operation,
            write_set_digest_reference=stage.write_set_digest_reference,
            staged_mutation_count=1,
        )

    async def read_exact_state_revision(self, _context, locator):
        self.events.append("state.read")
        return RuntimeApiExecutionStateRevisionReadResult(
            locator=locator,
            state=RuntimeExecutionState.RUNNING,
            record_digest_reference="state.revision.digest",
            observed_at=NOW,
        )

    async def read_exact_logical_execution_result_revision(self, _context, _locator):
        raise AssertionError("absent-result query must not read a logical result")


class CapabilityFactory:
    def __init__(self, events: list[str], *, resolved=None) -> None:
        self.events = events
        self.resolved = resolved
        self.contexts = []

    def __call__(self, _session, context):
        self.contexts.append(context)
        return Capability(self.events, resolved=self.resolved)


def local_operation(integration, *, callback_result=None, resolved=None):
    events: list[str] = []
    factory = CapabilityFactory(events, resolved=resolved)
    if callback_result is None and hasattr(integration, "stage"):
        callback_result = RuntimeApiDomainOperationResult(
            safe_result=safe_result(),
            stage=integration.stage,
        )
    callback = DomainCallback(callback_result)
    operation = RuntimeApiActiveTransactionLocalOperation(
        object(),  # type: ignore[arg-type]
        persistence_factory=factory,
        state_reader_factory=factory,
        logical_result_reader_factory=factory,
        domain_callback=callback,
    )
    return operation, callback, events, factory


@pytest.mark.asyncio
async def test_prepared_integration_facts_provider_is_operation_bound_and_one_shot() -> None:
    integration = submission_integration_facts()
    provider = OneShotRuntimeApiIntegrationFactsProvider(integration)
    assert await provider.provide_submission() is integration
    with pytest.raises(RuntimeApiIntegrationError, match="one-shot"):
        await provider.provide_submission()

    wrong = OneShotRuntimeApiIntegrationFactsProvider(integration)
    with pytest.raises(RuntimeApiIntegrationError, match="operation differs"):
        await wrong.provide_query()
    with pytest.raises(RuntimeApiIntegrationError, match="one-shot"):
        await wrong.provide_submission()


@pytest.mark.asyncio
async def test_pure_binder_carries_exact_submission_facts_without_io() -> None:
    integration = submission_integration_facts()
    request = RuntimeApiSubmissionInput(
        action_reference=integration.action_reference,
        command_reference=integration.command_reference,
        classification=integration.classification,
        idempotency_key="key.integration",
    )
    facts = RuntimeApiSubmissionFacts(
        command_id=integration.command_id,
        command_version=integration.command_version,
        receipt_id=integration.stage.transport_receipt_id,
        committed_at=NOW,
        correlation_reference=integration.correlation_reference,
        context=context_facts(),
        integration=integration,
    )
    digest = build_runtime_api_submission_digest(request, facts=facts)
    integration = integration.model_copy(update={"command_digest": digest})
    facts = facts.model_copy(update={"integration": integration})
    bound = await RuntimeApiExactOrchestrationFactBinder(object()).bind_submission(  # type: ignore[arg-type]
        principal(),
        scope(),
        permission(),
        request,
        facts,
        digest,
    )
    assert bound.integration is integration
    assert bound.invocation_reference == integration.invocation_reference
    assert bound.identity.command_digest == integration.command_digest


@pytest.mark.asyncio
async def test_new_submission_reads_then_calls_and_stages_exactly_once() -> None:
    supplied = command()
    operation, callback, events, factory = local_operation(supplied.integration)
    assert await operation.submit_invocation(supplied) == safe_result()
    assert events == ["binding.read", "local.stage"]
    assert callback.calls == 1
    assert len(factory.contexts) == 2
    assert factory.contexts[0] == factory.contexts[1] == supplied.integration.active_transaction


@pytest.mark.asyncio
async def test_binding_substitution_fails_before_callback_and_stage() -> None:
    supplied = command()
    substituted = supplied.integration.binding.persistence.model_copy(
        update={
            "requested_at": supplied.integration.binding.persistence.requested_at.replace(year=2027)
        }
    )
    operation, callback, events, _factory = local_operation(
        supplied.integration,
        resolved=substituted,
    )
    with pytest.raises(Exception, match="persisted facts are unavailable or conflict"):
        await operation.submit_invocation(supplied)
    assert events == ["binding.read"]
    assert callback.calls == 0


@pytest.mark.asyncio
async def test_domain_result_substitution_fails_before_local_stage() -> None:
    supplied = command()
    mismatched = RuntimeApiDomainOperationResult(
        safe_result=safe_result().model_copy(
            update={
                "projection": safe_result().projection.model_copy(
                    update={"invocation_reference": "invocation.substituted"}
                )
            }
        ),
        stage=supplied.integration.stage,
    )
    operation, callback, events, _factory = local_operation(
        supplied.integration,
        callback_result=mismatched,
    )
    with pytest.raises(Exception, match="domain operation submission stage differs"):
        await operation.submit_invocation(supplied)
    assert events == ["binding.read"]
    assert callback.calls == 1


@pytest.mark.asyncio
async def test_query_reads_exact_binding_and_state_without_mutation() -> None:
    integration = query_integration_facts()
    query = RuntimeApiInvocationQuery(
        query_id=integration.query_id,
        principal=principal(),
        scope=scope(),
        permission=permission(RuntimeApiPermission.READ),
        invocation_reference=integration.invocation_reference,
        correlation_reference=integration.correlation_reference,
        integration=integration,
    )
    operation, callback, events, factory = local_operation(integration)
    projection = await operation.get_invocation(query)
    assert projection.invocation_reference == query.invocation_reference
    assert projection.correlation_reference == query.correlation_reference
    assert projection.status_reference == "state.revision.digest"
    assert events == ["binding.read", "state.read"]
    assert callback.calls == 0
    assert len(factory.contexts) == 2


def test_integration_source_has_no_hidden_fact_or_transaction_control() -> None:
    source = (
        Path(__file__).parents[1] / "app" / "services" / "runtime_api_integration.py"
    ).read_text(encoding="utf-8")
    forbidden = (
        "uuid4",
        "datetime.now",
        "datetime.utcnow",
        "time.time",
        ".begin(",
        ".begin_nested(",
        ".commit(",
        ".rollback(",
        ".close(",
        "create_async_engine",
        "async_sessionmaker",
    )
    assert all(item not in source for item in forbidden)
