from app.db.models import (
    ChatMessage,
    ClientSession,
    Conversation,
    LongTermMemory,
)
from app.db.session import SessionLocal
from app.utils.time import utc_now_naive


def create_or_update_conversation(
    thread_id: str,
    first_message: str | None = None,
    client_id: str | None = None,
):
    db = SessionLocal()

    try:
        conversation = (
            db.query(Conversation)
            .filter(Conversation.thread_id == thread_id)
            .first()
        )

        if conversation and conversation.client_id != client_id:
            return None

        if not conversation:
            title = "New Chat"

            if first_message:
                title = first_message.strip()[:40]
                if len(first_message.strip()) > 40:
                    title += "..."

            conversation = Conversation(
                thread_id=thread_id,
                client_id=client_id,
                title=title,
                created_at=utc_now_naive(),
                updated_at=utc_now_naive(),
            )

            db.add(conversation)
        else:
            conversation.updated_at = utc_now_naive()

        db.commit()
        db.refresh(conversation)
        db.expunge(conversation)
        return conversation
    finally:
        db.close()


def list_conversations(client_id: str | None = None):
    db = SessionLocal()

    try:
        return (
            db.query(Conversation)
            .filter(Conversation.client_id == client_id)
            .order_by(Conversation.updated_at.desc())
            .all()
        )
    finally:
        db.close()


def rename_conversation(
    thread_id: str,
    title: str,
    client_id: str | None = None,
):
    db = SessionLocal()

    try:
        conversation = (
            db.query(Conversation)
            .filter(
                Conversation.thread_id == thread_id,
                Conversation.client_id == client_id,
            )
            .first()
        )

        if conversation is None:
            return None

        conversation.title = title
        conversation.updated_at = utc_now_naive()
        db.commit()
        db.refresh(conversation)
        db.expunge(conversation)
        return conversation
    finally:
        db.close()


def conversation_owned_by_client(thread_id: str, client_id: str) -> bool:
    db = SessionLocal()

    try:
        return (
            db.query(Conversation.id)
            .filter(
                Conversation.thread_id == thread_id,
                Conversation.client_id == client_id,
            )
            .first()
            is not None
        )
    finally:
        db.close()


def save_chat_message(thread_id: str, role: str, content: str):
    db = SessionLocal()

    try:
        msg = ChatMessage(
            thread_id=thread_id,
            role=role,
            content=content,
            created_at=utc_now_naive(),
        )

        db.add(msg)

        conversation = (
            db.query(Conversation)
            .filter(Conversation.thread_id == thread_id)
            .first()
        )

        if conversation:
            conversation.updated_at = utc_now_naive()

        db.commit()
    finally:
        db.close()


def get_chat_history(thread_id: str, client_id: str | None = None):
    db = SessionLocal()

    try:
        conversation = (
            db.query(Conversation.id)
            .filter(
                Conversation.thread_id == thread_id,
                Conversation.client_id == client_id,
            )
            .first()
        )
        if conversation is None:
            return None

        return (
            db.query(ChatMessage)
            .filter(ChatMessage.thread_id == thread_id)
            .order_by(ChatMessage.created_at.asc())
            .all()
        )
    finally:
        db.close()


def heartbeat_client_session(client_id: str, now=None):
    now = now or utc_now_naive()
    db = SessionLocal()

    try:
        session = db.get(ClientSession, client_id)
        if session is None:
            session = ClientSession(
                client_id=client_id,
                last_seen=now,
                closing_at=None,
            )
            db.add(session)
        else:
            session.last_seen = now
            session.closing_at = None

        db.commit()
    finally:
        db.close()


def mark_client_session_closing(client_id: str, now=None):
    now = now or utc_now_naive()
    db = SessionLocal()

    try:
        session = db.get(ClientSession, client_id)
        if session is None:
            session = ClientSession(
                client_id=client_id,
                last_seen=now,
                closing_at=now,
            )
            db.add(session)
        else:
            session.last_seen = now
            session.closing_at = now

        db.commit()
    finally:
        db.close()


def save_memory(thread_id: str, memory: str):
    db = SessionLocal()

    try:
        item = LongTermMemory(
            thread_id=thread_id,
            memory=memory,
            created_at=utc_now_naive(),
        )

        db.add(item)
        db.commit()

        return "Memory saved successfully."
    finally:
        db.close()


# Memory is intentionally global until user authentication exists; at that
# point it must be scoped per user.
def search_memory(thread_id: str, query: str):
    db = SessionLocal()

    try:
        memories = (
            db.query(LongTermMemory)
            .order_by(LongTermMemory.created_at.desc())
            .limit(20)
            .all()
        )

        if not memories:
            return "No saved memory found."

        return "\n".join([f"- {m.memory}" for m in memories])
    finally:
        db.close()
