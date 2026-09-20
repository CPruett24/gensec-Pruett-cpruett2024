"""Offline checks for JSON loading and the existing ingestion pipeline."""

import importlib
import json
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import Mock, patch

from langchain_core.document_loaders import BaseLoader
from langchain_core.documents import Document

from json_loader import CustomJSONLoader


class JSONLoaderTests(unittest.TestCase):
    """Check content extraction, metadata, errors, and ingestion without Google."""

    def test_sample(self):
        """Load the committed demo through the inherited BaseLoader interface."""
        path = Path(__file__).resolve().parents[1] / "rag_data/json/sample.json"
        loader = CustomJSONLoader(path)
        self.assertIsInstance(loader, BaseLoader)
        docs = loader.load()
        self.assertEqual(len(docs), 2)
        self.assertIn("reservation.student_id_required: true", docs[0].page_content)
        self.assertIn("Tuesday at 3 PM", docs[1].page_content)
        self.assertEqual(docs[1].metadata, {"source": str(path), "record_index": 1})
        self.assertEqual(docs, list(loader.lazy_load()))

    def test_nested_unicode_and_empty_values(self):
        """Preserve labels and scalar values while skipping empty records."""
        with TemporaryDirectory() as directory:
            path = Path(directory) / "nested.json"
            path.write_text(json.dumps([{}, None, {"title": "Café", "details": {
                "count": 0, "enabled": False, "tags": ["alpha", ""], "missing": None,
            }}]), encoding="utf-8-sig")
            docs = CustomJSONLoader(path).load()
            self.assertEqual(len(docs), 1)
            self.assertEqual(docs[0].metadata["record_index"], 2)
            self.assertEqual(docs[0].page_content,
                             "title: Café\ndetails.count: 0\ndetails.enabled: false\ndetails.tags[0]: alpha")

    def test_root_shapes(self):
        """Accept object and scalar roots and produce no documents for empty JSON."""
        with TemporaryDirectory() as directory:
            path = Path(directory) / "root.json"
            for value, expected in [({"title": "Notes"}, ["title: Notes"]),
                                    ("Notes", ["Notes"]), ([], []), ({}, []), (None, [])]:
                with self.subTest(value=value):
                    path.write_text(json.dumps(value), encoding="utf-8")
                    self.assertEqual([doc.page_content for doc in CustomJSONLoader(path).load()], expected)

    def test_invalid_and_missing_files(self):
        """Surface malformed JSON and missing files rather than silently skipping."""
        with TemporaryDirectory() as directory:
            path = Path(directory) / "invalid.json"
            with self.assertRaises(FileNotFoundError):
                CustomJSONLoader(path).load()
            path.write_text('{"unfinished":', encoding="utf-8")
            with self.assertRaises(json.JSONDecodeError):
                CustomJSONLoader(path).load()

    def test_ingestion_preserves_all_formats_and_metadata(self):
        """Run real TXT/JSON loaders and chunking with PDF/cloud boundaries stubbed."""
        ingestion = importlib.import_module("07_rag_loaddb")
        with TemporaryDirectory() as directory:
            root = Path(directory)
            for name in ("txt", "pdf", "json/nested"):
                (root / name).mkdir(parents=True)
            (root / "txt/notes.txt").write_text("Existing text support", encoding="utf-8")
            path = root / "json/nested/notes.json"
            path.write_text(json.dumps({"body": "JSON content " * 2000}), encoding="utf-8")
            store = Mock()
            pdf_doc = Document(page_content="Existing PDF support", metadata={"source": "sample.pdf"})
            with patch.object(ingestion, "DATA_DIRECTORY", root), \
                 patch.object(ingestion, "open_vectorstore", return_value=store), \
                 patch.object(ingestion, "get_sources", return_value=[]), \
                 patch.object(ingestion.PyPDFDirectoryLoader, "load", return_value=[pdf_doc]) as pdf_load, \
                 patch("builtins.print"):
                ingestion.main()
            pdf_load.assert_called_once()
            chunks = store.add_documents.call_args.kwargs["documents"]
            self.assertTrue(any("Existing text support" in doc.page_content for doc in chunks))
            self.assertTrue(any("Existing PDF support" in doc.page_content for doc in chunks))
            json_chunks = [doc for doc in chunks if doc.metadata["source"] == str(path.resolve())]
            self.assertGreater(len(json_chunks), 1)
            self.assertTrue(all(doc.metadata["record_index"] == 0 for doc in json_chunks))
            self.assertTrue(all(len(doc.page_content) <= 10000 for doc in json_chunks))


if __name__ == "__main__":
    unittest.main()
