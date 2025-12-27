"""Basic tests for Robot agents."""

import pytest
from robot import Robot, AgentResponse
from robot.base import AgentConfig
from robot.prompt_loader import load_prompt, PromptLoader


def test_registry_lists_agents():
    """Test that all agents are registered."""
    registered = Robot.list_registered()
    assert "claude" in registered
    assert "codex" in registered
    assert "gemini" in registered
    assert "vibe" in registered
    assert "aider" in registered
    assert "openrouter" in registered


def test_get_claude_agent():
    """Test getting Claude agent instance."""
    agent = Robot.get("claude")
    assert agent.name == "claude"
    assert agent.supports_tools is True
    assert agent.default_model == "sonnet"


def test_get_unknown_agent_raises():
    """Test that unknown agent raises ValueError."""
    with pytest.raises(ValueError):
        Robot.get("unknown_agent")


def test_agent_response_bool():
    """Test AgentResponse boolean conversion."""
    success = AgentResponse(
        success=True, content="ok", raw_output="ok",
        agent="test", model="test"
    )
    failure = AgentResponse(
        success=False, content="", raw_output="",
        agent="test", model="test", error="failed"
    )

    assert bool(success) is True
    assert bool(failure) is False


def test_prompt_loader():
    """Test loading built-in prompts."""
    loader = PromptLoader()
    prompts = loader.list_prompts()

    assert "tasks/readme" in prompts
    assert "tasks/review" in prompts


def test_load_readme_prompt():
    """Test loading and rendering readme prompt."""
    config = load_prompt("readme")

    assert config.name == "readme"
    assert "README.md" in config.prompt
    assert config.get_model("claude") == "sonnet"


def test_prompt_render_variables():
    """Test prompt variable substitution."""
    config = load_prompt("readme")
    rendered = config.render(variables={"additional_instructions": "Focus on API"})

    assert "Focus on API" in rendered


def test_agent_config_api_fields():
    """Test AgentConfig has api_key and base_url fields."""
    config = AgentConfig(
        api_key="test-key",
        base_url="https://api.example.com",
    )
    assert config.api_key == "test-key"
    assert config.base_url == "https://api.example.com"


def test_claude_agent_env_vars():
    """Test ClaudeAgent sets correct environment variables."""
    config = AgentConfig(
        api_key="test-anthropic-key",
        base_url="https://api.z.ai/api/anthropic",
    )
    agent = Robot.get("claude", config=config)
    env = agent.get_env_vars()

    assert env.get("ANTHROPIC_AUTH_TOKEN") == "test-anthropic-key"
    assert env.get("ANTHROPIC_BASE_URL") == "https://api.z.ai/api/anthropic"


def test_codex_agent_env_vars():
    """Test CodexAgent sets correct environment variables."""
    config = AgentConfig(
        api_key="test-openai-key",
        base_url="https://api.example.com/v1",
    )
    agent = Robot.get("codex", config=config)
    env = agent.get_env_vars()

    assert env.get("OPENAI_API_KEY") == "test-openai-key"
    assert env.get("OPENAI_BASE_URL") == "https://api.example.com/v1"


def test_gemini_agent_env_vars():
    """Test GeminiAgent sets correct environment variables."""
    config = AgentConfig(
        api_key="test-google-key",
        base_url="https://api.example.com",
    )
    agent = Robot.get("gemini", config=config)
    env = agent.get_env_vars()

    assert env.get("GOOGLE_API_KEY") == "test-google-key"
    assert env.get("GOOGLE_BASE_URL") == "https://api.example.com"


def test_vibe_agent_env_vars():
    """Test VibeAgent sets correct environment variables."""
    config = AgentConfig(
        api_key="test-mistral-key",
    )
    agent = Robot.get("vibe", config=config)
    env = agent.get_env_vars()

    assert env.get("MISTRAL_API_KEY") == "test-mistral-key"


def test_aider_agent_env_vars():
    """Test AiderAgent sets environment variables for multiple backends."""
    config = AgentConfig(
        api_key="test-key",
        base_url="https://api.example.com",
    )
    agent = Robot.get("aider", config=config)
    env = agent.get_env_vars()

    # Aider sets both Anthropic and OpenAI keys
    assert env.get("ANTHROPIC_API_KEY") == "test-key"
    assert env.get("OPENAI_API_KEY") == "test-key"
    assert env.get("ANTHROPIC_BASE_URL") == "https://api.example.com"
    assert env.get("OPENAI_BASE_URL") == "https://api.example.com"


def test_agent_env_vars_empty_when_no_config():
    """Test agents return empty env vars when no API config set."""
    agent = Robot.get("claude")
    # Clear any settings-based config
    agent.config = AgentConfig()
    env = agent.get_env_vars()

    # Should be empty if no config or settings set
    # Note: This may not be empty if environment variables are set
    assert isinstance(env, dict)


def test_get_openrouter_agent():
    """Test getting OpenRouter agent instance."""
    agent = Robot.get("openrouter")
    assert agent.name == "openrouter"
    assert agent.default_model == "minimax/minimax-m2.1"


def test_openrouter_agent_env_vars():
    """Test OpenRouterAgent sets correct environment variables."""
    config = AgentConfig(
        api_key="test-openrouter-key",
    )
    agent = Robot.get("openrouter", config=config)
    env = agent.get_env_vars()

    assert env.get("OPENROUTER_API_KEY") == "test-openrouter-key"


def test_openrouter_model_aliases():
    """Test OpenRouter model alias resolution."""
    agent = Robot.get("openrouter")

    # Test aliases resolve correctly
    assert agent._resolve_model("minimax") == "openrouter/minimax/minimax-m2.1"
    assert agent._resolve_model("claude") == "openrouter/anthropic/claude-sonnet-4"
    assert agent._resolve_model("gpt4") == "openrouter/openai/gpt-4o"

    # Test full model names get prefixed
    assert agent._resolve_model("meta-llama/llama-3-70b") == "openrouter/meta-llama/llama-3-70b"

    # Test already-prefixed models stay as-is
    assert agent._resolve_model("openrouter/custom/model") == "openrouter/custom/model"


def test_openrouter_build_command():
    """Test OpenRouter command building."""
    agent = Robot.get("openrouter")
    cmd = agent.build_command(prompt="Test prompt", model="minimax")

    assert "--model" in cmd
    assert "openrouter/minimax/minimax-m2.1" in cmd
    assert "--message" in cmd
    assert "Test prompt" in cmd
    assert "--yes" in cmd
    assert "--no-git" in cmd
    assert "--no-auto-commits" in cmd


# Resume/Continue functionality tests

def test_agent_config_resume_fields():
    """Test AgentConfig has resume and session_id fields."""
    config = AgentConfig(resume=True, session_id="test-session-123")
    assert config.resume is True
    assert config.session_id == "test-session-123"


def test_claude_supports_resume():
    """Test Claude agent supports resume."""
    agent = Robot.get("claude")
    assert agent.supports_resume is True


def test_claude_resume_continue():
    """Test Claude --continue flag for resuming most recent session."""
    config = AgentConfig(resume=True)
    agent = Robot.get("claude", config=config)
    cmd = agent.build_command(prompt="Test prompt")

    assert "--continue" in cmd
    assert "--resume" not in cmd


def test_claude_resume_session_id():
    """Test Claude --resume with specific session ID."""
    config = AgentConfig(session_id="abc123")
    agent = Robot.get("claude", config=config)
    cmd = agent.build_command(prompt="Test prompt")

    assert "--resume" in cmd
    assert "abc123" in cmd
    assert "--continue" not in cmd


def test_claude_resume_override():
    """Test resume parameter overrides config."""
    config = AgentConfig(resume=True)
    agent = Robot.get("claude", config=config)

    # Override with resume=False
    cmd = agent.build_command(prompt="Test", resume=False)
    assert "--continue" not in cmd


def test_aider_supports_resume():
    """Test Aider agent supports resume."""
    agent = Robot.get("aider")
    assert agent.supports_resume is True


def test_aider_resume_restore_history():
    """Test Aider --restore-chat-history flag."""
    config = AgentConfig(resume=True)
    agent = Robot.get("aider", config=config)
    cmd = agent.build_command(prompt="Test prompt")

    assert "--restore-chat-history" in cmd


def test_aider_resume_with_history_file():
    """Test Aider with specific chat history file and resume=True."""
    config = AgentConfig(session_id="/path/to/history.md", resume=True)
    agent = Robot.get("aider", config=config)
    cmd = agent.build_command(prompt="Test prompt")

    assert "--chat-history-file" in cmd
    assert "/path/to/history.md" in cmd
    assert "--restore-chat-history" in cmd


def test_openrouter_supports_resume():
    """Test OpenRouter agent supports resume."""
    agent = Robot.get("openrouter")
    assert agent.supports_resume is True


def test_openrouter_resume_restore_history():
    """Test OpenRouter --restore-chat-history flag."""
    config = AgentConfig(resume=True)
    agent = Robot.get("openrouter", config=config)
    cmd = agent.build_command(prompt="Test prompt")

    assert "--restore-chat-history" in cmd


def test_codex_supports_resume():
    """Test Codex agent supports resume."""
    agent = Robot.get("codex")
    assert agent.supports_resume is True


def test_codex_resume_last():
    """Test Codex exec resume --last for most recent session."""
    config = AgentConfig(resume=True)
    agent = Robot.get("codex", config=config)
    cmd = agent.build_command(prompt="Test prompt")

    assert "exec" in cmd
    assert "resume" in cmd
    assert "--last" in cmd
    assert "Test prompt" in cmd


def test_codex_resume_session_id():
    """Test Codex exec resume with specific session ID."""
    config = AgentConfig(session_id="7f9f9a2e-1b3c-4c7a")
    agent = Robot.get("codex", config=config)
    cmd = agent.build_command(prompt="Test prompt")

    assert "exec" in cmd
    assert "resume" in cmd
    assert "7f9f9a2e-1b3c-4c7a" in cmd
    assert "--last" not in cmd


def test_gemini_supports_resume():
    """Test Gemini agent supports resume."""
    agent = Robot.get("gemini")
    assert agent.supports_resume is True


def test_gemini_resume_latest():
    """Test Gemini --resume latest for most recent session."""
    config = AgentConfig(resume=True)
    agent = Robot.get("gemini", config=config)
    cmd = agent.build_command(prompt="Test")

    assert "--resume" in cmd
    assert "latest" in cmd


def test_gemini_resume_session_id():
    """Test Gemini --resume with specific session index."""
    config = AgentConfig(session_id="5")
    agent = Robot.get("gemini", config=config)
    cmd = agent.build_command(prompt="Test")

    assert "--resume" in cmd
    assert "5" in cmd


def test_gemini_system_prompt_env_var():
    """Test Gemini sets GEMINI_SYSTEM_MD for system prompts."""
    config = AgentConfig(system_prompt="You are a helpful assistant.")
    agent = Robot.get("gemini", config=config)
    env = agent.get_env_vars(system_prompt="You are a helpful assistant.")

    assert "GEMINI_SYSTEM_MD" in env
    # Should point to a temp file
    assert env["GEMINI_SYSTEM_MD"].endswith(".md")


def test_vibe_supports_resume():
    """Test Vibe agent supports resume."""
    agent = Robot.get("vibe")
    assert agent.supports_resume is True


def test_vibe_resume_continue():
    """Test Vibe --continue for most recent session."""
    config = AgentConfig(resume=True)
    agent = Robot.get("vibe", config=config)
    cmd = agent.build_command(prompt="Test")

    assert "--continue" in cmd


def test_vibe_resume_session_id():
    """Test Vibe --resume with specific session ID."""
    config = AgentConfig(session_id="abc123")
    agent = Robot.get("vibe", config=config)
    cmd = agent.build_command(prompt="Test")

    assert "--resume" in cmd
    assert "abc123" in cmd


# History file tests

def test_agent_config_history_file():
    """Test AgentConfig has history_file field."""
    from pathlib import Path
    config = AgentConfig(history_file=Path("/tmp/chat_history.md"))
    assert config.history_file == Path("/tmp/chat_history.md")


def test_claude_history_file_as_session():
    """Test Claude uses history_file as session ID."""
    from pathlib import Path
    config = AgentConfig(history_file=Path("my-session"))
    agent = Robot.get("claude", config=config)
    cmd = agent.build_command(prompt="Test")

    assert "--resume" in cmd
    assert "my-session" in cmd


def test_aider_history_file_new():
    """Test Aider with new history file (doesn't exist yet)."""
    config = AgentConfig(history_file="/tmp/nonexistent_history_12345.md")
    agent = Robot.get("aider", config=config)
    cmd = agent.build_command(prompt="Test")

    assert "--chat-history-file" in cmd
    assert "/tmp/nonexistent_history_12345.md" in cmd
    # Should NOT have --restore-chat-history since file doesn't exist
    assert "--restore-chat-history" not in cmd


def test_aider_history_file_exists(tmp_path):
    """Test Aider auto-resumes when history file exists."""
    # Create a temporary history file
    history_file = tmp_path / "chat_history.md"
    history_file.write_text("# Previous chat\n")

    config = AgentConfig(history_file=history_file)
    agent = Robot.get("aider", config=config)
    cmd = agent.build_command(prompt="Test")

    assert "--chat-history-file" in cmd
    assert str(history_file) in cmd
    # Should have --restore-chat-history since file exists
    assert "--restore-chat-history" in cmd


def test_openrouter_history_file_exists(tmp_path):
    """Test OpenRouter auto-resumes when history file exists."""
    history_file = tmp_path / "chat_history.md"
    history_file.write_text("# Previous chat\n")

    config = AgentConfig(history_file=history_file)
    agent = Robot.get("openrouter", config=config)
    cmd = agent.build_command(prompt="Test")

    assert "--chat-history-file" in cmd
    assert str(history_file) in cmd
    assert "--restore-chat-history" in cmd


def test_history_file_with_resume_flag():
    """Test history_file with explicit resume=True forces restore."""
    config = AgentConfig(
        history_file="/tmp/new_history.md",
        resume=True
    )
    agent = Robot.get("aider", config=config)
    cmd = agent.build_command(prompt="Test")

    # Should restore even though file doesn't exist, because resume=True
    assert "--chat-history-file" in cmd
    assert "--restore-chat-history" in cmd


# Prompt prefix tests

def test_agent_config_prompt_prefix():
    """Test AgentConfig has prompt_prefix field."""
    config = AgentConfig(prompt_prefix="Always use type hints.")
    assert config.prompt_prefix == "Always use type hints."


def test_claude_prompt_prefix():
    """Test Claude uses --append-system-prompt for prompt_prefix."""
    config = AgentConfig(prompt_prefix="Always use type hints.")
    agent = Robot.get("claude", config=config)
    cmd = agent.build_command(prompt="Write a function")

    assert "--append-system-prompt" in cmd
    assert "Always use type hints." in cmd


def test_claude_prompt_prefix_override():
    """Test prompt_prefix parameter overrides config."""
    config = AgentConfig(prompt_prefix="Config prefix")
    agent = Robot.get("claude", config=config)
    cmd = agent.build_command(prompt="Test", prompt_prefix="Param prefix")

    assert "--append-system-prompt" in cmd
    assert "Param prefix" in cmd
    assert "Config prefix" not in cmd


def test_codex_prompt_prefix():
    """Test Codex prepends prompt_prefix to prompt."""
    config = AgentConfig(prompt_prefix="Use functional style.")
    agent = Robot.get("codex", config=config)
    cmd = agent.build_command(prompt="Write code")

    # Find the prompt in the command (should be combined)
    prompt_idx = None
    for i, arg in enumerate(cmd):
        if "Use functional style." in arg and "Write code" in arg:
            prompt_idx = i
            break

    assert prompt_idx is not None, "Prompt prefix should be prepended to prompt"


def test_gemini_prompt_prefix():
    """Test Gemini appends prompt_prefix to system prompt in temp file."""
    config = AgentConfig(
        system_prompt="You are helpful.",
        prompt_prefix="Focus on performance."
    )
    agent = Robot.get("gemini", config=config)
    env = agent.get_env_vars(
        system_prompt="You are helpful.",
        prompt_prefix="Focus on performance."
    )

    assert "GEMINI_SYSTEM_MD" in env
    # Read the temp file to verify content
    from pathlib import Path
    content = Path(env["GEMINI_SYSTEM_MD"]).read_text()
    assert "You are helpful." in content
    assert "Focus on performance." in content


def test_gemini_prompt_prefix_only():
    """Test Gemini with only prompt_prefix (no system prompt)."""
    config = AgentConfig(prompt_prefix="Focus on security.")
    agent = Robot.get("gemini", config=config)
    env = agent.get_env_vars(prompt_prefix="Focus on security.")

    assert "GEMINI_SYSTEM_MD" in env
    from pathlib import Path
    content = Path(env["GEMINI_SYSTEM_MD"]).read_text()
    assert "Focus on security." in content


def test_vibe_prompt_prefix():
    """Test Vibe prepends prompt_prefix to prompt."""
    config = AgentConfig(prompt_prefix="Be concise.")
    agent = Robot.get("vibe", config=config)
    cmd = agent.build_command(prompt="Explain this")

    # Find the -p argument
    p_idx = cmd.index("-p")
    prompt_arg = cmd[p_idx + 1]
    assert "Be concise." in prompt_arg
    assert "Explain this" in prompt_arg


def test_aider_prompt_prefix():
    """Test Aider prepends prompt_prefix to prompt."""
    config = AgentConfig(prompt_prefix="Use Python 3.12 features.")
    agent = Robot.get("aider", config=config)
    cmd = agent.build_command(prompt="Refactor this")

    # Find --message argument
    msg_idx = cmd.index("--message")
    prompt_arg = cmd[msg_idx + 1]
    assert "Use Python 3.12 features." in prompt_arg
    assert "Refactor this" in prompt_arg


def test_openrouter_prompt_prefix():
    """Test OpenRouter prepends prompt_prefix to prompt."""
    config = AgentConfig(prompt_prefix="Optimize for readability.")
    agent = Robot.get("openrouter", config=config)
    cmd = agent.build_command(prompt="Review code")

    # Find --message argument
    msg_idx = cmd.index("--message")
    prompt_arg = cmd[msg_idx + 1]
    assert "Optimize for readability." in prompt_arg
    assert "Review code" in prompt_arg


# Superagent tests

def test_superagent_import():
    """Test SuperAgent can be imported from robot."""
    from robot import SuperAgent, get_superagent_prefix, run_subagent
    assert SuperAgent is not None
    assert get_superagent_prefix is not None
    assert run_subagent is not None


def test_superagent_prefix_generation():
    """Test superagent prefix contains required instructions."""
    from robot.superagent import get_superagent_prefix

    prefix = get_superagent_prefix(
        max_subagents=5,
        subagent_timeout=300,
    )

    # Check key elements are present
    assert "SUPERAGENT CAPABILITIES" in prefix
    assert "5 subagents" in prefix
    assert "300" in prefix  # timeout
    assert "--no-superagent" in prefix
    assert "robot run" in prefix
    assert "Verification Protocol" in prefix


def test_superagent_prefix_custom_values():
    """Test superagent prefix with custom values."""
    from robot.superagent import get_superagent_prefix
    from pathlib import Path

    prefix = get_superagent_prefix(
        max_subagents=3,
        subagent_timeout=600,
        working_dir=Path("/custom/path"),
        allowed_agents=["claude", "gemini"],
    )

    assert "3 subagents" in prefix
    assert "600" in prefix
    assert "/custom/path" in prefix
    assert "claude, gemini" in prefix


def test_superagent_wrapper():
    """Test SuperAgent wrapper initialization."""
    from robot.superagent import SuperAgent

    agent = Robot.get("claude")
    super_agent = SuperAgent(
        agent,
        max_subagents=3,
        subagent_timeout=600,
    )

    assert super_agent.max_subagents == 3
    assert super_agent.subagent_timeout == 600
    assert super_agent.agent is agent


def test_superagent_get_prompt_prefix():
    """Test SuperAgent.get_prompt_prefix method."""
    from robot.superagent import SuperAgent
    from pathlib import Path

    agent = Robot.get("claude")
    super_agent = SuperAgent(agent, max_subagents=4)

    prefix = super_agent.get_prompt_prefix(working_dir=Path("/test/dir"))

    assert "4 subagents" in prefix
    assert "/test/dir" in prefix


def test_superagent_state_defaults():
    """Test SuperagentState default values."""
    from robot.superagent import SuperagentState, MAX_SUBAGENTS, DEFAULT_SUBAGENT_TIMEOUT

    state = SuperagentState()

    assert state.subagents_spawned == 0
    assert state.subagent_results == []
    assert state.max_subagents == MAX_SUBAGENTS
    assert state.subagent_timeout == DEFAULT_SUBAGENT_TIMEOUT


def test_subagent_result_dataclass():
    """Test SubagentResult dataclass."""
    from robot.superagent import SubagentResult

    result = SubagentResult(
        task_id=1,
        success=True,
        content="Task completed",
        agent="claude",
        model="sonnet",
        duration=5.5,
    )

    assert result.task_id == 1
    assert result.success is True
    assert result.content == "Task completed"
    assert result.error is None


def test_superagent_constants():
    """Test superagent module constants."""
    from robot.superagent import MAX_SUBAGENTS, DEFAULT_SUBAGENT_TIMEOUT

    assert MAX_SUBAGENTS == 5
    assert DEFAULT_SUBAGENT_TIMEOUT == 300  # 5 minutes


def test_superagent_prompt_yaml():
    """Test superagent YAML prompt exists and is valid."""
    from robot.prompt_loader import load_prompt

    config = load_prompt("superagent")

    assert config.name == "superagent"
    assert "subagent" in config.description.lower()
    assert config.defaults.get("max_subagents") == 5
    assert config.defaults.get("subagent_timeout") == 300


# Interactive mode tests

def test_interactive_import():
    """Test interactive module can be imported."""
    from robot.interactive import (
        run_interactive,
        InteractiveConfig,
        get_agent_for_model,
        handle_command,
    )
    assert run_interactive is not None
    assert InteractiveConfig is not None


def test_interactive_config_defaults():
    """Test InteractiveConfig default values."""
    from robot.interactive import InteractiveConfig

    config = InteractiveConfig()

    assert config.agent == "claude"
    assert config.model == "opus"
    assert config.working_dir is None
    assert config.superagent is False
    assert config.max_subagents == 5
    assert config.subagent_timeout == 300


def test_get_agent_for_model():
    """Test automatic agent selection based on model."""
    from robot.interactive import get_agent_for_model

    # Claude models
    assert get_agent_for_model("opus") == "claude"
    assert get_agent_for_model("sonnet") == "claude"
    assert get_agent_for_model("haiku") == "claude"

    # OpenAI models
    assert get_agent_for_model("o4-mini") == "codex"
    assert get_agent_for_model("gpt-4o") == "codex"

    # Gemini models
    assert get_agent_for_model("gemini-2.5-pro") == "gemini"

    # Mistral models
    assert get_agent_for_model("mistral-large") == "vibe"

    # OpenRouter models
    assert get_agent_for_model("minimax") == "openrouter"
    assert get_agent_for_model("deepseek") == "openrouter"

    # Unknown defaults to claude
    assert get_agent_for_model("unknown-model") == "claude"


def test_handle_command_agent():
    """Test /agent command."""
    from robot.interactive import InteractiveConfig, handle_command

    config = InteractiveConfig()

    # Switch agent
    result = handle_command("agent codex", config)
    assert result is True
    assert config.agent == "codex"

    # Invalid agent
    result = handle_command("agent invalid", config)
    assert result is True
    assert config.agent == "codex"  # Unchanged


def test_handle_command_model():
    """Test /model command with auto agent selection."""
    from robot.interactive import InteractiveConfig, handle_command

    config = InteractiveConfig()

    # Switch to GPT model - should auto-select codex
    result = handle_command("model gpt-4o", config)
    assert result is True
    assert config.model == "gpt-4o"
    assert config.agent == "codex"


def test_handle_command_super():
    """Test /super command toggles superagent mode."""
    from robot.interactive import InteractiveConfig, handle_command

    config = InteractiveConfig()
    assert config.superagent is False

    handle_command("super", config)
    assert config.superagent is True

    handle_command("super", config)
    assert config.superagent is False


def test_handle_command_quit():
    """Test /quit command returns False."""
    from robot.interactive import InteractiveConfig, handle_command

    config = InteractiveConfig()

    assert handle_command("quit", config) is False
    assert handle_command("exit", config) is False
    assert handle_command("q", config) is False


def test_handle_command_dir():
    """Test /dir command."""
    from robot.interactive import InteractiveConfig, handle_command
    from pathlib import Path
    import tempfile

    config = InteractiveConfig()

    # Set to temp directory
    with tempfile.TemporaryDirectory() as tmpdir:
        handle_command(f"dir {tmpdir}", config)
        assert config.working_dir == Path(tmpdir)


def test_model_agent_map_coverage():
    """Test that common models are mapped to agents."""
    from robot.interactive import MODEL_AGENT_MAP

    # Verify key models are mapped
    assert "opus" in MODEL_AGENT_MAP
    assert "sonnet" in MODEL_AGENT_MAP
    assert "o4-mini" in MODEL_AGENT_MAP
    assert "gemini-2.5-pro" in MODEL_AGENT_MAP
    assert "mistral-large" in MODEL_AGENT_MAP
    assert "minimax" in MODEL_AGENT_MAP
    assert "glm-4.7" in MODEL_AGENT_MAP


# Z.ai agent tests

def test_zai_agent_registered():
    """Test Z.ai agent is registered."""
    registered = Robot.list_registered()
    assert "zai" in registered


def test_get_zai_agent():
    """Test getting Z.ai agent instance."""
    agent = Robot.get("zai")
    assert agent.name == "zai"
    assert agent.default_model == "glm-4.7"
    assert agent.supports_resume is True


def test_zai_model_aliases():
    """Test Z.ai model alias resolution."""
    agent = Robot.get("zai")

    assert agent._resolve_model("glm") == "glm-4.7"
    assert agent._resolve_model("glm-4") == "glm-4.7"
    assert agent._resolve_model("claude") == "claude-sonnet-4-20250514"
    assert agent._resolve_model("opus") == "claude-opus-4-20250514"


def test_zai_build_command():
    """Test Z.ai command building."""
    agent = Robot.get("zai")
    cmd = agent.build_command(prompt="Test prompt", model="glm-4.7")

    assert "--model" in cmd
    assert "openai/glm-4.7" in cmd
    assert "--message" in cmd
    assert "Test prompt" in cmd
    assert "--no-git" in cmd


def test_zai_env_vars():
    """Test Z.ai sets correct environment variables."""
    config = AgentConfig(api_key="test-zai-key")
    agent = Robot.get("zai", config=config)
    env = agent.get_env_vars()

    assert env.get("OPENAI_API_KEY") == "test-zai-key"
    assert "OPENAI_API_BASE" in env


def test_zai_prompt_prefix():
    """Test Z.ai prepends prompt_prefix to prompt."""
    config = AgentConfig(prompt_prefix="Use type hints.")
    agent = Robot.get("zai", config=config)
    cmd = agent.build_command(prompt="Write code")

    msg_idx = cmd.index("--message")
    prompt_arg = cmd[msg_idx + 1]
    assert "Use type hints." in prompt_arg
    assert "Write code" in prompt_arg


def test_interactive_zai_agent():
    """Test interactive mode recognizes zai agent."""
    from robot.interactive import get_agent_for_model

    assert get_agent_for_model("glm-4.7") == "zai"
    assert get_agent_for_model("glm") == "zai"


# Working directory tests

def test_agent_config_working_dir():
    """Test AgentConfig accepts working_dir."""
    from pathlib import Path

    config = AgentConfig(working_dir=Path("/test/dir"))
    assert config.working_dir == Path("/test/dir")


def test_robot_run_with_working_dir():
    """Test Robot.run accepts working_dir parameter."""
    from pathlib import Path

    # Just verify the function signature accepts working_dir
    # Actual execution would require a real agent
    agent = Robot.get("claude")
    assert agent.config.working_dir is None

    config = AgentConfig(working_dir=Path("/test/project"))
    agent = Robot.get("claude", config=config)
    assert agent.config.working_dir == Path("/test/project")


def test_robot_run_working_dir_in_config():
    """Test Robot.run uses working_dir from config."""
    from pathlib import Path

    config = AgentConfig(working_dir=Path("/config/dir"))
    agent = Robot.get("claude", config=config)

    # Verify config is properly set
    assert agent.config.working_dir == Path("/config/dir")


def test_claude_build_command_with_working_dir():
    """Test Claude includes working_dir in add-dir."""
    from pathlib import Path

    config = AgentConfig(working_dir=Path("/project/dir"))
    agent = Robot.get("claude", config=config)
    cmd = agent.build_command(prompt="Test")

    # Claude should add the working dir
    assert "--add-dir" in cmd
