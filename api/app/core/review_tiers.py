"""
Review tier classification.
Determines whether a job's output goes directly to the user or requires expert review.
"""

REVIEW_TIER_AUTO = "auto"
REVIEW_TIER_EXPERT = "expert"

# Quick lookup: skill_name -> tier
SKILL_REVIEW_TIERS: dict[str, str] = {
    # auto — AI direct output
    "privacy-filter": REVIEW_TIER_AUTO,
    "session-reviewer": REVIEW_TIER_AUTO,
    "staff-supervision": REVIEW_TIER_AUTO,
    "teacher-guide": REVIEW_TIER_AUTO,
    "parent-update": REVIEW_TIER_AUTO,
    "quick-summary": REVIEW_TIER_AUTO,
    "clinical-reflection": REVIEW_TIER_AUTO,
    "staff-onboarding": REVIEW_TIER_AUTO,
    "reinforcer-tracker": REVIEW_TIER_AUTO,

    # expert — must be reviewed
    "intake-interview": REVIEW_TIER_EXPERT,
    "profile-builder": REVIEW_TIER_EXPERT,
    "assessment-logger": REVIEW_TIER_EXPERT,
    "fba-analyzer": REVIEW_TIER_EXPERT,
    "plan-generator": REVIEW_TIER_EXPERT,
    "program-slicer": REVIEW_TIER_EXPERT,
    "milestone-report": REVIEW_TIER_EXPERT,
    "transfer-protocol": REVIEW_TIER_EXPERT,
}
