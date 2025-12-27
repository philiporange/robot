"""
OpenAI Codex CLI agent implementation.

Wraps the `codex` CLI for headless execution with quiet mode support.
"""

import logging
from typing import Optional

from robot.base import BaseAgent
from robot.config import settings
from robot.registry import register_agent

logger = logging.getLogger(__name__)


@register_agent("codex")
class CodexAgent(BaseAgent):
    """OpenAI Codex CLI wrapper."""

    name = "codex"
    cli_command = "codex"
    supports_tools = True
    supports_streaming = False
    supports_system_prompt = False
    supports_resume = True
    default_model = "gpt-5.2-codex"

    # Model aliases for Codex
    MODEL_ALIASES = {
        "codex": "gpt-5.2-codex",
        "5.2": "gpt-5.2-codex",
        "5.1": "gpt-5.1-codex-max",
        "max": "gpt-5.1-codex-max",
        # Legacy aliases
        "o4-mini": "o4-mini",
        "o4": "o4",
        "gpt-4o": "gpt-4o",
    }

    def get_cli_path(self) -> str:
        return settings.codex_path

    def _resolve_model(self, model: str) -> str:
        """Resolve model alias to full Codex model name."""
        return self.MODEL_ALIASES.get(model, model)

    def get_env_vars(self) -> dict[str, str]:
        """
        Get environment variables for Codex CLI.

        Sets OPENAI_API_KEY and OPENAI_BASE_URL if configured.
        """
        env = {}

        api_key = self.config.api_key or settings.codex_api_key
        base_url = self.config.base_url or settings.codex_base_url

        if api_key:
            env["OPENAI_API_KEY"] = api_key
        if base_url:
            env["OPENAI_BASE_URL"] = base_url

        return env

    def build_command(
        self,
        prompt: str,
        model: Optional[str] = None,
        approval_mode: str = "full-auto",
        resume: Optional[bool] = None,
        session_id: Optional[str] = None,
        prompt_prefix: Optional[str] = None,
        **kwargs,
    ) -> list[str]:
        """
        Build the Codex CLI command.

        Args:
            prompt: The prompt to send
            model: Model name
            approval_mode: Approval mode (full-auto for non-interactive)
            resume: Whether to resume most recent session (--last)
            session_id: Specific session ID to resume
            prompt_prefix: Prefix to prepend to prompt (like AGENTS.md)
        """
        # Handle prompt_prefix by prepending to prompt
        prefix = prompt_prefix or self.config.prompt_prefix
        if prefix:
            prompt = f"{prefix}\n\n{prompt}"

        # Handle resume functionality
        # Uses: codex exec resume --last "prompt" or codex exec resume <id> "prompt"
        should_resume = resume if resume is not None else self.config.resume
        sess_id = session_id or self.config.session_id
        if sess_id is None and self.config.history_file:
            sess_id = str(self.config.history_file)

        if sess_id:
            # Resume specific session
            cmd = [self.get_cli_path(), "exec", "resume", sess_id, prompt]
        elif should_resume:
            # Resume most recent session
            cmd = [self.get_cli_path(), "exec", "resume", "--last", prompt]
        else:
            # Normal execution
            cmd = [self.get_cli_path(), "-q", prompt]

        if model:
            resolved = self._resolve_model(model)
            cmd.extend(["--model", resolved])

        cmd.extend(["--approval-mode", approval_mode])

        return cmd

    def parse_output(self, stdout: str, stderr: str) -> tuple[bool, str]:
        """Parse Codex output (text-based)."""
        if stderr and not stdout:
            return False, stderr
        return True, stdout.strip()
