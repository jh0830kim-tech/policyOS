# Testing Strategy

## Test levels
- Unit: pure utilities and domain rules
- Integration: database and service interactions
- API: request, authentication, authorization, and response contracts
- Security regression: invalid tokens, denied permissions, organization isolation

## Rules
- Tests must be deterministic.
- Secrets and external AI calls must be mocked or isolated.
- Each security-sensitive branch requires a positive and negative test.
