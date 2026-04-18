# api/tests/test_review_service_unit.py
"""
Pure-function unit tests for app.services.review_service helpers.

Currently covers ``_normalize_client_code`` — the idempotent alias-to-code
normalizer introduced by BUG #20 fix.

BUG #20 context:
    The previous ``f"A-{alias}"`` formatting assumed ``child_alias`` was a
    bare alias (e.g. "小磊"). When users submitted the fully-qualified code
    ("A-小磊") the route produced "A-A-小磊" and wrote a rogue folder tree.
"""

import pytest

from app.services.review_service import _normalize_client_code


# ---------------------------------------------------------------------------
# Alias shape matrix (BUG #20)
# ---------------------------------------------------------------------------

@pytest.mark.parametrize(
    "alias_input, expected",
    [
        # 1. bare alias — the "historical happy path"
        ("小磊", "A-小磊"),
        # 2. already fully-qualified code — the BUG #20 trigger
        ("A-小磊", "A-小磊"),
        # 3. lowercase prefix — users who typed manually
        ("a-小磊", "A-小磊"),
    ],
)
def test_normalize_client_code_idempotent_shapes(alias_input, expected):
    """All three alias shapes must collapse to the same canonical code."""
    assert _normalize_client_code(alias_input) == expected


def test_normalize_client_code_empty_and_none_return_empty_string():
    """Empty / None / whitespace-only input must NOT yield a dangling ``A-`` prefix."""
    assert _normalize_client_code("") == ""
    assert _normalize_client_code(None) == ""
    assert _normalize_client_code("   ") == ""


def test_normalize_client_code_strips_surrounding_whitespace():
    """Trailing / leading whitespace should not break idempotency."""
    assert _normalize_client_code("  小磊  ") == "A-小磊"
    assert _normalize_client_code("  A-小磊  ") == "A-小磊"


def test_normalize_client_code_preserves_alias_content_with_hyphen():
    """Hyphens inside the alias body must survive (only the leading A- is consumed)."""
    # "A-B-X" — leading A- is a prefix, the rest "B-X" is the alias body.
    assert _normalize_client_code("A-B-X") == "A-B-X"
    # Bare alias containing a hyphen also works.
    assert _normalize_client_code("B-X") == "A-B-X"
