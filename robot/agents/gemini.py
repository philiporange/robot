"""
Gemini CLI agent implementation.

Wraps the `gemini` CLI for headless execution.
"""

import json
import logging
from pathlib import Path
from typing import Optional, Any, Callable

from robot.base import BaseAgent
from robot.config import settings
from robot.registry import register_agent

logger = logging.getLogger(__name__)


@register_agent("gemini")
class GeminiAgent(BaseAgent):
    """
    Gemini CLI wrapper.

    System prompts are supported via the GEMINI_SYSTEM_MD environment variable,
    which points to a markdown file containing the system prompt.
    """

    name = "gemini"
    cli_command = "gemini"
    supports_tools = True
    supports_streaming = True
    supports_system_prompt = True  # Via GEMINI_SYSTEM_MD env var
    supports_resume = True
    default_model = "gemini-3-pro-preview"

    # Model aliases for Gemini
    MODEL_ALIASES = {
        "pro": "gemini-3-pro-preview",
        "flash": "gemini-3-flash-preview",
        "thinking": "gemini-3-flash-thinking",
        # Legacy aliases
        "2.5-pro": "gemini-2.5-pro",
        "2.5-flash": "gemini-2.5-flash",
    }

    def get_cli_path(self) -> str:
        return settings.gemini_path

    def _resolve_model(self, model: str) -> str:
        """Resolve model alias to full Gemini model name."""
        return self.MODEL_ALIASES.get(model, model)

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._system_prompt_file: Optional[Path] = None

    def get_env_vars(
        self,
        system_prompt: Optional[str] = None,
        prompt_prefix: Optional[str] = None,
    ) -> dict[str, str]:
        """
        Get environment variables for Gemini CLI.

        Sets GOOGLE_API_KEY, GOOGLE_BASE_URL, and GEMINI_SYSTEM_MD if configured.
        System prompts are written to a temp file and GEMINI_SYSTEM_MD points to it.
        Prompt prefix is appended to the system prompt content.
        """
        from pathlib import Path

        env = {}

        api_key = self.config.api_key or settings.gemini_api_key
        base_url = self.config.base_url or settings.gemini_base_url

        if api_key:
            env["GOOGLE_API_KEY"] = api_key
        if base_url:
            env["GOOGLE_BASE_URL"] = base_url

        # Handle system prompt via GEMINI_SYSTEM_MD
        sys_prompt = system_prompt or self.config.system_prompt
        prefix = prompt_prefix or self.config.prompt_prefix

        # Combine system prompt and prefix
        content_parts = []
        if sys_prompt:
            content_parts.append(sys_prompt)
        if prefix:
            content_parts.append(prefix)

        if content_parts:
            # Write combined content to temp file
            self._system_prompt_file = self._generate_temp_path(".md")
            self._system_prompt_file.write_text("\n\n".join(content_parts))
            env["GEMINI_SYSTEM_MD"] = str(self._system_prompt_file)

        return env

    def build_command(
        self,
        prompt: str,
        model: Optional[str] = None,
        system_prompt: Optional[str] = None,
        prompt_prefix: Optional[str] = None,
        output_format: str = "json",
        resume: Optional[bool] = None,
        session_id: Optional[str] = None,
        **kwargs,
    ) -> list[str]:
        """
        Build the Gemini CLI command.

        Args:
            prompt: The prompt to send
            model: Model to use
            system_prompt: Set via GEMINI_SYSTEM_MD env var
            prompt_prefix: Appended after system prompt (via GEMINI_SYSTEM_MD)
            output_format: Output format (json or text)
            resume: Whether to resume most recent session
            session_id: Specific session index or "latest" to resume
        """
        cmd = [self.get_cli_path(), "--yolo"]

        # Handle resume functionality
        # Gemini uses --resume with "latest" or session index
        should_resume = resume if resume is not None else self.config.resume
        sess_id = session_id or self.config.session_id
        if sess_id is None and self.config.history_file:
            sess_id = str(self.config.history_file)

        if sess_id:
            cmd.extend(["--resume", sess_id])
        elif should_resume:
            cmd.extend(["--resume", "latest"])

        # Add prompt (positional argument for gemini)
        cmd.append(prompt)

        if model:
            resolved = self._resolve_model(model)
            cmd.extend(["--model", resolved])

        if output_format:
            cmd.extend(["--output-format", output_format])

        return cmd

    def parse_output(self, stdout: str, stderr: str) -> tuple[bool, str]:
        """Parse Gemini output."""
        if not stdout.strip():
            return False, stderr or "Empty response"

        try:
            output = json.loads(stdout)
            if isinstance(output, dict):
                content = output.get("result") or output.get("content") or output.get("response")
                if content:
                    return True, content
                return True, json.dumps(output, indent=2)
            return True, str(output)
        except json.JSONDecodeError:
            return True, stdout.strip()

    def run(
        self,
        prompt: str,
        model: Optional[str] = None,
        system_prompt: Optional[str] = None,
        prompt_prefix: Optional[str] = None,
        working_dir: Optional[Path] = None,
        on_retry: Optional[Callable[[int, str], None]] = None,
        **kwargs,
    ) -> "AgentResponse":
        """
        Run Gemini with the given prompt.

        Overrides base run to pass system_prompt and prompt_prefix to get_env_vars(),
        which writes them to a temp file and sets GEMINI_SYSTEM_MD.
        """
        import time
        from robot.response import AgentResponse

        model = model or self.config.model or self.default_model
        system_prompt = system_prompt or self.config.system_prompt
        prompt_prefix = prompt_prefix or self.config.prompt_prefix
        working_dir = working_dir or self.config.working_dir

        cmd = self.build_command(
            prompt=prompt,
            model=model,
            system_prompt=system_prompt,
            prompt_prefix=prompt_prefix,
            **kwargs,
        )

        # Get env vars with system_prompt and prompt_prefix for GEMINI_SYSTEM_MD
        env_vars = self.get_env_vars(system_prompt=system_prompt, prompt_prefix=prompt_prefix)

        last_error = None
        start_time = time.time()

        logger.info(f"Running {self.name}: model={model}, timeout={self.timeout}s")

        for attempt in range(self.max_retries):
            try:
                self._rate_limit()

                return_code, stdout, stderr = self._run_subprocess(
                    cmd,
                    working_dir=working_dir,
                    timeout=self.timeout,
                    env=env_vars,
                )

                if return_code == 0:
                    success, content = self.parse_output(stdout, stderr)
                    if success:
                        duration = time.time() - start_time
                        return AgentResponse(
                            success=True,
                            content=content,
                            raw_output=stdout,
                            agent=self.name,
                            model=model,
                            duration=duration,
                        )
                    else:
                        last_error = content
                else:
                    last_error = stderr or f"Exit code: {return_code}"

            except Exception as e:
                last_error = str(e)

            if attempt < self.max_retries - 1:
                backoff = 2 ** attempt
                if on_retry:
                    on_retry(attempt + 1, last_error)
                time.sleep(backoff)

        duration = time.time() - start_time
        return AgentResponse(
            success=False,
            content="",
            raw_output="",
            agent=self.name,
            model=model,
            duration=duration,
            error=last_error,
        )
