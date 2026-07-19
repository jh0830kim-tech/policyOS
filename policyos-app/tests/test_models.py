from app.db.base import Base
from app.models import AuditEvent, Membership, Organization, Permission, Role, User


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
    }
    assert expected.issubset(Base.metadata.tables)


def test_identity_model_table_names() -> None:
    assert Organization.__tablename__ == "organizations"
    assert User.__tablename__ == "users"
    assert Membership.__tablename__ == "memberships"
    assert Role.__tablename__ == "roles"
    assert Permission.__tablename__ == "permissions"
    assert AuditEvent.__tablename__ == "audit_events"


def test_membership_has_unique_org_user_constraint() -> None:
    constraint_names = {constraint.name for constraint in Membership.__table__.constraints}
    assert "uq_memberships_org_user" in constraint_names
