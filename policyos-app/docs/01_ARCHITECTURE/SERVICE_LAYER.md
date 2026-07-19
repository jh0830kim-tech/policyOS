# Service Layer

## Purpose
Services coordinate domain rules, persistence, authorization, and external integrations.

## Example responsibilities
- `AuthenticationService`: verifies credentials and issues tokens.
- `AuthorizationService`: evaluates permissions.
- `PolicyService`: manages policy candidate workflow.
- `AgentOrchestrationService`: routes work and records AI runs.
- `AuditService`: records governance-relevant events.

## Rules
- Services accept validated input.
- Services enforce organization boundaries.
- Services return domain or schema-friendly outputs.
- Database transaction behavior must be explicit.
- External side effects must be isolated and testable.
