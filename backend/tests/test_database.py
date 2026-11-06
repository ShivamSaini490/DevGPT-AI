from datetime import UTC, datetime, timedelta

from langgraph.checkpoint.base import empty_checkpoint

from app.db.models import (
    ChatMessage,
    Conversation,
    DocumentChunk,
    LongTermMemory,
)
from app.db.repository import (
    create_or_update_conversation,
    get_chat_history,
    list_conversations,
    rename_conversation,
    save_chat_message,
    save_memory,
    search_memory,
)
from app.db.session import SessionLocal
from app.services.cleanup import delete_conversation_data


def test_create_conversation_uses_message_as_title():
    create_or_update_conversation("thread-1", "A short first message")

    conversations = list_conversations()

    assert len(conversations) == 1
    assert conversations[0].thread_id == "thread-1"
    assert conversations[0].title == "A short first message"


def test_conversation_title_is_truncated_and_not_replaced_on_update():
    first_message = "x" * 50
    create_or_update_conversation("thread-1", first_message)
    create_or_update_conversation("thread-1", "A different title")

    conversations = list_conversations()

    assert len(conversations) == 1
    assert conversations[0].title == ("x" * 40) + "..."


def test_list_conversations_orders_most_recent_first():
    now = datetime.now(UTC).replace(tzinfo=None)
    db = SessionLocal()
    try:
        db.add_all(
            [
                Conversation(
                    thread_id="older",
                    title="Older",
                    created_at=now,
                    updated_at=now,
                ),
                Conversation(
                    thread_id="newer",
                    title="Newer",
                    created_at=now,
                    updated_at=now + timedelta(minutes=1),
                ),
            ]
        )
        db.commit()
    finally:
        db.close()

    assert [item.thread_id for item in list_conversations()] == ["newer", "older"]


def test_chat_messages_are_saved_in_chronological_order():
    create_or_update_conversation("thread-1")
    save_chat_message("thread-1", "user", "Hello")
    save_chat_message("thread-1", "assistant", "Hi")

    history = get_chat_history("thread-1")

    assert [(item.role, item.content) for item in history] == [
        ("user", "Hello"),
        ("assistant", "Hi"),
    ]


def test_memory_saved_in_one_thread_is_recalled_in_another_thread():
    assert search_memory("thread-1", "anything") == "No saved memory found."

    assert save_memory("thread-1", "Likes concise answers") == (
        "Memory saved successfully."
    )
    save_memory("thread-2", "Belongs to another thread")

    memories = search_memory("thread-3", "concise")
    assert memories.splitlines() == [
        "- Belongs to another thread",
        "- Likes concise answers",
    ]


def test_memory_recall_returns_only_the_20_most_recent_global_memories():
    now = datetime.now(UTC).replace(tzinfo=None)
    db = SessionLocal()
    try:
        db.add_all(
            [
                LongTermMemory(
                    thread_id=f"thread-{index % 3}",
                    memory=f"Memory {index}",
                    created_at=now + timedelta(seconds=index),
                )
                for index in range(21)
            ]
        )
        db.commit()
    finally:
        db.close()

    memories = search_memory("unrelated-thread", "anything").splitlines()

    assert len(memories) == 20
    assert memories[0] == "- Memory 20"
    assert memories[-1] == "- Memory 1"
    assert "- Memory 0" not in memories


def test_rename_conversation_updates_title_and_missing_returns_none():
    create_or_update_conversation("thread-1", "Original")

    renamed = rename_conversation("thread-1", "Updated title")

    assert renamed.thread_id == "thread-1"
    assert renamed.title == "Updated title"
    assert rename_conversation("missing", "Title") is None


def test_delete_conversation_removes_all_thread_data_and_checkpoint():
    from app.agents.graph import _CHECKPOINTER

    create_or_update_conversation("thread-delete", "Delete me")
    save_chat_message("thread-delete", "user", "Hello")
    save_memory("thread-delete", "Remember me")

    db = SessionLocal()
    try:
        db.add(
            DocumentChunk(
                id="chunk-delete",
                thread_id="thread-delete",
                content="Document content",
                cmetadata={"source": "test.txt"},
                embedding=[0.0] * 3072,
            )
        )
        db.commit()
    finally:
        db.close()

    checkpoint_config = {
        "configurable": {
            "thread_id": "thread-delete",
            "checkpoint_ns": "",
        }
    }
    _CHECKPOINTER.put(checkpoint_config, empty_checkpoint(), {}, {})
    assert _CHECKPOINTER.get_tuple(checkpoint_config) is not None

    assert delete_conversation_data("thread-delete") is True

    db = SessionLocal()
    try:
        assert db.query(Conversation).count() == 0
        assert db.query(ChatMessage).count() == 0
        assert db.query(LongTermMemory).count() == 0
        assert db.query(DocumentChunk).count() == 0
    finally:
        db.close()

    assert _CHECKPOINTER.get_tuple(checkpoint_config) is None
    assert delete_conversation_data("missing") is False


def test_delete_conversation_rolls_back_if_checkpoint_delete_fails(monkeypatch):
    import app.services.cleanup as cleanup_module

    create_or_update_conversation("thread-rollback", "Keep me")
    save_chat_message("thread-rollback", "user", "Still here")
    save_memory("thread-rollback", "Still remembered")

    def fail_checkpoint_delete(self, thread_id):
        raise RuntimeError("checkpoint delete failed")

    monkeypatch.setattr(
        cleanup_module.PostgresSaver,
        "delete_thread",
        fail_checkpoint_delete,
    )

    try:
        delete_conversation_data("thread-rollback")
    except RuntimeError as exc:
        assert str(exc) == "checkpoint delete failed"
    else:
        raise AssertionError("checkpoint failure should be propagated")

    db = SessionLocal()
    try:
        assert db.query(Conversation).count() == 1
        assert db.query(ChatMessage).count() == 1
        assert db.query(LongTermMemory).count() == 1
    finally:
        db.close()

