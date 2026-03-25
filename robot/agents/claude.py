"""
Claude Code CLI agent implementation.

Wraps the `claude` CLI for headless execution with full tool support,
JSON output parsing, and system prompt configuration. Strips inherited
ANTHROPIC env vars from the subprocess environment so the CLI defaults
to OAuth subscription auth unless an API key is explicitly configured.
"""

import json
import logging
import time
from pathlib import Path
from typing import Callable, Optional, Any

from robot.base import BaseAgent, AgentConfig
from robot.config import settings
from robot.registry import register_agent
from robot.response import AgentResponse
from robot.status import StatusCallback, StatusEvent, StatusType

logger = logging.getLogger(__name__)


@register_agent("claude")
class ClaudeAgent(BaseAgent):
    """Claude Code CLI wrapper."""

    name = "claude"
    cli_command = "claude"
    supports_tools = True
    supports_streaming = True
    supports_system_prompt = True
    supports_resume = True
    default_model = "sonnet"

    # Model aliases - use short names, CLI will resolve to latest versions
    MODEL_ALIASES = {
        "haiku": "haiku",
        "sonnet": "sonnet",
        "opus": "opus",
    }

    # Default tools for file operations
    DEFAULT_TOOLS = ["Read", "Glob", "Grep", "Write"]

    def get_cli_path(self) -> str:
        """Get the path to the Claude CLI."""
        return settings.claude_path

    def _get_base_env(self) -> dict[str, str]:
        """
        Get base environment with ANTHROPIC vars stripped.

        Prevents leaked ANTHROPIC_API_KEY (e.g. from dotenv loading ~/.env)
        from overriding OAuth subscription auth in the Claude CLI.
        Explicitly configured keys are re-added via get_env_vars().
        """
        import os
        env = os.environ.copy()
        env.pop("ANTHROPIC_API_KEY", None)
        # ANTHROPIC_AUTH_TOKEN is the Claude CLI's proxy/gateway auth var
        # (used by Z.ai etc). Different from ANTHROPIC_API_KEY but also
        # causes the CLI to skip OAuth if present.
        env.pop("ANTHROPIC_AUTH_TOKEN", None)
        return env

    def get_env_vars(self) -> dict[str, str]:
        """
        Get environment variables for Claude CLI.

        Sets ANTHROPIC_API_KEY and ANTHROPIC_BASE_URL if explicitly configured.
        When no key is configured, vars are left unset so the CLI uses OAuth.
        """
        env = {}

        # Check config first, then settings
        api_key = self.config.api_key or settings.claude_api_key
        base_url = self.config.base_url or settings.claude_base_url

        if api_key:
            env["ANTHROPIC_API_KEY"] = api_key
        if base_url:
            env["ANTHROPIC_BASE_URL"] = base_url

        return env

    def _resolve_model(self, model: str) -> str:
        """Resolve model alias to full name."""
        return self.MODEL_ALIASES.get(model, model)

    def build_command(
        self,
        prompt: str,
        model: Optional[str] = None,
        system_prompt: Optional[str] = None,
        prompt_prefix: Optional[str] = None,
        tools: Optional[list[str]] = None,
        add_dirs: Optional[list[str]] = None,
        output_format: str = "json",
        resume: Optional[bool] = None,
        session_id: Optional[str] = None,
        history_file: Optional[str] = None,
        **kwargs,
    ) -> list[str]:
        """
        Build the Claude CLI command.

        Args:
            prompt: The prompt to send
            model: Model alias or full name
            system_prompt: System prompt (replaces default)
            prompt_prefix: Appended after system prompt (like AGENTS.md)
            tools: Allowed tools (defaults to Read, Glob, Grep, Write)
            add_dirs: Additional directories to allow access
            output_format: Output format (json or text)
            resume: Whether to resume/continue most recent session
            session_id: Specific session ID to resume
            history_file: Session ID to use (treated as session_id for Claude)

        Returns:
            Command list for subprocess
        """
        cmd = [self.get_cli_path()]

        # Handle resume/continue functionality
        # history_file is treated as session_id for Claude
        should_resume = resume if resume is not None else self.config.resume
        sess_id = session_id or history_file
        if sess_id is None and self.config.history_file:
            sess_id = str(self.config.history_file)
        if sess_id is None:
            sess_id = self.config.session_id

        if sess_id:
            # Resume specific session by ID
            cmd.extend(["--resume", sess_id])
        elif should_resume:
            # Continue most recent session
            cmd.append("--continue")

        cmd.extend(["-p", prompt, "--output-format", output_format])

        if model:
            resolved = self._resolve_model(model)
            cmd.extend(["--model", resolved])

        if system_prompt:
            cmd.extend(["--system-prompt", system_prompt])

        # Handle prompt_prefix via --append-system-prompt
        prefix = prompt_prefix or self.config.prompt_prefix
        if prefix:
            cmd.extend(["--append-system-prompt", prefix])

        # Add tools
        allowed_tools = tools or self.config.tools or self.DEFAULT_TOOLS
        if allowed_tools:
            cmd.extend(["--allowed-tools", ",".join(allowed_tools)])

        # Add directories - include working_dir from config
        dirs_to_add = list(add_dirs) if add_dirs else []
        dirs_to_add.append(str(self.temp_dir))
        if self.config.working_dir:
            dirs_to_add.append(str(self.config.working_dir))
        for d in dirs_to_add:
            cmd.extend(["--add-dir", str(d)])

        # Skip permission prompts for headless operation
        cmd.append("--dangerously-skip-permissions")

        return cmd

    def run(
        self,
        prompt: str,
        model: Optional[str] = None,
        system_prompt: Optional[str] = None,
        working_dir: Optional[Path] = None,
        on_retry: Optional[Callable[[int, str], None]] = None,
        on_status: Optional[StatusCallback] = None,
        **kwargs,
    ) -> AgentResponse:
        """
        Execute Claude with the given prompt.

        When on_status is provided, uses streaming mode for real-time updates.

        Args:
            prompt: The prompt to send
            model: Model to use
            system_prompt: System prompt
            working_dir: Working directory
            on_retry: Callback for retry attempts
            on_status: Callback for streaming status events
            **kwargs: Additional arguments

        Returns:
            AgentResponse with results
        """
        model = model or self.config.model or self.default_model
        system_prompt = system_prompt or self.config.system_prompt
        working_dir = working_dir or self.config.working_dir

        # Use streaming mode when on_status is provided
        if on_status:
            return self._run_streaming(
                prompt=prompt,
                model=model,
                system_prompt=system_prompt,
                working_dir=working_dir,
                on_status=on_status,
                **kwargs,
            )

        # Otherwise use standard non-streaming mode
        return super().run(
            prompt=prompt,
            model=model,
            system_prompt=system_prompt,
            working_dir=working_dir,
            on_retry=on_retry,
            **kwargs,
        )

    def _run_streaming(
        self,
        prompt: str,
        model: str,
        system_prompt: Optional[str],
        working_dir: Optional[Path],
        on_status: StatusCallback,
        **kwargs,
    ) -> AgentResponse:
        """
        Run Claude with streaming output for real-time status updates.

        Uses stream-json output format and parses events as they arrive.
        """
        # Build command with streaming output format
        cmd = self.build_command(
            prompt=prompt,
            model=model,
            system_prompt=system_prompt,
            output_format="stream-json",
            **kwargs,
        )

        # Add --verbose required for stream-json
        cmd.append("--verbose")

        env_vars = self.get_env_vars()
        start_time = time.time()

        logger.info(f"Running {self.name} (streaming): model={model}")

        self._rate_limit()

        return_code, stdout, stderr = self._run_streaming_subprocess(
            cmd,
            working_dir=working_dir,
            timeout=self.timeout,
            env=env_vars,
            on_status=on_status,
        )

        duration = time.time() - start_time

        # Parse final result from stream output
        success, content = self._parse_streaming_output(stdout)

        if success:
            logger.info(f"Success: {len(content)} chars in {duration:.1f}s")
            return AgentResponse(
                success=True,
                content=content,
                raw_output=stdout,
                agent=self.name,
                model=model,
                duration=duration,
            )
        else:
            error = content or stderr or f"Exit code: {return_code}"
            logger.error(f"Failed: {error}")
            return AgentResponse(
                success=False,
                content="",
                raw_output=stdout,
                agent=self.name,
                model=model,
                duration=duration,
                error=error,
            )

    def _parse_streaming_output(self, stdout: str) -> tuple[bool, str]:
        """
        Parse streaming JSON output to extract final result.

        Returns:
            Tuple of (success, content)
        """
        # Look for the result event in the stream
        for line in stdout.strip().split("\n"):
            if not line.strip():
                continue
            try:
                event = json.loads(line)
                if event.get("type") == "result":
                    success = event.get("subtype") == "success"
                    content = event.get("result", "")
                    if not success:
                        content = event.get("error", content)
                    return success, content
            except json.JSONDecodeError:
                continue

        # No result event found, try to extract any content
        return False, "No result in stream output"

    def parse_output(self, stdout: str, stderr: str) -> tuple[bool, str]:
        """
        Parse Claude CLI JSON output.

        Returns:
            Tuple of (success, content)
        """
        if not stdout.strip():
            return False, stderr or "Empty response"

        try:
            output = json.loads(stdout)
            content = self._extract_content(output)

            # Check for API errors
            if output.get("is_error"):
                return False, content

            return True, content

        except json.JSONDecodeError:
            # Non-JSON output, return as-is
            return True, stdout

    def _extract_content(self, output: Any) -> str:
        """Extract text content from Claude JSON output."""
        if isinstance(output, dict):
            if "result" in output:
                result = output["result"]
                if isinstance(result, str):
                    return result
                return json.dumps(result, indent=2)
            if "content" in output:
                return output["content"]
            if "response" in output:
                return output["response"]
            return json.dumps(output, indent=2)

        if isinstance(output, str):
            return output

        return str(output)

    def run_with_file_output(
        self,
        prompt: str,
        output_path: Path,
        model: Optional[str] = None,
        system_prompt: Optional[str] = None,
        working_dir: Optional[Path] = None,
        **kwargs,
    ) -> AgentResponse:
        """
        Run Claude and expect output to be written to a file.

        This is useful for generation tasks where Claude writes directly
        to a file rather than returning content via stdout.

        Args:
            prompt: The prompt (should instruct Claude to write to output_path)
            output_path: Path where Claude should write output
            model: Model to use
            system_prompt: System prompt
            working_dir: Working directory

        Returns:
            AgentResponse with file contents
        """
        import time

        model = model or self.config.model or self.default_model
        working_dir = working_dir or self.config.working_dir

        # Ensure output file doesn't exist
        if output_path.exists():
            output_path.unlink()

        # Build command with temp dir access
        cmd = self.build_command(
            prompt=prompt,
            model=model,
            system_prompt=system_prompt,
            add_dirs=[str(output_path.parent)],
            **kwargs,
        )

        start_time = time.time()
        logger.info(f"Running Claude with file output: {output_path}")

        # Get environment variables for API config
        env_vars = self.get_env_vars()

        for attempt in range(self.max_retries):
            try:
                self._rate_limit()

                return_code, stdout, stderr = self._run_subprocess(
                    cmd,
                    working_dir=working_dir,
                    env=env_vars,
                )

                # Check if output file was created
                if output_path.exists():
                    content = output_path.read_text()
                    duration = time.time() - start_time
                    logger.info(f"Success: read {len(content)} chars from {output_path}")

                    return AgentResponse(
                        success=True,
                        content=content,
                        raw_output=stdout,
                        agent=self.name,
                        model=model,
                        duration=duration,
                        files_modified=[str(output_path)],
                    )

                if return_code == 0:
                    # File not created but command succeeded
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

                last_error = stderr or "Output file not created"
                logger.warning(f"Attempt {attempt + 1} failed: {last_error}")

            except Exception as e:
                last_error = str(e)
                logger.error(f"Exception on attempt {attempt + 1}: {e}")

            # Retry with backoff
            if attempt < self.max_retries - 1:
                import time as time_module
                backoff = 2 ** attempt
                time_module.sleep(backoff)

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
