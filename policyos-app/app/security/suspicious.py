"""Deterministic prompt-injection and suspicious-content findings."""

import re
from enum import StrEnum
from typing import Protocol

from pydantic import BaseModel, ConfigDict


class SuspiciousContentSeverity(StrEnum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class PromptInjectionFlag(StrEnum):
    INSTRUCTION_OVERRIDE = "instruction_override"
    SECRET_EXFILTRATION = "secret_exfiltration"
    TOOL_COERCION = "tool_coercion"
    SCRIPT_CONTENT = "script_content"
    OBFUSCATION = "obfuscation"
    ACCESS_BYPASS = "access_bypass"


class SuspiciousContentFinding(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)
    flag: PromptInjectionFlag
    count: int
    severity: SuspiciousContentSeverity
    exclude_from_agent_context: bool
    review_required: bool


class SuspiciousContentDetector(Protocol):
    def scan(self, text: str) -> tuple[SuspiciousContentFinding, ...]: ...


class DeterministicSuspiciousContentDetector:
    RULES = (
        (
            PromptInjectionFlag.INSTRUCTION_OVERRIDE,
            SuspiciousContentSeverity.HIGH,
            re.compile(r"ignore (?:all |the )?(?:previous|prior) instructions", re.I),
        ),
        (
            PromptInjectionFlag.INSTRUCTION_OVERRIDE,
            SuspiciousContentSeverity.HIGH,
            re.compile(r"system prompt.{0,20}(?:출력|공개)", re.I),
        ),
        (
            PromptInjectionFlag.SECRET_EXFILTRATION,
            SuspiciousContentSeverity.CRITICAL,
            re.compile(r"(?:비밀키|api key|credential).{0,30}(?:공개|전송|send)", re.I),
        ),
        (
            PromptInjectionFlag.TOOL_COERCION,
            SuspiciousContentSeverity.HIGH,
            re.compile(r"(?:execute|run|호출).{0,20}(?:tool|command|도구|명령)", re.I),
        ),
        (
            PromptInjectionFlag.SCRIPT_CONTENT,
            SuspiciousContentSeverity.HIGH,
            re.compile(r"<script\b|javascript:", re.I),
        ),
        (
            PromptInjectionFlag.OBFUSCATION,
            SuspiciousContentSeverity.MEDIUM,
            re.compile(r"(?:[A-Za-z0-9+/]{80,}={0,2})"),
        ),
        (
            PromptInjectionFlag.ACCESS_BYPASS,
            SuspiciousContentSeverity.CRITICAL,
            re.compile(r"(?:bypass|우회).{0,20}(?:permission|권한|policy|정책)", re.I),
        ),
    )

    def scan(self, text: str) -> tuple[SuspiciousContentFinding, ...]:
        findings = []
        for flag, severity, pattern in self.RULES:
            count = len(pattern.findall(text))
            if count:
                findings.append(
                    SuspiciousContentFinding(
                        flag=flag,
                        count=count,
                        severity=severity,
                        exclude_from_agent_context=severity
                        in {SuspiciousContentSeverity.HIGH, SuspiciousContentSeverity.CRITICAL},
                        review_required=True,
                    )
                )
        return tuple(findings)
