from typing import Annotated

from pydantic import BaseModel, StringConstraints, field_validator


StrippedNonEmptyString = Annotated[
    str,
    StringConstraints(strip_whitespace=True, min_length=1),
]


class ChatRequest(BaseModel):
    message: StrippedNonEmptyString
    thread_id: StrippedNonEmptyString = "default"
    model: str | None = None

    @field_validator("model", mode="before")
    @classmethod
    def use_default_for_non_string_model(cls, value):
        return value if isinstance(value, str) else None
