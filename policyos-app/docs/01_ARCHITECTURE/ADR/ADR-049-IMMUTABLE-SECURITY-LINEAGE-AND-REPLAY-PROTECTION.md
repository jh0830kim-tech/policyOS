# ADR-049: Immutable Security Lineage and Replay Protection

## Status

Accepted for Sprint 13 CP0.6.

## Context

Delegated execution crosses model, provider, MCP, connector,
cross-validation, Secretary, and repository boundaries. Exact identity
continuity must be reproducible, repository permits must reject substituted
requests, and historical authorization decisions must retain the exact engine
and rule-set versions used. Agents must never receive secret material.

## Decision

PolicyOS represents delegated execution as canonical, immutable public
metadata facts. `POLICYOS_LINEAGE_CANONICAL_V1` serializes fields in an
explicit order using UTF-8 JSON, stable enum values, explicit nulls, compact
separators, and UTC timestamps. SHA-256 produces a deterministic lineage
digest.

Parent and child records bind lineage IDs, parent digests, protected identity
facts, target specialization, and monotonic stages. Cross-validation runs
retain a common root lineage while using distinct run, agent, child-lineage,
and credential-grant identities.

Repository requests and authorization decisions have separate canonical
digests. Replay-protected permits bind the exact request, delegated lineage,
decision digest, policy revision, authorization-engine identity/version, and
rule-set identity/version. Only immutable `ISSUED` permit facts authorize an
operation.

Credential material is represented by an opaque broker-issued reference bound
to tenant, organization, service, secret reference, secret revision, broker,
and broker contract version. PolicyOS does not read, hash, truncate, or derive
identifiers from credential material.

## Security qualification

A lineage digest provides continuity and mismatch detection. It is not a
signature and does not authenticate the producer. A metadata-only attestation
reference is reserved for future signed validation; CP0.6 implements no
signing, signature verification, key access, certificates, or PKI.

The broker material reference is metadata, not a secret hash. It contains no
secret, suffix, prefix, encrypted credential, or reversibly derived value.

Invalid contract input fails validation. It is not automatically classified
as a runtime attack. A caller may separately record a confirmed critical
`DELEGATION_IDENTITY_MISMATCH`, which uses the existing first-event quarantine
policy.

## Replay limitation

Exact digest and version binding prevents request, lineage, decision, and
authorization-version substitution. Durable one-time permit consumption
across processes requires persistent consumption state. CP0.6 deliberately
provides no mutable in-memory registry, persistent replay cache, or database.

A permit remains bound to the versions under which it was issued. A newer
policy or engine version does not retroactively mutate an immutable permit;
expiry, revocation, or caller-supplied consumed state controls usability.

## Consequences

- Security lineage and authorization decisions are forensically reproducible.
- Downstream integrations must preserve protected lineage.
- Audit records retain exact request, decision, secret-revision, broker, and
  version references without payloads.
- Contract complexity increases, while runtime infrastructure remains
  explicitly deferred.
