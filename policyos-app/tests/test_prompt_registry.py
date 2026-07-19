import hashlib
from pathlib import Path

import pytest

from app.ai.domain import AgentIdentifier
from app.ai.prompts import (
    DuplicatePromptError,
    EmptyPromptError,
    FilePromptSource,
    InMemoryPromptSource,
    InvalidPromptVersionError,
    PromptDefinition,
    PromptNotFoundError,
    PromptRegistry,
    PromptStatus,
    UnsafePromptPathError,
)


def definition(
    *,
    version: str = "1.0.0",
    source_path: str = "policy.system.md",
) -> PromptDefinition:
    return PromptDefinition(
        agent_name=AgentIdentifier.POLICY_RESEARCH,
        prompt_name="system",
        version=version,
        status=PromptStatus.APPROVED,
        source_path=source_path,
    )


def test_normal_prompt_load_and_version_selection() -> None:
    source = InMemoryPromptSource({"v1": "First prompt", "v2": "Second prompt"})
    registry = PromptRegistry(source)
    first = registry.register(definition(version="1.0.0", source_path="v1"))
    second = registry.register(definition(version="2.0.0", source_path="v2"))

    assert registry.get(AgentIdentifier.POLICY_RESEARCH, "1.0.0") is first
    assert registry.get(AgentIdentifier.POLICY_RESEARCH, "2.0.0") is second


def test_content_hash_is_deterministic_sha256() -> None:
    content = "Stable system instruction."
    first = PromptRegistry(InMemoryPromptSource({"prompt": content})).register(
        definition(source_path="prompt")
    )
    second = PromptRegistry(InMemoryPromptSource({"prompt": content})).register(
        definition(source_path="prompt")
    )

    expected = hashlib.sha256(content.encode("utf-8")).hexdigest()
    assert first.content_hash == second.content_hash == expected


def test_missing_prompt_source_and_selection_are_typed_errors() -> None:
    registry = PromptRegistry(InMemoryPromptSource({}))

    with pytest.raises(PromptNotFoundError):
        registry.register(definition())
    with pytest.raises(PromptNotFoundError):
        registry.get(AgentIdentifier.POLICY_RESEARCH, "1.0.0")


@pytest.mark.parametrize("content", ["", "  \n\t"])
def test_empty_prompt_is_rejected(content: str) -> None:
    registry = PromptRegistry(InMemoryPromptSource({"policy.system.md": content}))

    with pytest.raises(EmptyPromptError):
        registry.register(definition())


def test_duplicate_agent_name_and_version_is_rejected() -> None:
    registry = PromptRegistry(InMemoryPromptSource({"policy.system.md": "Prompt"}))
    registry.register(definition())

    with pytest.raises(DuplicatePromptError):
        registry.register(definition())


def test_file_source_loads_existing_prompts_directory() -> None:
    source = FilePromptSource(Path("prompts"))
    registry = PromptRegistry(source)
    prompt = registry.register(
        definition(source_path="policy-research.system.md")
    )

    assert prompt.content.startswith("# Policy Research AI")
    assert prompt.source_path == "policy-research.system.md"


@pytest.mark.parametrize("source_path", ["../secret.md", "../../CODEX.md"])
def test_file_source_blocks_path_traversal(source_path: str) -> None:
    source = FilePromptSource(Path("prompts"))

    with pytest.raises(UnsafePromptPathError):
        source.read(source_path)


def test_system_instruction_and_user_input_remain_separate() -> None:
    registry = PromptRegistry(
        InMemoryPromptSource({"policy.system.md": "Trusted system instruction"})
    )
    registry.register(definition())

    invocation = registry.prepare(
        AgentIdentifier.POLICY_RESEARCH,
        "1.0.0",
        "Untrusted user request",
    )

    assert invocation.system_instruction == "Trusted system instruction"
    assert invocation.user_input == "Untrusted user request"
    assert invocation.user_input not in invocation.system_instruction


@pytest.mark.parametrize("version", ["1", "v1.0.0", "1.0", "01.0.0"])
def test_invalid_semantic_version_is_rejected(version: str) -> None:
    registry = PromptRegistry(InMemoryPromptSource({"policy.system.md": "Prompt"}))

    with pytest.raises(InvalidPromptVersionError):
        registry.register(definition(version=version))
