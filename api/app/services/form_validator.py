"""
Form input validation against FeatureModule.form_schema.
Enforces required fields, type checking, and strips unknown fields.
"""

from __future__ import annotations

from app.core.feature_registry import get_feature, FormField


def validate_form_data(feature_id: str, form_data: dict) -> dict:
    """
    Validate form_data against the feature's form_schema.
    Returns sanitized dict with only known fields.
    Raises ValueError for validation failures.
    """
    feature = get_feature(feature_id)
    if feature is None:
        raise ValueError(f"Unknown feature: {feature_id}")

    validated = {}

    for field in feature.form_schema:
        value = form_data.get(field.name)

        # Skip file fields (handled separately via multipart upload)
        if field.type == "file":
            continue

        # Skip select fields (client_id/staff_id handled by router)
        if field.type in ("select_client", "select_staff"):
            if value:
                validated[field.name] = str(value)
            continue

        # Required check
        if field.required and (value is None or str(value).strip() == ""):
            raise ValueError(f"必填字段缺失: {field.label}")

        if value is None:
            continue

        # Type validation
        validated[field.name] = _validate_field_type(field, value)

    return validated


def _validate_field_type(field: FormField, value) -> str | int | float:
    """Validate and coerce a single field value."""
    if field.type == "number":
        try:
            num = float(value) if "." in str(value) else int(value)
        except (ValueError, TypeError):
            raise ValueError(f"{field.label} 必须为数值")
        return num

    if field.type in ("text", "textarea"):
        text = str(value).strip()
        if field.type == "textarea" and len(text) > 5000:
            raise ValueError(f"{field.label} 超过 5000 字限制")
        if field.type == "text" and len(text) > 500:
            raise ValueError(f"{field.label} 超过 500 字限制")
        return text

    return str(value)
