from pydantic import BaseModel
from datetime import datetime
from typing import Any


class JobCreateRequest(BaseModel):
    feature_id: str
    client_id: str | None = None
    form_data: dict[str, Any] = {}


class JobResponse(BaseModel):
    id: str
    tenant_id: str
    user_id: str
    client_id: str | None
    feature_id: str
    status: str
    created_at: datetime
    completed_at: datetime | None = None

    model_config = {"from_attributes": True}


class JobDetailResponse(JobResponse):
    form_data_json: dict[str, Any] = {}
    output_content: str | None = None
    error_message: str | None = None
    input_tokens: int = 0
    output_tokens: int = 0


class JobListResponse(BaseModel):
    jobs: list[JobResponse]
    total: int
