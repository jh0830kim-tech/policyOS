from datetime import timedelta
from uuid import UUID

import pytest
from pydantic import ValidationError
from test_grounded_narrative_generator import NOW

from app.ai.privacy import DataClassification
from app.intelligence import (
    AgentCapability,
    AgentRole,
    DelegationContext,
    DelegationPolicy,
    DelegationRequest,
    WorkProductReference,
    WorkProductReferenceType,
    WorkProductType,
    build_agent_assignment,
    build_default_ai_office_agent_catalog,
    validate_delegation,
)
from app.intelligence.agent_errors import (
    AgentAssignmentError,
    DelegationIdentityError,
    UnknownAgentError,
)

IDS = [UUID(f"{i:08d}-9999-9999-9999-999999999999") for i in range(1, 9)]


def delegation(**changes):
    values = dict(
        delegation_id=IDS[0],
        root_delegation_id=IDS[0],
        requesting_agent_id="office.secretary",
        requested_role=AgentRole.POLICY_RESEARCHER,
        required_capabilities=(AgentCapability.POLICY_RESEARCH,),
        objective="Research policy options",
        input_references=(
            WorkProductReference(
                reference_id="source.1",
                reference_type=WorkProductReferenceType.EXECUTION_RESULT,
                object_id=IDS[1],
                execution_id=IDS[2],
                organization_id=IDS[3],
                classification=DataClassification.RESTRICTED,
            ),
        ),
        expected_work_product_types=(WorkProductType.POLICY_ANALYSIS,),
        organization_id=IDS[3],
        actor_id=IDS[4],
        correlation_id="correlation-1",
        classification=DataClassification.RESTRICTED,
        delegation_depth=0,
        issued_at=NOW,
        deadline=NOW + timedelta(minutes=5),
    )
    values.update(changes)
    return DelegationRequest(**values)


def context(**changes):
    values = dict(
        delegation_id=IDS[0],
        organization_id=IDS[3],
        actor_id=IDS[4],
        correlation_id="correlation-1",
        classification=DataClassification.RESTRICTED,
        current_depth=0,
        validated_at=NOW,
    )
    values.update(changes)
    return DelegationContext(**values)


def test_default_catalog_is_immutable_deterministic_and_role_bounded():
    first, second = build_default_ai_office_agent_catalog(), build_default_ai_office_agent_catalog()
    assert first == second and len(first.definitions) == 9
    secretary = first.require("office.secretary")
    assert secretary.may_delegate and AgentCapability.LEGAL_RESEARCH not in secretary.capabilities
    assert all(
        not item.may_delegate for item in first.definitions if item.role is not AgentRole.SECRETARY
    )
    with pytest.raises(ValidationError):
        first.definitions = ()
    with pytest.raises(UnknownAgentError):
        first.require("unknown")


def test_capabilities_fail_closed_and_provider_controls_are_unavailable():
    with pytest.raises(ValidationError):
        delegation(required_capabilities=("POLICY.RESEARCH",))
    with pytest.raises(ValidationError):
        delegation(required_capabilities=("policy.*",))
    with pytest.raises(ValidationError):
        DelegationRequest(**delegation().model_dump(), provider="openai")


def test_valid_delegation_selects_unique_agent_and_builds_assignment():
    catalog = build_default_ai_office_agent_catalog()
    result = validate_delegation(delegation(), context(), DelegationPolicy(), catalog)
    assert result.valid and result.eligible_agent_ids == ("office.policy_researcher",)
    assignment = build_agent_assignment(IDS[5], delegation(), result, catalog)
    assert assignment.approved_capabilities == (AgentCapability.POLICY_RESEARCH,)
    assert assignment.organization_id == IDS[3]


def test_specialist_redelegation_self_delegation_and_depth_fail_closed():
    catalog = build_default_ai_office_agent_catalog()
    specialist = delegation(requesting_agent_id="office.legal_reviewer")
    result = validate_delegation(specialist, context(), DelegationPolicy(), catalog)
    assert not result.valid and "delegation_not_allowed" in {i.code for i in result.issues}
    deep = delegation(delegation_depth=2, parent_delegation_id=IDS[6])
    result = validate_delegation(deep, context(current_depth=2), DelegationPolicy(), catalog)
    assert "delegation_depth_exceeded" in {i.code for i in result.issues}


def test_tenant_classification_deadline_and_cancellation_are_enforced():
    with pytest.raises(DelegationIdentityError):
        delegation(
            input_references=(
                delegation().input_references[0].model_copy(update={"organization_id": IDS[7]}),
            )
        )
    expired = validate_delegation(
        delegation(),
        context(validated_at=delegation().deadline),
        DelegationPolicy(),
        build_default_ai_office_agent_catalog(),
    )
    assert "delegation_expired" in {i.code for i in expired.issues}
    cancelled = validate_delegation(
        delegation(),
        context(cancellation_requested=True),
        DelegationPolicy(),
        build_default_ai_office_agent_catalog(),
    )
    assert not cancelled.valid


def test_invalid_validation_cannot_create_assignment_and_serialization_is_stable():
    catalog = build_default_ai_office_agent_catalog()
    invalid = validate_delegation(
        delegation(), context(cancellation_requested=True), DelegationPolicy(), catalog
    )
    with pytest.raises(AgentAssignmentError):
        build_agent_assignment(IDS[5], delegation(), invalid, catalog)
    first = validate_delegation(delegation(), context(), DelegationPolicy(), catalog)
    second = validate_delegation(delegation(), context(), DelegationPolicy(), catalog)
    assert first.model_dump_json() == second.model_dump_json()
