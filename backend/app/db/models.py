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
    project_id = Column(String, nullable=True, index=True)
    created_at = Column(DateTime, default=utc_now_naive)
    updated_at = Column(DateTime, default=utc_now_naive)


class Project(Base):
    """A named workspace: its instructions apply to every chat inside it."""

    __tablename__ = "projects"

    id = Column(String, primary_key=True)
    client_id = Column(String, nullable=False, index=True)
    name = Column(String, nullable=False)
    instructions = Column(Text, nullable=False, default="")
    created_at = Column(DateTime, default=utc_now_naive)
    updated_at = Column(DateTime, default=utc_now_naive)


class UploadedFile(Base):
    """A document or image a client added to a chat (also the "library")."""

    __tablename__ = "uploaded_files"

    id = Column(String, primary_key=True)
    client_id = Column(String, nullable=False, index=True)
    thread_id = Column(String, nullable=False, index=True)
    filename = Column(String, nullable=False)
    stored_name = Column(String, nullable=False)
    kind = Column(String, nullable=False)  # "document" | "image"
    mime_type = Column(String, nullable=False)
    size = Column(Integer, nullable=False, default=0)
    chunks = Column(Integer, nullable=False, default=0)
    # "upload", "sketch" or "generated"
    origin = Column(String, nullable=False, default="upload")
    created_at = Column(DateTime, default=utc_now_naive)


class ChatMessage(Base):
    __tablename__ = "chat_messages"

    id = Column(Integer, primary_key=True, index=True)
    thread_id = Column(String, index=True)
    role = Column(String)
    content = Column(Text)
    attachments = Column(JSONB, nullable=True)
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
