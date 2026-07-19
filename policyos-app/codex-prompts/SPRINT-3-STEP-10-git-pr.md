# Sprint 3 Step 10 — GitHub Save and PR

명시적 사용자 승인 후에만 진행하세요.

## 선행 조건
- branch: `feature/sprint-3-ai-office-core`
- `git diff --check`, `ruff check .`, `pytest` 통과
- secret 없음
- migration/docs 검토 완료

## 권장 commit
1. `feat(ai): add agent domain and registries`
2. `feat(ai): add specialist agents and orchestration`
3. `feat(ai): persist AI execution records`
4. `feat(api): add governed AI task endpoints`
5. `test(ai): add AI Office integration coverage`
6. `docs: document Sprint 3 AI Office architecture`

실제 diff에 맞게 조정하세요.

## Push
`origin/feature/sprint-3-ai-office-core`로 push하고 force push는 금지합니다.

## Draft PR
제목:
`Sprint 3: AI Office core, orchestration, and execution records`

본문에는 목표, architecture, agents, API, migration, RBAC/security, fake testing, CI, limitations, deferred provider/RAG, checklist를 포함하세요.

자동 merge는 금지합니다.
