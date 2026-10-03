"""Offline integration checks for document indexing, retrieval, and agent tools."""

import io
import os
import tempfile
import unittest
from contextlib import redirect_stdout
from pathlib import Path
from unittest.mock import patch

from langchain_chroma import Chroma
from langchain_core.documents import Document
from langchain_core.embeddings import Embeddings
from langchain_core.language_models.fake_chat_models import FakeListChatModel, FakeMessagesListChatModel
from langchain_core.messages import AIMessage, ToolMessage
from langchain_core.runnables import RunnableLambda

import app
import rag


class LocalEmbeddings(Embeddings):
    """Supply deterministic local vectors without credentials or network calls."""

    def embed_documents(self, texts):
        """Embed a batch using the same local representation as a query."""
        return [self.embed_query(text) for text in texts]

    def embed_query(self, text):
        """Represent a document by a few security keyword counts."""
        text = text.lower()
        return [1.0, float(text.count("log")), float(text.count("drill"))]


class ToolCallingModel(FakeMessagesListChatModel):
    """Allow scripted tool calls through the real LangChain agent loop."""

    def bind_tools(self, tools, **kwargs):
        """Return the scripted model without contacting a provider."""
        return self


class RagTests(unittest.TestCase):
    """Exercise persistent retrieval and CLI integration without Google requests."""

    def test_loading_chunking_and_idempotent_index(self):
        """Load TXT/JSON, preserve labels, deduplicate, and replace stale passages."""
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "txt").mkdir()
            (root / "json").mkdir()
            (root / "txt" / "notes.txt").write_text("Preserve the log. " * 200, encoding="utf-8")
            (root / "json" / "notes.json").write_text(
                '[{"drill": {"name": "Copper Lantern"}}, null]', encoding="utf-8"
            )
            docs = rag.load_documents(root)
            self.assertEqual(len(docs), 2)
            self.assertIn("drill.name: Copper Lantern", docs[1].page_content)
            self.assertEqual(docs[1].metadata["record_index"], 0)
            chunks = rag.split_documents(docs)
            self.assertTrue(all(len(doc.page_content) <= 1500 for doc in chunks))
            store = Chroma(
                collection_name="offline_test", embedding_function=LocalEmbeddings(),
                persist_directory=str(root / ".chromadb"),
            )
            count = rag.index_documents(docs, store)
            rag.index_documents(docs, store)
            self.assertEqual(len(store.get()["ids"]), count)
            rag.index_documents([docs[1]], store)
            self.assertEqual(len(store.get()["ids"]), 1)
            self.assertIn("Copper Lantern", store.as_retriever().invoke("drill")[0].page_content)
            # Release Chroma's file handles before TemporaryDirectory cleanup on Windows.
            store._client._system.stop()

    def test_rag_chain_and_agent_display(self):
        """Execute a scripted tool selection through an actual agent and print sources."""
        doc = Document(page_content="The drill is Copper Lantern. Preserve the log.",
                       metadata={"source": str(rag.DATA_DIRECTORY / "txt" / "notes.txt")})
        context = rag.format_docs([doc])
        self.assertIn("Source: txt", context)
        chain = rag.create_rag_chain(FakeListChatModel(responses=["Preserve the log."]))
        self.assertEqual(chain.invoke({"question": "What to preserve?", "context": context}),
                         "Preserve the log.")
        with tempfile.TemporaryDirectory() as directory:
            store = Chroma(collection_name="tool_test", embedding_function=LocalEmbeddings(),
                           persist_directory=directory)
            rag.index_documents([doc], store)
            model = ToolCallingModel(responses=[
                AIMessage(content="", tool_calls=[{
                    "name": "security_knowledge", "args": {"question": "What is the drill?"},
                    "id": "rag-call", "type": "tool_call",
                }]),
                AIMessage(content="The drill is Copper Lantern."),
                AIMessage(content="Preserve the log."),
            ])
            with patch.object(rag, "INDEX_DIRECTORY", Path(directory)), \
                 patch.object(rag, "open_vectorstore", return_value=store), \
                 patch.object(rag, "create_rag_chain", return_value=RunnableLambda(lambda _: "Copper Lantern.")), \
                 patch.object(app, "ChatGoogleGenerativeAI", return_value=model), \
                 patch.dict(os.environ, {"GOOGLE_MODEL": "test", "GOOGLE_API_KEY": "test"}):
                agent = app.build_agent()
                output = io.StringIO()
                with redirect_stdout(output):
                    result = agent.invoke({"messages": [{"role": "user", "content": "What is the drill?"}]},
                                          config={"callbacks": [app.TerminalDisplayHandler()]})
                tool_result = next(msg for msg in result["messages"] if isinstance(msg, ToolMessage))
                self.assertIn("Retrieved sources:", tool_result.content)
                self.assertIn("notes.txt", tool_result.content)
                self.assertIn("Tool call: security_knowledge", output.getvalue())
                self.assertIn("Tool result:", output.getvalue())
                followup = agent.invoke({"messages": [*result["messages"],
                                        {"role": "user", "content": "What do I preserve?"}]})
                self.assertGreater(len(followup["messages"]), len(result["messages"]))
            store._client._system.stop()

    def test_missing_index_and_cli_exits(self):
        """Report indexing guidance without embeddings and retain CLI stop behavior."""
        with tempfile.TemporaryDirectory() as directory, \
             patch.object(rag, "INDEX_DIRECTORY", Path(directory) / "missing"), \
             patch.object(rag, "open_vectorstore") as open_store:
            tool = rag.create_security_knowledge_tool(FakeListChatModel(responses=["unused"]))
            self.assertIn("index_documents.py", tool.invoke({"question": "policy?"}))
            open_store.assert_not_called()
        for ending in ["exit", "QUIT", EOFError(), KeyboardInterrupt()]:
            with patch("builtins.input", side_effect=[ending]), redirect_stdout(io.StringIO()):
                app.chat_loop(None)


if __name__ == "__main__":
    unittest.main()
