# Core Table Dictionary

## organizations
Represents a council office, committee, public institution, or tenant.

## users
Stores user identity and account state. Password hashes only; never plain passwords.

## memberships
Connects users to organizations and carries organization-specific status.

## roles
Named authorization roles.

## permissions
Atomic capabilities such as `policy.read`, `policy.write`, or `admin.manage_members`.

## role_permissions
Many-to-many mapping between roles and permissions.

## membership_roles
Many-to-many mapping between organization membership and roles.

## policy_candidates
Stores policy ideas and their lifecycle state.

## audit_events
Planned table for actor, action, target, timestamp, organization, result, and metadata.
## Sprint 6 knowledge tables

- `knowledge_sources`: organization-owned source registry and classification.
- `knowledge_documents`: source-owned logical documents and current lifecycle metadata.
- `knowledge_document_versions`: immutable, content-hash-deduplicated document snapshots.
- `knowledge_chunks`: version-owned text units prepared for later retrieval.
- `knowledge_ingestion_jobs`: ingestion lifecycle and safe error metadata.
- `knowledge_access_policies`: organization/source/classification read policy records.
- `citation_references`: stable source, document, version, chunk, date, and locator lineage.

Organization is included in every parent-child foreign key. Deleting an organization cascades its knowledge hierarchy; user creator references remain restrictive. Citation-to-chunk deletion is restrictive so cited lineage is not silently orphaned.
