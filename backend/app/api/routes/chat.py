import logging
import re
from typing import Annotated

from fastapi import APIRouter, Depends, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse, StreamingResponse
from fastapi.routing import APIRoute
from langchain_core.messages import AIMessage, AIMessageChunk, HumanMessage, ToolMessage

from app.agents import DEFAULT_MODEL, get_agent
from app.api.dependencies import get_client_id
from app.db import (
    create_or_update_conversation,
    get_project,
    get_uploaded_files,
    save_chat_message,
)
from app.schemas.chat import ChatRequest
from app.services.files import attachment_summary, describe_images
from app.utils.streaming import (
    extract_reasoning_from_chunk,
    extract_text_from_chunk,
    has_tool_call,
    should_stream_chunk,
    sse_data,
    tool_call_names,
)


logger = logging.getLogger(__name__)
MODEL_RATE_LIMIT_MESSAGE = (
    "The model rate limit was reached. Wait a minute or start a new chat."
)


def _is_model_rate_limit_error(exc: Exception) -> bool:
    error_text = str(exc).lower()
    return (
        "rate limit" in error_text
        or "rate_limit" in error_text
        or "request too large" in error_text
        or (
            "413" in error_text
            and ("tokens per minute" in error_text or "tpm" in error_text)
        )
    )


class ChatValidationRoute(APIRoute):
    def get_route_handler(self):
        original_route_handler = super().get_route_handler()

        async def validation_error_handler(request: Request):
            try:
                return await original_route_handler(request)
            except RequestValidationError as exc:
                errors = exc.errors()

                if any(error.get("loc", ())[-1:] == ("message",) for error in errors):
                    message = "Message is required."
                elif any(
                    error.get("loc", ())[-1:] == ("thread_id",)
                    for error in errors
                ):
                    message = "Thread ID is required."
                else:
                    message = "Invalid JSON body."

                return JSONResponse({"error": message}, status_code=400)

        return validation_error_handler


router = APIRouter(route_class=ChatValidationRoute)

_GENERATED_IMAGE = re.compile(r"IMAGE_URL:\s*(/files/[\w-]+/content)")


def _model_message(user_message: str, documents: list, image_notes: str) -> str:
    """The user's text plus what the model needs to know about attachments."""
    parts = [user_message]
    for item in documents:
        parts.append(
            f"[Attached document: {item.filename}. It is indexed for this chat; "
            "use search_uploaded_documents to read it.]"
        )
    if image_notes:
        parts.append(
            "[Attached image(s). A vision model described them for you:]\n"
            + image_notes
        )
    return "\n\n".join(parts)


@router.post("/chat/stream")
async def chat_stream(
    chat_request: ChatRequest,
    client_id: Annotated[str, Depends(get_client_id)],
):
    user_message = chat_request.message
    thread_id = chat_request.thread_id
    selected_model = chat_request.model or DEFAULT_MODEL
    mode = chat_request.mode or ""

    extra = {"project_id": chat_request.project_id} if chat_request.project_id else {}
    conversation = create_or_update_conversation(
        thread_id,
        user_message,
        client_id,
        **extra,
    )
    if conversation is None:
        return JSONResponse(
            {"error": "Conversation not found."},
            status_code=404,
        )

    instructions = ""
    project_id = getattr(conversation, "project_id", None)
    if project_id:
        project = get_project(project_id, client_id)
        instructions = project.instructions if project else ""

    attached = (
        get_uploaded_files(chat_request.attachments, client_id)
        if chat_request.attachments
        else []
    )
    images = [item for item in attached if item.kind == "image"]
    documents = [item for item in attached if item.kind == "document"]

    agent = get_agent(selected_model)
    if attached:
        save_chat_message(
            thread_id,
            "user",
            user_message,
            attachments=[attachment_summary(item) for item in attached],
        )
    else:
        save_chat_message(thread_id, "user", user_message)

    config = {
        "configurable": {
            "thread_id": thread_id,
        }
    }

    def event_generator():
        final_answer = ""
        # Where the current model message's text starts in final_answer, so it
        # can be withdrawn if that message turns out to be a tool call.
        segment_start = 0
        segment_id = None

        try:
            image_notes = ""
            if images:
                yield sse_data({"tool": "vision"})
                image_notes = describe_images(images, user_message)

            inputs = {
                "messages": [
                    HumanMessage(
                        content=_model_message(user_message, documents, image_notes)
                    ),
                ],
                "mode": mode,
                "instructions": instructions,
            }

            for chunk, metadata in agent.stream(
                inputs,
                config=config,
                stream_mode="messages",
            ):
                if isinstance(chunk, ToolMessage):
                    # A generated image is shown right away, ahead of the reply.
                    match = (
                        _GENERATED_IMAGE.search(chunk.content)
                        if isinstance(chunk.content, str)
                        else None
                    )
                    if match:
                        image_markdown = f"![Generated image]({match.group(1)})\n\n"
                        final_answer += image_markdown
                        yield sse_data({"token": image_markdown})
                    segment_id = None
                    segment_start = len(final_answer)
                elif isinstance(chunk, (AIMessage, AIMessageChunk)):
                    chunk_id = getattr(chunk, "id", None)
                    if chunk_id and chunk_id != segment_id:
                        segment_id = chunk_id
                        segment_start = len(final_answer)

                    # Text streamed before a tool call is the model thinking
                    # aloud, not part of the answer: take it back.
                    if has_tool_call(chunk) and len(final_answer) > segment_start:
                        final_answer = final_answer[:segment_start]
                        yield sse_data({"replace": final_answer})

                    for name in tool_call_names(chunk):
                        yield sse_data({"tool": name})

                    reasoning = extract_reasoning_from_chunk(chunk)
                    if reasoning:
                        yield sse_data({"reasoning": reasoning})

                if not should_stream_chunk(chunk, metadata):
                    continue

                token = extract_text_from_chunk(chunk)

                if token:
                    final_answer += token
                    yield sse_data({"token": token})

            if final_answer.strip():
                save_chat_message(thread_id, "assistant", final_answer)

            yield sse_data({"done": True})
        except Exception as e:
            if _is_model_rate_limit_error(e):
                logger.exception("Groq model request exceeded a rate limit")
                error_message = MODEL_RATE_LIMIT_MESSAGE
            else:
                error_message = str(e)

            yield sse_data({"error": error_message})
            yield sse_data({"done": True})

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )
