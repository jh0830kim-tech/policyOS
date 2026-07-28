# ADR-040: Evidence and Claim Comparison Contracts

## Status

Accepted for Sprint 12 Checkpoint 2.

## Context

ADR-039 preserves independent authorization, execution, and result lineage for every model run.
Later consensus work needs explicit claim and evidence relationships without treating repeated
model statements as truth or exposing unrestricted provider output.

## Decision

Extend app.cross_validation with immutable claim, evidence-reference, claim-link, comparison, and
metadata-only audit contracts. Claims are caller-supplied bounded atomic propositions. Automated
claim extraction, semantic pairing, and similarity search are deferred.

Every claim retains exact plan, run, result, tenant, resource, registry, provider, and model
lineage. Claim sets contain claims from exactly one run result. Evidence is referenced by typed
source, stable source/version identity, locator, and classification; source content is not
embedded. Referencing evidence grants no access authorization. Model-output evidence must identify
its originating plan and run result and is not automatically treated as external factual evidence.

Claim-evidence relations and claim-comparison relations are explicit caller assessments. They
record structure but do not decide truth, credibility, legal validity, winner, or model priority.
Comparison pairs use canonical claim-ID orientation. Both symmetric and directional relations are
interpreted against that canonical left-to-right orientation, preventing duplicate unordered
pairs while retaining deterministic direction for REFINING and QUALIFYING.

Comparison classification is supplied explicitly and must not be lower than any included claim or
evidence classification, using the existing PolicyOS classification ordering. Collections report
only expected, completed, missing, and relation counts. Model agreement is neither consensus nor
correctness.

## Consequences and limitations

CP2 performs no claim extraction, NLP, embeddings, semantic comparison, evidence retrieval,
provider or connector invocation, automatic pairing, scoring, ranking, voting, consensus,
synthesis, persistence, evaluation, or observability. These contracts may feed a future consensus
engine; consensus contracts are deferred to Sprint 12 CP3.
