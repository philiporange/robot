# Robot - Multi-Agent CLI Wrapper

A unified Python interface for programmatically calling CLI-based coding agents including Claude Code, OpenAI Codex CLI, Gemini CLI, Mistral Vibe, and Aider.

## Overview

Robot provides a consistent API for invoking various AI coding assistants in headless/non-interactive mode. Each agent has different CLI interfaces, output formats, and capabilities - Robot normalizes these into a single interface with YAML-based prompt configuration.

## Supported Agents

| Agent | CLI Command | Headless Support | Output Format |
|-------|-------------|------------------|---------------|
| Claude Code | `claude` | Yes (`-p` flag) | JSON |
| OpenAI Codex | `codex` | Yes (`-q` quiet mode) | Text/JSON |
| Gemini CLI | `gemini` | Yes (`-p` flag) | Text/JSON |
| Mistral Vibe | `vibe` | Yes (pipe mode) | Text |
| Aider | `aider` | Yes (`--message` flag) | Text |

## Architecture

```
robot/
├── pyproject.toml
├── requirements.txt
├── README.md
├── PLAN.md
├── robot/
│   ├── __init__.py
│   ├── config.py           # Settings with dotenv
│   ├── base.py             # Abstract base class for agents
│   ├── response.py         # Unified response dataclass
│   ├── registry.py         # Agent registry and factory
│   ├── prompts.py          # YAML prompt loader
│   ├── agents/
│   │   ├── __init__.py
│   │   ├── claude.py       # Claude Code wrapper
│   │   ├── codex.py        # OpenAI Codex wrapper
│   │   ├── gemini.py       # Gemini CLI wrapper
│   │   ├── vibe.py         # Mistral Vibe wrapper
│   │   └── aider.py        # Aider wrapper
│   └── prompts/
│       ├── default.yaml    # Default prompts
│       └── tasks/
│           ├── readme.yaml
│           ├── review.yaml
│           ├── refactor.yaml
│           └── explain.yaml
└── tests/
    └── test_agents.py
```

## Core Components

### 1. Base Agent Class

```python
class BaseAgent(ABC):
    """Abstract base class for all coding agents."""

    name: str                    # Agent identifier
    cli_command: str             # CLI binary name
    supports_tools: bool         # Whether agent supports tool use
    supports_streaming: bool     # Whether agent supports streaming
    default_model: str           # Default model for this agent

    @abstractmethod
    def run(self, prompt: str, **kwargs) -> AgentResponse:
        """Execute the agent with given prompt."""
        pass

    @abstractmethod
    def is_available(self) -> bool:
        """Check if CLI is installed and accessible."""
        pass
```

### 2. Unified Response

```python
@dataclass
class AgentResponse:
    success: bool
    content: str                 # Main text output
    raw_output: str              # Unprocessed CLI output
    agent: str                   # Which agent produced this
    model: str                   # Model used
    duration: float              # Execution time in seconds
    error: Optional[str] = None
    files_modified: list = None  # Files changed (if applicable)
    tokens_used: Optional[int] = None
    cost: Optional[float] = None
```

### 3. Agent Registry

```python
# Get agent by name
agent = Robot.get("claude")
response = agent.run("Explain this code", working_dir=project_path)

# List available agents
available = Robot.list_available()  # ["claude", "gemini", "aider"]

# Use default agent
response = Robot.run("Fix the bug in auth.py")
```

## Agent-Specific Implementation Details

### Claude Code

**CLI Interface:**
```bash
claude -p "<prompt>" --output-format json \
  --model <model> \
  --system-prompt "<system>" \
  --allowed-tools Read,Glob,Grep,Write \
  --add-dir <directory>
```

**Features:**
- Full tool use (Read, Write, Glob, Grep, Bash, etc.)
- System prompt support
- Model selection (sonnet, opus, haiku)
- Directory permissions
- JSON output format

**Implementation Notes:**
- Parse JSON output for structured responses
- Handle tool use results
- Support `--add-dir` for multi-directory projects

### OpenAI Codex CLI

**CLI Interface:**
```bash
codex -q "<prompt>" \
  --model <model> \
  --approval-mode full-auto
```

**Features:**
- Quiet mode for scripting (`-q`)
- Full auto mode for non-interactive use
- Model selection (o4-mini, o3, etc.)

**Implementation Notes:**
- Use `-q` for quiet/headless operation
- Parse text output
- Handle approval modes

### Gemini CLI

**CLI Interface:**
```bash
gemini -p "<prompt>" \
  --model <model> \
  --output-format json
```

**Features:**
- Prompt flag for non-interactive use
- Model selection (gemini-2.5-pro, etc.)
- JSON output support

**Implementation Notes:**
- Similar structure to Claude
- Parse JSON or text output

### Mistral Vibe

**CLI Interface:**
```bash
echo "<prompt>" | vibe --model <model>
# or
vibe --message "<prompt>" --model <model>
```

**Features:**
- Pipe-based input
- Model selection
- Text output

**Implementation Notes:**
- Use stdin for prompts
- Parse text output
- Handle streaming if needed

### Aider

**CLI Interface:**
```bash
aider --message "<prompt>" \
  --model <model> \
  --no-auto-commits \
  --yes \
  <files>
```

**Features:**
- Message flag for single prompts
- File targeting
- Git integration
- No-auto-commits mode for controlled operation

**Implementation Notes:**
- Use `--yes` for non-interactive approval
- Use `--no-auto-commits` for manual git control
- Can target specific files
- Parse text output for changes

## YAML Prompt System

### Prompt File Specification

```yaml
# prompts/tasks/readme.yaml
name: readme
description: Generate a README.md file for a project

# Default settings for this prompt
defaults:
  model: sonnet                  # Default model (agent-specific aliases)
  timeout: 300                   # Seconds
  tools:                         # Tools to allow (agent-dependent)
    - Read
    - Glob
    - Grep
    - Write

# Agent-specific model mappings
models:
  claude: sonnet                 # Claude: sonnet, opus, haiku
  codex: o4-mini                 # Codex: o4-mini, o3
  gemini: gemini-2.5-pro         # Gemini models
  vibe: mistral-large            # Mistral models
  aider: sonnet                  # Aider uses various backends

# System prompt (optional, not all agents support)
system: |
  You are a technical documentation expert.
  Generate clear, accurate README files based on actual project content.
  Focus on practical usage examples and clear explanations.

# Main prompt template (supports {variables})
prompt: |
  Analyze this project and generate a comprehensive README.md file.

  Include:
  - Project title and description
  - Installation instructions
  - Usage examples
  - API documentation (if applicable)
  - License information

  Write the README.md file to the project root.
  {additional_instructions}

# Variables with defaults
variables:
  additional_instructions: ""

# Output handling
output:
  type: file                     # file, stdout, json
  path: README.md                # Expected output file (for type: file)

# Validation (optional)
validate:
  min_length: 100                # Minimum output length
  contains:                      # Must contain these strings
    - "# "                       # Has a heading
    - "## "                      # Has subheadings
```

### Prompt Directory Structure

```
prompts/
├── default.yaml                 # Global defaults
├── agents/                      # Agent-specific overrides
│   ├── claude.yaml
│   ├── codex.yaml
│   ├── gemini.yaml
│   ├── vibe.yaml
│   └── aider.yaml
└── tasks/                       # Task-specific prompts
    ├── readme.yaml              # Generate README
    ├── usage.yaml               # Generate usage docs
    ├── review.yaml              # Code review
    ├── refactor.yaml            # Refactoring
    ├── explain.yaml             # Explain code
    ├── test.yaml                # Generate tests
    ├── fix.yaml                 # Fix bugs
    └── custom/                  # User-defined prompts
        └── ...
```

### Global Defaults (default.yaml)

```yaml
# prompts/default.yaml
defaults:
  timeout: 180
  max_retries: 3
  rate_limit: 10                 # Requests per minute

# Default agent preference order
agent_priority:
  - claude
  - gemini
  - codex
  - aider
  - vibe

# Model tier mappings (fast, balanced, powerful)
model_tiers:
  fast:
    claude: haiku
    codex: o4-mini
    gemini: gemini-2.0-flash
    vibe: mistral-small
    aider: haiku
  balanced:
    claude: sonnet
    codex: o4-mini
    gemini: gemini-2.5-pro
    vibe: mistral-large
    aider: sonnet
  powerful:
    claude: opus
    codex: o3
    gemini: gemini-2.5-pro
    vibe: mistral-large
    aider: opus
```

### Agent-Specific Config (agents/claude.yaml)

```yaml
# prompts/agents/claude.yaml
name: claude
cli_command: claude
description: Anthropic Claude Code CLI

defaults:
  model: sonnet
  timeout: 300
  output_format: json

# Model aliases
models:
  haiku: claude-haiku-4-20250414
  sonnet: claude-sonnet-4-20250514
  opus: claude-opus-4-20250514

# Available tools
tools:
  - Read
  - Write
  - Edit
  - Glob
  - Grep
  - Bash
  - Task
  - WebFetch
  - WebSearch

# CLI argument mappings
args:
  prompt: "-p"
  model: "--model"
  system: "--system-prompt"
  output_format: "--output-format"
  tools: "--allowed-tools"
  add_dir: "--add-dir"
```

## Basic API

### Simple Usage

```python
from robot import Robot

# Run with default agent
response = Robot.run("Explain what this code does")

# Run with specific agent
response = Robot.run("Explain this code", agent="claude")

# Run with prompt template
response = Robot.run_task("readme", working_dir="/path/to/project")

# Run with variables
response = Robot.run_task(
    "readme",
    working_dir="/path/to/project",
    variables={"additional_instructions": "Focus on the API"}
)
```

### Advanced Usage

```python
from robot import Robot, AgentConfig

# Configure agent
config = AgentConfig(
    model="opus",
    timeout=600,
    tools=["Read", "Glob", "Grep"],
    system_prompt="You are a code reviewer."
)

# Get configured agent
agent = Robot.get("claude", config=config)

# Run with full control
response = agent.run(
    prompt="Review this code for security issues",
    working_dir=Path("/path/to/project"),
    on_progress=lambda msg: print(msg),
    on_retry=lambda n, err: print(f"Retry {n}: {err}")
)

if response.success:
    print(response.content)
else:
    print(f"Error: {response.error}")
```

### Prompt Loading

```python
from robot.prompts import PromptLoader

loader = PromptLoader()

# Load task prompt
prompt = loader.load("tasks/readme")

# Render with variables
rendered = prompt.render(
    agent="claude",
    variables={"additional_instructions": "Use markdown tables"}
)

# Get agent-specific settings
settings = prompt.get_settings("claude")
# => {"model": "sonnet", "timeout": 300, "tools": [...]}
```

## Implementation Phases

### Phase 1: Core Infrastructure
- [ ] Base agent class and response dataclass
- [ ] YAML prompt loader with variable substitution
- [ ] Agent registry and factory
- [ ] Configuration with dotenv

### Phase 2: Claude Code Agent
- [ ] Port and adapt code from code_hub
- [ ] Full tool support
- [ ] JSON output parsing
- [ ] Rate limiting and retries

### Phase 3: Additional Agents
- [ ] OpenAI Codex wrapper
- [ ] Gemini CLI wrapper
- [ ] Mistral Vibe wrapper
- [ ] Aider wrapper

### Phase 4: Advanced Features
- [ ] Streaming output support
- [ ] Progress callbacks
- [ ] Cost tracking
- [ ] Token counting
- [ ] Fallback chains (try agent A, fall back to B)

### Phase 5: CLI and Utilities
- [ ] `robot` CLI for direct usage
- [ ] `robot list` - show available agents
- [ ] `robot run <task>` - run a task
- [ ] `robot check` - verify agent installations

## Dependencies

```
pyyaml>=6.0
python-dotenv>=1.0.0
```

## Environment Variables

```bash
# Agent binaries (optional, defaults to PATH lookup)
ROBOT_CLAUDE_PATH=claude
ROBOT_CODEX_PATH=codex
ROBOT_GEMINI_PATH=gemini
ROBOT_VIBE_PATH=vibe
ROBOT_AIDER_PATH=aider

# Defaults
ROBOT_DEFAULT_AGENT=claude
ROBOT_DEFAULT_TIMEOUT=180
ROBOT_PROMPTS_DIR=~/.robot/prompts

# Rate limits
ROBOT_RATE_LIMIT=10

# API keys (some agents need these)
OPENAI_API_KEY=...
GOOGLE_API_KEY=...
MISTRAL_API_KEY=...
ANTHROPIC_API_KEY=...
```

## Notes

- Each agent has different capabilities; the wrapper should gracefully handle unsupported features
- Some agents modify files directly, others return diffs - normalize the output
- Aider has strong git integration; may want to leverage or disable it
- Consider adding support for running agents in Docker for isolation
- Token/cost tracking requires parsing agent-specific output formats
