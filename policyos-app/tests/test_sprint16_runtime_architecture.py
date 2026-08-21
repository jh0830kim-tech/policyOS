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


def test_connector_operation_purpose_contract_and_selection_are_implemented() -> None:
    connector = (ROOT / "app/runtime/ports/connector.py").read_text(encoding="utf-8")
    validation = (ROOT / "app/runtime/ports/connector_validation.py").read_text(encoding="utf-8")
    worker = (ROOT / "app/services/runtime_worker_validation.py").read_text(encoding="utf-8")
    production = (ROOT / "app/services/runtime_connector_production.py").read_text(encoding="utf-8")

    for required in (
        'delivery_credential_purpose_reference: Literal["connector.invoke"]',
        'observation_credential_purpose_reference: Literal["connector.observe"]',
    ):
        assert required in connector
    assert 'entry.delivery_credential_purpose_reference != "connector.invoke"' in validation
    assert 'entry.observation_credential_purpose_reference != "connector.observe"' in validation
    for source in (worker, production):
        assert "isinstance(request, RuntimeConnectorMaterializationRequest)" in source
        assert "entry.delivery_credential_purpose_reference" in source
        assert "entry.observation_credential_purpose_reference" in source
    assert "validate_runtime_connector_observation_materialization_request(request)" in production


def test_adr126_connector_wire_evidence_and_backend_governance() -> None:
    adr123 = (
        ROOT
        / (
            "docs/01_ARCHITECTURE/ADR/ADR-123-S16-RUNTIME-PRODUCTION-EXTERNAL-"
            "ADAPTER-CREDENTIAL-LEASE-MATERIALIZATION-AND-ACKNOWLEDGEMENT-OWNERSHIP.md"
        )
    ).read_text(encoding="utf-8")
    adr124 = (
        ROOT
        / (
            "docs/01_ARCHITECTURE/ADR/ADR-124-S16-RUNTIME-CONNECTOR-"
            "ACKNOWLEDGEMENT-EVIDENCE-MAPPING-AND-CREDENTIAL-LEASE-EXACT-BINDING.md"
        )
    ).read_text(encoding="utf-8")
    adr125 = (
        ROOT
        / (
            "docs/01_ARCHITECTURE/ADR/ADR-125-S16-RUNTIME-CONNECTOR-PROVISIONING-"
            "CREDENTIAL-MATERIALIZATION-HANDOFF-AND-WORKER-INVOCATION-OWNERSHIP.md"
        )
    ).read_text(encoding="utf-8")
    adr126 = (
        ROOT
        / (
            "docs/01_ARCHITECTURE/ADR/ADR-126-S16-RUNTIME-CONNECTOR-WIRE-"
            "CONTRACT-PAYLOAD-MATERIALIZATION-PROVIDER-EVIDENCE-AND-BACKEND-OWNERSHIP.md"
        )
    ).read_text(encoding="utf-8")
    roadmap = (ROOT / "docs/01_ARCHITECTURE/RUNTIME-ROADMAP.md").read_text(encoding="utf-8")
    program = (ROOT / "docs/03_OPERATIONS/SPRINT-16-PROGRAM.md").read_text(encoding="utf-8")
    security = (ROOT / "docs/04_SECURITY/SECURITY.md").read_text(encoding="utf-8")

    for phrase in (
        "PolicyOS Governed HTTPS Connector Receiver v1",
        "POLICYOS_REFERENCE_NOTIFICATION_V1",
        "/v1/runtime/connector",
        "`deliver` or `observe`",
        "does not dereference or transmit the",
        "fixed field order",
        "length-prefixed UTF-8",
        "bare HTTP",
        "before the network",
        "fully validated acknowledgement",
        "RuntimeConnectorOutcomeFactsProvider",
        "20260808_0025",
    ):
        assert phrase in adr126

    assert "deployment-owned secret manager" in adr123
    assert "CONFIRMED_DELIVERED" in adr124
    assert "OBSERVATION_UNAVAILABLE" in adr124
    assert "delivery_factory(revalidation.materialization_request)" in adr125
    assert "Governed / Validated, Pending Review" in roadmap
    assert "POST /v1/runtime/connector" in program
    assert "private mutable" in security

    forbidden = (
        "dynamic destination discovery",
        "follow redirects",
        "HTTP 2xx proves delivery",
        "environment credential fallback",
        "migration 20260808_0025 is required",
    )
    for phrase in forbidden:
        assert phrase not in adr126


def test_connector_worker_materialization_handoff_contract_gate_is_bounded() -> None:
    connector = (ROOT / "app/runtime/ports/connector.py").read_text(encoding="utf-8")
    connector_validation = (ROOT / "app/runtime/ports/connector_validation.py").read_text(
        encoding="utf-8"
    )
    worker = (ROOT / "app/services/runtime_worker_protocols.py").read_text(encoding="utf-8")
    worker_validation = (ROOT / "app/services/runtime_worker_validation.py").read_text(
        encoding="utf-8"
    )
    roadmap = (ROOT / "docs/01_ARCHITECTURE/RUNTIME-ROADMAP.md").read_text(encoding="utf-8")
    program = (ROOT / "docs/03_OPERATIONS/SPRINT-16-PROGRAM.md").read_text(encoding="utf-8")
    security = (ROOT / "docs/04_SECURITY/SECURITY.md").read_text(encoding="utf-8")
    combined = "\n".join(
        (
            connector,
            connector_validation,
            worker,
            worker_validation,
            roadmap,
            program,
            security,
        )
    )

    for required in (
        "RuntimeConnectorObservationMaterializationRequest",
        "materialization_request: RuntimeConnectorMaterializationRequest | None",
        "self, request: RuntimeConnectorMaterializationRequest",
        "connector observation lease request time differs",
        "connector observation predates reconciliation request",
        "scope.attempt_id",
        "exactly one secret-free connector materialization",
        "fresh observation-specific lease",
        "no schema or migration `20260808_0025`",
    ):
        assert required in combined

    for prohibited in (
        "credential_secret:",
        "authorization_header:",
        "import fastapi",
        "import sqlalchemy",
        "select the latest credential",
    ):
        assert prohibited not in connector.lower()

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


def test_adr127_connector_authentication_encoding_and_transport_governance() -> None:
    adr127 = (
        ROOT
        / "docs/01_ARCHITECTURE/ADR"
        / (
            "ADR-127-S16-RUNTIME-CONNECTOR-AUTHENTICATION-CANONICAL-WIRE-ENCODING-"
            "AND-TRANSPORT-BOUNDS.md"
        )
    ).read_text(encoding="utf-8")
    roadmap = (ROOT / "docs/01_ARCHITECTURE/RUNTIME-ROADMAP.md").read_text(encoding="utf-8")
    program = (ROOT / "docs/03_OPERATIONS/SPRINT-16-PROGRAM.md").read_text(encoding="utf-8")
    security = (ROOT / "docs/04_SECURITY/SECURITY.md").read_text(encoding="utf-8")

    for required in (
        "policyos-runtime-connector-v1",
        "Authorization: Bearer <opaque-secret>",
        "Content-Type: application/json",
        "Only HTTP status `200`",
        "32,768 bytes",
        "16,384 bytes",
        "length-prefixed UTF-8",
        "YYYY-MM-DDTHH:MM:SS.ffffffZ",
        "sha256:<64 lowercase hexadecimal characters>",
        "delivery_acknowledgement",
        "delivery_observation",
        "TLS 1.2 or newer",
        "migration `20260808_0025`",
    ):
        assert required in adr127

    for prohibited in (
        "redirect following",
        "raw JSON byte equality",
        "environment",
        "fallback",
        "HTTP status never overrides",
    ):
        assert prohibited in adr127

    assert "Governed / Validated, Pending Review" in roadmap
    assert "Bearer-authenticated JSON protocol" in program
    assert "entire header is excluded or redacted" in security
    assert not any((ROOT / "alembic/versions").glob("20260808_0025*"))


def test_connector_wire_public_contract_gate_is_secret_free_and_bounded() -> None:
    connector = (ROOT / "app/runtime/ports/connector.py").read_text(encoding="utf-8")
    validation = (ROOT / "app/runtime/ports/connector_validation.py").read_text(encoding="utf-8")
    roadmap = (ROOT / "docs/01_ARCHITECTURE/RUNTIME-ROADMAP.md").read_text(encoding="utf-8")
    program = (ROOT / "docs/03_OPERATIONS/SPRINT-16-PROGRAM.md").read_text(encoding="utf-8")
    security = (ROOT / "docs/04_SECURITY/SECURITY.md").read_text(encoding="utf-8")
    combined = "\n".join((connector, validation, roadmap, program, security))

    for required in (
        "RuntimeConnectorDeliveryWireRequest",
        "RuntimeConnectorDeliveryAcknowledgement",
        "RuntimeConnectorObservationWireRequest",
        "RuntimeConnectorDeliveryObservation",
        "RuntimeConnectorOutcomeFactsProvider",
        "RUNTIME_CONNECTOR_REQUEST_BODY_MAX_BYTES = 32_768",
        "RUNTIME_CONNECTOR_RESPONSE_BODY_MAX_BYTES = 16_384",
        "runtime_connector_canonical_digest",
        "connector JSON contains a duplicate field",
        "exact HTTP 200",
        "no migration `20260808_0025`",
    ):
        assert required in combined

    for prohibited in (
        "import httpx",
        "import requests",
        "authorization_header:",
        "credential_secret:",
        "bearer_token:",
    ):
        assert prohibited not in connector.lower()

    assert not any((ROOT / "alembic/versions").glob("20260808_0025*"))


def test_adr128_connector_production_composition_and_materialization_facts_governance() -> None:
    adr_root = ROOT / "docs/01_ARCHITECTURE/ADR"
    adr128 = (
        adr_root
        / (
            "ADR-128-S16-RUNTIME-CONNECTOR-PRODUCTION-COMPOSITION-AND-"
            "MATERIALIZATION-FACTS-OWNERSHIP.md"
        )
    ).read_text(encoding="utf-8")
    adr119 = (
        adr_root
        / "ADR-119-CP10-RUNTIME-WORKER-PRE-INVOCATION-AUTHORITATIVE-REVALIDATION-OWNERSHIP.md"
    ).read_text(encoding="utf-8")
    adr125 = (
        adr_root
        / (
            "ADR-125-S16-RUNTIME-CONNECTOR-PROVISIONING-CREDENTIAL-MATERIALIZATION-"
            "HANDOFF-AND-WORKER-INVOCATION-OWNERSHIP.md"
        )
    ).read_text(encoding="utf-8")
    adr126 = (
        adr_root
        / (
            "ADR-126-S16-RUNTIME-CONNECTOR-WIRE-CONTRACT-PAYLOAD-MATERIALIZATION-"
            "PROVIDER-EVIDENCE-AND-BACKEND-OWNERSHIP.md"
        )
    ).read_text(encoding="utf-8")
    adr127 = (
        adr_root
        / (
            "ADR-127-S16-RUNTIME-CONNECTOR-AUTHENTICATION-CANONICAL-WIRE-ENCODING-"
            "AND-TRANSPORT-BOUNDS.md"
        )
    ).read_text(encoding="utf-8")
    roadmap = (ROOT / "docs/01_ARCHITECTURE/RUNTIME-ROADMAP.md").read_text(encoding="utf-8")
    program = (ROOT / "docs/03_OPERATIONS/SPRINT-16-PROGRAM.md").read_text(encoding="utf-8")
    security = (ROOT / "docs/04_SECURITY/SECURITY.md").read_text(encoding="utf-8")
    combined = "\n".join((adr128, adr119, adr125, adr126, adr127, roadmap, program, security))

    for required in (
        "RuntimeConnectorMaterializationFactsProvider",
        "runtime_connector_materialization_request_id",
        "runtime_connector_observation_materialization_request_id",
        "runtime_credential_lease_request_id",
        "credential_purpose_reference",
        "caller-supplied `requested_at`",
        "caller-supplied `expires_at`",
        "delivery_factory(revalidation.materialization_request)",
        "exactly once in reverse construction order",
        "No database transaction is open",
        "fresh observation-specific lease",
        "migration `20260808_0025`",
    ):
        assert required in combined

    for prohibited in (
        "latest provisioning entry,",
        "read an environment credential",
        "Store request-local preparation state globally",
        "Reuse the delivery lease for observation",
        "Generate request IDs and times inside production composition",
    ):
        assert prohibited in adr128

    assert "Production/public Python" not in adr128
    assert not any((ROOT / "alembic/versions").glob("20260808_0025*"))


def test_adr129_connector_materialization_provider_and_bundle_signature_governance() -> None:
    adr129 = (
        ROOT
        / "docs/01_ARCHITECTURE/ADR"
        / (
            "ADR-129-S16-RUNTIME-CONNECTOR-MATERIALIZATION-FACTS-PROVIDER-AND-"
            "PRODUCTION-BUNDLE-PUBLIC-SIGNATURE.md"
        )
    ).read_text(encoding="utf-8")
    roadmap = (ROOT / "docs/01_ARCHITECTURE/RUNTIME-ROADMAP.md").read_text(encoding="utf-8")
    program = (ROOT / "docs/03_OPERATIONS/SPRINT-16-PROGRAM.md").read_text(encoding="utf-8")
    security = (ROOT / "docs/04_SECURITY/SECURITY.md").read_text(encoding="utf-8")
    combined = "\n".join((adr129, roadmap, program, security))

    for required in (
        "RuntimeConnectorDeliveryMaterializationFacts",
        "RuntimeConnectorObservationMaterializationFacts",
        "MaterializationFactsT_co",
        "def facts(self) -> MaterializationFactsT_co",
        "RuntimeManagedConnectorMaterializationFactsProvider",
        "RuntimeConnectorDeliveryMaterializationFactsProviderFactory",
        "RuntimeConnectorObservationMaterializationFactsProviderFactory",
        "RuntimeConnectorProvisioningEntry",
        "RuntimeConnectorProvisioningCatalog",
        "select_runtime_connector_provisioning_entry",
        "RuntimeConnectorObservationPreparationCapability.prepare",
        "RuntimeConnectorOutcomeFactsProviderFactory",
        "RuntimeConnectorProductionDependencyBundle",
        "exactly nine fields",
        "migration `20260808_0025`",
    ):
        assert required in combined

    for required in (
        "Private secret-materialization and HTTPS transport factories are deliberately not public",
        "Neither factory has a zero-argument",
        "operation-matched facts method once",
    ):
        assert required in adr129

    for prohibited in (
        "select by URL, recency, partial scope or credential alone",
        "Let the catalog or provider construct missing values",
        "Put private secret and transport factories in the public bundle",
    ):
        assert prohibited in adr129

    assert not any((ROOT / "alembic/versions").glob("20260808_0025*"))


def test_connector_materialization_facts_and_bundle_public_contract_gate() -> None:
    connector = (ROOT / "app/runtime/ports/connector.py").read_text(encoding="utf-8")
    connector_validation = (ROOT / "app/runtime/ports/connector_validation.py").read_text(
        encoding="utf-8"
    )
    worker_protocols = (ROOT / "app/services/runtime_worker_protocols.py").read_text(
        encoding="utf-8"
    )
    worker_validation = (ROOT / "app/services/runtime_worker_validation.py").read_text(
        encoding="utf-8"
    )
    combined = "\n".join((connector, connector_validation, worker_protocols, worker_validation))

    for required in (
        "RuntimeConnectorDeliveryMaterializationFacts",
        "RuntimeConnectorObservationMaterializationFacts",
        "MaterializationFactsT_co",
        "RuntimeConnectorMaterializationFactsProvider",
        "RuntimeManagedConnectorMaterializationFactsProvider",
        "RuntimeConnectorProvisioningEntry",
        "RuntimeConnectorProvisioningCatalog",
        "select_runtime_connector_provisioning_entry",
        "RuntimeConnectorObservationPreparationCapability",
        "RuntimeConnectorOutcomeFactsProviderFactory",
        "RuntimeConnectorProductionDependencyBundle",
    ):
        assert required in combined

    assert (
        len(
            (
                "provisioning_catalog",
                "delivery_materialization_facts_provider_factory",
                "observation_materialization_facts_provider_factory",
                "credential_broker_factory",
                "outcome_facts_provider_factory",
                "pre_invocation_revalidation_factory",
                "delivery_factory",
                "observation_preparation_factory",
                "observation_factory",
            )
        )
        == 9
    )
    for prohibited in (
        "credential_secret",
        "bearer_token",
        "httpx.client",
        "requests.session",
        "sqlalchemy",
    ):
        assert prohibited not in connector.lower()
    assert not any((ROOT / "alembic/versions").glob("20260808_0025*"))


def test_sprint16_production_connector_composition_is_private_and_exact():
    production = ROOT / "app/services/runtime_connector_production.py"
    worker = ROOT / "app/services/runtime_worker.py"
    assert production.exists()
    source = production.read_text(encoding="utf-8")
    worker_source = worker.read_text(encoding="utf-8")
    assert "create_runtime_connector_production_dependencies" in source
    assert "secret_materialization_source" in source
    assert "https_transport_factory" in source
    assert "RuntimeConnectorProductionDependencyBundle" in source
    assert "datetime.now" not in source
    assert "uuid4" not in source
    assert "sqlalchemy" not in source.lower()
    assert "commit(" not in source and "rollback(" not in source
    assert "revalidation.materialization_request" in worker_source
    assert "self.dependencies.delivery_factory()" not in worker_source


def test_adr130_governs_operation_specific_connector_purposes() -> None:
    adr = (
        ROOT
        / "docs/01_ARCHITECTURE/ADR"
        / "ADR-130-S16-RUNTIME-CONNECTOR-OPERATION-PURPOSE-OWNERSHIP.md"
    ).read_text(encoding="utf-8")
    adr125 = next((ROOT / "docs/01_ARCHITECTURE/ADR").glob("ADR-125-*.md")).read_text(
        encoding="utf-8"
    )
    adr128 = next((ROOT / "docs/01_ARCHITECTURE/ADR").glob("ADR-128-*.md")).read_text(
        encoding="utf-8"
    )
    adr129 = next((ROOT / "docs/01_ARCHITECTURE/ADR").glob("ADR-129-*.md")).read_text(
        encoding="utf-8"
    )
    combined = "\n".join((adr, adr125, adr128, adr129))

    for required in (
        "exactly one immutable enabled provisioning entry",
        "delivery_credential_purpose_reference",
        "observation_credential_purpose_reference",
        "connector.invoke",
        "connector.observe",
        "concrete request type",
        "fresh observation lease",
        "exactly-nine-field shape",
        "migration `20260808_0025`",
    ):
        assert required in combined

    for prohibited in (
        "Share one generic purpose",
        "Create one catalog entry per operation",
        "Infer purpose from the request operation",
    ):
        assert prohibited in adr

    assert not any((ROOT / "alembic/versions").glob("20260808_0025*"))
