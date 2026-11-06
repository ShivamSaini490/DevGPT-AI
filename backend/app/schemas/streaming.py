from pydantic import BaseModel


class StreamEvent(BaseModel):
    token: str | None = None
    # Full answer text the client should show instead of what it has so far.
    # Sent when text already streamed turns out to belong to a tool-calling
    # step (the model "thinking aloud") and must be withdrawn.
    replace: str | None = None
    # Name of a tool the model started calling (for a status chip).
    tool: str | None = None
    # Model reasoning text, shown separately from the answer.
    reasoning: str | None = None
    error: str | None = None
    done: bool | None = None
