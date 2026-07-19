# ADR-001 — Layered Modular Architecture

## Status
Accepted

## Decision
Use API, application service, domain, persistence, and AI orchestration boundaries.

## Rationale
This structure supports testing, security review, and gradual expansion without coupling FastAPI routes directly to persistence or model-provider code.
