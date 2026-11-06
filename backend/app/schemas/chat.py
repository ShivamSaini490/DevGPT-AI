from typing import Annotated

from pydantic import BaseModel, Field, StringConstraints, field_validator


CHAT_MODES = {"web_search", "deep_research", "thinking", "image", "github", "figma"}

StrippedNonEmptyString = Annotated[
    str,
    StringConstraints(strip_whitespace=True, min_length=1),
]


class ChatRequest(BaseModel):
    message: StrippedNonEmptyString
    thread_id: StrippedNonEmptyString = "default"
    model: str | None = None
    # One of the modes from the composer's "+" menu; unknown values are ignored.
    mode: str | None = None
    # Ids of files uploaded via /files (or attached from the library).
    attachments: list[str] = Field(default_factory=list, max_length=10)
    project_id: str | None = None

    @field_validator("mode", mode="before")
    @classmethod
    def known_mode_only(cls, value):
        return value if isinstance(value, str) and value in CHAT_MODES else None

    @field_validator("model", mode="before")
    @classmethod
    def use_default_for_non_string_model(cls, value):
        return value if isinstance(value, str) else None
