# Sprint 13 Release Checkpoint

## RC2 baseline

Sprint 13 CP0 through CP3 delivered MCP governance, zero-trust delegation and
lineage, immutable evaluation contracts, deterministic planning/execution/
evidence/validation/pipeline records, and immutable observability contracts.
RC1 failed because classification stopped before the pipeline-to-observation
binding. ADR-057 corrected the full chain and made classification required.

The RC2 public contract baseline is breaking for serialized plan, execution,
evidence, validation, pipeline, observation, observability bundle, and
deployment-stop records that gained required classification. Producers must
use new caller-supplied contract/schema identifiers (conventionally v2) where
those identifiers already exist. PolicyOS neither generates nor upgrades
versions. Contracts without version metadata do not gain synthetic metadata.

## Migration and security invariants

Legacy records without classification fail closed. Their owning persistence
system must supply classification from trusted historical metadata before
deserialization. Tenant, organization, identity, URI, resource, actor, and
content are not trusted classification sources. Records without such history
cannot be migrated safely and cannot enter observability source validation.

Effective classification uses only explicit classifications and retains the
most restrictive. Missing values fail. Redaction never lowers classification.
Tenant and organization, delegated user, service actor, agent instance,
authorization decision/revision, policy/registry revision, and lineage identity
and digest remain exact bindings. Authorization, human approval, and invocation
permits remain separate.

COMPLETED does not prove evidence validity. Validation PASSED does not prove
evaluation correctness. Observation does not authorize retrieval or perform
quarantine. DeploymentStopSignal performs no deployment action and cannot be
less restrictive than its triggering observation.

## Dependency and public API freeze

The dependency direction is evaluation to shared security/execution contracts,
then observability binds to evaluation and other source domains; evaluation
does not import observability. Package public surfaces use explicit tuples.
The evaluation classification helper stays internal. The MCP governance export
tuple and zero-trust lineage stage order are frozen against incidental mutation.

## Release verification and limitations

RC2 regression coverage is in `tests/test_sprint13_release.py`, together with
the CP0-CP3 and prior-sprint suites. The sole allowed platform exception is
`PermissionError [WinError 5]` below
`tests/.knowledge_tmp/policyos-ingest-*`; ingestion code, assertions, and
temporary-directory behavior are unchanged.

No runtime evaluation, provider or MCP invocation, persistence migration,
telemetry exporter, dashboard, alert, automatic quarantine, or automatic
deployment stopping is part of Sprint 13. Sprint 14 may begin only after RC2
focused and regression suites, Ruff, import smoke, dependency/API/security
inspections, and Git whitespace checks pass, and after the RC2 changes are
reviewed and merged.
