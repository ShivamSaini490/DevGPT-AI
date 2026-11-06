import logging
from typing import Annotated

from fastapi import APIRouter, Depends, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse, StreamingResponse
from fastapi.routing import APIRoute
from langchain_core.messages import HumanMessage

from app.agents import DEFAULT_MODEL, get_agent
from app.api.dependencies import get_client_id
from app.db import (
    create_or_update_conversation,
    save_chat_message,
)
from app.schemas.chat import ChatRequest
from app.utils.streaming import (
    extract_text_from_chunk,
    should_stream_chunk,
    sse_data,
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


@router.post("/chat/stream")
async def chat_stream(
    chat_request: ChatRequest,
    client_id: Annotated[str, Depends(get_client_id)],
):
    user_message = chat_request.message
    thread_id = chat_request.thread_id
    selected_model = chat_request.model or DEFAULT_MODEL

    conversation = create_or_update_conversation(
        thread_id,
        user_message,
        client_id,
    )
    if conversation is None:
        return JSONResponse(
            {"error": "Conversation not found."},
            status_code=404,
        )

    agent = get_agent(selected_model)
    save_chat_message(thread_id, "user", user_message)

    config = {
        "configurable": {
            "thread_id": thread_id,
        }
    }

    def event_generator():
        final_answer = ""

        try:
            inputs = {
                "messages": [
                    HumanMessage(content=user_message),
                ]
            }

            for chunk, metadata in agent.stream(
                inputs,
                config=config,
                stream_mode="messages",
            ):
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
