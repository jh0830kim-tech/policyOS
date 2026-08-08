from app.db.base import Base
from app.models import (
    AgentRunRecord,
    AITaskRecord,
    ArtifactRecord,
    AuditEvent,
    Membership,
    Organization,
    Permission,
    Role,
    TenantOrganizationBinding,
    User,
    WorkPackageRecord,
)


def test_foundation_tables_are_registered() -> None:
    expected = {
        "organizations",
        "users",
        "memberships",
        "roles",
        "permissions",
        "role_permissions",
        "membership_roles",
        "audit_events",
        "policy_candidates",
        "ai_tasks",
        "agent_runs",
        "ai_work_packages",
        "ai_artifacts",
    }
    assert expected.issubset(Base.metadata.tables)


def test_identity_model_table_names() -> None:
    assert Organization.__tablename__ == "organizations"
    assert User.__tablename__ == "users"
    assert Membership.__tablename__ == "memberships"
    assert Role.__tablename__ == "roles"
    assert Permission.__tablename__ == "permissions"
    assert AuditEvent.__tablename__ == "audit_events"
    assert AITaskRecord.__tablename__ == "ai_tasks"
    assert AgentRunRecord.__tablename__ == "agent_runs"
    assert WorkPackageRecord.__tablename__ == "ai_work_packages"
    assert ArtifactRecord.__tablename__ == "ai_artifacts"


def test_membership_has_unique_org_user_constraint() -> None:
    constraint_names = {constraint.name for constraint in Membership.__table__.constraints}
    assert "uq_memberships_org_user" in constraint_names


def test_tenant_organization_binding_schema_is_fail_closed() -> None:
    table = TenantOrganizationBinding.__table__
    assert table.name == "tenant_organization_bindings"
    assert set(table.columns) == {
        table.c.id,
        table.c.organization_id,
        table.c.runtime_tenant_id,
        table.c.status,
        table.c.classification_ceiling,
        table.c.provisioning_reference,
        table.c.provisioned_by_user_id,
        table.c.created_at,
        table.c.status_changed_at,
    }
    assert all(not column.nullable for column in table.columns)
    assert table.c.id.default is None
    assert table.c.runtime_tenant_id.default is None
    assert table.c.created_at.default is None
    assert table.c.status_changed_at.default is None

    constraint_names = {constraint.name for constraint in table.constraints}
    assert {
        "uq_tenant_org_binding_organization",
        "uq_tenant_org_binding_tenant",
        "ck_tenant_org_binding_status",
        "ck_tenant_org_binding_classification",
        "ck_tenant_org_binding_provisioning_reference",
    }.issubset(constraint_names)

    foreign_keys = {
        (foreign_key.parent.name, foreign_key.target_fullname, foreign_key.ondelete)
        for foreign_key in table.foreign_keys
    }
    assert foreign_keys == {
        ("organization_id", "organizations.id", "RESTRICT"),
        ("provisioned_by_user_id", "users.id", "RESTRICT"),
    }


def test_tenant_organization_binding_has_no_sensitive_payload_columns() -> None:
    column_names = set(TenantOrganizationBinding.__table__.columns)
    assert not column_names.intersection(
        {"raw_token", "token", "secret", "provider_body", "payload", "metadata"}
    )


def test_runtime_permission_grant_event_is_registered_append_only_evidence() -> None:
    table = Base.metadata.tables["runtime_permission_grant_events"]
    assert table.c.event_id.primary_key
    constraint_names = {item.name for item in table.constraints}
    assert "uq_runtime_grant_event_request" in constraint_names
    assert "uq_runtime_grant_event_receipt" in constraint_names
    assert "payload" not in table.c
    assert "metadata" not in table.c
