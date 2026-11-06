from typing import Annotated

from pydantic import BaseModel, StringConstraints


class FileOut(BaseModel):
    id: str
    name: str
    kind: str
    mime_type: str
    size: int
    origin: str
    thread_id: str
    url: str
    created_at: str | None = None


class FileListResponse(BaseModel):
    files: list[FileOut]


class AttachRequest(BaseModel):
    thread_id: Annotated[str, StringConstraints(strip_whitespace=True, min_length=1)]
    project_id: str | None = None


class Attachment(BaseModel):
    id: str
    name: str
    kind: str
    url: str
