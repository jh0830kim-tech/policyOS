# Codex Master Prompt — Sprint 4 Operational AI Agents

작업 전 `CODEX.md`, `POLICYOS_CONSTITUTION.md`, Sprint 3 AI 관련 문서와 `specs/SPRINT-4-SPEC.md`, ADR-007~009, `prompts/`를 읽으세요.

현재 브랜치가 `feature/sprint-4-operational-agents`가 아니면 중단하세요.

공통 규칙:
- Sprint 2/3 기능과 기존 Agent/Gateway/PromptRegistry를 보존
- 외부 네트워크·실제 LLM 계정 없이 테스트
- API 키 하드코딩 금지
- 숨겨진 사고과정 요청·저장 금지
- 공식 발송·게시·승인·제출은 인간 승인 없이 금지
- 마지막까지 commit/push 금지
- 각 Phase 후 `ruff check .`와 `pytest`, 실패 시 중단

## PHASE 1 — 산출물 계약
기존 AgentResult와 호환되는 typed schema를 추가:
BudgetAnalysisOutput, StatisticsAnalysisOutput, SpeechDraftOutput, PressReleaseOutput, SNSContentOutput, PresentationOutlineOutput, OfficeWorkPackage, ArtifactMetadata.

공통 필드: title, summary, organization_id, task_id, authoring_agent, version, created_at, review_status, warnings, evidence_references, assumptions, approval_required.
상태: draft, needs_review, approved, rejected, archived.
민감정보·내부 prompt 제외, 길이 검증. 테스트.

## PHASE 2 — Budget Analysis Agent
`app/agents/budget_analysis.py`
출력: 목적, 비용 항목, 일회성/반복 비용, 재원, 가정, 시나리오 비교, 재정 위험, 누락 데이터, 근거, review note.
사실·추정·가정 구분, 근거 없는 확정 수치 금지. FakeGateway 테스트.

## PHASE 3 — Statistics Agent
`app/agents/statistics.py`
출력: 질문, 데이터셋 설명, 변수, 방법론, 지표, 해석, 한계, 차트 제안, 재현 메모, 근거.
실제 데이터 없을 때 가짜 수치 금지. 테스트.

## PHASE 4 — Speech Writer Agent
`app/agents/speech_writer.py`
출력: audience, purpose, duration, tone, opening, body, closing, verified claims, claims requiring review, notes, evidence.
공식 입장으로 확정하지 말고 draft 유지. 테스트.

## PHASE 5 — Press/PR 및 SNS Agent
`app/agents/press_pr.py`, `app/agents/sns_manager.py`
보도자료: headline, lead, body, quotes, media Q&A, fact checklist, reputational risks, evidence.
SNS: channel, audience, short/long copy, hashtags, visual suggestion, risky claims, approval status.
게시 기능 금지, human approval required, 근거 없는 인용 금지. 테스트.

## PHASE 6 — PPT Designer Agent
`app/agents/ppt_designer.py`
출력: title, audience, objective, slide sequence, slide titles, messages, visuals, chart requirements, notes, source notes, review status.
실제 pptx 생성은 범위 밖. 테스트.

## PHASE 7 — Chief Secretary workflow 확장
지원:
- policy package: Policy Research + Legal + Budget + Statistics
- communication package: Policy Research + PR + SNS + Speech
- presentation package: Policy Research + Statistics + PPT
- full office package: 모든 Agent

명시적 rules-based, deterministic order, dependency-aware, partial failure, OfficeWorkPackage 통합, public-facing artifact는 needs_review. 테스트.

## PHASE 8 — Artifact persistence
저장: artifact type/title, agent, task/org, version, review status, concise summary, structured payload/reference, evidence ids, created_by, approved_by/at, archived_at.
raw provider response, hidden reasoning, secret 금지. 조직 격리, payload size limit.
SQLAlchemy model, Alembic migration, service/repository, 상태 전환 테스트.

## PHASE 9 — API/RBAC
권장:
POST /api/v1/ai/work-packages
GET /api/v1/ai/work-packages/{package_id}
GET /api/v1/ai/work-packages
GET /api/v1/ai/artifacts/{artifact_id}
POST /api/v1/ai/artifacts/{artifact_id}/review

권한: agent.execute, agent.read, agent.review, artifact.read, artifact.review.
인증, active membership, 조직 격리, 안전한 401/403/404, 승인권자만 review. publish/send endpoint 금지. 테스트.

## PHASE 10 — 통합·문서·최종 검토
E2E: full office package 생성 → 8개 Agent → FakeGateway → package/artifact 저장 → 전부 needs_review → 권한 있는 reviewer 승인 → 무권한·타 조직 차단 → 네트워크 없음 → secret/hidden reasoning/raw payload 없음.

문서 업데이트: AI architecture, ERD, API, security, AI Office, agents, workflow, roadmap, changelog.

최종 실행:
git diff --check
ruff check .
pytest
git status

commit/push하지 말고 생성·수정 파일, Agent, workflow, migration, endpoint, permission, 테스트 수, Ruff/diff 결과, 기술부채, Sprint 5 OpenAI 연동 전 남은 작업, 권장 commit 분할을 보고하세요.
