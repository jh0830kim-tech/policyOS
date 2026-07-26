"""Safe typed failures for grounded narrative generation."""


class NarrativeGenerationError(Exception):
    code = "narrative_generation_error"
    retryable = False

    def __init__(self, message: str, *, retryable: bool | None = None) -> None:
        self.safe_message = message[:300]
        if retryable is not None:
            self.retryable = retryable
        super().__init__(self.safe_message)


class NarrativeGenerationRequestError(NarrativeGenerationError):
    code = "narrative_generation_request_error"


class NarrativeGenerationContextError(NarrativeGenerationError):
    code = "narrative_generation_context_error"


class NarrativeGenerationIdentityError(NarrativeGenerationError):
    code = "narrative_generation_identity_error"


class NarrativeGenerationClassificationError(NarrativeGenerationError):
    code = "narrative_generation_classification_error"


class NarrativeProviderCapabilityError(NarrativeGenerationError):
    code = "narrative_provider_capability_error"


class NarrativeProviderInvocationError(NarrativeGenerationError):
    code = "narrative_provider_invocation_error"


class NarrativeProviderTimeoutError(NarrativeProviderInvocationError):
    code = "narrative_provider_timeout"
    retryable = True


class NarrativeProviderMalformedOutputError(NarrativeProviderInvocationError):
    code = "narrative_provider_malformed_output"
    retryable = True


class NarrativeDraftNormalizationError(NarrativeGenerationError):
    code = "narrative_draft_normalization_error"


class NarrativeGenerationResultMismatchError(NarrativeGenerationError):
    code = "narrative_generation_result_mismatch"
