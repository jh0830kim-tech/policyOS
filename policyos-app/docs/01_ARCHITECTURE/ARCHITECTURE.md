# System Architecture

## Architectural style
PolicyOS uses a modular layered architecture with explicit service boundaries.

```mermaid
flowchart LR
    UI[Web / Future Mobile] --> API[FastAPI API]
    API --> AUTH[Authentication & Authorization]
    API --> SVC[Application Services]
    SVC --> DOMAIN[Domain Models]
    SVC --> AGENT[AI Agent Orchestrator]
    SVC --> REPO[Persistence Layer]
    REPO --> PG[(PostgreSQL)]
    AGENT --> KB[Knowledge / RAG]
    AGENT --> MODEL[LLM Provider]
    API --> AUDIT[Audit Service]
    SVC --> REDIS[(Redis)]
```

## Layer responsibilities

### API layer
- HTTP routing
- request validation
- dependency injection
- response formatting
- authentication entry points

### Application service layer
- business workflows
- transaction boundaries
- orchestration
- authorization-aware operations

### Domain layer
- core business entities
- domain invariants
- reusable business rules

### Persistence layer
- SQLAlchemy access
- queries and repositories
- migrations
- database-specific concerns

### AI orchestration layer
- agent selection
- prompt assembly
- tool permissions
- source tracking
- execution records
- human review state

## Boundary rule
Routers must not contain substantial business logic. AI agents must not access unrestricted data or tools directly.
