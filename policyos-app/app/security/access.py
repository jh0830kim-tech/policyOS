"""Organization, permission, classification and transmission access policy."""

from enum import StrEnum
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from app.ai.privacy import DataClassification


class SecurityModel(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)


class KnowledgeAction(StrEnum):
    INGEST = "ingest"
    READ = "read"
    SEARCH = "search"
    EMBED = "embed"
    EXPORT = "export"
    TRANSMIT_EXTERNAL = "transmit_external"
    ARCHIVE = "archive"
    DELETE = "delete"
    RECLASSIFY = "reclassify"
    APPROVE = "approve"
    MANAGE_SOURCE = "manage_source"
    EXECUTE_MCP = "execute_mcp"


class KnowledgeAccessContext(SecurityModel):
    user_id: UUID
    organization_id: UUID
    membership_id: UUID
    permissions: frozenset[str]
    source_id: UUID | None = None
    document_id: UUID | None = None
    document_version_id: UUID | None = None
    chunk_id: UUID | None = None
    data_classification: DataClassification
    action: KnowledgeAction
    purpose: str = Field(max_length=500)
    task_id: UUID | None = None
    work_package_id: UUID | None = None
    request_id: UUID
    correlation_id: str = Field(max_length=200)
    external_transmission: bool = False
    human_approval_reference: str | None = None
    membership_active: bool = True
    source_access_allowed: bool = True
    resource_revoked: bool = False
    confidential_allowed: bool = False


class KnowledgeAccessDecision(SecurityModel):
    allowed: bool
    decision: str
    reason_code: str
    required_permission: str


class KnowledgeAccessRule(SecurityModel):
    action: KnowledgeAction
    permission: str
    requires_approval: bool = False


class KnowledgePermissionError(PermissionError):
    pass


class ClassificationPolicyError(PermissionError):
    pass


_RULES = {
    KnowledgeAction.INGEST: "knowledge.ingest",
    KnowledgeAction.READ: "knowledge.read",
    KnowledgeAction.SEARCH: "knowledge.read",
    KnowledgeAction.EMBED: "knowledge.manage",
    KnowledgeAction.EXPORT: "knowledge.export",
    KnowledgeAction.TRANSMIT_EXTERNAL: "knowledge.transmit",
    KnowledgeAction.ARCHIVE: "knowledge.manage",
    KnowledgeAction.DELETE: "knowledge.delete",
    KnowledgeAction.RECLASSIFY: "knowledge.reclassify",
    KnowledgeAction.APPROVE: "knowledge.approve",
    KnowledgeAction.MANAGE_SOURCE: "knowledge.manage",
    KnowledgeAction.EXECUTE_MCP: "mcp.execute",
}
_ORDER = {
    DataClassification.PUBLIC: 0,
    DataClassification.INTERNAL: 1,
    DataClassification.CONFIDENTIAL: 2,
    DataClassification.RESTRICTED: 3,
}


class KnowledgeAccessPolicyService:
    def decide(self, context: KnowledgeAccessContext) -> KnowledgeAccessDecision:
        permission = _RULES[context.action]
        if not context.membership_active:
            return KnowledgeAccessDecision(
                allowed=False,
                decision="deny",
                reason_code="inactive_membership",
                required_permission=permission,
            )
        if context.resource_revoked or not context.source_access_allowed:
            return KnowledgeAccessDecision(
                allowed=False,
                decision="deny",
                reason_code="access_revoked",
                required_permission=permission,
            )
        if permission not in context.permissions:
            return KnowledgeAccessDecision(
                allowed=False,
                decision="deny",
                reason_code="missing_permission",
                required_permission=permission,
            )
        if (
            context.external_transmission
            and context.data_classification is DataClassification.RESTRICTED
        ):
            return KnowledgeAccessDecision(
                allowed=False,
                decision="deny",
                reason_code="restricted_external_block",
                required_permission=permission,
            )
        if (
            context.data_classification is DataClassification.CONFIDENTIAL
            and not context.confidential_allowed
        ):
            return KnowledgeAccessDecision(
                allowed=False,
                decision="deny",
                reason_code="confidential_policy",
                required_permission=permission,
            )
        if (
            context.action
            in {KnowledgeAction.DELETE, KnowledgeAction.EXPORT, KnowledgeAction.RECLASSIFY}
            and not context.human_approval_reference
        ):
            return KnowledgeAccessDecision(
                allowed=False,
                decision="deny",
                reason_code="approval_required",
                required_permission=permission,
            )
        return KnowledgeAccessDecision(
            allowed=True,
            decision="allow",
            reason_code="policy_allow",
            required_permission=permission,
        )

    def require(self, context: KnowledgeAccessContext) -> KnowledgeAccessDecision:
        decision = self.decide(context)
        if not decision.allowed:
            raise KnowledgePermissionError(decision.reason_code)
        return decision

    def validate_inheritance(self, parent: DataClassification, child: DataClassification) -> None:
        if _ORDER[child] < _ORDER[parent]:
            raise ClassificationPolicyError("Child classification cannot be lower than parent")

    def authorize_reclassification(
        self,
        current: DataClassification,
        target: DataClassification,
        *,
        is_admin: bool,
        approved: bool,
        dlp_clear: bool,
    ) -> None:
        if _ORDER[target] < _ORDER[current] and not (is_admin and approved and dlp_clear):
            raise ClassificationPolicyError(
                "Classification downgrade requires approved administrative review"
            )


class SourceAccessPolicy(KnowledgeAccessPolicyService):
    pass


class RetrievalAccessPolicy(KnowledgeAccessPolicyService):
    pass
