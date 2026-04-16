"""
Plan (subscription tier) configuration.
Controls which features a tenant organization can access.
"""

from __future__ import annotations

from dataclasses import dataclass
from app.core.feature_registry import get_all_feature_ids


@dataclass(frozen=True)
class PlanConfig:
    name: str
    display_name: str
    features: list[str] | str  # list of feature_ids or "__all__"
    max_clients: int
    max_staff: int
    monthly_jobs: int
    price_cents: int

    def get_feature_ids(self) -> list[str]:
        if self.features == "__all__":
            return get_all_feature_ids()
        return list(self.features)


PLAN_CONFIGS: dict[str, PlanConfig] = {
    "starter": PlanConfig(
        name="starter",
        display_name="基础版",
        features=[
            "intake", "session_review", "parent_letter",
            "teacher_guide", "quick_summary", "assessment",
            "fba", "plan_generator", "staff_supervision",
            "reinforcer", "program_slicer", "clinical_reflection",
        ],
        max_clients=10,
        max_staff=5,
        monthly_jobs=200,
        price_cents=19900,
    ),
    "professional": PlanConfig(
        name="professional",
        display_name="专业版",
        features=[
            "intake", "session_review", "parent_letter",
            "teacher_guide", "quick_summary", "assessment",
            "fba", "plan_generator", "staff_supervision",
            "reinforcer", "program_slicer", "clinical_reflection",
        ],
        max_clients=30,
        max_staff=15,
        monthly_jobs=500,
        price_cents=99900,
    ),
    "enterprise": PlanConfig(
        name="enterprise",
        display_name="旗舰版",
        features="__all__",
        max_clients=-1,
        max_staff=-1,
        monthly_jobs=2000,
        price_cents=399900,
    ),
}


def get_plan_config(plan_name: str) -> PlanConfig | None:
    return PLAN_CONFIGS.get(plan_name)
