# ADR-047: Automatic Quarantine and Internal Deployment Stop Criteria

## Status

Accepted for Sprint 13 CP0.5.

## Decision

PolicyOS owns explicit internal deployment-stop criteria. The first confirmed
mandatory critical security violation immediately quarantines the smallest
exact provider/model/MCP/tool/connector/agent combination justified by the
event. No repeated-event threshold applies.

Immutable registry snapshots retain violation, quarantine-decision, and
release-decision lineage. Enforcement occurs before model, MCP, connector,
credential, and repository operations. New agent instances and retries do not
bypass a matching quarantine.

Release is never automatic. It requires remediation evidence, security review
evidence, an explicit separate reviewer, and a new registry revision. Release
does not erase audit history.

## Consequences

- Tenant quarantine remains tenant-scoped; global quarantine is explicit.
- Unrelated combinations remain executable.
- CP0.5 provides no mutable registry, persistence, or review workflow.
