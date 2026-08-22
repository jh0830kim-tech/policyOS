# ADR-136: Gemini Provider, Model, Credential, and Evaluation Ownership

## Status

Accepted for the post-Sprint 17 provider-evaluation governance gate.

## Context

PolicyOS already exposes a provider-neutral model gateway, structured-output requests, bounded
resilience, metadata-only provider audit, and an explicit live-smoke boundary. The production
implementation currently selects only fake, disabled, or OpenAI execution. A Gemini connectivity
smoke proved only that a synthetic public request can reach the provider; it did not authorize
Gemini for application traffic, internal data, persistence, automatic fallback, or production use.

Adding `gemini` to the generic provider allowlist would silently inherit the existing eligibility
of internal data. Google credential discovery can also choose `GOOGLE_API_KEY` ahead of
`GEMINI_API_KEY`, while the provider SDK can inherit environment proxies and perform its own
retry. Those implicit choices conflict with PolicyOS's exact configuration, single retry owner,
and non-disclosure boundaries.

## Decision

### Provider and model ownership

The deployment configuration is the sole owner of provider selection. Gemini is selected only by
the exact value `AI_PROVIDER=gemini`; no gateway, request, response, array position, environment
fallback, or runtime health result may select or substitute it. There is no cross-provider retry
or automatic fallback.

`GEMINI_MODEL` is a required non-empty, trimmed, bounded exact model identifier whenever Gemini is
selected. The initial approved evaluation model is the explicitly configured
`gemini-3.7-flash`. There is no default Gemini model. The adapter rejects a response whose model
identity does not exactly match the requested configured model.

The initial transport is the official Gemini Developer API Interactions operation at the fixed
Google origin. It is non-streaming and does not use tools, files, background execution, stored
interaction history, a previous interaction identifier, caller-selected base URLs, or redirects.

### Credential ownership and lifetime

The deployment secret mechanism owns one `GEMINI_API_KEY`. PolicyOS passes that exact value into
the private client constructor and never relies on ambient SDK discovery. A simultaneous
`GOOGLE_API_KEY`, missing key, empty key, or ambiguous credential configuration fails application
construction before a provider call. The key is never added to a model request, public contract,
audit record, log, exception, error response, test snapshot, or database row.

The Gemini async client is request scoped and managed. It is closed exactly once on success,
provider failure, validation failure, cancellation, or timeout. Environment proxy inheritance is
disabled. SDK retry is explicitly disabled so the existing PolicyOS application retry loop remains
the only retry owner.

### Classification and transmission

The initial Gemini evaluation ceiling is `public` synthetic data only. `internal`, `confidential`,
and `restricted` content fail closed before client construction and network I/O until a separate
organization-approved data-processing and retention decision changes this ceiling. Merely adding
`gemini` to a generic approved-provider set is prohibited because it would implicitly authorize
internal transmission.

Existing tenant, organization, user, task, permission, redaction, and provider-policy checks remain
mandatory. Prompt text, structured context, output, raw response, hidden reasoning, credentials,
and provider error messages remain excluded from audit and logs.

The provider-policy contract owns one immutable explicit allowed-classification set per approved
provider. OpenAI retains `public` and `internal` eligibility, with `confidential` still governed
by its existing separate opt-in and `restricted` denied. Gemini's set contains only `public`.
An approved provider presented with a classification outside its set returns the new safe policy
decision `deny_classification`. It is not mislabeled as confidential, restricted, or unknown
provider denial. A global confidential opt-in cannot widen a provider's explicit set.

Evaluation remains fail-closed in this order: exact cross-organization binding, approved provider,
organization permission, user permission, restricted denial, provider-specific classification set,
then any provider-specific confidential opt-in. The policy copies and freezes caller-supplied
configuration; callers, environment values, requests, and responses cannot mutate the set.

### HTTP implementation ownership

The initial adapter uses PolicyOS's existing `httpx` dependency instead of adding a Gemini SDK.
This keeps the official origin, one fixed Interactions path, `trust_env=False`, redirect denial,
zero transport retries, bounded request/response bytes, and request-local exactly-once client close
under one implementation owner. The reference to disabled SDK retry remains a required invariant:
no SDK retry layer may be introduced later without another governance decision.

### Structured response validation

The adapter sends the caller-supplied JSON Schema through Gemini structured-output configuration
with JSON media type. Provider schema enforcement is not authoritative domain validation. The
adapter accepts a result only after all of the following succeed in order:

1. the provider operation completes within one bounded total timeout;
2. the response is completed and not blocked, refused, or incomplete;
3. a non-empty bounded response identifier is present;
4. the response model exactly equals the configured requested model;
5. one bounded JSON object is present and parses without unknown transport fields;
6. the existing Pydantic/domain output contract validates the object;
7. usage values are present where required, integral, non-negative, and bounded.

Missing output, malformed JSON, unsupported schema behavior, unknown completion state, model
substitution, or invalid usage maps to the safe `invalid_response` boundary. Raw response bodies
and provider messages are discarded.

### Timeout, retry, and errors

One PolicyOS total timeout covers the provider call and application retry waits. The SDK performs
zero retries. Cancellation propagates. Timeout and cancellation are not retried. Application retry
is bounded to connection failure, rate limiting, and transient provider server/unavailable results;
it never retries authentication, permission, invalid request, model-not-found configuration,
policy block, refusal, incomplete output, or response-validation failure.

Safe mappings are:

- authentication failure to `authentication`;
- permission failure to `permission_denied`;
- unknown or inaccessible configured model to `configuration`;
- quota or rate limit to `rate_limited`;
- timeout to `timeout`;
- transient unavailability to `provider_unavailable`;
- provider server failure to `server_error`;
- safety, recitation, or sensitive-information block to `policy_blocked`;
- malformed or identity-substituted output to `invalid_response`;
- every unclassified result to bounded `unknown` without provider detail.

Retry-after input is accepted only when bounded and valid. It cannot extend the total deadline.

### Usage and audit

Gemini input, output, cached-input, and total token counts map to the existing generic usage fields.
Thinking and tool-use tokens remain represented only in the provider total; they are neither
inferred nor added to output tokens. Therefore total tokens need not equal input plus output.
Estimated cost remains absent; pricing is not inferred or hard-coded.

Audit records contain only `provider=gemini`, the exact configured model, safe request lineage,
classification, redaction counts, response identifier, duration, retry count, bounded token
counts, decision, success, and safe error code. PolicyOS provider storage is recorded as disabled.
No raw provider evidence, thought signature, prompt, response, or credential is retained.

### Live-smoke boundary

Automated tests are network free. A Gemini live smoke is a separately approved staging operation
guarded by `RUN_GEMINI_LIVE_TESTS=1`. It uses one synthetic public request, one provider call,
application retry zero, no tools or history, and prints only provider/model identity, response ID,
latency, and token counts. It never prints or stores the key, prompt, raw response, or error body.

## Schema and migration decision

Existing provider audit and agent-run usage columns are provider neutral and sufficient. The
thinking/tool token distinction is intentionally not persisted separately. This gate adds no table,
column, backfill, normalization, or migration `20260808_0025`; single Alembic head remains
`20260808_0024`.

## Consequences

Gemini remains disabled until a separate config/privacy/adapter implementation gate is reviewed and
merged. That gate may add a pinned provider SDK dependency, but it cannot broaden classification,
change public model-gateway contracts, add persistence, or enable live traffic. Approval of
internal or confidential Gemini transmission, provider retention terms, production credentials,
quota, billing, deployment, tag, or release remains a separate governance action.

## Rejected alternatives

- Add Gemini to the generic allowlist and inherit internal-data eligibility.
- Reuse `deny_provider`, `deny_confidential`, or `deny_restricted` for internal Gemini data.
- Let a global confidential opt-in widen Gemini beyond its explicit classification set.
- Let the SDK discover whichever Google API key is present.
- Add a provider SDK when the existing bounded `httpx` transport is sufficient.
- Select the first configured model or accept a provider-substituted model.
- Enable SDK retry in addition to PolicyOS application retry.
- Treat HTTP success or schema-shaped JSON as authoritative domain validity.
- Persist raw output, provider messages, hidden reasoning, or new token subcategories.
- Reuse the manual connectivity smoke as application or production authorization.
