# Sprint 3 Step 6 — Chief Secretary Orchestrator


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
비서실장 AI의 MVP orchestration service를 구현하세요.

## 동작
1. task scope와 allowed capabilities 검증
2. 단순 실행 계획 작성
3. Policy Research/Legal Review 중 선택
4. 결정론적 순서로 실행
5. structured result 수집
6. review-ready 통합 결과 생성
7. evidence와 warnings 보존
8. evidence 부족, 법률 불확실성, 부분 실패, 대외 consequential action이 있으면 needs_review

## Planner
이번 Sprint는 명시적 rules-based planner를 사용하세요.
- policy/research -> Policy Research
- legal/ordinance/conflict -> Legal Review
- combined -> 둘 다

## 테스트
policy-only, legal-only, combined, unknown type, partial failure, evidence consolidation, review state.
