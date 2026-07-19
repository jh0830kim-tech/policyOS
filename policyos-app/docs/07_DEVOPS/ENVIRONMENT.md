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
