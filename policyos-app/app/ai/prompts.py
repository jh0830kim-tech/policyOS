"""Versioned, path-safe registry for approved agent system prompts."""

import hashlib
import re
from collections.abc import Mapping
from dataclasses import dataclass
from enum import StrEnum
from pathlib import Path
from typing import Protocol

from app.ai.domain import AgentIdentifier

SEMANTIC_VERSION_PATTERN = re.compile(
    r"^(0|[1-9]\d*)\.(0|[1-9]\d*)\.(0|[1-9]\d*)"
    r"(?:-[0-9A-Za-z-]+(?:\.[0-9A-Za-z-]+)*)?"
    r"(?:\+[0-9A-Za-z-]+(?:\.[0-9A-Za-z-]+)*)?$"
)


class PromptStatus(StrEnum):
    DRAFT = "draft"
    APPROVED = "approved"
    RETIRED = "retired"


class PromptRegistryError(Exception):
    """Base class for safe, typed prompt registry errors."""


class PromptNotFoundError(PromptRegistryError):
    pass


class EmptyPromptError(PromptRegistryError):
    pass


class DuplicatePromptError(PromptRegistryError):
    pass


class UnsafePromptPathError(PromptRegistryError):
    pass


class InvalidPromptVersionError(PromptRegistryError):
    pass


class PromptSource(Protocol):
    def read(self, source_path: str) -> str:
        """Read prompt content by a source-local path."""
        ...


class FilePromptSource:
    """Loads UTF-8 prompts strictly from one configured directory."""

    def __init__(self, root: Path) -> None:
        self.root = root.resolve()

    def read(self, source_path: str) -> str:
        candidate = (self.root / source_path).resolve()
        if not candidate.is_relative_to(self.root):
            raise UnsafePromptPathError("Prompt source path escapes the configured root")
        if not candidate.is_file():
            raise PromptNotFoundError(f"Prompt source not found: {source_path}")
        return candidate.read_text(encoding="utf-8")


class InMemoryPromptSource:
    """Deterministic prompt source for tests and dependency injection."""

    def __init__(self, prompts: Mapping[str, str]) -> None:
        self._prompts = dict(prompts)

    def read(self, source_path: str) -> str:
        try:
            return self._prompts[source_path]
        except KeyError as exc:
            raise PromptNotFoundError(f"Prompt source not found: {source_path}") from exc


@dataclass(frozen=True, slots=True)
class PromptDefinition:
    agent_name: AgentIdentifier
    prompt_name: str
    version: str
    status: PromptStatus
    source_path: str


@dataclass(frozen=True, slots=True)
class RegisteredPrompt:
    agent_name: AgentIdentifier
    prompt_name: str
    version: str
    content_hash: str
    status: PromptStatus
    source_path: str
    content: str


@dataclass(frozen=True, slots=True)
class PromptInvocation:
    """Keeps trusted system instructions separate from untrusted user input."""

    system_instruction: str
    user_input: str
    prompt: RegisteredPrompt


class PromptRegistry:
    def __init__(self, source: PromptSource) -> None:
        self._source = source
        self._prompts: dict[tuple[AgentIdentifier, str, str], RegisteredPrompt] = {}

    def register(self, definition: PromptDefinition) -> RegisteredPrompt:
        if not SEMANTIC_VERSION_PATTERN.fullmatch(definition.version):
            raise InvalidPromptVersionError(
                f"Invalid semantic version: {definition.version}"
            )
        if not definition.prompt_name.strip():
            raise EmptyPromptError("Prompt name must not be empty")

        key = (definition.agent_name, definition.prompt_name, definition.version)
        if key in self._prompts:
            raise DuplicatePromptError(
                "Prompt is already registered for the agent, name, and version"
            )

        content = self._source.read(definition.source_path)
        if not content.strip():
            raise EmptyPromptError(f"Prompt source is empty: {definition.source_path}")

        prompt = RegisteredPrompt(
            agent_name=definition.agent_name,
            prompt_name=definition.prompt_name,
            version=definition.version,
            content_hash=hashlib.sha256(content.encode("utf-8")).hexdigest(),
            status=definition.status,
            source_path=definition.source_path,
            content=content,
        )
        self._prompts[key] = prompt
        return prompt

    def get(
        self,
        agent_name: AgentIdentifier,
        version: str,
        *,
        prompt_name: str = "system",
    ) -> RegisteredPrompt:
        key = (agent_name, prompt_name, version)
        try:
            return self._prompts[key]
        except KeyError as exc:
            raise PromptNotFoundError(
                f"Prompt not registered: {agent_name.value}/{prompt_name}/{version}"
            ) from exc

    def prepare(
        self,
        agent_name: AgentIdentifier,
        version: str,
        user_input: str,
        *,
        prompt_name: str = "system",
    ) -> PromptInvocation:
        prompt = self.get(agent_name, version, prompt_name=prompt_name)
        return PromptInvocation(
            system_instruction=prompt.content,
            user_input=user_input,
            prompt=prompt,
        )
