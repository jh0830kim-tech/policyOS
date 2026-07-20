# Product Roadmap

## Sprint 0 ??Governance and documentation
- Constitution
- Architecture baseline
- Development rules
- Product and AI Office specifications

## Sprint 1 ??Foundation ??Completed
- FastAPI application
- Async SQLAlchemy
- Alembic
- Test and lint setup
- Packaging and repository hygiene

## Sprint 2 ??Authentication and identity ??Completed
- Password hashing
- JWT access tokens
- Login endpoint
- Current-user dependency
- Organization membership validation
- RBAC authorization
- Tests and audit hooks

## Sprint 3 ??AI Office Core
- Agent registry
- Task routing
- Chief Secretary orchestration
- Tool and permission boundaries
- Agent execution records

## Sprint 4 ??Knowledge and RAG
- Document ingestion
- Chunking and metadata
- Retrieval
- Source citation
- Knowledge permissions

## Sprint 5 ??Policy workflow
- Policy candidates
- Research briefs
- legal, budget, and statistics review
- Approval workflow
- Official document export

## Sprint 6 ??Frontend
- React dashboard
- Workspace
- Task inbox
- Agent activity
- Review and approval screens

## Sprint 7 ??Deployment and operations
- Docker
- CI/CD
- Monitoring
- Backup and restore
- Security hardening

## Release gates
No sprint is complete without:
- acceptance criteria met
- tests passing
- lint passing
- documentation updated
- security impact reviewed
### Sprint 3 implementation status
Agent/model contracts, registries, Policy Research and Legal Review agents, rules-based orchestration, execution records, and organization-scoped task APIs are implemented. Live providers, RAG, queues, streaming, and automatic publication remain deferred.
### Sprint 4 implementation status
Six operational agents, four deterministic work-package workflows, governed artifact persistence/review, RBAC APIs, and network-free end-to-end coverage are implemented. Sprint 5 must add a production OpenAI adapter, operational timeout/retry policy, approved prompt deployment, and observability before live model use.

## Sprint 6 v0.4 release candidate

The governed Knowledge Platform release candidate is covered by a synthetic, network-free E2E flow from login and organization RBAC through combined internal RAG/fake MCP routing, cited evidence merge, conflict/gap and confidence assessment, eight-agent Chief Secretary orchestration, reviewable Work Package/artifact persistence, and safe API output. All fixture facts are explicitly fictional. Default CI forbids real OpenAI, remote MCP, and subprocess MCP calls.

Release operation requires Alembic head `20260720_0013`, reviewed environment settings, backup/rollback, retention dry-run, legal-hold protection, privacy incident handling, and provider/MCP outage procedures. See `RELEASE_NOTES_v0.4.md` and `RUNBOOK.md`. Production pgvector/ANN, real government connectors, workers, Redis coordination, scheduled cleanup, SIEM integrations, and live staging verification remain deferred.