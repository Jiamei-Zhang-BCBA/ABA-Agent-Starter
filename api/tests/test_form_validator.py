# api/tests/test_form_validator.py
import pytest
from app.services.form_validator import validate_form_data


def test_rejects_missing_required_field():
    with pytest.raises(ValueError, match="必填"):
        validate_form_data("intake", {})
    # intake requires: child_alias (file fields validated separately)


def test_rejects_unknown_select_value():
    """quick_summary.purpose is a select; invalid value must be rejected."""
    with pytest.raises(ValueError, match="取值无效"):
        validate_form_data("quick_summary", {
            "client_id": "00000000-0000-0000-0000-000000000000",
            "purpose": "not-a-valid-option",
        })


def test_strips_unknown_fields():
    result = validate_form_data("privacy_filter", {
        "source_description": "legit note",
        "injected_field": "should be stripped",
        "__proto__": "attack",
    })
    assert "injected_field" not in result
    assert "__proto__" not in result
    assert result["source_description"] == "legit note"


def test_passes_valid_form():
    result = validate_form_data("intake", {
        "child_alias": "doudou",
        "parent_note": "optional note",
    })
    assert result["child_alias"] == "doudou"
    assert result["parent_note"] == "optional note"


def test_allows_empty_optional_fields():
    result = validate_form_data("privacy_filter", {})
    # privacy_filter has source_description as optional
    assert isinstance(result, dict)


def test_select_accepts_valid_value():
    """plan_generator.plan_type is a select; valid value must pass."""
    result = validate_form_data("plan_generator", {
        "client_id": "00000000-0000-0000-0000-000000000000",
        "plan_type": "IEP",
        "focus_areas": "mand training",
    })
    assert result["plan_type"] == "IEP"


def test_either_or_session_review_requires_text_or_file():
    """session_review must provide session_text OR session_file."""
    with pytest.raises(ValueError, match="至少提供其一"):
        validate_form_data("session_review", {
            "client_id": "00000000-0000-0000-0000-000000000000",
            "staff_id": "00000000-0000-0000-0000-000000000000",
        }, uploaded_filenames=[])


def test_either_or_session_review_text_only_passes():
    """session_review with only session_text should pass."""
    result = validate_form_data("session_review", {
        "client_id": "00000000-0000-0000-0000-000000000000",
        "staff_id": "00000000-0000-0000-0000-000000000000",
        "session_text": "kid did 3 mands today",
    }, uploaded_filenames=[])
    assert result["session_text"].startswith("kid")


def test_either_or_session_review_file_only_passes():
    """session_review with only an uploaded file should pass."""
    result = validate_form_data("session_review", {
        "client_id": "00000000-0000-0000-0000-000000000000",
        "staff_id": "00000000-0000-0000-0000-000000000000",
    }, uploaded_filenames=["session.pdf"])
    assert "session_text" not in result
