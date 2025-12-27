"""
Superagent functionality for spawning and managing subagents.

A superagent can spawn up to 5 subagents to handle subtasks. The superagent
is responsible for:
- Breaking down complex tasks into subtasks
- Spawning subagents with specific instructions
- Verifying and integrating subagent work
- Handling subagent failures gracefully

Subagents cannot spawn their own subagents (no recursive spawning).
"""

import json
import logging
import subprocess
import shutil
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional, Any

from robot.config import settings

logger = logging.getLogger(__name__)

# Default timeout for subagents (5 minutes)
DEFAULT_SUBAGENT_TIMEOUT = 300

# Maximum number of subagents a superagent can spawn
MAX_SUBAGENTS = 5


@dataclass
class SubagentResult:
    """Result from a subagent execution."""

    task_id: int
    success: bool
    content: str
    error: Optional[str] = None
    agent: str = "claude"
    model: Optional[str] = None
    duration: float = 0.0


@dataclass
class SuperagentState:
    """Tracks superagent state during execution."""

    subagents_spawned: int = 0
    subagent_results: list[SubagentResult] = field(default_factory=list)
    max_subagents: int = MAX_SUBAGENTS
    subagent_timeout: int = DEFAULT_SUBAGENT_TIMEOUT


def get_superagent_prefix(
    max_subagents: int = MAX_SUBAGENTS,
    subagent_timeout: int = DEFAULT_SUBAGENT_TIMEOUT,
    working_dir: Optional[Path] = None,
    allowed_agents: Optional[list[str]] = None,
) -> str:
    """
    Generate the prompt prefix that enables superagent capabilities.

    This prefix instructs the agent on how to spawn subagents using the
    robot CLI. The subagents run with --no-superagent to prevent recursion.

    Args:
        max_subagents: Maximum number of subagents allowed (default 5)
        subagent_timeout: Timeout in seconds for each subagent (default 300)
        working_dir: Working directory for subagents
        allowed_agents: List of allowed agent names (default: all)

    Returns:
        Prompt prefix string with subagent instructions
    """
    work_dir_str = str(working_dir) if working_dir else "."
    agents_str = ", ".join(allowed_agents) if allowed_agents else "claude, codex, gemini, vibe, aider, openrouter"

    return f"""# SUPERAGENT CAPABILITIES

You have the ability to spawn up to {max_subagents} subagents to help complete complex tasks.
Use subagents for parallelizable work, specialized tasks, or when you need fresh context.

## Spawning Subagents

To spawn a subagent, run this command:

```bash
robot run "<task_description>" --agent <agent_name> --timeout {subagent_timeout} --dir "{work_dir_str}" --no-superagent
```

Available agents: {agents_str}

### Example Usage

```bash
# Spawn a subagent to review code
robot run "Review the authentication module for security issues" --agent claude --timeout {subagent_timeout} --dir "{work_dir_str}" --no-superagent

# Spawn a subagent to write tests
robot run "Write unit tests for the User model" --agent claude --timeout {subagent_timeout} --dir "{work_dir_str}" --no-superagent

# Use a different agent for variety
robot run "Optimize the database queries in models.py" --agent codex --timeout {subagent_timeout} --dir "{work_dir_str}" --no-superagent
```

## Rules for Subagent Usage

1. **Maximum {max_subagents} subagents**: You can spawn at most {max_subagents} subagents total
2. **No nested superagents**: Subagents cannot spawn their own subagents (--no-superagent flag)
3. **Timeout**: Each subagent has a {subagent_timeout}s ({subagent_timeout // 60}min) timeout
4. **Verify work**: Always review subagent output before accepting it
5. **Handle failures**: If a subagent fails, decide whether to retry or handle differently
6. **Clear instructions**: Give each subagent specific, self-contained instructions

## When to Use Subagents

Good use cases:
- Parallel independent tasks (e.g., reviewing multiple files)
- Specialized work requiring fresh context
- Tasks that benefit from a second opinion
- Long-running analyses that can be delegated

Bad use cases:
- Simple tasks you can do directly
- Tasks requiring your accumulated context
- Sequential tasks where each depends on the previous

## Verification Protocol

After each subagent completes:
1. Read and understand the subagent's output
2. Verify the work is correct and complete
3. Check for errors or issues that need addressing
4. Integrate the results into your overall response
5. If the subagent failed or produced incorrect results, either:
   - Fix the issues yourself
   - Spawn another subagent with clearer instructions
   - Report the failure to the user

Remember: You are responsible for the quality of all subagent work.
"""


def run_subagent(
    prompt: str,
    agent: str = "claude",
    model: Optional[str] = None,
    timeout: int = DEFAULT_SUBAGENT_TIMEOUT,
    working_dir: Optional[Path] = None,
) -> SubagentResult:
    """
    Run a subagent with the given prompt.

    This function is used programmatically to spawn subagents.
    It ensures the subagent cannot spawn its own subagents.

    Args:
        prompt: The task description for the subagent
        agent: Agent to use (default: claude)
        model: Model to use (optional)
        timeout: Timeout in seconds (default: 300)
        working_dir: Working directory

    Returns:
        SubagentResult with the outcome
    """
    import time

    # Find robot CLI
    robot_path = shutil.which("robot")
    if not robot_path:
        return SubagentResult(
            task_id=0,
            success=False,
            content="",
            error="robot CLI not found in PATH",
            agent=agent,
        )

    cmd = [robot_path, "run", prompt, "--agent", agent, "--no-superagent"]

    if model:
        cmd.extend(["--model", model])

    if working_dir:
        cmd.extend(["--dir", str(working_dir)])

    logger.info(f"Spawning subagent: agent={agent}, timeout={timeout}s")

    start_time = time.time()
    try:
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=timeout,
            cwd=working_dir,
        )

        duration = time.time() - start_time

        if result.returncode == 0:
            return SubagentResult(
                task_id=0,
                success=True,
                content=result.stdout.strip(),
                agent=agent,
                model=model,
                duration=duration,
            )
        else:
            return SubagentResult(
                task_id=0,
                success=False,
                content=result.stdout.strip(),
                error=result.stderr.strip() or f"Exit code: {result.returncode}",
                agent=agent,
                model=model,
                duration=duration,
            )

    except subprocess.TimeoutExpired:
        duration = time.time() - start_time
        return SubagentResult(
            task_id=0,
            success=False,
            content="",
            error=f"Subagent timed out after {timeout}s",
            agent=agent,
            model=model,
            duration=duration,
        )
    except Exception as e:
        duration = time.time() - start_time
        return SubagentResult(
            task_id=0,
            success=False,
            content="",
            error=str(e),
            agent=agent,
            model=model,
            duration=duration,
        )


class SuperAgent:
    """
    Wrapper that adds superagent capabilities to any agent.

    Usage:
        from robot import Robot
        from robot.superagent import SuperAgent

        # Wrap any agent with superagent capabilities
        agent = Robot.get("claude")
        super_agent = SuperAgent(agent)
        response = super_agent.run("Complex task requiring multiple subagents")
    """

    def __init__(
        self,
        agent,
        max_subagents: int = MAX_SUBAGENTS,
        subagent_timeout: int = DEFAULT_SUBAGENT_TIMEOUT,
        allowed_agents: Optional[list[str]] = None,
    ):
        """
        Initialize superagent wrapper.

        Args:
            agent: Base agent to wrap
            max_subagents: Maximum subagents allowed (default 5)
            subagent_timeout: Timeout per subagent in seconds (default 300)
            allowed_agents: List of agents subagents can use
        """
        self.agent = agent
        self.max_subagents = max_subagents
        self.subagent_timeout = subagent_timeout
        self.allowed_agents = allowed_agents
        self.state = SuperagentState(
            max_subagents=max_subagents,
            subagent_timeout=subagent_timeout,
        )

    def get_prompt_prefix(self, working_dir: Optional[Path] = None) -> str:
        """Get the superagent prompt prefix."""
        return get_superagent_prefix(
            max_subagents=self.max_subagents,
            subagent_timeout=self.subagent_timeout,
            working_dir=working_dir or self.agent.config.working_dir,
            allowed_agents=self.allowed_agents,
        )

    def run(
        self,
        prompt: str,
        model: Optional[str] = None,
        system_prompt: Optional[str] = None,
        working_dir: Optional[Path] = None,
        **kwargs,
    ):
        """
        Run the agent with superagent capabilities.

        Adds the superagent prompt prefix to enable subagent spawning.
        """
        # Get the superagent prefix
        prefix = self.get_prompt_prefix(working_dir)

        # Combine with any existing prompt_prefix
        existing_prefix = kwargs.get("prompt_prefix", "") or self.agent.config.prompt_prefix or ""
        if existing_prefix:
            combined_prefix = f"{prefix}\n\n{existing_prefix}"
        else:
            combined_prefix = prefix

        return self.agent.run(
            prompt=prompt,
            model=model,
            system_prompt=system_prompt,
            working_dir=working_dir,
            prompt_prefix=combined_prefix,
            **kwargs,
        )
