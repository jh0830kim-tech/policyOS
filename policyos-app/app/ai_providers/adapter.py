"""Provider-neutral adapter protocol."""

from datetime import datetime
from typing import Protocol

from app.ai_models import ModelRegistrySnapshot
from app.ai_providers.domain import (
    NormalizedModelInvocationRequest,
    NormalizedModelInvocationResult,
    ProviderAdapterIdentity,
)
from app.ai_selection import AuthorizedInvocationPermit


class ProviderAdapter(Protocol):
    @property
    def identity(self) -> ProviderAdapterIdentity: ...

    def invoke(
        self,
        *,
        permit: AuthorizedInvocationPermit,
        request: NormalizedModelInvocationRequest,
        registry: ModelRegistrySnapshot,
        invoked_at: datetime,
    ) -> NormalizedModelInvocationResult: ...
