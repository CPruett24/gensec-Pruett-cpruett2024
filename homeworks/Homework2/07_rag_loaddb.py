"""Index TXT/PDF/JSON documents using the instructor's RAG ingestion flow."""

from langchain_community.document_loaders import (
    DirectoryLoader,
    PyPDFDirectoryLoader,
    TextLoader,
)
from langchain_text_splitters import RecursiveCharacterTextSplitter

from app import DATA_DIRECTORY, get_sources, open_vectorstore
from json_loader import CustomJSONLoader


def load_docs(docs, vectorstore):
    """Split documents using the instructor's settings and store their embeddings."""
    splitter = RecursiveCharacterTextSplitter(chunk_size=10000, chunk_overlap=10)
    splits = splitter.split_documents(docs)
    if splits:
        vectorstore.add_documents(documents=splits)
    return len(splits)


def main():
    """Load local TXT, PDF, and custom JSON documents into the RAG database."""
    docs = DirectoryLoader(
        str(DATA_DIRECTORY / "txt"),
        glob="**/*.txt",
        loader_cls=TextLoader,
        loader_kwargs={"encoding": "utf-8"},
    ).load()
    docs.extend(PyPDFDirectoryLoader(str(DATA_DIRECTORY / "pdf"), recursive=True).load())
    docs.extend(DirectoryLoader(
        str(DATA_DIRECTORY / "json"),
        glob="**/*.json",
        loader_cls=CustomJSONLoader,
    ).load())
    if not docs:
        print("Add files to rag_data/txt, rag_data/pdf, or rag_data/json, then run again.")
        return
    vectorstore = open_vectorstore()
    count = load_docs(docs, vectorstore)
    print(f"Stored {count} chunks. Indexed sources:")
    for source in get_sources(vectorstore):
        print(f"  {source}")


if __name__ == "__main__":
    main()
