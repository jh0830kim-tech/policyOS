# Environment Variables

Expected categories:
- application settings
- database URL
- Redis URL
- JWT secret and algorithm
- token expiration
- AI provider credentials
- logging and monitoring

Provide `.env.example` with placeholders only.

## OpenAI provider resilience

`OPENAI_TIMEOUT_SECONDS` caps the complete provider operation, including retry waits.
`OPENAI_MAX_RETRIES` is the number of retries after the initial attempt.
`OPENAI_RETRY_BACKOFF_SECONDS` is the base for exponential delays (`base * 2^retry_count`).
The OpenAI SDK retry count is fixed at zero so SDK and application retries never overlap.
Rate limits, server failures, and connection failures are retryable. Authentication,
permission, invalid request, schema/output validation, incomplete output, and refusal are not.
Provider errors expose only PolicyOS-safe codes; raw responses, credentials, and prompts are
never written to telemetry.

## AI privacy configuration

- `OPENAI_STORE_RESPONSES=false`: provider response storage; always false in test environments.
- `AI_DEFAULT_DATA_CLASSIFICATION=internal`: default classification for new AI contexts.
- `AI_ALLOW_CONFIDENTIAL_EXTERNAL_PROVIDER=false`: organization-level confidential-data opt-in.
- `AI_PROVIDER_AUDIT_RETENTION_DAYS=365`: provider audit metadata retention.
- `AI_USAGE_RETENTION_DAYS=365`: usage telemetry retention before fields are cleared.
- `AI_REDACTION_ENABLED=true`: enable the transmission redaction hook.
- `AI_REDACTION_CUSTOM_TERMS=`: comma-separated organization-specific terms to mask.

Custom terms are policy configuration, not a secret store. Do not place credentials in this value.

## Production workflow provider selection

Local and test environments default to `AI_PROVIDER=fake`. Production deployments explicitly set
`AI_PROVIDER=openai` and supply `OPENAI_API_KEY` through the approved secret mechanism, or select
`disabled` to fail safely. The composition root applies the configured model, store, timeout,
application retry, redaction, classification, confidential-data policy, and audit retention settings.
No live provider call is made by the automated test suite.
## Sprint 5 release gates

Before enabling `AI_PROVIDER=openai`, complete the environment and migration checklist in `RELEASE_NOTES_v0.3.md`, run `ruff check .`, `pytest`, and `pytest -m smoke`, and verify the configured retention/privacy values. `RUN_OPENAI_LIVE_TESTS` is intentionally absent from `.env.example`; set it temporarily to `1` only for an approved staging invocation of `python -m scripts.openai_smoke_test`. Automated tests never make external provider calls.
