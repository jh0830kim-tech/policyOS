"""Runtime access to the authoritative installed PolicyOS package version."""

from importlib.metadata import PackageNotFoundError, version

_DEVELOPMENT_FALLBACK = "0.0.0+unknown"


def get_version() -> str:
    """Return installed package metadata, or a deterministic unpackaged-tree marker."""
    try:
        return version("policyos")
    except PackageNotFoundError:
        return _DEVELOPMENT_FALLBACK
