"""Deterministic support for the CP9 PostgreSQL/HTTP acceptance gate."""

from __future__ import annotations

from dataclasses import dataclass
from uuid import NAMESPACE_URL, UUID, uuid5

from pydantic import BaseModel
from sqlalchemy import select

from app.ai.privacy import DataClassification
from app.models.identity import (
    Membership,
    MembershipRole,
    Organization,
    Role,
    RolePermission,
    TenantOrganizationBinding,
    User,
)
from app.models.runtime_registry import RuntimeRegistrySnapshotRecord
from app.runtime.persistence import (
    SQLAlchemyRuntimeRateAdmissionRepository,
    SQLAlchemyRuntimeRegistryRepository,
)
from app.runtime.ports import RuntimeRatePolicyProvisionCommand
from app.services.runtime_api_contracts import (
    RuntimeApiClockReading,
    RuntimeApiDeadlineBudgetResult,
    RuntimeApiDeadlineDisposition,
    RuntimeApiDisconnectDisposition,
    RuntimeApiDisconnectObservationResult,
    RuntimeApiOperation,
    RuntimeApiReconciliationFacts,
    RuntimeApiReconciliationInput,
    RuntimeApiReconciliationIntegrationFacts,
    RuntimeApiTrustedContextFacts,
)
from app.services.runtime_api_production import (
    RuntimeApiProductionRequestScopeFactory,
    SQLAlchemyRuntimeApiRateAdmissionCapability,
)
from app.services.runtime_api_protocols import (
    RuntimeApiProductionDependencyBundle,
    RuntimeApiReconciliationPreparationContext,
)
from app.services.runtime_api_validation import build_runtime_api_reconciliation_digest
from tests.test_runtime_api_binding_contracts import (
    ORGANIZATION,
    TENANT,
    operational_preflight,
    preparation_provenance,
    reconciliation_integration_facts,
    uid,
)
from tests.test_runtime_api_facade_persistence import ConcreteDomainCallback

AUDIENCE = "policyos-api-test"
PRINCIPAL_ID = uid(97)
POLICY_ACTOR_ID = uid(153)
POLICY_MEMBERSHIP_ID = uid(154)
RUNTIME_MEMBERSHIP_ID = uid(181)
RUNTIME_ROLE_ID = uid(182)
POLICY_ROLE_ID = uid(183)
BINDING_ID = uid(184)
PERMISSION_IDS = (
    UUID("00000000-0000-0000-0000-000000001901"),
    UUID("00000000-0000-0000-0000-000000001902"),
    UUID("00000000-0000-0000-0000-000000001903"),
)
RATE_PERMISSION_ID = UUID("00000000-0000-0000-0000-000000001905")


class ManagedCapability:
    def __init__(self, capability, events: list[str], name: str) -> None:
        self.capability = capability
        self.events = events
        self.name = name

    async def __aenter__(self):
        self.events.append(f"enter:{self.name}")
        return self.capability

    async def __aexit__(self, exc_type, exc, traceback):
        self.events.append(f"exit:{self.name}")
        return False


class DomainOperation:
    def __init__(self, callback: ConcreteDomainCallback) -> None:
        self.callback = callback

    async def submission_callback(self, provenance, facts):
        return self.callback

    async def reconciliation_callback(self, provenance, facts):
        return self.callback


class TrustedClock:
    def __init__(self, reading: RuntimeApiClockReading) -> None:
        self.reading = reading

    async def read(self, clock_reference):
        assert clock_reference == self.reading.clock_reference
        return self.reading


class DeadlineBudget:
    async def evaluate(self, request):
        return RuntimeApiDeadlineBudgetResult(
            request=request,
            disposition=RuntimeApiDeadlineDisposition.AVAILABLE,
            remaining=request.deadline_at - request.clock.observed_at,
        )


class DisconnectObservation:
    def __init__(self, signal) -> None:
        self.signal = signal

    async def observe(self, request):
        disconnected = await self.signal.is_disconnected()
        return RuntimeApiDisconnectObservationResult(
            request=request,
            disposition=(
                RuntimeApiDisconnectDisposition.DISCONNECTED
                if disconnected
                else RuntimeApiDisconnectDisposition.CONNECTED
            ),
            observed_at=request.clock.observed_at,
        )


class PreparationUpstream:
    def __init__(self, context: RuntimeApiReconciliationPreparationContext) -> None:
        self.context = context

    async def prepare_submission(self, claims, organization, request):
        raise AssertionError("submission is outside this acceptance scenario")

    async def prepare_query(self, claims, organization, request):
        raise AssertionError("query is outside this acceptance scenario")

    async def prepare_reconciliation(self, claims, organization, request):
        return self.context


@dataclass(slots=True)
class AcceptanceFactories:
    session_factory: object
    context: RuntimeApiReconciliationPreparationContext
    callback: ConcreteDomainCallback
    events: list[str]

    def domain(self):
        return ManagedCapability(DomainOperation(self.callback), self.events, "domain")

    def clock(self):
        return ManagedCapability(TrustedClock(self.context.clock), self.events, "clock")

    def rate(self):
        capability = SQLAlchemyRuntimeApiRateAdmissionCapability(self.session_factory)
        return ManagedCapability(capability, self.events, "rate")

    def deadline(self):
        return ManagedCapability(DeadlineBudget(), self.events, "deadline")

    def disconnect(self, signal):
        return ManagedCapability(DisconnectObservation(signal), self.events, "disconnect")

    def upstream(self, domain_operation, clock):
        return ManagedCapability(PreparationUpstream(self.context), self.events, "upstream")

    def bundle(self) -> RuntimeApiProductionDependencyBundle:
        scope = RuntimeApiProductionRequestScopeFactory(
            domain_operation_factory=self.domain,
            clock_factory=self.clock,
            rate_admission_factory=self.rate,
            deadline_budget_factory=self.deadline,
            disconnect_observation_factory=self.disconnect,
            preparation_upstream_factory=self.upstream,
        )
        return RuntimeApiProductionDependencyBundle(request_capability_scope_factory=scope)


async def seed_identity(session_factory) -> None:
    async with session_factory() as session, session.begin():
        if await session.get(Organization, ORGANIZATION) is None:
            session.add(
                Organization(
                    id=ORGANIZATION,
                    name="Runtime Acceptance",
                    slug="runtime-acceptance",
                )
            )
        for user_id, label in (
            (PRINCIPAL_ID, "Runtime Principal"),
            (POLICY_ACTOR_ID, "Rate Policy Manager"),
        ):
            if await session.get(User, user_id) is None:
                session.add(
                    User(
                        id=user_id,
                        email=f"{user_id}@acceptance.invalid",
                        display_name=label,
                    )
                )
        await session.flush()
        if await session.get(TenantOrganizationBinding, BINDING_ID) is None:
            existing = await session.scalar(
                select(TenantOrganizationBinding).where(
                    TenantOrganizationBinding.organization_id == ORGANIZATION
                )
            )
            if existing is None:
                session.add(
                    TenantOrganizationBinding(
                        id=BINDING_ID,
                        organization_id=ORGANIZATION,
                        runtime_tenant_id=TENANT,
                        status="active",
                        classification_ceiling="confidential",
                        provisioning_reference="acceptance:binding",
                        provisioned_by_user_id=POLICY_ACTOR_ID,
                        created_at=_now(),
                        status_changed_at=_now(),
                    )
                )
        for membership_id, user_id in (
            (RUNTIME_MEMBERSHIP_ID, PRINCIPAL_ID),
            (POLICY_MEMBERSHIP_ID, POLICY_ACTOR_ID),
        ):
            if await session.get(Membership, membership_id) is None:
                session.add(
                    Membership(
                        id=membership_id,
                        organization_id=ORGANIZATION,
                        user_id=user_id,
                        status="active",
                        joined_at=_now(),
                    )
                )
        for role_id, key, name in (
            (RUNTIME_ROLE_ID, "runtime-acceptance", "Runtime Acceptance"),
            (POLICY_ROLE_ID, "rate-policy-acceptance", "Rate Policy Acceptance"),
        ):
            if await session.get(Role, role_id) is None:
                session.add(Role(id=role_id, organization_id=ORGANIZATION, key=key, name=name))
        await session.flush()
        for membership_id, role_id in (
            (RUNTIME_MEMBERSHIP_ID, RUNTIME_ROLE_ID),
            (POLICY_MEMBERSHIP_ID, POLICY_ROLE_ID),
        ):
            if await session.get(MembershipRole, (membership_id, role_id)) is None:
                session.add(MembershipRole(membership_id=membership_id, role_id=role_id))
        for permission_id in PERMISSION_IDS:
            if await session.get(RolePermission, (RUNTIME_ROLE_ID, permission_id)) is None:
                session.add(RolePermission(role_id=RUNTIME_ROLE_ID, permission_id=permission_id))
        if await session.get(RolePermission, (RUNTIME_ROLE_ID, RATE_PERMISSION_ID)) is None:
            session.add(RolePermission(role_id=RUNTIME_ROLE_ID, permission_id=RATE_PERMISSION_ID))


def _now():
    from tests.test_runtime_api_binding_contracts import NOW

    return NOW


def reconciliation_case(idempotency_key: str):
    request = RuntimeApiReconciliationInput(
        invocation_reference="invocation-1",
        reconciliation_reference="reconciliation-1",
        idempotency_key=idempotency_key,
    )
    integration = _acceptance_integration(reconciliation_integration_facts())
    facts = RuntimeApiReconciliationFacts(
        command_id=integration.command_id,
        command_version=integration.command_version,
        receipt_id=integration.stage.transport_receipt_id,
        committed_at=_now(),
        correlation_reference=integration.correlation_reference,
        context=RuntimeApiTrustedContextFacts(
            authentication_reference="authentication:acceptance",
            validation_reference="validation:acceptance",
            authenticated_at=_now(),
            validated_at=_now(),
        ),
        integration=integration,
    )
    digest = build_runtime_api_reconciliation_digest(request, facts=facts)
    facts = facts.model_copy(
        update={"integration": integration.model_copy(update={"command_digest": digest})}
    )
    provenance = preparation_provenance(
        RuntimeApiOperation.REQUEST_RECONCILIATION,
        facts.command_id,
        digest,
        facts.correlation_reference,
        DataClassification.CONFIDENTIAL,
    )
    preflight = operational_preflight(provenance)
    policy = preflight.rate_admission.policy.revision.model_copy(
        update={
            "actor_principal_id": PRINCIPAL_ID,
            "actor_user_id": PRINCIPAL_ID,
            "actor_membership_id": RUNTIME_MEMBERSHIP_ID,
        }
    )
    rate_admission = preflight.rate_admission.model_copy(
        update={
            "policy": preflight.rate_admission.policy.model_copy(update={"revision": policy}),
            "decision": preflight.rate_admission.decision.model_copy(update={"policy": policy}),
        }
    )
    preflight = preflight.model_copy(update={"rate_admission": rate_admission})
    callback = ConcreteDomainCallback()
    context = RuntimeApiReconciliationPreparationContext(
        provenance=provenance,
        clock=preflight.rate_admission.clock,
        preflight=preflight,
        facts=facts,
        domain_callback=callback,
    )
    return request, facts, context, callback


def _acceptance_integration(
    integration: RuntimeApiReconciliationIntegrationFacts,
) -> RuntimeApiReconciliationIntegrationFacts:
    preserved = {
        TENANT,
        ORGANIZATION,
        PRINCIPAL_ID,
        POLICY_ACTOR_ID,
        POLICY_MEMBERSHIP_ID,
    }

    def replace(value):
        if isinstance(value, BaseModel):
            return value.model_copy(
                update={name: replace(getattr(value, name)) for name in type(value).model_fields}
            )
        if isinstance(value, tuple):
            return tuple(replace(item) for item in value)
        if isinstance(value, UUID) and value not in preserved:
            return uuid5(NAMESPACE_URL, f"policyos:cp9-acceptance:{value}")
        return value

    result = replace(integration)
    assert isinstance(result, RuntimeApiReconciliationIntegrationFacts)
    return result


async def seed_persistence(session_factory, facts, context) -> None:
    await seed_identity(session_factory)
    async with session_factory() as session, session.begin():
        snapshot = facts.integration.binding.persistence.registry_resolution_admission.snapshot
        existing = await session.get(
            RuntimeRegistrySnapshotRecord,
            (snapshot.runtime_registry_snapshot_id, snapshot.registry_revision),
        )
        if existing is None:
            await SQLAlchemyRuntimeRegistryRepository(session).append_binding(
                facts.integration.binding.persistence
            )
    async with session_factory() as session, session.begin():
        command = RuntimeRatePolicyProvisionCommand(
            policy=context.preflight.rate_admission.policy.revision,
            permission_reference=f"permission:{RATE_PERMISSION_ID}",
        )
        await SQLAlchemyRuntimeRateAdmissionRepository(session).provision_policy(command)
