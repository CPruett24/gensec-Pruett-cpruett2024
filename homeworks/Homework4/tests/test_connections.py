"""Integration tests for both real MCP processes and portable configuration."""

import asyncio
import importlib.util
from pathlib import Path
import subprocess

from mcp import ClientSession
from mcp.client.stdio import stdio_client
import pytest

PROJECT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("mcp_connections", PROJECT / "mcp_connections.py")
connections = importlib.util.module_from_spec(spec)
spec.loader.exec_module(connections)


def git_read(repo: Path, *args: str) -> bytes:
    """Run fixed read-only Git queries without refreshing the index on disk."""
    return subprocess.check_output(["git", "--no-optional-locks", "-C", str(repo), *args])


def test_repository_configuration(monkeypatch):
    """Resolve the default and relative override independently of the caller cwd."""
    monkeypatch.delenv("HW4_REPOSITORY", raising=False)
    expected = PROJECT.parents[1]
    assert connections.repository_path() == expected
    monkeypatch.setenv("HW4_REPOSITORY", "../..")
    assert connections.repository_path() == expected
    monkeypatch.setenv("HW4_REPOSITORY", str(expected))
    assert connections.repository_path() == expected
    monkeypatch.setenv("HW4_REPOSITORY", "sample_logs")
    with pytest.raises(ValueError, match="repository root"):
        connections.repository_path()


def test_both_stdio_servers():
    """Discover both servers, call harmless tools, and verify Git state is unchanged."""
    repo = connections.repository_path()
    before = (
        git_read(repo, "rev-parse", "HEAD"),
        git_read(repo, "status", "--porcelain=v1", "--untracked-files=all"),
        git_read(repo, "diff", "--binary"),
        git_read(repo, "diff", "--cached", "--binary"),
        git_read(repo, "show-ref"),
    )

    async def exercise():
        """Keep both initialized sessions alive together and close via context managers."""
        async with asyncio.timeout(45):
            async with stdio_client(connections.custom_server_parameters()) as (cr, cw):
                async with ClientSession(cr, cw) as custom:
                    await custom.initialize()
                    async with stdio_client(connections.git_server_parameters()) as (gr, gw):
                        async with ClientSession(gr, gw) as git:
                            await git.initialize()
                            custom_names = sorted(tool.name for tool in (await custom.list_tools()).tools)
                            git_names = sorted(tool.name for tool in (await git.list_tools()).tools)
                            print("Custom tools:", ", ".join(custom_names))
                            print("Git tools:", ", ".join(git_names))
                            assert set(custom_names) == {
                                "list_log_files", "read_security_log", "analyze_failed_logins"
                            }
                            assert {"git_status", "git_log"} <= set(git_names)
                            sample = await custom.call_tool("list_log_files", {})
                            assert not sample.isError
                            assert "auth.log" in "".join(item.text for item in sample.content)
                            status = await git.call_tool("git_status", {"repo_path": str(repo)})
                            assert not status.isError
                            assert "On branch" in "".join(item.text for item in status.content)
                            history = await git.call_tool("git_log", {"repo_path": str(repo), "max_count": 1})
                            assert not history.isError
                            assert before[0].decode().strip() in "".join(item.text for item in history.content)

    asyncio.run(exercise())
    after = (
        git_read(repo, "rev-parse", "HEAD"),
        git_read(repo, "status", "--porcelain=v1", "--untracked-files=all"),
        git_read(repo, "diff", "--binary"),
        git_read(repo, "diff", "--cached", "--binary"),
        git_read(repo, "show-ref"),
    )
    assert after == before
