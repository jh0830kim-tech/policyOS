"""Stable, content-safe errors for narrative domain contracts."""


class NarrativeContractError(ValueError):
    """Base error that never includes narrative or source payloads."""

    code = "narrative_contract_error"


class NarrativeIdentityError(NarrativeContractError):
    code = "narrative_identity_error"


class NarrativeSourceError(NarrativeContractError):
    code = "narrative_source_error"


class NarrativeClassificationError(NarrativeContractError):
    code = "narrative_classification_error"
