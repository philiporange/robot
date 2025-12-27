"""
Unified response dataclass for all coding agents.

Normalizes output from different CLI tools into a consistent format
regardless of whether the underlying agent returns JSON, text, or
modifies files directly.
"""

from dataclasses import dataclass, field
from typing import Optional


@dataclass
class AgentResponse:
    """Unified response from any coding agent."""

    success: bool
    content: str
    raw_output: str
    agent: str
    model: str
    duration: float = 0.0
    error: Optional[str] = None
    files_modified: list[str] = field(default_factory=list)
    tokens_used: Optional[int] = None
    cost: Optional[float] = None

    def __bool__(self) -> bool:
        """Allow using response in boolean context."""
        return self.success

    def __str__(self) -> str:
        if self.success:
            return self.content
        return f"Error: {self.error}"
