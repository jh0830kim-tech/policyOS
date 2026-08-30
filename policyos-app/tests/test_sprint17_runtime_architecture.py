"""Focused, network-free guards for Sprint 17 Runtime governance."""

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def _read(relative: str) -> str:
    return (ROOT / relative).read_text(encoding="utf-8")


def test_adr131_governs_operator_enablement_without_runtime_registry() -> None:
    adr = _read(
        "docs/01_ARCHITECTURE/ADR/"
        "ADR-131-S17-RUNTIME-CONNECTOR-OPERATOR-ENABLEMENT-SECRET-BACKEND-AND-"
        "DEPLOYMENT-OWNERSHIP.md"
    )
    program = _read("docs/03_OPERATIONS/SPRINT-17-PROGRAM.md")
    roadmap = _read("docs/01_ARCHITECTURE/RUNTIME-ROADMAP.md")
    security = _read("docs/04_SECURITY/SECURITY.md")

    for phrase in (
        "deployment-owned immutable manifest",
        "no provisioning mutation API",
        "separate operator approval",
        "exactly once",
        "migration `20260808_0025`",
        "single head `20260808_0024`",
    ):
        assert phrase in adr

    assert "PolicyOS-managed provisioning registry" in adr
    assert "Rejected for the initial Sprint 17 boundary" in adr
    assert "Environment or caller-selected endpoint and credential" in adr
    assert "Automatic activation after merge or startup" in adr
    assert "one deployment-owned immutable, secret-free manifest" in program
    assert "Sprint 17 operator-enablement governance boundary" in roadmap
    assert "Sprint 17 operator-enablement security boundary" in security
    assert not any((ROOT / "alembic/versions").glob("20260808_0025*"))


def test_adr146_public_contracts_preserve_source_and_effective_classification() -> None:
    contracts = _read("app/runtime/ports/runtime_api_persistence.py")
    roadmap = _read("docs/01_ARCHITECTURE/RUNTIME-ROADMAP.md")
    program = _read("docs/03_OPERATIONS/SPRINT-17-PROGRAM.md")
    security = _read("docs/04_SECURITY/SECURITY.md")

    assert contracts.count("execution_request_classification: DataClassification") == 2
    for phrase in (
        "not_lower(self.scope.classification, self.execution_request_classification)",
        "not_lower(scope.classification, expected.classification)",
        "result.execution_request_classification",
        "self.locator.execution_request_classification",
    ):
        assert phrase in contracts
    assert "Sprint 17 logical-result source/effective classification public contracts" in roadmap
    assert "Logical-result source/effective classification public-contract gate" in program
    assert "Sprint 17 logical-result classification contract security boundary" in security
    assert not any((ROOT / "alembic/versions").glob("20260808_0025*"))


def test_adr143_governs_registry_snapshot_production_composition() -> None:
    adr = _read(
        "docs/01_ARCHITECTURE/ADR/"
        "ADR-143-S17-GEMINI-REGISTRY-SNAPSHOT-AND-PRODUCTION-COMPOSITION-OWNERSHIP.md"
    )
    for phrase in (
        "production application factory",
        "caller-supplied immutable",
        "`ModelRegistrySnapshot`",
        "pure composition binder",
        "exact logical model selection",
        "`RegisteredModel.provider_model_name`",
        "before credential access",
        "migration `20260808_0025`",
    ):
        assert phrase in adr
    for name in ("ADR-032", "ADR-037", "ADR-038", "ADR-136", "ADR-142"):
        path = next((ROOT / "docs/01_ARCHITECTURE/ADR").glob(f"{name}-*.md"))
        assert "ADR-143" in _read(path.relative_to(ROOT).as_posix())
    assert "Sprint 17 Gemini registry-snapshot production composition governance" in _read(
        "docs/01_ARCHITECTURE/RUNTIME-ROADMAP.md"
    )
    assert "Gemini registry snapshot and production composition governance gate" in _read(
        "docs/03_OPERATIONS/SPRINT-17-PROGRAM.md"
    )
    assert "Gemini registry-snapshot composition security boundary" in _read(
        "docs/04_SECURITY/SECURITY.md"
    )
    assert not any((ROOT / "alembic/versions").glob("20260808_0025*"))


def test_adr144_governs_ai_office_dependency_bundle_and_route_composition() -> None:
    adr = _read(
        "docs/01_ARCHITECTURE/ADR/"
        "ADR-144-S17-AI-OFFICE-PRODUCTION-DEPENDENCY-BUNDLE-AND-ROUTE-"
        "COMPOSITION-OWNERSHIP.md"
    )
    for phrase in (
        "immutable AI Office production dependency bundle",
        "artifacts-router factory",
        "prebuilt composition",
        "application lifetime",
        "before the router is exposed",
        "before credential access",
        "mutable `app.state`",
        "module-global",
        "migration `20260808_0025`",
    ):
        assert phrase in adr
    for name in ("ADR-038", "ADR-136", "ADR-142", "ADR-143"):
        path = next((ROOT / "docs/01_ARCHITECTURE/ADR").glob(f"{name}-*.md"))
        assert "ADR-144" in _read(path.relative_to(ROOT).as_posix())
    assert "Sprint 17 AI Office dependency-bundle and route-composition governance" in _read(
        "docs/01_ARCHITECTURE/RUNTIME-ROADMAP.md"
    )
    assert "AI Office production dependency-bundle and route-composition governance gate" in _read(
        "docs/03_OPERATIONS/SPRINT-17-PROGRAM.md"
    )
    assert "Gemini AI Office dependency-bundle and route-composition security boundary" in _read(
        "docs/04_SECURITY/SECURITY.md"
    )
    assert not any((ROOT / "alembic/versions").glob("20260808_0025*"))


def test_adr145_governs_request_scoped_gateway_audit_and_execution_composition() -> None:
    adr = _read(
        "docs/01_ARCHITECTURE/ADR/"
        "ADR-145-S17-AI-OFFICE-REQUEST-SCOPED-GATEWAY-AUDIT-AND-EXECUTION-"
        "COMPOSITION-OWNERSHIP.md"
    )
    for phrase in (
        "`OfficeCompositionBlueprint`",
        "`AIOfficeProductionDependencyBundle`",
        "`request_execution_scope_factory: OfficeRequestExecutionScopeFactory`",
        "`model_registry_snapshot: ModelRegistrySnapshot | None`",
        "`logical_model_id: str | None`",
        "open(audit_sink: ProviderAuditSink)",
        "AsyncContextManager[OfficeExecutionComposition]",
        "`ProviderAuditRepository(db)`",
        "reverse-order exactly-once cleanup",
        "migration `20260808_0025`",
    ):
        assert phrase in adr
    for name in ("ADR-038", "ADR-136", "ADR-143", "ADR-144"):
        path = next((ROOT / "docs/01_ARCHITECTURE/ADR").glob(f"{name}-*.md"))
        assert "ADR-145" in _read(path.relative_to(ROOT).as_posix())
    assert "Sprint 17 AI Office request-scoped gateway and audit governance" in _read(
        "docs/01_ARCHITECTURE/RUNTIME-ROADMAP.md"
    )
    assert "AI Office request-scoped gateway, audit and execution-composition governance gate" in (
        _read("docs/03_OPERATIONS/SPRINT-17-PROGRAM.md")
    )
    assert "Gemini AI Office request-scoped gateway and audit security boundary" in _read(
        "docs/04_SECURITY/SECURITY.md"
    )


def test_ai_office_production_composition_is_request_scoped_and_explicit() -> None:
    production = _read("app/ai/production.py")
    composition = _read("app/ai/composition.py")
    artifacts = _read("app/api/routes/artifacts.py")
    service = _read("app/services/office_application.py")
    main = _read("app/main.py")
    gemini = _read("app/ai/providers/gemini_interactions.py")

    for required in (
        "class OfficeCompositionBlueprint",
        "class AIOfficeProductionDependencyBundle",
        "class OfficeRequestExecutionScopeFactory",
        "def bind_ai_office_production",
    ):
        assert required in production
    assert "build_office_composition_from_gateway" in composition
    assert "def create_artifacts_router" in artifacts
    assert "ProviderAuditRepository(db)" in artifacts
    assert "request_execution_scope_factory.open" in artifacts
    assert "get_settings" not in artifacts
    assert "build_office_composition" not in service
    assert "create_model_gateway" not in service
    assert "ai_office_dependencies" in main
    assert "provider_model_name" in gemini
    assert "app.state" not in production
    assert "20260808_0025" not in production
    assert not any((ROOT / "alembic/versions").glob("20260808_0025*"))


def test_adr141_governs_stable_path_and_closed_http_404_provenance() -> None:
    adr = _read(
        "docs/01_ARCHITECTURE/ADR/"
        "ADR-141-S17-GEMINI-CANONICAL-API-VERSION-PATH-AND-HTTP-404-PROVENANCE.md"
    )
    for phrase in (
        "`/v1/interactions`",
        "`request_http_404_unclassified`",
        "model alone is unavailable",
        "change only the literal path",
        "and stop",
        "migration `20260808_0025`",
        "`20260808_0024`",
    ):
        assert phrase in adr
    for name in ("ADR-136", "ADR-137", "ADR-140"):
        path = next((ROOT / "docs/01_ARCHITECTURE/ADR").glob(f"{name}-*.md"))
        assert "ADR-141" in _read(path.relative_to(ROOT).as_posix())
    assert not any((ROOT / "alembic/versions").glob("20260808_0025*"))


def test_postgresql_connector_evidence_acceptance_is_explicit_and_secret_free() -> None:
    support = _read("tests/runtime_connector_acceptance_test_support.py")
    acceptance = _read("tests/test_runtime_connector_postgresql_acceptance.py")
    roadmap = _read("docs/01_ARCHITECTURE/RUNTIME-ROADMAP.md")
    program = _read("docs/03_OPERATIONS/SPRINT-17-PROGRAM.md")
    security = _read("docs/04_SECURITY/SECURITY.md")

    for phrase in (
        "materialization_request=None",
        "_catalog_for_request(request)",
        "accepted_at=request.requested_at + timedelta(seconds=1)",
    ):
        assert phrase in support
    for phrase in (
        "real_https_dependencies",
        "RuntimeEffectLifecycleCommitDisposition.APPENDED",
        "RuntimeEffectLifecycleCommitDisposition.EXACT_REPLAY",
        "deserialize_delivery_model",
        '"sandbox-private-token"',
        '"authorization"',
    ):
        assert phrase in acceptance
    assert "Sprint 17 PostgreSQL connector evidence acceptance" in roadmap
    assert "PostgreSQL connector evidence acceptance gate" in program
    assert "Sprint 17 PostgreSQL connector evidence security proof" in security
    assert not any((ROOT / "alembic/versions").glob("20260808_0025*"))


def test_operator_manifest_contract_reuses_catalog_and_rejects_path_substitution() -> None:
    source = _read("app/runtime/ports/connector_validation.py")
    adr = _read(
        "docs/01_ARCHITECTURE/ADR/"
        "ADR-131-S17-RUNTIME-CONNECTOR-OPERATOR-ENABLEMENT-SECRET-BACKEND-AND-"
        "DEPLOYMENT-OWNERSHIP.md"
    )
    program = _read("docs/03_OPERATIONS/SPRINT-17-PROGRAM.md")

    assert 'parsed.path != "/v1/runtime/connector"' in source
    assert "runtime representation of the deployment manifest" in adr
    assert "Therefore no second" in adr
    assert "manifest wrapper" in adr
    assert "Construction accepts only the canonical path" in program
    assert "`/v1/runtime/connector`" in program
    assert not any((ROOT / "alembic/versions").glob("20260808_0025*"))


def test_adr132_governs_deployment_neutral_secret_and_transport_backends() -> None:
    adr = _read(
        "docs/01_ARCHITECTURE/ADR/"
        "ADR-132-S17-RUNTIME-CONNECTOR-SECRET-BACKEND-AND-HTTPS-TRANSPORT-"
        "PRODUCTION-OWNERSHIP.md"
    )
    adr126 = _read(
        "docs/01_ARCHITECTURE/ADR/"
        "ADR-126-S16-RUNTIME-CONNECTOR-WIRE-CONTRACT-PAYLOAD-MATERIALIZATION-"
        "PROVIDER-EVIDENCE-AND-BACKEND-OWNERSHIP.md"
    )
    adr128 = _read(
        "docs/01_ARCHITECTURE/ADR/"
        "ADR-128-S16-RUNTIME-CONNECTOR-PRODUCTION-COMPOSITION-AND-"
        "MATERIALIZATION-FACTS-OWNERSHIP.md"
    )
    adr131 = _read(
        "docs/01_ARCHITECTURE/ADR/"
        "ADR-131-S17-RUNTIME-CONNECTOR-OPERATOR-ENABLEMENT-SECRET-BACKEND-AND-"
        "DEPLOYMENT-OWNERSHIP.md"
    )
    program = _read("docs/03_OPERATIONS/SPRINT-17-PROGRAM.md")
    roadmap = _read("docs/01_ARCHITECTURE/RUNTIME-ROADMAP.md")
    security = _read("docs/04_SECURITY/SECURITY.md")

    for phrase in (
        "deployment-injected, version-pinned",
        "workload authentication",
        "request-local buffer",
        "hardened `httpx` transport",
        "`trust_env=False`",
        "migration `20260808_0025`",
        "single head `20260808_0024`",
    ):
        assert phrase in adr

    for forbidden_choice in (
        "Read a secret from environment or filesystem",
        "Use environment proxy and trust defaults",
        "Cache clients or secret values globally",
        "Choose a cloud secret manager in repository code",
    ):
        assert forbidden_choice in adr

    assert "ADR-132 deployment-neutral backend clarification" in adr126
    assert "ADR-132 private-backend clarification" in adr128
    assert "Deployment-neutral backend clarification" in adr131
    assert "ADR-132 deployment-neutral backend gate" in program
    assert "Sprint 17 deployment-neutral secret backend" in roadmap
    assert "Sprint 17 deployment-neutral private-backend security boundary" in security
    assert not any((ROOT / "alembic/versions").glob("20260808_0025*"))


def test_adr133_governs_trusted_deadline_clock_and_transport_timeout() -> None:
    adr = _read(
        "docs/01_ARCHITECTURE/ADR/"
        "ADR-133-S17-RUNTIME-CONNECTOR-TRUSTED-DEADLINE-CLOCK-AND-TRANSPORT-"
        "TIMEOUT-OWNERSHIP.md"
    )
    adr127 = _read(
        "docs/01_ARCHITECTURE/ADR/"
        "ADR-127-S16-RUNTIME-CONNECTOR-AUTHENTICATION-CANONICAL-WIRE-ENCODING-"
        "AND-TRANSPORT-BOUNDS.md"
    )
    adr128 = _read(
        "docs/01_ARCHITECTURE/ADR/"
        "ADR-128-S16-RUNTIME-CONNECTOR-PRODUCTION-COMPOSITION-AND-"
        "MATERIALIZATION-FACTS-OWNERSHIP.md"
    )
    adr132 = _read(
        "docs/01_ARCHITECTURE/ADR/"
        "ADR-132-S17-RUNTIME-CONNECTOR-SECRET-BACKEND-AND-HTTPS-TRANSPORT-"
        "PRODUCTION-OWNERSHIP.md"
    )
    program = _read("docs/03_OPERATIONS/SPRINT-17-PROGRAM.md")
    roadmap = _read("docs/01_ARCHITECTURE/RUNTIME-ROADMAP.md")
    security = _read("docs/04_SECURITY/SECURITY.md")

    for phrase in (
        "request-scoped managed clock capability",
        "immediately before the governed network-call boundary",
        "remaining_duration = caller_supplied_deadline - observed_at",
        "zero or negative duration",
        "performs no rounding, clamping",
        "migration `20260808_0025`",
        "Alembic head remains the single",
    ):
        assert phrase in adr

    for forbidden_choice in (
        "Read the process wall clock directly",
        "Use the HTTP client's default timeout",
        "Convert with event-loop monotonic time",
        "Clamp or refresh the remaining duration",
        "Persist clock readings or timeout budgets",
    ):
        assert forbidden_choice in adr

    assert "ADR-133 trusted deadline-clock clarification" in adr127
    assert "ADR-133 deadline-clock clarification" in adr128
    assert "ADR-133 trusted timeout clarification" in adr132
    assert "ADR-133 trusted deadline-clock gate" in program
    assert "Sprint 17 trusted deadline clock and transport timeout governance" in roadmap
    assert "Sprint 17 trusted deadline-clock security boundary" in security
    assert not any((ROOT / "alembic/versions").glob("20260808_0025*"))


def test_adr134_governs_private_backend_signatures_and_tls_trust() -> None:
    adr = _read(
        "docs/01_ARCHITECTURE/ADR/"
        "ADR-134-S17-RUNTIME-CONNECTOR-PRIVATE-BACKEND-SIGNATURE-AND-TLS-TRUST-"
        "OWNERSHIP.md"
    )
    adr128 = _read(
        "docs/01_ARCHITECTURE/ADR/"
        "ADR-128-S16-RUNTIME-CONNECTOR-PRODUCTION-COMPOSITION-AND-"
        "MATERIALIZATION-FACTS-OWNERSHIP.md"
    )
    adr132 = _read(
        "docs/01_ARCHITECTURE/ADR/"
        "ADR-132-S17-RUNTIME-CONNECTOR-SECRET-BACKEND-AND-HTTPS-TRANSPORT-"
        "PRODUCTION-OWNERSHIP.md"
    )
    adr133 = _read(
        "docs/01_ARCHITECTURE/ADR/"
        "ADR-133-S17-RUNTIME-CONNECTOR-TRUSTED-DEADLINE-CLOCK-AND-TRANSPORT-"
        "TIMEOUT-OWNERSHIP.md"
    )
    program = _read("docs/03_OPERATIONS/SPRINT-17-PROGRAM.md")
    roadmap = _read("docs/01_ARCHITECTURE/RUNTIME-ROADMAP.md")
    security = _read("docs/04_SECURITY/SECURITY.md")

    for phrase in (
        "version-pinned accessor",
        "credential_purpose_reference",
        "connector_provisioning_reference",
        "zero-argument TLS-context factory",
        "RuntimeClockPort",
        "strictly positive `datetime.timedelta`",
        "`trust_env=False`",
        "migration `20260808_0025`",
    ):
        assert phrase in adr

    for forbidden_choice in (
        "Return raw secret bytes without identity echoes",
        "Add a new credential-version identity",
        "Use default or environment TLS trust",
        "Reuse one clock, TLS context, client, or secret buffer across requests",
        "Export private backend Protocols publicly",
    ):
        assert forbidden_choice in adr

    assert "ADR-134 private backend signature clarification" in adr128
    assert "ADR-134 private accessor and TLS signature clarification" in adr132
    assert "ADR-134 managed clock factory clarification" in adr133
    assert "ADR-134 private backend signature gate" in program
    assert "Sprint 17 private backend signature and TLS trust governance" in roadmap
    assert "Sprint 17 private backend signature and TLS trust boundary" in security
    assert not any((ROOT / "alembic/versions").glob("20260808_0025*"))


def test_adr134_private_backend_implementation_is_explicit_and_private() -> None:
    source = _read("app/services/runtime_connector_production.py")
    for phrase in (
        "version_pinned_secret_accessor",
        "tls_context_factory",
        "clock_factory",
        "expected_clock_reference",
        "ssl.CERT_REQUIRED",
        "ssl.TLSVersion.TLSv1_2",
        "trust_env=False",
        "follow_redirects=False",
        "remaining <= timedelta(0)",
    ):
        assert phrase in source
    for forbidden in (
        "datetime.now",
        "uuid4",
        "trust_env=True",
        "follow_redirects=True",
    ):
        assert forbidden not in source
    assert not any((ROOT / "alembic/versions").glob("20260808_0025*"))


def test_local_https_provider_sandbox_uses_the_production_transport_boundary() -> None:
    support = _read("tests/runtime_connector_acceptance_test_support.py")
    acceptance = _read("tests/test_runtime_connector_provider_acceptance.py")
    roadmap = _read("docs/01_ARCHITECTURE/RUNTIME-ROADMAP.md")
    program = _read("docs/03_OPERATIONS/SPRINT-17-PROGRAM.md")
    security = _read("docs/04_SECURITY/SECURITY.md")

    for phrase in (
        "asyncio.start_server",
        "ssl.PROTOCOL_TLS_SERVER",
        '"openssl"',
        'f"https://127.0.0.1:{port}/v1/runtime/connector"',
        "RealAsyncClient",
        "real_https_dependencies",
    ):
        assert phrase in support
    for phrase in (
        "test_real_loopback_https_delivery_verifies_tls_and_acknowledgement",
        "test_real_loopback_https_observation_verifies_provider_state",
        "test_real_loopback_https_uncertain_or_invalid_response_is_ambiguous",
    ):
        assert phrase in acceptance
    assert "Sprint 17 local HTTPS provider-sandbox acceptance" in roadmap
    assert "Local HTTPS provider-sandbox acceptance gate" in program
    assert "Sprint 17 local HTTPS acceptance security evidence" in security
    assert not any((ROOT / "alembic/versions").glob("20260808_0025*"))


def test_sprint17_closeout_is_complete_with_deployment_deferred() -> None:
    roadmap = _read("docs/01_ARCHITECTURE/RUNTIME-ROADMAP.md")
    program = _read("docs/03_OPERATIONS/SPRINT-17-PROGRAM.md")
    security = _read("docs/04_SECURITY/SECURITY.md")

    assert "Completed with Deployment Deferred" in roadmap
    assert "`COMPLETED WITH DEPLOYMENT DEFERRED`" in program
    assert "Sprint 17 closeout security boundary" in security
    for phrase in (
        "PR #163 through PR #170",
        "local validation sprint",
        "migration `20260808_0025`",
    ):
        assert phrase in roadmap
    for phrase in (
        "process entrypoint/runbook",
        "controlled deployment",
        "tag, and release",
    ):
        assert phrase in program
    assert "is not production enablement" in security
    assert not any((ROOT / "alembic/versions").glob("20260808_0025*"))


def test_adr135_governs_atomic_outbox_to_effect_handoff_without_new_schema() -> None:
    adr = _read(
        "docs/01_ARCHITECTURE/ADR/"
        "ADR-135-S17-RUNTIME-OUTBOX-TO-EFFECT-INITIALIZATION-OWNERSHIP-AND-"
        "ATOMIC-HANDOFF.md"
    )
    related = (
        _read(
            "docs/01_ARCHITECTURE/ADR/"
            "ADR-085-CP8-OUTBOX-PACKAGE-PLACEMENT-AND-EFFECT-DELIVERY-SEMANTICS.md"
        ),
        _read("docs/01_ARCHITECTURE/ADR/ADR-086-CP8-POSTGRESQL-EFFECT-DELIVERY-IMPLEMENTATION.md"),
        _read(
            "docs/01_ARCHITECTURE/ADR/"
            "ADR-092-CP9-RUNTIME-LOCAL-FACT-BINDING-AND-TRANSACTION-INTEGRATION.md"
        ),
        _read(
            "docs/01_ARCHITECTURE/ADR/"
            "ADR-114-CP10-RUNTIME-WORKER-PREPARED-DELIVERY-OWNERSHIP-EXACT-"
            "BINDING-AND-OUTCOME-SEQUENCING.md"
        ),
    )
    roadmap = _read("docs/01_ARCHITECTURE/RUNTIME-ROADMAP.md")
    program = _read("docs/03_OPERATIONS/SPRINT-17-PROGRAM.md")
    security = _read("docs/04_SECURITY/SECURITY.md")

    for phrase in (
        "No dispatcher or inferred conversion",
        "RuntimeEffectAtomicWriteSet",
        "facade remains the sole owner",
        "zero local effect mutation",
        "no committed outbox-to-effect crash window",
        "Execution projection and effect-delivery lifecycle remain separate",
        "migration `20260808_0025`",
    ):
        assert phrase in adr
    for text in related:
        assert "ADR-135" in text
    assert "Sprint 17 outbox-to-effect atomic handoff correction" in roadmap
    assert "ADR-135 atomic handoff correction gate" in program
    assert "Sprint 17 atomic outbox-to-effect handoff security boundary" in security
    assert not any((ROOT / "alembic/versions").glob("20260808_0025*"))


def test_adr135_submission_stage_contracts_are_closed_without_persistence_changes() -> None:
    contracts = _read("app/runtime/ports/runtime_api_persistence.py")
    roadmap = _read("docs/01_ARCHITECTURE/RUNTIME-ROADMAP.md")
    program = _read("docs/03_OPERATIONS/SPRINT-17-PROGRAM.md")
    security = _read("docs/04_SECURITY/SECURITY.md")

    for phrase in (
        "RuntimeAtomicWriteSet | RuntimeEffectAtomicWriteSet | None",
        "validate_runtime_effect_atomic_write_set(write_set)",
        "deliverable Runtime API submission requires initial effect facts",
        "base_write_set = write_set.base_write_set",
        "payload_time = base_write_set.requested_at",
    ):
        assert phrase in contracts
    assert "Active Persistence Implemented / Pending Review" in roadmap
    assert "ADR-135 submission-stage public contracts" in program
    assert "Sprint 17 closed submission-stage contract boundary" in security
    assert not any((ROOT / "alembic/versions").glob("20260808_0025*"))


def test_adr135_active_session_effect_persistence_is_transaction_neutral() -> None:
    active = _read("app/runtime/persistence/active_transaction.py")
    delivery = _read("app/runtime/persistence/delivery_transaction.py")
    roadmap = _read("docs/01_ARCHITECTURE/RUNTIME-ROADMAP.md")
    program = _read("docs/03_OPERATIONS/SPRINT-17-PROGRAM.md")
    security = _read("docs/04_SECURITY/SECURITY.md")

    helper = "_persist_runtime_effect_atomic_write_set"
    assert helper in active
    assert delivery.count(f"async def {helper}(") == 1
    helper_body = delivery.split(f"async def {helper}(", 1)[1].split("def _transaction_receipt", 1)[
        0
    ]
    for forbidden in (
        ".begin(",
        ".commit(",
        ".rollback(",
        ".close(",
        "validate_runtime_clock_reading",
    ):
        assert forbidden not in helper_body
    for phrase in (
        "RuntimeEffect(",
        "RuntimeEffectLifecycleRevision(",
        "RuntimeEffectLifecycleHead(",
        "await session.flush()",
    ):
        assert phrase in helper_body
    assert "Active Persistence Implemented / Pending Review" in roadmap
    assert "ADR-135 active-session effect persistence" in program
    assert "Sprint 17 active-session initial-effect persistence boundary" in security
    assert not any((ROOT / "alembic/versions").glob("20260808_0025*"))


def test_adr146_governs_source_and_effective_classification_before_schema_change() -> None:
    adr = _read(
        "docs/01_ARCHITECTURE/ADR/"
        "ADR-146-S17-RUNTIME-LOGICAL-RESULT-SOURCE-AND-EFFECTIVE-"
        "CLASSIFICATION-OWNERSHIP.md"
    )
    related = (
        _read(
            "docs/01_ARCHITECTURE/ADR/"
            "ADR-098-CP9-RUNTIME-EXECUTION-LIFECYCLE-PUBLIC-STATUS-AND-"
            "AUTHORITATIVE-REFERENCE.md"
        ),
        _read(
            "docs/01_ARCHITECTURE/ADR/"
            "ADR-099-CP9-RUNTIME-LOGICAL-EXECUTION-RESULT-IDENTITY-AND-"
            "PERSISTENCE-OWNERSHIP.md"
        ),
        _read(
            "docs/01_ARCHITECTURE/ADR/"
            "ADR-135-S17-RUNTIME-OUTBOX-TO-EFFECT-INITIALIZATION-OWNERSHIP-"
            "AND-ATOMIC-HANDOFF.md"
        ),
    )
    roadmap = _read("docs/01_ARCHITECTURE/RUNTIME-ROADMAP.md")
    program = _read("docs/03_OPERATIONS/SPRINT-17-PROGRAM.md")
    security = _read("docs/04_SECURITY/SECURITY.md")

    for phrase in (
        "source classification",
        "effective classification",
        "must be equal to",
        "or higher than the source classification",
        "execution_request_classification",
        "fk_runtime_logical_result_execution_request",
        "one logical-result ID per tenant, organization",
        "execution request, and attempt",
        "Migration `20260808_0025`",
        "No latest-row selection",
        "Populated downgrade fails",
        "zero residue",
    ):
        assert phrase in adr
    for text in related:
        assert "ADR-146" in text
    assert "Sprint 17 logical-result source/effective classification governance" in roadmap
    assert "ADR-146 logical-result classification ownership governance gate" in program
    assert "Sprint 17 logical-result source/effective classification security boundary" in security
    assert not any((ROOT / "alembic/versions").glob("20260808_0025*"))


def test_adr139_governs_safe_request_rejection_and_one_variable_probe() -> None:
    adr = _read(
        "docs/01_ARCHITECTURE/ADR/"
        "ADR-139-S17-GEMINI-REQUEST-REJECTION-SAFE-DIAGNOSTIC-AND-WIRE-PROBE-"
        "GOVERNANCE.md"
    )
    related = (
        _read(
            "docs/01_ARCHITECTURE/ADR/"
            "ADR-136-S17-GEMINI-PROVIDER-MODEL-CREDENTIAL-AND-EVALUATION-OWNERSHIP.md"
        ),
        _read(
            "docs/01_ARCHITECTURE/ADR/"
            "ADR-137-S17-GEMINI-WIRE-REVISION-AND-DOMAIN-OUTPUT-VALIDATION-OWNERSHIP.md"
        ),
        _read(
            "docs/01_ARCHITECTURE/ADR/"
            "ADR-138-S17-GEMINI-DOCUMENTED-OPTIONAL-RESPONSE-FIELDS-USAGE-"
            "CARDINALITY-AND-SAFE-REJECTION-DIAGNOSTICS.md"
        ),
    )
    roadmap = _read("docs/01_ARCHITECTURE/RUNTIME-ROADMAP.md")
    program = _read("docs/03_OPERATIONS/SPRINT-17-PROGRAM.md")
    security = _read("docs/04_SECURITY/SECURITY.md")

    for phrase in (
        "HTTP 400 and 422 remain safe non-retryable public `invalid_request`",
        "`INVALID_ARGUMENT`",
        "`FAILED_PRECONDITION`",
        "`OUT_OF_RANGE`",
        "request_http_400_<reason>",
        "request_http_422_<reason>",
        "array containing exactly one object",
        "`/v1beta/interactions`",
        "`Api-Revision: 2026-05-20`",
        "stop after that result without a second call",
        "migration `20260808_0025`",
    ):
        assert phrase in adr
    for text in related:
        assert "ADR-139" in text
    assert "Sprint 17 Gemini request-rejection diagnostic and wire-probe governance" in roadmap
    assert "Gemini request-rejection safe diagnostic and wire-probe governance gate" in program
    assert "Gemini request-rejection diagnostic and single-probe security boundary" in security
    assert not any((ROOT / "alembic/versions").glob("20260808_0025*"))


def test_adr140_governs_one_literal_api_version_path_probe() -> None:
    adr = _read(
        "docs/01_ARCHITECTURE/ADR/"
        "ADR-140-S17-GEMINI-INTERACTIONS-API-VERSION-PATH-OWNERSHIP-AND-SINGLE-"
        "VARIABLE-PROBE.md"
    )
    related = (
        _read(
            "docs/01_ARCHITECTURE/ADR/"
            "ADR-136-S17-GEMINI-PROVIDER-MODEL-CREDENTIAL-AND-EVALUATION-OWNERSHIP.md"
        ),
        _read(
            "docs/01_ARCHITECTURE/ADR/"
            "ADR-137-S17-GEMINI-WIRE-REVISION-AND-DOMAIN-OUTPUT-VALIDATION-OWNERSHIP.md"
        ),
        _read(
            "docs/01_ARCHITECTURE/ADR/"
            "ADR-139-S17-GEMINI-REQUEST-REJECTION-SAFE-DIAGNOSTIC-AND-WIRE-PROBE-"
            "GOVERNANCE.md"
        ),
    )
    roadmap = _read("docs/01_ARCHITECTURE/RUNTIME-ROADMAP.md")
    program = _read("docs/03_OPERATIONS/SPRINT-17-PROGRAM.md")
    security = _read("docs/04_SECURITY/SECURITY.md")

    for phrase in (
        "`/v1beta2/interactions`",
        "`Api-Revision: 2026-05-20`",
        "change only the path",
        "provider fallback zero",
        "stop after the first result",
        "migration `20260808_0025`",
    ):
        assert phrase in adr
    for text in related:
        assert "ADR-140" in text
    assert "Sprint 17 Gemini API-version path governance" in roadmap
    assert "Gemini API-version path governance gate" in program
    assert "Gemini API-version path security boundary" in security
    assert not any((ROOT / "alembic/versions").glob("20260808_0025*"))


def test_adr142_separates_logical_model_from_provider_wire_resource() -> None:
    adr = _read(
        "docs/01_ARCHITECTURE/ADR/"
        "ADR-142-S17-GEMINI-LOGICAL-MODEL-IDENTITY-AND-PROVIDER-WIRE-RESOURCE-OWNERSHIP.md"
    )
    for phrase in (
        "logical `model_id`",
        "provider wire model resource",
        "must not derive either value",
        "exact pair",
        "response echo",
        "single-variable",
        "migration `20260808_0025`",
    ):
        assert phrase in adr
    for name in ("ADR-136", "ADR-137", "ADR-141"):
        path = next((ROOT / "docs/01_ARCHITECTURE/ADR").glob(f"{name}-*.md"))
        assert "ADR-142" in _read(path.relative_to(ROOT).as_posix())
    assert "Sprint 17 Gemini logical-model and wire-resource governance" in _read(
        "docs/01_ARCHITECTURE/RUNTIME-ROADMAP.md"
    )
    assert "Gemini logical model and provider wire resource governance gate" in _read(
        "docs/03_OPERATIONS/SPRINT-17-PROGRAM.md"
    )
    assert "Gemini logical-model and wire-resource security boundary" in _read(
        "docs/04_SECURITY/SECURITY.md"
    )
    assert not any((ROOT / "alembic/versions").glob("20260808_0025*"))


def test_adr147_governs_historical_payload_backfill_and_trigger_ordering() -> None:
    adr = _read(
        "docs/01_ARCHITECTURE/ADR/"
        "ADR-147-S17-RUNTIME-LOGICAL-RESULT-HISTORICAL-PAYLOAD-BACKFILL-AND-"
        "IMMUTABLE-MIGRATION-ORDERING.md"
    )
    related = (
        _read(
            "docs/01_ARCHITECTURE/ADR/"
            "ADR-099-CP9-RUNTIME-LOGICAL-EXECUTION-RESULT-IDENTITY-AND-PERSISTENCE-"
            "OWNERSHIP.md"
        ),
        _read(
            "docs/01_ARCHITECTURE/ADR/"
            "ADR-146-S17-RUNTIME-LOGICAL-RESULT-SOURCE-AND-EFFECTIVE-CLASSIFICATION-"
            "OWNERSHIP.md"
        ),
    )
    for phrase in (
        "same joined source row",
        "no payload already contains `execution_request_classification`",
        "Before any trigger, constraint, schema, or row change",
        "recreate and verify the exact immutability trigger",
        "It cannot inject",
        "populated logical-result identity or revision table",
        "migration `20260808_0025`",
    ):
        assert phrase in adr
    for text in related:
        assert "ADR-147" in text
    assert "logical-result historical payload backfill governance" in _read(
        "docs/01_ARCHITECTURE/RUNTIME-ROADMAP.md"
    )
    assert "logical-result historical payload backfill governance gate" in _read(
        "docs/03_OPERATIONS/SPRINT-17-PROGRAM.md"
    )
    assert "logical-result historical payload backfill security boundary" in _read(
        "docs/04_SECURITY/SECURITY.md"
    )
    assert not any((ROOT / "alembic/versions").glob("20260808_0025*"))
