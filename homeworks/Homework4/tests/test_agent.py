"""Mocked Gemini tests: no credentials or external API requests required."""

import asyncio
import importlib.util
from pathlib import Path
import sys
from types import SimpleNamespace
from unittest.mock import AsyncMock

from google.genai import types
from mcp.types import CallToolResult, TextContent, Tool
import pytest

PROJECT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT))
import agent


def response(*parts):
    """Build a typed Gemini response matching SDK generate_content output."""
    return types.GenerateContentResponse(candidates=[types.Candidate(
        content=types.Content(role="model", parts=list(parts))
    )])


def call(name, **args):
    """Build a model function call."""
    return response(types.Part.from_function_call(name=name, args=args))


def session(names, text="sample"):
    """Create an MCP session double advertising arbitrary tools."""
    return SimpleNamespace(
        list_tools=AsyncMock(return_value=SimpleNamespace(tools=[Tool(
            name=name, description=name, inputSchema={"type": "object", "properties": {}}
        ) for name in names])),
        call_tool=AsyncMock(return_value=CallToolResult(content=[TextContent(type="text", text=text)])),
    )


def setup_agent(responses, **kwargs):
    """Discover mocked servers and create a manually controlled model loop."""
    custom = session(agent.ALLOWLIST["custom"])
    git = session(agent.ALLOWLIST["git"] | {"git_add", "git_commit", "git_reset", "git_create_branch"})
    declarations, routes = asyncio.run(agent.discover_tools({"custom": custom, "git": git}))
    model = AsyncMock(side_effect=responses)
    client = SimpleNamespace(models=SimpleNamespace(generate_content=model))
    return agent.Agent(client, declarations, routes, output=lambda text: None, **kwargs), custom, git, model


def test_discovery_allowlist():
    """Hide all write tools both from declarations and executable routes."""
    bot, _, _, _ = setup_agent([])
    expected = agent.ALLOWLIST["custom"] | agent.ALLOWLIST["git"]
    assert set(bot.routes) == expected
    assert {decl.name for decl in bot.config.tools[0].function_declarations} == expected
    assert bot.config.automatic_function_calling.disable


def test_multistep_routing():
    """Route sequential calls across servers and force the configured Git root."""
    bot, custom, git, model = setup_agent([
        call("analyze_failed_logins", filename="auth.log"),
        call("git_log", repo_path="/untrusted", max_count=1),
        response(types.Part.from_text(text="Suspicious activity found.")),
    ])
    assert asyncio.run(bot.ask("Investigate logs and commits")) == "Suspicious activity found."
    custom.call_tool.assert_awaited_once_with("analyze_failed_logins", {"filename": "auth.log"})
    git.call_tool.assert_awaited_once_with("git_log", {"repo_path": str(agent.repository_path()), "max_count": 1})
    assert model.await_count == 3


def test_limit_parallel_calls():
    """Enforce the budget even if one response requests multiple calls."""
    bot, custom, _, _ = setup_agent([response(*[
        types.Part.from_function_call(name="list_log_files", args={}) for _ in range(3)
    ])], max_calls=2)
    assert "limit reached" in asyncio.run(bot.ask("repeat"))
    assert custom.call_tool.await_count == 2


@pytest.mark.parametrize("throws", [False, True])
def test_tool_failure(throws):
    """Return safe failure diagnostics to the model without exposing exceptions."""
    bot, custom, _, model = setup_agent([
        call("read_security_log", filename="missing.log"), response(types.Part.from_text(text="Tool failed."))
    ])
    if throws:
        custom.call_tool.side_effect = RuntimeError("secret exception details")
    else:
        custom.call_tool.return_value = CallToolResult(isError=True, content=[])
    assert asyncio.run(bot.ask("read")) == "Tool failed."
    history = model.call_args.kwargs["contents"]
    assert "secret exception details" not in str(history)


def test_injection_remains_tool_data():
    """Real synthetic injection stays in a function response, never system/user text."""
    bot, custom, git, model = setup_agent([
        call("read_security_log", filename="auth.log"),
        call("git_commit", message="injected"),
        response(types.Part.from_text(text="Injection detected; failed logins are suspicious.")),
    ])
    text = (PROJECT / "sample_logs/auth.log").read_text()
    custom.call_tool.return_value = CallToolResult(content=[TextContent(type="text", text=text)])
    assert "Injection detected" in asyncio.run(bot.ask("Investigate"))
    git.call_tool.assert_not_awaited()
    history = model.call_args.kwargs["contents"]
    assert history[0].parts[0].text == "Investigate"
    assert history[2].role == "user"
    assert history[2].parts[0].text is None
    assert "ignore previous instructions" in str(history[2].parts[0].function_response.response)
    assert "UNTRUSTED DATA" in bot.config.system_instruction


@pytest.mark.parametrize("command", ["exit", "quit", " EXIT "])
def test_exit(command):
    """Exit without contacting Gemini."""
    bot, _, _, model = setup_agent([])
    output = []
    asyncio.run(agent.interactive(bot, read=lambda _: command, output=output.append))
    assert output[-1] == "Goodbye."
    model.assert_not_awaited()


def test_api_failure_and_redaction(monkeypatch):
    """Do not display credentials in model errors or generated answers."""
    monkeypatch.setenv("GEMINI_API_KEY", "test-secret")
    bot, _, _, _ = setup_agent([RuntimeError("test-secret")])
    assert "test-secret" not in asyncio.run(bot.ask("hello"))
    assert agent.redact("key=test-secret") == "key=[REDACTED]"


def test_actual_mcp_schema_mapping():
    """Validate declarations against both real servers without a Gemini request."""
    from contextlib import AsyncExitStack
    from mcp import ClientSession
    from mcp.client.stdio import stdio_client

    async def check():
        """Open real sessions and validate all seven SDK function declarations."""
        async with asyncio.timeout(30), AsyncExitStack() as stack:
            sessions = {}
            for name, parameters in [("custom", agent.custom_server_parameters()), ("git", agent.git_server_parameters())]:
                reader, writer = await stack.enter_async_context(stdio_client(parameters))
                current = await stack.enter_async_context(ClientSession(reader, writer))
                await current.initialize()
                sessions[name] = current
            declarations, routes = await agent.discover_tools(sessions)
            assert len(declarations) == len(routes) == 7
            for declaration in declarations:
                if declaration.name.startswith("git_"):
                    assert "repo_path" not in declaration.parameters_json_schema["properties"]
    asyncio.run(check())


@pytest.mark.parametrize("code", [429, 500, 502, 503, 504])
def test_retry_success(monkeypatch, code):
    """Retry transient responses with exponential delays and return the answer."""
    failure = agent.errors.APIError(code, {"message": "sensitive details"})
    bot, _, _, model = setup_agent([
        failure, failure, response(types.Part.from_text(text="Recovered."))
    ])
    sleep = AsyncMock()
    monkeypatch.setattr(agent.asyncio, "sleep", sleep)
    assert asyncio.run(bot.ask("hello")) == "Recovered."
    assert model.await_count == 3
    assert [entry.args[0] for entry in sleep.await_args_list] == [1, 2]


def test_retry_exhausted(monkeypatch):
    """Stop after three attempts without exposing API response details."""
    failure = agent.errors.APIError(503, {"message": "sensitive details"})
    bot, _, _, model = setup_agent([failure] * 3)
    sleep = AsyncMock()
    monkeypatch.setattr(agent.asyncio, "sleep", sleep)
    answer = asyncio.run(bot.ask("hello"))
    assert "HTTP 503" in answer
    assert "sensitive details" not in answer
    assert model.await_count == 3
    assert sleep.await_count == 2


def test_parallel_and_sequential_function_response_history():
    """Regress HTTP 400: use Gemini roles while preserving IDs and signed parts."""
    import json

    parallel = response(
        types.Part(function_call=types.FunctionCall(
            name="read_security_log", args={"filename": "auth.log"}, id="log-call"
        ), thought_signature=b"opaque-signature"),
        types.Part(function_call=types.FunctionCall(
            name="git_log", args={"max_count": 1}, id="git-call"
        )),
    )
    sequential = response(types.Part(function_call=types.FunctionCall(
        name="analyze_failed_logins", args={"filename": "auth.log"}, id="analysis-call"
    )))
    bot, custom, git, model = setup_agent([
        parallel, sequential, response(types.Part.from_text(text="Evidence summarized."))
    ])
    assert asyncio.run(bot.ask("Investigate")) == "Evidence summarized."
    history = model.call_args.kwargs["contents"]
    assert [item.role for item in history] == ["user", "model", "user", "model", "user"]
    assert history[1] is parallel.candidates[0].content
    assert history[1].parts[0].thought_signature == b"opaque-signature"
    replies = [part.function_response for part in history[2].parts]
    assert [(part.name, part.id) for part in replies] == [
        ("read_security_log", "log-call"), ("git_log", "git-call")
    ]
    assert history[4].parts[0].function_response.id == "analysis-call"
    for message in (history[2], history[4]):
        for part in message.parts:
            assert part.text is None
            payload = json.loads(json.dumps(part.function_response.response))
            assert json.loads(payload["untrusted_data"])["isError"] is False
    assert custom.call_tool.await_count == 2
    assert git.call_tool.await_count == 1


@pytest.mark.parametrize("code", [400, 401, 403, 404])
def test_permanent_error_not_retried(monkeypatch, code):
    """Do not retry bad requests, invalid keys, denied access, or missing models."""
    bot, _, _, model = setup_agent([agent.errors.APIError(code, {"message": "secret"})])
    sleep = AsyncMock()
    monkeypatch.setattr(agent.asyncio, "sleep", sleep)
    assert f"HTTP {code}" in asyncio.run(bot.ask("hello"))
    assert model.await_count == 1
    sleep.assert_not_awaited()
