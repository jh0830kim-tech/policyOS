"""Explicit in-memory registry for dependency-injected AI agents."""

from collections.abc import Iterable

from app.ai.agent import Agent
from app.ai.domain import AgentCapability, AgentIdentifier


class AgentRegistryError(Exception):
    """Base class for safe, typed registry errors."""


class DuplicateAgentError(AgentRegistryError):
    def __init__(self, name: AgentIdentifier) -> None:
        self.name = name
        super().__init__(f"Agent is already registered: {name.value}")


class UnknownAgentError(AgentRegistryError):
    def __init__(self, name: AgentIdentifier | str) -> None:
        self.name = name
        safe_name = name.value if isinstance(name, AgentIdentifier) else name
        super().__init__(f"Unknown agent: {safe_name}")


class AgentRegistry:
    """Stores explicitly registered agent instances by stable name."""

    def __init__(self, agents: Iterable[Agent] = ()) -> None:
        self._agents: dict[AgentIdentifier, Agent] = {}
        for agent in agents:
            self.register(agent)

    def register(self, agent: Agent) -> None:
        if agent.name in self._agents:
            raise DuplicateAgentError(agent.name)
        self._agents[agent.name] = agent

    def get(self, name: AgentIdentifier | str) -> Agent:
        try:
            identifier = name if isinstance(name, AgentIdentifier) else AgentIdentifier(name)
        except ValueError as exc:
            raise UnknownAgentError(name) from exc

        try:
            return self._agents[identifier]
        except KeyError as exc:
            raise UnknownAgentError(identifier) from exc

    def list(self) -> tuple[Agent, ...]:
        return tuple(self._agents.values())

    def with_capability(self, capability: AgentCapability) -> tuple[Agent, ...]:
        return tuple(
            agent for agent in self._agents.values() if capability in agent.capabilities
        )
