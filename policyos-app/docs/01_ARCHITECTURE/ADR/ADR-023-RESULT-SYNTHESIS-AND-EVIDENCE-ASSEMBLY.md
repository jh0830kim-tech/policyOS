# ADR-023: Result Synthesis and Evidence Assembly

## Status

Accepted for Sprint 8 Checkpoint 6.

## Context

ADR-018 through ADR-022 establish execution plans, runtime state, provider resolution, safe
dispatch binding, and provider invocation. Completed step results need a deterministic,
provider-free path to an immutable `ExecutionResult` and a safe narrative input for Sprint 9.

## Decision

Add a synchronous, pure `ResultAssembler`. It accepts an immutable plan, a complete set of
terminal step results, and caller-supplied aware start/completion timestamps. It performs no
provider call, runtime transition, persistence, network access, UUID generation, or clock read.

Evidence identity is the case-folded, trimmed `(source, record_id)` pair. The evidence graph is
canonically ordered by that ID. Every original evidence object is retained in its node; duplicate
references produce one deterministic representative in the final result without mutating any
reference. Observable disagreements in title, URI, or classification become bounded conflict
records. Conflict detection never removes evidence and does not attempt semantic claim analysis.

Citations are ordered by canonical source ID and contain bounded labels only. Confidence uses
explicit integer rules based on evidence count, source diversity, citation completeness,
conflicts, and failed steps. Warning codes are stable, unique, and bounded. There is no random or
floating weighted score.

`NarrativeInput` contains successful step outputs, deduplicated evidence, citations, conflicts,
confidence, and warnings. It is JSON-safe and immutable but performs no narrative or LLM
generation. The assembled execution status respects required versus optional plan steps, metrics
are deterministically aggregated, and the narrative input is stored as the final output.

## Consequences

Assembly is replayable for identical inputs. Building the graph is linear in evidence count and
canonical ordering is `O(E log E)`, bounded to 500 evidence references. Conflict detection is
linear over bounded node variants. Semantic contradiction detection, claim extraction, LLM
narration, persistence, orchestration, and telemetry remain deferred to Sprint 9 or later.
