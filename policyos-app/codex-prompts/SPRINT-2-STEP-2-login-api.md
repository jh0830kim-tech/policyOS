# Codex Prompt — Sprint 2 Step 2: Login API

Read before editing:

- `CODEX.md`
- `POLICYOS_CONSTITUTION.md`
- `specs/epics/EPIC-001-authentication.md`
- `specs/features/FEATURE-003-login-api.md`
- `docs/03_API/API_GUIDE.md`
- `docs/03_API/ERROR_CODES.md`
- `docs/04_SECURITY/SECURITY.md`
- `docs/04_SECURITY/JWT.md`
- `docs/04_SECURITY/PASSWORD_POLICY.md`

Inspect the current project and the Sprint 2 Step 1 implementation first.

Do not recreate the existing identity models:
`Organization`, `User`, `Membership`, `Role`, `Permission`,
`RolePermission`, and `MembershipRole`.

## Goal

Implement:

```http
POST /api/v1/auth/login
```

## Required behavior

1. Accept a login identifier and password.
2. Look up the user asynchronously with the existing SQLAlchemy async session.
3. Verify the password using the Step 1 security utility.
4. Return the same generic `401 Unauthorized` response for an unknown user and a wrong password.
5. Reject inactive users when the existing `User` model has an active or status field.
6. Create and return a signed bearer access token.
7. Do not expose password hashes or internal authentication details.
8. Follow the existing application route-registration style.

Recommended request:

```json
{
  "email": "user@example.com",
  "password": "plain-text-input"
}
```

Recommended response:

```json
{
  "access_token": "<signed-jwt>",
  "token_type": "bearer",
  "expires_in": 1800
}
```

Use the configured expiration value rather than hard-coding `1800`.
If the actual User model uses another login field, use that field and explain why.

## Suggested boundaries

Prefer these modules when compatible with the current project:

```text
app/api/routes/auth.py
app/schemas/auth.py
app/services/authentication.py
```

Do not create duplicate package structures when equivalent modules already exist.

### Schemas

Define:

- `LoginRequest`
- `TokenResponse`

Never include a password hash in a response schema.

### Service

Keep substantial authentication logic out of the router. The service should:

- query the user asynchronously,
- verify the password,
- check account activity when supported,
- create the access token.

### Router

The router should:

- receive the async database session through dependency injection,
- call the authentication service,
- return the token response,
- return generic HTTP 401 for authentication failure,
- include `WWW-Authenticate: Bearer` on HTTP 401 responses.

## Security rules

- Do not reveal whether an account exists.
- Do not log plain passwords.
- Do not return stored password hashes.
- Do not put sensitive data in the JWT.
- Reuse the existing JWT functions.
- Do not implement refresh tokens, logout, current-user dependencies, or RBAC yet.
- Do not implement rate limiting yet; list it as remaining work.
- Do not modify unrelated routes or identity models.

## Tests

Add focused tests for:

1. Valid credentials return HTTP 200.
2. Response contains `access_token`.
3. `token_type` is `bearer`.
4. `expires_in` matches configuration.
5. Unknown user returns generic HTTP 401.
6. Wrong password returns the same generic HTTP 401.
7. Inactive user returns HTTP 401 when supported by the model.
8. Response contains no password or password hash.
9. Returned token can be decoded by the Step 1 utility.
10. Existing tests remain passing.

Use the existing API and database test patterns. Do not introduce a separate incompatible test setup.

## Validation

Run:

```bash
ruff check .
pytest
```

Both must pass.

## Git restrictions

- Do not commit.
- Do not push.
- Do not create a pull request.

## Completion report

Report:

1. Files created and modified
2. Actual login field used
3. Authentication service design
4. HTTP response behavior
5. Tests added
6. Ruff result
7. Pytest result
8. Warnings or technical debt
9. Remaining work for Sprint 2 Step 3: current authenticated user
