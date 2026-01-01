"""
Command-line interface for Robot.

Provides direct CLI access to run prompts, tasks, and check agent availability.
Supports superagent mode for spawning subagents and interactive TUI mode.
"""

import sys
from pathlib import Path

import click


def print_status(event):
    """Print a status event to stderr for live feedback."""
    from robot.status import StatusType

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

    # Use carriage return to overwrite the line
    click.echo(f"\r\033[K{icon} {event.message}", nl=False, err=True)

    # Print newline for complete/error events
    if event.type in (StatusType.COMPLETE, StatusType.ERROR):
        click.echo(err=True)


@click.group(invoke_without_command=True)
@click.option("-a", "--agent", default=None, help="Agent to use (default: claude)")
@click.option("-m", "--model", default=None, help="Model to use (default: opus)")
@click.option("-d", "--dir", "working_dir", default=None, help="Working directory")
@click.option("--superagent", is_flag=True, help="Enable superagent mode")
@click.pass_context
def cli(ctx, agent, model, working_dir, superagent):
    """Unified interface for CLI coding agents."""
    ctx.ensure_object(dict)
    ctx.obj["agent"] = agent
    ctx.obj["model"] = model
    ctx.obj["working_dir"] = working_dir
    ctx.obj["superagent"] = superagent

    if ctx.invoked_subcommand is None:
        # Default to interactive mode
        ctx.invoke(
            interactive,
            agent=agent,
            model=model,
            working_dir=working_dir,
            superagent=superagent,
        )


@cli.command("interactive")
@click.option("-a", "--agent", default=None, help="Agent to use")
@click.option("-m", "--model", default=None, help="Model to use (default: opus)")
@click.option("-d", "--dir", "working_dir", default=None, help="Working directory")
@click.option("--superagent", is_flag=True, help="Enable superagent mode")
def interactive(agent, model, working_dir, superagent):
    """Interactive mode (default)."""
    from robot.interactive import run_interactive

    run_interactive(
        agent=agent,
        model=model,
        working_dir=Path(working_dir) if working_dir else None,
        superagent=superagent,
    )


@cli.command()
@click.argument("prompt")
@click.option("-a", "--agent", default=None, help="Agent to use")
@click.option("-m", "--model", default=None, help="Model to use")
@click.option("-d", "--dir", "working_dir", default=None, help="Working directory")
@click.option("-t", "--timeout", type=int, default=None, help="Timeout in seconds")
@click.option("-s", "--stream", is_flag=True, help="Show live status updates")
@click.option("-q", "--quiet", is_flag=True, help="Suppress status and error messages")
@click.option("--superagent", is_flag=True, help="Enable superagent mode (can spawn subagents)")
@click.option("--no-superagent", is_flag=True, help="Disable superagent capabilities (used for subagents)")
@click.option("--max-subagents", type=int, default=None, help="Maximum number of subagents (default: 5)")
@click.option("--subagent-timeout", type=int, default=None, help="Timeout per subagent in seconds (default: 300)")
def run(prompt, agent, model, working_dir, timeout, stream, quiet, superagent, no_superagent, max_subagents, subagent_timeout):
    """Run a single prompt."""
    from robot import Robot
    from robot.base import AgentConfig

    # Build config with timeout
    config_kwargs = {}
    if timeout:
        config_kwargs["timeout"] = timeout

    config = AgentConfig(**config_kwargs) if config_kwargs else None

    # Status callback for streaming (disabled in quiet mode)
    on_status = None
    if stream and not quiet:
        on_status = print_status

    # Check for superagent mode
    if superagent and not no_superagent:
        from robot.superagent import SuperAgent, DEFAULT_SUBAGENT_TIMEOUT, MAX_SUBAGENTS

        base_agent = Robot.get(agent or "claude", config=config)
        agent_instance = SuperAgent(
            base_agent,
            max_subagents=max_subagents or MAX_SUBAGENTS,
            subagent_timeout=subagent_timeout or DEFAULT_SUBAGENT_TIMEOUT,
        )
        response = agent_instance.run(
            prompt=prompt,
            model=model,
            working_dir=Path(working_dir) if working_dir else None,
        )
    else:
        agent_instance = Robot.get(agent or "claude", config=config)
        response = agent_instance.run(
            prompt=prompt,
            model=model,
            working_dir=Path(working_dir) if working_dir else None,
            on_status=on_status,
        )

    if response.success:
        click.echo(response.content)
    else:
        if not quiet:
            click.echo(f"Error: {response.error}", err=True)
        sys.exit(1)


@cli.command()
@click.argument("task")
@click.option("-a", "--agent", default=None, help="Agent to use")
@click.option("-d", "--dir", "working_dir", default=None, help="Working directory")
def task(task, agent, working_dir):
    """Run a predefined task."""
    from robot import Robot

    response = Robot.run_task(
        task=task,
        agent=agent,
        working_dir=Path(working_dir) if working_dir else None,
    )

    if response.success:
        click.echo(response.content)
    else:
        click.echo(f"Error: {response.error}", err=True)
        sys.exit(1)


@cli.command("list")
def list_agents():
    """List available agents."""
    from robot import Robot

    click.echo("Registered agents:")
    for name in Robot.list_registered():
        click.echo(f"  - {name}")

    click.echo("\nAvailable (installed):")
    for name in Robot.list_available():
        click.echo(f"  - {name}")


@cli.command()
@click.argument("agent")
def check(agent):
    """Check agent availability."""
    from robot import Robot

    agent_instance = Robot.get(agent)
    if agent_instance.is_available():
        click.echo(f"{agent}: available at {agent_instance.get_cli_path()}")
    else:
        click.echo(f"{agent}: not found")
        sys.exit(1)


@cli.command()
@click.option("--host", default=None, help="Server host (default: localhost)")
@click.option("--port", type=int, default=None, help="Server port (default: 9999)")
def auth(host, port):
    """Generate web authentication link."""
    import secrets
    import uuid
    from datetime import datetime, timedelta, timezone

    from peewee import SqliteDatabase, Model, CharField, DateTimeField, BooleanField

    from robot.config import settings

    # Database setup (same as server.py)
    DB_PATH = Path("/tmp/robot/robot_web.db")
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    db = SqliteDatabase(str(DB_PATH))

    class BaseDBModel(Model):
        class Meta:
            database = db

    class AuthCode(BaseDBModel):
        id = CharField(primary_key=True, default=lambda: str(uuid.uuid4()))
        code = CharField(unique=True, max_length=64)
        created_at = DateTimeField(default=lambda: datetime.now(timezone.utc))
        expires_at = DateTimeField()
        used = BooleanField(default=False)

    # Ensure table exists
    db.connect()
    db.create_tables([AuthCode])

    # Generate code
    code = secrets.token_urlsafe(32)
    expires_at = datetime.now(timezone.utc) + timedelta(hours=1)
    AuthCode.create(code=code, expires_at=expires_at)

    # Build URL - use CLI args, then config, then defaults
    server_host = host or settings.server_host
    server_port = port or settings.server_port
    url = f"http://{server_host}:{server_port}/api/auth/verify?code={code}"

    click.echo(f"\nAuthentication link (expires in 1 hour):\n")
    click.echo(f"  {url}\n")

    # Display QR code if terminal supports it
    try:
        import qrcode
        qr = qrcode.QRCode(
            version=1,
            error_correction=qrcode.constants.ERROR_CORRECT_L,
            box_size=1,
            border=1,
        )
        qr.add_data(url)
        qr.make(fit=True)

        click.echo("Scan this QR code:\n")
        qr.print_ascii(invert=True)
        click.echo()
    except ImportError:
        click.echo("(Install 'qrcode' package for QR code display)")


def main():
    """Main entry point."""
    cli()


if __name__ == "__main__":
    main()
