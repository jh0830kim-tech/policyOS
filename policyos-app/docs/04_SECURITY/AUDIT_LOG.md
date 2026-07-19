# Audit Logging

Audit records should capture:
- timestamp
- actor user and membership
- organization
- action
- target type and identifier
- outcome
- request or correlation ID
- relevant metadata
- source IP and user agent where legally appropriate

Audit logs should be append-oriented and protected from ordinary modification.

## Authentication events
Sprint 2 records `authentication.login` with a `success` or `failure` outcome and `authorization.denied` for failed permission checks. Authentication audit metadata may include actor identifiers, organization and membership identifiers, request ID, source IP, and user agent. It must never include plaintext passwords, bearer tokens, submitted email addresses for unknown accounts, or full request bodies.
