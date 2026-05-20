"""
Command Code CLI agent implementation.

Wraps the `cmd` CLI (also installed as `commandcode`) for headless execution
via its `-p` print mode. Defaults to deepseek-v4-pro, with aliases for other
Command Code models. Uses --yolo and --skip-onboarding so non-interactive runs
do not prompt for permissions or taste onboarding.
"""

import logging
from typing import Optional

from robot.base import BaseAgent
from robot.config import settings
from robot.registry import register_agent

logger = logging.getLogger(__name__)


@register_agent("commandcode")
class CommandCodeAgent(BaseAgent):
    """Command Code CLI wrapper."""

    name = "commandcode"
    cli_command = "cmd"
    supports_tools = True
    supports_streaming = False
    supports_system_prompt = False
    supports_resume = True
    default_model = "deepseek/deepseek-v4-pro"

    MODEL_ALIASES = {
        # Default DeepSeek
        "deepseek": "deepseek/deepseek-v4-pro",
        "deepseek-v4-pro": "deepseek/deepseek-v4-pro",
        "deepseek-v4-flash": "deepseek/deepseek-v4-flash",
        "flash": "deepseek/deepseek-v4-flash",
        # Claude
        "claude": "claude-opus-4-7",
        "opus": "claude-opus-4-7",
        "claude-opus-4-7": "claude-opus-4-7",
        "claude-opus-4-6": "claude-opus-4-7",
        "sonnet": "claude-sonnet-4-6",
        "sonnet-4.6": "claude-sonnet-4-6",
        "claude-sonnet-4-6": "claude-sonnet-4-6",
        "haiku": "claude-haiku-4-5-20251001",
        # OpenAI
        "gpt-5.4": "gpt-5.4",
        "gpt-5.4-mini": "gpt-5.4-mini",
        "gpt-5.5": "gpt-5.5",
        "gpt-5.3-codex": "gpt-5.3-codex",
        # MiniMax
        "minimax": "minimax/minimax-m2.7",
        "minimax-m2.7": "minimax/minimax-m2.7",
        "minimax-m2.5": "minimax/minimax-m2.5",
    }

    def get_cli_path(self) -> str:
        return settings.commandcode_path

    def _resolve_model(self, model: str) -> str:
        """Resolve model alias to canonical Command Code model id."""
        return self.MODEL_ALIASES.get(model, model)

    def get_env_vars(self) -> dict[str, str]:
        """
        Get environment variables for Command Code CLI.

        Sets COMMAND_CODE_API_KEY and COMMANDCODE_API_URL if configured.
        When no key is configured, vars are left unset so the CLI uses the
        credentials stored in ~/.commandcode/auth.json.
        """
        env = {}

        api_key = self.config.api_key or settings.commandcode_api_key
        base_url = self.config.base_url or settings.commandcode_base_url

        if api_key:
            env["COMMAND_CODE_API_KEY"] = api_key
        if base_url:
            env["COMMANDCODE_API_URL"] = base_url

        return env

    def build_command(
        self,
        prompt: str,
        model: Optional[str] = None,
        prompt_prefix: Optional[str] = None,
        add_dirs: Optional[list[str]] = None,
        resume: Optional[bool] = None,
        session_id: Optional[str] = None,
        max_turns: Optional[int] = None,
        verbose: bool = False,
        **kwargs,
    ) -> list[str]:
        """
        Build the Command Code CLI command.

        Args:
            prompt: The prompt to send (passed via -p)
            model: Model alias or canonical id
            prompt_prefix: Prefix to prepend to prompt (like AGENTS.md)
            add_dirs: Additional directories to add to workspace context
            resume: Whether to continue the most recent session
            session_id: Specific session name to resume (-r <name>)
            max_turns: Maximum conversation turns in print mode
            verbose: Stream tool execution progress to stderr
        """
        prefix = prompt_prefix or self.config.prompt_prefix
        if prefix:
            prompt = f"{prefix}\n\n{prompt}"

        cmd = [self.get_cli_path()]

        # Resume handling: prefer explicit session id, otherwise --continue
        should_resume = resume if resume is not None else self.config.resume
        sess_id = session_id or self.config.session_id
        if sess_id is None and self.config.history_file:
            sess_id = str(self.config.history_file)

        if sess_id:
            cmd.extend(["--resume", sess_id])
        elif should_resume:
            cmd.append("--continue")

        # Non-interactive print mode with the prompt
        cmd.extend(["-p", prompt])

        if model:
            cmd.extend(["--model", self._resolve_model(model)])

        # Additional workspace directories
        dirs_to_add = list(add_dirs) if add_dirs else []
        if self.config.working_dir:
            dirs_to_add.append(str(self.config.working_dir))
        for d in dirs_to_add:
            cmd.extend(["--add-dir", str(d)])

        if max_turns is not None:
            cmd.extend(["--max-turns", str(max_turns)])

        if verbose:
            cmd.append("--verbose")

        # Headless-friendly flags
        cmd.append("--yolo")
        cmd.append("--skip-onboarding")
        cmd.append("--trust")

        return cmd

    def parse_output(self, stdout: str, stderr: str) -> tuple[bool, str]:
        """Parse Command Code output (text-based)."""
        if stderr and not stdout:
            return False, stderr
        return True, stdout.strip()
