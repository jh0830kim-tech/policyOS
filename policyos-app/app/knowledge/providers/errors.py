"""Safe, provider-neutral knowledge provider errors."""

from __future__ import annotations


class KnowledgeProviderError(RuntimeError):
    code = "knowledge_provider_error"
    retryable = False

    def __init__(
        self,
        safe_message: str,
        *,
        provider_type: str | None = None,
        retryable: bool | None = None,
        fallback_attempted: bool = False,
        correlation_id: str | None = None,
    ) -> None:
        super().__init__(safe_message)
        self.safe_message = safe_message
        self.provider_type = provider_type
        if retryable is not None:
            self.retryable = retryable
        self.fallback_attempted = fallback_attempted
        self.correlation_id = correlation_id


class KnowledgeProviderNotFoundError(KnowledgeProviderError):
    code = "provider_not_found"


class KnowledgeProviderDisabledError(KnowledgeProviderError):
    code = "provider_disabled"


class KnowledgeProviderUnavailableError(KnowledgeProviderError):
    code = "provider_unavailable"
    retryable = True


class KnowledgeProviderTimeoutError(KnowledgeProviderError):
    code = "provider_timeout"
    retryable = True


class KnowledgeProviderRateLimitError(KnowledgeProviderError):
    code = "provider_rate_limited"
    retryable = True


class KnowledgeProviderAuthenticationError(KnowledgeProviderError):
    code = "provider_authentication_failed"


class KnowledgeProviderUnsupportedOperationError(KnowledgeProviderError):
    code = "provider_unsupported_operation"


class KnowledgeProviderMalformedResponseError(KnowledgeProviderError):
    code = "provider_malformed_response"


class KnowledgeProviderSchemaError(KnowledgeProviderError):
    code = "provider_schema_error"


class KnowledgeProviderSecurityError(KnowledgeProviderError):
    code = "provider_security_violation"


class KnowledgeProviderPolicyDeniedError(KnowledgeProviderError):
    code = "provider_policy_denied"


class KnowledgeProviderResultTooLargeError(KnowledgeProviderError):
    code = "provider_result_too_large"


class KnowledgeProviderNoResultError(KnowledgeProviderError):
    code = "provider_no_result"


class KnowledgeProviderFallbackExhaustedError(KnowledgeProviderError):
    code = "provider_fallback_exhausted"

    def __init__(self, safe_message: str, *, failures: tuple[str, ...], **kwargs) -> None:
        super().__init__(safe_message, fallback_attempted=True, **kwargs)
        self.failures = failures
