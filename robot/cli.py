"""
Command-line interface for Robot.

Provides direct CLI access to run prompts, tasks, and check agent availability.
Supports superagent mode for spawning subagents and interactive TUI mode.
"""

import argparse
import sys
from pathlib import Path


def cmd_interactive(args):
    """Run in interactive mode."""
    from robot.interactive import run_interactive

    run_interactive(
        agent=args.agent,
        model=args.model,
        working_dir=Path(args.dir) if args.dir else None,
        superagent=args.superagent,
    )


def cmd_run(args):
    """Run a prompt with an agent."""
    from robot import Robot
    from robot.base import AgentConfig

    # Build config with timeout
    config_kwargs = {}
    if args.timeout:
        config_kwargs["timeout"] = args.timeout

    config = AgentConfig(**config_kwargs) if config_kwargs else None

    # Check for superagent mode
    if args.superagent and not args.no_superagent:
        from robot.superagent import SuperAgent, DEFAULT_SUBAGENT_TIMEOUT, MAX_SUBAGENTS

        base_agent = Robot.get(args.agent or "claude", config=config)
        agent = SuperAgent(
            base_agent,
            max_subagents=args.max_subagents or MAX_SUBAGENTS,
            subagent_timeout=args.subagent_timeout or DEFAULT_SUBAGENT_TIMEOUT,
        )
        response = agent.run(
            prompt=args.prompt,
            model=args.model,
            working_dir=Path(args.dir) if args.dir else None,
        )
    else:
        response = Robot.run(
            prompt=args.prompt,
            agent=args.agent,
            model=args.model,
            working_dir=Path(args.dir) if args.dir else None,
            config=config,
        )

    if response.success:
        print(response.content)
    else:
        print(f"Error: {response.error}", file=sys.stderr)
        sys.exit(1)


def cmd_task(args):
    """Run a predefined task."""
    from robot import Robot

    response = Robot.run_task(
        task=args.task,
        agent=args.agent,
        working_dir=Path(args.dir) if args.dir else None,
    )

    if response.success:
        print(response.content)
    else:
        print(f"Error: {response.error}", file=sys.stderr)
        sys.exit(1)


def cmd_list(args):
    """List available agents."""
    from robot import Robot

    print("Registered agents:")
    for name in Robot.list_registered():
        print(f"  - {name}")

    print("\nAvailable (installed):")
    for name in Robot.list_available():
        print(f"  - {name}")


def cmd_check(args):
    """Check agent availability."""
    from robot import Robot

    agent = Robot.get(args.agent)
    if agent.is_available():
        print(f"{args.agent}: available at {agent.get_cli_path()}")
    else:
        print(f"{args.agent}: not found")
        sys.exit(1)


def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(
        prog="robot",
        description="Unified interface for CLI coding agents",
    )

    # Global options for interactive mode (when no subcommand)
    parser.add_argument("-a", "--agent", default=None, help="Agent to use (default: claude)")
    parser.add_argument("-m", "--model", default=None, help="Model to use (default: opus)")
    parser.add_argument("-d", "--dir", default=None, help="Working directory")
    parser.add_argument("--superagent", action="store_true", help="Enable superagent mode")

    subparsers = parser.add_subparsers(dest="command", help="Commands")

    # interactive command (explicit)
    interactive_parser = subparsers.add_parser("interactive", aliases=["i"], help="Interactive mode (default)")
    interactive_parser.add_argument("-a", "--agent", default=None, help="Agent to use")
    interactive_parser.add_argument("-m", "--model", default=None, help="Model to use (default: opus)")
    interactive_parser.add_argument("-d", "--dir", default=None, help="Working directory")
    interactive_parser.add_argument("--superagent", action="store_true", help="Enable superagent mode")
    interactive_parser.set_defaults(func=cmd_interactive)

    # run command
    run_parser = subparsers.add_parser("run", help="Run a single prompt")
    run_parser.add_argument("prompt", help="Prompt to send")
    run_parser.add_argument("-a", "--agent", default=None, help="Agent to use")
    run_parser.add_argument("-m", "--model", default=None, help="Model to use")
    run_parser.add_argument("-d", "--dir", default=None, help="Working directory")
    run_parser.add_argument("-t", "--timeout", type=int, default=None, help="Timeout in seconds")

    # Superagent options
    run_parser.add_argument(
        "--superagent", action="store_true",
        help="Enable superagent mode (can spawn subagents)"
    )
    run_parser.add_argument(
        "--no-superagent", action="store_true",
        help="Disable superagent capabilities (used for subagents)"
    )
    run_parser.add_argument(
        "--max-subagents", type=int, default=None,
        help="Maximum number of subagents (default: 5)"
    )
    run_parser.add_argument(
        "--subagent-timeout", type=int, default=None,
        help="Timeout per subagent in seconds (default: 300)"
    )
    run_parser.set_defaults(func=cmd_run)

    # task command
    task_parser = subparsers.add_parser("task", help="Run a predefined task")
    task_parser.add_argument("task", help="Task name (e.g., readme, review)")
    task_parser.add_argument("-a", "--agent", default=None, help="Agent to use")
    task_parser.add_argument("-d", "--dir", default=None, help="Working directory")
    task_parser.set_defaults(func=cmd_task)

    # list command
    list_parser = subparsers.add_parser("list", help="List available agents")
    list_parser.set_defaults(func=cmd_list)

    # check command
    check_parser = subparsers.add_parser("check", help="Check agent availability")
    check_parser.add_argument("agent", help="Agent to check")
    check_parser.set_defaults(func=cmd_check)

    args = parser.parse_args()

    if args.command is None:
        # Default to interactive mode
        cmd_interactive(args)
    else:
        args.func(args)


if __name__ == "__main__":
    main()
