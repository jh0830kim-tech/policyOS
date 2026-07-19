# Sprint 3 Step 4 — Model Gateway Abstraction


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
Agent가 특정 공급자 SDK에 직접 의존하지 않도록 Model Gateway 추상화를 만드세요.

## 계약
ModelRequest/ModelResponse는 다음을 지원해야 합니다.
- system prompt
- user instruction
- structured context
- requested output format/schema
- timeout
- model id
- usage metadata
- provider request id
- safe error mapping

## 구현
1. Protocol 또는 abstract gateway
2. deterministic FakeModelGateway
3. provider 미설정 시 명확히 실패하는 disabled gateway
4. 외부 API 호출은 아직 필수 구현하지 않음

## 규칙
- CI에서 network call 금지
- timeout과 typed error
- hidden reasoning 저장 금지
- final structured output과 concise metadata만 반환

## 테스트
fake response, timeout/error mapping, missing config, metadata, no network.
