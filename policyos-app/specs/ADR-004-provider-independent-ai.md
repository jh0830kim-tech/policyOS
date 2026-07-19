# ADR-004 — Provider-Independent AI Gateway

## Decision
Agent는 특정 공급자 SDK가 아니라 PolicyOS Model Gateway 계약에 의존합니다.

## Rationale
결정론적 테스트, 공급자 교체, 보안·timeout 중앙화, 비용·감사 통제, CI에서 외부 API 불필요.
