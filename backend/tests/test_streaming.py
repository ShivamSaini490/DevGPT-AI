import json

from langchain_core.messages import AIMessage, AIMessageChunk, HumanMessage, ToolMessage

from app.utils.streaming import (
    extract_text_from_chunk,
    has_tool_call,
    should_stream_chunk,
    sse_data,
)


def test_has_tool_call_detects_streamed_and_complete_tool_calls():
    assert has_tool_call(
        AIMessageChunk(
            content="",
            tool_call_chunks=[{"name": "calculator", "args": "{}", "id": "c1", "index": 0}],
        )
    )
    assert has_tool_call(
        AIMessage(content="", tool_calls=[{"name": "calculator", "args": {}, "id": "c1"}])
    )
    assert not has_tool_call(AIMessageChunk(content="plain text"))
    assert not has_tool_call(ToolMessage(content="8", tool_call_id="c1"))


def test_sse_data_serializes_unicode_payload():
    encoded = sse_data({"token": "नमस्ते"})

    assert encoded.startswith("data: ")
    assert encoded.endswith("\n\n")
    assert json.loads(encoded.removeprefix("data: ").strip()) == {"token": "नमस्ते"}


def test_sse_data_preserves_event_wire_format():
    assert sse_data({"token": "hello"}) == 'data: {"token": "hello"}\n\n'
    assert sse_data({"error": "failed"}) == 'data: {"error": "failed"}\n\n'
    assert sse_data({"done": True}) == 'data: {"done": true}\n\n'


def test_should_stream_normal_ai_chunks_only():
    assert should_stream_chunk(AIMessageChunk(content="hello"), {"langgraph_node": "chatbot"})
    assert should_stream_chunk(AIMessage(content="hello"), {})
    assert not should_stream_chunk(HumanMessage(content="hello"), {})
    assert not should_stream_chunk(
        ToolMessage(content="tool output", tool_call_id="call-1"),
        {},
    )
    assert not should_stream_chunk(
        AIMessageChunk(content="hidden"),
        {"langgraph_node": "tools"},
    )
    assert not should_stream_chunk(
        AIMessageChunk(
            content="",
            tool_calls=[{"name": "calculator", "args": {}, "id": "call-1"}],
        ),
        {},
    )


def test_extract_text_from_supported_content_shapes():
    assert extract_text_from_chunk(AIMessageChunk(content="plain")) == "plain"
    assert extract_text_from_chunk(
        AIMessageChunk(
            content=[
                "one",
                {"type": "text", "text": "two"},
                {"content": "three"},
                {"type": "image", "url": "ignored"},
            ]
        )
    ) == "onetwothree"
    assert extract_text_from_chunk(AIMessageChunk(content=[])) == ""

