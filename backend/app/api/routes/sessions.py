from typing import Annotated

from fastapi import APIRouter, Depends, Response, status

from app.api.dependencies import get_client_id, get_close_client_id
from app.db import heartbeat_client_session, mark_client_session_closing
from app.schemas.sessions import SessionHeartbeatResponse


router = APIRouter()


@router.post(
    "/sessions/heartbeat",
    response_model=SessionHeartbeatResponse,
)
async def heartbeat(
    client_id: Annotated[str, Depends(get_client_id)],
):
    heartbeat_client_session(client_id)
    return SessionHeartbeatResponse(success=True)


@router.post(
    "/sessions/close",
    status_code=status.HTTP_204_NO_CONTENT,
    response_class=Response,
)
async def close_session(
    client_id: Annotated[str, Depends(get_close_client_id)],
):
    mark_client_session_closing(client_id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)
