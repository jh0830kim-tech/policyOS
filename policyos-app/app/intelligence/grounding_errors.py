"""Safe typed errors for grounding validation."""


class GroundingError(Exception):
    code = "grounding_error"
    retryable = False

    def __init__(self, message: str, *, retryable: bool | None = None) -> None:
        self.safe_message = message[:300]
        if retryable is not None:
            self.retryable = retryable
        super().__init__(self.safe_message)


class GroundingRequestError(GroundingError):
    code = "grounding_request_error"


class GroundingContextError(GroundingError):
    code = "grounding_context_error"


class GroundingIdentityError(GroundingError):
    code = "grounding_identity_error"


class GroundingClassificationError(GroundingError):
    code = "grounding_classification_error"


class GroundingProviderCapabilityError(GroundingError):
    code = "grounding_provider_capability_error"


class GroundingProviderInvocationError(GroundingError):
    code = "grounding_provider_invocation_error"


class GroundingProviderMalformedOutputError(GroundingError):
    code = "grounding_provider_malformed_output"
    retryable = True


class GroundingResultMismatchError(GroundingError):
    code = "grounding_result_mismatch"
