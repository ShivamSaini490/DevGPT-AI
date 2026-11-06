from types import SimpleNamespace

import pytest
from langchain_core.documents import Document

from app.rag import loaders
from app.rag import service


@pytest.mark.parametrize("extension", [".txt", ".md", ".py", ".csv"])
def test_read_file_text_for_plain_text_formats(tmp_path, extension):
    file_path = tmp_path / f"sample{extension}"
    file_path.write_text("hello\nworld", encoding="utf-8")

    assert loaders.read_file_text(str(file_path)) == "hello\nworld"


def test_read_file_text_from_pdf(monkeypatch, tmp_path):
    file_path = tmp_path / "sample.pdf"
    file_path.write_bytes(b"placeholder")
    fake_reader = SimpleNamespace(
        pages=[
            SimpleNamespace(extract_text=lambda: "page one"),
            SimpleNamespace(extract_text=lambda: None),
        ]
    )
    monkeypatch.setattr(loaders, "PdfReader", lambda path: fake_reader)

    assert loaders.read_file_text(str(file_path)) == "page one\n\n"


def test_read_file_text_from_docx(monkeypatch, tmp_path):
    file_path = tmp_path / "sample.docx"
    file_path.write_bytes(b"placeholder")
    monkeypatch.setattr(loaders.docx2txt, "process", lambda path: "docx text")

    assert loaders.read_file_text(str(file_path)) == "docx text"


def test_read_file_text_rejects_unsupported_format(tmp_path):
    file_path = tmp_path / "sample.exe"
    file_path.write_bytes(b"content")

    with pytest.raises(ValueError, match="Unsupported file type"):
        loaders.read_file_text(str(file_path))


def test_add_document_to_rag_preserves_chunking_and_metadata(monkeypatch, tmp_path):
    file_path = tmp_path / "knowledge.txt"
    file_path.write_text("A" * 1000, encoding="utf-8")
    captured = []
    monkeypatch.setattr(
        service.vectorstore,
        "add_documents",
        lambda documents: captured.extend(documents),
    )

    result = service.add_document_to_rag(str(file_path), "thread-1")

    assert result == {"filename": "knowledge.txt", "chunks": 2}
    assert len(captured) == 2
    assert all(document.metadata["thread_id"] == "thread-1" for document in captured)
    assert all(document.metadata["source"] == "knowledge.txt" for document in captured)
    assert len(captured[0].page_content) == 900
    assert captured[0].page_content[-150:] == captured[1].page_content[:150]


def test_add_document_to_rag_rejects_empty_text(monkeypatch):
    monkeypatch.setattr(service, "read_file_text", lambda path: "   \n")

    with pytest.raises(ValueError, match="No text could be extracted"):
        service.add_document_to_rag("empty.txt", "thread-1")


def test_retrieve_from_rag_formats_sources(monkeypatch):
    monkeypatch.setattr(
        service.vectorstore,
        "similarity_search",
        lambda query, k, filter: [
            Document(page_content="First", metadata={"source": "one.txt"}),
            Document(page_content="Second", metadata={}),
        ],
    )

    result = service.retrieve_from_rag("question", "thread-1", k=2)

    assert result == (
        "[Source 1: one.txt]\nFirst\n\n"
        "[Source 2: uploaded document]\nSecond"
    )


def test_retrieve_from_rag_returns_empty_message(monkeypatch):
    monkeypatch.setattr(
        service.vectorstore,
        "similarity_search",
        lambda query, k, filter: [],
    )

    assert service.retrieve_from_rag("question", "thread-1") == (
        "No relevant uploaded document content found."
    )

