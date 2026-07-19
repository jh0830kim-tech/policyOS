# Error Model

## Current Sprint 2 behavior
Authentication and authorization endpoints currently use FastAPI's standard public error body:

```json
{
  "detail": "Invalid credentials"
}
```

Public messages are intentionally generic:
- login failures: `401 Invalid credentials`
- token and current-user failures: `401 Could not validate credentials`
- missing permission: `403 Permission denied`
- missing or inaccessible organization context: `404 Organization not found`

Authentication `401` responses include `WWW-Authenticate: Bearer`. Unknown users, wrong passwords, inactive users, malformed tokens, and inaccessible tenants must not expose which internal condition occurred.

## Target structured model
A future API-wide error migration may introduce:

```json
{
  "error": {
    "code": "AUTH_INVALID_CREDENTIALS",
    "message": "The credentials are invalid.",
    "details": {},
    "request_id": "..."
  }
}
```

Reserved initial codes:
- `AUTH_INVALID_CREDENTIALS`
- `AUTH_TOKEN_EXPIRED`
- `AUTH_TOKEN_INVALID`
- `AUTH_FORBIDDEN`
- `ORG_MEMBERSHIP_REQUIRED`
- `RESOURCE_NOT_FOUND`
- `RESOURCE_CONFLICT`
- `VALIDATION_FAILED`
- `INTERNAL_ERROR`

Do not assume the structured envelope is implemented until a versioned API migration adopts it consistently.
