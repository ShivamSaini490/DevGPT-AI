from pydantic import BaseModel


class StreamEvent(BaseModel):
    token: str | None = None
    # Full answer text the client should show instead of what it has so far.
    # Sent when text already streamed turns out to belong to a tool-calling
    # step (the model "thinking aloud") and must be withdrawn.
    replace: str | None = None
    error: str | None = None
    done: bool | None = None
