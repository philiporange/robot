"""
Robot - Unified Python interface for CLI-based coding agents.

Provides a consistent API for invoking AI coding assistants (Claude Code,
OpenAI Codex, Gemini CLI, Mistral Vibe, Aider) in headless mode with
YAML-based prompt configuration. Supports superagent mode for spawning
subagents to handle complex multi-step tasks.
"""

from robot.response import AgentResponse
from robot.registry import Robot
from robot.base import BaseAgent
from robot.superagent import SuperAgent, get_superagent_prefix, run_subagent

__version__ = "0.1.0"
__all__ = [
    "Robot",
    "AgentResponse",
    "BaseAgent",
    "SuperAgent",
    "get_superagent_prefix",
    "run_subagent",
]
