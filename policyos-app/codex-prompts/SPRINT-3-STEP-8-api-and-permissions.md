# Sprint 3 Step 8 — AI Office API and RBAC


작업 전 다음 문서를 읽으세요.

- `CODEX.md`
- `POLICYOS_CONSTITUTION.md`
- `docs/01_ARCHITECTURE/ARCHITECTURE.md`
- `docs/01_ARCHITECTURE/AI_ARCHITECTURE.md`
- `docs/05_AI_OFFICE/AI_OFFICE.md`
- `docs/05_AI_OFFICE/AGENTS.md`
- `docs/05_AI_OFFICE/SYSTEM_PROMPTS.md`
- `docs/05_AI_OFFICE/WORKFLOW.md`
- `specs/epics/EPIC-002-ai-office.md`

기존 코드를 먼저 조사하고 Sprint 2의 인증, 조직 격리, RBAC, 테스트, CI를 보존하세요.

공통 규칙:
- 테스트에서 외부 네트워크를 사용하지 마세요.
- 공급자 API 키를 하드코딩하지 마세요.
- 숨겨진 chain-of-thought를 요청하거나 저장하지 마세요.
- 자동 commit/push는 해당 프롬프트에서 명시적으로 허용할 때만 수행하세요.
- 완료 후 `ruff check .`와 `pytest`를 실행하세요.


## 목표
AI Office task 생성/조회 API를 구현하세요.

## 권장 endpoint
- `POST /api/v1/ai/tasks`
- `GET /api/v1/ai/tasks/{task_id}`
- `GET /api/v1/ai/tasks`
- 선택: `POST /api/v1/ai/tasks/{task_id}/review`

## 권한
기존 RBAC를 사용해 다음 atomic permission을 적용하세요.
- `agent.execute`
- `agent.read`
- `agent.review`

## 요구사항
- authentication 필수
- active organization membership 필수
- organization isolation
- instruction/task type request schema
- structured reviewable output
- internal prompt/raw provider payload/secret/hidden reasoning 노출 금지
- MVP에서는 bounded synchronous execution 허용
- safe error code

## 테스트
성공, 401, membership denial, 403, cross-org denial, sensitive field 없음, org-scoped list.
