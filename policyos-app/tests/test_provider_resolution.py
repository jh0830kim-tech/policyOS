from datetime import UTC, datetime, timedelta
from uuid import uuid4

import pytest
from pydantic import ValidationError

from app.ai.privacy import DataClassification
from app.execution import ExecutionContext
from app.execution.provider_errors import (
    BindingExpiredError,
    BindingIdentityMismatchError,
    NoEligibleProviderError,
    ProviderPolicyError,
    UnknownProviderError,
)
from app.execution.provider_resolution import (
    AvailabilityStatus,
    DeterministicProviderResolver,
    DispatchBinding,
    ProviderAvailability,
    ProviderAvailabilitySnapshot,
    ProviderCapability,
    ProviderCatalog,
    ProviderDescriptor,
    ProviderKind,
    ProviderRequirement,
    ProviderSelectionPolicy,
    bind_dispatch,
    korean_law_mcp_descriptor,
)
from app.execution.runtime import DispatchRequest, ExecutionSession, SessionStatus

NOW = datetime(2026, 7, 26, 1, tzinfo=UTC)


def descriptor(provider_id="knowledge.alpha", **changes):
    values = dict(
        provider_id=provider_id,
        provider_kind=ProviderKind.KNOWLEDGE,
        capabilities=(ProviderCapability(capability_id="knowledge.search"),),
        priority=100,
        reliability_tier=5,
    )
    values.update(changes)
    return ProviderDescriptor(**values)


def requirement(ids, **changes):
    values = dict(
        capability_id="knowledge.search",
        classification=DataClassification.INTERNAL,
        organization_id=ids[0],
        actor_id=ids[1],
        policy_id="trusted.default",
        execution_id=ids[2],
        step_id="search",
    )
    values.update(changes)
    return ProviderRequirement(**values)


def policy(**changes):
    values = dict(policy_id="trusted.default")
    values.update(changes)
    return ProviderSelectionPolicy(**values)


def availability(*provider_ids, status=AvailabilityStatus.AVAILABLE, valid_until=None):
    return ProviderAvailabilitySnapshot.from_entries(
        ProviderAvailability(
            provider_id=item,
            status=status,
            observed_at=NOW,
            valid_until=valid_until,
        )
        for item in provider_ids
    )


def test_catalog_factory_is_immutable_and_canonical():
    catalog = ProviderCatalog.from_providers([descriptor("knowledge.zed"), descriptor()])
    assert [item.provider_id for item in catalog.all()] == ["knowledge.alpha", "knowledge.zed"]
    with pytest.raises(ValidationError):
        catalog.providers = ()


def test_catalog_rejects_duplicates_and_requires_known_provider():
    item = descriptor()
    with pytest.raises(ValidationError, match="duplicate provider"):
        ProviderCatalog(providers=(item, item))
    with pytest.raises(UnknownProviderError):
        ProviderCatalog(providers=()).require("knowledge.missing")


@pytest.mark.parametrize(
    "provider_id",
    ["UPPER.case", "no_dot", "https.example", "knowledge.a/b", "knowledge.secret-token"],
)
def test_provider_identifier_is_stable_and_safe(provider_id):
    with pytest.raises(ValidationError):
        descriptor(provider_id)


def test_descriptor_rejects_duplicate_capabilities_and_tenant_overlap():
    capability = ProviderCapability(capability_id="knowledge.search")
    with pytest.raises(ValidationError):
        descriptor(capabilities=(capability, capability))
    organization_id = uuid4()
    with pytest.raises(ValidationError):
        descriptor(
            allowed_organization_ids=(organization_id,),
            denied_organization_ids=(organization_id,),
        )


def test_descriptor_metadata_rejects_secrets_and_runtime_objects():
    with pytest.raises(ValidationError):
        descriptor(metadata={"api_key": "value"})
    with pytest.raises(ValidationError):
        descriptor(metadata={"client": object()})


def test_missing_availability_fails_closed(ids):
    with pytest.raises(NoEligibleProviderError):
        DeterministicProviderResolver().resolve(
            requirement(ids), ProviderCatalog.from_providers([descriptor()]), None, policy(), NOW
        )


def test_unknown_availability_can_be_explicitly_allowed(ids):
    decision = DeterministicProviderResolver().resolve(
        requirement(ids),
        ProviderCatalog.from_providers([descriptor()]),
        None,
        policy(allow_unknown_availability=True),
        NOW,
    )
    assert decision.selected_provider_id == "knowledge.alpha"


@pytest.mark.parametrize("status", [AvailabilityStatus.UNAVAILABLE, AvailabilityStatus.DISABLED])
def test_unavailable_provider_is_ineligible(ids, status):
    with pytest.raises(NoEligibleProviderError):
        DeterministicProviderResolver().resolve(
            requirement(ids),
            ProviderCatalog.from_providers([descriptor()]),
            availability("knowledge.alpha", status=status),
            policy(allow_unknown_availability=True),
            NOW,
        )


def test_degraded_provider_requires_policy_opt_in(ids):
    catalog = ProviderCatalog.from_providers([descriptor()])
    snapshot = availability("knowledge.alpha", status=AvailabilityStatus.DEGRADED)
    with pytest.raises(NoEligibleProviderError):
        DeterministicProviderResolver().resolve(requirement(ids), catalog, snapshot, policy(), NOW)
    decision = DeterministicProviderResolver().resolve(
        requirement(ids), catalog, snapshot, policy(allow_degraded=True), NOW
    )
    assert decision.selected_provider_id == "knowledge.alpha"


def test_snapshot_is_stale_at_valid_until(ids):
    with pytest.raises(NoEligibleProviderError):
        DeterministicProviderResolver().resolve(
            requirement(ids),
            ProviderCatalog.from_providers([descriptor()]),
            availability("knowledge.alpha", valid_until=NOW),
            policy(),
            NOW,
        )


def test_classification_and_organization_are_fail_closed(ids):
    organization_id = ids[0]
    providers = [
        descriptor(maximum_classification=DataClassification.PUBLIC),
        descriptor("knowledge.beta", denied_organization_ids=(organization_id,)),
    ]
    with pytest.raises(NoEligibleProviderError):
        DeterministicProviderResolver().resolve(
            requirement(ids),
            ProviderCatalog.from_providers(providers),
            availability("knowledge.alpha", "knowledge.beta"),
            policy(),
            NOW,
        )


def test_feature_and_policy_limits_are_enforced(ids):
    provider = descriptor(cost_tier=5, latency_tier=5)
    with pytest.raises(NoEligibleProviderError):
        DeterministicProviderResolver().resolve(
            requirement(ids, required_citations=True, maximum_cost_tier=2),
            ProviderCatalog.from_providers([provider]),
            availability("knowledge.alpha"),
            policy(),
            NOW,
        )


def test_ranking_is_deterministic_and_uses_provider_id_tie_breaker(ids):
    providers = [descriptor("knowledge.zed"), descriptor("knowledge.alpha")]
    decision = DeterministicProviderResolver().resolve(
        requirement(ids),
        ProviderCatalog.from_providers(reversed(providers)),
        availability("knowledge.zed", "knowledge.alpha"),
        policy(),
        NOW,
    )
    assert decision.selected_provider_id == "knowledge.alpha"
    assert [item.provider_id for item in decision.candidates] == [
        "knowledge.alpha",
        "knowledge.zed",
    ]


def test_trusted_preference_precedes_priority(ids):
    decision = DeterministicProviderResolver().resolve(
        requirement(ids, preferred_provider_ids=("knowledge.zed",)),
        ProviderCatalog.from_providers(
            [descriptor("knowledge.alpha", priority=0), descriptor("knowledge.zed", priority=999)]
        ),
        availability("knowledge.alpha", "knowledge.zed"),
        policy(),
        NOW,
    )
    assert decision.selected_provider_id == "knowledge.zed"


def test_optional_requirement_can_return_safe_unbound_decision(ids):
    decision = DeterministicProviderResolver().resolve(
        requirement(ids, required=False), ProviderCatalog(providers=()), None, policy(), NOW
    )
    assert decision.selected_provider_id is None
    assert decision.warnings == ("optional_capability_unavailable",)


def test_policy_identity_and_preference_overlap_are_rejected(ids):
    with pytest.raises(ValidationError, match="must not overlap"):
        requirement(
            ids,
            preferred_provider_ids=("knowledge.alpha",),
            excluded_provider_ids=("knowledge.alpha",),
        )
    with pytest.raises(ProviderPolicyError):
        DeterministicProviderResolver().resolve(
            requirement(ids),
            ProviderCatalog(providers=()),
            None,
            ProviderSelectionPolicy(policy_id="trusted.other"),
            NOW,
        )


def dispatch_scope(ids):
    organization_id, actor_id, execution_id, session_id, plan_id = ids
    session = ExecutionSession(
        session_id=session_id,
        execution_id=execution_id,
        plan_id=plan_id,
        organization_id=organization_id,
        actor_id=actor_id,
        correlation_id="corr",
        classification=DataClassification.INTERNAL,
        status=SessionStatus.RUNNING,
        created_at=NOW,
        started_at=NOW,
        updated_at=NOW,
        deadline=NOW + timedelta(minutes=5),
    )
    context = ExecutionContext(
        execution_id=execution_id,
        organization_id=organization_id,
        actor_id=actor_id,
        classification=DataClassification.INTERNAL,
        correlation_id="corr",
        deadline=session.deadline,
    )
    dispatch = DispatchRequest(
        dispatch_id=uuid4(),
        session_id=session_id,
        execution_id=execution_id,
        plan_id=plan_id,
        step_id="search",
        capability_id="knowledge.search",
        input={"query": "safe"},
        classification=DataClassification.INTERNAL,
        organization_id=organization_id,
        actor_id=actor_id,
        correlation_id="corr",
        attempt=1,
        timeout_seconds=60,
        deadline=session.deadline,
        issued_at=NOW,
    )
    return dispatch, session, context


@pytest.fixture
def ids():
    return tuple(uuid4() for _ in range(5))


def test_dispatch_binding_validates_all_identities_and_omits_input(ids):
    dispatch, session, context = dispatch_scope(ids)
    req = requirement(ids)
    catalog = ProviderCatalog.from_providers([descriptor()])
    decision = DeterministicProviderResolver().resolve(
        req, catalog, availability("knowledge.alpha"), policy(), NOW
    )
    binding = bind_dispatch(
        dispatch,
        session,
        context,
        req,
        decision,
        catalog,
        binding_id=uuid4(),
        bound_at=NOW,
        idempotency_key="dispatch.search.1",
    )
    assert isinstance(binding, DispatchBinding)
    assert binding.provider_id == "knowledge.alpha"
    assert "input" not in binding.model_dump()


def test_dispatch_binding_rejects_identity_mismatch(ids):
    dispatch, session, context = dispatch_scope(ids)
    req = requirement(ids)
    catalog = ProviderCatalog.from_providers([descriptor()])
    decision = DeterministicProviderResolver().resolve(
        req, catalog, availability("knowledge.alpha"), policy(), NOW
    )
    with pytest.raises(BindingIdentityMismatchError):
        bind_dispatch(
            dispatch.model_copy(update={"actor_id": uuid4()}),
            session,
            context,
            req,
            decision,
            catalog,
            binding_id=uuid4(),
            bound_at=NOW,
            idempotency_key="dispatch.search.1",
        )


def test_dispatch_binding_rejects_expired_deadline(ids):
    dispatch, session, context = dispatch_scope(ids)
    req = requirement(ids)
    catalog = ProviderCatalog.from_providers([descriptor()])
    decision = DeterministicProviderResolver().resolve(
        req, catalog, availability("knowledge.alpha"), policy(), NOW
    )
    with pytest.raises(BindingExpiredError):
        bind_dispatch(
            dispatch,
            session,
            context,
            req,
            decision,
            catalog,
            binding_id=uuid4(),
            bound_at=dispatch.deadline,
            idempotency_key="dispatch.search.1",
        )


def test_requirement_must_match_dispatch_classification(ids):
    dispatch, _, _ = dispatch_scope(ids)
    with pytest.raises(ValueError):
        requirement(ids, classification=DataClassification.RESTRICTED).validate_dispatch(dispatch)


def test_korean_law_descriptor_is_static_safe_and_resolvable(ids):
    provider = korean_law_mcp_descriptor()
    assert provider.provider_id == "knowledge.korean_law_mcp"
    assert provider.metadata == {"legacy_provider_name": "korean-law-mcp"}
    assert not any("client" in name or "credential" in name for name in type(provider).model_fields)
    req = requirement(ids, capability_id="knowledge.legal_search", required_citations=True)
    decision = DeterministicProviderResolver().resolve(
        req,
        ProviderCatalog.from_providers([provider]),
        availability(provider.provider_id),
        policy(),
        NOW,
    )
    assert decision.selected_provider_id == provider.provider_id
