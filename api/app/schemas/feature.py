from pydantic import BaseModel
from typing import Any


class FormFieldSchema(BaseModel):
    name: str
    label: str
    type: str
    required: bool
    accept: list[str] = []
    options: list[dict[str, str]] = []


class FormSchema(BaseModel):
    fields: list[FormFieldSchema]


class FeatureResponse(BaseModel):
    id: str
    display_name: str
    description: str
    icon: str
    category: str
    form_schema: FormSchema
    output_template: str


class FeatureListResponse(BaseModel):
    features: list[FeatureResponse]
