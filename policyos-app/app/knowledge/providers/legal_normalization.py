"""Normalize validated Korean Law MCP data into legal and knowledge evidence."""

from __future__ import annotations

import hashlib
from datetime import UTC, date, datetime
from typing import Any, Literal

from pydantic import Field, model_validator

from app.ai.privacy import DataClassification
from app.knowledge.providers.domain import (
    KnowledgeEvidence,
    KnowledgeProviderType,
    KnowledgeProviderWarning,
    ProviderModel,
)
from app.knowledge.providers.korean_law import KOREAN_LAW_PROVIDER_NAME
from app.knowledge.providers.korean_law_mcp import KoreanLawMcpRawResponse
from app.knowledge.providers.scoring import (
    EvidenceConfidenceService,
    EvidenceFreshnessService,
)


class LegalNormalizationError(ValueError):
    code = "legal_normalization_error"


class LegalItem(ProviderModel):
    item_number: str = Field(min_length=1, max_length=100)
    text: str = Field(min_length=1, max_length=20_000)


class LegalParagraph(ProviderModel):
    paragraph_number: str = Field(min_length=1, max_length=100)
    text: str = Field(min_length=1, max_length=20_000)
    items: tuple[LegalItem, ...] = ()


class LegalArticle(ProviderModel):
    article_number: str = Field(min_length=1, max_length=100)
    title: str | None = Field(default=None, max_length=500)
    text: str = Field(default="", max_length=50_000)
    paragraphs: tuple[LegalParagraph, ...] = ()


class LegalVersion(ProviderModel):
    version_id: str = Field(min_length=1, max_length=500)
    effective_date: date | None = None
    proclamation_date: date | None = None
    end_date: date | None = None
    current: bool = False

    @model_validator(mode="after")
    def valid_range(self):
        if self.effective_date and self.end_date and self.effective_date > self.end_date:
            raise ValueError("Legal version date range is invalid")
        return self


class LegalRelationship(ProviderModel):
    relationship_type: str = Field(min_length=1, max_length=100)
    target_resource_id: str = Field(min_length=1, max_length=500)
    description: str | None = Field(default=None, max_length=1000)


class LegalTemporalMetadata(ProviderModel):
    effective_date: date | None = None
    decision_date: date | None = None
    proclamation_date: date | None = None
    retrieved_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    current_version: str | None = Field(default=None, max_length=500)
    temporal_match: bool = True
    warnings: tuple[str, ...] = ()


class LegalResource(ProviderModel):
    resource_id: str = Field(min_length=1, max_length=500)
    source_type: str
    authority: str = Field(default="unknown", max_length=500)
    title: str = Field(min_length=1, max_length=1000)
    safe_excerpt: str = Field(default="", max_length=2000)
    official_source: bool = True
    source_url: str | None = Field(default=None, max_length=2000)
    jurisdiction: str | None = Field(default=None, max_length=200)
    temporal: LegalTemporalMetadata
    articles: tuple[LegalArticle, ...] = ()
    versions: tuple[LegalVersion, ...] = ()
    relationships: tuple[LegalRelationship, ...] = ()
    metadata_allowlist: dict[str, Any] = Field(default_factory=dict)


class LawResource(LegalResource):
    source_type: Literal["law"] = "law"


class CaseResource(LegalResource):
    source_type: Literal["case"] = "case"
    case_number: str | None = Field(default=None, max_length=200)
    court: str | None = Field(default=None, max_length=500)


class AdministrativeRuleResource(LegalResource):
    source_type: Literal["administrative_rule"] = "administrative_rule"
    rule_number: str | None = Field(default=None, max_length=200)


class LocalOrdinanceResource(LegalResource):
    source_type: Literal["local_ordinance"] = "local_ordinance"
    local_government: str | None = Field(default=None, max_length=500)


class LegalInterpretationResource(LegalResource):
    source_type: Literal["legal_interpretation"] = "legal_interpretation"
    interpretation_number: str | None = Field(default=None, max_length=200)


class LegalCitation(ProviderModel):
    source_type: str
    resource_id: str
    label: str = Field(min_length=1, max_length=2000)
    article_locator: str | None = Field(default=None, max_length=200)
    complete: bool
    warnings: tuple[str, ...] = ()


class LegalEvidence(ProviderModel):
    resource: LegalResource
    citation: LegalCitation
    knowledge_evidence: KnowledgeEvidence
    temporal: LegalTemporalMetadata
    warnings: tuple[KnowledgeProviderWarning, ...] = ()


class LegalCitationBuilder:
    def build(self, resource: LegalResource) -> LegalCitation:
        locator = resource.articles[0].article_number if resource.articles else None
        temporal = resource.temporal
        parts = [resource.title]
        warnings = []
        if isinstance(resource, CaseResource):
            parts.extend(
                value
                for value in (
                    resource.court or resource.authority,
                    resource.case_number or resource.resource_id,
                    _date_label("decided", temporal.decision_date),
                )
                if value
            )
            complete = bool(resource.case_number and temporal.decision_date)
        elif isinstance(resource, LocalOrdinanceResource):
            parts.extend(
                value
                for value in (
                    resource.local_government or resource.authority,
                    locator,
                    _date_label("effective", temporal.effective_date),
                )
                if value
            )
            complete = bool(
                (resource.local_government or resource.authority != "unknown")
                and temporal.effective_date
            )
        elif isinstance(resource, AdministrativeRuleResource):
            parts.extend(
                value
                for value in (
                    resource.authority,
                    resource.rule_number or resource.resource_id,
                    locator,
                    _date_label("effective", temporal.effective_date),
                )
                if value
            )
            complete = bool(resource.rule_number and temporal.effective_date)
        elif isinstance(resource, LegalInterpretationResource):
            parts.extend(
                value
                for value in (
                    resource.authority,
                    resource.interpretation_number or resource.resource_id,
                    _date_label(
                        "issued",
                        temporal.decision_date or temporal.proclamation_date,
                    ),
                )
                if value
            )
            complete = bool(
                resource.interpretation_number
                and (temporal.decision_date or temporal.proclamation_date)
            )
        else:
            parts.extend(
                value
                for value in (
                    resource.authority,
                    locator,
                    _date_label("effective", temporal.effective_date),
                )
                if value
            )
            complete = bool(resource.authority != "unknown" and temporal.effective_date)
        if not locator and isinstance(resource, (LawResource, LocalOrdinanceResource)):
            warnings.append("article_locator_missing")
        if not complete:
            warnings.append("citation_incomplete")
        return LegalCitation(
            source_type=resource.source_type,
            resource_id=resource.resource_id,
            label=", ".join(dict.fromkeys(str(value) for value in parts if value)),
            article_locator=locator,
            complete=complete,
            warnings=tuple(warnings),
        )


def _date_label(prefix: str, value: date | None) -> str | None:
    return f"{prefix} {value.isoformat()}" if value else None


def _parse_date(value: Any, field_name: str) -> date | None:
    if value is None or value == "":
        return None
    if isinstance(value, date) and not isinstance(value, datetime):
        return value
    try:
        return date.fromisoformat(str(value))
    except ValueError as exc:
        raise LegalNormalizationError(f"Invalid {field_name}") from exc


def _parse_datetime(value: Any) -> datetime:
    if value is None or value == "":
        return datetime.now(UTC)
    if isinstance(value, datetime):
        parsed = value
    else:
        try:
            parsed = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
        except ValueError as exc:
            raise LegalNormalizationError("Invalid retrieved_at") from exc
    return parsed if parsed.tzinfo else parsed.replace(tzinfo=UTC)


class KoreanLawLegalNormalizer:
    def __init__(
        self,
        *,
        citation_builder: LegalCitationBuilder | None = None,
        confidence_service: EvidenceConfidenceService | None = None,
        freshness_service: EvidenceFreshnessService | None = None,
    ) -> None:
        self.citations = citation_builder or LegalCitationBuilder()
        self.confidence = confidence_service or EvidenceConfidenceService()
        self.freshness = freshness_service or EvidenceFreshnessService()

    def normalize(
        self,
        response: KoreanLawMcpRawResponse,
        *,
        requested_effective_date: date | None = None,
        cache_status: str = "miss",
        classification: DataClassification = DataClassification.PUBLIC,
    ) -> tuple[LegalEvidence, ...]:
        resources = [self._resource(item, requested_effective_date) for item in response.items]
        self._require_unique_identifiers(resources)
        conflict_ids = self._temporal_conflicts(resources)
        return tuple(
            self._evidence(
                resource,
                response_warnings=response.warnings,
                conflict=resource.resource_id in conflict_ids
                or resource.metadata_allowlist.get("canonical_id") in conflict_ids,
                requested_effective_date=requested_effective_date,
                cache_status=cache_status,
                classification=classification,
            )
            for resource in resources
        )

    def _resource(
        self, item: dict[str, Any], requested_effective_date: date | None
    ) -> LegalResource:
        effective_date = _parse_date(item.get("effective_date"), "effective_date")
        decision_date = _parse_date(item.get("decision_date"), "decision_date")
        proclamation_date = _parse_date(item.get("proclamation_date"), "proclamation_date")
        retrieved_at = _parse_datetime(item.get("retrieved_at"))
        temporal_warnings = []
        temporal_match = not (
            requested_effective_date
            and effective_date
            and effective_date > requested_effective_date
        )
        if not temporal_match:
            temporal_warnings.append("temporal_mismatch")
        if not (effective_date or decision_date or proclamation_date):
            temporal_warnings.append("legal_date_missing")
        temporal = LegalTemporalMetadata(
            effective_date=effective_date,
            decision_date=decision_date,
            proclamation_date=proclamation_date,
            retrieved_at=retrieved_at,
            current_version=_optional_string(item.get("current_version"), 500),
            temporal_match=temporal_match,
            warnings=tuple(temporal_warnings),
        )
        source_type = str(item["source_type"])
        common = {
            "resource_id": str(item["resource_id"]),
            "authority": _optional_string(item.get("authority"), 500) or "unknown",
            "title": _optional_string(item.get("title"), 1000) or "Untitled legal resource",
            "safe_excerpt": self._excerpt(item),
            "official_source": bool(item.get("official_source", True)),
            "source_url": _optional_string(item.get("source_url"), 2000),
            "jurisdiction": _optional_string(item.get("jurisdiction"), 200),
            "temporal": temporal,
            "articles": self._articles(item.get("articles", ())),
            "versions": self._versions(item.get("versions", ())),
            "relationships": self._relationships(item.get("relationships", ())),
            "metadata_allowlist": {
                key: item[key]
                for key in ("canonical_id", "language", "document_type")
                if key in item and isinstance(item[key], (str, int, bool))
            },
        }
        resource_types = {
            "law": (LawResource, {}),
            "case": (
                CaseResource,
                {
                    "case_number": _optional_string(item.get("case_number"), 200),
                    "court": _optional_string(item.get("court"), 500),
                },
            ),
            "administrative_rule": (
                AdministrativeRuleResource,
                {"rule_number": _optional_string(item.get("rule_number"), 200)},
            ),
            "local_ordinance": (
                LocalOrdinanceResource,
                {"local_government": _optional_string(item.get("local_government"), 500)},
            ),
            "legal_interpretation": (
                LegalInterpretationResource,
                {"interpretation_number": _optional_string(item.get("interpretation_number"), 200)},
            ),
        }
        try:
            model, specialized = resource_types[source_type]
        except KeyError as exc:
            raise LegalNormalizationError("Unsupported legal source type") from exc
        return model(**common, **specialized)

    @staticmethod
    def _excerpt(item):
        value = item.get("safe_excerpt") or item.get("excerpt") or item.get("content") or ""
        if not isinstance(value, str):
            raise LegalNormalizationError("Legal content must be text")
        return value[:2000]

    @staticmethod
    def _articles(values) -> tuple[LegalArticle, ...]:
        if not values:
            return ()
        if not isinstance(values, (list, tuple)):
            raise LegalNormalizationError("Articles must be a collection")
        try:
            return tuple(LegalArticle.model_validate(value) for value in values)
        except ValueError as exc:
            raise LegalNormalizationError("Invalid legal article") from exc

    @staticmethod
    def _versions(values) -> tuple[LegalVersion, ...]:
        if not values:
            return ()
        if not isinstance(values, (list, tuple)):
            raise LegalNormalizationError("Versions must be a collection")
        try:
            return tuple(LegalVersion.model_validate(value) for value in values)
        except ValueError as exc:
            raise LegalNormalizationError("Invalid legal version") from exc

    @staticmethod
    def _relationships(values) -> tuple[LegalRelationship, ...]:
        if not values:
            return ()
        if not isinstance(values, (list, tuple)):
            raise LegalNormalizationError("Relationships must be a collection")
        try:
            return tuple(LegalRelationship.model_validate(value) for value in values)
        except ValueError as exc:
            raise LegalNormalizationError("Invalid legal relationship") from exc

    @staticmethod
    def _require_unique_identifiers(resources) -> None:
        identifiers = [resource.resource_id for resource in resources]
        if len(set(identifiers)) != len(identifiers):
            raise LegalNormalizationError("Duplicate legal resource identifier")

    @staticmethod
    def _temporal_conflicts(resources) -> set[str]:
        grouped: dict[str, set[tuple[date | None, str | None]]] = {}
        for resource in resources:
            canonical_id = str(
                resource.metadata_allowlist.get("canonical_id") or resource.resource_id
            )
            grouped.setdefault(canonical_id, set()).add(
                (
                    resource.temporal.effective_date,
                    resource.temporal.current_version,
                )
            )
        return {identifier for identifier, versions in grouped.items() if len(versions) > 1}

    def _evidence(
        self,
        resource,
        *,
        response_warnings,
        conflict,
        requested_effective_date,
        cache_status,
        classification,
    ):
        citation = self.citations.build(resource)
        warnings = [
            KnowledgeProviderWarning(code=value, message=_warning_message(value))
            for value in (
                *response_warnings,
                *resource.temporal.warnings,
                *citation.warnings,
            )
        ]
        if conflict:
            warnings.append(
                KnowledgeProviderWarning(
                    code="legal_version_conflict",
                    message="Conflicting legal versions were preserved for review",
                )
            )
        content_hash = hashlib.sha256(resource.safe_excerpt.encode()).hexdigest()
        knowledge = KnowledgeEvidence(
            source_type=resource.source_type,
            authority=resource.authority,
            title=resource.title,
            safe_excerpt=resource.safe_excerpt,
            citation=citation.label,
            resource_id=resource.resource_id,
            official_source=resource.official_source,
            effective_date=resource.temporal.effective_date,
            published_at=_as_datetime(
                resource.temporal.decision_date or resource.temporal.proclamation_date
            ),
            retrieved_at=resource.temporal.retrieved_at,
            confidence=0,
            freshness="unknown",
            provenance=f"mcp:{KOREAN_LAW_PROVIDER_NAME}",
            provider_name=KOREAN_LAW_PROVIDER_NAME,
            provider_type=KnowledgeProviderType.MCP,
            content_hash=content_hash,
            classification=classification,
            warnings=tuple(dict.fromkeys(warnings)),
            metadata_allowlist={
                "citation_complete": citation.complete,
                "current_version": resource.temporal.current_version,
                "temporal_match": resource.temporal.temporal_match,
                **(
                    {"canonical_id": resource.metadata_allowlist["canonical_id"]}
                    if "canonical_id" in resource.metadata_allowlist
                    else {}
                ),
            },
        )
        freshness, freshness_warnings = self.freshness.evaluate(
            knowledge,
            effective_date=requested_effective_date,
            cache_status=cache_status,
        )
        confidence, confidence_warnings = self.confidence.evaluate(
            knowledge,
            temporal_match=resource.temporal.temporal_match,
            schema_valid=True,
            provider_healthy=True,
        )
        all_warnings = tuple(
            dict.fromkeys((*knowledge.warnings, *freshness_warnings, *confidence_warnings))
        )
        knowledge = knowledge.model_copy(
            update={
                "confidence": confidence,
                "freshness": freshness,
                "warnings": all_warnings,
            }
        )
        return LegalEvidence(
            resource=resource,
            citation=citation,
            knowledge_evidence=knowledge,
            temporal=resource.temporal,
            warnings=all_warnings,
        )


def _optional_string(value: Any, maximum: int) -> str | None:
    if value is None or value == "":
        return None
    if not isinstance(value, str):
        raise LegalNormalizationError("Legal metadata must be text")
    return value[:maximum]


def _as_datetime(value: date | None) -> datetime | None:
    return datetime.combine(value, datetime.min.time(), tzinfo=UTC) if value else None


def _warning_message(code: str) -> str:
    return {
        "prompt_injection_treated_as_data": "Untrusted instruction was retained as data",
        "executable_instruction_treated_as_data": "Executable-looking text was retained as data",
        "temporal_mismatch": "Legal evidence did not match the requested effective date",
        "legal_date_missing": "Legal date metadata is missing",
        "article_locator_missing": "Article locator is missing",
        "citation_incomplete": "Legal citation is incomplete",
    }.get(code, "Legal evidence requires review")
