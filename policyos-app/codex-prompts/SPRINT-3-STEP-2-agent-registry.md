# Sprint 3 Step 2 — Agent Interface and Registry


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
재사용 가능한 Agent 인터페이스와 Registry를 구현하세요.

## 구현
- Agent protocol 또는 abstract base
- stable name, display name, description, version, capabilities, required permission
- register, duplicate prevention, lookup, list, capability filter
- deterministic fake agent

## 규칙
- import side effect로 자동 등록하지 마세요.
- dependency injection을 사용하세요.
- registry가 네트워크 client를 생성하지 않게 하세요.
- unknown agent는 typed safe error를 반환하세요.
- FastAPI에 의존하지 마세요.

## 권장 위치
- `app/ai/agent.py`
- `app/ai/registry.py`

## 테스트
등록, 중복 거부, 이름 조회, capability 필터, unknown error, fake 실행.
