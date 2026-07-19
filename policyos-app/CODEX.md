# Codex Working Agreement for PolicyOS

## Mission
Build PolicyOS incrementally as a secure, auditable AI policy-office platform for a Korean local council office.

## Current MVP scope
1. FastAPI service
2. PostgreSQL persistence
3. Redis-ready infrastructure
4. Policy Candidate CRUD
5. Health endpoint and tests

## Engineering rules
- Python 3.12, full type hints, async SQLAlchemy.
- Every write action needs validation, authorization hooks, and audit-event design.
- Never fabricate policy facts or citations.
- Store AI outputs separately from verified facts.
- Add tests for each endpoint and migration.
- Keep modules small and domain-oriented.
- Do not expose secrets or personal constituent data.

## Next implementation sequence
1. Alembic migrations and seed data.
2. Organization, membership, RBAC, audit events.
3. Policy candidate screening and assessment.
4. Strategic goals, portfolio, agenda, dependencies.
5. Missions, tasks, milestones, RACI and delivery room.
6. Knowledge graph and evidence registry.
7. Jamie orchestration and specialist agents.
8. React/Next.js dashboard.

## Definition of done per change
- Code passes Ruff and Pytest.
- API schema is documented.
- DB changes include migration.
- Security and audit impacts are noted.
- README is updated when startup steps change.
