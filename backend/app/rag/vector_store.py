import uuid

from langchain_core.documents import Document
from langchain_google_genai import GoogleGenerativeAIEmbeddings
from sqlalchemy import select

from app.core.config import EMBEDDING_MODEL
from app.db.models import DocumentChunk
from app.db.session import SessionLocal


embeddings = GoogleGenerativeAIEmbeddings(model=EMBEDDING_MODEL)


class PostgresVectorStore:
    """Store and retrieve document chunks with PostgreSQL and pgvector."""

    def add_documents(self, documents: list[Document]) -> list[str]:
        if not documents:
            return []

        texts = [document.page_content for document in documents]
        vectors = embeddings.embed_documents(texts)
        ids = [str(uuid.uuid4()) for _ in documents]
        db = SessionLocal()

        try:
            for document_id, document, vector in zip(ids, documents, vectors):
                metadata = dict(document.metadata)
                db.add(
                    DocumentChunk(
                        id=document_id,
                        thread_id=metadata.get("thread_id", ""),
                        content=document.page_content,
                        cmetadata=metadata,
                        embedding=vector,
                    )
                )

            db.commit()
            return ids
        except Exception:
            db.rollback()
            raise
        finally:
            db.close()

    def similarity_search(
        self,
        query: str,
        k: int = 4,
        filter: dict | None = None,
    ) -> list[Document]:
        query_vector = embeddings.embed_query(query)
        db = SessionLocal()

        try:
            statement = select(DocumentChunk)

            if filter and "thread_id" in filter:
                statement = statement.where(
                    DocumentChunk.thread_id == filter["thread_id"]
                )

            statement = statement.order_by(
                DocumentChunk.embedding.l2_distance(query_vector)
            ).limit(k)

            chunks = db.scalars(statement).all()
            return [
                Document(
                    page_content=chunk.content,
                    metadata=dict(chunk.cmetadata),
                )
                for chunk in chunks
            ]
        finally:
            db.close()


vectorstore = PostgresVectorStore()
