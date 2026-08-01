"""Sprint 14 CP1-A trusted source binding contract tests."""

from datetime import timedelta
from pathlib import Path

import pytest
from pydantic import ValidationError

from app.ai.privacy import DataClassification
from app.evaluation import build_evaluation_pipeline_record
from app.source_bindings import (
    TrustedBindingAuthority,
    TrustedBindingAuthorityType,
    TrustedMetadataOrigin,
    TrustedSourceAuthorityError,
    TrustedSourceBinding,
    TrustedSourceBindingAuditMetadata,
    TrustedSourceBindingBundle,
    TrustedSourceBindingBundleVersion,
    TrustedSourceBindingStatus,
    TrustedSourceBindingVersion,
    TrustedSourceGovernanceContext,
    TrustedSourceIdentityError,
    TrustedSourceIdentityReference,
    TrustedSourceLineageContext,
    TrustedSourceStatusError,
    TrustedSourceType,
    TrustedSupplementalCategory,
    build_trusted_source_binding,
    validate_trusted_source_binding,
)
from tests.test_evaluation_pipeline import pipeline_values
from tests.test_evaluation_planner import NOW, uid

ROOT = Path(__file__).resolve().parents[1]
TENANT = uid(91001)
ORG = uid(91002)
LINEAGE = uid(91003)
SOURCE_ID = uid(91020)
DIGEST = "lineage-digest"
VERSION = TrustedSourceBindingVersion(
    trusted_binding_version="binding-v1",
    trusted_binding_contract_version="contract-v1",
    trusted_binding_schema_version="trusted-source-binding-schema-v1",
)


def authority(authority_type=TrustedBindingAuthorityType.EVALUATION_GOVERNANCE):
    updates = {}
    if authority_type is TrustedBindingAuthorityType.MIGRATION_AUTHORITY:
        updates["migration_reference"] = "migration://approved/1"
    if authority_type is TrustedBindingAuthorityType.MANUAL_REVIEW_AUTHORITY:
        updates["manual_review_reference"] = "review://approved/1"
    return TrustedBindingAuthority(
        binding_authority_id=uid(91010),
        authority_type=authority_type,
        authority_name_reference="authority://governance",
        authority_version="1",
        authority_revision=1,
        policy_revision=1,
        tenant_id=TENANT,
        organization_id=ORG,
        classification=DataClassification.INTERNAL,
        created_at=NOW,
        **updates,
    )


def binding(
    *,
    source_type=TrustedSourceType.CROSS_VALIDATION_RUN_COLLECTION,
    source_id=SOURCE_ID,
    owner="app.cross_validation",
    categories=(
        TrustedSupplementalCategory.ORGANIZATION,
        TrustedSupplementalCategory.CLASSIFICATION,
        TrustedSupplementalCategory.LINEAGE,
    ),
    authority_type=TrustedBindingAuthorityType.EVALUATION_GOVERNANCE,
    status=TrustedSourceBindingStatus.ACTIVE,
    reasons=(),
    origin=TrustedMetadataOrigin.AUTHORITY_SUPPLIED,
    recorded_at=NOW,
):
    return TrustedSourceBinding(
        trusted_source_binding_id=uid(91030),
        source_identity=TrustedSourceIdentityReference(
            source_identity_reference_id=uid(91031),
            source_type=source_type,
            source_id=source_id,
            source_schema_version="source-schema-v1",
            source_owner_package=owner,
            created_at=NOW,
        ),
        governance_context=TrustedSourceGovernanceContext(
            tenant_id=TENANT,
            organization_id=ORG,
            classification=DataClassification.INTERNAL,
            policy_revision=1,
        ),
        lineage_context=TrustedSourceLineageContext(
            lineage_id=LINEAGE,
            lineage_digest_reference=DIGEST,
            lineage_schema_version="lineage-v1",
            source_recorded_at=recorded_at,
            bound_at=recorded_at + timedelta(seconds=1),
        ),
        binding_authority=authority(authority_type),
        binding_version=VERSION,
        binding_revision=1,
        status=status,
        metadata_origin=origin,
        supplemental_field_categories=categories,
        reason_codes=reasons,
        created_at=recorded_at + timedelta(seconds=2),
    )


def validate_incomplete(candidate):
    validate_trusted_source_binding(
        candidate,
        expected_type=TrustedSourceType.CROSS_VALIDATION_RUN_COLLECTION,
        expected_id=SOURCE_ID,
        owner_package="app.cross_validation",
        required_supplemental=(
            TrustedSupplementalCategory.ORGANIZATION,
            TrustedSupplementalCategory.CLASSIFICATION,
            TrustedSupplementalCategory.LINEAGE,
        ),
        native_tenant=TENANT,
        native_recorded_at=NOW,
    )


def test_contracts_are_strict_frozen_and_caller_supplied():
    item = binding()
    assert item.trusted_source_binding_id == uid(91030)
    assert item.model_config["frozen"] and item.model_config["strict"]
    assert item.model_config["extra"] == "forbid"
    with pytest.raises(ValidationError):
        item.binding_revision = 2
    values = item.model_dump()
    values["extra"] = True
    with pytest.raises(ValidationError):
        TrustedSourceBinding.model_validate(values)


def test_timestamps_are_aware_and_lineage_has_no_self_parent():
    values = binding().lineage_context.model_dump()
    values["bound_at"] = values["bound_at"].replace(tzinfo=None)
    with pytest.raises(ValidationError):
        TrustedSourceLineageContext.model_validate(values)
    values = binding().lineage_context.model_dump()
    values["parent_lineage_id"] = values["lineage_id"]
    values["parent_lineage_digest_reference"] = "parent"
    with pytest.raises(ValidationError):
        TrustedSourceLineageContext.model_validate(values)


def test_valid_authority_supplied_incomplete_binding_passes():
    validate_incomplete(binding())


@pytest.mark.parametrize(
    "authority_type",
    (
        TrustedBindingAuthorityType.SOURCE_DOMAIN,
        TrustedBindingAuthorityType.POLICY_ENGINE,
        TrustedBindingAuthorityType.ORGANIZATION_REGISTRY,
        TrustedBindingAuthorityType.TENANT_REGISTRY,
    ),
)
def test_overbroad_or_wrong_authority_fails(authority_type):
    with pytest.raises(TrustedSourceAuthorityError):
        validate_incomplete(binding(authority_type=authority_type))


def test_migration_and_manual_authorities_require_references():
    for authority_type, field in (
        (TrustedBindingAuthorityType.MIGRATION_AUTHORITY, "migration_reference"),
        (TrustedBindingAuthorityType.MANUAL_REVIEW_AUTHORITY, "manual_review_reference"),
    ):
        values = authority(authority_type).model_dump()
        values[field] = None
        with pytest.raises(ValidationError):
            TrustedBindingAuthority.model_validate(values)


def test_missing_or_conflicting_supplemental_categories_fail():
    with pytest.raises(TrustedSourceAuthorityError):
        validate_incomplete(binding(categories=()))
    with pytest.raises(TrustedSourceAuthorityError):
        validate_incomplete(binding(origin=TrustedMetadataOrigin.SOURCE_NATIVE))


@pytest.mark.parametrize(
    "status",
    (
        TrustedSourceBindingStatus.SUPERSEDED,
        TrustedSourceBindingStatus.REVOKED,
        TrustedSourceBindingStatus.INVALIDATED,
    ),
)
def test_inactive_bindings_cannot_be_used(status):
    item = binding(status=status, reasons=("inactive",))
    with pytest.raises(TrustedSourceStatusError):
        validate_incomplete(item)


def test_complete_evaluation_pipeline_binding_is_exact():
    pipeline = build_evaluation_pipeline_record(pipeline_values())
    complete = binding(
        source_type=TrustedSourceType.EVALUATION_PIPELINE_RECORD,
        source_id=pipeline.pipeline_id,
        owner="app.evaluation",
        categories=(),
        authority_type=TrustedBindingAuthorityType.SOURCE_DOMAIN,
        origin=TrustedMetadataOrigin.SOURCE_NATIVE,
        recorded_at=pipeline.created_at,
    ).model_copy(
        update={
            "governance_context": binding().governance_context.model_copy(
                update={
                    "tenant_id": pipeline.tenant_id,
                    "organization_id": pipeline.organization_id,
                    "classification": pipeline.classification,
                }
            ),
            "lineage_context": binding(recorded_at=pipeline.created_at).lineage_context.model_copy(
                update={
                    "lineage_id": pipeline.delegation_lineage_id,
                    "lineage_digest_reference": pipeline.delegation_lineage_digest,
                }
            ),
            "binding_authority": authority(TrustedBindingAuthorityType.SOURCE_DOMAIN).model_copy(
                update={
                    "tenant_id": pipeline.tenant_id,
                    "organization_id": pipeline.organization_id,
                    "classification": pipeline.classification,
                }
            ),
            "source_identity": binding(
                source_type=TrustedSourceType.EVALUATION_PIPELINE_RECORD,
                source_id=pipeline.pipeline_id,
                owner="app.evaluation",
            ).source_identity.model_copy(update={"source_revision": pipeline.registry_revision}),
        }
    )
    assert build_trusted_source_binding(complete, pipeline) is complete
    wrong = complete.model_copy(
        update={
            "source_identity": complete.source_identity.model_copy(update={"source_id": uid(91999)})
        }
    )
    with pytest.raises(TrustedSourceIdentityError):
        build_trusted_source_binding(wrong, pipeline)


def test_bundle_is_canonical_active_and_scope_bound():
    item = binding()
    audit = TrustedSourceBindingAuditMetadata(
        trusted_source_binding_id=item.trusted_source_binding_id,
        source_type=item.source_identity.source_type,
        source_id=item.source_identity.source_id,
        tenant_id=TENANT,
        organization_id=ORG,
        classification=item.governance_context.classification,
        lineage_id=LINEAGE,
        authority_id=item.binding_authority.binding_authority_id,
        authority_type=item.binding_authority.authority_type,
        binding_revision=1,
        status=item.status,
        supplemental_field_categories=item.supplemental_field_categories,
        created_at=item.created_at,
    )
    bundle = TrustedSourceBindingBundle(
        trusted_binding_bundle_id=uid(91040),
        bundle_version=TrustedSourceBindingBundleVersion(
            trusted_binding_bundle_version="bundle-v1",
            trusted_binding_bundle_contract_version="contract-v1",
            trusted_binding_bundle_schema_version="trusted-source-binding-bundle-schema-v1",
        ),
        bindings=(item,),
        tenant_id=TENANT,
        organization_id=ORG,
        classification=DataClassification.INTERNAL,
        root_lineage_id=LINEAGE,
        root_lineage_digest_reference=DIGEST,
        audit_metadata=(audit,),
        created_at=item.created_at,
    )
    assert bundle.bindings == (item,)
    values = bundle.model_dump()
    values["organization_id"] = uid(99999)
    with pytest.raises(ValidationError):
        TrustedSourceBindingBundle.model_validate(values)


def test_duplicate_source_identity_and_non_active_bundle_fail():
    first = binding()
    second = first.model_copy(update={"trusted_source_binding_id": uid(91032)})
    values = {
        "trusted_binding_bundle_id": uid(91040),
        "bundle_version": {
            "trusted_binding_bundle_version": "bundle-v1",
            "trusted_binding_bundle_contract_version": "contract-v1",
            "trusted_binding_bundle_schema_version": "trusted-source-binding-bundle-schema-v1",
        },
        "bindings": (first, second),
        "tenant_id": TENANT,
        "organization_id": ORG,
        "classification": DataClassification.INTERNAL,
        "root_lineage_id": LINEAGE,
        "root_lineage_digest_reference": DIGEST,
        "created_at": first.created_at,
    }
    with pytest.raises(ValidationError):
        TrustedSourceBindingBundle.model_validate(values)
    values["bindings"] = (binding(status=TrustedSourceBindingStatus.REVOKED, reasons=("revoked",)),)
    with pytest.raises(ValidationError):
        TrustedSourceBindingBundle.model_validate(values)


def test_public_api_is_explicit_and_runtime_boundaries_absent():
    import app.source_bindings as public

    assert isinstance(public.__all__, tuple)
    assert all(not name.startswith("_") for name in public.__all__)
    text = "\n".join(
        path.read_text(encoding="utf-8") for path in (ROOT / "app" / "source_bindings").glob("*.py")
    )
    for forbidden in (
        "datetime.now",
        "datetime.utcnow",
        "time.time",
        "uuid4",
        "hashlib",
        "requests",
        "httpx",
        "subprocess",
        "sqlalchemy",
        "FastAPI",
        "open(",
    ):
        assert forbidden not in text
