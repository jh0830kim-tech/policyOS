"""Safe errors for multi-agent role and delegation contracts."""


class AgentDomainError(Exception):
    code = "agent_domain_error"


class AgentDefinitionError(AgentDomainError):
    code = "agent_definition_error"


class AgentCatalogError(AgentDomainError):
    code = "agent_catalog_error"


class DuplicateAgentDefinitionError(AgentCatalogError):
    code = "duplicate_agent_definition"


class UnknownAgentError(AgentCatalogError):
    code = "unknown_agent"


class DelegationError(AgentDomainError):
    code = "delegation_error"


class DelegationIdentityError(DelegationError):
    code = "delegation_identity_error"


class DelegationClassificationError(DelegationError):
    code = "delegation_classification_error"


class AgentAssignmentError(DelegationError):
    code = "agent_assignment_error"


class AgentWorkProductError(DelegationError):
    code = "agent_work_product_error"
