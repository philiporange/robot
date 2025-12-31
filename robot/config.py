"""
Configuration management with dotenv support.

Loads settings from environment variables with sensible defaults.
Agent-specific paths and settings can be overridden via ROBOT_* env vars.
"""

import os
import shutil
from pathlib import Path
from dataclasses import dataclass, field
from typing import Optional

from dotenv import load_dotenv

load_dotenv()


def _get_path(env_var: str, default: str) -> str:
    """Get path from env var, falling back to PATH lookup."""
    path = os.getenv(env_var)
    if path:
        return path
    found = shutil.which(default)
    return found if found else default


@dataclass
class Settings:
    """Global settings for Robot."""

    # Agent binary paths
    claude_path: str = field(default_factory=lambda: _get_path("ROBOT_CLAUDE_PATH", "claude"))
    codex_path: str = field(default_factory=lambda: _get_path("ROBOT_CODEX_PATH", "codex"))
    gemini_path: str = field(default_factory=lambda: _get_path("ROBOT_GEMINI_PATH", "gemini"))
    vibe_path: str = field(default_factory=lambda: _get_path("ROBOT_VIBE_PATH", "vibe"))
    aider_path: str = field(default_factory=lambda: _get_path("ROBOT_AIDER_PATH", "aider"))

    # Claude API configuration
    claude_api_key: Optional[str] = field(
        default_factory=lambda: os.getenv("ROBOT_CLAUDE_API_KEY") or os.getenv("ANTHROPIC_AUTH_TOKEN")
    )
    claude_base_url: Optional[str] = field(
        default_factory=lambda: os.getenv("ROBOT_CLAUDE_BASE_URL") or os.getenv("ANTHROPIC_BASE_URL")
    )

    # OpenAI/Codex API configuration
    codex_api_key: Optional[str] = field(
        default_factory=lambda: os.getenv("ROBOT_CODEX_API_KEY") or os.getenv("OPENAI_API_KEY")
    )
    codex_base_url: Optional[str] = field(
        default_factory=lambda: os.getenv("ROBOT_CODEX_BASE_URL") or os.getenv("OPENAI_BASE_URL")
    )

    # Gemini API configuration
    gemini_api_key: Optional[str] = field(
        default_factory=lambda: os.getenv("ROBOT_GEMINI_API_KEY") or os.getenv("GOOGLE_API_KEY")
    )
    gemini_base_url: Optional[str] = field(
        default_factory=lambda: os.getenv("ROBOT_GEMINI_BASE_URL")
    )

    # Mistral/Vibe API configuration
    vibe_api_key: Optional[str] = field(
        default_factory=lambda: os.getenv("ROBOT_VIBE_API_KEY") or os.getenv("MISTRAL_API_KEY")
    )
    vibe_base_url: Optional[str] = field(
        default_factory=lambda: os.getenv("ROBOT_VIBE_BASE_URL")
    )

    # Aider API configuration (uses various backends)
    aider_api_key: Optional[str] = field(
        default_factory=lambda: os.getenv("ROBOT_AIDER_API_KEY")
    )
    aider_base_url: Optional[str] = field(
        default_factory=lambda: os.getenv("ROBOT_AIDER_BASE_URL")
    )

    # OpenRouter API configuration
    openrouter_api_key: Optional[str] = field(
        default_factory=lambda: os.getenv("ROBOT_OPENROUTER_API_KEY") or os.getenv("OPENROUTER_API_KEY") or "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"
    )
    openrouter_base_url: Optional[str] = field(
        default_factory=lambda: os.getenv("ROBOT_OPENROUTER_BASE_URL") or "https://openrouter.ai/api/v1"
    )

    # Defaults
    default_agent: str = field(
        default_factory=lambda: os.getenv("ROBOT_DEFAULT_AGENT", "claude")
    )
    default_timeout: int = field(
        default_factory=lambda: int(os.getenv("ROBOT_DEFAULT_TIMEOUT", "180"))
    )
    max_retries: int = field(
        default_factory=lambda: int(os.getenv("ROBOT_MAX_RETRIES", "3"))
    )
    rate_limit: int = field(
        default_factory=lambda: int(os.getenv("ROBOT_RATE_LIMIT", "10"))
    )

    # Paths
    prompts_dir: Path = field(
        default_factory=lambda: Path(
            os.getenv("ROBOT_PROMPTS_DIR", "~/.robot/prompts")
        ).expanduser()
    )
    temp_dir: Path = field(
        default_factory=lambda: Path("/tmp/robot")
    )

    # Web server settings
    server_host: str = field(
        default_factory=lambda: os.getenv("ROBOT_SERVER_HOST", "localhost")
    )
    server_port: int = field(
        default_factory=lambda: int(os.getenv("ROBOT_SERVER_PORT", "9999"))
    )

    def get_agent_path(self, agent: str) -> str:
        """Get CLI path for a specific agent."""
        paths = {
            "claude": self.claude_path,
            "codex": self.codex_path,
            "gemini": self.gemini_path,
            "vibe": self.vibe_path,
            "aider": self.aider_path,
        }
        return paths.get(agent, agent)

    def get_agent_api_key(self, agent: str) -> Optional[str]:
        """Get API key for a specific agent."""
        keys = {
            "claude": self.claude_api_key,
            "codex": self.codex_api_key,
            "gemini": self.gemini_api_key,
            "vibe": self.vibe_api_key,
            "aider": self.aider_api_key,
            "openrouter": self.openrouter_api_key,
        }
        return keys.get(agent)

    def get_agent_base_url(self, agent: str) -> Optional[str]:
        """Get base URL for a specific agent."""
        urls = {
            "claude": self.claude_base_url,
            "codex": self.codex_base_url,
            "gemini": self.gemini_base_url,
            "vibe": self.vibe_base_url,
            "aider": self.aider_base_url,
            "openrouter": self.openrouter_base_url,
        }
        return urls.get(agent)


settings = Settings()
