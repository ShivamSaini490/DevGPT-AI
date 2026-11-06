from sqlalchemy import Column, DateTime, Integer, String, Text
from sqlalchemy.dialects.postgresql import JSONB
from pgvector.sqlalchemy import VECTOR

from app.core.config import EMBEDDING_DIMENSIONS
from app.db.session import Base
from app.utils.time import utc_now_naive


class Conversation(Base):
    __tablename__ = "conversations"

    id = Column(Integer, primary_key=True, index=True)
    thread_id = Column(String, unique=True, index=True)
    client_id = Column(String, nullable=True, index=True)
    title = Column(String, default="New Chat")
    created_at = Column(DateTime, default=utc_now_naive)
    updated_at = Column(DateTime, default=utc_now_naive)


class ChatMessage(Base):
    __tablename__ = "chat_messages"

    id = Column(Integer, primary_key=True, index=True)
    thread_id = Column(String, index=True)
    role = Column(String)
    content = Column(Text)
    created_at = Column(DateTime, default=utc_now_naive)


class LongTermMemory(Base):
    __tablename__ = "long_term_memory"

    id = Column(Integer, primary_key=True, index=True)
    thread_id = Column(String, index=True)
    memory = Column(Text)
    created_at = Column(DateTime, default=utc_now_naive)


class DocumentChunk(Base):
    __tablename__ = "document_chunks"

    id = Column(String, primary_key=True)
    thread_id = Column(String, index=True, nullable=False)
    content = Column(Text, nullable=False)
    cmetadata = Column(JSONB, nullable=False, default=dict)
    embedding = Column(VECTOR(EMBEDDING_DIMENSIONS), nullable=False)


class ClientSession(Base):
    __tablename__ = "client_sessions"

    client_id = Column(String, primary_key=True)
    last_seen = Column(DateTime, nullable=False)
    closing_at = Column(DateTime, nullable=True)
