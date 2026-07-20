"""Unicode-safe deterministic query normalization and tokenization."""

import re
import unicodedata
from typing import Protocol

_CONTROL = re.compile(r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]")
_QUOTED = re.compile(r'"([^"\r\n]+)"')
_TOKEN = re.compile(r"[\w가-힣]+", re.UNICODE)


class QueryTokenizer(Protocol):
    def tokenize(self, text: str) -> tuple[str, ...]: ...


class SimpleKoreanAwareTokenizer:
    """Conservative tokens; no invented synonyms or external morphology."""

    _PARTICLES = (
        "으로",
        "에서",
        "에게",
        "까지",
        "부터",
        "은",
        "는",
        "이",
        "가",
        "을",
        "를",
        "의",
        "에",
        "와",
        "과",
        "도",
    )

    def tokenize(self, text: str) -> tuple[str, ...]:
        values = []
        for raw in _TOKEN.findall(text.casefold()):
            token = raw
            for suffix in self._PARTICLES:
                if len(token) > len(suffix) + 1 and token.endswith(suffix):
                    token = token[: -len(suffix)]
                    break
            if token:
                values.append(token)
        return tuple(values)


class FakeTokenizer:
    def tokenize(self, text: str) -> tuple[str, ...]:
        return tuple(text.casefold().split())


class QueryNormalizer:
    def __init__(self, tokenizer: QueryTokenizer | None = None, *, max_length: int = 8000) -> None:
        self.tokenizer = tokenizer or SimpleKoreanAwareTokenizer()
        self.max_length = max_length

    def normalize(self, text: str) -> tuple[str, tuple[str, ...], tuple[str, ...]]:
        cleaned = _CONTROL.sub("", unicodedata.normalize("NFKC", text))
        cleaned = " ".join(cleaned.split())
        if not cleaned:
            raise ValueError("Query must not be empty")
        if len(cleaned) > self.max_length:
            raise ValueError("Query exceeds maximum length")
        phrases = tuple(" ".join(item.split()).casefold() for item in _QUOTED.findall(cleaned))
        normalized = cleaned.casefold()
        return normalized, self.tokenizer.tokenize(normalized), phrases
