"""
Aider CLI agent implementation.

Wraps the `aider` CLI for headless execution with --message flag.
Aider has strong git integration and can target specific files.
"""

import logging
from pathlib import Path
from typing import Optional

from robot.base import BaseAgent
from robot.config import settings
from robot.registry import register_agent

logger = logging.getLogger(__name__)


@register_agent("aider")
class AiderAgent(BaseAgent):
    """Aider CLI wrapper."""

    name = "aider"
    cli_command = "aider"
    supports_tools = False
    supports_streaming = True
    supports_system_prompt = False
    supports_resume = True
    default_model = "sonnet"

    # Model aliases (aider uses various backends)
    MODEL_ALIASES = {
        "haiku": "claude-3-5-haiku-latest",
        "sonnet": "claude-3-5-sonnet-latest",
        "opus": "claude-3-opus-latest",
        "gpt4": "gpt-4o",
        "o1": "o1-preview",
    }

    def get_cli_path(self) -> str:
        return settings.aider_path

    def get_env_vars(self) -> dict[str, str]:
        """
        Get environment variables for Aider CLI.

        Aider uses various backends (Anthropic, OpenAI, etc), so we set
        environment variables for all supported providers.
        """
        env = {}

        # Aider-specific config takes priority
        api_key = self.config.api_key or settings.aider_api_key
        base_url = self.config.base_url or settings.aider_base_url

        if api_key:
            # Aider uses ANTHROPIC_API_KEY for Claude models
            env["ANTHROPIC_API_KEY"] = api_key
            # Also set OpenAI key for OpenAI models
            env["OPENAI_API_KEY"] = api_key

        if base_url:
            env["ANTHROPIC_BASE_URL"] = base_url
            env["OPENAI_BASE_URL"] = base_url

        return env

    def _resolve_model(self, model: str) -> str:
        """Resolve model alias to full name."""
        return self.MODEL_ALIASES.get(model, model)

    def build_command(
        self,
        prompt: str,
        model: Optional[str] = None,
        files: Optional[list[str]] = None,
        auto_commits: bool = False,
        resume: Optional[bool] = None,
        chat_history_file: Optional[str] = None,
        history_file: Optional[str] = None,
        prompt_prefix: Optional[str] = None,
        **kwargs,
    ) -> list[str]:
        """
        Build the Aider CLI command.

        Args:
            prompt: The message/instruction
            model: Model alias or full name
            files: Files to include in the edit context
            auto_commits: Whether to auto-commit changes
            resume: Whether to restore chat history
            chat_history_file: Specific chat history file to restore (deprecated, use history_file)
            history_file: Chat history file path (auto-resumes if exists)
            prompt_prefix: Prefix to prepend to prompt (like AGENTS.md)
        """
        from pathlib import Path

        # Handle prompt_prefix by prepending to prompt
        prefix = prompt_prefix or self.config.prompt_prefix
        if prefix:
            prompt = f"{prefix}\n\n{prompt}"

        cmd = [self.get_cli_path(), "--message", prompt, "--yes"]

        if model:
            resolved = self._resolve_model(model)
            cmd.extend(["--model", resolved])

        if not auto_commits:
            cmd.append("--no-auto-commits")

        # Handle resume/restore functionality
        # Priority: history_file param > chat_history_file param > config.history_file > config.session_id
        hist_file = history_file or chat_history_file
        if hist_file is None and self.config.history_file:
            hist_file = str(self.config.history_file)
        if hist_file is None:
            hist_file = self.config.session_id

        should_resume = resume if resume is not None else self.config.resume

        if hist_file:
            cmd.extend(["--chat-history-file", hist_file])
            # Auto-resume if file exists, or if resume explicitly requested
            if Path(hist_file).exists() or should_resume:
                cmd.append("--restore-chat-history")
        elif should_resume:
            cmd.append("--restore-chat-history")

        # Add files to context
        if files:
            cmd.extend(files)

        return cmd

    def parse_output(self, stdout: str, stderr: str) -> tuple[bool, str]:
        """Parse Aider output."""
        # Aider outputs progress to stderr and results to stdout
        output = stdout.strip()
        if not output and stderr:
            # Some aider output goes to stderr
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
        Run Aider targeting specific files.

        Args:
            prompt: The instruction
            files: Files to include in context
            model: Model to use
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
