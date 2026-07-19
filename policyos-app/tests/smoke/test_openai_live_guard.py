import pytest

from scripts.openai_smoke_test import require_opt_in


def test_live_openai_smoke_requires_explicit_opt_in(monkeypatch) -> None:
    monkeypatch.delenv("RUN_OPENAI_LIVE_TESTS", raising=False)
    with pytest.raises(SystemExit, match="disabled"):
        require_opt_in()