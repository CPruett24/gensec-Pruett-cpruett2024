"""Portable STDIO configurations for the Homework 4 MCP servers."""

import os
from pathlib import Path
import sys

from mcp import StdioServerParameters

PROJECT_DIR = Path(__file__).resolve().parent


def repository_path() -> Path:
    """Resolve HW4_REPOSITORY or the course repository above homeworks/Homework4.

    Relative overrides are interpreted relative to this project, not the caller.
    """
    configured = os.environ.get("HW4_REPOSITORY")
    path = Path(configured).expanduser() if configured else PROJECT_DIR.parents[1]
    if not path.is_absolute():
        path = PROJECT_DIR / path
    path = path.resolve()
    if not path.is_dir() or not (path / ".git").exists():
        raise ValueError("HW4_REPOSITORY must identify a Git repository root.")
    return path


def custom_server_parameters() -> StdioServerParameters:
    """Launch the custom server using the current uv project interpreter."""
    return StdioServerParameters(
        command=sys.executable,
        args=[str(PROJECT_DIR / "mcp-server.py")],
        cwd=str(PROJECT_DIR),
    )


def git_server_parameters() -> StdioServerParameters:
    """Launch the installed published Git server over local STDIO."""
    return StdioServerParameters(
        command=sys.executable,
        args=["-m", "mcp_server_git", "--repository", str(repository_path())],
        cwd=str(PROJECT_DIR),
        env={**os.environ, "GIT_OPTIONAL_LOCKS": "0"},
    )
