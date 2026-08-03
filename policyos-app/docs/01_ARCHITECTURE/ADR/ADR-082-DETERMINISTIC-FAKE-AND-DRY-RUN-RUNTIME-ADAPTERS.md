# ADR-082: Deterministic Fake and Dry-Run Runtime Adapters

## Status

Accepted for Sprint 15 CP6 Runtime Adapters implementation.

## Context

ADR-065 places adapter implementations downstream of Runtime Ports. ADR-072 requires fake and
dry-run adapters before any live model, provider, MCP, connector, or internal-action integration.
ADR-079 defines `RuntimeAdapterPort` and its reference-only invocation and result contracts.
ADR-080 completes the adapter-facing policy selector binding. ADR-081 makes Orchestration the
only application boundary that revalidates authority, permits, state, registry, audit,
cancellation, credentials, and time before invoking exactly one adapter.

CP6 must prove that a concrete adapter can implement this boundary without adding a second
policy engine or introducing external effects. Existing adapters in `app.execution`,
`app.ai_providers`, `app.knowledge`, `app.mcp`, and `app.connectors` use earlier contracts and
cannot silently acquire Sprint 15 authority.

## Decision

Create `app.runtime.adapters` with two deterministic, per-invocation implementations of
`RuntimeAdapterPort`:

- `FakeRuntimeAdapter` returns one caller-supplied bounded result for one exact immutable
  invocation envelope.
- `DryRunRuntimeAdapter` has the same behavior and additionally requires both the plan mode and
  execution environment to be exactly `DRY_RUN`.

Each adapter instance is a frozen, slotted value bound to a complete caller-supplied
`RuntimeAdapterInvocationEnvelope` and `RuntimeAdapterInvocationResult`. Construction validates
the result against the envelope. Invocation compares the entire supplied envelope for equality
before returning the validated result. No field is inferred, normalized, generated, or repaired.

The same implementations cover the closed model, provider, MCP, connector, and internal-action
adapter families because the exact family remains part of the immutable envelope. They do not
perform family-specific integration or dynamic dispatch.

## Exact binding and authority boundary

Whole-envelope equality preserves the exact adapter identity and version, action identity and
version, registry snapshot and resolution, schemas, policy selectors, destination, permits,
input and digest references, idempotency key, state, tenant, organization, actor, attempt,
classification, lineage, revisions, cancellation reference, credential lease reference, request
time, and deadline. Any substitution fails before a result is returned.

An adapter does not approve, authorize, issue or revalidate a permit, admit execution, select an
action, progress state, append audit, decide retry, perform cancellation, start compensation, or
claim result correctness. Immediate permit, cancellation, credential lease, and clock validation
remain owned by the merged Orchestration boundary. Adapter selection remains an exact Registry
fact and grants no authority.

## Fake and dry-run behavior

Fake behavior is an observed deterministic test fact, not a real external effect. It may return
caller-supplied succeeded, failed, timed-out, cancelled, or ambiguous results that already satisfy
the Ports result contract. It keeps no call history, mutable registry, callback, or hidden state.

Dry-run behavior performs no external side effect. A dry-run success means only that the supplied
dry-run result passed the immutable boundary. It is not admission, current permit validity,
future live execution success, publication, transmission, deployment, or correctness.

## Sensitive-data and credential boundary

Adapters receive only the approved reference-only Ports envelope. They contain no raw prompt,
chain-of-thought, model output, source-document content, provider payload, password, token, API
key, private key, credential value, client, executable callback, dynamic import path, or arbitrary
metadata dictionary. They retain no credential broker, credential request, or credential lease
object. An optional opaque credential lease identifier remains only inside the immutable expected
envelope.

## Dependency direction and package placement

`app.runtime.adapters` implements contracts from `app.runtime.ports` and may compare the stable
Authority and Planning mode enums carried by those contracts. Runtime domain, Audit, Ports, and
Orchestration packages do not import Adapters. API and workers must continue calling
Orchestration rather than importing an adapter directly.

Adapters import no existing provider/model/MCP/connector implementation, SDK, FastAPI,
SQLAlchemy, Redis, repository, transaction, outbox, worker, scheduler, filesystem, network,
environment, logging, or subprocess facility. Existing earlier adapter packages remain unchanged.

## Determinism

All identifiers, timestamps, digests, references, scopes, results, failures, and artifacts are
caller-supplied immutable values. The implementations perform no clock reads, UUID generation,
hashing, randomness, sorting, deduplication, filesystem, database, queue, network, environment,
logging, or subprocess operation.

## Verification

Focused tests cover all five adapter families, exact-envelope substitution rejection, result
binding, dry-run mode enforcement, immutable configuration, typed non-success outcomes, explicit
exports, zero external dependencies, and sensitive-data exclusions. Combined CP0 through CP6
tests retain the existing Orchestration evidence that expired authority fails before adapter
invocation.

## Alternatives considered

### Reuse earlier provider or connector adapters directly

Rejected because those packages use different request, authority, payload, credential, and result
contracts. Direct reuse could make earlier execution metadata appear authorized by Sprint 15.

### Generate fake identifiers, timestamps, or results

Rejected because hidden construction would make tests nondeterministic and allow the adapter to
invent execution facts.

### Add a production adapter registry or factory

Rejected because Registry already owns exact adapter selection metadata and CP6 prohibits adapter
self-registration or dynamic discovery.

### Enable a live provider in the first CP6 change

Rejected because fake and dry-run evidence, a separate threat review, destination enforcement,
tenant-bound credential resolution, and explicit enablement must precede every live integration.

## Consequences

PolicyOS gains concrete, independently testable Runtime Adapter implementations without enabling
external execution. Per-invocation construction is intentionally strict and verbose, but proves
that every adapter-facing fact can remain exact and reviewable. Later live adapters may implement
the same Port only through separate approval and security review.

## Deferred scope

Live model/provider/MCP/connector/internal-action adapters, compatibility bridges, provider SDKs,
network clients, credential-broker implementations, secret resolution, real clocks,
cancellation mechanisms, repositories, transactions, persistence, migrations, outbox storage or
delivery, API, workers, schedulers, automatic retries, compensation execution, project version
changes, releases, and Git tags remain deferred.
