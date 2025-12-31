"""
Status event system for streaming agent progress.

Provides real-time status updates from coding agents during execution.
Events are emitted as agents work: starting tools, completing actions,
and producing output. This enables live feedback in CLI, web, and TUI.
"""

import json
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any, Callable, Optional


class StatusType(Enum):
    """Types of status events emitted during agent execution."""
    INIT = "init"           # Session started
    THINKING = "thinking"   # Agent is processing
    TOOL_START = "tool_start"     # Tool execution started
    TOOL_COMPLETE = "tool_complete"  # Tool execution finished
    RESPONDING = "responding"  # Agent is generating text
    COMPLETE = "complete"   # Task finished successfully
    ERROR = "error"         # Task failed


@dataclass
class StatusEvent:
    """
    A status event from an agent execution.

    Attributes:
        type: The type of status event
        message: Human-readable description of what's happening
        timestamp: When the event occurred
        tool_name: Name of the tool being used (for tool events)
        tool_input: Input parameters to the tool
        session_id: Session identifier
        cost_usd: Cumulative cost so far
        duration_ms: Duration so far in milliseconds
        raw: Raw event data from the agent (for debugging)
    """
    type: StatusType
    message: str
    timestamp: datetime = field(default_factory=datetime.now)
    tool_name: Optional[str] = None
    tool_input: Optional[dict] = None
    session_id: Optional[str] = None
    cost_usd: Optional[float] = None
    duration_ms: Optional[int] = None
    raw: Optional[dict] = None

    def to_dict(self) -> dict:
        """Convert to dictionary for JSON serialization."""
        return {
            "type": self.type.value,
            "message": self.message,
            "timestamp": self.timestamp.isoformat(),
            "tool_name": self.tool_name,
            "tool_input": self.tool_input,
            "session_id": self.session_id,
            "cost_usd": self.cost_usd,
            "duration_ms": self.duration_ms,
        }

    def to_json(self) -> str:
        """Convert to JSON string."""
        return json.dumps(self.to_dict())


# Type alias for status callbacks
StatusCallback = Callable[[StatusEvent], None]


def describe_tool_use(tool_name: str, tool_input: dict) -> str:
    """
    Generate a human-readable description of a tool use.

    Args:
        tool_name: Name of the tool
        tool_input: Input parameters to the tool

    Returns:
        Human-readable description of what the tool is doing
    """
    if tool_name == "Bash":
        cmd = tool_input.get("command", "")
        desc = tool_input.get("description", "")
        if desc:
            return f"Running: {desc}"
        return f"Running: {cmd[:60]}..." if len(cmd) > 60 else f"Running: {cmd}"

    elif tool_name == "Read":
        path = tool_input.get("file_path", "")
        return f"Reading: {_short_path(path)}"

    elif tool_name == "Write":
        path = tool_input.get("file_path", "")
        return f"Writing: {_short_path(path)}"

    elif tool_name == "Edit":
        path = tool_input.get("file_path", "")
        return f"Editing: {_short_path(path)}"

    elif tool_name == "Glob":
        pattern = tool_input.get("pattern", "")
        return f"Searching: {pattern}"

    elif tool_name == "Grep":
        pattern = tool_input.get("pattern", "")
        return f"Searching for: {pattern[:40]}"

    elif tool_name == "Task":
        desc = tool_input.get("description", "")
        agent_type = tool_input.get("subagent_type", "")
        if desc:
            return f"Spawning agent: {desc}"
        return f"Spawning {agent_type} agent"

    elif tool_name == "WebSearch":
        query = tool_input.get("query", "")
        return f"Searching web: {query[:40]}"

    elif tool_name == "WebFetch":
        url = tool_input.get("url", "")
        return f"Fetching: {_short_url(url)}"

    elif tool_name == "TodoWrite":
        return "Updating task list"

    elif tool_name == "LSP":
        op = tool_input.get("operation", "")
        path = tool_input.get("filePath", "")
        return f"LSP {op}: {_short_path(path)}"

    else:
        return f"Using tool: {tool_name}"


def _short_path(path: str, max_len: int = 50) -> str:
    """Shorten a path for display."""
    if len(path) <= max_len:
        return path
    # Keep the filename and some of the path
    parts = path.split("/")
    if len(parts) <= 2:
        return path[:max_len] + "..."
    return ".../" + "/".join(parts[-2:])


def _short_url(url: str, max_len: int = 50) -> str:
    """Shorten a URL for display."""
    if len(url) <= max_len:
        return url
    return url[:max_len] + "..."


class StatusParser:
    """
    Parse streaming output from agents into StatusEvents.

    Currently supports Claude CLI's stream-json format.
    Can be extended to support other agents' streaming formats.
    """

    def __init__(self, agent_name: str = "claude"):
        self.agent_name = agent_name
        self._pending_tool: Optional[str] = None

    def parse_line(self, line: str) -> Optional[StatusEvent]:
        """
        Parse a single line of streaming output.

        Args:
            line: A line of JSON from the agent's stream output

        Returns:
            StatusEvent if the line represents a status change, None otherwise
        """
        line = line.strip()
        if not line:
            return None

        try:
            event = json.loads(line)
        except json.JSONDecodeError:
            return None

        return self._parse_claude_event(event)

    def _parse_claude_event(self, event: dict) -> Optional[StatusEvent]:
        """Parse a Claude stream-json event."""
        event_type = event.get("type")
        subtype = event.get("subtype")

        if event_type == "system" and subtype == "init":
            model = event.get("model", "unknown")
            return StatusEvent(
                type=StatusType.INIT,
                message=f"Starting session with {model}",
                session_id=event.get("session_id"),
                raw=event
            )

        elif event_type == "assistant":
            message = event.get("message", {})
            content = message.get("content", [])

            for item in content:
                if item.get("type") == "tool_use":
                    tool_name = item.get("name", "unknown")
                    tool_input = item.get("input", {})
                    self._pending_tool = tool_name

                    description = describe_tool_use(tool_name, tool_input)

                    return StatusEvent(
                        type=StatusType.TOOL_START,
                        message=description,
                        tool_name=tool_name,
                        tool_input=tool_input,
                        session_id=event.get("session_id"),
                        raw=event
                    )

                elif item.get("type") == "text":
                    text = item.get("text", "")
                    # Truncate long text for status
                    preview = text[:80] + "..." if len(text) > 80 else text
                    # Remove newlines for compact display
                    preview = preview.replace("\n", " ")
                    return StatusEvent(
                        type=StatusType.RESPONDING,
                        message=preview,
                        session_id=event.get("session_id"),
                        raw=event
                    )

        elif event_type == "user":
            tool_result = event.get("tool_use_result", {})
            if tool_result:
                tool_name = self._pending_tool or "Tool"
                self._pending_tool = None
                return StatusEvent(
                    type=StatusType.TOOL_COMPLETE,
                    message=f"{tool_name} completed",
                    tool_name=tool_name,
                    session_id=event.get("session_id"),
                    raw=event
                )

        elif event_type == "result":
            success = subtype == "success"
            duration_ms = event.get("duration_ms", 0)
            cost_usd = event.get("total_cost_usd", 0)

            if success:
                return StatusEvent(
                    type=StatusType.COMPLETE,
                    message=f"Completed in {duration_ms}ms (${cost_usd:.4f})",
                    cost_usd=cost_usd,
                    duration_ms=duration_ms,
                    session_id=event.get("session_id"),
                    raw=event
                )
            else:
                error = event.get("error", "Unknown error")
                return StatusEvent(
                    type=StatusType.ERROR,
                    message=f"Failed: {error}",
                    duration_ms=duration_ms,
                    session_id=event.get("session_id"),
                    raw=event
                )

        return None
