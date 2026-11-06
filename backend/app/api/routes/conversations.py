from typing import Annotated

from fastapi import APIRouter, Depends
from fastapi.responses import JSONResponse

from app.api.dependencies import get_client_id
from app.db import (
    conversation_owned_by_client,
    get_chat_history,
    list_conversations,
    rename_conversation,
)
from app.services.cleanup import delete_conversation_data
from app.schemas.conversations import (
    ConversationDeleteResponse,
    ConversationListResponse,
    ConversationOut,
    ConversationRenameRequest,
    HistoryResponse,
)


router = APIRouter()


@router.get("/conversations", response_model=ConversationListResponse)
async def conversations(
    client_id: Annotated[str, Depends(get_client_id)],
):
    items = list_conversations(client_id)

    return {
        "conversations": [
            {
                "thread_id": item.thread_id,
                "title": item.title,
                "project_id": item.project_id,
                "created_at": item.created_at.isoformat(),
                "updated_at": item.updated_at.isoformat(),
            }
            for item in items
        ]
    }


@router.patch("/conversations/{thread_id}", response_model=ConversationOut)
async def update_conversation(
    thread_id: str,
    request: ConversationRenameRequest,
    client_id: Annotated[str, Depends(get_client_id)],
):
    conversation = rename_conversation(thread_id, request.title, client_id)

    if conversation is None:
        return JSONResponse(
            {"error": "Conversation not found."},
            status_code=404,
        )

    return conversation


@router.delete(
    "/conversations/{thread_id}",
    response_model=ConversationDeleteResponse,
)
async def remove_conversation(
    thread_id: str,
    client_id: Annotated[str, Depends(get_client_id)],
):
    if not conversation_owned_by_client(thread_id, client_id):
        return JSONResponse(
            {"error": "Conversation not found."},
            status_code=404,
        )

    if not delete_conversation_data(thread_id):
        return JSONResponse(
            {"error": "Conversation not found."},
            status_code=404,
        )

    return ConversationDeleteResponse(success=True)


@router.get("/history/{thread_id}", response_model=HistoryResponse)
async def history(
    thread_id: str,
    client_id: Annotated[str, Depends(get_client_id)],
):
    messages = get_chat_history(thread_id, client_id)

    if messages is None:
        return JSONResponse(
            {"error": "Conversation not found."},
            status_code=404,
        )

    return {
        "messages": [
            {
                "role": msg.role,
                "content": msg.content,
                "attachments": msg.attachments or [],
            }
            for msg in messages
        ]
    }
