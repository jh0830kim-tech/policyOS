# Database Strategy

## Primary database
PostgreSQL is the system of record.

## ORM
SQLAlchemy 2.x async.

## Migration
Alembic migrations are required for schema changes.

## Conventions
- Primary keys: UUID preferred for externally exposed entities.
- Timestamps: UTC, timezone-aware.
- Soft deletion: use only where audit or recovery requirements justify it.
- Organization scope: explicit foreign key for organization-owned records.
- Sensitive fields: classify and protect according to security policy.

## Transaction rule
A business operation that must succeed or fail as a unit must run within one explicit transaction boundary.
