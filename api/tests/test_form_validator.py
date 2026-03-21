# api/tests/test_form_validator.py
import pytest
from app.services.form_validator import validate_form_data


def test_rejects_missing_required_field():
    with pytest.raises(ValueError, match="必填"):
        validate_form_data("intake", {})
    # intake requires: child_alias, age


def test_rejects_wrong_type_for_number():
    with pytest.raises(ValueError, match="数值"):
        validate_form_data("intake", {
            "child_alias": "test",
            "age": "not-a-number",
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
        "age": 4,
        "parent_note": "optional note",
    })
    assert result["child_alias"] == "doudou"
    assert result["age"] == 4


def test_allows_empty_optional_fields():
    result = validate_form_data("privacy_filter", {})
    # privacy_filter has source_description as optional
    assert isinstance(result, dict)
