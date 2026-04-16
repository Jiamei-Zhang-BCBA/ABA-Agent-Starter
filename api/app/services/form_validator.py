"""
Form input validation against FeatureModule.form_schema.
Enforces required fields, type checking, range validation,
file extension validation, and strips unknown fields.
"""

from __future__ import annotations

from app.core.feature_registry import get_feature, FormField


# Number range constraints by field name
NUMBER_RANGES: dict[str, tuple[float, float]] = {
    "age": (0, 99),
}


# Either-or constraints: at least one of the listed fields must be provided.
# Format: feature_id -> list of (field_name_a, field_name_b, error_label)
EITHER_OR_RULES: dict[str, list[tuple[str, str, str]]] = {
    "session_review": [
        ("session_text", "session_file", "课后记录文字 或 课后记录文件"),
    ],
    "staff_supervision": [
        ("observation_text", "observation_file", "听课随笔 或 听课记录文件"),
    ],
}


def validate_form_data(feature_id: str, form_data: dict, uploaded_filenames: list[str] | None = None) -> dict:
    """
    Validate form_data against the feature's form_schema.
    Returns sanitized dict with only known fields.
    Raises ValueError for validation failures.

    `uploaded_filenames` is the list of file names attached to this submission;
    used by either-or rules that pair a textarea with a file upload.
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

        # select_client / select_staff are dynamic options handled by router
        if field.type in ("select_client", "select_staff"):
            if value:
                validated[field.name] = str(value)
            continue

        # Required check (applies to text/textarea/number/select)
        if field.required and (value is None or str(value).strip() == ""):
            raise ValueError(f"必填字段缺失: {field.label}")

        if value is None or str(value).strip() == "":
            continue

        # Type validation
        validated[field.name] = _validate_field_type(field, value)

    # Either-or post-check
    files = uploaded_filenames or []
    for text_field, file_field, label in EITHER_OR_RULES.get(feature_id, []):
        has_text = bool(validated.get(text_field, "").strip()) if isinstance(validated.get(text_field), str) else bool(validated.get(text_field))
        has_file = bool(files)  # any uploaded file counts; finer-grained mapping not needed yet
        if not has_text and not has_file:
            raise ValueError(f"必须至少提供其一: {label}")

    return validated


def validate_file_extensions(feature_id: str, filenames: list[str]) -> None:
    """
    Validate uploaded file extensions against the feature's accepted types.
    Raises ValueError if any file has an unaccepted extension.
    """
    feature = get_feature(feature_id)
    if feature is None:
        return

    # Collect all accepted extensions from file fields
    accepted = set()
    for field in feature.form_schema:
        if field.type == "file" and field.accept:
            accepted.update(ext.lower() for ext in field.accept)

    if not accepted:
        return

    for filename in filenames:
        ext = ""
        if "." in filename:
            ext = "." + filename.rsplit(".", 1)[-1].lower()
        if ext not in accepted:
            raise ValueError(
                f"文件 {filename} 的格式 ({ext or '无扩展名'}) 不被接受。"
                f"支持的格式: {', '.join(sorted(accepted))}"
            )


def _validate_field_type(field: FormField, value) -> str | int | float:
    """Validate and coerce a single field value."""
    if field.type == "number":
        try:
            num = float(value) if "." in str(value) else int(value)
        except (ValueError, TypeError):
            raise ValueError(f"{field.label} 必须为数值")

        # Range validation
        if field.name in NUMBER_RANGES:
            lo, hi = NUMBER_RANGES[field.name]
            if num < lo or num > hi:
                raise ValueError(f"{field.label} 必须在 {lo} 到 {hi} 之间")

        return num

    if field.type in ("text", "textarea"):
        text = str(value).strip()
        if field.type == "textarea" and len(text) > 5000:
            raise ValueError(f"{field.label} 超过 5000 字限制")
        if field.type == "text" and len(text) > 500:
            raise ValueError(f"{field.label} 超过 500 字限制")
        return text

    if field.type == "select":
        text = str(value).strip()
        valid_values = {opt.get("value") for opt in field.options}
        if valid_values and text not in valid_values:
            raise ValueError(f"{field.label} 取值无效（必须是: {', '.join(sorted(valid_values))}）")
        return text

    return str(value)
