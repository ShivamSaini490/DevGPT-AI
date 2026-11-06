import uuid
from pathlib import Path
from typing import Annotated

from fastapi import APIRouter, Depends, File, Form, UploadFile
from fastapi.responses import JSONResponse

from app.api.dependencies import get_client_id
from app.core.config import MAX_UPLOAD_MB
from app.core.paths import UPLOADS_DIR
from app.db import create_or_update_conversation
from app.rag import add_document_to_rag
from app.schemas.documents import UploadResponse


router = APIRouter()


@router.post("/upload", response_model=UploadResponse)
async def upload_document(
    client_id: Annotated[str, Depends(get_client_id)],
    file: UploadFile = File(...),
    thread_id: str = Form(...),
):
    file_path = None

    try:
        allowed_extensions = [".pdf", ".docx", ".txt", ".md", ".py", ".csv"]

        original_filename = file.filename or "uploaded_file"
        safe_filename = Path(
            original_filename.replace("\\", "/")
        ).name.replace(" ", "_")
        suffix = Path(safe_filename).suffix.lower()

        if suffix not in allowed_extensions:
            return JSONResponse(
                {
                    "success": False,
                    "message": "Unsupported file type. Upload PDF, DOCX, TXT, MD, PY, or CSV.",
                },
                status_code=400,
            )

        file_id = str(uuid.uuid4())
        file_path = UPLOADS_DIR / f"{file_id}_{safe_filename}"

        maximum_bytes = MAX_UPLOAD_MB * 1024 * 1024
        uploaded_bytes = 0
        exceeds_limit = False

        with open(file_path, "wb") as f:
            while chunk := await file.read(1024 * 1024):
                uploaded_bytes += len(chunk)

                if uploaded_bytes > maximum_bytes:
                    exceeds_limit = True
                    break

                f.write(chunk)

        if exceeds_limit:
            file_path.unlink(missing_ok=True)
            return JSONResponse(
                {
                    "success": False,
                    "message": (
                        "File is too large. Maximum size is "
                        f"{MAX_UPLOAD_MB} MB."
                    ),
                },
                status_code=413,
            )

        conversation = create_or_update_conversation(
            thread_id,
            "Uploaded document",
            client_id,
        )
        if conversation is None:
            file_path.unlink(missing_ok=True)
            return JSONResponse(
                {"error": "Conversation not found."},
                status_code=404,
            )

        result = add_document_to_rag(
            file_path=str(file_path),
            thread_id=thread_id,
        )

        return UploadResponse(
            success=True,
            message=(
                f"Uploaded {original_filename} and created "
                f"{result['chunks']} chunks."
            ),
        )
    except Exception as e:
        if file_path is not None:
            try:
                file_path.unlink(missing_ok=True)
            except OSError:
                pass

        return JSONResponse(
            {
                "success": False,
                "message": str(e),
            },
            status_code=500,
        )
