# Sprint 3 Step 7 — Execution Records


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
AI task와 agent run의 추적 가능한 실행 기록을 DB에 저장하세요.

## 최소 데이터
- AI task record
- agent run record
- prompt version/hash
- provider/model metadata
- started/finished timestamps
- status/error code/review status
- requesting user/organization
- parent orchestration task
- concise result summary 또는 artifact reference

## 보안
password, token, API key, hidden reasoning, unrestricted sensitive payload 저장 금지.

## DB 작업
- 현재 스타일에 맞는 SQLAlchemy model
- Alembic migration
- service/repository
- organization scoping
- 명시적 transaction boundary

## 테스트
생성, 상태 전환, 조직 격리, parent-child run, error 기록, 금지 필드 없음, migration metadata.
