"""
Pure logic tests for the ABA SaaS feature gating system.

No HTTP server, no database connections — all external dependencies are
replaced with simple MagicMock objects that mirror the real SQLAlchemy
model attribute shapes used by feature_gate.py.

TDD cycle enforced: each test describes expected behaviour; implementation
must satisfy all assertions.
"""

from __future__ import annotations

from unittest.mock import MagicMock

import pytest
from fastapi import HTTPException

# ---------------------------------------------------------------------------
# Modules under test (imported directly — pure logic, no I/O)
# ---------------------------------------------------------------------------

from app.core.feature_registry import (
    FeatureModule,
    get_all_feature_ids,
    get_feature,
    get_public_features,
)
from app.core.plan_config import get_plan_config
from app.core.role_config import get_visible_features
from app.services.feature_gate import check_feature_access, get_user_visible_feature_ids


# ---------------------------------------------------------------------------
# Helper factories
# ---------------------------------------------------------------------------

def _make_plan(name: str) -> MagicMock:
    """Return a mock object that looks like app.models.tenant.Plan."""
    plan = MagicMock()
    plan.name = name
    return plan


def _make_tenant(plan_name: str) -> MagicMock:
    """Return a mock object that looks like app.models.tenant.Tenant."""
    tenant = MagicMock()
    tenant.plan = _make_plan(plan_name)
    return tenant


def _make_user(role: str, plan_name: str) -> MagicMock:
    """Return a mock object that looks like app.models.user.User."""
    user = MagicMock()
    user.role = role
    user.tenant = _make_tenant(plan_name)
    return user


# ---------------------------------------------------------------------------
# Constants mirrored from the registry for test assertions
# ---------------------------------------------------------------------------

STARTER_FEATURES = [
    "intake",
    "session_review",
    "parent_letter",
    "teacher_guide",
    "quick_summary",
]

TEACHER_FEATURES = ["session_review", "teacher_guide", "quick_summary"]
PARENT_FEATURES = ["parent_letter", "quick_summary"]

TOTAL_FEATURE_COUNT = 17

# All keys present in the public dict produced by FeatureModule.to_public_dict()
PUBLIC_DICT_REQUIRED_KEYS = {
    "id",
    "display_name",
    "description",
    "icon",
    "category",
    "form_schema",
    "output_template",
}

# Server-only fields that must NEVER appear in a public dict
PRIVATE_FIELDS = {"_skill_name", "_review_tier", "_model", "_context_files"}


# ===========================================================================
# 1. Feature Registry — get_feature
# ===========================================================================


class TestGetFeature:
    def test_get_feature_existing(self):
        """get_feature('intake') must return a FeatureModule instance."""
        result = get_feature("intake")

        assert result is not None, "Expected a FeatureModule for 'intake', got None"
        assert isinstance(result, FeatureModule)
        assert result.id == "intake"

    def test_get_feature_nonexistent(self):
        """get_feature with an unknown ID must return None (no exception)."""
        result = get_feature("nonexistent")

        assert result is None


# ===========================================================================
# 2. Feature Registry — get_all_feature_ids
# ===========================================================================


class TestGetAllFeatureIds:
    def test_all_features_count(self):
        """Registry must contain exactly 17 feature IDs."""
        ids = get_all_feature_ids()

        assert isinstance(ids, list)
        assert len(ids) == TOTAL_FEATURE_COUNT, (
            f"Expected {TOTAL_FEATURE_COUNT} features, got {len(ids)}: {ids}"
        )

    def test_all_feature_ids_are_strings(self):
        """Every entry in the registry must be a non-empty string key."""
        for fid in get_all_feature_ids():
            assert isinstance(fid, str) and fid, f"Invalid feature ID: {fid!r}"

    def test_all_features_count_is_consistent_with_get_feature(self):
        """Each ID returned by get_all_feature_ids must resolve via get_feature."""
        for fid in get_all_feature_ids():
            assert get_feature(fid) is not None, f"get_feature('{fid}') returned None"


# ===========================================================================
# 3. Plan Config — get_plan_config
# ===========================================================================


class TestGetPlanConfig:
    def test_get_plan_config_nonexistent(self):
        """get_plan_config with an unknown plan name must return None."""
        assert get_plan_config("ultra_premium_9000") is None

    def test_starter_plan_features(self):
        """Starter plan must expose exactly the 5 documented feature IDs."""
        plan = get_plan_config("starter")

        assert plan is not None
        assert sorted(plan.get_feature_ids()) == sorted(STARTER_FEATURES), (
            f"Starter feature mismatch.\n"
            f"  Expected: {sorted(STARTER_FEATURES)}\n"
            f"  Got:      {sorted(plan.get_feature_ids())}"
        )

    def test_professional_plan_feature_count(self):
        """Professional plan must expose exactly 12 feature IDs."""
        plan = get_plan_config("professional")

        assert plan is not None
        assert len(plan.get_feature_ids()) == 12, (
            f"Expected 12 features for professional plan, got {len(plan.get_feature_ids())}"
        )

    def test_enterprise_plan_all_features(self):
        """Enterprise plan must expose all 17 features."""
        plan = get_plan_config("enterprise")

        assert plan is not None
        enterprise_ids = plan.get_feature_ids()
        all_ids = get_all_feature_ids()

        assert len(enterprise_ids) == TOTAL_FEATURE_COUNT, (
            f"Enterprise plan should have {TOTAL_FEATURE_COUNT} features, "
            f"got {len(enterprise_ids)}"
        )
        assert sorted(enterprise_ids) == sorted(all_ids), (
            "Enterprise plan feature IDs must match the full feature registry"
        )


# ===========================================================================
# 4. Role Config — get_visible_features
# ===========================================================================


class TestGetVisibleFeatures:
    def test_org_admin_sees_all_plan_features(self):
        """org_admin with __all_in_plan__ sentinel must pass through all plan IDs."""
        plan = get_plan_config("starter")
        plan_ids = plan.get_feature_ids()

        visible = get_visible_features("org_admin", plan_ids)

        assert len(visible) == len(STARTER_FEATURES), (
            f"org_admin on starter should see {len(STARTER_FEATURES)} features, "
            f"got {len(visible)}"
        )
        assert sorted(visible) == sorted(STARTER_FEATURES)

    def test_bcba_sees_all_plan_features(self):
        """bcba mirrors org_admin — __all_in_plan__ for their plan."""
        plan = get_plan_config("starter")
        plan_ids = plan.get_feature_ids()

        visible = get_visible_features("bcba", plan_ids)

        assert sorted(visible) == sorted(STARTER_FEATURES)

    def test_teacher_role_filtering(self):
        """teacher on enterprise plan sees only their 3 role-permitted features."""
        enterprise_plan = get_plan_config("enterprise")
        plan_ids = enterprise_plan.get_feature_ids()

        visible = get_visible_features("teacher", plan_ids)

        assert sorted(visible) == sorted(TEACHER_FEATURES), (
            f"teacher should see exactly {TEACHER_FEATURES}, got {visible}"
        )

    def test_parent_role_filtering(self):
        """parent on starter plan sees only parent_letter and quick_summary."""
        starter_plan = get_plan_config("starter")
        plan_ids = starter_plan.get_feature_ids()

        visible = get_visible_features("parent", plan_ids)

        assert sorted(visible) == sorted(PARENT_FEATURES), (
            f"parent should see exactly {PARENT_FEATURES}, got {visible}"
        )

    def test_teacher_with_starter_plan(self):
        """teacher on starter plan: role features ∩ plan features = all 3 teacher features."""
        # All 3 teacher features (session_review, teacher_guide, quick_summary)
        # are present in the starter plan, so the result must equal TEACHER_FEATURES.
        starter_plan = get_plan_config("starter")
        plan_ids = starter_plan.get_feature_ids()

        visible = get_visible_features("teacher", plan_ids)

        assert sorted(visible) == sorted(TEACHER_FEATURES), (
            f"All teacher features are in starter; expected {TEACHER_FEATURES}, got {visible}"
        )

    def test_parent_with_professional_plan(self):
        """parent_letter and quick_summary are in professional; parent must see both."""
        professional_plan = get_plan_config("professional")
        plan_ids = professional_plan.get_feature_ids()

        visible = get_visible_features("parent", plan_ids)

        assert sorted(visible) == sorted(PARENT_FEATURES)

    def test_unknown_role_returns_empty(self):
        """An unrecognised role string must yield an empty list."""
        plan_ids = ["intake", "session_review"]

        visible = get_visible_features("ghost_role", plan_ids)

        assert visible == []

    def test_empty_plan_ids_returns_empty(self):
        """If the plan exposes no features, every role must see nothing."""
        for role in ("org_admin", "bcba", "teacher", "parent"):
            assert get_visible_features(role, []) == [], (
                f"Expected [] for role '{role}' with empty plan, got non-empty"
            )


# ===========================================================================
# 5. Feature Gate Service — check_feature_access / get_user_visible_feature_ids
# ===========================================================================


class TestCheckFeatureAccess:
    def test_org_admin_starter_can_access_intake(self):
        """org_admin on starter may access 'intake', which is in the plan."""
        user = _make_user("org_admin", "starter")

        # Must not raise
        check_feature_access(user, "intake")

    def test_org_admin_starter_blocked_from_fba(self):
        """org_admin on starter must be blocked from 'fba' (not in starter plan)."""
        user = _make_user("org_admin", "starter")

        with pytest.raises(HTTPException) as exc_info:
            check_feature_access(user, "fba")

        assert exc_info.value.status_code == 403

    def test_teacher_enterprise_can_access_session_review(self):
        """teacher on enterprise can access session_review (in role list)."""
        user = _make_user("teacher", "enterprise")

        check_feature_access(user, "session_review")

    def test_teacher_enterprise_blocked_from_intake(self):
        """teacher on enterprise is blocked from 'intake' (not in teacher role list)."""
        user = _make_user("teacher", "enterprise")

        with pytest.raises(HTTPException) as exc_info:
            check_feature_access(user, "intake")

        assert exc_info.value.status_code == 403

    def test_parent_starter_can_access_parent_letter(self):
        """parent on starter can access parent_letter."""
        user = _make_user("parent", "starter")

        check_feature_access(user, "parent_letter")

    def test_parent_starter_blocked_from_session_review(self):
        """parent on starter is blocked from session_review (not in parent role list)."""
        user = _make_user("parent", "starter")

        with pytest.raises(HTTPException) as exc_info:
            check_feature_access(user, "session_review")

        assert exc_info.value.status_code == 403

    def test_403_detail_contains_feature_id(self):
        """The 403 error detail message must mention the requested feature ID."""
        user = _make_user("parent", "starter")
        feature_id = "fba"

        with pytest.raises(HTTPException) as exc_info:
            check_feature_access(user, feature_id)

        assert feature_id in exc_info.value.detail, (
            f"Expected '{feature_id}' in error detail, got: {exc_info.value.detail!r}"
        )

    def test_unknown_feature_id_raises_403(self):
        """Requesting a completely unknown feature ID must also yield 403."""
        user = _make_user("org_admin", "enterprise")

        with pytest.raises(HTTPException) as exc_info:
            check_feature_access(user, "does_not_exist")

        assert exc_info.value.status_code == 403


class TestGetUserVisibleFeatureIds:
    def test_org_admin_starter_returns_5_features(self):
        """org_admin on starter plan must receive exactly 5 visible feature IDs."""
        user = _make_user("org_admin", "starter")

        ids = get_user_visible_feature_ids(user)

        assert len(ids) == len(STARTER_FEATURES), (
            f"Expected {len(STARTER_FEATURES)} features, got {len(ids)}: {ids}"
        )
        assert sorted(ids) == sorted(STARTER_FEATURES)

    def test_teacher_enterprise_returns_3_features(self):
        """teacher on enterprise must receive exactly 3 visible feature IDs."""
        user = _make_user("teacher", "enterprise")

        ids = get_user_visible_feature_ids(user)

        assert sorted(ids) == sorted(TEACHER_FEATURES)

    def test_parent_starter_returns_2_features(self):
        """parent on starter must receive exactly 2 visible feature IDs."""
        user = _make_user("parent", "starter")

        ids = get_user_visible_feature_ids(user)

        assert sorted(ids) == sorted(PARENT_FEATURES)

    def test_bcba_enterprise_returns_all_17_features(self):
        """bcba on enterprise has __all_in_plan__ so must see all 17 features."""
        user = _make_user("bcba", "enterprise")

        ids = get_user_visible_feature_ids(user)

        assert len(ids) == TOTAL_FEATURE_COUNT, (
            f"Expected {TOTAL_FEATURE_COUNT} features for bcba/enterprise, got {len(ids)}"
        )

    def test_returns_list_type(self):
        """get_user_visible_feature_ids must always return a list."""
        user = _make_user("org_admin", "starter")

        result = get_user_visible_feature_ids(user)

        assert isinstance(result, list)

    def test_unknown_plan_falls_back_to_starter(self):
        """If user.tenant.plan.name is not a known plan, falls back to 'starter'."""
        user = _make_user("org_admin", "nonexistent_plan")

        ids = get_user_visible_feature_ids(user)

        # Fallback to starter: org_admin sees all starter features
        assert sorted(ids) == sorted(STARTER_FEATURES)


# ===========================================================================
# 6. Public Feature Shape — get_public_features
# ===========================================================================


class TestPublicFeaturesShape:
    def test_public_features_shape(self):
        """
        Public dicts from get_public_features must include all required keys
        and must NOT leak any private server-only fields.
        """
        all_ids = get_all_feature_ids()
        public_list = get_public_features(all_ids)

        assert len(public_list) == TOTAL_FEATURE_COUNT, (
            f"Expected {TOTAL_FEATURE_COUNT} public dicts, got {len(public_list)}"
        )

        for feature_dict in public_list:
            feature_id = feature_dict.get("id", "<missing id>")

            # All required public keys must be present
            missing = PUBLIC_DICT_REQUIRED_KEYS - feature_dict.keys()
            assert not missing, (
                f"Feature '{feature_id}' missing public keys: {missing}"
            )

            # Private server-only keys must be absent
            leaked = PRIVATE_FIELDS & feature_dict.keys()
            assert not leaked, (
                f"Feature '{feature_id}' leaks private fields: {leaked}"
            )

    def test_public_feature_form_schema_is_dict_with_fields(self):
        """form_schema must be a dict containing a 'fields' list."""
        public_list = get_public_features(["intake"])

        assert len(public_list) == 1
        form_schema = public_list[0]["form_schema"]

        assert isinstance(form_schema, dict), (
            f"form_schema should be a dict, got {type(form_schema)}"
        )
        assert "fields" in form_schema, "form_schema must contain a 'fields' key"
        assert isinstance(form_schema["fields"], list)
        assert len(form_schema["fields"]) > 0, (
            "intake form_schema.fields must not be empty"
        )

    def test_public_features_empty_input(self):
        """get_public_features([]) must return an empty list without errors."""
        result = get_public_features([])

        assert result == []

    def test_public_features_skips_unknown_ids(self):
        """Unknown feature IDs in the input list are silently skipped."""
        result = get_public_features(["intake", "totally_fake_feature", "session_review"])

        returned_ids = [d["id"] for d in result]
        assert "intake" in returned_ids
        assert "session_review" in returned_ids
        assert "totally_fake_feature" not in returned_ids
        assert len(returned_ids) == 2

    def test_public_feature_dict_values_are_strings_where_expected(self):
        """Core string fields in a public dict must be non-empty strings."""
        feature = get_feature("session_review")
        assert feature is not None

        public = feature.to_public_dict()

        for key in ("id", "display_name", "description", "icon", "category", "output_template"):
            value = public[key]
            assert isinstance(value, str) and value, (
                f"session_review.{key} should be a non-empty string, got {value!r}"
            )
