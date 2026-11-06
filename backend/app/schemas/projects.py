from datetime import datetime
from typing import Annotated

from pydantic import BaseModel, ConfigDict, StringConstraints


ProjectName = Annotated[
    str,
    StringConstraints(strip_whitespace=True, min_length=1, max_length=60),
]
ProjectInstructions = Annotated[
    str,
    StringConstraints(strip_whitespace=True, max_length=4000),
]


class ProjectOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    name: str
    instructions: str
    created_at: datetime
    updated_at: datetime


class ProjectListResponse(BaseModel):
    projects: list[ProjectOut]


class ProjectCreateRequest(BaseModel):
    name: ProjectName
    instructions: ProjectInstructions = ""


class ProjectUpdateRequest(BaseModel):
    name: ProjectName | None = None
    instructions: ProjectInstructions | None = None


class ProjectDeleteResponse(BaseModel):
    success: bool
