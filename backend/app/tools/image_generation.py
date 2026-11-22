from pathlib import Path
import logging

from langchain_core.runnables import RunnableConfig
from langchain_core.tools import tool
from pydantic import BaseModel, Field

from app.db import get_conversation_owner
from app.services.files import store_bytes
from app.services.image_generation import generate_image_with_provider


logger = logging.getLogger(__name__)


class ImageInput(BaseModel):
    prompt: str = Field(
        description=(
            "Detailed English description of the image to create: subject, "
            "style, composition, colours, lighting."
        )
    )


@tool(args_schema=ImageInput)
def generate_image(prompt: str, config: RunnableConfig) -> str:
    """Create a brand-new image from a text description and show it to the user."""
    thread_id = config["configurable"]["thread_id"]
    client_id = get_conversation_owner(thread_id)
    if client_id is None:
        return "Image generation failed: conversation not found."

    try:
        path, provider = generate_image_with_provider(prompt)
        generated_path = Path(path)
        data = generated_path.read_bytes()
    except Exception as exc:
        logger.error("Image generation tool failed: %s", exc)
        return f"Image generation failed: {exc}"

    slug = "-".join(prompt.lower().split()[:6]) or "image"
    slug = "".join(ch for ch in slug if ch.isalnum() or ch == "-")[:48] or "image"
    item = store_bytes(
        data=data,
        kind="image",
        filename=f"{slug}{generated_path.suffix}",
        thread_id=thread_id,
        client_id=client_id,
        origin="generated",
    )

    return (
        f"IMAGE_URL: /files/{item.id}/content\n"
        f"IMAGE_PATH: {generated_path}\n"
        f"IMAGE_PROVIDER: {provider}\n"
        "The image was generated and is already displayed to the user above "
        "your reply. Do not repeat the URL or image markdown; just describe "
        "briefly what you created and offer variations."
    )
