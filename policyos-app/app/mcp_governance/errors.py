"""Safe, bounded MCP governance errors."""


class McpGovernanceError(ValueError):
    """Base error for pure MCP governance validation."""


class McpRegistryError(McpGovernanceError):
    pass


class McpRegistryDuplicateError(McpRegistryError):
    pass


class McpRegistryNotFoundError(McpRegistryError):
    pass


class McpProtocolVersionError(McpGovernanceError):
    pass


class McpCapabilityError(McpGovernanceError):
    pass


class McpExtensionError(McpGovernanceError):
    pass


class McpAuthenticationCompatibilityError(McpGovernanceError):
    pass


class McpCompatibilityError(McpGovernanceError):
    pass


class McpAuthorizationError(McpGovernanceError):
    pass


class McpApprovalError(McpAuthorizationError):
    pass


class McpPermitError(McpAuthorizationError):
    pass


class McpInvocationError(McpGovernanceError):
    pass


class McpCrossValidationBindingError(McpGovernanceError):
    pass


class McpContractTestError(McpGovernanceError):
    pass


class McpMigrationError(McpGovernanceError):
    pass
