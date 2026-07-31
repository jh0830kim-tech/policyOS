"""Pure legacy/vNext contract-test and migration gates."""

from datetime import datetime
from enum import StrEnum
from uuid import UUID

from pydantic import field_validator, model_validator

from app.execution.domain import ExecutionModel
from app.execution.validation import require_aware
from app.mcp_governance.domain import (
    BoundedId,
    McpCompatibilityReason,
    McpCompatibilityStatus,
    canonical,
)
from app.mcp_governance.registry import McpRegistrySnapshot

KOREAN_LAW_LEGACY_OPERATIONS = (
    "compare_versions",
    "explore_legal_chain",
    "get_article_history",
    "get_legal_resource",
    "search_administrative_rules",
    "search_cases",
    "search_laws",
    "search_legal_interpretations",
    "search_local_ordinances",
)


class McpDeploymentTrack(StrEnum):
    LEGACY = "legacy"
    VNEXT = "vnext"
    SHADOW = "shadow"
    CANARY = "canary"
    CURRENT = "current"
    DEPRECATED = "deprecated"
    RETIRED = "retired"


class McpMigrationStatus(StrEnum):
    DISCOVERED = "discovered"
    CONTRACT_TESTING = "contract_testing"
    CONTRACT_TEST_FAILED = "contract_test_failed"
    SHADOW_VALIDATED = "shadow_validated"
    APPROVED_FOR_CANARY = "approved_for_canary"
    CANARY = "canary"
    APPROVED_FOR_CURRENT = "approved_for_current"
    CURRENT = "current"
    ROLLBACK_REQUIRED = "rollback_required"
    DEPRECATED = "deprecated"
    RETIRED = "retired"


class McpMigrationCandidate(ExecutionModel):
    migration_id: UUID
    service_alias: BoundedId
    legacy_server_id: BoundedId
    candidate_server_id: BoundedId
    legacy_contract_revision: BoundedId
    candidate_contract_revision: BoundedId
    required_contract_test_suite_id: BoundedId
    migration_status: McpMigrationStatus
    created_at: datetime

    @field_validator("created_at")
    @classmethod
    def aware(cls, v):
        return require_aware(v, "created_at")

    @model_validator(mode="after")
    def distinct(self):
        if self.legacy_server_id == self.candidate_server_id:
            raise ValueError("candidate server must have a distinct identity")
        return self


class McpContractTestResult(ExecutionModel):
    contract_test_result_id: UUID
    suite_id: BoundedId
    migration_id: UUID
    legacy_server_id: BoundedId
    candidate_server_id: BoundedId
    legacy_contract_revision: BoundedId
    candidate_contract_revision: BoundedId
    tested_operations: tuple[BoundedId, ...]
    passed_operations: tuple[BoundedId, ...]
    failed_operations: tuple[BoundedId, ...]
    compatibility_status: McpCompatibilityStatus
    reason_codes: tuple[McpCompatibilityReason, ...] = ()
    tested_at: datetime

    @field_validator("tested_operations", "passed_operations", "failed_operations")
    @classmethod
    def operations(cls, v, info):
        return canonical(v, info.field_name)

    @field_validator("reason_codes")
    @classmethod
    def reasons(cls, v):
        return canonical(v, "reason codes") if v else v

    @field_validator("tested_at")
    @classmethod
    def aware(cls, v):
        return require_aware(v, "tested_at")

    @model_validator(mode="after")
    def partition(self):
        if set(self.passed_operations) & set(self.failed_operations) or set(
            self.passed_operations
        ) | set(self.failed_operations) != set(self.tested_operations):
            raise ValueError("operation results must exactly partition tested operations")
        return self


class McpMigrationGateDecision(ExecutionModel):
    migration_gate_decision_id: UUID
    migration_id: UUID
    from_status: McpMigrationStatus
    requested_status: McpMigrationStatus
    allowed: bool
    reason_codes: tuple[McpCompatibilityReason, ...]
    alias_switch_authorized: bool = False
    decided_at: datetime

    @field_validator("reason_codes")
    @classmethod
    def reasons(cls, v):
        return canonical(v, "reason codes")

    @field_validator("decided_at")
    @classmethod
    def aware(cls, v):
        return require_aware(v, "decided_at")


def evaluate_mcp_migration_gate(
    candidate: McpMigrationCandidate,
    registry: McpRegistrySnapshot,
    contract_test: McpContractTestResult | None,
    *,
    requested_status: McpMigrationStatus,
    required_operations: tuple[str, ...],
    explicit_approval: bool,
    successful_canary: bool,
    decision_id: UUID,
    decided_at: datetime,
) -> McpMigrationGateDecision:
    reasons = []
    try:
        legacy = registry.server(candidate.legacy_server_id)
        registry.server(candidate.candidate_server_id)
        if not legacy.enabled or legacy.compatibility_status not in {
            McpCompatibilityStatus.COMPATIBLE,
            McpCompatibilityStatus.DEGRADED,
        }:
            reasons.append(McpCompatibilityReason.SECURITY_POLICY_REJECTED)
    except Exception:
        reasons.append(McpCompatibilityReason.SECURITY_POLICY_REJECTED)
    if contract_test is None:
        reasons.append(McpCompatibilityReason.CONTRACT_TEST_FAILED)
    else:
        lineage = (
            contract_test.migration_id,
            contract_test.suite_id,
            contract_test.legacy_server_id,
            contract_test.candidate_server_id,
            contract_test.legacy_contract_revision,
            contract_test.candidate_contract_revision,
        )
        expected = (
            candidate.migration_id,
            candidate.required_contract_test_suite_id,
            candidate.legacy_server_id,
            candidate.candidate_server_id,
            candidate.legacy_contract_revision,
            candidate.candidate_contract_revision,
        )
        if (
            lineage != expected
            or not set(required_operations) <= set(contract_test.passed_operations)
            or contract_test.failed_operations
            or contract_test.compatibility_status is not McpCompatibilityStatus.COMPATIBLE
        ):
            reasons.append(McpCompatibilityReason.CONTRACT_TEST_FAILED)
    if (
        requested_status in {McpMigrationStatus.CANARY, McpMigrationStatus.CURRENT}
        and not explicit_approval
    ):
        reasons.append(McpCompatibilityReason.MANUAL_APPROVAL_REQUIRED)
    if requested_status is McpMigrationStatus.CURRENT and not successful_canary:
        reasons.append(McpCompatibilityReason.SECURITY_POLICY_REJECTED)
    if reasons:
        allowed = False
    elif requested_status is McpMigrationStatus.SHADOW_VALIDATED:
        allowed = True
    elif requested_status is McpMigrationStatus.CANARY:
        allowed = candidate.migration_status in {
            McpMigrationStatus.SHADOW_VALIDATED,
            McpMigrationStatus.APPROVED_FOR_CANARY,
        }
    elif requested_status is McpMigrationStatus.CURRENT:
        allowed = candidate.migration_status in {
            McpMigrationStatus.CANARY,
            McpMigrationStatus.APPROVED_FOR_CURRENT,
        }
    else:
        allowed = False
    if not allowed and not reasons:
        reasons = [McpCompatibilityReason.SECURITY_POLICY_REJECTED]
    return McpMigrationGateDecision(
        migration_gate_decision_id=decision_id,
        migration_id=candidate.migration_id,
        from_status=candidate.migration_status,
        requested_status=requested_status,
        allowed=allowed,
        reason_codes=tuple(sorted(set(reasons), key=str)),
        alias_switch_authorized=False,
        decided_at=decided_at,
    )
