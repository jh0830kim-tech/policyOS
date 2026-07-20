"""DLP scanning reports pattern categories and counts, never matched values."""

import re
from typing import Protocol

from pydantic import BaseModel, ConfigDict


class DLPFinding(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)
    finding_type: str
    count: int
    severity: str
    redaction_required: bool
    transmission_blocked: bool
    review_required: bool


class DLPScanner(Protocol):
    def scan(self, text: str) -> tuple[DLPFinding, ...]: ...


class DeterministicDLPScanner:
    RULES = (
        ("api_key", re.compile(r"\bsk-[A-Za-z0-9_-]{16,}\b", re.I), "critical"),
        ("bearer_token", re.compile(r"\bbearer\s+[A-Za-z0-9._~+/-]+=*", re.I), "critical"),
        ("password", re.compile(r"\bpassword\s*[:=]\s*\S+", re.I), "high"),
        (
            "private_key",
            re.compile(r"-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----"),
            "critical",
        ),
        ("resident_registration", re.compile(r"\b\d{6}-?[1-4]\d{6}\b"), "high"),
        ("account_number", re.compile(r"\b\d{2,4}-\d{2,6}-\d{4,8}\b"), "medium"),
        ("email", re.compile(r"\b[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}\b", re.I), "medium"),
        (
            "phone",
            re.compile(r"(?<!\d)(?:\+?82[- ]?)?0?1[016789][- ]?\d{3,4}[- ]?\d{4}(?!\d)"),
            "medium",
        ),
    )

    def __init__(self, custom_terms: tuple[str, ...] = ()) -> None:
        self.custom = tuple(re.compile(re.escape(term), re.I) for term in custom_terms if term)

    def scan(self, text: str) -> tuple[DLPFinding, ...]:
        findings = []
        for name, pattern, severity in self.RULES:
            count = len(pattern.findall(text))
            if count:
                findings.append(
                    DLPFinding(
                        finding_type=name,
                        count=count,
                        severity=severity,
                        redaction_required=True,
                        transmission_blocked=severity in {"high", "critical"},
                        review_required=True,
                    )
                )
        count = sum(len(pattern.findall(text)) for pattern in self.custom)
        if count:
            findings.append(
                DLPFinding(
                    finding_type="custom_secret",
                    count=count,
                    severity="high",
                    redaction_required=True,
                    transmission_blocked=True,
                    review_required=True,
                )
            )
        return tuple(findings)
