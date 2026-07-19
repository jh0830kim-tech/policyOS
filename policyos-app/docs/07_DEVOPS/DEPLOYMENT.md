# Deployment

Environments:
- local
- test
- staging
- production

Each environment must have separate credentials and databases. Production deployment requires migration review, rollback plan, health verification, and release notes.
## AI provider release and rollback

Sprint 5 deployments must apply Alembic through revision `20260720_0006`, validate the network-free smoke suite, and enable OpenAI only after privacy and secret-management approval. During rollback, first switch `AI_PROVIDER=disabled`, drain in-flight work, roll back application instances, and downgrade additive migrations only when operationally necessary and after metadata archival. The full checklist and incident procedures are in `RELEASE_NOTES_v0.3.md` and `RUNBOOK.md`.
