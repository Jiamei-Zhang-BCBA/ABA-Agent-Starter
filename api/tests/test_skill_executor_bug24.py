"""BUG #24 回归测试：skill_executor._cloud_mode_supplement 必须含真名零出现禁令。

背景：v4 测试 (2026-04-18) 发现 AI assessment-logger 在 meta-commentary 里写
"原始资料中出现的父母姓名（李建国/陈婉仪）：已通过 privacy-filter 处理"，
把真名搬进了正式档案。此测试锁定修复生效——所有云端 job 的 system prompt
supplement 必须包含"真名零出现"硬规则。
"""
from __future__ import annotations

from unittest.mock import MagicMock

from app.services.skill_executor import SkillExecutor


def _make_executor() -> SkillExecutor:
    """Minimal executor with a mocked vault; only _cloud_mode_supplement is tested."""
    vault = MagicMock()
    return SkillExecutor(vault=vault)


def test_cloud_mode_supplement_contains_bug24_hard_rule() -> None:
    """Core anchor — BUG #24 rule must be embedded in every cloud job prompt."""
    text = _make_executor()._cloud_mode_supplement()

    # Key anchors from the BUG #24 rule block
    assert "BUG #24" in text, "supplement must cite BUG #24 for traceability"
    assert "真名" in text
    assert "meta-commentary" in text.lower() or "meta" in text.lower()
    assert "自毁式脱敏" in text

    # Must also name at least one banned location
    assert "frontmatter" in text
    # The "解释性引用仍是泄漏" pattern must be taught explicitly
    assert "引用" in text and ("禁" in text or "不得" in text or "❌" in text)


def test_cloud_mode_supplement_lists_explicit_violation_example() -> None:
    """The supplement must teach the AI with a concrete wrong/right pair.

    Hard lesson from v4: Claude was "trying to explain compliance" and ended
    up leaking names. The fixed prompt needs an explicit ❌/✅ contrast so
    the model recognises the pattern.
    """
    text = _make_executor()._cloud_mode_supplement()

    assert "❌" in text
    assert "✅" in text
    # Correct form must reference role-based aliases
    assert "角色代称" in text


def test_cloud_mode_supplement_preserves_obs02_date_rule() -> None:
    """Regression guard: adding BUG #24 must not remove earlier OBS-02 content."""
    text = _make_executor()._cloud_mode_supplement()

    # OBS-02 anchors
    assert "OBS-02" in text or "时间悖论" in text
    assert "数据窗口截止" in text


def test_cloud_mode_supplement_preserves_data_priority_rule() -> None:
    """Regression guard: data-priority block must still exist after BUG #24 edit."""
    text = _make_executor()._cloud_mode_supplement()

    # Data priority block anchors
    assert "数据优先级" in text
    assert "档案代号" in text
