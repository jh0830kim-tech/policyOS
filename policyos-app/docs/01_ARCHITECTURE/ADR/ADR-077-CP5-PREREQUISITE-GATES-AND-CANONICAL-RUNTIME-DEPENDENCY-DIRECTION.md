# ADR-077: CP5 Prerequisite Gates and Canonical Runtime Dependency Direction

## Status

Accepted for Sprint 15 CP5 governance preparation.

## Context

ADR-065 makes Registry, Audit, and Ports inputs to Orchestration. The dependency summary in
`AGENTS.md` placed Orchestration before Registry and Ports, which could authorize a reverse
dependency or an incomplete CP5 implementation. CP4 resolved the Registry/Planning sequencing
exception in ADR-076, but Runtime Audit and Runtime Ports still have no implemented packages or
independent review units in the fixed CP0 through CP10 delivery sequence.

CP5 cannot safely combine Audit, Ports, and Orchestration in one change. Audit owns immutable
facts, Ports own implementation-neutral protocols, and Orchestration consumes both. Combining
them would obscure dependency direction and allow application behavior to define its own evidence
or infrastructure boundary.

## Decision

ADR-065 remains the architecture source of truth. This ADR does not supersede it. The
`AGENTS.md` dependency summary is corrected to match ADR-065 and the implemented ADR-076
exception: Planning does not import Registry, and their structural binding remains downstream.

The canonical import direction is:

1. Authority may consume approved Sprint 14 public contracts.
2. Planning and Registry may consume stable Authority contracts; Planning and Registry do not
   import each other.
3. State may consume Authority and Planning.
4. Audit may consume stable public Authority, Planning, State, and Registry contracts.
5. Ports may consume stable public runtime domain and Audit contracts.
6. Orchestration may consume Authority, Planning, State, Registry, Audit, and Ports.
7. Adapters and Persistence implement Ports. API and Workers call the approved
   application/orchestration boundary.

No upstream package may import a downstream consumer. Ports must not import Orchestration.
Orchestration must not define or implement its own repositories, adapters, credential broker,
clock, outbox storage, or audit transport.

## Governed review units

The fixed CP0 through CP10 numbering does not change. Two named prerequisite gates are inserted
before CP5 implementation:

1. **CP5-Gate-Audit** implements `app.runtime.audit` as immutable, append-only, safe event
   contracts and pure validation. It receives a dedicated implementation ADR and PR.
2. **CP5-Gate-Ports** implements `app.runtime.ports` as Protocol and immutable boundary contracts
   only. It starts after CP5-Gate-Audit merges and receives a dedicated implementation ADR and PR.

CP5 Orchestration remains blocked until both gates are merged and its application-boundary
contract is approved. These gates are not new numbered checkpoints and do not move CP6 through
CP10.

## Audit boundary

Audit is evidence, not authority. It never grants approval, authorization, permit, admission,
execution, state progression, retry, cancellation, compensation, or correctness. Audit events
contain allowlisted bounded references, exact tenant and organization, monotonic classification,
lineage, revisions, event identity and sequence, and caller-supplied aware timestamps. They contain
no raw prompts, model outputs, source content, provider payloads, credentials, tokens, secrets, or
arbitrary metadata dictionaries. CP5-Gate-Audit adds no sink, transport, database, filesystem,
network, queue, or logging implementation.

## Ports boundary

Ports define adapter invocation, bounded result/error, repository, transaction, outbox-storage,
clock, cancellation, and tenant-bound credential-broker contracts. Ports contain no concrete
adapter, repository, transaction manager, outbox dispatcher, clock, broker, client, SDK, database,
network, filesystem, environment lookup, secret value, or provider payload. Test doubles may live
in tests but are not production implementations.

Repository and outbox-storage implementations remain CP7 scope. Fake and dry-run adapter
implementations remain CP6 scope. Outbox delivery/package placement remains the separate R15-07
decision for CP8.

## Verification and merge gates

Each prerequisite gate must have its own clean branch, ADR, focused tests, explicit tuple exports,
dependency and sensitive-data guards, CP0 through current-gate regressions, import smoke,
dependency checks where required, and `git diff --check`. Each gate merges independently with
green CI. CP5 cannot use an unmerged gate contract.

## Consequences

The dependency contradiction is resolved without renumbering the Sprint or weakening ADR-065.
Audit facts cannot be invented by Orchestration, and infrastructure implementations cannot leak
into Ports. The additional PRs add review overhead but make CP5 independently testable and prevent
cycles.

## Deferred scope

This ADR creates no production package. Audit and Ports implementation, Orchestration, adapters,
persistence, outbox delivery, API, workers, real clocks, credentials, provider calls, project
version changes, releases, and Git tags remain deferred to their approved gates or checkpoints.
