from datetime import datetime, timedelta
from threading import Event

from fastapi import FastAPI
from fastapi.testclient import TestClient
from langgraph.checkpoint.base import empty_checkpoint

from app.api.dependencies import LEGACY_CLIENT_ID
from app.db.models import (
    ChatMessage,
    ClientSession,
    Conversation,
    DocumentChunk,
    LongTermMemory,
)
from app.db.repository import (
    create_or_update_conversation,
    heartbeat_client_session,
    mark_client_session_closing,
    save_chat_message,
    save_memory,
)
from app.db.session import SessionLocal
from app.services.cleanup import delete_conversation_data, run_cleanup


CLIENT_ONE = "11111111-1111-4111-8111-111111111111"
CLIENT_TWO = "22222222-2222-4222-8222-222222222222"


def _conversation_exists(thread_id):
    db = SessionLocal()
    try:
        return (
            db.query(Conversation)
            .filter(Conversation.thread_id == thread_id)
            .first()
            is not None
        )
    finally:
        db.close()


def test_close_with_newer_heartbeat_is_not_deleted():
    now = datetime(2026, 1, 1, 12, 0, 0)
    create_or_update_conversation("active-thread", "Active", CLIENT_ONE)
    mark_client_session_closing(CLIENT_ONE, now)
    heartbeat_client_session(CLIENT_ONE, now + timedelta(seconds=1))

    run_cleanup(now + timedelta(seconds=60))

    assert _conversation_exists("active-thread")
    db = SessionLocal()
    try:
        assert db.get(ClientSession, CLIENT_ONE) is not None
    finally:
        db.close()


def test_close_without_new_heartbeat_is_deleted_after_grace_period():
    now = datetime(2026, 1, 1, 12, 0, 0)
    create_or_update_conversation("closed-thread", "Closed", CLIENT_ONE)
    mark_client_session_closing(CLIENT_ONE, now)

    run_cleanup(now + timedelta(seconds=46))

    assert not _conversation_exists("closed-thread")
    db = SessionLocal()
    try:
        assert db.get(ClientSession, CLIENT_ONE) is None
    finally:
        db.close()


def test_idle_client_is_deleted():
    now = datetime(2026, 1, 1, 12, 0, 0)
    create_or_update_conversation("idle-thread", "Idle", CLIENT_ONE)
    heartbeat_client_session(CLIENT_ONE, now)

    run_cleanup(now + timedelta(minutes=11))

    assert not _conversation_exists("idle-thread")


def test_retention_deletes_old_conversations_for_every_client():
    now = datetime(2026, 1, 2, 12, 0, 0)
    create_or_update_conversation("uuid-old", "Old", CLIENT_ONE)
    create_or_update_conversation("legacy-old", "Old", LEGACY_CLIENT_ID)
    create_or_update_conversation("null-old", "Old", None)

    db = SessionLocal()
    try:
        db.query(Conversation).update(
            {Conversation.created_at: now - timedelta(hours=25)}
        )
        db.commit()
    finally:
        db.close()

    run_cleanup(now)

    db = SessionLocal()
    try:
        assert db.query(Conversation).count() == 0
    finally:
        db.close()


def test_legacy_client_is_not_deleted_by_close_or_idle_rules():
    now = datetime(2026, 1, 2, 12, 0, 0)
    create_or_update_conversation(
        "legacy-active",
        "Legacy",
        LEGACY_CLIENT_ID,
    )
    mark_client_session_closing(
        LEGACY_CLIENT_ID,
        now - timedelta(hours=1),
    )

    run_cleanup(now)

    assert _conversation_exists("legacy-active")
    db = SessionLocal()
    try:
        assert db.get(ClientSession, LEGACY_CLIENT_ID) is not None
    finally:
        db.close()


def test_delete_conversation_removes_files_rows_and_checkpoint(
    tmp_path,
    monkeypatch,
):
    import app.services.cleanup as cleanup_module
    from app.agents.graph import _CHECKPOINTER

    monkeypatch.setattr(cleanup_module, "UPLOADS_DIR", tmp_path)
    stored_file = tmp_path / "stored.txt"
    stored_file.write_text("stored", encoding="utf-8")
    outside_file = tmp_path.parent / "outside.txt"
    outside_file.write_text("outside", encoding="utf-8")

    create_or_update_conversation("full-thread", "Full", CLIENT_TWO)
    save_chat_message("full-thread", "user", "Hello")
    save_memory("full-thread", "Remember")
    db = SessionLocal()
    try:
        db.add_all(
            [
                DocumentChunk(
                    id="chunk-safe",
                    thread_id="full-thread",
                    content="Safe",
                    cmetadata={"source": "stored.txt"},
                    embedding=[0.0] * 3072,
                ),
                DocumentChunk(
                    id="chunk-unsafe",
                    thread_id="full-thread",
                    content="Unsafe",
                    cmetadata={"source": "../outside.txt"},
                    embedding=[0.0] * 3072,
                ),
            ]
        )
        db.commit()
    finally:
        db.close()

    checkpoint_config = {
        "configurable": {
            "thread_id": "full-thread",
            "checkpoint_ns": "",
        }
    }
    _CHECKPOINTER.put(checkpoint_config, empty_checkpoint(), {}, {})

    assert delete_conversation_data("full-thread") is True
    assert not stored_file.exists()
    assert outside_file.exists()
    assert _CHECKPOINTER.get_tuple(checkpoint_config) is None

    db = SessionLocal()
    try:
        assert db.query(Conversation).count() == 0
        assert db.query(ChatMessage).count() == 0
        assert db.query(LongTermMemory).count() == 0
        assert db.query(DocumentChunk).count() == 0
    finally:
        db.close()

    outside_file.unlink()


def test_cleanup_lifespan_starts_and_stops_task(monkeypatch):
    import app.main as main_module

    started = Event()
    stopped = Event()

    async def fake_cleanup_loop():
        started.set()
        try:
            await main_module.asyncio.Event().wait()
        finally:
            stopped.set()

    monkeypatch.setattr(main_module, "ENABLE_CLEANUP_TASK", True)
    monkeypatch.setattr(main_module, "init_db", lambda: None)
    monkeypatch.setattr(main_module, "_cleanup_loop", fake_cleanup_loop)
    test_app = FastAPI(lifespan=main_module.lifespan)

    with TestClient(test_app):
        assert started.wait(timeout=1)

    assert stopped.wait(timeout=1)
