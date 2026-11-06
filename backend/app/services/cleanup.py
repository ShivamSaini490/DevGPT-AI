import logging
from datetime import datetime, timedelta
from pathlib import Path

from langgraph.checkpoint.postgres import PostgresSaver
from sqlalchemy import delete, select

from app.api.dependencies import LEGACY_CLIENT_ID
from app.core.config import (
    CHAT_RETENTION_HOURS,
    CLOSE_GRACE_SECONDS,
    IDLE_TIMEOUT_MINUTES,
)
from app.core.paths import UPLOADS_DIR
from app.db.models import (
    ChatMessage,
    ClientSession,
    Conversation,
    DocumentChunk,
    LongTermMemory,
)
from app.db.session import SessionLocal


logger = logging.getLogger(__name__)


def _delete_uploaded_sources(sources: set[str]) -> None:
    uploads_dir = UPLOADS_DIR.resolve()

    for source in sources:
        candidate = (uploads_dir / source).resolve()
        if not candidate.is_relative_to(uploads_dir):
            continue

        try:
            candidate.unlink(missing_ok=True)
        except OSError:
            logger.exception("Failed to delete uploaded file %s", candidate)


def delete_conversation_data(thread_id: str) -> bool:
    db = SessionLocal()
    sources: set[str] = set()

    try:
        with db.begin():
            conversation = db.scalar(
                select(Conversation).where(
                    Conversation.thread_id == thread_id
                )
            )
            if conversation is None:
                return False

            metadata_rows = db.scalars(
                select(DocumentChunk.cmetadata).where(
                    DocumentChunk.thread_id == thread_id
                )
            ).all()
            sources = {
                source
                for metadata in metadata_rows
                if isinstance(metadata, dict)
                and isinstance((source := metadata.get("source")), str)
                and source
            }

            for model in (ChatMessage, LongTermMemory, DocumentChunk):
                db.execute(delete(model).where(model.thread_id == thread_id))

            db.execute(
                delete(Conversation).where(
                    Conversation.thread_id == thread_id
                )
            )

            raw_connection = db.connection().connection.driver_connection
            PostgresSaver(raw_connection).delete_thread(thread_id)
    finally:
        db.close()

    _delete_uploaded_sources(sources)
    return True


def run_cleanup(now: datetime) -> None:
    db = SessionLocal()

    try:
        sessions = db.scalars(select(ClientSession)).all()
        closing_cutoff = now - timedelta(seconds=CLOSE_GRACE_SECONDS)
        idle_cutoff = now - timedelta(minutes=IDLE_TIMEOUT_MINUTES)

        expired_client_ids = {
            session.client_id
            for session in sessions
            if session.client_id != LEGACY_CLIENT_ID
            and not (
                session.closing_at is not None
                and session.last_seen > session.closing_at
            )
            and (
                (
                    session.closing_at is not None
                    and session.closing_at < closing_cutoff
                    and session.last_seen <= session.closing_at
                )
                or session.last_seen < idle_cutoff
            )
        }

        client_threads = db.scalars(
            select(Conversation.thread_id).where(
                Conversation.client_id.in_(expired_client_ids)
            )
        ).all() if expired_client_ids else []

        retention_cutoff = now - timedelta(hours=CHAT_RETENTION_HOURS)
        old_threads = db.scalars(
            select(Conversation.thread_id).where(
                Conversation.created_at < retention_cutoff
            )
        ).all()
    finally:
        db.close()

    for thread_id in set(client_threads) | set(old_threads):
        delete_conversation_data(thread_id)

    if expired_client_ids:
        db = SessionLocal()
        try:
            with db.begin():
                db.execute(
                    delete(ClientSession).where(
                        ClientSession.client_id.in_(expired_client_ids)
                    )
                )
        finally:
            db.close()
