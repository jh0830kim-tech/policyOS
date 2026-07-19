# FEATURE-003 ??Login API

## Endpoint
`POST /api/v1/auth/login`

## Input
- `email`: 3 to 320 characters
- `password`: 1 to 1024 characters

## Successful output
- `access_token`
- `token_type`: `bearer`
- `expires_in`: configured lifetime in seconds

## Security behavior
- unknown users, invalid passwords, and inactive users return the same generic `401`
- a dummy Argon2 hash prevents the unknown-user path from skipping password verification work
- successful and failed attempts emit `authentication.login` audit events
- audit metadata excludes passwords, bearer tokens, unknown-account email input, and full request bodies
- rate limiting is a documented gateway or dependency integration point; no ad hoc Redis limiter is included
