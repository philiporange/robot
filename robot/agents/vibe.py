"""
Mistral Vibe CLI agent implementation.

Wraps the `vibe` CLI for headless execution via stdin/pipe mode.
"""

import logging
from typing import Optional

from robot.base import BaseAgent
from robot.config import settings
from robot.registry import register_agent
from robot.response import AgentResponse

logger = logging.getLogger(__name__)


@register_agent("vibe")
class VibeAgent(BaseAgent):
    """Mistral Vibe CLI wrapper."""

    name = "vibe"
    cli_command = "vibe"
    supports_tools = False
    supports_streaming = True
    supports_system_prompt = False
    supports_resume = True
    default_model = "mistral-large"

    def get_cli_path(self) -> str:
        return settings.vibe_path

    def get_env_vars(self) -> dict[str, str]:
        """
        Get environment variables for Vibe CLI.

        Sets MISTRAL_API_KEY and MISTRAL_BASE_URL if configured.
        """
        env = {}

        api_key = self.config.api_key or settings.vibe_api_key
        base_url = self.config.base_url or settings.vibe_base_url

        if api_key:
            env["MISTRAL_API_KEY"] = api_key
        if base_url:
            env["MISTRAL_BASE_URL"] = base_url

        return env

    def build_command(
        self,
        prompt: str,
        model: Optional[str] = None,
        resume: Optional[bool] = None,
        session_id: Optional[str] = None,
        prompt_prefix: Optional[str] = None,
        **kwargs,
    ) -> list[str]:
        """
        Build the Vibe CLI command.

        Args:
            prompt: The prompt (passed via -p flag)
            model: Model to use
            resume: Whether to continue most recent session
            session_id: Specific session ID to resume
            prompt_prefix: Prefix to prepend to prompt (like AGENTS.md)
        """
        # Handle prompt_prefix by prepending to prompt
        prefix = prompt_prefix or self.config.prompt_prefix
        if prefix:
            prompt = f"{prefix}\n\n{prompt}"

        cmd = [self.get_cli_path(), "--auto-approve"]

        # Handle resume/continue functionality
        should_resume = resume if resume is not None else self.config.resume
        sess_id = session_id or self.config.session_id
        if sess_id is None and self.config.history_file:
            sess_id = str(self.config.history_file)

        if sess_id:
            cmd.extend(["--resume", sess_id])
        elif should_resume:
            cmd.append("--continue")

        # Use -p for programmatic mode
        cmd.extend(["-p", prompt])

        if model:
            cmd.extend(["--model", model])

        return cmd

    def parse_output(self, stdout: str, stderr: str) -> tuple[bool, str]:
        """Parse Vibe output (text-based)."""
        if stderr and not stdout:
            return False, stderr
        return True, stdout.strip()
