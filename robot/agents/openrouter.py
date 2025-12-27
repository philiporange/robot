"""
OpenRouter agent implementation.

Uses the aider CLI to access any model via OpenRouter's API.
OpenRouter provides access to many models including Claude, GPT-4,
Llama, Mistral, and others through a unified OpenAI-compatible API.
"""

import logging
from pathlib import Path
from typing import Optional

from robot.base import BaseAgent
from robot.config import settings
from robot.registry import register_agent

logger = logging.getLogger(__name__)


@register_agent("openrouter")
class OpenRouterAgent(BaseAgent):
    """OpenRouter agent using aider CLI."""

    name = "openrouter"
    cli_command = "aider"
    supports_tools = False
    supports_streaming = True
    supports_system_prompt = False
    supports_resume = True
    default_model = "minimax/minimax-m2.1"

    # Model aliases for common OpenRouter models
    MODEL_ALIASES = {
        # MiniMax (cost-effective coding)
        "minimax": "minimax/minimax-m2.1",
        "m2.1": "minimax/minimax-m2.1",
        # Anthropic Claude
        "claude": "anthropic/claude-sonnet-4",
        "sonnet": "anthropic/claude-sonnet-4",
        "opus": "anthropic/claude-opus-4",
        "haiku": "anthropic/claude-haiku-4",
        # OpenAI
        "gpt5": "openai/gpt-5.2",
        "gpt4": "openai/gpt-4o",
        "gpt4o": "openai/gpt-4o",
        # Google Gemini
        "gemini": "google/gemini-3-pro-preview",
        "gemini-pro": "google/gemini-3-pro-preview",
        "gemini-flash": "google/gemini-3-flash-preview",
        # Meta Llama
        "llama": "meta-llama/llama-3.3-70b-instruct",
        # DeepSeek
        "deepseek": "deepseek/deepseek-chat",
        # Qwen
        "qwen": "qwen/qwen-2.5-72b-instruct",
    }

    def get_cli_path(self) -> str:
        return settings.aider_path

    def get_env_vars(self) -> dict[str, str]:
        """
        Get environment variables for OpenRouter via aider.

        Sets OPENROUTER_API_KEY for aider to use OpenRouter.
        """
        env = {}

        api_key = self.config.api_key or settings.openrouter_api_key
        base_url = self.config.base_url or settings.openrouter_base_url

        if api_key:
            env["OPENROUTER_API_KEY"] = api_key

        if base_url:
            env["OPENAI_API_BASE"] = base_url

        return env

    def _resolve_model(self, model: str) -> str:
        """Resolve model alias to full OpenRouter model name."""
        resolved = self.MODEL_ALIASES.get(model, model)
        # Ensure model has openrouter/ prefix for aider
        if not resolved.startswith("openrouter/"):
            return f"openrouter/{resolved}"
        return resolved

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
        Build the aider CLI command for OpenRouter.

        Args:
            prompt: The message/instruction
            model: Model name (will be prefixed with openrouter/)
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

        model = model or self.default_model
        resolved = self._resolve_model(model)

        cmd = [self.get_cli_path(), "--message", prompt, "--yes", "--model", resolved, "--no-git"]

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
        Run OpenRouter agent targeting specific files.

        Args:
            prompt: The instruction
            files: Files to include in context
            model: Model to use (any OpenRouter model)
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
