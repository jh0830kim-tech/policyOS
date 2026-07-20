# API Guide

## Base path
Use versioned routes such as `/api/v1`.

## Resource naming
Use plural nouns such as `/organizations`, `/users`, and `/policy-candidates`.

## Authentication
Protected endpoints require an `Authorization: Bearer <access_token>` header. Access tokens are short-lived signed JWTs; membership and permissions are always resolved from the database rather than trusted from token claims.

### Login
`POST /api/v1/auth/login`

Request:

```json
{
  "email": "user@example.com",
  "password": "user-supplied-password"
}
```

A successful response contains `access_token`, the literal token type `bearer`, and `expires_in` in seconds. Passwords and password hashes are never returned. Unknown users, wrong passwords, and inactive users receive the same `401` public response and `WWW-Authenticate: Bearer` header.

Login success and failure are audited without storing passwords, bearer tokens, submitted email addresses for unknown accounts, or full request bodies. Rate limiting is an explicit gateway or dependency integration point and is not implemented in Sprint 2.

### Current user
`GET /api/v1/auth/me`

This endpoint requires a valid bearer token and returns only `id`, `email`, and `display_name`. Missing, malformed, expired, incorrectly signed, or otherwise invalid tokens return the same generic `401` response. Inactive and nonexistent token subjects are also rejected.

## Organization context
Organization-scoped routes use an `organization_id` path parameter. The `get_active_organization_context` dependency resolves an active organization and active membership belonging to the authenticated user. Nonexistent, inactive, and inaccessible organization contexts all return the same `404` response to avoid tenant disclosure.

## Authorization
Routes declare atomic permissions with dependencies such as `Depends(require_permission("policy.read"))`. Missing exact permissions return `403`; authentication failures remain `401`. See `docs/04_SECURITY/RBAC.md` for organization isolation rules.

## Response behavior
- `200`: successful read or update
- `201`: successful creation
- `204`: successful deletion without body
- `400`: malformed or invalid request
- `401`: missing or invalid authentication
- `403`: authenticated but not authorized
- `404`: resource not found within accessible scope
- `409`: state or uniqueness conflict
- `422`: schema validation error

## Current error shape
Sprint 2 endpoints currently use FastAPI's standard error body, for example `{"detail": "Invalid credentials"}`. The structured error envelope and stable codes in `ERROR_CODES.md` remain a future API-wide migration; clients must not infer account or tenant existence from authentication errors.
## AI Office tasks
POST /api/v1/ai/tasks requires agent.execute. List and item GET endpoints require agent.read. All require organization_id, authentication, active membership, and organization-scoped RBAC. Responses exclude instructions, prompts, provider payloads, secrets, and hidden reasoning.
## Sprint 4 work packages and artifacts
- `POST /api/v1/ai/work-packages?organization_id={uuid}` requires `agent.execute`.
- Package list and item reads require `agent.read`.
- `GET /api/v1/ai/artifacts/{artifact_id}?organization_id={uuid}` requires `artifact.read`.
- `POST /api/v1/ai/artifacts/{artifact_id}/review?organization_id={uuid}` requires `artifact.review`.
No publish or send endpoint exists.

## Work Package execution

`POST /api/v1/ai/work-packages` now performs governed workflow execution synchronously. It requires
active membership and `agent.execute`. Supported package types are policy, communication,
presentation, and full-office packages. `Idempotency-Key` or `client_request_id` prevents duplicate
creation within one organization. Provider policy denial returns `403`; timeout returns `504`;
rate limit, unavailable provider, and configuration failures return safe `503` responses. Provider
messages, stack traces, credentials, prompts, and raw responses are never returned.

List/item Work Package and Artifact reads remain organization-scoped. Artifact review still requires
`artifact.review`, and execution status is exposed separately from human review status.
## Knowledge ingestion boundary

Sprint 6 Checkpoint 2 provides framework-neutral `IngestionRequest`, `IngestionResult`, parser contracts, and `KnowledgeIngestionService`. A multipart HTTP endpoint is intentionally deferred so upload transport limits and streaming can be designed without buffering untrusted files in a thin router. The future endpoint must derive organization and user IDs exclusively from authenticated active-membership context and require `knowledge.ingest`; job reads require `knowledge.read` and an organization predicate. Parser errors must map to allowlisted safe codes without stack traces.
## Knowledge chunking boundary

Sprint 6 Checkpoint 3 provides `KnowledgeChunkingService` and framework-neutral chunk/citation contracts. HTTP endpoints for chunk creation/list/citation reads remain deferred with the ingestion transport API. Future routes must derive organization from active membership, require `knowledge.ingest` for chunk creation and `knowledge.read` for reads, and avoid returning restricted chunk content unless an explicit classification-aware policy authorizes it. Safe citation metadata can be returned separately from raw chunk text.

## Sprint 6 Checkpoint 4: Embedding and vector retrieval

- Embeddings use a provider-independent gateway (`fake`, `disabled`, or explicitly configured `openai`).
- Model, dimension, chunking configuration, normalization strategy, provider, and policy version participate in immutable embedding revisions.
- The default fake provider is SHA-256 deterministic and performs no network I/O. OpenAI uses bounded application retries while SDK retries are disabled.
- External embedding follows provider transmission policy: restricted content is blocked and confidential content requires organization policy. Embedding records never duplicate source text or secrets.
- Current persistence stores validated vectors as JSON for PostgreSQL/SQLite compatibility. `VectorStore` isolates this detail; production pgvector indexing is planned and must fail clearly if the extension is unavailable.
- Retrieval enforces organization, model, dimension, classification, document/source, effective-date, top-k, and minimum-score filters. Cosine scores remain in the native [-1, 1] range.
- Usage records capture input count/tokens, batch/retry count, latency, provider request ID and nullable estimated cost; pricing is not hard-coded.
- Public embedding/search HTTP endpoints are deferred; application services are the authorization-ready boundary.
