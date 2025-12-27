"""
Agent implementations for various CLI coding tools.

Each agent module implements the BaseAgent interface for a specific
CLI tool (Claude Code, Codex, Gemini, Vibe, Aider) or API gateway
(OpenRouter, Z.ai).
"""

# Import agents to register them
from robot.agents import claude, codex, gemini, vibe, aider, openrouter, zai

__all__ = ["claude", "codex", "gemini", "vibe", "aider", "openrouter", "zai"]
