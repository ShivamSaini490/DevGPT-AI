"""GitHub, Figma, image generation, vision and library-copy behaviour (no network)."""

import json

import httpx
import pytest
from langchain_core.messages import AIMessage, HumanMessage

import app.services.files as files_service
import app.tools.figma as figma_module
import app.tools.github as github_module
import app.tools.image_generation as image_module
from app.db.models import DocumentChunk
from app.db.repository import create_or_update_conversation
from app.db.session import SessionLocal


CLIENT_ID = "11111111-1111-4111-8111-111111111111"
PNG = b"\x89PNG\r\n\x1a\n" + b"\x00" * 32
CONFIG = {"configurable": {"thread_id": "t-int"}}


def _response(status, payload=None, content=None, url="https://example.test"):
    request = httpx.Request("GET", url)
    if content is not None:
        return httpx.Response(status, content=content, request=request)
    return httpx.Response(status, json=payload, request=request)


@pytest.fixture
def uploads(monkeypatch, tmp_path):
    monkeypatch.setattr(files_service, "UPLOADS_DIR", tmp_path)
    monkeypatch.setattr(
        files_service, "add_document_to_rag", lambda file_path, thread_id: {"chunks": 1}
    )
    return tmp_path


# ---------- GitHub ----------


@pytest.fixture
def github_api(monkeypatch):
    routes = {}
    calls = []

    def fake_request(method, url, headers, timeout, **kwargs):
        calls.append((method, url, kwargs))
        path = url.removeprefix(github_module.GITHUB_API_URL)
        status, payload = routes.get((method, path), (404, {"message": "Not Found"}))
        return _response(status, payload, url=url)

    monkeypatch.setattr(github_module.httpx, "request", fake_request)
    return routes, calls


def test_github_repo_overview_and_lists(github_api):
    routes, _ = github_api
    routes[("GET", "/repos/o/r")] = (
        200,
        {"full_name": "o/r", "stargazers_count": 5, "default_branch": "main"},
    )
    routes[("GET", "/repos/o/r/pulls")] = (
        200,
        [{"number": 1, "title": "Fix", "user": {"login": "a"}, "labels": [{"name": "bug"}]}],
    )
    routes[("GET", "/repos/o/r/issues")] = (
        200,
        [
            {"number": 2, "title": "Issue", "user": {"login": "b"}},
            {"number": 3, "title": "PR", "pull_request": {}},
        ],
    )
    routes[("GET", "/repos/o/r/actions/runs")] = (
        200,
        {"workflow_runs": [{"name": "CI", "conclusion": "failure"}]},
    )

    overview = json.loads(github_module.github_repo_overview.invoke({"repo": "https://github.com/o/r"}))
    assert overview["stars"] == 5
    assert overview["latest_release"] is None

    pulls = json.loads(github_module.github_list_pull_requests.invoke({"repo": "o/r"}))
    assert pulls[0]["labels"] == ["bug"]

    issues = json.loads(github_module.github_list_issues.invoke({"repo": "o/r"}))
    assert [i["number"] for i in issues] == [2]

    runs = json.loads(github_module.github_ci_status.invoke({"repo": "o/r", "branch": "main"}))
    assert runs[0]["conclusion"] == "failure"


def test_github_pull_request_details(github_api):
    routes, _ = github_api
    routes[("GET", "/repos/o/r/pulls/7")] = (
        200,
        {"number": 7, "title": "T", "body": "x" * 2000, "head": {"sha": "abc"}},
    )
    routes[("GET", "/repos/o/r/pulls/7/files")] = (200, [{"filename": "a.py", "patch": "+1"}])
    routes[("GET", "/repos/o/r/pulls/7/reviews")] = (200, [{"user": {"login": "r"}, "state": "APPROVED"}])
    routes[("GET", "/repos/o/r/commits/abc/check-runs")] = (
        200,
        {"check_runs": [{"name": "test", "conclusion": "success"}]},
    )

    details = json.loads(
        github_module.github_pull_request_details.invoke({"repo": "o/r", "number": 7})
    )
    assert details["files"][0]["file"] == "a.py"
    assert details["checks"][0]["conclusion"] == "success"
    assert len(details["body"]) == 1200


def test_github_errors_are_reported_as_text(github_api, monkeypatch):
    routes, _ = github_api
    routes[("GET", "/repos/o/private")] = (403, {"message": "rate limited"})

    assert "Not found" in github_module.github_repo_overview.invoke({"repo": "o/missing"})
    assert "rate limited" in github_module.github_repo_overview.invoke({"repo": "o/private"})
    assert "not a repository" in github_module.github_list_issues.invoke({"repo": "nope"})

    def broken(*args, **kwargs):
        raise httpx.ConnectError("offline")

    monkeypatch.setattr(github_module.httpx, "request", broken)
    assert "request failed" in github_module.github_ci_status.invoke({"repo": "o/r"})


def test_github_publishing_requires_token_then_posts(github_api, monkeypatch):
    routes, calls = github_api
    monkeypatch.setattr(github_module, "GITHUB_TOKEN", "")
    assert "GITHUB_TOKEN" in github_module.github_create_issue.invoke(
        {"repo": "o/r", "title": "Bug"}
    )

    monkeypatch.setattr(github_module, "GITHUB_TOKEN", "token")
    routes[("POST", "/repos/o/r/issues")] = (201, {"number": 9, "html_url": "u"})
    routes[("POST", "/repos/o/r/issues/9/comments")] = (201, {"html_url": "c"})

    created = json.loads(
        github_module.github_create_issue.invoke(
            {"repo": "o/r", "title": "Bug", "body": "b", "labels": ["bug"]}
        )
    )
    commented = json.loads(
        github_module.github_add_comment.invoke({"repo": "o/r", "number": 9, "body": "hi"})
    )

    assert created == {"created": True, "number": 9, "url": "u"}
    assert commented == {"posted": True, "url": "c"}
    assert calls[-2][2]["json"]["labels"] == ["bug"]
    assert github_module._headers()["Authorization"] == "Bearer token"


# ---------- Figma ----------


def test_figma_requires_token(monkeypatch):
    monkeypatch.setattr(figma_module, "FIGMA_TOKEN", "")
    assert "FIGMA_TOKEN" in figma_module.figma_get_design.invoke({"file": "AbCdEf1234567"})


def test_figma_summarizes_design(monkeypatch):
    monkeypatch.setattr(figma_module, "FIGMA_TOKEN", "token")
    document = {
        "document": {
            "children": [
                {
                    "type": "CANVAS",
                    "name": "Page",
                    "children": [
                        {
                            "id": "1:2",
                            "type": "FRAME",
                            "name": "Card",
                            "absoluteBoundingBox": {"width": 320, "height": 200},
                            "layoutMode": "VERTICAL",
                            "itemSpacing": 8,
                            "cornerRadius": 12,
                            "fills": [{"type": "SOLID", "color": {"r": 1, "g": 1, "b": 1, "a": 1}}],
                            "strokes": [{"type": "SOLID", "color": {"r": 0, "g": 0, "b": 0}, "opacity": 0.5}],
                            "children": [
                                {
                                    "type": "TEXT",
                                    "name": "Title",
                                    "characters": "Hello",
                                    "style": {"fontFamily": "Inter", "fontWeight": 600, "fontSize": 20},
                                },
                                {"type": "RECTANGLE", "name": "Hidden", "visible": False},
                            ],
                        }
                    ],
                }
            ]
        },
        "name": "App",
    }

    def fake_get(url, params=None, headers=None, timeout=None):
        if "/images/" in url:
            return _response(200, {"images": {"1:2": "https://preview.png"}}, url=url)
        return _response(200, document, url=url)

    monkeypatch.setattr(figma_module.httpx, "get", fake_get)
    result = figma_module.figma_get_design.invoke({"file": "https://figma.com/design/AbCdEf1234567/App"})

    assert result.startswith("Figma file: App")
    assert "Preview image: https://preview.png" in result
    assert 'FRAME "Card" 320x200 flex-col gap=8' in result
    assert "fill=#ffffff" in result
    assert "border=1px #000000 @ 0.50" in result
    assert 'text="Hello"' in result
    assert "Hidden" not in result


def test_figma_node_request_and_errors(monkeypatch):
    monkeypatch.setattr(figma_module, "FIGMA_TOKEN", "token")
    monkeypatch.setattr(figma_module, "_MAX_NODES", 1)

    def fake_get(url, params=None, headers=None, timeout=None):
        if "/images/" in url:
            return _response(500, {}, url=url)
        assert params["ids"] == "1:2"
        return _response(
            200,
            {"name": "App", "nodes": {"1:2": {"document": {"type": "FRAME", "name": "F", "children": [{"type": "TEXT"}]}}}},
            url=url,
        )

    monkeypatch.setattr(figma_module.httpx, "get", fake_get)
    result = figma_module.figma_get_design.invoke(
        {"file": "https://figma.com/file/AbCdEf1234567/App?node-id=1-2"}
    )
    assert "truncated" in result
    assert "Preview" not in result

    monkeypatch.setattr(figma_module.httpx, "get", lambda *a, **k: _response(403, {}))
    assert "refused access (403)" in figma_module.figma_get_design.invoke({"file": "AbCdEf1234567"})
    monkeypatch.setattr(figma_module.httpx, "get", lambda *a, **k: _response(500, {}))
    assert "failed (500)" in figma_module.figma_get_design.invoke({"file": "AbCdEf1234567"})
    assert "Give a Figma file URL" in figma_module.figma_get_design.invoke({"file": "x"})

    def offline(*args, **kwargs):
        raise httpx.ConnectError("offline")

    monkeypatch.setattr(figma_module.httpx, "get", offline)
    assert "request failed" in figma_module.figma_get_design.invoke({"file": "AbCdEf1234567"})


# ---------- Image generation & vision ----------


def test_generate_image_tool_stores_image(monkeypatch, uploads):
    create_or_update_conversation("t-int", "hi", CLIENT_ID)
    monkeypatch.setattr(
        files_service.httpx, "get", lambda url, **kwargs: _response(200, content=PNG, url=url)
    )

    result = image_module.generate_image.invoke({"prompt": "A red fox"}, config=CONFIG)

    assert result.startswith("IMAGE_URL: /files/")
    stored = list(uploads.iterdir())
    assert len(stored) == 1 and stored[0].name.endswith("_a-red-fox.png")


def test_generate_image_tool_failures(monkeypatch, uploads):
    assert "conversation not found" in image_module.generate_image.invoke(
        {"prompt": "x"}, config={"configurable": {"thread_id": "missing"}}
    )

    create_or_update_conversation("t-int", "hi", CLIENT_ID)
    monkeypatch.setattr(
        files_service.httpx, "get", lambda url, **kwargs: _response(200, content=b"<html>", url=url)
    )
    assert "did not return an image" in image_module.generate_image.invoke(
        {"prompt": "x"}, config=CONFIG
    )


def test_image_extension_detection():
    assert files_service.image_extension(PNG) == ".png"
    assert files_service.image_extension(b"GIF89a") == ".gif"
    assert files_service.image_extension(b"RIFF0000WEBP") == ".webp"
    assert files_service.image_extension(b"\xff\xd8\xff") == ".jpg"


def test_describe_images_uses_vision_model(monkeypatch, uploads):
    item = files_service.store_bytes(
        data=PNG, filename="a.png", kind="image", thread_id="t-v", client_id=CLIENT_ID
    )
    captured = {}

    class FakeVision:
        def invoke(self, messages):
            captured["messages"] = messages
            return AIMessage(content="<think>hmm</think> A diagram. ")

    monkeypatch.setattr(files_service, "_vision_llm", lambda: FakeVision())

    assert files_service.describe_images([], "q") == ""
    assert files_service.describe_images([item], "What is it?") == "A diagram."
    parts = captured["messages"][0].content
    assert isinstance(captured["messages"][0], HumanMessage)
    assert parts[1]["image_url"]["url"].startswith("data:image/png;base64,")

    class BrokenVision:
        def invoke(self, messages):
            raise RuntimeError("model down")

    monkeypatch.setattr(files_service, "_vision_llm", lambda: BrokenVision())
    assert "could not be analysed" in files_service.describe_images([item], "q")


def test_copy_to_thread_duplicates_document_chunks(uploads):
    item = files_service.store_bytes(
        data=b"text", filename="n.txt", kind="document", thread_id="t-src", client_id=CLIENT_ID
    )
    db = SessionLocal()
    with db.begin():
        db.add(
            DocumentChunk(
                id="chunk-1",
                thread_id="t-src",
                content="hello",
                cmetadata={"thread_id": "t-src", "source": item.stored_name},
                embedding=[0.0] * 3072,
            )
        )
        db.add(
            DocumentChunk(
                id="chunk-2",
                thread_id="t-src",
                content="other file",
                cmetadata={"thread_id": "t-src", "source": "other"},
                embedding=[0.0] * 3072,
            )
        )
    db.close()

    copy = files_service.copy_to_thread(item, "t-dst", CLIENT_ID)

    db = SessionLocal()
    rows = db.query(DocumentChunk).filter(DocumentChunk.thread_id == "t-dst").all()
    db.close()
    assert [row.content for row in rows] == ["hello"]
    assert rows[0].cmetadata["source"] == copy.stored_name

    files_service.stored_path(copy.stored_name).unlink()
    with pytest.raises(files_service.FileRejected):
        files_service.copy_to_thread(copy, "t-other", CLIENT_ID)


def test_stored_path_refuses_escape(uploads):
    with pytest.raises(files_service.FileRejected):
        files_service.stored_path("../secret.txt")


# ---------- Files routes edge cases ----------


def test_files_route_limits_and_missing(client, uploads, monkeypatch):
    monkeypatch.setattr(files_service, "MAX_IMAGE_MB", 0)
    import app.api.routes.files as files_routes

    monkeypatch.setattr(files_routes, "limit_bytes", lambda kind: 10)
    too_big = client.post(
        "/files", data={"thread_id": "t-f"}, files={"file": ("a.png", PNG, "image/png")}
    )
    assert too_big.status_code == 413

    empty = client.post(
        "/files", data={"thread_id": "t-f"}, files={"file": ("a.txt", b"", "text/plain")}
    )
    assert empty.status_code == 400

    assert client.get("/files/missing/content").status_code == 404
    assert client.post("/files/missing/attach", json={"thread_id": "t"}).status_code == 404
    assert client.patch("/projects/missing", json={"name": "x"}).status_code == 404


def test_files_route_rejects_other_clients_thread(client, uploads, client_headers):
    create_or_update_conversation("t-owned", "hi", "22222222-2222-4222-8222-222222222222")
    response = client.post(
        "/files", data={"thread_id": "t-owned"}, files={"file": ("a.png", PNG, "image/png")}
    )
    assert response.status_code == 404


def test_library_filters_by_kind_and_attaching_to_same_thread_is_noop(client, uploads):
    image = client.post(
        "/files", data={"thread_id": "t-k"}, files={"file": ("a.png", PNG, "image/png")}
    ).json()
    client.post("/files", data={"thread_id": "t-k"}, files={"file": ("b.txt", b"x", "text/plain")})

    images = client.get("/files?kind=image").json()["files"]
    assert [f["name"] for f in images] == ["a.png"]

    same = client.post(f"/files/{image['id']}/attach", json={"thread_id": "t-k"}).json()
    assert same["id"] == image["id"]


# ---------- Graph modes ----------


def test_agent_binds_mode_tools_and_reasoning_effort(database, monkeypatch):
    import app.agents.graph as graph_module

    binds = []

    class FakeChatModel:
        def __init__(self, **kwargs):
            pass

        def bind_tools(self, bound_tools, **kwargs):
            binds.append(({t.name for t in bound_tools}, kwargs))
            return self

        def invoke(self, messages):
            binds.append(("system", messages[0].content))
            return AIMessage(content="ok")

    monkeypatch.setattr(graph_module, "ChatGroq", FakeChatModel)
    agent = graph_module.build_agent("openai/gpt-oss-120b")

    agent.invoke(
        {"messages": [HumanMessage(content="hi")], "mode": "thinking", "instructions": "Be kind."},
        config={"configurable": {"thread_id": "graph-mode-1"}},
    )
    agent.invoke(
        {"messages": [HumanMessage(content="hi")], "mode": "github", "instructions": ""},
        config={"configurable": {"thread_id": "graph-mode-2"}},
    )
    agent.invoke(
        {"messages": [HumanMessage(content="hi")], "mode": "bogus"},
        config={"configurable": {"thread_id": "graph-mode-3"}},
    )

    thinking_tools, thinking_kwargs = binds[0]
    assert thinking_kwargs == {"reasoning_effort": "high"}
    assert "Mode: Thinking." in binds[1][1] and "Be kind." in binds[1][1]
    github_tools, github_kwargs = binds[2]
    assert "github_ci_status" in github_tools and github_kwargs == {}
    assert binds[-1][1] == graph_module.SYSTEM_PROMPT
