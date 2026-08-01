"""Focused guards for the PolicyOS release-version source of truth."""

import re
import tomllib
from importlib.metadata import version
from pathlib import Path

from app.main import app
from app.version import get_version

ROOT = Path(__file__).resolve().parents[1]
SEMVER = re.compile(
    r"^(0|[1-9]\d*)\.(0|[1-9]\d*)\.(0|[1-9]\d*)"
    r"(?:-([0-9A-Za-z-]+(?:\.[0-9A-Za-z-]+)*))?"
    r"(?:\+([0-9A-Za-z-]+(?:\.[0-9A-Za-z-]+)*))?$"
)
TAG = re.compile(
    r"^v(0|[1-9]\d*)\.(0|[1-9]\d*)\.(0|[1-9]\d*)"
    r"(?:-([0-9A-Za-z-]+(?:\.[0-9A-Za-z-]+)*))?"
    r"(?:\+([0-9A-Za-z-]+(?:\.[0-9A-Za-z-]+)*))?$"
)


def project_version() -> str:
    with (ROOT / "pyproject.toml").open("rb") as file:
        return tomllib.load(file)["project"]["version"]


def test_project_metadata_is_valid_semver_and_runtime_source_of_truth() -> None:
    authoritative = project_version()
    assert SEMVER.fullmatch(authoritative)
    assert version("policyos") == authoritative
    assert get_version() == authoritative
    assert app.version == authoritative
    assert app.openapi()["info"]["version"] == authoritative


def test_release_tag_convention_is_strict_semver_with_v_prefix() -> None:
    for valid in ("v1.2.3", "v0.1.0-rc.1", "v2.0.0+build.7"):
        assert TAG.fullmatch(valid)
    for invalid in ("1.2.3", "v1.2", "v01.2.3", "Sprint-13", "v0.13"):
        assert TAG.fullmatch(invalid) is None


def test_policy_document_exists_and_sprints_do_not_define_versions() -> None:
    policy = ROOT / "docs" / "03_OPERATIONS" / "VERSIONING-AND-RELEASE-POLICY.md"
    text = policy.read_text(encoding="utf-8")
    assert "pyproject.toml" in text
    assert "Sprint numbers do not determine" in text
