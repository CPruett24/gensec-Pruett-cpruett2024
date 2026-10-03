# Homework 3 agent

The CLI offers the built-in `terminal` tool and two custom tools:
`security_knowledge` for answers grounded in your local security/course notes,
and `file_security_analysis` for deterministic local file hashes and metadata.
It prints tool calls, arguments, results, and the final agent answer.

From `Homework3`, install dependencies with `uv sync`. Set the following
environment variables in the same PowerShell session (replace the placeholders):

```powershell
$env:GOOGLE_API_KEY = "<your Google API key>"
$env:GOOGLE_MODEL = "<your Gemini chat model>"
$env:GOOGLE_EMBEDDING_MODEL = "<your Google embedding model>"
```

The code reads the process environment; it does not automatically load `.env` files.
The RAG tool uses Google API-key embeddings rather than Homework 2's Vertex AI
embeddings, so it needs no separate cloud project/location configuration.

Place UTF-8 `.txt` documents in `rag_data/txt`, PDFs in `rag_data/pdf`, and JSON
in `rag_data/json`. Subdirectories are supported. JSON records retain their field
labels and record indices, and PDF passages retain page metadata. Homework 2's
documents and database are not read or changed automatically.

```powershell
uv run index_documents.py
uv run app.py
```

Indexing uses overlapping 1,500-character passages, persistent Chroma vectors,
and stable chunk IDs. Run indexing again after editing or removing documents;
with a nonempty corpus it updates passages and removes stale chunks without
creating duplicates. With an empty corpus it reports setup guidance and leaves
any existing index intact. Changing `GOOGLE_EMBEDDING_MODEL` selects a separate
collection; index again before querying with that model. Restart the CLI after
changing configuration. General chat and Terminal work before the RAG index exists.

To demonstrate tool selection, add a note containing a distinctive course fact,
for example `rag_data/txt/demo.txt` containing:

```text
Course exercise: The incident response drill is named Copper Lantern.
The drill requires students to preserve the authentication log before analysis.
```

Index it, start the agent, and ask:

> According to my local course documents, what is the incident response drill
> called, and what must students preserve before analysis? Use security_knowledge.

The CLI should show `Tool call: security_knowledge`, the question arguments,
`Tool result:` with the grounded answer and retrieved sources, then the final
agent response. A follow-up such as "What must I preserve for that drill?" also
checks conversation history. The agent decides which tool to call; visible
tool output is the evidence it used retrieval. Ask about a fact absent from your
notes to check that it reports insufficient evidence. Type `exit` or `quit` to stop.

## Local file analysis

`file_security_analysis` accepts a local file path, verifies it is a regular
file, and returns its name, resolved path, size in bytes, and SHA-256, SHA-1,
and MD5 hashes. It reads binary data in 1 MiB chunks using standard-library
Python, without executing or modifying the file. Hashes fingerprint the file;
the tool does not determine whether it contains malware. Invalid, missing,
directory, and unreadable paths return a structured error.

Relative paths resolve against the directory where you start the CLI. Absolute
paths and `~` are supported, including paths containing spaces. The file should
remain unchanged while it is being read. The file analysis tool needs no RAG
index or embedding model setting; the conversational CLI still needs
`GOOGLE_MODEL` and `GOOGLE_API_KEY`.

From `Homework3`, run `uv run app.py` and enter:

> Use file_security_analysis to calculate the SHA-256, SHA-1, and MD5 of
> README.md and report its file name and size in bytes.

Look for `Tool call: file_security_analysis`, the path arguments, and
`Tool result:` containing `status: ok`, metadata, and all three hashes, followed
by the agent's answer. Try `missing-file.bin` or `rag_data` to demonstrate errors.
For a file elsewhere, include its full path in your request.

The prompt and tool docstrings direct the agent to use file analysis for hashes
and metadata, `security_knowledge` for questions grounded in course documents,
and Terminal for shell operations.

Offline verification (uses local test embeddings and fake model responses):

```powershell
uv run python -m unittest discover -s tests -v
```
