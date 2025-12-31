"""
Interactive TUI mode for Robot.

Provides a terminal-based interactive interface that mimics the interactive
modes of underlying CLI tools. Supports multi-line input, command history,
streaming output, and persistent action summaries showing commands and file
operations performed during each response.
"""

import os
import sys
import subprocess
import shutil
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

from robot.config import settings


# Model to agent mapping for automatic agent selection
MODEL_AGENT_MAP = {
    # Claude models -> claude agent
    "opus": "claude",
    "sonnet": "claude",
    "haiku": "claude",
    "claude-opus-4": "claude",
    "claude-sonnet-4": "claude",
    "claude-haiku-4": "claude",
    # OpenAI/Codex models -> codex agent
    "codex": "codex",
    "gpt-5.2-codex": "codex",
    "gpt-5.1-codex-max": "codex",
    "gpt-5.2": "codex",
    "gpt-5": "codex",
    "o4-mini": "codex",
    "o4": "codex",
    "gpt-4": "codex",
    "gpt-4o": "codex",
    # Gemini models -> gemini agent
    "gemini-3-pro-preview": "gemini",
    "gemini-3-flash-preview": "gemini",
    "gemini-3-pro": "gemini",
    "gemini-3-flash": "gemini",
    "pro": "gemini",
    "flash": "gemini",
    # Legacy Gemini
    "gemini-2.5-pro": "gemini",
    "gemini-2.5-flash": "gemini",
    # Mistral models -> vibe agent
    "mistral-large": "vibe",
    "mistral-medium": "vibe",
    "codestral": "vibe",
    # Z.ai models -> zai agent
    "glm": "zai",
    "glm-4": "zai",
    "glm-4.7": "zai",
    # OpenRouter prefixed models
    "openrouter/": "openrouter",
    "minimax": "openrouter",
    "m2.1": "openrouter",
    "deepseek": "openrouter",
    "llama": "openrouter",
    "qwen": "openrouter",
}


@dataclass
class InteractiveConfig:
    """Configuration for interactive mode."""

    agent: str = "claude"
    model: str = "opus"
    working_dir: Optional[Path] = None
    superagent: bool = False
    max_subagents: int = 5
    subagent_timeout: int = 300


def get_agent_for_model(model: str) -> str:
    """
    Determine the appropriate agent for a given model.

    Args:
        model: Model name or alias

    Returns:
        Agent name to use
    """
    # Check direct mapping
    if model in MODEL_AGENT_MAP:
        return MODEL_AGENT_MAP[model]

    # Check prefix mappings
    for prefix, agent in MODEL_AGENT_MAP.items():
        if prefix.endswith("/") and model.startswith(prefix):
            return agent

    # Check if model contains agent hints
    model_lower = model.lower()
    if "claude" in model_lower or "anthropic" in model_lower:
        return "claude"
    if "gpt" in model_lower or "openai" in model_lower:
        return "codex"
    if "gemini" in model_lower or "google" in model_lower:
        return "gemini"
    if "mistral" in model_lower:
        return "vibe"

    # Default to claude
    return "claude"


def get_cli_path(agent: str) -> Optional[str]:
    """Get the CLI path for an agent."""
    paths = {
        "claude": settings.claude_path,
        "codex": settings.codex_path,
        "gemini": settings.gemini_path,
        "vibe": settings.vibe_path,
        "aider": settings.aider_path,
        "openrouter": settings.aider_path,  # OpenRouter uses aider
    }
    path = paths.get(agent)
    if path and shutil.which(path):
        return path
    return None


def print_banner(config: InteractiveConfig):
    """Print the welcome banner."""
    print("\n╭─────────────────────────────────────────╮")
    print("│           Robot Interactive Mode        │")
    print("╰─────────────────────────────────────────╯")
    print(f"  Agent: {config.agent}  Model: {config.model}")
    if config.working_dir:
        print(f"  Dir: {config.working_dir}")
    print()
    print("  Commands:")
    print("    /agent <name>  - Switch agent (claude, codex, gemini, vibe, aider)")
    print("    /model <name>  - Switch model")
    print("    /super         - Toggle superagent mode")
    print("    /help          - Show commands")
    print("    /quit          - Exit")
    print()


def print_help():
    """Print help information."""
    print("\nCommands:")
    print("  /agent <name>    - Switch to a different agent")
    print("  /model <name>    - Switch to a different model")
    print("  /super           - Toggle superagent mode (spawn subagents)")
    print("  /dir <path>      - Change working directory")
    print("  /status          - Show current settings")
    print("  /help            - Show this help")
    print("  /quit, /exit     - Exit interactive mode")
    print()
    print("Multi-line input:")
    print("  End a line with \\ to continue on next line")
    print("  Or use triple quotes \"\"\" for multi-line blocks")
    print()


def handle_command(cmd: str, config: InteractiveConfig) -> bool:
    """
    Handle a slash command.

    Args:
        cmd: Command string (without leading /)
        config: Current configuration (modified in place)

    Returns:
        True to continue, False to exit
    """
    parts = cmd.split(None, 1)
    command = parts[0].lower()
    arg = parts[1] if len(parts) > 1 else ""

    if command in ("quit", "exit", "q"):
        print("Goodbye!")
        return False

    elif command == "help":
        print_help()

    elif command == "agent":
        if arg:
            valid_agents = ["claude", "codex", "gemini", "vibe", "aider", "openrouter", "zai"]
            if arg in valid_agents:
                config.agent = arg
                print(f"Switched to agent: {arg}")
            else:
                print(f"Unknown agent: {arg}")
                print(f"Valid agents: {', '.join(valid_agents)}")
        else:
            print(f"Current agent: {config.agent}")

    elif command == "model":
        if arg:
            config.model = arg
            # Auto-select agent based on model
            suggested_agent = get_agent_for_model(arg)
            if suggested_agent != config.agent:
                config.agent = suggested_agent
                print(f"Switched to model: {arg} (using {suggested_agent} agent)")
            else:
                print(f"Switched to model: {arg}")
        else:
            print(f"Current model: {config.model}")

    elif command == "super":
        config.superagent = not config.superagent
        status = "enabled" if config.superagent else "disabled"
        print(f"Superagent mode: {status}")

    elif command == "dir":
        if arg:
            path = Path(arg).expanduser().resolve()
            if path.is_dir():
                config.working_dir = path
                print(f"Working directory: {path}")
            else:
                print(f"Not a directory: {arg}")
        else:
            print(f"Working directory: {config.working_dir or os.getcwd()}")

    elif command == "status":
        print(f"\nCurrent settings:")
        print(f"  Agent: {config.agent}")
        print(f"  Model: {config.model}")
        print(f"  Superagent: {'enabled' if config.superagent else 'disabled'}")
        print(f"  Working dir: {config.working_dir or os.getcwd()}")
        print()

    else:
        print(f"Unknown command: /{command}")
        print("Type /help for available commands")

    return True


def read_multiline_input() -> Optional[str]:
    """
    Read potentially multi-line input from the user.

    Supports:
    - Line continuation with trailing backslash
    - Multi-line blocks with triple quotes
    - Ctrl+C to cancel
    - Ctrl+D to exit

    Returns:
        The input string, or None to exit
    """
    try:
        # Try to use prompt_toolkit if available
        try:
            from prompt_toolkit import prompt
            from prompt_toolkit.history import FileHistory
            from prompt_toolkit.auto_suggest import AutoSuggestFromHistory

            history_file = Path.home() / ".robot_history"
            history = FileHistory(str(history_file))

            line = prompt(
                ">>> ",
                history=history,
                auto_suggest=AutoSuggestFromHistory(),
                multiline=False,
            )
        except ImportError:
            # Fall back to basic input
            line = input(">>> ")

        if not line:
            return ""

        # Handle slash commands immediately
        if line.startswith("/"):
            return line

        # Check for line continuation
        lines = [line]
        while lines[-1].endswith("\\"):
            lines[-1] = lines[-1][:-1]  # Remove trailing backslash
            try:
                continuation = input("... ")
                lines.append(continuation)
            except EOFError:
                break

        # Check for triple-quote multi-line
        full_input = "\n".join(lines)
        if '"""' in full_input:
            # Count quotes - if odd number, need to read until closing
            if full_input.count('"""') % 2 == 1:
                while True:
                    try:
                        continuation = input("... ")
                        lines.append(continuation)
                        if '"""' in continuation:
                            break
                    except EOFError:
                        break
                full_input = "\n".join(lines)

        return full_input

    except EOFError:
        print()
        return None
    except KeyboardInterrupt:
        print("\n(Cancelled)")
        return ""


# Action type configurations for CLI display
ACTION_CONFIGS = {
    "Bash": {"icon": "⚡", "color": "\033[33m", "type": "command"},  # Yellow
    "Read": {"icon": "📖", "color": "\033[34m", "type": "read"},     # Blue
    "Write": {"icon": "✏️ ", "color": "\033[32m", "type": "write"},   # Green
    "Edit": {"icon": "🔧", "color": "\033[35m", "type": "edit"},     # Purple
    "Glob": {"icon": "🔍", "color": "\033[36m", "type": "search"},   # Cyan
    "Grep": {"icon": "🔎", "color": "\033[36m", "type": "search"},   # Cyan
    "Task": {"icon": "🤖", "color": "\033[95m", "type": "agent"},    # Pink
    "TodoWrite": {"icon": "📋", "color": "\033[90m", "type": "tool"}, # Gray
    "WebFetch": {"icon": "🌐", "color": "\033[96m", "type": "web"},   # Teal
    "WebSearch": {"icon": "🔍", "color": "\033[96m", "type": "web"},  # Teal
}
RESET_COLOR = "\033[0m"


def event_to_action(event):
    """Convert a status event to an action dict for display."""
    from robot.status import StatusType

    if event.type != StatusType.TOOL_START or not event.tool_name:
        return None

    tool_name = event.tool_name
    config = ACTION_CONFIGS.get(tool_name, {"icon": "🔧", "color": "\033[90m", "type": "tool"})

    # Extract meaningful detail from tool input
    detail = ""
    name = tool_name

    if event.tool_input:
        if tool_name == "Bash":
            cmd = event.tool_input.get("command", "")
            desc = event.tool_input.get("description", "")
            name = desc if desc else (cmd[:50] + "..." if len(cmd) > 50 else cmd)
            detail = cmd
        elif tool_name in ("Read", "Write", "Edit"):
            path = event.tool_input.get("file_path", "")
            name = path.split("/")[-1] if path else tool_name
            detail = path
        elif tool_name == "Glob":
            pattern = event.tool_input.get("pattern", "")
            name = f"glob: {pattern}"
            detail = pattern
        elif tool_name == "Grep":
            pattern = event.tool_input.get("pattern", "")
            name = f"grep: {pattern[:30]}" if len(pattern) > 30 else f"grep: {pattern}"
            detail = pattern
        elif tool_name == "Task":
            desc = event.tool_input.get("description", "")
            name = desc if desc else "Subagent"
            detail = event.tool_input.get("prompt", "")[:100]
        else:
            name = event.message[:50] if event.message else tool_name
            detail = str(event.tool_input)[:100]

    return {
        "type": config["type"],
        "name": name,
        "detail": detail,
        "icon": config["icon"],
        "color": config["color"],
    }


def print_actions_summary(actions):
    """Print a summary of actions taken during the response."""
    if not actions:
        return

    print("\n╭─ Actions ─────────────────────────────────╮")
    for action in actions:
        icon = action["icon"]
        color = action["color"]
        name = action["name"]
        # Truncate long names
        if len(name) > 42:
            name = name[:39] + "..."
        print(f"│ {icon} {color}{name}{RESET_COLOR}")
    print("╰───────────────────────────────────────────╯")


# Global list to collect actions during execution
_collected_actions = []


def print_interactive_status(event):
    """Print a status event with live updates in interactive mode."""
    from robot.status import StatusType

    # Collect actions
    action = event_to_action(event)
    if action:
        _collected_actions.append(action)

    icons = {
        StatusType.INIT: "→",
        StatusType.THINKING: "·",
        StatusType.TOOL_START: "▶",
        StatusType.TOOL_COMPLETE: "✓",
        StatusType.RESPONDING: "·",
        StatusType.COMPLETE: "✓",
        StatusType.ERROR: "✗",
    }
    icon = icons.get(event.type, "·")

    # Use carriage return to overwrite the status line
    print(f"\r\033[K  {icon} {event.message}", end="", flush=True)

    # Print newline for complete/error events
    if event.type in (StatusType.COMPLETE, StatusType.ERROR):
        print()


def run_prompt_interactive(prompt: str, config: InteractiveConfig):
    """
    Run a prompt using the Robot API with live status updates.

    Args:
        prompt: The prompt to send
        config: Current configuration
    """
    global _collected_actions
    from robot import Robot
    from robot.base import AgentConfig

    # Use Robot API for Claude to get status updates
    if config.agent == "claude":
        agent_config = AgentConfig(
            model=config.model,
            working_dir=config.working_dir,
        )

        if config.superagent:
            from robot.superagent import get_superagent_prefix
            agent_config.prompt_prefix = get_superagent_prefix(
                max_subagents=config.max_subagents,
                subagent_timeout=config.subagent_timeout,
                working_dir=config.working_dir,
            )

        try:
            # Clear collected actions
            _collected_actions = []

            print()  # Blank line before status
            agent = Robot.get(config.agent, config=agent_config)
            response = agent.run(
                prompt=prompt,
                working_dir=config.working_dir,
                on_status=print_interactive_status,
            )

            # Print actions summary
            if _collected_actions:
                print_actions_summary(_collected_actions)

            if response.success:
                print(response.content)
            else:
                print(f"\nError: {response.error}")
            print()

        except KeyboardInterrupt:
            print("\n(Interrupted)")
        except Exception as e:
            print(f"\nError: {e}")
        return

    # For other agents, fall back to CLI-based execution
    cli_path = get_cli_path(config.agent)

    if not cli_path:
        run_prompt_via_robot(prompt, config)
        return

    # Build command based on agent
    if config.agent == "codex":
        cmd = [cli_path, prompt, "--model", config.model, "--approval-mode", "full-auto"]

    elif config.agent == "gemini":
        cmd = [cli_path, prompt, "--model", config.model]

    elif config.agent == "vibe":
        cmd = [cli_path, "-p", prompt, "--model", config.model]

    elif config.agent in ("aider", "openrouter"):
        model = config.model
        if config.agent == "openrouter" and not model.startswith("openrouter/"):
            from robot.agents.openrouter import OpenRouterAgent
            agent = OpenRouterAgent()
            model = agent._resolve_model(model)
        cmd = [cli_path, "--message", prompt, "--yes", "--model", model, "--no-auto-commits"]
        if config.agent == "openrouter":
            cmd.append("--no-git")

    else:
        run_prompt_via_robot(prompt, config)
        return

    # Run with streaming output
    try:
        cwd = config.working_dir or Path.cwd()
        process = subprocess.Popen(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            cwd=cwd,
            bufsize=1,
        )

        print()
        for line in process.stdout:
            print(line, end="", flush=True)

        process.wait()
        print()

    except KeyboardInterrupt:
        print("\n(Interrupted)")
        process.terminate()
    except Exception as e:
        print(f"\nError: {e}")


def run_prompt_via_robot(prompt: str, config: InteractiveConfig):
    """
    Run a prompt using the robot command.

    Args:
        prompt: The prompt to send
        config: Current configuration
    """
    robot_path = shutil.which("robot")
    if not robot_path:
        # Use module directly
        robot_path = sys.executable
        cmd = [robot_path, "-m", "robot.cli", "run", prompt]
    else:
        cmd = [robot_path, "run", prompt]

    cmd.extend(["--agent", config.agent, "--model", config.model])

    if config.working_dir:
        cmd.extend(["--dir", str(config.working_dir)])

    if config.superagent:
        cmd.append("--superagent")
        cmd.extend(["--max-subagents", str(config.max_subagents)])
        cmd.extend(["--subagent-timeout", str(config.subagent_timeout)])

    try:
        cwd = config.working_dir or Path.cwd()
        process = subprocess.Popen(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            cwd=cwd,
            bufsize=1,
        )

        print()
        for line in process.stdout:
            print(line, end="", flush=True)

        process.wait()
        print()

    except KeyboardInterrupt:
        print("\n(Interrupted)")
        process.terminate()
    except Exception as e:
        print(f"\nError: {e}")


def run_interactive(
    agent: Optional[str] = None,
    model: Optional[str] = None,
    working_dir: Optional[Path] = None,
    superagent: bool = False,
):
    """
    Run the interactive mode.

    Args:
        agent: Initial agent (default: claude)
        model: Initial model (default: opus)
        working_dir: Working directory
        superagent: Enable superagent mode
    """
    # Set defaults
    default_model = model or "opus"
    default_agent = agent or get_agent_for_model(default_model)

    config = InteractiveConfig(
        agent=default_agent,
        model=default_model,
        working_dir=working_dir,
        superagent=superagent,
    )

    print_banner(config)

    while True:
        try:
            user_input = read_multiline_input()

            if user_input is None:
                # EOF - exit
                print("Goodbye!")
                break

            if not user_input.strip():
                continue

            # Handle commands
            if user_input.startswith("/"):
                if not handle_command(user_input[1:], config):
                    break
                continue

            # Run the prompt
            run_prompt_interactive(user_input, config)

        except KeyboardInterrupt:
            print("\n(Use /quit to exit)")
            continue
