# Homework 2: baseline RAG application

This is the initial foundation for a NotebookLM-like application. It loads local
documents, splits them, stores Vertex AI embeddings in Chroma, retrieves relevant
chunks, and answers questions with Gemini through a terminal or Chainlit UI.
The custom Homework 2 feature adds JSON support through a LangChain `BaseLoader` subclass.

## Instructor foundation

Adapted from `C:\Projects\gensec-code-reference\02_LangChain\07_RAG`:

| Instructor file | Homework adaptation |
| --- | --- |
| `07_rag_loaddb.py` | Same local TXT/PDF loaders, `RecursiveCharacterTextSplitter` settings (10,000 characters, 10 overlap), Vertex AI `gemini-embedding-001`, and persistent Chroma storage. |
| `08_rag_docsearch.py` | Same similarity search and closest-source display. |
| `09_rag_query.py` | Same local prompt, document formatting, retriever, `RunnablePassthrough`, Gemini, and `StrOutputParser` chain. |
| `10_chainlit_rag_query.py` | Callbacks now live in `app.py`; `10_chainlit_rag_query.py` remains a compatibility entry point. Same RAG answers, with a homework welcome message and asynchronous invocation. |
| `requirements.txt` | Reduced to the dependencies used by this baseline, managed with `pyproject.toml` and `uv.lock`. |

`app.py` is the main Chainlit application entry point and shares the small
database/chain setup across scripts so indexing and
querying use identical embeddings and paths. Paths are anchored to this project.
The external-source demos (Wikipedia, GitHub, YouTube, arXiv) and other document
formats are omitted from this initial baseline. Unused imports and `readline`
were removed for Windows compatibility. The instructor repository is unchanged.

## Setup (PowerShell)

```powershell
Set-Location C:\Projects\gensec-Pruett-cpruett2024\homeworks\Homework2
uv sync --locked
Copy-Item .env.example .env
```

Edit `.env` locally:

- `GOOGLE_API_KEY`: your Google AI Studio key for chat.
- `GOOGLE_MODEL`: the Gemini chat model available to your account/course.
- `GOOGLE_CLOUD_PROJECT`: your Google Cloud project for Vertex AI embeddings.
- `GOOGLE_CLOUD_LOCATION`: the instructor's default is `us-west1`.
- `GOOGLE_APPLICATION_CREDENTIALS`: absolute path to an existing Google Cloud
  credential JSON outside the repository. Use forward slashes in `.env` paths.
  Alternatively, remove this entry if you already have Application Default
  Credentials configured in your environment.

The embedding project needs Vertex AI access and billing/credits. Vertex AI
embeddings use Google Cloud credentials; the AI Studio key is for chat. Secrets
and project IDs are read from the environment. `uv run --env-file .env` loads the
local file; if you set variables directly in PowerShell, omit `--env-file .env`.
The local `.env`, credential directory, private source documents, vector database, and
generated application files are ignored by Git. Never place credential JSON
files elsewhere inside the repository.

## Index and run

Place your UTF-8 `.txt` files under `rag_data/txt/` and text-based `.pdf` files
under `rag_data/pdf/`. These folders start empty; no instructor datasets are copied.
JSON files go under `rag_data/json/`, which includes the small `sample.json` demo.

```powershell
uv run --env-file .env python 07_rag_loaddb.py
uv run --env-file .env python 08_rag_docsearch.py
uv run --env-file .env python 09_rag_query.py
uv run --env-file .env chainlit run app.py
```

Run indexing first, then choose search, terminal chat, or browser chat. Open the
local URL printed by Chainlit. A blank line exits the terminal loops.

As in the instructor example, indexing appends documents: running it twice adds
duplicates. To rebuild, stop the application and remove only this homework's
`rag_data/.chromadb` directory before indexing again. PDF loading does not perform
OCR. Indexing and answering require network access and may consume API credits.

## Custom JSON loader

`json_loader.py` defines `CustomJSONLoader(BaseLoader)` and implements
`lazy_load()`; LangChain's inherited `load()` collects the resulting documents.
It reads UTF-8 JSON (also accepting a BOM), emits one `Document` per top-level
array item, and treats any other JSON root as one record. Nested field labels
are retained with string, numeric, and boolean values; nulls and blank/empty
records are skipped. Each document has an absolute `source` path and zero-based
`record_index` metadata. Invalid JSON or unreadable files raise an error.

The existing `07_rag_loaddb.py` uses `DirectoryLoader` with this custom loader,
then sends JSON documents through the same splitter, Vertex AI embeddings, and
Chroma storage as TXT/PDF documents. The prompt and retrieval chain are unchanged.
No additional dependencies are needed.

For a demo, run the indexing and `chainlit run app.py` commands above, then ask:
"How do I reserve a study room at Harbor Library?" or "When is the research
skills workshop?" Add your own `.json` files under `rag_data/json/` and rerun
indexing (the append/duplicate behavior noted above still applies). Only the
supplied sample JSON is included in Git by default.

## Validation

Run the offline tests without API credentials:

```powershell
uv run --offline --locked python -m unittest discover -s tests -v
```

Dependency installation and offline smoke checks can validate imports, loaders,
chunking, and the retrieval chain without calling Google. Full embedding and
Gemini answer validation requires your credentials and documents.
