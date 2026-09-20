"""Terminal RAG chat, adapted from instructor 09_rag_query.py."""

from app import create_rag_chain, get_sources, open_vectorstore


def main():
    """Answer questions from indexed sources until an empty line is entered."""
    vectorstore = open_vectorstore()
    sources = get_sources(vectorstore)
    if not sources:
        print("No indexed documents. Run 07_rag_loaddb.py first.")
        return
    rag_chain = create_rag_chain(vectorstore)
    print("Ask a question about these documents (blank line to exit):")
    print("\n".join(sources))
    while question := input("llm>> ").strip():
        print(rag_chain.invoke(question))


if __name__ == "__main__":
    main()
