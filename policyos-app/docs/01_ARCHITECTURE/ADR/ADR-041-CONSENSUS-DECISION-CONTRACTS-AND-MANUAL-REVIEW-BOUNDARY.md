# ADR-041: Consensus Decision Contracts and Manual Review Boundary

## Status

Accepted for Sprint 12 Checkpoint 3.

## Decision

Consensus is a deterministic description of structural state, not a truth
determination. Only caller-supplied, validated CP2 claim comparison records are
eligible inputs. CP3 neither discovers claims nor groups them implicitly.

The explicit relation mapping and expected-comparison coverage determine status
using fail-closed precedence: explicit review policy, incomplete comparison,
conflict, evidence insufficiency, partial alignment, agreement, then no
consensus. Agreement counts do not establish correctness. There is no majority
or weighted voting, model ranking, truth score, evidence-quality score, or
hidden weighting.

Distinct run identity defines independent support. Repeated claims from one run
count once. Multiple runs of the same model remain distinct runs while retaining
one model identity. Contradictions remain unresolved until a separate manual
review occurs; review requirements do not approve or resolve anything.

All records retain exact plan, tenant, resource, registry revision, claim, run,
run-result, comparison, and classification lineage. Effective classification
cannot be lower than nested inputs. Audit records contain identifiers and bounded
enums only, never claim text, evidence content, model output, or reasoning.

Final-answer synthesis and Secretary integration are deferred to Sprint 12 CP4.
Evaluation and observability remain deferred to Sprint 13.
