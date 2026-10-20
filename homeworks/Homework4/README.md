# Homework 4: MCP Security Log Analyzer

Minimal Python server using the official MCP Python SDK v1 and FastMCP over
STDIO. No API key, environment variables, or external services are required.

From this directory, install and run:

```powershell
uv sync --locked
uv run python mcp-server.py
```

The server waits for an MCP client on STDIO. Run all tests (including an SDK
client that starts the server, discovers and calls its tools, and exits):

```powershell
uv run pytest -q
```

Tools:

- `list_log_files()`: sorted sample `.log` filenames.
- `read_security_log(filename)`: raw UTF-8 text from an allowed sample file.
- `analyze_failed_logins(filename)`: failed SSH login counts by IP and addresses
  with at least three failures.

`sample_logs/auth.log` is entirely synthetic, with documentation IP addresses,
successful and failed logins, timestamps, usernames, and a prompt-injection
example. All log text is untrusted data; the server never executes it or sends
it to an AI model. Any future agent must also treat tool output as untrusted.

Only simple `.log` basenames are accepted. Traversal, absolute paths, alternate
streams, subdirectories, and symbolic links are rejected. Missing files produce
tool errors. Paths are anchored to this module rather than the working directory.
Parsing intentionally supports only the exact timestamped SSH format in the
sample; other lines are ignored. The threshold is fixed at three.

This local teaching server assumes the sample directory is maintained by a
trusted local user; it is not hardened against concurrent filesystem replacement
or arbitrarily large files. It does not authenticate clients or expose HTTP.
`.env` and `.venv` are ignored locally. The agent is reserved for a later milestone.

## Published Git MCP server (Milestone 2)

The official reference implementation is
[modelcontextprotocol/servers, src/git](https://github.com/modelcontextprotocol/servers/tree/main/src/git).
Before installation, its documented package name was checked against the
[PyPI mcp-server-git page](https://pypi.org/project/mcp-server-git/), which links
back to that upstream source. Installation used PyPI explicitly, not a marketplace.
This verifies the published project's identity, not a full source security audit.

`uv.lock` selects `mcp-server-git==0.6.2` and records distribution hashes.
The dependency is constrained below v2 to preserve our existing SDK v1/FastMCP
setup. Use `uv sync --locked` to reproduce the tested versions. This server was
selected because it is the project's published Python Git reference server and
supports local STDIO without Docker, Node.js, cloud services, or credentials.
Git must be installed and available on PATH.

`mcp_connections.py` exposes `custom_server_parameters()` and
`git_server_parameters()`, returning SDK `StdioServerParameters`. Both use
`sys.executable`, so a caller launched through `uv run python ...` uses the
Homework4 environment, including on Windows. The child working directory is
anchored to Homework4. The custom server launches `mcp-server.py`; the Git server
launches `python -m mcp_server_git --repository <resolved-root>`.

The default repository is derived from this project's location, two levels up.
Optionally set `HW4_REPOSITORY` to another repository root; relative values are
resolved against Homework4. For example, in PowerShell:

```powershell
$env:HW4_REPOSITORY = "../.."
uv run python -m mcp_server_git --repository ../..
```

The variable is read by the connection helper; the manual CLI command above
passes its path explicitly. No `.env` file is required or automatically loaded.
Both launches wait for an MCP client on STDIO and expose no network endpoint.

Run only the connection integration tests, showing discovered tools:

```powershell
uv run pytest tests/test_connections.py -q -s
```

Run the full suite with `uv run pytest -q`. The integration test keeps both
initialized sessions open, discovers tools, calls the custom `list_log_files`
and Git `git_status` and `git_log`, then closes both processes. It compares HEAD,
refs, status, and staged/unstaged diffs before and after to detect repository
changes. Git optional index refresh writes are disabled in the connection.

The tested Git release exposes `git_status`, `git_diff_unstaged`,
`git_diff_staged`, `git_log`, `git_add`, `git_commit`, `git_reset`, and
`git_create_branch`. The integration tests call only read-only tools.
The upstream server also exposes write tools: this configuration does not
make it read-only or provide an OS sandbox. Do not give an untrusted agent
unrestricted access, and do not assume `--repository` is a security boundary.
Repository content and tool responses remain untrusted data. Tests verify
observable Git state, not every possible filesystem side effect. No agent is
implemented in Milestone 2.

## Gemini agent (Milestone 3)

From Homework4:

```powershell
uv sync --locked
Copy-Item .env.example .env
# Edit .env locally and replace the placeholder with your Gemini API key.
uv run python agent.py
```

Alternatively set `GEMINI_API_KEY` in your environment. The local `.env` loads
without overriding existing environment values and remains Git-ignored. Never
commit it. The default model is `gemini-flash-latest`; override with `GEMINI_MODEL`
if needed. This alias can change over time. The implementation uses the official
[Google Gen AI SDK](https://googleapis.github.io/python-genai/), `google-genai`
2.31.0, with a manual async function-calling loop. MCP remains 1.30.0.
Real requests require Internet access and may consume quota or incur cost.

Example prompts:

- "Investigate auth.log for suspicious login attempts, inspect the latest Git commits, and summarize any security concerns."
- "Read auth.log, identify prompt injection, and compare it with the failed-login counts."
- "Show Git status and summarize staged and unstaged changes."

Type `exit` or `quit` to close both sessions. Each question starts fresh.
The CLI displays tool names and a call count. It processes at most ten tool
requests per question, including rejected requests. MCP calls time out after
30 seconds; Gemini HTTP requests time out after 60 seconds. Failures show safe
diagnostics rather than raw exceptions.

The seven agent tools are `list_log_files`, `read_security_log`,
`analyze_failed_logins`, `git_status`, `git_log`, `git_diff_unstaged`, and
`git_diff_staged`. Write tools are excluded from declarations and dispatch.
Application code supplies the configured repository path, overriding model input.
No generated shell commands are run.

All retrieved content is marked untrusted in system instructions. Tool results
remain structured function responses, separate from the system instruction and
original user message. They never become executable code or system instructions.
This does not guarantee model accuracy or resistance to every injection. Review
the evidence. Requested repository and log contents are sent to Google; use
only material you are permitted to share. The Git server itself still exposes
write tools to other clients; this teaching application is not an OS sandbox.

Run `uv run pytest -q` for the complete suite without an API key. Agent tests
mock Gemini and validate declarations against both real local MCP servers.
Injection tests establish message separation and blocked write dispatch, not
real-model resistance.

Optional real-model smoke test: configure the key, launch the agent, and ask
the first example prompt. Verify log analysis and `git_log` appear in the tool
diagnostics and suspicious IP `203.0.113.42` appears in the evidence. Ask the
second prompt and verify the injection is reported rather than followed. Type
`quit` to verify clean exit. API/model availability and real-model behavior
remain unverified until this manual test is performed.

Gemini requests retry HTTP 429, 500, 502, 503, and 504 with waits of one and
two seconds, for at most three attempts per model request. SDK-level retries
are disabled to avoid multiplying attempts. Other errors, including HTTP
400/401/403/404, are not retried. Diagnostics include only HTTP codes, not raw
API error details. Retries do not repeat already completed MCP calls or increase
the ten-tool-request budget.

The installed SDK accepts `gemini-2.5-flash`, which supports function calling.
However, [Google's current model documentation](https://ai.google.dev/gemini-api/docs/models/gemini-2.5-flash)
limits access to prior active users, so it is not the universal recommendation
for this project. If your account has access, it is a suitable explicit model
override via `GEMINI_MODEL=gemini-2.5-flash`. The existing default and all
environment overrides are preserved; an SDK accepting a model identifier does
not guarantee API access for that account.
