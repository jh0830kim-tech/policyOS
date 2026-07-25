"""Resolve persisted connector records into safe provider factory inputs."""

from __future__ import annotations

from app.connectors.repositories import ConnectorConfigurationRepository


class ConnectorProviderConfigurationResolver:
    """Reads organization-scoped connector records without resolving secret values."""

    def __init__(self, db) -> None:
        self.repository = ConnectorConfigurationRepository(db)

    async def list_enabled(self, organization_id):
        items = await self.repository.list_for_organization(organization_id)
        configurations = []
        for item in items:
            if not item.enabled:
                continue
            metadata = item.metadata_json or {}
            provider_type = metadata.get("provider_type")
            if provider_type not in {"mcp", "internal_knowledge"}:
                continue
            value = {
                "provider_name": item.stable_name,
                "provider_type": provider_type,
                "implementation_version": item.version,
                "priority": int(metadata.get("priority", 100)),
                "enabled": item.enabled,
                "source_types": tuple(metadata.get("source_types", ())),
                "capabilities": tuple(item.supported_operations),
                "organization_id": item.organization_id,
                "configuration_reference": f"connector:{item.id}",
                "fallback_group": metadata.get("fallback_group"),
                "health_state": "unknown",
            }
            if provider_type == "mcp":
                value.update(
                    {
                        "server_name": metadata.get("server_name", item.stable_name),
                        "operations": dict(metadata.get("operations", {})),
                        "allowed_tools": tuple(metadata.get("allowed_tools", ())),
                    }
                )
            configurations.append(value)
        return tuple(configurations)
