"""Attachments for chat: photos, documents, sketches and the file library."""

from typing import Annotated

from fastapi import APIRouter, Depends, File, Form, Query, UploadFile
from fastapi.responses import FileResponse, JSONResponse

from app.api.dependencies import get_client_id
from app.db import (
    create_or_update_conversation,
    get_uploaded_file,
    list_uploaded_files,
)
from app.schemas.files import AttachRequest, FileListResponse, FileOut
from app.services.files import (
    FileRejected,
    classify,
    copy_to_thread,
    limit_bytes,
    safe_filename,
    serialize,
    store_bytes,
    stored_path,
)


router = APIRouter()

UNSUPPORTED = (
    "Unsupported file type. Upload an image (PNG, JPG, WEBP, GIF) or a "
    "document (PDF, DOCX, TXT, MD, PY, CSV)."
)


def _error(message: str, status_code: int) -> JSONResponse:
    return JSONResponse({"error": message}, status_code=status_code)


def _ensure_conversation(thread_id, title, client_id, project_id):
    kwargs = {"project_id": project_id} if project_id else {}
    return create_or_update_conversation(thread_id, title, client_id, **kwargs)


@router.post("/files", response_model=FileOut)
async def upload_file(
    client_id: Annotated[str, Depends(get_client_id)],
    file: UploadFile = File(...),
    thread_id: str = Form(...),
    origin: str = Form("upload"),
    project_id: str | None = Form(None),
):
    filename = safe_filename(file.filename)
    kind = classify(filename)
    if kind is None:
        return _error(UNSUPPORTED, 400)

    maximum = limit_bytes(kind)
    data = bytearray()
    while chunk := await file.read(1024 * 1024):
        data.extend(chunk)
        if len(data) > maximum:
            return _error(
                f"File is too large. Maximum size is {maximum // (1024 * 1024)} MB.",
                413,
            )

    if not data:
        return _error("The file is empty.", 400)

    if _ensure_conversation(thread_id, f"File: {filename}", client_id, project_id) is None:
        return _error("Conversation not found.", 404)

    try:
        item = store_bytes(
            data=bytes(data),
            filename=filename,
            kind=kind,
            thread_id=thread_id,
            client_id=client_id,
            origin="sketch" if origin == "sketch" else "upload",
        )
    except FileRejected as exc:
        return _error(str(exc), exc.status_code)
    except Exception as exc:
        return _error(str(exc) or "Upload failed.", 500)

    return serialize(item)


@router.get("/files", response_model=FileListResponse)
async def library(
    client_id: Annotated[str, Depends(get_client_id)],
    q: Annotated[str | None, Query(max_length=120)] = None,
    kind: Annotated[str | None, Query()] = None,
):
    items = list_uploaded_files(client_id, q)
    if kind in {"image", "document"}:
        items = [item for item in items if item.kind == kind]

    # The same file attached to several chats shows once, newest copy first.
    seen: set[tuple[str, int]] = set()
    unique = []
    for item in items:
        key = (item.filename, item.size)
        if key in seen:
            continue
        seen.add(key)
        unique.append(serialize(item))

    return {"files": unique}


@router.post("/files/{file_id}/attach", response_model=FileOut)
async def attach_from_library(
    file_id: str,
    request: AttachRequest,
    client_id: Annotated[str, Depends(get_client_id)],
):
    item = get_uploaded_file(file_id, client_id)
    if item is None:
        return _error("File not found.", 404)

    if item.thread_id == request.thread_id:
        return serialize(item)

    conversation = _ensure_conversation(
        request.thread_id,
        f"File: {item.filename}",
        client_id,
        request.project_id,
    )
    if conversation is None:
        return _error("Conversation not found.", 404)

    try:
        copy = copy_to_thread(item, request.thread_id, client_id)
    except FileRejected as exc:
        return _error(str(exc), exc.status_code)

    return serialize(copy)


@router.get("/files/{file_id}/content")
async def file_content(file_id: str):
    # File ids are random UUIDs, so the URL itself is the capability; <img>
    # tags cannot send the X-Client-Id header.
    item = get_uploaded_file(file_id)
    if item is None:
        return _error("File not found.", 404)

    try:
        path = stored_path(item.stored_name)
    except FileRejected:
        return _error("File not found.", 404)

    if not path.is_file():
        return _error("File not found.", 404)

    disposition = "inline" if item.kind == "image" else "attachment"
    return FileResponse(
        path,
        media_type=item.mime_type,
        filename=item.filename,
        content_disposition_type=disposition,
        headers={
            "Cache-Control": "private, max-age=86400",
            "X-Content-Type-Options": "nosniff",
        },
    )
