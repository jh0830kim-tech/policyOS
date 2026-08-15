import os
from typing import Annotated

from fastapi import Depends

os.environ.setdefault("JWT_ISSUER", "https://issuer.policyos.test")
os.environ.setdefault("JWT_AUDIENCES", '["policyos-api-test"]')
os.environ.setdefault("RUNTIME_API_REQUIRED_AUDIENCE", "policyos-api-test")

from app.api.deps import OrganizationContext, require_permission  # noqa: E402
from app.core.config import get_settings  # noqa: E402
from app.main import app  # noqa: E402

get_settings.cache_clear()


PROTECTED_TEST_PATH = "/_test/organizations/{organization_id}/policy-read"


@app.get(PROTECTED_TEST_PATH, include_in_schema=False)
async def protected_test_route(
    context: Annotated[OrganizationContext, Depends(require_permission("policy.read"))],
) -> dict[str, str]:
    """Exercise the production authentication and RBAC dependency chain in tests."""
    return {"organization_id": str(context.organization_id)}
