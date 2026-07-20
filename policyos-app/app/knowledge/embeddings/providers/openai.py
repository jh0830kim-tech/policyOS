"""OpenAI embeddings adapter with bounded application retries."""

import asyncio
from time import perf_counter

import openai
from openai import AsyncOpenAI

from app.ai.privacy import ProviderTransmissionPolicy
from app.knowledge.embeddings.domain import (
    EmbeddingError,
    EmbeddingErrorCode,
    EmbeddingRequest,
    EmbeddingResponse,
    EmbeddingUsage,
    EmbeddingVector,
)


class OpenAIEmbeddingGateway:
    def __init__(
        self,
        client: AsyncOpenAI,
        *,
        timeout_seconds: float = 30,
        max_retries: int = 2,
        transmission_policy: ProviderTransmissionPolicy | None = None,
    ) -> None:
        self.client = client
        self.timeout_seconds = timeout_seconds
        self.max_retries = max_retries
        self.policy = transmission_policy or ProviderTransmissionPolicy()

    async def embed(self, request: EmbeddingRequest) -> EmbeddingResponse:
        context = request.transmission_context
        if context is None or not self.policy.evaluate("openai", context).allowed:
            raise EmbeddingError(
                EmbeddingErrorCode.PRIVACY_BLOCKED, "Embedding transmission is not allowed"
            )
        started = perf_counter()
        retries = 0
        while True:
            try:
                kwargs = {"input": list(request.texts), "model": request.model}
                if request.dimensions is not None:
                    kwargs["dimensions"] = request.dimensions
                response = await asyncio.wait_for(
                    self.client.embeddings.create(**kwargs),
                    timeout=request.timeout_seconds or self.timeout_seconds,
                )
                vectors = tuple(
                    EmbeddingVector(index=item.index, values=tuple(item.embedding))
                    for item in sorted(response.data, key=lambda item: item.index)
                )
                dimensions = len(vectors[0].values) if vectors else 0
                if (
                    len(vectors) != len(request.texts)
                    or dimensions < 1
                    or any(len(v.values) != dimensions for v in vectors)
                ):
                    raise EmbeddingError(
                        EmbeddingErrorCode.INVALID_VECTOR, "Provider returned invalid embeddings"
                    )
                usage = getattr(response, "usage", None)
                return EmbeddingResponse(
                    vectors=vectors,
                    provider="openai",
                    model=getattr(response, "model", request.model),
                    dimensions=dimensions,
                    provider_request_id=getattr(response, "id", None),
                    usage=EmbeddingUsage(
                        input_tokens=getattr(usage, "prompt_tokens", 0)
                        or getattr(usage, "total_tokens", 0)
                        or 0,
                        input_count=len(request.texts),
                        retry_count=retries,
                    ),
                    latency_ms=max(0, round((perf_counter() - started) * 1000)),
                )
            except asyncio.CancelledError:
                raise
            except (TimeoutError, openai.APITimeoutError):
                error = EmbeddingError(
                    EmbeddingErrorCode.TIMEOUT, "Embedding provider timed out", retryable=True
                )
            except openai.RateLimitError:
                error = EmbeddingError(
                    EmbeddingErrorCode.RATE_LIMIT,
                    "Embedding provider rate limited the request",
                    retryable=True,
                )
            except openai.AuthenticationError as exc:
                raise EmbeddingError(
                    EmbeddingErrorCode.AUTHENTICATION, "Embedding provider authentication failed"
                ) from exc
            except (openai.BadRequestError, openai.PermissionDeniedError) as exc:
                raise EmbeddingError(
                    EmbeddingErrorCode.INVALID_REQUEST, "Embedding request was rejected"
                ) from exc
            except openai.APIConnectionError:
                error = EmbeddingError(
                    EmbeddingErrorCode.CONNECTION,
                    "Embedding provider is unavailable",
                    retryable=True,
                )
            except openai.APIStatusError as exc:
                if exc.status_code >= 500:
                    error = EmbeddingError(
                        EmbeddingErrorCode.PROVIDER, "Embedding provider failed", retryable=True
                    )
                else:
                    raise EmbeddingError(
                        EmbeddingErrorCode.PROVIDER, "Embedding provider rejected the request"
                    ) from exc
            if retries >= self.max_retries:
                raise error from error
            retries += 1
            await asyncio.sleep(min(0.25 * (2 ** (retries - 1)), 2.0))
