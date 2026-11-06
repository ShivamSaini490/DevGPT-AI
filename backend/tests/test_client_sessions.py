from app.api.dependencies import LEGACY_CLIENT_ID
from app.db.models import ClientSession, Conversation
from app.db.repository import create_or_update_conversation
from app.db.session import SessionLocal
import app.api.routes.documents as document_routes


CLIENT_ONE = "11111111-1111-4111-8111-111111111111"
CLIENT_TWO = "22222222-2222-4222-8222-222222222222"


def test_client_id_header_is_required_and_must_be_a_uuid(
    unauthenticated_client,
):
    missing = unauthenticated_client.get("/conversations")
    invalid = unauthenticated_client.get(
        "/conversations",
        headers={"X-Client-Id": "not-a-uuid"},
    )
    missing_close = unauthenticated_client.post("/sessions/close")
    invalid_close = unauthenticated_client.post(
        "/sessions/close?client_id=not-a-uuid"
    )

    assert missing.status_code == 400
    assert missing.json() == {"error": "Client ID is required."}
    assert invalid.status_code == 400
    assert invalid.json() == {"error": "Client ID is required."}
    assert missing_close.status_code == 400
    assert missing_close.json() == {"error": "Client ID is required."}
    assert invalid_close.status_code == 400
    assert invalid_close.json() == {"error": "Client ID is required."}


def test_require_client_id_false_uses_legacy_fallback(
    unauthenticated_client,
    monkeypatch,
):
    import app.api.dependencies as dependencies

    monkeypatch.setattr(dependencies, "REQUIRE_CLIENT_ID", False)
    create_or_update_conversation(
        "legacy-thread",
        "Legacy chat",
        LEGACY_CLIENT_ID,
    )

    response = unauthenticated_client.get("/conversations")

    assert response.status_code == 200
    assert response.json()["conversations"][0]["thread_id"] == (
        "legacy-thread"
    )


def test_conversation_routes_are_isolated_by_client(client):
    create_or_update_conversation("owned-thread", "Private", CLIENT_ONE)

    owner_list = client.get("/conversations")
    other_headers = {"X-Client-Id": CLIENT_TWO}
    other_list = client.get("/conversations", headers=other_headers)
    other_history = client.get(
        "/history/owned-thread",
        headers=other_headers,
    )
    other_rename = client.patch(
        "/conversations/owned-thread",
        headers=other_headers,
        json={"title": "Not allowed"},
    )
    other_delete = client.delete(
        "/conversations/owned-thread",
        headers=other_headers,
    )
    other_chat = client.post(
        "/chat/stream",
        headers=other_headers,
        json={"message": "Hello", "thread_id": "owned-thread"},
    )

    assert [
        item["thread_id"]
        for item in owner_list.json()["conversations"]
    ] == ["owned-thread"]
    assert other_list.json() == {"conversations": []}
    for response in (
        other_history,
        other_rename,
        other_delete,
        other_chat,
    ):
        assert response.status_code == 404
        assert response.json() == {"error": "Conversation not found."}

    db = SessionLocal()
    try:
        assert db.query(Conversation).count() == 1
    finally:
        db.close()


def test_upload_rejects_thread_owned_by_another_client(
    client,
    monkeypatch,
    tmp_path,
):
    create_or_update_conversation("upload-owned", "Private", CLIENT_ONE)
    monkeypatch.setattr(document_routes, "UPLOADS_DIR", tmp_path)
    indexed = []
    monkeypatch.setattr(
        document_routes,
        "add_document_to_rag",
        lambda **kwargs: indexed.append(kwargs),
    )

    response = client.post(
        "/upload",
        headers={"X-Client-Id": CLIENT_TWO},
        data={"thread_id": "upload-owned"},
        files={"file": ("notes.txt", b"private", "text/plain")},
    )

    assert response.status_code == 404
    assert response.json() == {"error": "Conversation not found."}
    assert indexed == []
    assert list(tmp_path.iterdir()) == []


def test_close_marks_session_without_deleting_conversation(client):
    create_or_update_conversation("close-thread", "Close", CLIENT_ONE)

    response = client.post(f"/sessions/close?client_id={CLIENT_ONE}")

    assert response.status_code == 204
    assert response.content == b""
    db = SessionLocal()
    try:
        session = db.get(ClientSession, CLIENT_ONE)
        assert session.closing_at is not None
        assert db.query(Conversation).count() == 1
    finally:
        db.close()


def test_heartbeat_clears_closing_at(client):
    client.post(f"/sessions/close?client_id={CLIENT_ONE}")

    response = client.post("/sessions/heartbeat")

    assert response.status_code == 200
    assert response.json() == {"success": True}
    db = SessionLocal()
    try:
        session = db.get(ClientSession, CLIENT_ONE)
        assert session.closing_at is None
        assert session.last_seen is not None
    finally:
        db.close()
