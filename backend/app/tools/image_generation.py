from langchain_core.runnables import RunnableConfig
from langchain_core.tools import tool
from pydantic import BaseModel, Field

from app.db import get_conversation_owner
from app.services.files import (
    generate_image_bytes,
    image_extension,
    store_bytes,
)


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
        data = generate_image_bytes(prompt)
    except Exception as exc:
        return f"Image generation failed: {exc}"

    slug = "-".join(prompt.lower().split()[:6]) or "image"
    slug = "".join(ch for ch in slug if ch.isalnum() or ch == "-")[:48] or "image"
    item = store_bytes(
        data=data,
        kind="image",
        filename=f"{slug}{image_extension(data)}",
        thread_id=thread_id,
        client_id=client_id,
        origin="generated",
    )

    return (
        f"IMAGE_URL: /files/{item.id}/content\n"
        "The image was generated and is already displayed to the user above "
        "your reply. Do not repeat the URL or image markdown; just describe "
        "briefly what you created and offer variations."
    )
