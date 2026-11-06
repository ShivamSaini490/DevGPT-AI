import pytest
from langchain_core.documents import Document
from sqlalchemy import func, select

from app.db.models import DocumentChunk
from app.db.session import SessionLocal
from app.rag import vector_store as vector_store_module


def _vector(first_value: float) -> list[float]:
    return [first_value] + [0.0] * 3071


class FakeEmbeddings:
    def __init__(self):
        self.document_calls = []
        self.query_calls = []

    def embed_documents(self, texts):
        self.document_calls.append(texts)
        return [_vector(float(text.split(":", 1)[0])) for text in texts]

    def embed_query(self, query):
        self.query_calls.append(query)
        return _vector(float(query))


@pytest.fixture
def fake_embeddings(monkeypatch):
    fake = FakeEmbeddings()
    monkeypatch.setattr(vector_store_module, "embeddings", fake)
    return fake


def test_add_documents_returns_ids_and_persists_metadata(fake_embeddings):
    store = vector_store_module.PostgresVectorStore()
    documents = [
        Document(
            page_content="0:first chunk",
            metadata={"thread_id": "thread-1", "source": "notes.txt"},
        ),
        Document(
            page_content="5:second chunk",
            metadata={"thread_id": "thread-1", "source": "notes.txt"},
        ),
    ]

    ids = store.add_documents(documents)

    assert len(ids) == 2
    assert len(set(ids)) == 2
    assert fake_embeddings.document_calls == [["0:first chunk", "5:second chunk"]]

    db = SessionLocal()
    try:
        rows = db.scalars(select(DocumentChunk).order_by(DocumentChunk.content)).all()
        assert len(rows) == 2
        assert rows[0].thread_id == "thread-1"
        assert rows[0].cmetadata == {
            "thread_id": "thread-1",
            "source": "notes.txt",
        }
    finally:
        db.close()


def test_add_documents_with_empty_list_does_not_embed(fake_embeddings):
    store = vector_store_module.PostgresVectorStore()

    assert store.add_documents([]) == []
    assert fake_embeddings.document_calls == []


def test_embedding_client_is_optional_until_rag_is_used(monkeypatch):
    monkeypatch.setattr(vector_store_module, "embeddings", None)
    monkeypatch.setattr(vector_store_module, "GOOGLE_API_KEY", "")

    with pytest.raises(RuntimeError, match="GOOGLE_API_KEY is required"):
        vector_store_module.PostgresVectorStore().similarity_search("query")


def test_similarity_search_uses_l2_order_and_thread_filter(fake_embeddings):
    store = vector_store_module.PostgresVectorStore()
    store.add_documents(
        [
            Document(page_content="0:near", metadata={"thread_id": "thread-1"}),
            Document(page_content="8:far", metadata={"thread_id": "thread-1"}),
            Document(page_content="1:other", metadata={"thread_id": "thread-2"}),
        ]
    )

    results = store.similarity_search(
        "1",
        k=4,
        filter={"thread_id": "thread-1"},
    )

    assert [document.page_content for document in results] == ["0:near", "8:far"]
    assert all(document.metadata["thread_id"] == "thread-1" for document in results)
    assert fake_embeddings.query_calls == ["1"]


def test_embedding_failure_does_not_create_partial_rows(monkeypatch):
    class FailingEmbeddings:
        def embed_documents(self, texts):
            raise RuntimeError("embedding failed")

    monkeypatch.setattr(vector_store_module, "embeddings", FailingEmbeddings())
    store = vector_store_module.PostgresVectorStore()

    with pytest.raises(RuntimeError, match="embedding failed"):
        store.add_documents(
            [Document(page_content="content", metadata={"thread_id": "thread-1"})]
        )

    db = SessionLocal()
    try:
        assert db.scalar(select(func.count()).select_from(DocumentChunk)) == 0
    finally:
        db.close()


def test_database_failure_rolls_back_document_batch(fake_embeddings, monkeypatch):
    monkeypatch.setattr(vector_store_module.uuid, "uuid4", lambda: "duplicate-id")
    store = vector_store_module.PostgresVectorStore()

    with pytest.raises(Exception):
        store.add_documents(
            [
                Document(page_content="0:first", metadata={"thread_id": "thread-1"}),
                Document(page_content="1:second", metadata={"thread_id": "thread-1"}),
            ]
        )

    db = SessionLocal()
    try:
        assert db.scalar(select(func.count()).select_from(DocumentChunk)) == 0
    finally:
        db.close()
