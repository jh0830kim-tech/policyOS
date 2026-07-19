from typing import Annotated

from fastapi import Depends

from app.api.deps import OrganizationContext, require_permission
from app.main import app

PROTECTED_TEST_PATH = "/_test/organizations/{organization_id}/policy-read"


@app.get(PROTECTED_TEST_PATH, include_in_schema=False)
async def protected_test_route(
    context: Annotated[OrganizationContext, Depends(require_permission("policy.read"))],
) -> dict[str, str]:
    """Exercise the production authentication and RBAC dependency chain in tests."""
    return {"organization_id": str(context.organization_id)}
