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
