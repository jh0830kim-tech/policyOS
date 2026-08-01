"""Canonical security lineage and continuity contracts.

Lineage digests detect metadata substitution and continuity mismatches. They
are not signatures and do not authenticate the producer of the metadata.
"""

import hashlib
import json
from datetime import UTC, datetime
from enum import StrEnum
from types import MappingProxyType
from uuid import UUID

from pydantic import Field, field_validator, model_validator

from app.ai.privacy import DataClassification
from app.execution.domain import ExecutionModel
from app.execution.validation import require_aware
from app.zero_trust.errors import (
    AttestationReferenceError,
    CrossValidationLineageError,
    LineageCanonicalizationError,
    LineageContinuityError,
    LineageDigestError,
    LineageStageError,
)


class LineageDigestAlgorithm(StrEnum):
    SHA256 = "sha256"


class LineageDigestVersion(StrEnum):
    V1 = "policyos_lineage_digest_v1"


class LineageCanonicalizationVersion(StrEnum):
    POLICYOS_LINEAGE_CANONICAL_V1 = "policyos_lineage_canonical_v1"


class LineageStage(StrEnum):
    DELEGATION_CREATED = "delegation_created"
    MODEL_BOUND = "model_bound"
    PROVIDER_BOUND = "provider_bound"
    MCP_BOUND = "mcp_bound"
    CONNECTOR_BOUND = "connector_bound"
    CROSS_VALIDATION_BOUND = "cross_validation_bound"
    SECRETARY_HANDOFF_BOUND = "secretary_handoff_bound"
    REPOSITORY_REQUEST_BOUND = "repository_request_bound"
    REPOSITORY_PERMIT_BOUND = "repository_permit_bound"
    RESULT_STORAGE_BOUND = "result_storage_bound"


_STAGE_ORDER = MappingProxyType(
    {stage: index for index, stage in enumerate(LineageStage)}
)
_LINEAGE_FIELD_ORDER = (
    "delegation_id",
    "tenant_id",
    "organization_id",
    "on_behalf_of_user_id",
    "service_actor_id",
    "agent_instance_id",
    "task_id",
    "resource_id",
    "resource_type",
    "action",
    "purpose",
    "risk_level",
    "classification",
    "delegation_scope",
    "authorization_decision_id",
    "issued_at",
    "expires_at",
    "parent_delegation_id",
    "cross_validation_plan_id",
    "cross_validation_run_id",
    "provider_instance_id",
    "model_id",
    "mcp_server_id",
    "tool_id",
    "connector_id",
)
_PROTECTED_FIELDS = (
    "tenant_id",
    "organization_id",
    "on_behalf_of_user_id",
    "service_actor_id",
    "agent_instance_id",
    "task_id",
    "resource_id",
    "resource_type",
    "action",
    "purpose",
    "risk_level",
    "classification",
    "delegation_scope",
    "authorization_decision_id",
)
_TARGET_FIELDS = (
    "cross_validation_plan_id",
    "cross_validation_run_id",
    "provider_instance_id",
    "model_id",
    "mcp_server_id",
    "tool_id",
    "connector_id",
)


def _utc_iso(value: datetime) -> str:
    aware = require_aware(value, "lineage timestamp")
    return aware.astimezone(UTC).isoformat(timespec="microseconds").replace("+00:00", "Z")


def _canonical_scalar(value):
    if isinstance(value, datetime):
        return _utc_iso(value)
    if isinstance(value, UUID):
        return str(value)
    if isinstance(value, StrEnum):
        return value.value
    return value


def _canonical_json(values: tuple[tuple[str, object], ...]) -> bytes:
    payload = {key: _canonical_scalar(value) for key, value in values}
    try:
        return json.dumps(
            payload,
            ensure_ascii=False,
            separators=(",", ":"),
            sort_keys=False,
        ).encode("utf-8")
    except (TypeError, ValueError) as exc:
        raise LineageCanonicalizationError("metadata cannot be canonicalized") from exc


class DelegationLineageFacts(ExecutionModel):
    delegation_id: UUID
    tenant_id: UUID
    organization_id: UUID
    on_behalf_of_user_id: UUID
    service_actor_id: UUID
    agent_instance_id: UUID
    task_id: UUID
    resource_id: str = Field(min_length=1, max_length=200)
    resource_type: str = Field(min_length=1, max_length=100)
    action: str = Field(min_length=1, max_length=100)
    purpose: str = Field(min_length=1, max_length=100)
    risk_level: str = Field(min_length=1, max_length=50)
    classification: DataClassification
    delegation_scope: str = Field(pattern=r"^[a-z][a-z0-9_.-]{0,99}$")
    authorization_decision_id: UUID
    issued_at: datetime
    expires_at: datetime | None = None
    parent_delegation_id: UUID | None = None
    cross_validation_plan_id: UUID | None = None
    cross_validation_run_id: UUID | None = None
    provider_instance_id: str | None = Field(default=None, max_length=200)
    model_id: str | None = Field(default=None, max_length=200)
    mcp_server_id: str | None = Field(default=None, max_length=200)
    tool_id: str | None = Field(default=None, max_length=200)
    connector_id: str | None = Field(default=None, max_length=200)

    @field_validator("issued_at", "expires_at")
    @classmethod
    def aware(cls, value, info):
        return require_aware(value, info.field_name)


def canonicalize_delegation_lineage(
    facts: DelegationLineageFacts,
    *,
    canonicalization_version: LineageCanonicalizationVersion = (
        LineageCanonicalizationVersion.POLICYOS_LINEAGE_CANONICAL_V1
    ),
) -> bytes:
    if canonicalization_version is not LineageCanonicalizationVersion.POLICYOS_LINEAGE_CANONICAL_V1:
        raise LineageCanonicalizationError("unsupported lineage canonicalization version")
    return _canonical_json(tuple((field, getattr(facts, field)) for field in _LINEAGE_FIELD_ORDER))


class DelegationLineageDigest(ExecutionModel):
    digest_algorithm: LineageDigestAlgorithm
    digest_version: LineageDigestVersion
    canonicalization_version: LineageCanonicalizationVersion
    digest_value: str = Field(pattern=r"^[0-9a-f]{64}$")
    lineage_id: UUID
    parent_lineage_digest: str | None = Field(default=None, pattern=r"^[0-9a-f]{64}$")
    attestation_reference: str | None = Field(default=None, max_length=200)
    created_at: datetime

    @field_validator("created_at")
    @classmethod
    def aware(cls, value):
        return require_aware(value, "created_at")


def compute_delegation_lineage_digest(
    facts: DelegationLineageFacts,
    *,
    lineage_id: UUID,
    created_at: datetime,
    parent_lineage_digest: str | None = None,
    attestation_reference: str | None = None,
    digest_algorithm: LineageDigestAlgorithm = LineageDigestAlgorithm.SHA256,
    digest_version: LineageDigestVersion = LineageDigestVersion.V1,
    canonicalization_version: LineageCanonicalizationVersion = (
        LineageCanonicalizationVersion.POLICYOS_LINEAGE_CANONICAL_V1
    ),
) -> DelegationLineageDigest:
    if digest_algorithm is not LineageDigestAlgorithm.SHA256:
        raise LineageDigestError("unsupported lineage digest algorithm")
    if digest_version is not LineageDigestVersion.V1:
        raise LineageDigestError("unsupported lineage digest version")
    canonical = canonicalize_delegation_lineage(
        facts, canonicalization_version=canonicalization_version
    )
    return DelegationLineageDigest(
        digest_algorithm=digest_algorithm,
        digest_version=digest_version,
        canonicalization_version=canonicalization_version,
        digest_value=hashlib.sha256(canonical).hexdigest(),
        lineage_id=lineage_id,
        parent_lineage_digest=parent_lineage_digest,
        attestation_reference=attestation_reference,
        created_at=created_at,
    )


def verify_delegation_lineage_digest(
    facts: DelegationLineageFacts,
    digest: DelegationLineageDigest,
) -> None:
    expected = compute_delegation_lineage_digest(
        facts,
        lineage_id=digest.lineage_id,
        created_at=digest.created_at,
        parent_lineage_digest=digest.parent_lineage_digest,
        attestation_reference=digest.attestation_reference,
        digest_algorithm=digest.digest_algorithm,
        digest_version=digest.digest_version,
        canonicalization_version=digest.canonicalization_version,
    )
    if expected.digest_value != digest.digest_value:
        raise LineageDigestError("delegation lineage digest mismatch")


class DelegationLineageRecord(ExecutionModel):
    lineage_id: UUID
    facts: DelegationLineageFacts
    digest: DelegationLineageDigest
    parent_lineage_id: UUID | None = None
    lineage_stage: LineageStage
    created_at: datetime

    @field_validator("created_at")
    @classmethod
    def aware(cls, value):
        return require_aware(value, "created_at")

    @model_validator(mode="after")
    def internally_consistent(self):
        if self.lineage_id != self.digest.lineage_id:
            raise LineageDigestError("lineage record and digest identity mismatch")
        if (self.parent_lineage_id is None) != (self.digest.parent_lineage_digest is None):
            raise LineageContinuityError("parent lineage identity is incomplete")
        verify_delegation_lineage_digest(self.facts, self.digest)
        return self


def validate_lineage_continuity(
    upstream: DelegationLineageRecord,
    downstream: DelegationLineageRecord,
    *,
    require_adjacent_stage: bool = False,
) -> None:
    verify_delegation_lineage_digest(upstream.facts, upstream.digest)
    verify_delegation_lineage_digest(downstream.facts, downstream.digest)
    if downstream.parent_lineage_id != upstream.lineage_id:
        raise LineageContinuityError("downstream parent lineage identity mismatch")
    if downstream.digest.parent_lineage_digest != upstream.digest.digest_value:
        raise LineageContinuityError("downstream parent lineage digest mismatch")
    if any(
        getattr(upstream.facts, field) != getattr(downstream.facts, field)
        for field in _PROTECTED_FIELDS
    ):
        raise LineageContinuityError("protected delegation lineage changed")
    for field in _TARGET_FIELDS:
        upstream_value = getattr(upstream.facts, field)
        downstream_value = getattr(downstream.facts, field)
        if upstream_value is not None and downstream_value != upstream_value:
            raise LineageContinuityError("lineage target was substituted")
    upstream_stage = _STAGE_ORDER[upstream.lineage_stage]
    downstream_stage = _STAGE_ORDER[downstream.lineage_stage]
    if downstream_stage <= upstream_stage:
        raise LineageStageError("lineage stage did not progress")
    if require_adjacent_stage and downstream_stage != upstream_stage + 1:
        raise LineageStageError("mandatory lineage stage relationship was skipped")


class CrossValidationLineageRun(ExecutionModel):
    run_id: UUID
    agent_instance_id: UUID
    credential_grant_id: UUID
    root_lineage_id: UUID
    root_lineage_digest: str = Field(pattern=r"^[0-9a-f]{64}$")
    child_lineage: DelegationLineageRecord


def validate_cross_validation_lineage_set(
    root: DelegationLineageRecord,
    runs: tuple[CrossValidationLineageRun, ...],
    *,
    require_distinct_agents: bool = True,
    require_distinct_credentials: bool = True,
) -> None:
    if not runs:
        raise CrossValidationLineageError("cross-validation lineage is missing")
    run_ids = [run.run_id for run in runs]
    if len(run_ids) != len(set(run_ids)):
        raise CrossValidationLineageError("cross-validation run identity was reused")
    if require_distinct_agents:
        agent_ids = [run.agent_instance_id for run in runs]
        if len(agent_ids) != len(set(agent_ids)):
            raise CrossValidationLineageError("cross-validation agent identity was reused")
    if require_distinct_credentials:
        grant_ids = [run.credential_grant_id for run in runs]
        if len(grant_ids) != len(set(grant_ids)):
            raise CrossValidationLineageError("cross-validation credential grant was reused")
    protected_root = (
        root.facts.tenant_id,
        root.facts.organization_id,
        root.facts.on_behalf_of_user_id,
        root.facts.task_id,
        root.facts.resource_id,
        root.facts.action,
        root.facts.purpose,
        root.facts.risk_level,
        root.facts.classification,
        root.facts.delegation_scope,
        root.facts.authorization_decision_id,
    )
    for run in runs:
        verify_delegation_lineage_digest(run.child_lineage.facts, run.child_lineage.digest)
        if (
            run.root_lineage_id != root.lineage_id
            or run.root_lineage_digest != root.digest.digest_value
        ):
            raise CrossValidationLineageError("cross-validation root lineage mismatch")
        child = run.child_lineage.facts
        observed = (
            child.tenant_id,
            child.organization_id,
            child.on_behalf_of_user_id,
            child.task_id,
            child.resource_id,
            child.action,
            child.purpose,
            child.risk_level,
            child.classification,
            child.delegation_scope,
            child.authorization_decision_id,
        )
        if observed != protected_root:
            raise CrossValidationLineageError("cross-validation protected lineage changed")
        if run.child_lineage.parent_lineage_id != root.lineage_id:
            raise CrossValidationLineageError("cross-validation child parent is missing")
        if run.child_lineage.digest.parent_lineage_digest != root.digest.digest_value:
            raise CrossValidationLineageError("cross-validation child digest is discontinuous")
        if child.cross_validation_run_id != run.run_id:
            raise CrossValidationLineageError("cross-validation run lineage mismatch")
        if child.agent_instance_id != run.agent_instance_id:
            raise CrossValidationLineageError("cross-validation agent lineage mismatch")


class LineageAttestationReference(ExecutionModel):
    attestation_reference_id: UUID
    attestation_provider_id: str = Field(min_length=1, max_length=200)
    attestation_scheme: str = Field(pattern=r"^[a-z][a-z0-9_.-]{0,99}$")
    attestation_version: str = Field(min_length=1, max_length=100)
    subject_lineage_id: UUID
    subject_lineage_digest: str = Field(pattern=r"^[0-9a-f]{64}$")
    issued_at: datetime
    expires_at: datetime | None = None

    @field_validator("issued_at", "expires_at")
    @classmethod
    def aware(cls, value, info):
        return require_aware(value, info.field_name)

    @model_validator(mode="after")
    def lifetime(self):
        if self.expires_at is not None and self.expires_at <= self.issued_at:
            raise AttestationReferenceError("attestation reference expiry is invalid")
        return self
