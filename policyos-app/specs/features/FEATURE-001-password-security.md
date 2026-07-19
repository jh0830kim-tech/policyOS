# FEATURE-001 — Password Security

## Requirements
- Use `pwdlib` with Argon2.
- Provide `hash_password(password: str) -> str`.
- Provide `verify_password(plain_password: str, password_hash: str) -> bool`.
- Support recommended rehashing behavior in future revisions.
- Never log plain passwords.

## Tests
- a hash differs from the original password
- correct password verifies
- wrong password fails
- repeated hashes for the same password differ
