"""
Role-based feature access control.
Determines which features each role can see within their plan's allowance.
"""

from __future__ import annotations

ROLE_FEATURES: dict[str, list[str] | str] = {
    "org_admin": "__all_in_plan__",
    "bcba": "__all_in_plan__",
    "teacher": [
        "session_review",
        "teacher_guide",
        "quick_summary",
    ],
    "parent": [
        "parent_letter",
        "quick_summary",
    ],
}


def get_visible_features(role: str, plan_feature_ids: list[str]) -> list[str]:
    """
    Compute the intersection of plan features and role features.
    visible = plan_features ∩ role_features
    """
    role_allowed = ROLE_FEATURES.get(role, [])

    if role_allowed == "__all_in_plan__":
        return plan_feature_ids

    return [fid for fid in role_allowed if fid in plan_feature_ids]
