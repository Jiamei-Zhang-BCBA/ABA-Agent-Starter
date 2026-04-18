# api/tests/test_vault_edit_marker.py
"""
BUG #19 regression tests:
- vault_service must parse `| EDIT:section` / `| MERGE` modifiers in FILE markers
- EDIT must replace a matching markdown section in-place, keeping the rest of the file
- `_replace_markdown_section` must match section names emoji-insensitively per
  skills/_config.md matching rules.
"""

from __future__ import annotations

import pytest

import app.services.vault_service as vault_module
from app.services.vault_service import (
    LocalVaultService,
    _normalize_section_key,
    _replace_markdown_section,
    write_output_to_vault,
)


# ---------------------------------------------------------------------------
# _normalize_section_key: emoji / whitespace / punctuation stripped
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("raw, expected", [
    ("🚨 历史问题行为备忘", "历史问题行为备忘"),
    (" 历史问题行为备忘 ", "历史问题行为备忘"),
    ("### 🚨 历史问题行为备忘", "历史问题行为备忘"),
    ("Core Profile 核心档案", "coreprofile核心档案"),
    ("🧩 核心能力画像", "核心能力画像"),
    ("", ""),
    ("   ", ""),
])
def test_normalize_section_key(raw, expected):
    assert _normalize_section_key(raw) == expected


# ---------------------------------------------------------------------------
# _replace_markdown_section: replaces matching section, keeps neighbors
# ---------------------------------------------------------------------------


def test_replace_section_with_emoji_heading_keeps_other_sections():
    doc = (
        "# [[Client-A-小航-核心档案]]\n\n"
        "## 👤 基本信息\n\n小航，女，5y2m\n\n"
        "## 🚨 历史问题行为备忘\n\n"
        "> ⏳ 待 fba-analyzer 填写\n\n"
        "## 🔗 全生命周期索引\n\n"
        "- [[Client-A-小航-IEP]]\n"
    )
    new_body = (
        "### 行为 1：啃手指 🔴 高优先级\n"
        "- 功能：自动强化 / 焦虑缓解\n"
        "- BIP：橡皮触觉环\n"
    )

    result = _replace_markdown_section(doc, "🚨 历史问题行为备忘", new_body)

    assert "## 👤 基本信息" in result
    assert "小航，女，5y2m" in result
    assert "## 🚨 历史问题行为备忘" in result
    # Old body must be replaced
    assert "⏳ 待 fba-analyzer 填写" not in result
    # New body must land under the heading
    assert "啃手指 🔴 高优先级" in result
    assert "橡皮触觉环" in result
    # Section order preserved
    assert result.index("基本信息") < result.index("历史问题行为备忘") < result.index("全生命周期索引")
    # Downstream section survives untouched
    assert "[[Client-A-小航-IEP]]" in result


def test_replace_section_strips_duplicate_heading_from_new_body():
    doc = "## 🚨 历史问题行为备忘\n\n旧内容\n\n## 下一节\n"
    new_body = "## 🚨 历史问题行为备忘（基于 2026-04-22 FBA 更新）\n\n新内容\n"

    result = _replace_markdown_section(doc, "🚨 历史问题行为备忘", new_body)

    # Only one heading that normalizes to the target
    headings = [line for line in result.splitlines() if line.startswith("##") and "历史问题行为备忘" in line]
    assert len(headings) == 1
    assert "新内容" in result
    assert "旧内容" not in result
    assert "## 下一节" in result


def test_replace_section_missing_appends_instead_of_dropping():
    doc = "# Title\n\n## A\ntext-a\n"
    new_body = "brand new content"

    result = _replace_markdown_section(doc, "🔬 新章节", new_body)

    # Original content preserved
    assert "## A" in result
    assert "text-a" in result
    # New section appended at end
    assert "## 🔬 新章节" in result
    assert "brand new content" in result


def test_replace_section_matches_across_heading_levels():
    """Heading level is irrelevant as long as normalized text matches."""
    doc = "# Top\n\n### 🎯 当前目标\n\n旧目标\n\n## 其他\n"
    new_body = "目标 1 / 目标 2 / 目标 3"

    result = _replace_markdown_section(doc, "当前目标", new_body)

    assert "旧目标" not in result
    assert "目标 1 / 目标 2 / 目标 3" in result


# ---------------------------------------------------------------------------
# write_output_to_vault: full-stack BUG #19 regression
# ---------------------------------------------------------------------------


@pytest.fixture()
def vault(tmp_path, monkeypatch):
    monkeypatch.setattr(vault_module.settings, "local_storage_path", str(tmp_path))
    return LocalVaultService("test-tenant-edit")


def _seed_core_file(vault, code):
    """Create a typical core profile skeleton for the given client code."""
    path = f"01-Clients/Client-{code}/Client-{code}-核心档案.md"
    content = (
        f"# [[Client-{code}-核心档案]]\n\n"
        "## 👤 基本信息\n\n占位基本信息\n\n"
        "## 🚨 历史问题行为备忘\n\n"
        "> ⏳ 等待 fba-analyzer 执行\n\n"
        "## 🔗 全生命周期索引\n\n- [[somewhere]]\n"
    )
    vault.write_file(path, content)
    return path


def test_bug19_edit_marker_replaces_section_in_core_file(vault):
    code = "A-test1"
    path = _seed_core_file(vault, code)

    ai_output = (
        "Intro text before any marker.\n"
        f"<!-- FILE: {path} | EDIT:🚨 历史问题行为备忘 -->\n"
        "### 行为 1：啃手指\n"
        "- 功能：自动强化\n"
        "- BIP：橡皮触觉环\n"
    )

    write_output_to_vault(vault, "fba-analyzer", code, ai_output)

    # Garbage path MUST NOT be created (regression guard)
    bad_path = f"{path} | EDIT:🚨 历史问题行为备忘"
    assert vault.read_file(bad_path) is None, (
        "BUG #19 regression: EDIT marker was written as a literal path file"
    )

    # Real core file must reflect the edit
    updated = vault.read_file(path)
    assert updated is not None
    assert "## 🚨 历史问题行为备忘" in updated
    assert "啃手指" in updated
    assert "橡皮触觉环" in updated
    assert "⏳ 等待 fba-analyzer 执行" not in updated
    # Sibling sections untouched
    assert "## 👤 基本信息" in updated
    assert "## 🔗 全生命周期索引" in updated


def test_bug19_mixed_markers_write_append_edit(vault):
    """A single AI output with WRITE + APPEND + EDIT markers routes each correctly."""
    code = "A-test2"
    core_path = _seed_core_file(vault, code)
    log_path = "04-Supervision/系统变更日志.md"
    vault.write_file(log_path, "# 系统变更日志\n\n[2026-01-01] init\n")

    new_file_path = f"01-Clients/Client-{code}/Client-{code}-FBA分析.md"

    ai_output = (
        f"<!-- FILE: {new_file_path} -->\n"
        "# FBA 分析\n\n完整 FBA 内容\n"
        f"<!-- FILE: {core_path} | EDIT:🚨 历史问题行为备忘 -->\n"
        "### 新的问题行为备忘\n"
        f"<!-- FILE: {log_path} | APPEND -->\n"
        "[2026-04-22] fba-analyzer 执行\n"
    )

    write_output_to_vault(vault, "fba-analyzer", code, ai_output)

    # WRITE marker creates new file with full content
    fba = vault.read_file(new_file_path)
    assert fba is not None
    assert "完整 FBA 内容" in fba

    # EDIT marker replaces just the section
    core = vault.read_file(core_path)
    assert "新的问题行为备忘" in core
    assert "⏳ 等待 fba-analyzer 执行" not in core
    assert "## 👤 基本信息" in core  # other section survives

    # APPEND preserves existing log entries
    log = vault.read_file(log_path)
    assert "[2026-01-01] init" in log
    assert "[2026-04-22] fba-analyzer 执行" in log

    # No garbage files anywhere
    garbage = f"{core_path} | EDIT:🚨 历史问题行为备忘"
    assert vault.read_file(garbage) is None


def test_bug19_merge_modifier_degrades_to_append(vault):
    """MERGE currently degrades to APPEND so no data is lost."""
    code = "A-test3"
    path = f"01-Clients/Client-{code}/Client-{code}-核心档案.md"
    vault.write_file(path, "# Core\n\noriginal body\n")

    ai_output = (
        f"<!-- FILE: {path} | MERGE -->\n"
        "new addition\n"
    )

    write_output_to_vault(vault, "profile-builder", code, ai_output)

    result = vault.read_file(path)
    assert "original body" in result
    assert "new addition" in result


def test_bug19_edit_when_target_file_missing_writes_new_file(vault):
    """If EDIT target doesn't exist yet, we should still save the content (not lose it)."""
    code = "A-test4"
    path = f"01-Clients/Client-{code}/Client-{code}-核心档案.md"
    # Deliberately do NOT seed the file

    ai_output = (
        f"<!-- FILE: {path} | EDIT:🎯 当前目标 -->\n"
        "目标内容\n"
    )

    write_output_to_vault(vault, "plan-generator", code, ai_output)

    result = vault.read_file(path)
    assert result is not None
    assert "目标内容" in result


# ---------------------------------------------------------------------------
# BUG #21 — SECTION_REPLACE / REPLACE_SECTION / APPEND_SECTION synonyms
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "modifier",
    [
        "SECTION_REPLACE:🚨 历史问题行为备忘",
        "REPLACE_SECTION:🚨 历史问题行为备忘",
    ],
)
def test_bug21_section_replace_synonyms_canonicalize_to_edit(vault, modifier):
    """
    BUG #21: AI skill prompts sometimes emit SECTION_REPLACE or REPLACE_SECTION
    as synonyms for EDIT. The regex previously only recognized EDIT/APPEND/MERGE,
    so the modifier leaked into the path group — producing a garbage file path
    and silently dropping the intended section replacement.

    Both synonyms must now behave identically to `EDIT:<section>`.
    """
    code = "A-test-bug21-replace"
    path = _seed_core_file(vault, code)

    ai_output = (
        f"<!-- FILE: {path} | {modifier} -->\n"
        "### 行为 1：扑咬 🔴 高优先级\n"
        "- 功能：逃避 + 社会正强化\n"
        "- BIP：两级协议\n"
    )

    write_output_to_vault(vault, "fba-analyzer", code, ai_output)

    # Section must actually be replaced (old placeholder gone, new content in place)
    updated = vault.read_file(path)
    assert updated is not None, "core file must still exist after SECTION_REPLACE"
    assert "## 🚨 历史问题行为备忘" in updated
    assert "扑咬 🔴 高优先级" in updated
    assert "两级协议" in updated
    assert "⏳ 等待 fba-analyzer 执行" not in updated
    # Sibling sections intact
    assert "## 👤 基本信息" in updated
    assert "## 🔗 全生命周期索引" in updated

    # Regression guard: the modifier must NOT have leaked into a garbage path
    garbage_path = f"{path} | {modifier}"
    assert vault.read_file(garbage_path) is None, (
        f"BUG #21 regression: '{modifier}' was written as a literal path file"
    )


def test_bug21_append_section_degrades_to_append(vault):
    """
    `APPEND_SECTION:<name>` is a prompt-level synonym for plain APPEND (targeted
    section-append isn't implemented yet). It must at minimum preserve existing
    content and add the new body instead of leaking into the path group.
    """
    code = "A-test-bug21-append"
    path = "04-Supervision/系统变更日志.md"
    vault.write_file(path, "# 系统变更日志\n\n[2026-01-01] init\n")

    ai_output = (
        f"<!-- FILE: {path} | APPEND_SECTION:## 2026-04 -->\n"
        "[2026-04-22] fba-analyzer 执行\n"
    )

    write_output_to_vault(vault, "fba-analyzer", code, ai_output)

    result = vault.read_file(path)
    assert "[2026-01-01] init" in result
    assert "[2026-04-22] fba-analyzer 执行" in result

    # No garbage file with the modifier in the path
    garbage = f"{path} | APPEND_SECTION:## 2026-04"
    assert vault.read_file(garbage) is None
