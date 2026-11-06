"""Tests for the composer "+" menu: files, library, projects, modes and tools."""

import json

import pytest
from langchain_core.messages import AIMessageChunk, ToolMessage

import app.api.routes.chat as chat_routes
import app.services.files as files_service
from app.agents.prompts import SYSTEM_PROMPT, build_system_prompt
from app.db.repository import create_or_update_conversation, get_chat_history
from app.tools.figma import parse_figma_reference
from app.tools.github import GitHubError, normalize_repo
from app.tools.registry import tools, tools_for_mode
from app.utils.streaming import extract_reasoning_from_chunk, tool_call_names


CLIENT_ID = "11111111-1111-4111-8111-111111111111"
OTHER_CLIENT = {"X-Client-Id": "22222222-2222-4222-8222-222222222222"}
PNG = b"\x89PNG\r\n\x1a\n" + b"\x00" * 32


def _sse(response):
    return [
        json.loads(line.removeprefix("data: "))
        for line in response.text.splitlines()
        if line.startswith("data: ")
    ]


@pytest.fixture
def uploads(monkeypatch, tmp_path):
    monkeypatch.setattr(files_service, "UPLOADS_DIR", tmp_path)
    monkeypatch.setattr(
        files_service,
        "add_document_to_rag",
        lambda file_path, thread_id: {"chunks": 3},
    )
    return tmp_path


# ---------- Files & library ----------


def test_upload_image_and_serve_content(client, uploads):
    response = client.post(
        "/files",
        data={"thread_id": "t-img"},
        files={"file": ("photo.png", PNG, "image/png")},
    )

    assert response.status_code == 200
    body = response.json()
    assert body["kind"] == "image"
    assert body["name"] == "photo.png"
    assert body["url"] == f"/files/{body['id']}/content"

    content = client.get(body["url"])
    assert content.status_code == 200
    assert content.content == PNG
    assert content.headers["content-type"] == "image/png"


def test_upload_rejects_fake_image_and_unknown_type(client, uploads):
    fake = client.post(
        "/files",
        data={"thread_id": "t-x"},
        files={"file": ("photo.png", b"not an image", "image/png")},
    )
    unknown = client.post(
        "/files",
        data={"thread_id": "t-x"},
        files={"file": ("tool.exe", b"MZ", "application/octet-stream")},
    )

    assert fake.status_code == 400
    assert unknown.status_code == 400
    assert list(uploads.iterdir()) == []


def test_library_lists_and_attaches_to_another_chat(client, uploads):
    uploaded = client.post(
        "/files",
        data={"thread_id": "t-a"},
        files={"file": ("notes.txt", b"hello", "text/plain")},
    ).json()
    assert uploaded["kind"] == "document"

    library = client.get("/files").json()["files"]
    assert [item["name"] for item in library] == ["notes.txt"]
    assert client.get("/files", headers=OTHER_CLIENT).json()["files"] == []

    attached = client.post(
        f"/files/{uploaded['id']}/attach",
        json={"thread_id": "t-b"},
    )
    assert attached.status_code == 200
    copy = attached.json()
    assert copy["id"] != uploaded["id"]
    assert copy["thread_id"] == "t-b"
    assert len(list(uploads.iterdir())) == 2

    # Another client cannot attach someone else's file.
    denied = client.post(
        f"/files/{uploaded['id']}/attach",
        json={"thread_id": "t-c"},
        headers=OTHER_CLIENT,
    )
    assert denied.status_code == 404


# ---------- Projects ----------


def test_project_crud_and_conversation_membership(client):
    created = client.post(
        "/projects",
        json={"name": "  Website  ", "instructions": "Answer in French."},
    )
    assert created.status_code == 201
    project = created.json()
    assert project["name"] == "Website"

    assert [p["id"] for p in client.get("/projects").json()["projects"]] == [project["id"]]
    assert client.get("/projects", headers=OTHER_CLIENT).json()["projects"] == []

    renamed = client.patch(f"/projects/{project['id']}", json={"name": "Site"})
    assert renamed.json()["name"] == "Site"
    assert renamed.json()["instructions"] == "Answer in French."

    create_or_update_conversation("t-proj", "hi", CLIENT_ID, project_id=project["id"])
    listed = client.get("/conversations").json()["conversations"]
    assert listed[0]["project_id"] == project["id"]

    assert client.delete(f"/projects/{project['id']}").json() == {"success": True}
    listed = client.get("/conversations").json()["conversations"]
    assert listed[0]["project_id"] is None
    assert client.delete(f"/projects/{project['id']}").status_code == 404


# ---------- Chat with modes, projects and attachments ----------


class RecordingAgent:
    def __init__(self, chunks=()):
        self.inputs = None
        self.chunks = chunks

    def stream(self, inputs, config, stream_mode):
        self.inputs = inputs
        yield from self.chunks or [
            (AIMessageChunk(content="ok"), {"langgraph_node": "chatbot"})
        ]


def test_chat_passes_mode_and_project_instructions(client, monkeypatch):
    agent = RecordingAgent()
    monkeypatch.setattr(chat_routes, "get_agent", lambda model: agent)
    project = client.post(
        "/projects", json={"name": "P", "instructions": "Be brief."}
    ).json()

    response = client.post(
        "/chat/stream",
        json={
            "message": "latest news",
            "thread_id": "t-mode",
            "mode": "web_search",
            "project_id": project["id"],
        },
    )

    assert response.status_code == 200
    assert agent.inputs["mode"] == "web_search"
    assert agent.inputs["instructions"] == "Be brief."


def test_chat_ignores_unknown_mode(client, monkeypatch):
    agent = RecordingAgent()
    monkeypatch.setattr(chat_routes, "get_agent", lambda model: agent)

    client.post(
        "/chat/stream",
        json={"message": "hi", "thread_id": "t-unknown", "mode": "hack"},
    )

    assert agent.inputs["mode"] == ""


def test_chat_describes_attached_images_and_saves_attachments(
    client, monkeypatch, uploads
):
    agent = RecordingAgent()
    monkeypatch.setattr(chat_routes, "get_agent", lambda model: agent)
    monkeypatch.setattr(
        chat_routes,
        "describe_images",
        lambda images, question: f"A cat ({len(images)} image)",
    )
    image = client.post(
        "/files",
        data={"thread_id": "t-vision"},
        files={"file": ("cat.png", PNG, "image/png")},
    ).json()

    response = client.post(
        "/chat/stream",
        json={
            "message": "What is this?",
            "thread_id": "t-vision",
            "attachments": [image["id"]],
        },
    )

    assert _sse(response)[0] == {"tool": "vision"}
    content = agent.inputs["messages"][0].content
    assert content.startswith("What is this?")
    assert "A cat (1 image)" in content

    history = get_chat_history("t-vision", CLIENT_ID)
    assert history[0].attachments == [
        {"id": image["id"], "name": "cat.png", "kind": "image", "url": image["url"]}
    ]
    api_history = client.get("/history/t-vision").json()["messages"]
    assert api_history[0]["attachments"][0]["name"] == "cat.png"


def test_chat_shows_generated_image_before_reply(client, monkeypatch):
    node = {"langgraph_node": "chatbot"}
    agent = RecordingAgent(
        [
            (
                AIMessageChunk(
                    content="",
                    id="m1",
                    tool_call_chunks=[
                        {"name": "generate_image", "args": "{}", "id": "c1", "index": 0}
                    ],
                ),
                node,
            ),
            (
                ToolMessage(
                    content="IMAGE_URL: /files/abc-123/content\nDone.",
                    tool_call_id="c1",
                ),
                {"langgraph_node": "tools"},
            ),
            (AIMessageChunk(content="Here it is.", id="m2"), node),
        ]
    )
    monkeypatch.setattr(chat_routes, "get_agent", lambda model: agent)

    response = client.post(
        "/chat/stream",
        json={"message": "a cat", "thread_id": "t-gen", "mode": "image"},
    )

    assert _sse(response) == [
        {"tool": "generate_image"},
        {"token": "![Generated image](/files/abc-123/content)\n\n"},
        {"token": "Here it is."},
        {"done": True},
    ]
    saved = get_chat_history("t-gen", CLIENT_ID)
    assert saved[-1].content.startswith("![Generated image](/files/abc-123/content)")


# ---------- Prompts, registry and helpers ----------


def test_build_system_prompt_adds_mode_and_project_instructions():
    assert build_system_prompt() == SYSTEM_PROMPT
    prompt = build_system_prompt("deep_research", "Use metric units.")
    assert "Mode: Deep research." in prompt
    assert prompt.endswith("Use metric units.\n")


def test_mode_tools_are_only_offered_in_their_mode():
    def names(mode):
        return {item.name for item in tools_for_mode(mode)}

    base = {item.name for item in tools}
    assert names(None) == base
    assert "generate_image" in names("image") - base
    assert "github_list_pull_requests" in names("github")
    assert "figma_get_design" in names("figma")
    assert names("web_search") == base


def test_stream_helpers_read_tool_names_and_reasoning():
    chunk = AIMessageChunk(
        content="",
        tool_call_chunks=[{"name": "calculator", "args": "", "id": "c", "index": 0}],
    )
    assert tool_call_names(chunk) == ["calculator"]
    assert tool_call_names(AIMessageChunk(content="x")) == []
    assert (
        extract_reasoning_from_chunk(
            AIMessageChunk(content="", additional_kwargs={"reasoning_content": "hmm"})
        )
        == "hmm"
    )


@pytest.mark.parametrize(
    ("value", "expected"),
    [
        ("octocat/Hello-World", "octocat/Hello-World"),
        ("https://github.com/octocat/Hello-World", "octocat/Hello-World"),
        ("https://github.com/octocat/Hello-World/pull/5", "octocat/Hello-World"),
        ("github.com/a/b.git", "a/b"),
    ],
)
def test_normalize_repo(value, expected):
    assert normalize_repo(value) == expected


def test_normalize_repo_rejects_garbage():
    with pytest.raises(GitHubError):
        normalize_repo("not a repo")


def test_parse_figma_reference():
    key, node = parse_figma_reference(
        "https://www.figma.com/design/AbCdEf1234567/My-App?node-id=12-34&t=x"
    )
    assert key == "AbCdEf1234567"
    assert node == "12:34"
    assert parse_figma_reference("AbCdEf1234567") == ("AbCdEf1234567", None)
    with pytest.raises(ValueError):
        parse_figma_reference("nope")
