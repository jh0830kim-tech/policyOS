"""Named failure-mode providers for deterministic, network-free tests."""

from app.knowledge.providers.adapters import FakeKnowledgeProvider
from app.knowledge.providers.errors import (
    KnowledgeProviderMalformedResponseError,
    KnowledgeProviderRateLimitError,
    KnowledgeProviderSecurityError,
    KnowledgeProviderTimeoutError,
)


class FakeTimeoutProvider(FakeKnowledgeProvider):
    def __init__(self, provider_name="fake-timeout", **kwargs):
        kwargs["error"] = KnowledgeProviderTimeoutError("Provider timed out")
        super().__init__(provider_name, **kwargs)


class FakeRateLimitedProvider(FakeKnowledgeProvider):
    def __init__(self, provider_name="fake-rate-limited", **kwargs):
        kwargs["error"] = KnowledgeProviderRateLimitError("Provider is rate limited")
        super().__init__(provider_name, **kwargs)


class FakeMalformedProvider(FakeKnowledgeProvider):
    def __init__(self, provider_name="fake-malformed", **kwargs):
        kwargs["error"] = KnowledgeProviderMalformedResponseError("Provider response is malformed")
        super().__init__(provider_name, **kwargs)


class FakeSecurityViolationProvider(FakeKnowledgeProvider):
    def __init__(self, provider_name="fake-security-violation", **kwargs):
        kwargs["error"] = KnowledgeProviderSecurityError("Provider response violated policy")
        super().__init__(provider_name, **kwargs)
