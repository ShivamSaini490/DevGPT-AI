import uuid
from typing import Annotated

from fastapi import APIRouter, Depends
from fastapi.responses import JSONResponse

from app.api.dependencies import get_client_id
from app.db import create_project, delete_project, list_projects, update_project
from app.schemas.projects import (
    ProjectCreateRequest,
    ProjectDeleteResponse,
    ProjectListResponse,
    ProjectOut,
    ProjectUpdateRequest,
)


router = APIRouter()

NOT_FOUND = {"error": "Project not found."}


@router.get("/projects", response_model=ProjectListResponse)
async def projects(client_id: Annotated[str, Depends(get_client_id)]):
    return {"projects": list_projects(client_id)}


@router.post("/projects", response_model=ProjectOut, status_code=201)
async def new_project(
    request: ProjectCreateRequest,
    client_id: Annotated[str, Depends(get_client_id)],
):
    return create_project(
        str(uuid.uuid4()),
        client_id,
        request.name,
        request.instructions,
    )


@router.patch("/projects/{project_id}", response_model=ProjectOut)
async def edit_project(
    project_id: str,
    request: ProjectUpdateRequest,
    client_id: Annotated[str, Depends(get_client_id)],
):
    project = update_project(
        project_id,
        client_id,
        name=request.name,
        instructions=request.instructions,
    )
    if project is None:
        return JSONResponse(NOT_FOUND, status_code=404)
    return project


@router.delete("/projects/{project_id}", response_model=ProjectDeleteResponse)
async def remove_project(
    project_id: str,
    client_id: Annotated[str, Depends(get_client_id)],
):
    if not delete_project(project_id, client_id):
        return JSONResponse(NOT_FOUND, status_code=404)
    return ProjectDeleteResponse(success=True)
