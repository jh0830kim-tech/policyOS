import inspect
from uuid import UUID

from app.services.runtime_api_contracts import RuntimeApiCommandIdentity, RuntimeApiOperation
from app.services.runtime_api_idempotency import SQLAlchemyRuntimeApiIdempotencyTransaction
from app.services.runtime_api_protocols import RuntimeApiIdempotencyTransactionPort


def test_production_transaction_structurally_conforms_to_port() -> None:
    assert isinstance(SQLAlchemyRuntimeApiIdempotencyTransaction, type)
    assert set(inspect.signature(SQLAlchemyRuntimeApiIdempotencyTransaction.commit).parameters) == {
        "self",
        "identity",
        "facts",
        "mutation",
    }
    assert hasattr(RuntimeApiIdempotencyTransactionPort, "commit")


def test_lock_key_is_stable_and_excludes_digest() -> None:
    from app.services.runtime_api_idempotency import _advisory_lock_key

    first = RuntimeApiCommandIdentity(
        command_id=UUID(int=11),
        operation=RuntimeApiOperation.SUBMIT_INVOCATION,
        tenant_id=UUID(int=1),
        organization_id=UUID(int=2),
        principal_id=UUID(int=3),
        command_version="v1",
        idempotency_key="key-1",
        command_digest="digest-reference-0001",
        correlation_reference="correlation-1",
    )
    changed = first.model_copy(update={"command_digest": "digest-reference-9999"})
    assert _advisory_lock_key(first) == _advisory_lock_key(first)
    assert _advisory_lock_key(first) == _advisory_lock_key(changed)
