"""Storage for chat attachments: documents, photos, sketches and generated images."""

import base64
from io import BytesIO
import logging
import random
import re
import shutil
import time
import uuid
from pathlib import Path
from urllib.parse import quote

import httpx
from langchain_core.messages import HumanMessage
from PIL import Image, ImageDraw, ImageFont, UnidentifiedImageError
from sqlalchemy import select

from app.core.config import (
    EXTERNAL_API_TIMEOUT_SECONDS,
    IMAGE_GENERATION_URL,
    MAX_IMAGE_MB,
    MAX_UPLOAD_MB,
    VISION_MODEL,
)
from app.core.paths import UPLOADS_DIR
from app.db import add_uploaded_file
from app.db.models import DocumentChunk
from app.db.session import SessionLocal
from app.rag import add_document_to_rag


logger = logging.getLogger(__name__)

DOCUMENT_EXTENSIONS = {".pdf", ".docx", ".txt", ".md", ".py", ".csv"}
IMAGE_TYPES = {
    ".png": "image/png",
    ".jpg": "image/jpeg",
    ".jpeg": "image/jpeg",
    ".webp": "image/webp",
    ".gif": "image/gif",
}
DOCUMENT_TYPES = {
    ".pdf": "application/pdf",
    ".docx": (
        "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
    ),
    ".txt": "text/plain",
    ".md": "text/markdown",
    ".py": "text/x-python",
    ".csv": "text/csv",
}
# Magic numbers, so a renamed file can't pose as an image.
_IMAGE_SIGNATURES = (
    b"\x89PNG\r\n\x1a\n",
    b"\xff\xd8\xff",
    b"GIF87a",
    b"GIF89a",
)


class FileRejected(Exception):
    """The upload is not acceptable; the message is shown to the user."""

    def __init__(self, message: str, status_code: int = 400):
        super().__init__(message)
        self.status_code = status_code


def safe_filename(name: str | None, fallback: str = "uploaded_file") -> str:
    cleaned = Path((name or fallback).replace("\\", "/")).name.replace(" ", "_")
    return cleaned or fallback


def classify(filename: str) -> str | None:
    suffix = Path(filename).suffix.lower()
    if suffix in IMAGE_TYPES:
        return "image"
    if suffix in DOCUMENT_EXTENSIONS:
        return "document"
    return None


def looks_like_image(data: bytes) -> bool:
    if data.startswith(_IMAGE_SIGNATURES):
        return True
    return data[:4] == b"RIFF" and data[8:12] == b"WEBP"


def mime_for(filename: str) -> str:
    suffix = Path(filename).suffix.lower()
    return IMAGE_TYPES.get(suffix) or DOCUMENT_TYPES.get(suffix) or "application/octet-stream"


def limit_bytes(kind: str) -> int:
    megabytes = MAX_IMAGE_MB if kind == "image" else MAX_UPLOAD_MB
    return megabytes * 1024 * 1024


def stored_path(stored_name: str) -> Path:
    """Resolve a stored name inside the uploads folder, refusing escapes."""
    uploads = UPLOADS_DIR.resolve()
    candidate = (uploads / stored_name).resolve()
    if not candidate.is_relative_to(uploads):
        raise FileRejected("Invalid file.", status_code=404)
    return candidate


def file_url(file_id: str) -> str:
    return f"/files/{file_id}/content"


def serialize(item) -> dict:
    return {
        "id": item.id,
        "name": item.filename,
        "kind": item.kind,
        "mime_type": item.mime_type,
        "size": item.size,
        "origin": item.origin,
        "thread_id": item.thread_id,
        "url": file_url(item.id),
        "created_at": item.created_at.isoformat() if item.created_at else None,
    }


def attachment_summary(item) -> dict:
    """The small record kept on a chat message for its attachments."""
    return {
        "id": item.id,
        "name": item.filename,
        "kind": item.kind,
        "url": file_url(item.id),
    }


def store_bytes(
    *,
    data: bytes,
    filename: str,
    kind: str,
    thread_id: str,
    client_id: str,
    origin: str = "upload",
):
    """Write bytes to disk, index documents for RAG, and record the file."""
    if kind == "image" and not looks_like_image(data):
        raise FileRejected("That file is not a valid PNG, JPEG, WEBP or GIF image.")

    file_id = str(uuid.uuid4())
    stored_name = f"{file_id}_{filename}"
    path = stored_path(stored_name)
    path.write_bytes(data)

    chunks = 0
    try:
        if kind == "document":
            result = add_document_to_rag(file_path=str(path), thread_id=thread_id)
            chunks = result["chunks"]

        return add_uploaded_file(
            id=file_id,
            client_id=client_id,
            thread_id=thread_id,
            filename=filename,
            stored_name=stored_name,
            kind=kind,
            mime_type=mime_for(filename),
            size=len(data),
            chunks=chunks,
            origin=origin,
        )
    except Exception:
        path.unlink(missing_ok=True)
        raise


def copy_to_thread(item, thread_id: str, client_id: str):
    """Attach a library file to another chat without re-embedding it."""
    new_id = str(uuid.uuid4())
    new_stored_name = f"{new_id}_{item.filename}"
    source = stored_path(item.stored_name)
    target = stored_path(new_stored_name)

    if not source.is_file():
        raise FileRejected("This file is no longer available.", status_code=404)

    shutil.copyfile(source, target)

    try:
        if item.kind == "document":
            db = SessionLocal()
            try:
                with db.begin():
                    rows = db.scalars(
                        select(DocumentChunk).where(
                            DocumentChunk.thread_id == item.thread_id
                        )
                    ).all()
                    for row in rows:
                        metadata = dict(row.cmetadata or {})
                        if metadata.get("source") != item.stored_name:
                            continue
                        metadata.update(thread_id=thread_id, source=new_stored_name)
                        db.add(
                            DocumentChunk(
                                id=str(uuid.uuid4()),
                                thread_id=thread_id,
                                content=row.content,
                                cmetadata=metadata,
                                embedding=row.embedding,
                            )
                        )
            finally:
                db.close()

        return add_uploaded_file(
            id=new_id,
            client_id=client_id,
            thread_id=thread_id,
            filename=item.filename,
            stored_name=new_stored_name,
            kind=item.kind,
            mime_type=item.mime_type,
            size=item.size,
            chunks=item.chunks,
            origin=item.origin,
        )
    except Exception:
        target.unlink(missing_ok=True)
        raise


# ---------- Vision ----------


def _vision_llm():
    from langchain_groq import ChatGroq

    return ChatGroq(model=VISION_MODEL, temperature=0.2, max_retries=1, timeout=60)


def describe_images(images: list, question: str) -> str:
    """Turn attached images into text the (text-only) chat model can use."""
    if not images:
        return ""

    content: list[dict] = [
        {
            "type": "text",
            "text": (
                "The user attached the image(s) below and asked: "
                f"{question!r}\n\n"
                "For each image, describe everything relevant in detail: "
                "objects, layout, any text (transcribe it exactly), code, "
                "charts, numbers, diagrams or hand-drawn sketches. Do not "
                "answer the question itself; only describe."
            ),
        }
    ]
    for item in images:
        data = stored_path(item.stored_name).read_bytes()
        encoded = base64.b64encode(data).decode("ascii")
        content.append(
            {
                "type": "image_url",
                "image_url": {"url": f"data:{item.mime_type};base64,{encoded}"},
            }
        )

    try:
        response = _vision_llm().invoke([HumanMessage(content=content)])
        text = response.content if isinstance(response.content, str) else ""
    except Exception as exc:  # vision is best-effort; the chat still runs
        logger.exception("Vision model failed")
        return f"(The attached image could not be analysed: {exc})"

    # Reasoning models may prefix their answer with a <think> block.
    text = re.sub(r"<think>.*?(</think>|$)", "", text, flags=re.DOTALL)
    return text.strip()


# ---------- Image generation ----------


_IMAGE_RETRY_STATUS_CODES = {402, 429, 500, 502, 503, 504}
_IMAGE_GENERATION_ATTEMPTS = 3
_IMAGE_RETRY_DELAY_SECONDS = 5.25
_IMAGE_MAX_RETRY_DELAY_SECONDS = 50.0


def _image_retry_delay(response: httpx.Response) -> float:
    retry_after = response.headers.get("Retry-After", "").strip()
    if retry_after:
        try:
            return min(
                max(float(retry_after) + 0.75, _IMAGE_RETRY_DELAY_SECONDS),
                _IMAGE_MAX_RETRY_DELAY_SECONDS,
            )
        except ValueError:
            pass

    match = re.search(r"retry after\s+(\d+(?:\.\d+)?)s", response.text, re.I)
    if match:
        return min(
            max(float(match.group(1)) + 0.75, _IMAGE_RETRY_DELAY_SECONDS),
            _IMAGE_MAX_RETRY_DELAY_SECONDS,
        )
    return _IMAGE_RETRY_DELAY_SECONDS


def generate_image_bytes(prompt: str) -> bytes:
    url = IMAGE_GENERATION_URL.replace("{prompt}", quote(prompt, safe="")).replace(
        "{seed}", str(random.randint(1, 2_000_000_000))
    )
    # The legacy Pollinations endpoint accepts these quality options. Preserve
    # custom providers by adding them only for Pollinations URLs and only when
    # the deployment has not already selected an explicit value.
    if "pollinations.ai" in url:
        quality_options = {
            "model": "sana",
            "enhance": "false",
            "quality": "high",
            "guidance_scale": "12",
            "nologo": "true",
        }
        if re.search(r"\b(?:son\s+)?goku\b", prompt, re.I):
            quality_options["negative_prompt"] = quote(
                "photorealistic, live action, realistic human face, 3D render, "
                "western comic, generic anime character, character redesign, "
                "wrong costume, black gi, dark outfit, sleeveless black shirt, "
                "cloak, brown or yellow gi, angry scowl, circular portrait "
                "frame, moon background, blurry face, deformed "
                "hands, extra fingers, closed eyes, reference sheet, multiple "
                "views, collage, duplicated character, text, logo, watermark",
                safe="",
            )
        elif re.search(r"\bben\s*(?:10|ten)\b", prompt, re.I):
            quality_options["negative_prompt"] = quote(
                "adult, woman, girl, female, feminine body, cleavage, revealing "
                "outfit, black bodysuit, realistic person, photorealistic, 3D "
                "render, long hair, teenager, wrong costume, diagonal stripe, "
                "green shirt, green shirt stripe, green clothing except cargo "
                "pants, high collar, turtleneck, long-sleeve "
                "undershirt, missing Omnitrix, hidden left wrist, watch on right "
                "wrist, circular frame, collage, duplicated character, text, "
                "logo, watermark",
                safe="",
            )
        for name, value in quality_options.items():
            if f"{name}=" not in url:
                separator = "&" if "?" in url else "?"
                url += f"{separator}{name}={value}"
    response = None
    for attempt in range(_IMAGE_GENERATION_ATTEMPTS):
        response = httpx.get(
            url,
            timeout=max(EXTERNAL_API_TIMEOUT_SECONDS, 120.0),
            follow_redirects=True,
        )
        if (
            response.status_code not in _IMAGE_RETRY_STATUS_CODES
            or attempt == _IMAGE_GENERATION_ATTEMPTS - 1
        ):
            break

        # The anonymous legacy endpoint returns the remaining per-IP cooldown
        # in its 402 response. Waiting for that reset avoids repeated failures.
        delay = _image_retry_delay(response)
        response.close()
        time.sleep(delay)

    response.raise_for_status()
    data = response.content

    if not looks_like_image(data):
        raise RuntimeError("The image service did not return an image.")
    return add_devgpt_watermark(data)


def add_devgpt_watermark(data: bytes) -> bytes:
    """Add DevGPT branding while retaining the provider's own attribution."""
    try:
        with Image.open(BytesIO(data)) as source:
            source_format = (source.format or "PNG").upper()
            image = source.convert("RGBA")
    except (UnidentifiedImageError, OSError):
        logger.warning("Could not decode generated image for DevGPT branding")
        return data

    width, height = image.size
    font_size = max(18, min(width, height) // 24)
    font = ImageFont.load_default(size=font_size)
    label = "DevGPT"
    overlay = Image.new("RGBA", image.size, (0, 0, 0, 0))
    draw = ImageDraw.Draw(overlay)
    text_box = draw.textbbox((0, 0), label, font=font, stroke_width=1)
    text_width = text_box[2] - text_box[0]
    text_height = text_box[3] - text_box[1]
    padding_x = max(10, font_size // 2)
    padding_y = max(7, font_size // 3)
    margin = max(10, font_size // 2)
    left = margin
    top = height - text_height - (padding_y * 2) - margin
    right = left + text_width + (padding_x * 2)
    bottom = height - margin

    draw.rounded_rectangle(
        (left, top, right, bottom),
        radius=max(8, font_size // 3),
        fill=(7, 10, 28, 205),
        outline=(99, 102, 241, 235),
        width=max(1, font_size // 12),
    )
    draw.text(
        (left + padding_x, top + padding_y - text_box[1]),
        label,
        font=font,
        fill=(255, 255, 255, 255),
        stroke_width=1,
        stroke_fill=(30, 33, 70, 255),
    )
    branded = Image.alpha_composite(image, overlay)
    output = BytesIO()
    if source_format in {"JPG", "JPEG"}:
        branded.convert("RGB").save(output, format="JPEG", quality=95, optimize=True)
    elif source_format == "WEBP":
        branded.save(output, format="WEBP", quality=95, method=6)
    else:
        branded.save(output, format="PNG", optimize=True)
    return output.getvalue()


def image_extension(data: bytes) -> str:
    if data.startswith(b"\x89PNG"):
        return ".png"
    if data.startswith(b"GIF8"):
        return ".gif"
    if data[:4] == b"RIFF":
        return ".webp"
    return ".jpg"
