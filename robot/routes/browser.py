"""
Code browser API routes.

Provides endpoints for browsing project directories and viewing file contents
with syntax highlighting support.
"""

import os
from pathlib import Path
from typing import Optional

from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel

router = APIRouter(prefix="/api/browser", tags=["browser"])

# Language detection mapping
EXTENSION_LANGUAGE_MAP = {
    ".py": "python",
    ".js": "javascript",
    ".ts": "typescript",
    ".jsx": "javascript",
    ".tsx": "typescript",
    ".html": "html",
    ".htm": "html",
    ".css": "css",
    ".scss": "scss",
    ".sass": "sass",
    ".less": "less",
    ".json": "json",
    ".yaml": "yaml",
    ".yml": "yaml",
    ".xml": "xml",
    ".md": "markdown",
    ".markdown": "markdown",
    ".sh": "bash",
    ".bash": "bash",
    ".zsh": "bash",
    ".fish": "fish",
    ".sql": "sql",
    ".go": "go",
    ".rs": "rust",
    ".rb": "ruby",
    ".php": "php",
    ".java": "java",
    ".kt": "kotlin",
    ".kts": "kotlin",
    ".swift": "swift",
    ".c": "c",
    ".h": "c",
    ".cpp": "cpp",
    ".cc": "cpp",
    ".cxx": "cpp",
    ".hpp": "cpp",
    ".cs": "csharp",
    ".r": "r",
    ".R": "r",
    ".lua": "lua",
    ".pl": "perl",
    ".pm": "perl",
    ".ex": "elixir",
    ".exs": "elixir",
    ".erl": "erlang",
    ".hrl": "erlang",
    ".clj": "clojure",
    ".cljs": "clojure",
    ".scala": "scala",
    ".hs": "haskell",
    ".ml": "ocaml",
    ".mli": "ocaml",
    ".vim": "vim",
    ".dockerfile": "dockerfile",
    ".toml": "toml",
    ".ini": "ini",
    ".cfg": "ini",
    ".conf": "ini",
    ".env": "bash",
    ".gitignore": "gitignore",
    ".dockerignore": "gitignore",
    ".editorconfig": "ini",
    ".vue": "vue",
    ".svelte": "svelte",
}

# Files/directories to hide
HIDDEN_PATTERNS = {
    "__pycache__",
    ".git",
    ".svn",
    ".hg",
    "node_modules",
    ".venv",
    "venv",
    ".env",
    ".mypy_cache",
    ".pytest_cache",
    ".tox",
    ".nox",
    ".coverage",
    ".eggs",
    "*.egg-info",
    ".DS_Store",
    "Thumbs.db",
    ".idea",
    ".vscode",
}


class BrowserItem(BaseModel):
    """An item in the directory listing."""
    name: str
    path: str
    is_dir: bool
    size: Optional[int] = None
    extension: Optional[str] = None


class FileContent(BaseModel):
    """File content response."""
    content: str
    path: str
    language: str
    size: int
    name: str


def should_hide(name: str) -> bool:
    """Check if a file/directory should be hidden."""
    if name.startswith("."):
        return True
    return name in HIDDEN_PATTERNS


def detect_language(path: Path) -> str:
    """Detect programming language from file extension."""
    # Special case for Dockerfile
    if path.name.lower() == "dockerfile":
        return "dockerfile"
    if path.name.lower() == "makefile":
        return "makefile"

    ext = path.suffix.lower()
    return EXTENSION_LANGUAGE_MAP.get(ext, "plaintext")


def get_file_size(path: Path) -> Optional[int]:
    """Get file size, returning None for directories."""
    try:
        if path.is_file():
            return path.stat().st_size
    except (OSError, PermissionError):
        pass
    return None


@router.get("", response_model=list[BrowserItem])
async def list_directory(path: Optional[str] = None):
    """
    List contents of a directory.

    Args:
        path: Directory path to list. Defaults to ~/Code.

    Returns:
        List of files and directories with metadata.
    """
    if path:
        base_path = Path(path).expanduser()
    else:
        base_path = Path.home() / "Code"

    if not base_path.exists():
        raise HTTPException(status_code=404, detail="Directory not found")

    if not base_path.is_dir():
        raise HTTPException(status_code=400, detail="Path is not a directory")

    items = []
    try:
        for item in sorted(base_path.iterdir(), key=lambda x: (not x.is_dir(), x.name.lower())):
            if should_hide(item.name):
                continue

            items.append(BrowserItem(
                name=item.name,
                path=str(item),
                is_dir=item.is_dir(),
                size=get_file_size(item),
                extension=item.suffix.lstrip(".") if item.is_file() and item.suffix else None
            ))
    except PermissionError:
        raise HTTPException(status_code=403, detail="Permission denied")

    return items


@router.get("/file", response_model=FileContent)
async def get_file(file_path: str):
    """
    Get file content with language detection.

    Args:
        file_path: Path to the file to read.

    Returns:
        File content with language and metadata.
    """
    path = Path(file_path).expanduser()

    if not path.exists():
        raise HTTPException(status_code=404, detail="File not found")

    if not path.is_file():
        raise HTTPException(status_code=400, detail="Path is not a file")

    # Check file size - limit to 1MB
    size = path.stat().st_size
    if size > 1024 * 1024:
        raise HTTPException(status_code=400, detail="File too large (max 1MB)")

    try:
        content = path.read_text(encoding="utf-8", errors="replace")
    except PermissionError:
        raise HTTPException(status_code=403, detail="Permission denied")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to read file: {e}")

    return FileContent(
        content=content,
        path=str(path),
        language=detect_language(path),
        size=size,
        name=path.name
    )
