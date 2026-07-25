"""Organization-scoped connector endpoints."""

from urllib.parse import urlsplit

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import OrganizationContext, require_permission
from app.connectors.repositories import (
    ConnectorConfigurationRepository,
    ConnectorHealthStateRepository,
    ConnectorSyncStateRepository,
)
from app.connectors.security import ConnectorSecurityPolicy
from app.connectors.services import (
    ConnectorConfigurationService,
    ConnectorServiceError,
    ConnectorSyncStateService,
)
from app.core.config import get_settings
from app.db.session import get_db
from app.schemas.connectors import (
    ConnectorConfigurationCreate,
    ConnectorConfigurationResponse,
    ConnectorConfigurationUpdate,
    ConnectorHealthResponse,
    ConnectorSyncRequest,
    ConnectorSyncStatusResponse,
)

router = APIRouter(prefix="/connectors", tags=["connectors"])


def service(db):
    settings = get_settings()
    origins = tuple(
        value.strip() for value in settings.connector_endpoint_allowlist.split(",") if value.strip()
    )
    return ConnectorConfigurationService(
        db,
        ConnectorSecurityPolicy(
            allowlist=origins,
            block_private_networks=settings.connector_block_private_networks,
        ),
    )


def response(item):
    parsed = urlsplit(item.endpoint_reference)
    port = "" if parsed.port in {None, 443} else f":{parsed.port}"
    return ConnectorConfigurationResponse(
        id=item.id,
        stable_name=item.stable_name,
        display_name=item.display_name,
        connector_type=item.connector_type,
        version=item.version,
        enabled=item.enabled,
        read_only=item.read_only,
        endpoint_origin=f"{parsed.scheme}://{parsed.hostname}{port}",
        credential_configured=bool(item.credential_reference),
        supported_operations=item.supported_operations,
        allowed_classifications=item.allowed_classifications,
        cache_enabled=item.cache_enabled,
        health_check_enabled=item.health_check_enabled,
        sync_enabled=item.sync_enabled,
        created_at=item.created_at,
        updated_at=item.updated_at,
    )


def error(exc):
    return HTTPException(
        status_code=exc.http_status,
        detail={"code": exc.code, "message": exc.safe_message},
    )


async def find(db, organization_id, name):
    item = await ConnectorConfigurationRepository(db).get_by_stable_name(organization_id, name)
    if item is None:
        raise HTTPException(status_code=404, detail="Connector not found")
    return item


@router.get("", response_model=list[ConnectorConfigurationResponse])
async def list_connectors(
    context: OrganizationContext = Depends(require_permission("connector.read")),
    db: AsyncSession = Depends(get_db),
):
    items = await ConnectorConfigurationRepository(db).list_for_organization(
        context.organization_id
    )
    return [response(item) for item in items]


@router.post("", response_model=ConnectorConfigurationResponse, status_code=201)
async def create_connector(
    payload: ConnectorConfigurationCreate,
    context: OrganizationContext = Depends(require_permission("connector.manage")),
    db: AsyncSession = Depends(get_db),
):
    try:
        return response(await service(db).create(context.organization_id, context.user.id, payload))
    except ConnectorServiceError as exc:
        raise error(exc) from exc


@router.get("/{name}", response_model=ConnectorConfigurationResponse)
async def get_connector(
    name: str,
    context: OrganizationContext = Depends(require_permission("connector.read")),
    db: AsyncSession = Depends(get_db),
):
    return response(await find(db, context.organization_id, name))


@router.patch("/{name}", response_model=ConnectorConfigurationResponse)
async def update_connector(
    name: str,
    payload: ConnectorConfigurationUpdate,
    context: OrganizationContext = Depends(require_permission("connector.manage")),
    db: AsyncSession = Depends(get_db),
):
    try:
        return response(await service(db).update(context.organization_id, name, payload))
    except ConnectorServiceError as exc:
        raise error(exc) from exc


async def set_enabled(name, enabled, context, db):
    try:
        return response(await service(db).set_enabled(context.organization_id, name, enabled))
    except ConnectorServiceError as exc:
        raise error(exc) from exc


@router.post("/{name}/enable", response_model=ConnectorConfigurationResponse)
async def enable_connector(
    name: str,
    context: OrganizationContext = Depends(require_permission("connector.manage")),
    db: AsyncSession = Depends(get_db),
):
    return await set_enabled(name, True, context, db)


@router.post("/{name}/disable", response_model=ConnectorConfigurationResponse)
async def disable_connector(
    name: str,
    context: OrganizationContext = Depends(require_permission("connector.manage")),
    db: AsyncSession = Depends(get_db),
):
    return await set_enabled(name, False, context, db)


@router.post("/{name}/sync", response_model=ConnectorSyncStatusResponse)
async def start_sync(
    name: str,
    payload: ConnectorSyncRequest,
    context: OrganizationContext = Depends(require_permission("connector.sync")),
    db: AsyncSession = Depends(get_db),
):
    item = await find(db, context.organization_id, name)
    if not item.enabled or not item.sync_enabled:
        raise HTTPException(status_code=409, detail="Connector sync disabled")
    try:
        return await ConnectorSyncStateService(db).start(
            context.organization_id, item.id, payload.sync_key, payload.sync_key
        )
    except ValueError as exc:
        raise HTTPException(status_code=409, detail="Connector sync already running") from exc


@router.get("/{name}/sync-status", response_model=ConnectorSyncStatusResponse)
async def sync_status(
    name: str,
    sync_key: str = "default",
    context: OrganizationContext = Depends(require_permission("connector.read")),
    db: AsyncSession = Depends(get_db),
):
    item = await find(db, context.organization_id, name)
    state = await ConnectorSyncStateRepository(db).get(context.organization_id, item.id, sync_key)
    if state is None:
        raise HTTPException(status_code=404, detail="Connector sync state not found")
    return state


@router.get("/{name}/health", response_model=ConnectorHealthResponse)
async def health(
    name: str,
    context: OrganizationContext = Depends(require_permission("connector.read")),
    db: AsyncSession = Depends(get_db),
):
    item = await find(db, context.organization_id, name)
    state = await ConnectorHealthStateRepository(db).get(context.organization_id, item.id)
    if state is None:
        raise HTTPException(status_code=404, detail="Connector health not found")
    return state
