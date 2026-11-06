from app.db.models import (
    ChatMessage,
    ClientSession,
    Conversation,
    LongTermMemory,
    Project,
    UploadedFile,
)
from app.db.session import SessionLocal
from app.utils.time import utc_now_naive


def create_or_update_conversation(
    thread_id: str,
    first_message: str | None = None,
    client_id: str | None = None,
    project_id: str | None = None,
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
                project_id=project_id,
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


def save_chat_message(
    thread_id: str,
    role: str,
    content: str,
    attachments: list[dict] | None = None,
):
    db = SessionLocal()

    try:
        msg = ChatMessage(
            thread_id=thread_id,
            role=role,
            content=content,
            attachments=attachments or None,
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


def get_conversation(thread_id: str, client_id: str | None = None):
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
        if conversation is not None:
            db.expunge(conversation)
        return conversation
    finally:
        db.close()


def get_conversation_owner(thread_id: str) -> str | None:
    db = SessionLocal()

    try:
        return (
            db.query(Conversation.client_id)
            .filter(Conversation.thread_id == thread_id)
            .scalar()
        )
    finally:
        db.close()


# ---------- Projects ----------


def list_projects(client_id: str):
    db = SessionLocal()

    try:
        return (
            db.query(Project)
            .filter(Project.client_id == client_id)
            .order_by(Project.updated_at.desc())
            .all()
        )
    finally:
        db.close()


def get_project(project_id: str, client_id: str):
    db = SessionLocal()

    try:
        project = (
            db.query(Project)
            .filter(Project.id == project_id, Project.client_id == client_id)
            .first()
        )
        if project is not None:
            db.expunge(project)
        return project
    finally:
        db.close()


def create_project(project_id: str, client_id: str, name: str, instructions: str):
    db = SessionLocal()

    try:
        now = utc_now_naive()
        project = Project(
            id=project_id,
            client_id=client_id,
            name=name,
            instructions=instructions,
            created_at=now,
            updated_at=now,
        )
        db.add(project)
        db.commit()
        db.refresh(project)
        db.expunge(project)
        return project
    finally:
        db.close()


def update_project(
    project_id: str,
    client_id: str,
    name: str | None = None,
    instructions: str | None = None,
):
    db = SessionLocal()

    try:
        project = (
            db.query(Project)
            .filter(Project.id == project_id, Project.client_id == client_id)
            .first()
        )
        if project is None:
            return None

        if name is not None:
            project.name = name
        if instructions is not None:
            project.instructions = instructions
        project.updated_at = utc_now_naive()
        db.commit()
        db.refresh(project)
        db.expunge(project)
        return project
    finally:
        db.close()


def delete_project(project_id: str, client_id: str) -> bool:
    """Delete a project; its chats stay, moved back to "Recent"."""
    db = SessionLocal()

    try:
        project = (
            db.query(Project)
            .filter(Project.id == project_id, Project.client_id == client_id)
            .first()
        )
        if project is None:
            return False

        (
            db.query(Conversation)
            .filter(Conversation.project_id == project_id)
            .update({Conversation.project_id: None})
        )
        db.delete(project)
        db.commit()
        return True
    finally:
        db.close()


# ---------- Uploaded files / library ----------


def add_uploaded_file(**fields):
    db = SessionLocal()

    try:
        item = UploadedFile(created_at=utc_now_naive(), **fields)
        db.add(item)
        db.commit()
        db.refresh(item)
        db.expunge(item)
        return item
    finally:
        db.close()


def get_uploaded_file(file_id: str, client_id: str | None = None):
    db = SessionLocal()

    try:
        query = db.query(UploadedFile).filter(UploadedFile.id == file_id)
        if client_id is not None:
            query = query.filter(UploadedFile.client_id == client_id)
        item = query.first()
        if item is not None:
            db.expunge(item)
        return item
    finally:
        db.close()


def get_uploaded_files(file_ids: list[str], client_id: str):
    if not file_ids:
        return []

    db = SessionLocal()

    try:
        items = (
            db.query(UploadedFile)
            .filter(
                UploadedFile.id.in_(file_ids),
                UploadedFile.client_id == client_id,
            )
            .all()
        )
        by_id = {item.id: item for item in items}
        for item in items:
            db.expunge(item)
        return [by_id[file_id] for file_id in file_ids if file_id in by_id]
    finally:
        db.close()


def list_uploaded_files(client_id: str, query: str | None = None, limit: int = 100):
    db = SessionLocal()

    try:
        statement = db.query(UploadedFile).filter(
            UploadedFile.client_id == client_id
        )
        if query:
            statement = statement.filter(
                UploadedFile.filename.ilike(f"%{query.strip()}%")
            )
        return (
            statement.order_by(UploadedFile.created_at.desc())
            .limit(limit)
            .all()
        )
    finally:
        db.close()
