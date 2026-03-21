"""
Feature Gate Service.
Computes visible features for a user based on plan × role intersection.
"""

from __future__ import annotations

from fastapi import HTTPException, status

from app.models.user import User
from app.core.feature_registry import get_public_features, get_feature, FEATURE_REGISTRY
from app.core.plan_config import get_plan_config, PLAN_CONFIGS
from app.core.role_config import get_visible_features


def get_user_plan_name(user: User) -> str:
    """Extract plan name from user's tenant. Falls back to starter."""
    plan = user.tenant.plan
    if plan and plan.name in PLAN_CONFIGS:
        return plan.name
    return "starter"


def get_user_visible_feature_ids(user: User) -> list[str]:
    """Compute the set of feature IDs visible to this user."""
    plan_name = get_user_plan_name(user)
    plan_config = get_plan_config(plan_name)
    if plan_config is None:
        return []

    plan_feature_ids = plan_config.get_feature_ids()
    return get_visible_features(user.role, plan_feature_ids)


def get_user_features_public(user: User) -> list[dict]:
    """Return public feature dicts for frontend rendering."""
    feature_ids = get_user_visible_feature_ids(user)
    return get_public_features(feature_ids)


def check_feature_access(user: User, feature_id: str) -> None:
    """Raise 403 if user cannot access this feature."""
    allowed = get_user_visible_feature_ids(user)
    if feature_id not in allowed:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=f"Feature '{feature_id}' not available in your plan/role",
        )
