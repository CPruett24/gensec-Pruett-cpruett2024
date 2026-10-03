"""Offline file hashing, error handling, and agent integration tests."""

import hashlib
import io
import os
import tempfile
import unittest
from contextlib import redirect_stdout
from pathlib import Path
from unittest.mock import patch

from langchain_core.language_models.fake_chat_models import FakeMessagesListChatModel
from langchain_core.messages import AIMessage, ToolMessage

import app
from file_security import analyze_file, file_security_analysis


class FileToolModel(FakeMessagesListChatModel):
    """Script tool selection while using LangChain's real agent execution loop."""

    def bind_tools(self, tools, **kwargs):
        """Verify that all three agent tools are registered without a provider call."""
        assert {tool.name for tool in tools} == {
            "terminal", "security_knowledge", "file_security_analysis"
        }
        return self


class FileSecurityTests(unittest.TestCase):
    """Verify exact fingerprints, bounded streaming, and actionable errors."""

    def test_known_hashes_and_metadata(self):
        """Hash a known byte sequence using a path containing spaces."""
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "sample file.bin"
            path.write_bytes(b"abc")
            result = file_security_analysis.invoke({"file_path": str(path)})
            self.assertEqual(result["status"], "ok")
            self.assertEqual(result["file_name"], path.name)
            self.assertEqual(result["path"], str(path.resolve()))
            self.assertEqual(result["size_bytes"], 3)
            self.assertEqual(result["hashes"], {
                "sha256": "ba7816bf8f01cfea414140de5dae2223b00361a396177a9cb410ff61f20015ad",
                "sha1": "a9993e364706816aba3e25717850c26c9cd0d89d",
                "md5": "900150983cd24fb0d6963f7d28e17f72",
            })
            self.assertEqual(path.read_bytes(), b"abc")

    def test_empty_and_multi_chunk_binary_files(self):
        """Support empty files and binary data spanning multiple read chunks."""
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "binary.bin"
            for content in [b"", bytes(range(256)) * 9000]:
                with self.subTest(size=len(content)):
                    path.write_bytes(content)
                    result = analyze_file(str(path))
                    self.assertEqual(result["size_bytes"], len(content))
                    for algorithm in ["sha256", "sha1", "md5"]:
                        expected = hashlib.new(algorithm, content, usedforsecurity=False).hexdigest()
                        self.assertEqual(result["hashes"][algorithm], expected)

    def test_invalid_paths(self):
        """Reject missing files, directories, blank input, and malformed paths."""
        with tempfile.TemporaryDirectory() as directory:
            for path, message in [
                (str(Path(directory) / "missing.bin"), "does not exist"),
                (directory, "not a regular file"),
                ("  ", "must not be blank"),
                ("invalid\0path", "Unable to analyze"),
            ]:
                with self.subTest(path=path):
                    result = file_security_analysis.invoke({"file_path": path})
                    self.assertEqual(result["status"], "error")
                    self.assertIn(message, result["error"])
                    self.assertNotIn("hashes", result)

    def test_unreadable_file(self):
        """Report read permission errors deterministically on Windows and Unix."""
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "private.bin"
            path.write_bytes(b"private")
            with patch.object(Path, "open", side_effect=PermissionError("denied")):
                result = analyze_file(str(path))
            self.assertEqual(result["status"], "error")
            self.assertIn("Permission denied", result["error"])

    def test_agent_call_and_visible_result(self):
        """Execute the file tool through the agent and display actual computed hashes."""
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "sample.bin"
            path.write_bytes(b"abc")
            model = FileToolModel(responses=[
                AIMessage(content="", tool_calls=[{
                    "name": "file_security_analysis", "args": {"file_path": str(path)},
                    "id": "file-call", "type": "tool_call",
                }]),
                AIMessage(content="The file contains 3 bytes."),
            ])
            with patch.object(app, "ChatGoogleGenerativeAI", return_value=model), \
                 patch.dict(os.environ, {"GOOGLE_MODEL": "test", "GOOGLE_API_KEY": "test"}):
                agent = app.build_agent()
                output = io.StringIO()
                with redirect_stdout(output):
                    result = agent.invoke(
                        {"messages": [{"role": "user", "content": f"Hash {path}"}]},
                        config={"callbacks": [app.TerminalDisplayHandler()]},
                    )
                message = next(msg for msg in result["messages"] if isinstance(msg, ToolMessage))
                self.assertIn("900150983cd24fb0d6963f7d28e17f72", message.content)
                self.assertIn("Tool call: file_security_analysis", output.getvalue())
                self.assertIn("Tool result:", output.getvalue())


if __name__ == "__main__":
    unittest.main()
