# Domain Model

## Identity context
- Organization
- User
- Membership
- Role
- Permission
- RolePermission
- MembershipRole

## Policy context
- PolicyCandidate
- ResearchBrief
- EvidenceItem
- Review
- Decision

## Document context
- Document
- DocumentVersion
- Attachment
- Citation
- Export

## AI context
- AgentDefinition
- AgentTask
- AgentRun
- ToolInvocation
- PromptVersion
- ModelResponse

## Governance context
- AuditEvent
- Approval
- DataClassification
- RetentionPolicy

## Core invariant
Every organization-scoped resource must be associated with an organization and accessed through validated membership.
