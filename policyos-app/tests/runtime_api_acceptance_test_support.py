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
    SQLAlchemyExecutionRequestRepository,
    SQLAlchemyRuntimeRateAdmissionRepository,
    SQLAlchemyRuntimeRegistryRepository,
)
from app.runtime.ports import (
    RuntimeApiLocalWriteSetOperation,
    RuntimeApiLocalWriteSetStage,
    RuntimeApiLogicalExecutionResultMutationPresent,
    RuntimeRatePolicyProvisionCommand,
    RuntimeRepositoryWriteRequest,
)
from app.services.runtime_api_contracts import (
    RuntimeApiClockReading,
    RuntimeApiDeadlineBudgetResult,
    RuntimeApiDeadlineDisposition,
    RuntimeApiDisconnectDisposition,
    RuntimeApiDisconnectObservationResult,
    RuntimeApiDomainOperationResult,
    RuntimeApiOperation,
    RuntimeApiPublicStatus,
    RuntimeApiReconciliationFacts,
    RuntimeApiReconciliationInput,
    RuntimeApiReconciliationIntegrationFacts,
    RuntimeApiSafeResult,
    RuntimeApiStatusProjection,
    RuntimeApiSubmissionBindingFacts,
    RuntimeApiSubmissionFacts,
    RuntimeApiSubmissionInput,
    RuntimeApiSubmissionIntegrationFacts,
    RuntimeApiTrustedContextFacts,
)
from app.services.runtime_api_production import (
    RuntimeApiProductionRequestScopeFactory,
    SQLAlchemyRuntimeApiRateAdmissionCapability,
)
from app.services.runtime_api_protocols import (
    RuntimeApiProductionDependencyBundle,
    RuntimeApiReconciliationPreparationContext,
    RuntimeApiSubmissionPreparationContext,
)
from app.services.runtime_api_validation import (
    build_runtime_api_reconciliation_digest,
    build_runtime_api_submission_digest,
)
from tests.test_runtime_api_binding_contracts import (
    ORGANIZATION,
    TENANT,
    active_transaction_context,
    binding_for_effect_write_set,
    logical_execution_result,
    operational_preflight,
    preparation_provenance,
    reconciliation_integration_facts,
    uid,
)
from tests.test_runtime_api_facade_persistence import ConcreteDomainCallback
from tests.test_runtime_delivery_persistence_contracts import effect_write_set
from tests.test_runtime_orchestration_domain import invocation_request
from tests.test_runtime_persistence import seed_atomic_heads

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
    def __init__(
        self,
        context: RuntimeApiSubmissionPreparationContext
        | RuntimeApiReconciliationPreparationContext,
    ) -> None:
        self.context = context

    async def prepare_submission(self, claims, organization, request):
        if not isinstance(self.context, RuntimeApiSubmissionPreparationContext):
            raise AssertionError("submission is outside this acceptance scenario")
        return self.context

    async def prepare_query(self, claims, organization, request):
        raise AssertionError("query is outside this acceptance scenario")

    async def prepare_reconciliation(self, claims, organization, request):
        if not isinstance(self.context, RuntimeApiReconciliationPreparationContext):
            raise AssertionError("reconciliation is outside this acceptance scenario")
        return self.context


@dataclass(slots=True)
class AcceptanceFactories:
    session_factory: object
    context: RuntimeApiSubmissionPreparationContext | RuntimeApiReconciliationPreparationContext
    callback: object
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


async def seed_identity(
    session_factory,
    *,
    tenant_id=TENANT,
    organization_id=ORGANIZATION,
    classification_ceiling="confidential",
) -> None:
    async with session_factory() as session, session.begin():
        if await session.get(Organization, organization_id) is None:
            session.add(
                Organization(
                    id=organization_id,
                    name="Runtime Acceptance",
                    slug=f"runtime-acceptance-{organization_id}",
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
                    TenantOrganizationBinding.organization_id == organization_id
                )
            )
            if existing is None:
                session.add(
                    TenantOrganizationBinding(
                        id=BINDING_ID,
                        organization_id=organization_id,
                        runtime_tenant_id=tenant_id,
                        status="active",
                        classification_ceiling=classification_ceiling,
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
                        organization_id=organization_id,
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
                session.add(Role(id=role_id, organization_id=organization_id, key=key, name=name))
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


class SubmissionDomainCallback:
    def __init__(self) -> None:
        self.calls = 0

    async def __call__(self, command):
        self.calls += 1
        return RuntimeApiDomainOperationResult(
            safe_result=RuntimeApiSafeResult(
                result_reference="result:vertical-submission",
                projection=RuntimeApiStatusProjection(
                    invocation_reference=command.invocation_reference,
                    status=RuntimeApiPublicStatus.SUCCEEDED,
                    status_reference="status:vertical-submission",
                    correlation_reference=command.identity.correlation_reference,
                    observed_at=command.integration.stage.staged_at,
                ),
            ),
            stage=command.integration.stage,
        )


async def submission_case(idempotency_key: str):
    write_set = await effect_write_set()
    base = write_set.base_write_set
    scope = base.idempotency_reservation.scope
    binding = binding_for_effect_write_set(write_set)
    reservation = base.idempotency_reservation
    registry_facts = binding.registry_resolution_admission
    snapshot = registry_facts.snapshot.model_copy(
        update={
            "entries": tuple(
                entry.model_copy(
                    update={
                        "action_definition": entry.action_definition.model_copy(
                            update={
                                "identity": entry.action_definition.identity.model_copy(
                                    update={
                                        "action_definition_id": (reservation.action_definition_id),
                                        "action": reservation.action,
                                        "action_version": reservation.action_version,
                                    }
                                ),
                                "tenant_id": scope.tenant_id,
                                "organization_id": scope.organization_id,
                                "classification": scope.classification,
                                "root_lineage_id": scope.root_lineage_id,
                                "root_lineage_digest_reference": (
                                    scope.root_lineage_digest_reference
                                ),
                            }
                        )
                    }
                )
                for entry in registry_facts.snapshot.entries
            )
        }
    )
    binding = binding.model_copy(
        update={
            "registry_resolution_admission": registry_facts.model_copy(
                update={"snapshot": snapshot}
            )
        }
    )
    command_id = uuid5(NAMESPACE_URL, f"policyos:vertical:command:{idempotency_key}")
    receipt_id = uuid5(NAMESPACE_URL, f"policyos:vertical:receipt:{idempotency_key}")
    request = RuntimeApiSubmissionInput(
        action_reference="action-1",
        command_reference="command:vertical-submission",
        classification=scope.classification,
        idempotency_key=idempotency_key,
    )
    stage = RuntimeApiLocalWriteSetStage(
        local_write_set_id=uuid5(NAMESPACE_URL, f"policyos:vertical:stage:{idempotency_key}"),
        transport_receipt_id=receipt_id,
        operation=RuntimeApiLocalWriteSetOperation.SUBMIT_INVOCATION,
        binding=binding,
        write_set_digest_reference="write-set.vertical-deliverable",
        logical_execution_result=RuntimeApiLogicalExecutionResultMutationPresent(
            logical_execution_result=logical_execution_result(base, persisted=binding)
        ),
        write_set=write_set,
        staged_at=base.requested_at,
    )
    integration = RuntimeApiSubmissionIntegrationFacts(
        binding=RuntimeApiSubmissionBindingFacts(persistence=binding),
        active_transaction=active_transaction_context(),
        stage=stage,
        command_id=command_id,
        command_version="v1",
        command_digest="sha256:vertical-submission-placeholder",
        action_reference=request.action_reference,
        command_reference=request.command_reference,
        invocation_reference="invocation:vertical-submission",
        correlation_reference="correlation:vertical-submission",
        classification=scope.classification,
        tenant_id=scope.tenant_id,
        organization_id=scope.organization_id,
        root_lineage_id=scope.root_lineage_id,
        root_lineage_digest_reference=scope.root_lineage_digest_reference,
    )
    facts = RuntimeApiSubmissionFacts(
        command_id=command_id,
        command_version="v1",
        receipt_id=receipt_id,
        committed_at=_now(),
        correlation_reference=integration.correlation_reference,
        context=RuntimeApiTrustedContextFacts(
            authentication_reference="authentication:vertical-submission",
            validation_reference="validation:vertical-submission",
            authenticated_at=_now(),
            validated_at=_now(),
        ),
        integration=integration,
    )
    digest = build_runtime_api_submission_digest(request, facts=facts)
    integration = integration.model_copy(update={"command_digest": digest})
    facts = facts.model_copy(update={"integration": integration})
    provenance = preparation_provenance(
        RuntimeApiOperation.SUBMIT_INVOCATION,
        command_id,
        digest,
        integration.correlation_reference,
        scope.classification,
    ).model_copy(update={"tenant_id": scope.tenant_id, "organization_id": scope.organization_id})
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
    callback = SubmissionDomainCallback()
    context = RuntimeApiSubmissionPreparationContext(
        provenance=provenance,
        clock=preflight.rate_admission.clock,
        preflight=preflight,
        facts=facts,
        domain_callback=callback,
    )
    return request, facts, context, callback, write_set


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


async def seed_submission_persistence(session_factory, facts, context, write_set) -> None:
    base = write_set.base_write_set
    scope = base.idempotency_reservation.scope
    execution_request = invocation_request().authority.execution_request.model_copy(
        update={"classification": scope.classification}
    )
    if execution_request.runtime_execution_request_id != scope.runtime_execution_request_id:
        raise AssertionError("execution request differs from the exact submission scope")
    await seed_identity(
        session_factory,
        tenant_id=scope.tenant_id,
        organization_id=scope.organization_id,
        classification_ceiling=scope.classification.value,
    )
    previous_state = base.state_record.model_copy(
        update={"current_revision": base.expected_state_revision}
    )
    previous_audit = base.audit_trail.model_copy(
        update={"trail_revision": base.expected_audit_revision}
    )
    async with session_factory() as session, session.begin():
        await SQLAlchemyExecutionRequestRepository(session).save(
            execution_request,
            RuntimeRepositoryWriteRequest(
                runtime_repository_write_request_id=uuid5(
                    NAMESPACE_URL,
                    "policyos:vertical:execution-request:write",
                ),
                runtime_repository_write_receipt_id=uuid5(
                    NAMESPACE_URL,
                    "policyos:vertical:execution-request:receipt",
                ),
                record_id=execution_request.runtime_execution_request_id,
                tenant_id=execution_request.tenant_id,
                organization_id=execution_request.organization_id,
                classification=execution_request.classification,
                resulting_revision=1,
                record_digest_reference="request.vertical-input-digest",
                requested_at=execution_request.requested_at,
            ),
            stored_at=base.requested_at,
        )
        await SQLAlchemyRuntimeRegistryRepository(session).append_binding(
            facts.integration.binding.persistence
        )
        await seed_atomic_heads(session, previous_state, previous_audit)
    async with session_factory() as session, session.begin():
        await SQLAlchemyRuntimeRateAdmissionRepository(session).provision_policy(
            RuntimeRatePolicyProvisionCommand(
                policy=context.preflight.rate_admission.policy.revision,
                permission_reference=f"permission:{RATE_PERMISSION_ID}",
            )
        )
