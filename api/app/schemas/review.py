from pydantic import BaseModel
from datetime import datetime


class ReviewResponse(BaseModel):
    id: str
    job_id: str
    reviewer_id: str | None
    output_content: str
    modified_content: str | None
    status: str
    comments: str | None
    created_at: datetime
    reviewed_at: datetime | None

    model_config = {"from_attributes": True}


class ReviewApproveRequest(BaseModel):
    modified_content: str | None = None
    comments: str | None = None


class ReviewRejectRequest(BaseModel):
    comments: str


class AIReviseRequest(BaseModel):
    content: str
    instruction: str


class AIReviseResponse(BaseModel):
    revised_content: str
    input_tokens: int
    output_tokens: int
