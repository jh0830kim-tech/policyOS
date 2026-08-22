# ADR-143: Gemini Registry Snapshot and Production Composition Ownership

## Status

Accepted for the Sprint 17 Gemini registry-composition governance gate.

## Context

ADR-142 makes `RegisteredModel.provider_model_name` the sole Gemini wire-resource owner. Current
office composition constructs a gateway from `Settings` alone and uses `gemini_model` as both
logical and wire identity. It receives no authoritative model-registry snapshot.

## Decision

The production application factory owns explicit injection of one caller-supplied immutable
`ModelRegistrySnapshot` and one exact logical model selection. The snapshot's caller-supplied ID
and revision remain authoritative. Configuration may identify the logical selection but cannot
create a snapshot, wire name, registration, alias, or fallback.

A pure composition binder receives those facts, performs no I/O, hidden time, mutation, sorting,
discovery, or latest selection, and requires exactly one active model plus its active Gemini
provider. It returns the exact logical `model_id` and
`RegisteredModel.provider_model_name`. Missing, stale, disabled, deprecated, cross-provider,
revision-mismatched, duplicate, or substituted facts fail before credential access, client
construction, or network I/O.

The construction order is immutable snapshot and selection, application factory, pure binder,
private gateway construction, then request-scoped invocation. The gateway receives both exact
strings but not the snapshot. It compares `ModelRequest.model_id` with the logical identity,
serializes only the wire resource, validates the response echo against the wire resource, and
returns and audits the logical identity.

This narrow bridge does not merge the office `ModelGateway` with `app.ai_providers`, create a
permit, or bypass ADR-037/038. `ModelRequest` and `ModelResponse` signatures remain unchanged.
Settings, environment, adapters, provider responses, first entries, current database heads, and
health checks cannot own or repair the binding. A second wire-model setting, prefix generation,
aliasing, fallback, and runtime refresh are prohibited.

## Follow-up implementation

A separately approved network-free gate may add the pure binder, expand internal factory
signatures, update the private Gemini gateway, and add focused construction/request/response tests.
It must first prove exact files and no public-contract change. A live probe remains separately
approved and changes only the outbound wire-model field.

## Schema and migration decision

The immutable registry contracts already exist. This gate adds no persistence, table, column,
backfill, normalization, schema, or migration `20260808_0025`. Alembic remains at the single head
`20260808_0024`.

## Rejected alternatives

- Add a separate Gemini wire-model environment variable.
- Prefix or strip a logical model inside the adapter.
- Build a synthetic snapshot during startup.
- Query or cache the latest registry row.
- Let a provider response select or repair model identity.
- Move the private adapter across public boundaries in this gate.

## ADR-144 route-composition amendment

ADR-144 resolves the concrete owner that this ADR left implicit. The application-construction
caller supplies one immutable AI Office dependency bundle, the application factory binds and
prebuilds one office composition, and an artifacts-router factory receives that exact composition.
`OfficeApplicationService` cannot reconstruct composition from settings per request. Missing or
partial Gemini dependencies fail application construction rather than creating mutable
`app.state`, module-global authority, synthetic snapshots, latest lookup, or endpoint fallback.
