"""Focused, network-free guards for Sprint 16 Runtime governance."""

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def test_adr123_governs_initial_connector_credentials_and_acknowledgement() -> None:
    adr = (
        ROOT
        / "docs/01_ARCHITECTURE/ADR"
        / (
            "ADR-123-S16-RUNTIME-PRODUCTION-EXTERNAL-ADAPTER-CREDENTIAL-LEASE-"
            "MATERIALIZATION-AND-ACKNOWLEDGEMENT-OWNERSHIP.md"
        )
    ).read_text(encoding="utf-8")
    roadmap = (ROOT / "docs/01_ARCHITECTURE/RUNTIME-ROADMAP.md").read_text(encoding="utf-8")
    program = (ROOT / "docs/03_OPERATIONS/SPRINT-16-PROGRAM.md").read_text(encoding="utf-8")
    security = (ROOT / "docs/04_SECURITY/SECURITY.md").read_text(encoding="utf-8")
    combined = "\n".join((adr, roadmap, program, security))

    for required in (
        "first production Runtime adapter family is exactly `CONNECTOR`",
        "explicitly provisioned and approved HTTPS connector endpoint",
        "Dynamic URLs, caller-supplied endpoints, redirects",
        "request-local managed invocation capability",
        "asynchronous context manager with one invocation opportunity",
        "exactly-once cleanup",
        "HTTP status alone, including any `2xx`, is not sufficient",
        "stable provider-issued operation or resource identifier",
        "send boundary was not crossed",
        "remains `AMBIGUOUS`",
        "Only a provider-specific observation capability",
        "A different endpoint",
        "PolicyOS-wide exactly-once guarantee",
        "adds no schema or migration `20260808_0025`",
    ):
        assert required in combined

    for prohibited in (
        "dynamic URL is allowed",
        "follow provider redirects",
        "HTTP 2xx proves delivery",
        "store credential material",
        "automatic blind retry",
    ):
        assert prohibited not in combined

    assert not any((ROOT / "alembic/versions").glob("20260808_0025*"))


def test_adr125_governs_connector_provisioning_and_worker_handoff() -> None:
    adr = (
        ROOT
        / "docs/01_ARCHITECTURE/ADR"
        / (
            "ADR-125-S16-RUNTIME-CONNECTOR-PROVISIONING-CREDENTIAL-"
            "MATERIALIZATION-HANDOFF-AND-WORKER-INVOCATION-OWNERSHIP.md"
        )
    ).read_text(encoding="utf-8")
    adr114 = (
        ROOT
        / "docs/01_ARCHITECTURE/ADR"
        / (
            "ADR-114-CP10-RUNTIME-WORKER-PREPARED-DELIVERY-OWNERSHIP-"
            "EXACT-BINDING-AND-OUTCOME-SEQUENCING.md"
        )
    ).read_text(encoding="utf-8")
    adr119 = (
        ROOT
        / "docs/01_ARCHITECTURE/ADR"
        / ("ADR-119-CP10-RUNTIME-WORKER-PRE-INVOCATION-AUTHORITATIVE-REVALIDATION-OWNERSHIP.md")
    ).read_text(encoding="utf-8")
    roadmap = (ROOT / "docs/01_ARCHITECTURE/RUNTIME-ROADMAP.md").read_text(encoding="utf-8")
    program = (ROOT / "docs/03_OPERATIONS/SPRINT-16-PROGRAM.md").read_text(encoding="utf-8")
    security = (ROOT / "docs/04_SECURITY/SECURITY.md").read_text(encoding="utf-8")
    combined = "\n".join((adr, adr114, adr119, roadmap, program, security))

    for required in (
        "globally non-reusable `connector_provisioning_reference`",
        "exactly one enabled entry",
        "one canonical HTTPS endpoint",
        "change requires a new reference",
        "private materialization source",
        "`RuntimeConnectorMaterializationRequest`",
        "only for a closed invokable connector result",
        "accepts the exact `RuntimeConnectorMaterializationRequest`",
        "fresh observation-specific credential lease",
        "No database transaction is open",
        "replay/conflict call count zero",
        "no durable provisioning table",
        "migration `20260808_0025`",
    ):
        assert required in combined

    for prohibited in (
        "adapter may read production environment credentials",
        "delivery lease may be reused for reconciliation",
        "handoff may use mutable process state",
        "endpoint replacement may reuse its provisioning reference",
    ):
        assert prohibited not in combined.lower()

    assert not any((ROOT / "alembic/versions").glob("20260808_0025*"))


def test_connector_persistence_sufficiency_gate_reuses_exact_cp8_payloads() -> None:
    roadmap = (ROOT / "docs/01_ARCHITECTURE/RUNTIME-ROADMAP.md").read_text(encoding="utf-8")
    program = (ROOT / "docs/03_OPERATIONS/SPRINT-16-PROGRAM.md").read_text(encoding="utf-8")
    security = (ROOT / "docs/04_SECURITY/SECURITY.md").read_text(encoding="utf-8")
    serialization = (ROOT / "app/runtime/persistence/serialization.py").read_text(encoding="utf-8")
    registry_serialization = (ROOT / "app/runtime/persistence/registry_serialization.py").read_text(
        encoding="utf-8"
    )
    models = (ROOT / "app/runtime/persistence/models.py").read_text(encoding="utf-8")
    registry_models = (ROOT / "app/models/runtime_registry.py").read_text(encoding="utf-8")
    combined = "\n".join(
        (
            roadmap,
            program,
            security,
            serialization,
            registry_serialization,
            models,
            registry_models,
        )
    )

    for required in (
        "Sprint 16 connector persistence sufficiency",
        "`result_payload`",
        "`observation_payload`",
        "`request_payload`",
        "strict allowlisted serialization",
        "exact relational scope",
        "provider-operation table",
        "migration `20260808_0025`",
        "record_digest_reference",
    ):
        assert required in combined

    for prohibited in (
        "select the latest provider operation",
        "may persist credential secret",
        "may infer acknowledgement identity",
        "must backfill connector evidence",
    ):
        assert prohibited not in combined

    assert not any((ROOT / "alembic/versions").glob("20260808_0025*"))


def test_adr124_governs_connector_evidence_mapping_and_exact_lease_binding() -> None:
    adr = (
        ROOT
        / "docs/01_ARCHITECTURE/ADR"
        / (
            "ADR-124-S16-RUNTIME-CONNECTOR-ACKNOWLEDGEMENT-EVIDENCE-MAPPING-"
            "AND-CREDENTIAL-LEASE-EXACT-BINDING.md"
        )
    ).read_text(encoding="utf-8")
    adr85 = (
        ROOT
        / "docs/01_ARCHITECTURE/ADR"
        / "ADR-085-CP8-OUTBOX-PACKAGE-PLACEMENT-AND-EFFECT-DELIVERY-SEMANTICS.md"
    ).read_text(encoding="utf-8")
    adr86 = (
        ROOT
        / "docs/01_ARCHITECTURE/ADR"
        / "ADR-086-CP8-POSTGRESQL-EFFECT-DELIVERY-IMPLEMENTATION.md"
    ).read_text(encoding="utf-8")
    adr123 = (
        ROOT
        / "docs/01_ARCHITECTURE/ADR"
        / (
            "ADR-123-S16-RUNTIME-PRODUCTION-EXTERNAL-ADAPTER-CREDENTIAL-LEASE-"
            "MATERIALIZATION-AND-ACKNOWLEDGEMENT-OWNERSHIP.md"
        )
    ).read_text(encoding="utf-8")
    roadmap = (ROOT / "docs/01_ARCHITECTURE/RUNTIME-ROADMAP.md").read_text(encoding="utf-8")
    program = (ROOT / "docs/03_OPERATIONS/SPRINT-16-PROGRAM.md").read_text(encoding="utf-8")
    security = (ROOT / "docs/04_SECURITY/SECURITY.md").read_text(encoding="utf-8")
    combined = "\n".join((adr, adr85, adr86, adr123, roadmap, program, security))

    for required in (
        "`acknowledgement_reference` is the stable provider-issued operation",
        "`acknowledgement_digest_reference` is the digest of canonical, bounded",
        "`result_reference` is the caller-supplied bounded logical connector-result reference",
        "`AMBIGUOUS` requires bounded failure evidence and may",
        "acknowledgement pair when a provider identity was observed",
        "adapter family `CONNECTOR`, adapter reference, and adapter contract version",
        "connector provisioning reference and exact destination reference",
        "delivery-envelope identity and envelope digest reference",
        "stable effect identity and unchanged effect idempotency key",
        "cleanup failure cannot rewrite its",
        "delivery certainty",
        "No new table, column, uniqueness constraint",
    ):
        assert required in combined

    for prohibited in (
        "provider identity alone proves delivery",
        "select the latest provider operation",
        "store raw acknowledgement body",
        "infer the destination from the credential",
    ):
        assert prohibited not in combined

    assert not any((ROOT / "alembic/versions").glob("20260808_0025*"))


def test_managed_connector_public_contract_gate_is_bounded() -> None:
    connector = (ROOT / "app/runtime/ports/connector.py").read_text(encoding="utf-8")
    credentials = (ROOT / "app/runtime/ports/credentials.py").read_text(encoding="utf-8")
    delivery = (ROOT / "app/runtime/ports/delivery.py").read_text(encoding="utf-8")
    roadmap = (ROOT / "docs/01_ARCHITECTURE/RUNTIME-ROADMAP.md").read_text(encoding="utf-8")
    program = (ROOT / "docs/03_OPERATIONS/SPRINT-16-PROGRAM.md").read_text(encoding="utf-8")
    security = (ROOT / "docs/04_SECURITY/SECURITY.md").read_text(encoding="utf-8")
    combined = "\n".join((connector, credentials, delivery, roadmap, program, security))

    for required in (
        "RuntimeConnectorMaterializationRequest",
        "RuntimeManagedConnectorInvocationCapability",
        "RuntimeConnectorObservationInvocation",
        "RuntimeManagedConnectorObservationCapability",
        "adapter_contract_version",
        "connector_provisioning_reference",
        "runtime_effect_delivery_envelope_id",
        "effect_idempotency_key",
        "definite non-delivery cannot contain acknowledgement evidence",
        "request-local asynchronous",
        "no schema or migration `20260808_0025`",
    ):
        assert required in combined

    for prohibited in (
        "import fastapi",
        "import sqlalchemy",
        "import requests",
        "import httpx",
        "authorization_header:",
        "credential_secret:",
    ):
        assert prohibited not in connector.lower()

    assert not any((ROOT / "alembic/versions").glob("20260808_0025*"))
