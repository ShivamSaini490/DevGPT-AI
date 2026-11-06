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
        "max_retries": 1,
        "timeout": 30,
    }
    assert captured["tools"] == graph_module.tools
    assert captured["messages"][0].content == graph_module.SYSTEM_PROMPT
    assert captured["messages"][1].content == "hello"


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

