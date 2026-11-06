import json
import re
from pathlib import Path

from langchain_core.messages import AIMessageChunk, ToolMessage

from app.db.repository import create_or_update_conversation, save_chat_message
import app.api.routes.chat as chat_routes
import app.api.routes.documents as document_routes


CLIENT_ID = "11111111-1111-4111-8111-111111111111"


def _sse_payloads(response):
    return [
        json.loads(line.removeprefix("data: "))
        for line in response.text.splitlines()
        if line.startswith("data: ")
    ]


def test_homepage_and_static_assets_are_served(client):
    home = client.get("/")
    openapi = client.get("/openapi.json")

    assert home.status_code == 200
    assert "DevGPT" in home.text

    # The chat page is a client-side route of the same app.
    chat_page = client.get("/chat")
    assert chat_page.status_code == 200
    assert chat_page.text == home.text

    # When the React build is present, every asset index.html references
    # must be served from /static.
    asset_paths = re.findall(r'(?:src|href)="(/static/[^"]+)"', home.text)
    for asset_path in asset_paths:
        assert client.get(asset_path).status_code == 200, asset_path

    assert openapi.json()["info"]["title"] == "DevGPT API"
    assert openapi.json()["info"]["version"] == "0.1.0"

    schema = openapi.json()
    assert schema["paths"]["/chat/stream"]["post"]["requestBody"]["content"][
        "application/json"
    ]["schema"]["$ref"] == "#/components/schemas/ChatRequest"
    assert schema["paths"]["/conversations"]["get"]["responses"]["200"][
        "content"
    ]["application/json"]["schema"]["$ref"] == (
        "#/components/schemas/ConversationListResponse"
    )
    assert schema["paths"]["/history/{thread_id}"]["get"]["responses"]["200"][
        "content"
    ]["application/json"]["schema"]["$ref"] == (
        "#/components/schemas/HistoryResponse"
    )
    assert schema["paths"]["/upload"]["post"]["responses"]["200"]["content"][
        "application/json"
    ]["schema"]["$ref"] == "#/components/schemas/UploadResponse"


def test_cors_preflight_allows_configured_react_origin(client):
    response = client.options(
        "/chat/stream",
        headers={
            "Origin": "http://localhost:5173",
            "Access-Control-Request-Method": "POST",
            "Access-Control-Request-Headers": "content-type,x-client-id",
        },
    )

    assert response.status_code == 200
    assert response.headers["access-control-allow-origin"] == (
        "http://localhost:5173"
    )
    assert response.headers["access-control-allow-credentials"] == "true"
    assert "POST" in response.headers["access-control-allow-methods"]
    assert "content-type" in response.headers["access-control-allow-headers"].lower()
    assert "x-client-id" in response.headers["access-control-allow-headers"].lower()


def test_cors_preflight_rejects_disallowed_origin(client):
    response = client.options(
        "/chat/stream",
        headers={
            "Origin": "https://untrusted.example",
            "Access-Control-Request-Method": "POST",
        },
    )

    assert response.status_code == 400
    assert "access-control-allow-origin" not in response.headers


def test_conversation_and_history_endpoints(client):
    create_or_update_conversation("thread-1", "Hello DevGPT", CLIENT_ID)
    save_chat_message("thread-1", "user", "Hello")
    save_chat_message("thread-1", "assistant", "Hi")

    conversations = client.get("/conversations")
    history = client.get("/history/thread-1")

    assert conversations.status_code == 200
    assert conversations.json()["conversations"][0]["thread_id"] == "thread-1"
    assert conversations.json()["conversations"][0]["title"] == "Hello DevGPT"
    assert history.status_code == 200
    assert history.json() == {
        "messages": [
            {"role": "user", "content": "Hello", "attachments": []},
            {"role": "assistant", "content": "Hi", "attachments": []},
        ]
    }


def test_conversation_rename_and_delete_endpoints(client):
    create_or_update_conversation("thread-1", "Original title", CLIENT_ID)
    save_chat_message("thread-1", "user", "Hello")

    renamed = client.patch(
        "/conversations/thread-1",
        json={"title": "  Renamed conversation  "},
    )
    deleted = client.delete("/conversations/thread-1")

    assert renamed.status_code == 200
    assert renamed.json()["thread_id"] == "thread-1"
    assert renamed.json()["title"] == "Renamed conversation"
    assert deleted.status_code == 200
    assert deleted.json() == {"success": True}
    missing_history = client.get("/history/thread-1")
    assert missing_history.status_code == 404
    assert missing_history.json() == {"error": "Conversation not found."}


def test_conversation_rename_and_delete_return_404_when_missing(client):
    renamed = client.patch(
        "/conversations/missing",
        json={"title": "New title"},
    )
    deleted = client.delete("/conversations/missing")

    assert renamed.status_code == 404
    assert renamed.json() == {"error": "Conversation not found."}
    assert deleted.status_code == 404
    assert deleted.json() == {"error": "Conversation not found."}


def test_chat_rejects_invalid_json_and_empty_message(client):
    invalid_json = client.post(
        "/chat/stream",
        content="not-json",
        headers={"content-type": "application/json"},
    )
    empty_message = client.post(
        "/chat/stream",
        json={"message": "   ", "thread_id": "thread-1"},
    )
    non_string_message = client.post(
        "/chat/stream",
        json={"message": 123, "thread_id": "thread-1"},
    )
    missing_thread = client.post(
        "/chat/stream",
        json={"message": "hello", "thread_id": ""},
    )
    non_object_json = client.post(
        "/chat/stream",
        json=["not", "an", "object"],
    )

    assert invalid_json.status_code == 400
    assert invalid_json.json() == {"error": "Invalid JSON body."}
    assert empty_message.status_code == 400
    assert empty_message.json() == {"error": "Message is required."}
    assert non_string_message.status_code == 400
    assert non_string_message.json() == {"error": "Message is required."}
    assert missing_thread.status_code == 400
    assert missing_thread.json() == {"error": "Thread ID is required."}
    assert non_object_json.status_code == 400
    assert non_object_json.json() == {"error": "Invalid JSON body."}


def test_chat_streams_only_ai_text_and_saves_final_answer(client, monkeypatch):
    class FakeAgent:
        def stream(self, inputs, config, stream_mode):
            assert inputs["messages"][0].content == "Question"
            assert config == {"configurable": {"thread_id": "thread-1"}}
            assert stream_mode == "messages"
            yield AIMessageChunk(content="Hello "), {"langgraph_node": "chatbot"}
            yield ToolMessage(content="hidden", tool_call_id="call-1"), {
                "langgraph_node": "tools"
            }
            yield AIMessageChunk(content="world"), {"langgraph_node": "chatbot"}

    saved_messages = []
    conversations = []
    monkeypatch.setattr(chat_routes, "get_agent", lambda model: FakeAgent())
    def fake_create_conversation(thread_id, message, client_id):
        conversations.append((thread_id, message, client_id))
        return object()

    monkeypatch.setattr(
        chat_routes,
        "create_or_update_conversation",
        fake_create_conversation,
    )
    monkeypatch.setattr(
        chat_routes,
        "save_chat_message",
        lambda thread_id, role, content: saved_messages.append(
            (thread_id, role, content)
        ),
    )

    response = client.post(
        "/chat/stream",
        headers={"Origin": "http://localhost:5173"},
        json={
            "message": "Question",
            "thread_id": "thread-1",
            "model": "openai/gpt-oss-120b",
        },
    )

    assert response.status_code == 200
    assert response.headers["access-control-allow-origin"] == (
        "http://localhost:5173"
    )
    assert response.headers["access-control-allow-credentials"] == "true"
    assert response.headers["content-type"].startswith("text/event-stream")
    assert _sse_payloads(response) == [
        {"token": "Hello "},
        {"token": "world"},
        {"done": True},
    ]
    assert conversations == [("thread-1", "Question", CLIENT_ID)]
    assert saved_messages == [
        ("thread-1", "user", "Question"),
        ("thread-1", "assistant", "Hello world"),
    ]


def test_chat_withdraws_text_streamed_before_a_tool_call(client, monkeypatch):
    """The model sometimes 'thinks aloud' in content before calling a tool.

    That text is streamed before the tool call is visible, so the server must
    withdraw it with a `replace` event and keep it out of the saved answer.
    """

    class ThinkingAloudAgent:
        def stream(self, inputs, config, stream_mode):
            node = {"langgraph_node": "chatbot"}
            yield AIMessageChunk(content="User asks 2*4. ", id="m1"), node
            yield AIMessageChunk(content="Use calculator.", id="m1"), node
            yield AIMessageChunk(
                content="",
                id="m1",
                tool_call_chunks=[
                    {"name": "calculator", "args": "{}", "id": "c1", "index": 0}
                ],
            ), node
            yield ToolMessage(content="8", tool_call_id="c1"), {"langgraph_node": "tools"}
            yield AIMessageChunk(content="The answer is ", id="m2"), node
            yield AIMessageChunk(content="8.", id="m2"), node

    saved_messages = []
    monkeypatch.setattr(chat_routes, "get_agent", lambda model: ThinkingAloudAgent())
    monkeypatch.setattr(
        chat_routes,
        "create_or_update_conversation",
        lambda thread_id, message, client_id: object(),
    )
    monkeypatch.setattr(
        chat_routes,
        "save_chat_message",
        lambda thread_id, role, content: saved_messages.append((role, content)),
    )

    response = client.post(
        "/chat/stream",
        json={"message": "2*4", "thread_id": "thread-think", "model": None},
    )

    assert _sse_payloads(response) == [
        {"token": "User asks 2*4. "},
        {"token": "Use calculator."},
        {"replace": ""},
        {"tool": "calculator"},
        {"token": "The answer is "},
        {"token": "8."},
        {"done": True},
    ]
    assert saved_messages == [("user", "2*4"), ("assistant", "The answer is 8.")]


def test_chat_stream_reports_agent_errors(client, monkeypatch):
    class FailingAgent:
        def stream(self, inputs, config, stream_mode):
            raise RuntimeError("agent failed")
            yield

    monkeypatch.setattr(chat_routes, "get_agent", lambda model: FailingAgent())
    monkeypatch.setattr(
        chat_routes,
        "create_or_update_conversation",
        lambda *args: object(),
    )
    monkeypatch.setattr(chat_routes, "save_chat_message", lambda *args: None)

    response = client.post(
        "/chat/stream",
        json={"message": "Question", "thread_id": "thread-1"},
    )

    assert response.status_code == 200
    assert _sse_payloads(response) == [
        {"error": "agent failed"},
        {"done": True},
    ]


def test_chat_stream_returns_friendly_error_for_model_rate_limit(
    client,
    monkeypatch,
    caplog,
):
    class RateLimitedAgent:
        def stream(self, inputs, config, stream_mode):
            raise RuntimeError(
                "413 Request too large for tokens per minute (TPM): "
                "Limit 8000, Requested 9629"
            )
            yield

    monkeypatch.setattr(chat_routes, "get_agent", lambda model: RateLimitedAgent())
    monkeypatch.setattr(
        chat_routes,
        "create_or_update_conversation",
        lambda *args: object(),
    )
    monkeypatch.setattr(chat_routes, "save_chat_message", lambda *args: None)

    with caplog.at_level("ERROR", logger=chat_routes.__name__):
        response = client.post(
            "/chat/stream",
            json={"message": "Question", "thread_id": "thread-1"},
        )

    assert response.status_code == 200
    assert _sse_payloads(response) == [
        {"error": chat_routes.MODEL_RATE_LIMIT_MESSAGE},
        {"done": True},
    ]
    assert "413 Request too large" in caplog.text


def test_chat_uses_default_model_for_non_string_model(client, monkeypatch):
    captured = {}

    class FakeAgent:
        def stream(self, inputs, config, stream_mode):
            yield AIMessageChunk(content="ok"), {"langgraph_node": "chatbot"}

    def fake_get_agent(model):
        captured["model"] = model
        return FakeAgent()

    monkeypatch.setattr(chat_routes, "get_agent", fake_get_agent)
    monkeypatch.setattr(
        chat_routes,
        "create_or_update_conversation",
        lambda *args: object(),
    )
    monkeypatch.setattr(chat_routes, "save_chat_message", lambda *args: None)

    response = client.post(
        "/chat/stream",
        json={"message": "Question", "thread_id": "thread-1", "model": 123},
    )

    assert response.status_code == 200
    assert captured["model"] == chat_routes.DEFAULT_MODEL


def test_upload_rejects_unsupported_file(client, monkeypatch, tmp_path):
    monkeypatch.setattr(document_routes, "UPLOADS_DIR", tmp_path)

    response = client.post(
        "/upload",
        data={"thread_id": "thread-1"},
        files={"file": ("malware.exe", b"content", "application/octet-stream")},
    )

    assert response.status_code == 400
    assert response.json()["success"] is False
    assert list(tmp_path.iterdir()) == []


def test_upload_saves_file_and_indexes_document(client, monkeypatch, tmp_path):
    captured = {}
    monkeypatch.setattr(document_routes, "UPLOADS_DIR", tmp_path)
    monkeypatch.setattr(
        document_routes,
        "create_or_update_conversation",
        lambda thread_id, message, client_id: (
            captured.update(
                {"conversation": (thread_id, message, client_id)}
            )
            or object()
        ),
    )

    def fake_add_document(file_path, thread_id):
        captured["file_path"] = Path(file_path)
        captured["thread_id"] = thread_id
        return {"filename": Path(file_path).name, "chunks": 2}

    monkeypatch.setattr(document_routes, "add_document_to_rag", fake_add_document)

    response = client.post(
        "/upload",
        data={"thread_id": "thread-1"},
        files={"file": ("my notes.txt", b"document text", "text/plain")},
    )

    assert response.status_code == 200
    assert response.json() == {
        "success": True,
        "message": "Uploaded my notes.txt and created 2 chunks.",
    }
    assert captured["file_path"].read_bytes() == b"document text"
    assert captured["file_path"].parent == tmp_path
    assert captured["file_path"].name.endswith("_my_notes.txt")
    assert captured["thread_id"] == "thread-1"
    assert captured["conversation"] == (
        "thread-1",
        "Uploaded document",
        CLIENT_ID,
    )


def test_upload_rejects_file_larger_than_configured_limit(
    client,
    monkeypatch,
    tmp_path,
):
    monkeypatch.setattr(document_routes, "UPLOADS_DIR", tmp_path)
    monkeypatch.setattr(document_routes, "MAX_UPLOAD_MB", 1)
    indexed = []
    monkeypatch.setattr(
        document_routes,
        "add_document_to_rag",
        lambda **kwargs: indexed.append(kwargs),
    )

    response = client.post(
        "/upload",
        data={"thread_id": "thread-1"},
        files={"file": ("large.txt", b"x" * (1024 * 1024 + 1), "text/plain")},
    )

    assert response.status_code == 413
    assert response.json() == {
        "success": False,
        "message": "File is too large. Maximum size is 1 MB.",
    }
    assert indexed == []
    assert list(tmp_path.iterdir()) == []


def test_upload_filename_cannot_escape_upload_directory(client, monkeypatch, tmp_path):
    captured = {}
    monkeypatch.setattr(document_routes, "UPLOADS_DIR", tmp_path)
    monkeypatch.setattr(
        document_routes,
        "create_or_update_conversation",
        lambda *args: object(),
    )

    def fake_add_document(file_path, thread_id):
        captured["file_path"] = Path(file_path).resolve()
        return {"filename": Path(file_path).name, "chunks": 1}

    monkeypatch.setattr(document_routes, "add_document_to_rag", fake_add_document)

    response = client.post(
        "/upload",
        data={"thread_id": "thread-1"},
        files={"file": ("../../../escape.txt", b"safe", "text/plain")},
    )

    assert response.status_code == 200
    assert captured["file_path"].is_relative_to(tmp_path.resolve())
    assert captured["file_path"].parent == tmp_path.resolve()


def test_failed_document_indexing_removes_partial_upload(client, monkeypatch, tmp_path):
    monkeypatch.setattr(document_routes, "UPLOADS_DIR", tmp_path)
    monkeypatch.setattr(
        document_routes,
        "create_or_update_conversation",
        lambda *args: object(),
    )
    monkeypatch.setattr(
        document_routes,
        "add_document_to_rag",
        lambda **kwargs: (_ for _ in ()).throw(RuntimeError("index failed")),
    )

    response = client.post(
        "/upload",
        data={"thread_id": "thread-1"},
        files={"file": ("notes.txt", b"content", "text/plain")},
    )

    assert response.status_code == 500
    assert response.json() == {"success": False, "message": "index failed"}
    assert list(tmp_path.iterdir()) == []

