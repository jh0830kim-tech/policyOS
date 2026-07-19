"""Explicit opt-in live OpenAI Responses API smoke test.

This command prints only response identifiers and usage metadata. It never prints
prompt content, credentials, raw responses, or hidden reasoning.
"""

import asyncio
import json
import os
import uuid

from app.ai.model_gateway import ModelRequest
from app.ai.privacy import DataClassification, ProviderTransmissionContext
from app.ai.providers.registry import create_model_gateway
from app.core.config import Settings

_OPT_IN_VARIABLE = "RUN_OPENAI_LIVE_TESTS"


def require_opt_in() -> None:
    if os.getenv(_OPT_IN_VARIABLE) != "1":
        raise SystemExit(
            f"Live OpenAI smoke test is disabled. Set {_OPT_IN_VARIABLE}=1 explicitly to run it."
        )


async def run() -> None:
    require_opt_in()
    settings = Settings()
    if settings.ai_provider != "openai":
        raise SystemExit("AI_PROVIDER=openai is required for the live smoke test.")

    task_id = uuid.uuid4()
    organization_id = uuid.uuid4()
    gateway = create_model_gateway(settings)
    result = await gateway.generate(
        ModelRequest(
            system_prompt="Return the requested release health object only.",
            user_instruction="Report the service as ready for a connectivity smoke test.",
            output_schema={
                "type": "object",
                "properties": {
                    "status": {"type": "string", "enum": ["ready"]},
                },
                "required": ["status"],
                "additionalProperties": False,
            },
            timeout_seconds=settings.openai_timeout_seconds,
            model_id=settings.openai_model,
            transmission_context=ProviderTransmissionContext(
                organization_id=organization_id,
                authorized_organization_id=organization_id,
                user_id=uuid.uuid4(),
                task_id=task_id,
                data_classification=DataClassification.PUBLIC,
            ),
        )
    )
    print(
        json.dumps(
            {
                "provider_response_id": result.provider_request_id,
                "model": result.usage.model,
                "latency_ms": result.usage.duration_ms,
                "input_tokens": result.usage.input_tokens,
                "output_tokens": result.usage.output_tokens,
                "total_tokens": result.usage.total_tokens,
                "cached_input_tokens": result.usage.cached_input_tokens,
            },
            sort_keys=True,
        )
    )


def main() -> None:
    asyncio.run(run())


if __name__ == "__main__":
    main()