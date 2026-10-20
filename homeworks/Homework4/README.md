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
implemented in this milestone.
