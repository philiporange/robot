"""
Agent registry and factory.

Provides a central interface for discovering, instantiating, and running
coding agents. The Robot class is the main entry point for using the library.
"""

import logging
from pathlib import Path
from typing import Optional, Type

from robot.base import BaseAgent, AgentConfig
from robot.response import AgentResponse
from robot.prompt_loader import load_prompt, PromptConfig
from robot.config import settings

logger = logging.getLogger(__name__)

# Registry of available agent classes
_agent_registry: dict[str, Type[BaseAgent]] = {}


def register_agent(name: str):
    """Decorator to register an agent class."""
    def decorator(cls: Type[BaseAgent]):
        _agent_registry[name] = cls
        cls.name = name
        return cls
    return decorator


class Robot:
    """Main interface for running coding agents."""

    @classmethod
    def get(cls, agent: Optional[str] = None, config: Optional[AgentConfig] = None) -> BaseAgent:
        """
        Get an agent instance by name.

        Args:
            agent: Agent name (claude, codex, gemini, vibe, aider)
            config: Optional configuration

        Returns:
            Configured agent instance
        """
        agent = agent or settings.default_agent

        if agent not in _agent_registry:
            # Try to import agent module to trigger registration
            try:
                __import__(f"robot.agents.{agent}")
            except ImportError:
                pass

        if agent not in _agent_registry:
            raise ValueError(f"Unknown agent: {agent}. Available: {list(_agent_registry.keys())}")

        agent_cls = _agent_registry[agent]
        return agent_cls(config=config)

    @classmethod
    def run(
        cls,
        prompt: str,
        agent: Optional[str] = None,
        model: Optional[str] = None,
        working_dir: Optional[Path] = None,
        config: Optional[AgentConfig] = None,
        **kwargs,
    ) -> AgentResponse:
        """
        Run a prompt with the specified agent.

        Args:
            prompt: The prompt to send
            agent: Agent name (defaults to ROBOT_DEFAULT_AGENT)
            model: Model to use
            working_dir: Working directory (overrides config.working_dir)
            config: Agent configuration
            **kwargs: Additional agent-specific arguments

        Returns:
            AgentResponse with results
        """
        # Merge working_dir into config if provided
        if config is None:
            config = AgentConfig()
        if working_dir:
            config.working_dir = working_dir

        agent_instance = cls.get(agent, config=config)
        return agent_instance.run(
            prompt=prompt,
            model=model,
            working_dir=working_dir or config.working_dir,
            **kwargs,
        )

    @classmethod
    def run_task(
        cls,
        task: str,
        agent: Optional[str] = None,
        working_dir: Optional[Path] = None,
        config: Optional[AgentConfig] = None,
        variables: Optional[dict[str, str]] = None,
        **kwargs,
    ) -> AgentResponse:
        """
        Run a predefined task from YAML prompts.

        Args:
            task: Task name (e.g., "readme", "review")
            agent: Agent name
            working_dir: Working directory (overrides config.working_dir)
            config: Agent configuration
            variables: Template variables
            **kwargs: Additional arguments

        Returns:
            AgentResponse with results
        """
        agent = agent or settings.default_agent
        prompt_config = load_prompt(task)

        # Get agent-specific settings
        task_settings = prompt_config.get_settings(agent)
        model = task_settings.get("model")
        system_prompt = prompt_config.system or None

        # Render prompt with variables
        rendered_prompt = prompt_config.render(agent=agent, variables=variables)

        # Merge working_dir into config
        if config is None:
            config = AgentConfig()
        if working_dir:
            config.working_dir = working_dir

        agent_instance = cls.get(agent, config=config)
        return agent_instance.run(
            prompt=rendered_prompt,
            model=model,
            system_prompt=system_prompt,
            working_dir=working_dir or config.working_dir,
            **kwargs,
        )

    @classmethod
    def list_available(cls) -> list[str]:
        """List all available (installed) agents."""
        # Import all agents to populate registry
        cls._import_all_agents()

        available = []
        for name, agent_cls in _agent_registry.items():
            try:
                agent = agent_cls()
                if agent.is_available():
                    available.append(name)
            except Exception:
                pass
        return available

    @classmethod
    def list_registered(cls) -> list[str]:
        """List all registered agents (may not all be installed)."""
        cls._import_all_agents()
        return list(_agent_registry.keys())

    @classmethod
    def _import_all_agents(cls) -> None:
        """Import all agent modules to populate registry."""
        agent_names = ["claude", "codex", "gemini", "vibe", "aider", "openrouter", "zai"]
        for name in agent_names:
            try:
                __import__(f"robot.agents.{name}")
            except ImportError:
                pass
