import json

from langchain_core.messages import AIMessage, AIMessageChunk, ToolMessage

from app.schemas.streaming import StreamEvent


def sse_data(payload: dict | StreamEvent) -> str:
    event = (
        payload
        if isinstance(payload, StreamEvent)
        else StreamEvent.model_validate(payload)
    )
    data = event.model_dump(exclude_none=True)
    return f"data: {json.dumps(data, ensure_ascii=False)}\n\n"


def should_stream_chunk(chunk, metadata) -> bool:
    """
    Stream only normal AI text chunks and hide tool calls/tool output.
    """

    metadata = metadata or {}
    node_name = str(metadata.get("langgraph_node", "")).lower()

    if "tool" in node_name:
        return False

    if isinstance(chunk, ToolMessage):
        return False

    if not isinstance(chunk, (AIMessage, AIMessageChunk)):
        return False

    if getattr(chunk, "tool_calls", None):
        return False

    if getattr(chunk, "invalid_tool_calls", None):
        return False

    additional_kwargs = getattr(chunk, "additional_kwargs", {}) or {}
    if additional_kwargs.get("tool_calls"):
        return False

    return True


def extract_text_from_chunk(chunk) -> str:
    content = getattr(chunk, "content", "")

    if not content:
        return ""

    if isinstance(content, str):
        return content

    if isinstance(content, list):
        text_parts = []

        for item in content:
            if isinstance(item, str):
                text_parts.append(item)
            elif isinstance(item, dict):
                if item.get("type") == "text" and isinstance(item.get("text"), str):
                    text_parts.append(item["text"])
                elif isinstance(item.get("text"), str):
                    text_parts.append(item["text"])
                elif isinstance(item.get("content"), str):
                    text_parts.append(item["content"])

        return "".join(text_parts)

    return ""
