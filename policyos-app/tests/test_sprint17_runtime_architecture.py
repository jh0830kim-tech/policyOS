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
    for forbidden in ("datetime.now", "uuid4", "trust_env=True", "follow_redirects=True"):
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
