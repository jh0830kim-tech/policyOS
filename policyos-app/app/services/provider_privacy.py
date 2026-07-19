"""Persistence and organization-scoped retention for provider metadata."""

import uuid
from datetime import UTC, datetime, timedelta

from sqlalchemy import delete, or_, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.ai.privacy import ProviderAuditMetadata
from app.models.ai_execution import AgentRunRecord
from app.models.provider_audit import ProviderAuditRecord


class ProviderAuditRepository:
    def __init__(self, db: AsyncSession) -> None:
        self.db = db

    async def record(self, metadata: ProviderAuditMetadata) -> None:
        self.db.add(
            ProviderAuditRecord(
                provider=metadata.provider,
                model=metadata.model,
                organization_id=metadata.organization_id,
                user_id=metadata.user_id,
                task_id=metadata.task_id,
                data_classification=metadata.data_classification.value,
                redaction_applied=metadata.redaction_applied,
                redacted_item_count=metadata.redacted_item_count,
                store_enabled=metadata.store_enabled,
                transmitted_at=metadata.transmitted_at,
                success=metadata.success,
                policy_decision=metadata.policy_decision.value,
                error_code=metadata.error_code,
            )
        )


class AIRetentionService:
    """Manual cleanup boundary; artifact retention remains owned by ArtifactRepository."""

    def __init__(self, db: AsyncSession) -> None:
        self.db = db

    async def cleanup_expired_metadata(
        self,
        *,
        organization_id: uuid.UUID,
        provider_audit_retention_days: int,
        usage_retention_days: int,
        now: datetime | None = None,
    ) -> None:
        current = now or datetime.now(UTC)
        audit_cutoff = current - timedelta(days=provider_audit_retention_days)
        usage_cutoff = current - timedelta(days=usage_retention_days)
        await self.db.execute(
            delete(ProviderAuditRecord).where(
                ProviderAuditRecord.organization_id == organization_id,
                ProviderAuditRecord.transmitted_at < audit_cutoff,
            )
        )
        await self.db.execute(
            update(AgentRunRecord)
            .where(
                AgentRunRecord.organization_id == organization_id,
                or_(
                    AgentRunRecord.finished_at < usage_cutoff,
                    (
                        AgentRunRecord.finished_at.is_(None)
                        & (AgentRunRecord.started_at < usage_cutoff)
                    ),
                ),
            )
            .values(
                provider_response_id=None,
                input_tokens=None,
                output_tokens=None,
                total_tokens=None,
                cached_input_tokens=None,
                latency_ms=None,
                retry_count=0,
                estimated_cost=None,
            )
        )
        await self.db.commit()
