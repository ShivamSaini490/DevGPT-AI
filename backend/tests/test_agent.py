import pytest


def test_model_name_validation_uses_allowlist_and_fallback(database):
    from app.agents.graph import DEFAULT_MODEL, normalize_model_name

    assert normalize_model_name("openai/gpt-oss-20b") == "openai/gpt-oss-20b"
    assert normalize_model_name("  qwen/qwen3.8-27b  ") == (
        "qwen/qwen3.8-27b"
    )
    assert normalize_model_name(None) == DEFAULT_MODEL
    assert normalize_model_name("not-a-real-model") == DEFAULT_MODEL


def test_system_prompt_requires_proactive_memory_tool_use():
    from app.agents.prompts import SYSTEM_PROMPT

    assert (
        "always call recall_memory before answering" in SYSTEM_PROMPT
    )
    assert (
        "never say you have no record without calling recall_memory first"
        in SYSTEM_PROMPT
    )
    assert "call remember_this automatically" in SYSTEM_PROMPT
    assert '"my favourite language is Python"' in SYSTEM_PROMPT


def test_system_prompt_keeps_reasoning_out_of_answers():
    from app.agents.prompts import SYSTEM_PROMPT

    assert "Never include your internal reasoning" in SYSTEM_PROMPT


def test_current_info_detection_routes_time_sensitive_questions():
    from datetime import date

    from app.agents.current_info import live_search_query, needs_live_web_search

    assert needs_live_web_search("Who is the president of USA?")
    assert needs_live_web_search("Who is the CM of Nepal?")
    assert needs_live_web_search("facp in intellectual disability")
    assert needs_live_web_search("What is the latest stable Python version?")
    assert needs_live_web_search("Tell me about AI", "web_search")
    assert not needs_live_web_search("Explain the US presidency")
    assert not needs_live_web_search("What is the weather today?")
    assert not needs_live_web_search("What is the current stock price of AAPL?")
    assert not needs_live_web_search("Create an image of the latest phone", "image")

    query = live_search_query(
        "Who is the president of USA?", date(2026, 11, 20)
    )
    assert query.startswith("Who is the president of USA?")
    assert "as of 2026-11-20" in query
    assert "official and primary sources" in query


def test_current_info_router_creates_tavily_call_for_current_role(database):
    from langchain_core.messages import HumanMessage
    import app.agents.graph as graph_module

    routed = graph_module._automatic_tool_router(
        {
            "messages": [HumanMessage(content="Who is the president of USA?")],
            "mode": "",
        }
    )

    assert routed["auto_web_search"] is True
    assert routed["auto_tool_call"] is True
    assert routed["auto_image_generation"] is False
    call = routed["messages"][0].tool_calls[0]
    assert call["name"] == "tavily_search"
    assert "official and primary sources" in call["args"]["query"]
    assert graph_module._route_automatic_tool(routed) == "tools"


def test_current_info_router_skips_ordinary_question(database):
    from langchain_core.messages import HumanMessage
    import app.agents.graph as graph_module

    routed = graph_module._automatic_tool_router(
        {"messages": [HumanMessage(content="Explain recursion")], "mode": ""}
    )

    assert routed == {
        "auto_web_search": False,
        "auto_tool_call": False,
        "auto_image_generation": False,
    }
    assert graph_module._route_automatic_tool(routed) == "chatbot"


def test_automatic_tool_router_forces_image_generation(database):
    from langchain_core.messages import HumanMessage, ToolMessage
    import app.agents.graph as graph_module

    routed = graph_module._automatic_tool_router(
        {
            "messages": [HumanMessage(content="create an image of goku")],
            "mode": "image",
        }
    )
    call = routed["messages"][0].tool_calls[0]

    assert routed["auto_tool_call"] is True
    assert routed["auto_image_generation"] is True
    assert call["name"] == "generate_image"
    assert "create an image of goku" in call["args"]["prompt"]
    assert "canonical Son Goku from Dragon Ball Z" in call["args"]["prompt"]
    assert "jet-black spiky hair" in call["args"]["prompt"]
    assert "bright orange gi must dominate" in call["args"]["prompt"]
    assert "Single centered front-facing" in call["args"]["prompt"]
    assert "circular frame" in call["args"]["prompt"]
    assert "STRICT flat 2D cel-animation" in call["args"]["prompt"]
    assert "accurate anatomy" in call["args"]["prompt"]
    assert graph_module._route_automatic_tool(routed) == "tools"

    state = {
        "mode": "image",
        "auto_image_generation": True,
        "messages": [
            HumanMessage(content="create an image of goku"),
            routed["messages"][0],
            ToolMessage(
                content="IMAGE_URL: /files/generated/content",
                tool_call_id=call["id"],
                name="generate_image",
            ),
        ],
    }
    assert graph_module._route_after_tools(state) == "image_confirmation"
    confirmation = graph_module._image_confirmation_node(state)
    assert "created the image" in confirmation["messages"][0].content


def test_image_followup_inherits_previous_prompt_and_character_details(database):
    from langchain_core.messages import AIMessage, HumanMessage, ToolMessage
    import app.agents.graph as graph_module

    previous_call = AIMessage(
        content="",
        tool_calls=[
            {
                "name": "generate_image",
                "args": {"prompt": "create an image of Goku"},
                "id": "image-1",
                "type": "tool_call",
            }
        ],
    )
    state = {
        "mode": "",
        "messages": [
            HumanMessage(content="create an image of Goku"),
            previous_call,
            ToolMessage(
                content="IMAGE_URL: /files/one/content",
                tool_call_id="image-1",
                name="generate_image",
            ),
            AIMessage(content="Done"),
            HumanMessage(content="I want it in supper saiyan 3"),
        ],
    }

    routed = graph_module._automatic_tool_router(state)
    prompt = routed["messages"][0].tool_calls[0]["args"]["prompt"]

    assert routed["auto_image_generation"] is True
    assert "Original image request: create an image of Goku" in prompt
    assert "Requested revision: I want it in supper saiyan 3" in prompt
    assert "extremely long dense golden hair" in prompt
    assert "no eyebrows" in prompt
    assert "blue-white lightning" in prompt
    assert "realism" in prompt

    next_state = {
        "mode": "",
        "messages": state["messages"]
        + routed["messages"]
        + [
            ToolMessage(
                content="IMAGE_URL: /files/two/content",
                tool_call_id=routed["messages"][0].tool_calls[0]["id"],
                name="generate_image",
            ),
            AIMessage(content="Done"),
            HumanMessage(content="make the background blue"),
        ],
    }
    next_routed = graph_module._automatic_tool_router(next_state)
    next_prompt = next_routed["messages"][0].tool_calls[0]["args"]["prompt"]
    assert next_prompt.count("STRICT flat 2D cel-animation") == 1
    assert "Original image request: Original image request:" not in next_prompt


def test_image_prompt_preserves_canonical_ben_10_identity(database):
    from langchain_core.messages import HumanMessage
    import app.agents.graph as graph_module

    routed = graph_module._automatic_tool_router(
        {
            "messages": [HumanMessage(content="create a image of ben 10")],
            "mode": "image",
        }
    )
    prompt = routed["messages"][0].tool_calls[0]["args"]["prompt"]

    assert "canonical Ben Tennyson" in prompt
    assert "10-year-old boy" in prompt
    assert "original 2005 Ben 10 series" in prompt
    assert "white short-sleeve T-shirt" in prompt
    assert "solid black vertical stripe from collar to hem" in prompt
    assert "olive-green cargo pants" in prompt
    assert "black-and-green Omnitrix" in prompt
    assert "left wrist" in prompt
    assert "raised left forearm" in prompt
    assert "Green appears only on the Omnitrix dial and cargo pants" in prompt
    assert "No adult, woman, girl, diagonal stripe, green shirt" in prompt


def test_image_confirmation_uses_only_the_current_turn_result(database):
    from langchain_core.messages import AIMessage, HumanMessage, ToolMessage
    import app.agents.graph as graph_module

    state = {
        "messages": [
            HumanMessage(content="create an image of Goku"),
            AIMessage(
                content="",
                tool_calls=[
                    {
                        "name": "generate_image",
                        "args": {"prompt": "Goku"},
                        "id": "image-1",
                        "type": "tool_call",
                    }
                ],
            ),
            ToolMessage(
                content="IMAGE_URL: /files/one/content",
                tool_call_id="image-1",
                name="generate_image",
            ),
            AIMessage(content="Done"),
            HumanMessage(content="make it Super Saiyan 3"),
            AIMessage(
                content="",
                tool_calls=[
                    {
                        "name": "generate_image",
                        "args": {"prompt": "Super Saiyan 3 Goku"},
                        "id": "image-2",
                        "type": "tool_call",
                    }
                ],
            ),
            ToolMessage(
                content="Image generation failed: provider busy",
                tool_call_id="image-2",
                name="generate_image",
            ),
        ]
    }

    confirmation = graph_module._image_confirmation_node(state)

    assert confirmation["messages"][0].content == (
        "Image generation failed: provider busy"
    )


def test_search_is_flattened_and_tools_disabled_for_final_answer(database):
    from langchain_core.messages import AIMessage, HumanMessage, ToolMessage
    import app.agents.graph as graph_module

    messages = [
        HumanMessage(content="Who is the CM of Nepal?"),
        AIMessage(
            content="",
            tool_calls=[
                {
                    "name": "tavily_search",
                    "args": {"query": "current CM of Nepal"},
                    "id": "search-1",
                    "type": "tool_call",
                }
            ],
        ),
        ToolMessage(
            content="live results",
            tool_call_id="search-1",
            name="tavily_search",
        ),
    ]

    names = {
        tool.name
        for tool in graph_module._tools_for_model_turn("web_search", messages)
    }

    flattened = graph_module._flatten_current_web_search(messages)

    assert names == set()
    assert "live results" in flattened[-1].content
    assert "do not request another search" in flattened[-1].content
    assert not any(isinstance(message, ToolMessage) for message in flattened)
    assert not any(isinstance(message, AIMessage) for message in flattened)
    assert "tavily_search" in {
        tool.name
        for tool in graph_module._tools_for_model_turn(
            "deep_research", messages
        )
    }


def test_model_history_trimming_keeps_latest_human_and_drops_orphan_tool(
    database,
    monkeypatch,
):
    from langchain_core.messages import AIMessage, HumanMessage, ToolMessage
    import app.agents.graph as graph_module

    monkeypatch.setattr(graph_module, "MAX_CONTEXT_TOKENS", 20)
    latest = HumanMessage(content="latest question")
    history = [
        HumanMessage(content="old question " * 100),
        AIMessage(content="old response " * 100),
        latest,
        ToolMessage(content="orphan result", tool_call_id="missing-call"),
    ]

    trimmed = graph_module._messages_for_model(history)

    assert latest in trimmed
    assert isinstance(trimmed[0], HumanMessage)
    assert not any(isinstance(message, ToolMessage) for message in trimmed)


def test_model_history_truncates_long_tool_output(database, monkeypatch):
    from langchain_core.messages import AIMessage, HumanMessage, ToolMessage
    import app.agents.graph as graph_module

    monkeypatch.setattr(graph_module, "MAX_CONTEXT_TOKENS", 1000)
    monkeypatch.setattr(graph_module, "MAX_TOOL_OUTPUT_CHARS", 40)
    history = [
        HumanMessage(content="search for this"),
        AIMessage(
            content="",
            tool_calls=[
                {
                    "name": "search",
                    "args": {"query": "this"},
                    "id": "call-1",
                    "type": "tool_call",
                }
            ],
        ),
        ToolMessage(content="x" * 200, tool_call_id="call-1"),
    ]

    trimmed = graph_module._messages_for_model(history)
    tool_message = next(
        message for message in trimmed if isinstance(message, ToolMessage)
    )

    assert len(tool_message.content) == 40
    assert tool_message.content.endswith("... [truncated]")
    assert tool_message.tool_call_id == "call-1"

    wrapped = graph_module._truncate_tool_call_result(
        object(),
        lambda request: ToolMessage(
            content="y" * 200,
            tool_call_id="call-2",
        ),
    )
    assert len(wrapped.content) == 40
    assert wrapped.content.endswith("... [truncated]")


def test_build_agent_executes_graph_without_external_model_call(database, monkeypatch):
    from langchain_core.messages import AIMessage, HumanMessage
    import app.agents.graph as graph_module

    captured = {}

    class FakeChatModel:
        def __init__(self, **kwargs):
            captured["model_kwargs"] = kwargs

        def bind_tools(self, bound_tools):
            captured["tools"] = bound_tools
            return self

        def invoke(self, messages):
            captured["messages"] = messages
            return AIMessage(content="fake response")

    monkeypatch.setattr(graph_module, "ChatGroq", FakeChatModel)

    agent = graph_module.build_agent("openai/gpt-oss-20b")
    result = agent.invoke(
        {"messages": [HumanMessage(content="hello")]},
        config={"configurable": {"thread_id": "agent-build-test"}},
    )

    assert result["messages"][-1].content == "fake response"
    assert captured["model_kwargs"] == {
        "model": "openai/gpt-oss-20b",
        "temperature": 0.3,
        "streaming": True,
        "max_retries": 0,
        "timeout": 30,
    }
    assert captured["tools"] == graph_module.tools
    assert captured["messages"][0].content.startswith(graph_module.SYSTEM_PROMPT)
    assert "Current date:" in captured["messages"][0].content
    assert captured["messages"][1].content == "hello"


def test_build_agent_falls_back_immediately_on_model_rate_limit(
    database,
    monkeypatch,
):
    from langchain_core.messages import AIMessage, HumanMessage
    import app.agents.graph as graph_module

    created_models = []

    class FakeChatModel:
        def __init__(self, **kwargs):
            self.model = kwargs["model"]
            created_models.append((self.model, kwargs["max_retries"]))

        def bind_tools(self, bound_tools, **kwargs):
            return self

        def invoke(self, messages):
            if self.model == "openai/gpt-oss-120b":
                raise RuntimeError("429 rate_limit_exceeded: TPM limit reached")
            return AIMessage(content=f"answered by {self.model}")

    monkeypatch.setattr(graph_module, "ChatGroq", FakeChatModel)

    agent = graph_module.build_agent("openai/gpt-oss-120b")
    result = agent.invoke(
        {"messages": [HumanMessage(content="hello")]},
        config={"configurable": {"thread_id": "agent-fallback-test"}},
    )

    assert result["messages"][-1].content == (
        "answered by openai/gpt-oss-20b"
    )
    assert created_models == [
        ("openai/gpt-oss-120b", 0),
        ("openai/gpt-oss-20b", 0),
    ]


def test_non_rate_limit_model_errors_are_not_hidden(database, monkeypatch):
    from langchain_core.messages import HumanMessage
    import app.agents.graph as graph_module

    class BrokenChatModel:
        def __init__(self, **kwargs):
            pass

        def bind_tools(self, bound_tools, **kwargs):
            return self

        def invoke(self, messages):
            raise RuntimeError("invalid request")

    monkeypatch.setattr(graph_module, "ChatGroq", BrokenChatModel)
    agent = graph_module.build_agent("openai/gpt-oss-120b")

    with pytest.raises(RuntimeError, match="invalid request"):
        agent.invoke(
            {"messages": [HumanMessage(content="hello")]},
            config={
                "configurable": {"thread_id": "agent-no-fallback-test"}
            },
        )


def test_get_agent_caches_by_normalized_model(database, monkeypatch):
    import app.agents.graph as graph_module

    monkeypatch.setattr(graph_module, "DEFAULT_MODEL", "openai/gpt-oss-120b")
    graph_module._AGENT_CACHE.clear()
    builds = []
    monkeypatch.setattr(
        graph_module,
        "build_agent",
        lambda model: builds.append(model) or object(),
    )

    first = graph_module.get_agent("openai/gpt-oss-120b")
    second = graph_module.get_agent("openai/gpt-oss-120b")
    fallback = graph_module.get_agent("unsupported")

    assert first is second
    assert builds.count("openai/gpt-oss-120b") == 1
    assert fallback is first

