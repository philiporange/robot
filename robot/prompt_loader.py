"""
YAML-based prompt loading and templating system.

Loads prompt configurations from YAML files, supports variable substitution,
and provides agent-specific settings for each prompt template.
"""

import logging
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional, Any

import yaml

from robot.config import settings

logger = logging.getLogger(__name__)


@dataclass
class PromptConfig:
    """Parsed prompt configuration from YAML."""

    name: str
    description: str = ""
    prompt: str = ""
    system: str = ""
    defaults: dict[str, Any] = field(default_factory=dict)
    models: dict[str, str] = field(default_factory=dict)
    variables: dict[str, str] = field(default_factory=dict)
    output: dict[str, Any] = field(default_factory=dict)
    validate: dict[str, Any] = field(default_factory=dict)

    def render(
        self,
        agent: Optional[str] = None,
        variables: Optional[dict[str, str]] = None,
    ) -> str:
        """
        Render the prompt with variable substitution.

        Args:
            agent: Agent name for model selection
            variables: Variables to substitute in template

        Returns:
            Rendered prompt string
        """
        # Merge default variables with provided ones
        all_vars = {**self.variables}
        if variables:
            all_vars.update(variables)

        # Simple {variable} substitution
        rendered = self.prompt
        for key, value in all_vars.items():
            rendered = rendered.replace(f"{{{key}}}", str(value))

        return rendered

    def get_model(self, agent: str) -> Optional[str]:
        """Get the model for a specific agent."""
        return self.models.get(agent)

    def get_settings(self, agent: str) -> dict[str, Any]:
        """Get all settings for a specific agent."""
        result = dict(self.defaults)
        if agent in self.models:
            result["model"] = self.models[agent]
        return result


class PromptLoader:
    """Load and manage prompt configurations from YAML files."""

    def __init__(self, prompts_dir: Optional[Path] = None):
        self.prompts_dir = prompts_dir or settings.prompts_dir
        self._cache: dict[str, PromptConfig] = {}
        self._defaults: Optional[dict] = None

    def _get_search_paths(self) -> list[Path]:
        """Get directories to search for prompts."""
        paths = []

        # User prompts directory
        if self.prompts_dir.exists():
            paths.append(self.prompts_dir)

        # Package prompts directory
        package_prompts = Path(__file__).parent / "prompts"
        if package_prompts.exists():
            paths.append(package_prompts)

        return paths

    def _load_yaml(self, path: Path) -> dict:
        """Load a YAML file."""
        try:
            with open(path) as f:
                return yaml.safe_load(f) or {}
        except Exception as e:
            logger.error(f"Failed to load {path}: {e}")
            return {}

    def _load_defaults(self) -> dict:
        """Load global defaults from default.yaml."""
        if self._defaults is not None:
            return self._defaults

        self._defaults = {}
        for search_path in self._get_search_paths():
            default_file = search_path / "default.yaml"
            if default_file.exists():
                self._defaults = self._load_yaml(default_file)
                break

        return self._defaults

    def load(self, name: str) -> PromptConfig:
        """
        Load a prompt configuration by name.

        Args:
            name: Prompt name (e.g., "readme", "tasks/review")

        Returns:
            PromptConfig instance
        """
        # Check cache
        if name in self._cache:
            return self._cache[name]

        # Search for the file
        for search_path in self._get_search_paths():
            # Try direct path
            yaml_path = search_path / f"{name}.yaml"
            if yaml_path.exists():
                data = self._load_yaml(yaml_path)
                break

            # Try with tasks/ prefix
            yaml_path = search_path / "tasks" / f"{name}.yaml"
            if yaml_path.exists():
                data = self._load_yaml(yaml_path)
                break
        else:
            logger.warning(f"Prompt not found: {name}")
            data = {"name": name, "prompt": ""}

        # Merge with defaults
        defaults = self._load_defaults()
        merged_defaults = {**defaults.get("defaults", {}), **data.get("defaults", {})}

        config = PromptConfig(
            name=data.get("name", name),
            description=data.get("description", ""),
            prompt=data.get("prompt", ""),
            system=data.get("system", ""),
            defaults=merged_defaults,
            models=data.get("models", {}),
            variables=data.get("variables", {}),
            output=data.get("output", {}),
            validate=data.get("validate", {}),
        )

        self._cache[name] = config
        return config

    def list_prompts(self) -> list[str]:
        """List all available prompt names."""
        prompts = set()

        for search_path in self._get_search_paths():
            if not search_path.exists():
                continue

            # Find all yaml files
            for yaml_file in search_path.rglob("*.yaml"):
                if yaml_file.name == "default.yaml":
                    continue
                # Get relative path without extension
                rel_path = yaml_file.relative_to(search_path)
                name = str(rel_path.with_suffix(""))
                prompts.add(name)

        return sorted(prompts)

    def reload(self) -> None:
        """Clear cache and reload all prompts."""
        self._cache.clear()
        self._defaults = None


# Global loader instance
_loader: Optional[PromptLoader] = None


def get_loader() -> PromptLoader:
    """Get the global prompt loader."""
    global _loader
    if _loader is None:
        _loader = PromptLoader()
    return _loader


def load_prompt(name: str) -> PromptConfig:
    """Convenience function to load a prompt."""
    return get_loader().load(name)
