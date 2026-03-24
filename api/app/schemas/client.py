from typing import Literal

from pydantic import BaseModel
from datetime import datetime


class ClientCreateRequest(BaseModel):
    code_name: str
    display_alias: str


class ClientResponse(BaseModel):
    id: str
    tenant_id: str
    code_name: str
    display_alias: str
    status: str
    created_at: datetime

    model_config = {"from_attributes": True}


class StaffResponse(BaseModel):
    id: str
    name: str
    role: str

    model_config = {"from_attributes": True}


# --- Assignment schemas ---

class ClientAssignRequest(BaseModel):
    user_id: str
    relation: Literal["teacher", "parent"]


class ClientAssignmentResponse(BaseModel):
    id: str
    client_id: str
    user_id: str
    user_name: str
    user_role: str
    relation: str
