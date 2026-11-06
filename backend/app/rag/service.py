from pathlib import Path
from typing import List

from langchain_core.documents import Document
from langchain_text_splitters import RecursiveCharacterTextSplitter

from app.rag.loaders import read_file_text
from app.rag.vector_store import vectorstore


def add_document_to_rag(file_path: str, thread_id: str):
    text = read_file_text(file_path)

    if not text.strip():
        raise ValueError("No text could be extracted from this file.")

    splitter = RecursiveCharacterTextSplitter(
        chunk_size=900,
        chunk_overlap=150,
    )

    chunks = splitter.split_text(text)

    docs: List[Document] = [
        Document(
            page_content=chunk,
            metadata={
                "thread_id": thread_id,
                "source": Path(file_path).name,
            },
        )
        for chunk in chunks
    ]

    vectorstore.add_documents(docs)

    return {
        "filename": Path(file_path).name,
        "chunks": len(docs),
    }


def retrieve_from_rag(query: str, thread_id: str, k: int = 4) -> str:
    docs = vectorstore.similarity_search(
        query,
        k=k,
        filter={"thread_id": thread_id},
    )

    if not docs:
        return "No relevant uploaded document content found."

    results = []

    for i, doc in enumerate(docs, start=1):
        source = doc.metadata.get("source", "uploaded document")
        results.append(f"[Source {i}: {source}]\n{doc.page_content}")

    return "\n\n".join(results)
