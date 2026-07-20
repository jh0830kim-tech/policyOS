# Privacy

## Principles
- Collect only necessary data.
- Classify personal and sensitive information.
- Restrict data by organization and role.
- Define retention and deletion policies.
- Avoid sending unnecessary personal data to external AI providers.
- Record the legal and operational basis for data processing.

## AI rule
Prompts and retrieved context must be minimized to the information required for the assigned task.

## AI provider privacy and retention

Provider-side response storage defaults to disabled. Test environments force `store=false` even
when an environment override requests storage. Before transmission, the configured redactor masks
OpenAI-style API keys, bearer tokens, Korean resident-registration numbers, email addresses,
telephone numbers, known secret placeholders, and configured custom terms. Only whether redaction
occurred and the number of replacements are audited; original and redacted prompt text are not.

Regex redaction is best-effort and can produce false positives or miss novel formats. Restricted
data therefore remains blocked rather than relying on redaction. Provider audit metadata expires
after `AI_PROVIDER_AUDIT_RETENTION_DAYS`. After `AI_USAGE_RETENTION_DAYS`, token, latency, cost,
retry, and provider-response identifiers are cleared while the execution record remains. Structured
artifact retention continues to follow the existing artifact governance policy.

## Production provider data path

The production composition injects the privacy policy, redactor, response-storage setting, and a
request-scoped provider audit sink before any OpenAI call. Only redacted instructions and minimal
structured context cross the provider boundary. Database models have no API-key, bearer-token, raw
provider-response, prompt, or hidden-reasoning columns. Generated artifacts contain validated final
structured output only and remain `needs_review` until an authorized reviewer acts.
## Knowledge ingestion privacy

Original upload bytes are transient and are not persisted or logged. PolicyOS stores normalized parsed content because it is the governed retrieval source, plus minimum metadata such as filename, hash, size, parser/normalization versions, dates, classification, creator, and scan outcome. Restricted documents remain within the local parser/scanner boundary and are never sent to an AI provider or external parser. Job failures retain safe error codes only; malware signatures may be represented by scanner metadata but file content and secrets must never enter logs.

## Sprint 6 Checkpoint 4: Embedding and vector retrieval

- Embeddings use a provider-independent gateway (`fake`, `disabled`, or explicitly configured `openai`).
- Model, dimension, chunking configuration, normalization strategy, provider, and policy version participate in immutable embedding revisions.
- The default fake provider is SHA-256 deterministic and performs no network I/O. OpenAI uses bounded application retries while SDK retries are disabled.
- External embedding follows provider transmission policy: restricted content is blocked and confidential content requires organization policy. Embedding records never duplicate source text or secrets.
- Current persistence stores validated vectors as JSON for PostgreSQL/SQLite compatibility. `VectorStore` isolates this detail; production pgvector indexing is planned and must fail clearly if the extension is unavailable.
- Retrieval enforces organization, model, dimension, classification, document/source, effective-date, top-k, and minimum-score filters. Cosine scores remain in the native [-1, 1] range.
- Usage records capture input count/tokens, batch/retry count, latency, provider request ID and nullable estimated cost; pricing is not hard-coded.
- Public embedding/search HTTP endpoints are deferred; application services are the authorization-ready boundary.
