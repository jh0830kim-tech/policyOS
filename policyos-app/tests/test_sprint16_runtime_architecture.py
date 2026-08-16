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
