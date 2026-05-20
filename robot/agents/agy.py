"""
Antigravity CLI agent implementation.

Wraps Google's `agy` (Antigravity) CLI for headless execution via its
`-p`/`--print` mode. The CLI itself does not accept a `--model` flag; the
model is selected via the CASCADE_DEFAULT_MODEL_OVERRIDE environment variable
that agy reads at startup. Defaults to gemini-3.5-flash.
"""

import logging
from typing import Optional

from robot.base import BaseAgent
from robot.config import settings
from robot.registry import register_agent

logger = logging.getLogger(__name__)


@register_agent("agy")
class AgyAgent(BaseAgent):
    """Antigravity (`agy`) CLI wrapper."""

    name = "agy"
    cli_command = "agy"
    supports_tools = True
    supports_streaming = False
    supports_system_prompt = False
    supports_resume = True
    default_model = "gemini-3.5-flash"

    MODEL_ALIASES = {
        # Gemini 3.5 flash (latest fast model)
        "flash": "gemini-3.5-flash",
        "gemini-3.5-flash": "gemini-3.5-flash",
        # Gemini 3.1 pro (current pro model)
        "pro": "gemini-3.1-pro",
        "gemini-3.1-pro": "gemini-3.1-pro",
        # Gemini 3.1 lite
        "flash-lite": "gemini-3.1-flash-lite-preview",
        "gemini-3.1-flash-lite": "gemini-3.1-flash-lite-preview",
        # Legacy preview names
        "gemini-3-pro-preview": "gemini-3-pro-preview",
        "gemini-3-flash-preview": "gemini-3-flash-preview",
    }

    def get_cli_path(self) -> str:
        return settings.agy_path

    def _resolve_model(self, model: str) -> str:
        """Resolve model alias to full Antigravity model name."""
        return self.MODEL_ALIASES.get(model, model)

    def get_env_vars(self, model: Optional[str] = None) -> dict[str, str]:
        """
        Get environment variables for Antigravity CLI.

        The agy CLI has no --model flag; instead it reads
        CASCADE_DEFAULT_MODEL_OVERRIDE to select the active model. Auth flows
        through Google credentials configured by `agy install` and stored in
        ~/.antigravity, so an explicit API key is only needed for override.
        """
        env = {}

        api_key = self.config.api_key or settings.agy_api_key
        if api_key:
            env["GOOGLE_API_KEY"] = api_key

        resolved_model = model or self.config.model
        if resolved_model:
            env["CASCADE_DEFAULT_MODEL_OVERRIDE"] = self._resolve_model(resolved_model)

        return env

    def build_command(
        self,
        prompt: str,
        model: Optional[str] = None,  # noqa: ARG002 - applied via env var
        prompt_prefix: Optional[str] = None,
        add_dirs: Optional[list[str]] = None,
        resume: Optional[bool] = None,
        session_id: Optional[str] = None,
        print_timeout: Optional[str] = None,
        **kwargs,
    ) -> list[str]:
        """
        Build the agy CLI command.

        Args:
            prompt: The prompt to send (passed via -p print mode)
            model: Resolved via CASCADE_DEFAULT_MODEL_OVERRIDE env var, not CLI
            prompt_prefix: Prefix to prepend to prompt (like AGENTS.md)
            add_dirs: Additional workspace directories (--add-dir, repeatable)
            resume: Whether to continue the most recent conversation
            session_id: Conversation id to resume (--conversation <id>)
            print_timeout: Override the default 5m print-mode timeout
        """
        prefix = prompt_prefix or self.config.prompt_prefix
        if prefix:
            prompt = f"{prefix}\n\n{prompt}"

        cmd = [self.get_cli_path()]

        # Resume handling: prefer explicit conversation id, otherwise --continue
        should_resume = resume if resume is not None else self.config.resume
        sess_id = session_id or self.config.session_id
        if sess_id is None and self.config.history_file:
            sess_id = str(self.config.history_file)

        if sess_id:
            cmd.extend(["--conversation", sess_id])
        elif should_resume:
            cmd.append("--continue")

        # Additional workspace directories
        dirs_to_add = list(add_dirs) if add_dirs else []
        if self.config.working_dir:
            dirs_to_add.append(str(self.config.working_dir))
        for d in dirs_to_add:
            cmd.extend(["--add-dir", str(d)])

        if print_timeout:
            cmd.extend(["--print-timeout", print_timeout])

        # Headless-friendly: auto-approve tool permission prompts
        cmd.append("--dangerously-skip-permissions")

        # Non-interactive print mode with the prompt
        cmd.extend(["-p", prompt])

        return cmd

    def parse_output(self, stdout: str, stderr: str) -> tuple[bool, str]:
        """Parse agy output (text-based)."""
        if stderr and not stdout:
            return False, stderr
        return True, stdout.strip()

    def run(self, prompt, model=None, **kwargs):
        """
        Override run() to surface model selection to get_env_vars().

        Antigravity selects the model via CASCADE_DEFAULT_MODEL_OVERRIDE, which
        is built in get_env_vars() — base run() does not pass `model` there.
        """
        import time
        from robot.response import AgentResponse

        resolved_model = model or self.config.model or self.default_model
        working_dir = kwargs.pop("working_dir", None) or self.config.working_dir
        on_retry = kwargs.pop("on_retry", None)

        cmd = self.build_command(prompt=prompt, model=resolved_model, **kwargs)
        env_vars = self.get_env_vars(model=resolved_model)

        last_error = None
        start_time = time.time()

        logger.info(f"Running {self.name}: model={resolved_model}, timeout={self.timeout}s")

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
                            model=resolved_model,
                            duration=duration,
                        )
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
            model=resolved_model,
            duration=duration,
            error=last_error,
        )
