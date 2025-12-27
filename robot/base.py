"""
Abstract base class for coding agents.

Defines the interface that all agent implementations must follow.
Includes common functionality like rate limiting, retries, and
subprocess execution.
"""

import logging
import subprocess
import time
import uuid
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional, Callable, Any

from robot.config import settings
from robot.response import AgentResponse

logger = logging.getLogger(__name__)


@dataclass
class AgentConfig:
    """Configuration for an agent execution."""

    model: Optional[str] = None
    timeout: Optional[int] = None
    max_retries: Optional[int] = None
    system_prompt: Optional[str] = None
    prompt_prefix: Optional[str] = None  # Appended after system prompt (like AGENTS.md)
    tools: Optional[list[str]] = None
    working_dir: Optional[Path] = None
    api_key: Optional[str] = None
    base_url: Optional[str] = None
    resume: bool = False  # Resume/continue most recent session
    session_id: Optional[str] = None  # Resume specific session by ID
    history_file: Optional[Path] = None  # Chat history file (auto-resumes if exists)
    extra_args: dict[str, Any] = field(default_factory=dict)


class BaseAgent(ABC):
    """Abstract base class for all coding agents."""

    name: str = "base"
    cli_command: str = ""
    supports_tools: bool = False
    supports_streaming: bool = False
    supports_system_prompt: bool = False
    supports_resume: bool = False  # Whether agent supports session resume
    default_model: str = ""

    def __init__(self, config: Optional[AgentConfig] = None):
        self.config = config or AgentConfig()
        self.timeout = self.config.timeout or settings.default_timeout
        self.max_retries = self.config.max_retries or settings.max_retries
        self._last_call_time = 0.0
        self._min_interval = 60.0 / settings.rate_limit

        # Ensure temp directory exists
        self.temp_dir = settings.temp_dir / self.name
        self.temp_dir.mkdir(parents=True, exist_ok=True)

    def _rate_limit(self) -> None:
        """Enforce rate limiting between calls."""
        elapsed = time.time() - self._last_call_time
        if elapsed < self._min_interval:
            wait_time = self._min_interval - elapsed
            logger.debug(f"Rate limiting: waiting {wait_time:.1f}s")
            time.sleep(wait_time)
        self._last_call_time = time.time()

    def _generate_temp_path(self, suffix: str = ".txt") -> Path:
        """Generate a unique temp file path."""
        unique_id = uuid.uuid4().hex[:12]
        return self.temp_dir / f"{unique_id}{suffix}"

    def _run_subprocess(
        self,
        cmd: list[str],
        working_dir: Optional[Path] = None,
        timeout: Optional[int] = None,
        input_text: Optional[str] = None,
        env: Optional[dict[str, str]] = None,
    ) -> tuple[int, str, str]:
        """
        Run a subprocess with the given command.

        Args:
            cmd: Command to run
            working_dir: Working directory
            timeout: Timeout in seconds
            input_text: Text to pass to stdin
            env: Additional environment variables to set

        Returns:
            Tuple of (return_code, stdout, stderr)
        """
        import os

        timeout = timeout or self.timeout
        cwd = working_dir or self.config.working_dir

        # Merge additional env vars with current environment
        proc_env = os.environ.copy()
        if env:
            proc_env.update(env)

        logger.debug(f"Running: {' '.join(cmd[:4])}...")

        try:
            result = subprocess.run(
                cmd,
                cwd=cwd,
                capture_output=True,
                text=True,
                timeout=timeout,
                input=input_text,
                env=proc_env,
            )
            return result.returncode, result.stdout, result.stderr
        except subprocess.TimeoutExpired:
            return -1, "", f"Timeout after {timeout}s"
        except Exception as e:
            return -1, "", str(e)

    @abstractmethod
    def get_cli_path(self) -> str:
        """Get the path to the CLI binary."""
        pass

    def get_env_vars(self) -> dict[str, str]:
        """
        Get environment variables for this agent.

        Override in subclasses to set agent-specific env vars
        like API keys and base URLs.

        Returns:
            Dictionary of environment variables to set
        """
        return {}

    @abstractmethod
    def build_command(
        self,
        prompt: str,
        model: Optional[str] = None,
        system_prompt: Optional[str] = None,
        **kwargs,
    ) -> list[str]:
        """Build the CLI command for this agent."""
        pass

    @abstractmethod
    def parse_output(self, stdout: str, stderr: str) -> tuple[bool, str]:
        """
        Parse the CLI output.

        Returns:
            Tuple of (success, content)
        """
        pass

    def is_available(self) -> bool:
        """Check if the CLI is installed and accessible."""
        import shutil
        path = self.get_cli_path()
        return shutil.which(path) is not None

    def run(
        self,
        prompt: str,
        model: Optional[str] = None,
        system_prompt: Optional[str] = None,
        working_dir: Optional[Path] = None,
        on_retry: Optional[Callable[[int, str], None]] = None,
        **kwargs,
    ) -> AgentResponse:
        """
        Execute the agent with the given prompt.

        Args:
            prompt: The prompt to send to the agent
            model: Model to use (agent-specific)
            system_prompt: System prompt (if supported)
            working_dir: Working directory for execution
            on_retry: Callback for retry attempts
            **kwargs: Additional agent-specific arguments

        Returns:
            AgentResponse with results
        """
        model = model or self.config.model or self.default_model
        system_prompt = system_prompt or self.config.system_prompt
        working_dir = working_dir or self.config.working_dir

        cmd = self.build_command(
            prompt=prompt,
            model=model,
            system_prompt=system_prompt,
            **kwargs,
        )

        # Get agent-specific environment variables
        env_vars = self.get_env_vars()

        last_error = None
        start_time = time.time()

        logger.info(f"Running {self.name}: model={model}, timeout={self.timeout}s")

        for attempt in range(self.max_retries):
            try:
                self._rate_limit()
                attempt_start = time.time()

                return_code, stdout, stderr = self._run_subprocess(
                    cmd,
                    working_dir=working_dir,
                    timeout=self.timeout,
                    env=env_vars,
                )

                attempt_duration = time.time() - attempt_start
                logger.debug(f"Completed in {attempt_duration:.1f}s, code: {return_code}")

                if return_code == 0:
                    success, content = self.parse_output(stdout, stderr)
                    if success:
                        duration = time.time() - start_time
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
                        last_error = content
                else:
                    last_error = stderr or f"Exit code: {return_code}"
                    logger.warning(f"Non-zero exit code: {last_error[:200]}")

            except Exception as e:
                last_error = str(e)
                logger.error(f"Exception on attempt {attempt + 1}: {e}")

            # Retry with exponential backoff
            if attempt < self.max_retries - 1:
                backoff = 2 ** attempt
                logger.info(f"Retrying in {backoff}s...")
                if on_retry:
                    on_retry(attempt + 1, last_error)
                time.sleep(backoff)

        total_duration = time.time() - start_time
        logger.error(f"All {self.max_retries} attempts failed: {last_error}")

        return AgentResponse(
            success=False,
            content="",
            raw_output="",
            agent=self.name,
            model=model,
            duration=total_duration,
            error=last_error,
        )
