from datetime import datetime

from typing import Annotated

from pydantic import BaseModel, ConfigDict, StringConstraints


StrippedTitle = Annotated[
    str,
    StringConstraints(strip_whitespace=True, min_length=1, max_length=80),
]


class ConversationOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    thread_id: str
    title: str
    created_at: datetime
    updated_at: datetime


class ConversationListResponse(BaseModel):
    conversations: list[ConversationOut]


class ConversationRenameRequest(BaseModel):
    title: StrippedTitle


class ConversationDeleteResponse(BaseModel):
    success: bool


class HistoryMessage(BaseModel):
    role: str
    content: str


class HistoryResponse(BaseModel):
    messages: list[HistoryMessage]
