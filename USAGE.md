This is the documentation for the `robot` project, an expert system for managing and interacting with various AI coding agents via a unified Python interface and CLI.

## `robot.base.AgentConfig`

The `AgentConfig` dataclass holds configuration parameters for executing an agent. This allows for fine-grained control over model selection, timeouts, API keys, and session management for individual agent runs.

```python
from robot.base import AgentConfig
from pathlib import Path

# Example usage of AgentConfig
config = AgentConfig(
    model="sonnet",
    timeout=300,
    api_key="my-secret-key",
    working_dir=Path("/path/to/project"),
    resume=True,
    session_id="session-123"
)

print(config.model)
print(config.timeout)
print(config.resume)
```

*   **Initialization**: Creates a configuration object specifying parameters like the model to use, execution timeout, API credentials, working directory, and session resume options.
*   **Model Selection**: The `model` attribute specifies the AI model (e.g., "sonnet", "gpt-4o") the agent should use.
*   **Session Management**: `resume` (boolean) and `session_id` (string) control whether to continue a previous conversation or start a new one.
*   **Environment Overrides**: `api_key` and `base_url` allow overriding global environment variables for specific agent instances.

## `robot.base.BaseAgent`

`BaseAgent` is the abstract base class defining the core interface for all coding agents. It provides common utilities like rate limiting, subprocess execution, and error handling.

```python
from robot.base import BaseAgent, AgentConfig
from robot.response import AgentResponse
from typing import Optional, list

# Example of a minimal concrete agent implementation (for demonstration)
class MockAgent(BaseAgent):
    name = "mock"
    default_model = "mock-v1"

    def get_cli_path(self) -> str:
        return "echo" # Use a simple command for testing availability

    def build_command(self, prompt: str, model: Optional[str] = None, system_prompt: Optional[str] = None, **kwargs) -> list[str]:
        return [self.get_cli_path(), f"Response to: {prompt}"]

    def parse_output(self, stdout: str, stderr: str) -> tuple[bool, str]:
        return True, stdout.strip()

# Instantiate the mock agent
mock_agent = MockAgent(config=AgentConfig(timeout=10))

# Check availability (will likely succeed if 'echo' is in PATH)
is_available = mock_agent.is_available()
print(f"MockAgent available: {is_available}")

# Simulate running the agent
# Note: This actual run will use subprocess.run and is mocked here for output clarity.
# response = mock_agent.run("Write a function")
# print(response.content)
```

*   **Abstract Interface**: Defines required methods (`get_cli_path`, `build_command`, `parse_output`) that all concrete agents must implement to interact with their respective CLI tools.
*   **Rate Limiting**: The internal `_rate_limit` method ensures that agent calls adhere to configured rate limits, preventing API overuse.
*   **Subprocess Execution**: `_run_subprocess` and `_run_streaming_subprocess` handle the execution of the underlying CLI commands, managing timeouts, working directories, and environment variables.
*   **Execution Flow**: The `run` method orchestrates the execution, including retries, error handling, and wrapping the final result in an `AgentResponse`.

## `robot.config.Settings`

The `Settings` dataclass manages global configuration for the project, loading values from environment variables (`.env` file support is included) or falling back to sensible defaults.

```python
from robot.config import settings

# Accessing default settings
print(f"Default Agent: {settings.default_agent}")
print(f"Default Timeout: {settings.default_timeout}s")

# Accessing an agent's configured path (may be loaded from env var)
claude_path = settings.get_agent_path("claude")
print(f"Claude CLI Path: {claude_path}")

# Accessing API key (may be loaded from env var)
openrouter_key = settings.get_agent_api_key("openrouter")
print(f"OpenRouter API Key (first 5 chars): {openrouter_key[:5]}...")
```

*   **Environment Loading**: Uses `dotenv` to load configuration from environment variables, prioritizing `ROBOT_*` prefixed variables.
*   **Agent Paths**: Provides methods (`get_agent_path`, `get_agent_api_key`, `get_agent_base_url`) to retrieve specific configuration details for each supported agent.
*   **Global Defaults**: Sets defaults for common parameters like `default_agent` ("claude") and `default_timeout` (180 seconds).

## `robot.status.StatusEvent`

The `StatusEvent` dataclass represents a real-time update on the agent's progress during execution, particularly useful for streaming interfaces.

```python
from robot.status import StatusEvent, StatusType
from datetime import datetime

# Create a StatusEvent for a tool start
event = StatusEvent(
    type=StatusType.TOOL_START,
    message="Starting bash command",
    tool_name="Bash",
    tool_input={"command": "ls -l"},
    duration_ms=100
)

# Convert to dictionary for serialization
event_dict = event.to_dict()
print(event_dict['type'])
print(event_dict['message'])
```

*   **Real-time Feedback**: Used to communicate the agent's internal state (thinking, tool use, responding) to the user interface (CLI, TUI, Web).
*   **Tool Tracking**: Includes fields (`tool_name`, `tool_input`) to detail which tool the agent is currently using.
*   **Serialization**: Provides `to_dict` and `to_json` methods for easy transmission over network streams (e.g., SSE in the web server).

## `robot.status.StatusParser`

The `StatusParser` is responsible for consuming raw streaming output from an agent's CLI (currently optimized for Claude's `stream-json` format) and converting it into structured `StatusEvent` objects.

```python
from robot.status import StatusParser, StatusType
import json

parser = StatusParser(agent_name="claude")

# Simulate a line of stream-json output from Claude CLI
simulated_line = json.dumps({
    "type": "assistant",
    "subtype": "tool_use",
    "message": {"content": [{"type": "tool_use", "name": "Read", "input": {"file_path": "README.md"}}]}
})

event = parser.parse_line(simulated_line)

if event:
    print(f"Parsed Event Type: {event.type.value}")
    print(f"Parsed Tool Name: {event.tool_name}")
```

*   **Stream Processing**: Reads line-by-line output from the agent's subprocess.
*   **Event Extraction**: Identifies and parses JSON structures within the stream that correspond to status changes.
*   **Normalization**: Converts agent-specific output formats into the unified `StatusEvent` structure.

## `robot.response.AgentResponse`

`AgentResponse` is the unified dataclass used to return results from any agent execution, normalizing the output regardless of the underlying CLI tool.

```python
from robot.response import AgentResponse

# Example of a successful response
response = AgentResponse(
    success=True,
    content="def hello(): return 'world'",
    raw_output="[LOGS] ... \n def hello(): return 'world'",
    agent="claude",
    model="sonnet",
    duration=5.2,
    files_modified=["main.py"]
)

# Check success status
if response:
    print(f"Agent: {response.agent}, Duration: {response.duration:.2f}s")
    print(response.content)
```

*   **Consistency**: Ensures all agent results are returned in a predictable format, including success status, final content, raw output, and metadata.
*   **Boolean Context**: Allows the response object to be used directly in conditional statements (`if response:`).
*   **Error Reporting**: Includes an `error` field for detailed failure messages.

## `robot.registry.Robot`

The `Robot` class serves as the main entry point and factory for interacting with all agents. It manages the agent registry and provides high-level methods for running prompts and tasks.

```python
from robot import Robot
from robot.base import AgentConfig

# 1. Get a specific agent instance
claude_agent = Robot.get("claude", config=AgentConfig(model="opus"))
print(f"Agent instance name: {claude_agent.name}")

# 2. Run a prompt