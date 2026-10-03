"""Index Homework 3's local security/course documents before starting the CLI."""

from rag import index_documents, load_documents, open_vectorstore


def main() -> None:
    """Load, chunk, embed, and persist the local TXT, PDF, and JSON documents."""
    docs = load_documents()
    if not docs:
        print("Add documents to rag_data/txt, rag_data/pdf, or rag_data/json first.")
        return
    count = index_documents(docs, open_vectorstore())
    print(f"Indexed {count} chunks from {len(docs)} documents/pages/records.")
    for source in sorted({doc.metadata["source"] for doc in docs}):
        print(f"  {source}")


if __name__ == "__main__":
    main()
