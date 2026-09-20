"""Index local TXT/PDF documents, adapted from instructor 07_rag_loaddb.py."""

from langchain_community.document_loaders import (
    DirectoryLoader,
    PyPDFDirectoryLoader,
    TextLoader,
)
from langchain_text_splitters import RecursiveCharacterTextSplitter

from app import DATA_DIRECTORY, get_sources, open_vectorstore


def load_docs(docs, vectorstore):
    """Split documents using the instructor's settings and store their embeddings."""
    splitter = RecursiveCharacterTextSplitter(chunk_size=10000, chunk_overlap=10)
    splits = splitter.split_documents(docs)
    if splits:
        vectorstore.add_documents(documents=splits)
    return len(splits)


def main():
    """Load local text and PDF files into the persistent RAG database."""
    docs = DirectoryLoader(
        str(DATA_DIRECTORY / "txt"),
        glob="**/*.txt",
        loader_cls=TextLoader,
        loader_kwargs={"encoding": "utf-8"},
    ).load()
    docs.extend(PyPDFDirectoryLoader(str(DATA_DIRECTORY / "pdf"), recursive=True).load())
    if not docs:
        print("Add TXT files to rag_data/txt or PDFs to rag_data/pdf, then run again.")
        return
    vectorstore = open_vectorstore()
    count = load_docs(docs, vectorstore)
    print(f"Stored {count} chunks. Indexed sources:")
    for source in get_sources(vectorstore):
        print(f"  {source}")


if __name__ == "__main__":
    main()
