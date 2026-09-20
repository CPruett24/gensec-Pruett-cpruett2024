"""Search indexed documents, adapted from instructor 08_rag_docsearch.py."""

from app import get_sources, open_vectorstore


def search_db(query, vectorstore):
    """Print the closest source returned by the instructor's similarity search."""
    docs = vectorstore.similarity_search(query)
    if docs:
        print(f"Closest document match: {docs[0].metadata.get('source')}, count={len(docs)}")
    else:
        print("No matching documents")


def main():
    """List indexed sources and accept searches until an empty line is entered."""
    vectorstore = open_vectorstore()
    sources = get_sources(vectorstore)
    if not sources:
        print("No indexed documents. Run 07_rag_loaddb.py first.")
        return
    print("Indexed sources:\n" + "\n".join(sources))
    while query := input(">> ").strip():
        search_db(query, vectorstore)


if __name__ == "__main__":
    main()
