from typing import Annotated
from uuid import UUID

from fastapi import Header, Query, Request
from fastapi.responses import JSONResponse

from app.core.config import REQUIRE_CLIENT_ID


LEGACY_CLIENT_ID = "legacy"
CLIENT_ID_ERROR = "Client ID is required."


class ClientIdError(Exception):
    pass


def validate_client_id(value: str | None) -> str:
    if value is None or not value.strip():
        raise ClientIdError

    try:
        return str(UUID(value.strip()))
    except ValueError as exc:
        raise ClientIdError from exc


def get_client_id(
    x_client_id: Annotated[
        str | None,
        Header(alias="X-Client-Id"),
    ] = None,
) -> str:
    if x_client_id is None and not REQUIRE_CLIENT_ID:
        return LEGACY_CLIENT_ID
    return validate_client_id(x_client_id)


def get_close_client_id(
    client_id: Annotated[str | None, Query()] = None,
) -> str:
    return validate_client_id(client_id)


async def client_id_error_handler(
    request: Request,
    exc: ClientIdError,
) -> JSONResponse:
    return JSONResponse(
        {"error": CLIENT_ID_ERROR},
        status_code=400,
    )
