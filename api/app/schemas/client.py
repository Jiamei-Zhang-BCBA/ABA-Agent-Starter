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
