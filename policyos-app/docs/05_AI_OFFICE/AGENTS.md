# Agent Catalog

## Chief Secretary AI
Routes work, resolves dependencies, consolidates outputs, and manages review state.

## Policy Research AI
Builds issue briefs, compares cases, identifies policy options, and lists evidence gaps.

## Legal Review AI
Reviews legal authority, conflicts, procedural risks, and areas requiring counsel.

## Budget Analysis AI
Estimates cost categories, fiscal impact, funding sources, and budget risks.

## Statistics AI
Validates data, computes indicators, explains methodology, and prepares chart-ready outputs.

## Press & PR AI
Creates source-grounded press releases, media Q&A, and communication plans.

## Speech Writer AI
Produces speeches and remarks aligned with audience, policy, and verified facts.

## SNS Manager AI
Creates channel-specific drafts and publishing calendars; publishing requires authorization.

## PPT Designer AI
Converts approved content into slide structures, visual hierarchy, and speaker notes.

## Meeting Assistant AI
Prepares agendas, captures decisions, assigns follow-ups, and preserves meeting records.

## Citizen Communication AI
Classifies constituent requests, drafts respectful replies, and routes cases to staff.
## Sprint 4 implementation notes
Budget separates cost categories, estimates, assumptions, scenarios, and fiscal risk. Statistics preserves dataset, method, limitation, and reproducibility boundaries. Speech, Press/PR, and SNS generate drafts only and cannot publish. PPT Designer generates an outline only, not a `.pptx` file.

## Sprint 6 Checkpoint 8: Evidence-aware AI Office

The production Office application service can receive an injected governed Knowledge Router before specialist execution. It builds one organization-scoped query, rejects wholly unavailable evidence, converts the router result to a minimized `OfficeEvidencePackage`, and stores only query/route identifiers plus counts, confidence, sufficiency, failures, and fallback status on the Work Package.

`AgentContext` carries the optional package. The Chief Secretary workflow deterministically selects legal evidence for Legal Review, budget evidence for Budget Analysis, statistical evidence for Statistics, and approved cited facts for public-facing agents. Safe excerpts, classifications, stable evidence IDs and existing citation IDs propagate through AgentResult and artifact structured payloads; agents cannot create substitute citations. All approved prompt files instruct agents to use supplied evidence only and expose conflicts, gaps, stale sources and unsupported claims.

Partial/insufficient evidence, material gaps, unresolved conflicts, incomplete or stale citations, public-facing artifacts, unsupported claims, or partial Agent failures require review. Approval is never automatic. Evidence-unavailable execution stops before provider calls. Existing timeout, cancellation, privacy, provider telemetry and artifact review controls remain authoritative. API request schemas accept legal/budget/minutes workflows and source/date/fiscal context; production router/executor composition in the HTTP dependency container remains follow-up work.

## Sprint 6 v0.4 release candidate

The governed Knowledge Platform release candidate is covered by a synthetic, network-free E2E flow from login and organization RBAC through combined internal RAG/fake MCP routing, cited evidence merge, conflict/gap and confidence assessment, eight-agent Chief Secretary orchestration, reviewable Work Package/artifact persistence, and safe API output. All fixture facts are explicitly fictional. Default CI forbids real OpenAI, remote MCP, and subprocess MCP calls.

Release operation requires Alembic head `20260720_0013`, reviewed environment settings, backup/rollback, retention dry-run, legal-hold protection, privacy incident handling, and provider/MCP outage procedures. See `RELEASE_NOTES_v0.4.md` and `RUNBOOK.md`. Production pgvector/ANN, real government connectors, workers, Redis coordination, scheduled cleanup, SIEM integrations, and live staging verification remain deferred.