"""Custom JSON document loader for the Homework 2 RAG pipeline."""

import json
from pathlib import Path

from langchain_core.document_loaders import BaseLoader
from langchain_core.documents import Document


def text_lines(value, path=""):
    """Flatten JSON values into labeled lines, skipping null and blank values."""
    if isinstance(value, dict):
        for key, item in value.items():
            yield from text_lines(item, f"{path}.{key}" if path else key)
    elif isinstance(value, list):
        for index, item in enumerate(value):
            yield from text_lines(item, f"{path}[{index}]")
    elif value is not None:
        text = value.strip() if isinstance(value, str) else json.dumps(value)
        if text:
            yield f"{path}: {text}" if path else text


class CustomJSONLoader(BaseLoader):
    """Load one document per top-level JSON array item, or one for any other root.

    Nested field labels retain context for text, numbers, and booleans. Empty
    records are skipped. Metadata includes the absolute source and zero-based
    record index. The file is parsed once; documents are yielded by lazy_load.
    """

    def __init__(self, file_path):
        """Store the JSON file path without reading the file yet."""
        self.file_path = Path(file_path).resolve()

    def lazy_load(self):
        """Read UTF-8 JSON and yield documents; file and parse errors propagate."""
        with self.file_path.open(encoding="utf-8-sig") as handle:
            data = json.load(handle)
        records = data if isinstance(data, list) else [data]
        for index, record in enumerate(records):
            content = "\n".join(text_lines(record))
            if content:
                yield Document(
                    page_content=content,
                    metadata={"source": str(self.file_path), "record_index": index},
                )
