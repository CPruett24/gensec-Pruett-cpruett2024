"""Main Chainlit RAG app, adapted from instructor examples 07, 09, and 10."""

import os

import chainlit as cl
from pathlib import Path

from langchain_chroma import Chroma
from langchain_core.output_parsers import StrOutputParser
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.runnables import RunnablePassthrough
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_google_vertexai import VertexAIEmbeddings

DATA_DIRECTORY = Path(__file__).resolve().parent / "rag_data"


def required_env(name):
    """Read a required environment variable without embedding credentials in code."""
    value = os.environ.get(name, "").strip()
    if not value:
        raise ValueError(f"Set {name} in your environment or local .env file.")
    return value


def open_vectorstore():
    """Open the instructor's persistent Chroma store with Vertex AI embeddings."""
    return Chroma(
        embedding_function=VertexAIEmbeddings(
            model_name="gemini-embedding-001",
            project=required_env("GOOGLE_CLOUD_PROJECT"),
            location=os.environ.get("GOOGLE_CLOUD_LOCATION") or "us-west1",
        ),
        persist_directory=str(DATA_DIRECTORY / ".chromadb"),
    )


def get_sources(vectorstore):
    """Return the unique source names recorded in the vector database."""
    return sorted({
        metadata.get("source", "Unknown source")
        for metadata in vectorstore.get()["metadatas"]
        if metadata
    })


def format_docs(docs):
    """Join retrieved document contents into one prompt context string."""
    return "\n\n".join(doc.page_content for doc in docs)


def create_rag_chain(vectorstore):
    """Build the instructor's retrieval, prompt, Gemini, and text-parser chain."""
    llm = ChatGoogleGenerativeAI(
        model=required_env("GOOGLE_MODEL"),
        google_api_key=required_env("GOOGLE_API_KEY"),
        vertexai=False,
    )
    retriever = vectorstore.as_retriever()
    prompt = ChatPromptTemplate.from_template(
        """You are an assistant for question-answering tasks.
Use the following pieces of retrieved context to answer the question.
If you don't know the answer, just say that you don't know.
Use three sentences maximum and keep the answer concise.

Question: {question}

Context: {context}

Answer:"""
    )
    return (
        {"context": retriever | format_docs, "question": RunnablePassthrough()}
        | prompt
        | llm
        | StrOutputParser()
    )


@cl.on_chat_start
async def on_chat_start():
    """Initialize the session's RAG chain and welcome the user."""
    vectorstore = await cl.make_async(open_vectorstore)()
    sources = await cl.make_async(get_sources)(vectorstore)
    if not sources:
        await cl.Message(content="No indexed documents. Run 07_rag_loaddb.py, then start a new chat.").send()
        return
    rag_chain = create_rag_chain(vectorstore)
    cl.user_session.set("rag_chain", rag_chain)
    await cl.Message(content="Welcome to Homework 2 RAG! Ask a question about your indexed documents.").send()


@cl.on_message
async def on_message(message: cl.Message):
    """Answer a user question with the instructor's retrieval-augmented chain."""
    rag_chain = cl.user_session.get("rag_chain")
    if rag_chain is None:
        await cl.Message(content="Index documents with 07_rag_loaddb.py, then start a new chat.").send()
        return
    answer = await rag_chain.ainvoke(message.content)
    await cl.Message(content=answer).send()
