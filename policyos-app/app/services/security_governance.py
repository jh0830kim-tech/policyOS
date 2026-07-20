"""Unified security audit and governed knowledge lifecycle services."""

import uuid
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import Protocol

from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.ai.privacy import DataClassification
from app.models.security_governance import LegalHold, ReclassificationRequest, UnifiedAuditEvent
from app.security.access import ClassificationPolicyError, KnowledgeAccessPolicyService

_FORBIDDEN_METADATA_KEYS = frozenset(
    {
        "prompt",
        "raw_prompt",
        "raw_document",
        "raw_provider_response",
        "raw_mcp_output",
        "api_key",
        "bearer_token",
        "password",
        "hidden_reasoning",
        "chain_of_thought",
    }
)


class GovernanceError(ValueError):
    """Safe lifecycle policy error."""


class CacheInvalidator(Protocol):
    async def invalidate(self, organization_id: uuid.UUID, resource_id: uuid.UUID) -> None: ...


class NoOpCacheInvalidator:
    async def invalidate(self, organization_id: uuid.UUID, resource_id: uuid.UUID) -> None:
        return None


@dataclass(frozen=True)
class AuditEventInput:
    organization_id: uuid.UUID
    event_type: str
    action: str
    decision: str
    reason_code: str
    classification: str
    started_at: datetime
    completed_at: datetime
    success: bool
    correlation_id: str
    user_id: uuid.UUID | None = None
    membership_id: uuid.UUID | None = None
    task_id: uuid.UUID | None = None
    work_package_id: uuid.UUID | None = None
    agent_run_id: uuid.UUID | None = None
    source_id: uuid.UUID | None = None
    document_id: uuid.UUID | None = None
    document_version_id: uuid.UUID | None = None
    chunk_id: uuid.UUID | None = None
    artifact_id: uuid.UUID | None = None
    server_name: str | None = None
    tool_name: str | None = None
    external_transmission: bool = False
    redaction_applied: bool = False
    finding_count: int = 0
    error_code: str | None = None
    metadata: dict[str, object] | None = None


class UnifiedAuditRepository:
    def __init__(self, db: AsyncSession) -> None:
        self.db = db

    async def record(self, item: AuditEventInput) -> UnifiedAuditEvent:
        metadata = item.metadata or {}
        if _FORBIDDEN_METADATA_KEYS.intersection(key.lower() for key in metadata):
            raise GovernanceError("Sensitive content is not permitted in audit metadata")
        latency_ms = max(0, int((item.completed_at - item.started_at).total_seconds() * 1000))
        event = UnifiedAuditEvent(
            **{key: value for key, value in vars(item).items() if key != "metadata"},
            latency_ms=latency_ms,
            metadata_json=metadata,
        )
        self.db.add(event)
        return event

    async def query(
        self, organization_id: uuid.UUID, *, event_type: str | None = None, limit: int = 100
    ) -> list[UnifiedAuditEvent]:
        statement = select(UnifiedAuditEvent).where(
            UnifiedAuditEvent.organization_id == organization_id
        )
        if event_type:
            statement = statement.where(UnifiedAuditEvent.event_type == event_type)
        result = await self.db.scalars(
            statement.order_by(UnifiedAuditEvent.started_at.desc()).limit(min(max(limit, 1), 500))
        )
        return list(result)


class LegalHoldService:
    def __init__(self, db: AsyncSession) -> None:
        self.db = db

    async def place(
        self,
        *,
        organization_id: uuid.UUID,
        target_type: str,
        target_id: uuid.UUID,
        reason_code: str,
        user_id: uuid.UUID,
        authorized: bool,
        now: datetime | None = None,
    ) -> LegalHold:
        if not authorized:
            raise GovernanceError("legal_hold_permission_denied")
        hold = LegalHold(
            organization_id=organization_id,
            target_type=target_type,
            target_id=target_id,
            reason_code=reason_code,
            placed_by=user_id,
            placed_at=now or datetime.now(UTC),
            active=True,
            metadata_json={},
        )
        self.db.add(hold)
        return hold

    async def is_held(
        self, organization_id: uuid.UUID, target_type: str, target_id: uuid.UUID
    ) -> bool:
        statement = select(LegalHold.id).where(
            LegalHold.organization_id == organization_id,
            LegalHold.target_type == target_type,
            LegalHold.target_id == target_id,
            LegalHold.active.is_(True),
        )
        return (await self.db.scalar(statement)) is not None

    def release(self, hold: LegalHold, *, user_id: uuid.UUID, authorized: bool) -> None:
        if not authorized:
            raise GovernanceError("legal_hold_permission_denied")
        hold.active = False
        hold.released_by = user_id
        hold.released_at = datetime.now(UTC)


@dataclass(frozen=True)
class RetentionPolicy:
    audit_days: int
    document_days: int
    chunk_days: int
    embedding_days: int
    mcp_cache_days: int


@dataclass(frozen=True)
class RetentionCandidate:
    resource_type: str
    resource_id: uuid.UUID
    created_at: datetime
    current_version: bool = False
    approved_artifact: bool = False
    legal_hold: bool = False


@dataclass(frozen=True)
class RetentionPlan:
    selected: tuple[RetentionCandidate, ...]
    excluded: tuple[RetentionCandidate, ...]
    dry_run: bool


class KnowledgeRetentionService:
    _ORDER = {"embedding": 0, "chunk": 1, "document_version": 2, "document": 3, "audit": 4}

    def plan(
        self,
        candidates: list[RetentionCandidate],
        policy: RetentionPolicy,
        *,
        now: datetime | None = None,
        dry_run: bool = True,
    ) -> RetentionPlan:
        current = now or datetime.now(UTC)
        days = {
            "audit": policy.audit_days,
            "document": policy.document_days,
            "document_version": policy.document_days,
            "chunk": policy.chunk_days,
            "embedding": policy.embedding_days,
            "mcp_cache": policy.mcp_cache_days,
        }
        selected: list[RetentionCandidate] = []
        excluded: list[RetentionCandidate] = []
        for candidate in candidates:
            cutoff = current - timedelta(days=days[candidate.resource_type])
            protected = (
                candidate.legal_hold or candidate.current_version or candidate.approved_artifact
            )
            (excluded if protected or candidate.created_at >= cutoff else selected).append(
                candidate
            )
        selected.sort(key=lambda item: self._ORDER.get(item.resource_type, 99))
        return RetentionPlan(tuple(selected), tuple(excluded), dry_run)

    def authorize_execution(self, plan: RetentionPlan, *, approval_reference: str | None) -> None:
        if plan.dry_run:
            raise GovernanceError("dry_run_cannot_execute")
        if not approval_reference:
            raise GovernanceError("retention_approval_required")

    async def purge_expired_audit(
        self,
        db: AsyncSession,
        *,
        organization_id: uuid.UUID,
        cutoff: datetime,
        approval_reference: str | None,
    ) -> None:
        if not approval_reference:
            raise GovernanceError("retention_approval_required")
        held_ids = select(LegalHold.target_id).where(
            LegalHold.organization_id == organization_id,
            LegalHold.target_type == "audit",
            LegalHold.active.is_(True),
        )
        await db.execute(
            delete(UnifiedAuditEvent).where(
                UnifiedAuditEvent.organization_id == organization_id,
                UnifiedAuditEvent.started_at < cutoff,
                UnifiedAuditEvent.id.not_in(held_ids),
            )
        )


class ReclassificationService:
    def __init__(
        self, db: AsyncSession, *, cache_invalidator: CacheInvalidator | None = None
    ) -> None:
        self.db = db
        self.cache_invalidator = cache_invalidator or NoOpCacheInvalidator()
        self.policy = KnowledgeAccessPolicyService()

    async def request(
        self,
        *,
        organization_id: uuid.UUID,
        document_id: uuid.UUID,
        current: DataClassification,
        target: DataClassification,
        requested_by: uuid.UUID,
        reason_code: str,
        is_admin: bool,
        approval_reference: str | None,
        dlp_clear: bool,
        finding_count: int = 0,
    ) -> ReclassificationRequest:
        self.policy.authorize_reclassification(
            current,
            target,
            is_admin=is_admin,
            approved=bool(approval_reference),
            dlp_clear=dlp_clear,
        )
        item = ReclassificationRequest(
            organization_id=organization_id,
            document_id=document_id,
            current_classification=current.value,
            requested_classification=target.value,
            status="approved" if approval_reference else "requested",
            requested_by=requested_by,
            approval_reference=approval_reference,
            reason_code=reason_code,
            finding_count=finding_count,
        )
        self.db.add(item)
        return item

    async def apply(self, request: ReclassificationRequest, resources: list[object]) -> None:
        if request.status != "approved":
            raise ClassificationPolicyError("Reclassification has not been approved")
        for resource in resources:
            if getattr(resource, "organization_id", None) != request.organization_id:
                raise GovernanceError("cross_organization_reclassification_denied")
            resource.classification = request.requested_classification
        request.status = "applied"
        await self.cache_invalidator.invalidate(request.organization_id, request.document_id)


class RetrievalSecurityService:
    """Final query-boundary filter; debug flags never bypass policy checks."""

    def __init__(self, policy: KnowledgeAccessPolicyService | None = None) -> None:
        self.policy = policy or KnowledgeAccessPolicyService()

    def filter(
        self, context, results: list[object], *, restricted_excerpt_max_chars: int
    ) -> list[object]:
        self.policy.require(context)
        visible = []
        for item in results:
            if getattr(item, "organization_id", None) != context.organization_id:
                continue
            if getattr(item, "status", "active") != "active":
                continue
            if getattr(item, "revoked", False) or not getattr(item, "source_access_allowed", True):
                continue
            if context.data_classification is DataClassification.RESTRICTED and hasattr(
                item, "content"
            ):
                item.content = item.content[:restricted_excerpt_max_chars]
            visible.append(item)
        return visible


class ArchiveDeletionService:
    """State-transition boundary; physical purge is a separate approved operation."""

    def archive(
        self, resource: object, *, actor_id: uuid.UUID, now: datetime | None = None
    ) -> None:
        resource.status = "archived"
        if hasattr(resource, "archived_at"):
            resource.archived_at = now or datetime.now(UTC)

    def restore(self, resource: object) -> None:
        if getattr(resource, "deleted_at", None):
            raise GovernanceError("deleted_resource_cannot_restore")
        resource.status = "active"
        if hasattr(resource, "archived_at"):
            resource.archived_at = None

    def soft_delete(
        self,
        resource: object,
        *,
        actor_id: uuid.UUID,
        reason_code: str,
        legal_hold: bool,
        approved_artifact: bool,
        now: datetime | None = None,
    ) -> None:
        if legal_hold:
            raise GovernanceError("legal_hold_blocks_deletion")
        if approved_artifact:
            raise GovernanceError("approved_artifact_blocks_deletion")
        resource.status = "archived"
        for name, value in (
            ("deleted_at", now or datetime.now(UTC)),
            ("deleted_by", actor_id),
            ("deletion_reason_code", reason_code),
        ):
            if hasattr(resource, name):
                setattr(resource, name, value)

    def authorize_purge(
        self, *, legal_hold: bool, approval_reference: str | None, dry_run: bool
    ) -> None:
        if legal_hold:
            raise GovernanceError("legal_hold_blocks_deletion")
        if dry_run:
            raise GovernanceError("dry_run_cannot_execute")
        if not approval_reference:
            raise GovernanceError("purge_approval_required")
