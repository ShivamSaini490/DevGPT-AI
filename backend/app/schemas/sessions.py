from pydantic import BaseModel


class SessionHeartbeatResponse(BaseModel):
    success: bool
