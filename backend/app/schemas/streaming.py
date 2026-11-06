from pydantic import BaseModel


class StreamEvent(BaseModel):
    token: str | None = None
    error: str | None = None
    done: bool | None = None
