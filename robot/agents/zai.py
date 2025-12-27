"""
Z.ai agent implementation.

Wraps the aider CLI to access Z.ai's hosted models including GLM-4.7,
Claude variants, and other models via their OpenAI-compatible API.
"""

import logging
from pathlib import Path
from typing import Optional

from robot.base import BaseAgent
from robot.config import settings
from robot.registry import register_agent

logger = logging.getLogger(__name__)


@register_agent("zai")
class ZaiAgent(BaseAgent):
    """Z.ai agent using aider CLI with Z.ai's OpenAI-compatible API."""

    name = "zai"
    cli_command = "aider"
    supports_tools = False
    supports_streaming = True
    supports_system_prompt = False
    supports_resume = True
    default_model = "glm-4.7"

    # Z.ai model aliases
    MODEL_ALIASES = {
        "glm": "glm-4.7",
        "glm-4": "glm-4.7",
        "glm-4.7": "glm-4.7",
        "claude": "claude-sonnet-4-20250514",
        "sonnet": "claude-sonnet-4-20250514",
        "opus": "claude-opus-4-20250514",
        "haiku": "claude-haiku-4-20250414",
    }

    # Z.ai API endpoint
    ZAI_BASE_URL = "https://api.z.ai/api/openai"

    def get_cli_path(self) -> str:
        return settings.aider_path

    def get_env_vars(self) -> dict[str, str]:
        """
        Get environment variables for Z.ai via aider.

        Uses OPENAI_API_KEY and OPENAI_API_BASE for Z.ai's
        OpenAI-compatible endpoint.
        """
        import os

        env = {}

        # Z.ai API key - check various sources
        api_key = (
            self.config.api_key
            or os.getenv("ZAI_API_KEY")
            or os.getenv("ROBOT_ZAI_API_KEY")
            or settings.claude_api_key  # Z.ai often uses same key as Anthropic
        )

        base_url = self.config.base_url or self.ZAI_BASE_URL

        if api_key:
            env["OPENAI_API_KEY"] = api_key
        if base_url:
            env["OPENAI_API_BASE"] = base_url

        return env

    def _resolve_model(self, model: str) -> str:
        """Resolve model alias to Z.ai model name."""
        return self.MODEL_ALIASES.get(model, model)

    def build_command(
        self,
        prompt: str,
        model: Optional[str] = None,
        files: Optional[list[str]] = None,
        auto_commits: bool = False,
        resume: Optional[bool] = None,
        history_file: Optional[str] = None,
        prompt_prefix: Optional[str] = None,
        **kwargs,
    ) -> list[str]:
        """
        Build the aider CLI command for Z.ai.

        Args:
            prompt: The message/instruction
            model: Model name (glm-4.7, claude, etc.)
            files: Files to include in the edit context
            auto_commits: Whether to auto-commit changes
            resume: Whether to restore chat history
            history_file: Chat history file path
            prompt_prefix: Prefix to prepend to prompt
        """
        # Handle prompt_prefix
        prefix = prompt_prefix or self.config.prompt_prefix
        if prefix:
            prompt = f"{prefix}\n\n{prompt}"

        model = model or self.default_model
        resolved = self._resolve_model(model)

        # Use openai/ prefix for aider with custom OpenAI-compatible endpoints
        if not resolved.startswith("openai/"):
            resolved = f"openai/{resolved}"

        cmd = [
            self.get_cli_path(),
            "--message", prompt,
            "--yes",
            "--model", resolved,
            "--no-git",
        ]

        if not auto_commits:
            cmd.append("--no-auto-commits")

        # Handle resume/restore functionality
        hist_file = history_file
        if hist_file is None and self.config.history_file:
            hist_file = str(self.config.history_file)
        if hist_file is None:
            hist_file = self.config.session_id

        should_resume = resume if resume is not None else self.config.resume

        if hist_file:
            cmd.extend(["--chat-history-file", hist_file])
            if Path(hist_file).exists() or should_resume:
                cmd.append("--restore-chat-history")
        elif should_resume:
            cmd.append("--restore-chat-history")

        if files:
            cmd.extend(files)

        return cmd

    def parse_output(self, stdout: str, stderr: str) -> tuple[bool, str]:
        """Parse aider output."""
        output = stdout.strip()
        if not output and stderr:
            output = stderr.strip()

        if not output:
            return False, "Empty response"

        return True, output

    def run_on_files(
        self,
        prompt: str,
        files: list[str | Path],
        model: Optional[str] = None,
        working_dir: Optional[Path] = None,
        auto_commits: bool = False,
        **kwargs,
    ):
        """
        Run Z.ai agent targeting specific files.

        Args:
            prompt: The instruction
            files: Files to include in context
            model: Model to use (glm-4.7, claude, etc.)
            working_dir: Working directory
            auto_commits: Whether to auto-commit changes
        """
        file_strs = [str(f) for f in files]
        return self.run(
            prompt=prompt,
            model=model,
            working_dir=working_dir,
            files=file_strs,
            auto_commits=auto_commits,
            **kwargs,
        )
