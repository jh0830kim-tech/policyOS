"""Safe reflection contract errors."""


class ReflectionError(Exception):
    code = "reflection_error"


class ReflectionRequestError(ReflectionError):
    code = "reflection_request_error"


class ReflectionContextError(ReflectionError):
    code = "reflection_context_error"


class ReflectionIdentityError(ReflectionError):
    code = "reflection_identity_error"


class ReflectionClassificationError(ReflectionError):
    code = "reflection_classification_error"
