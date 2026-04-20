"""Unit tests for privacy_guard (BUG #25 post-hoc防护)."""
from __future__ import annotations

import pytest

from app.services.privacy_guard import (
    _parse_mapping_table,
    _is_allowed_path,
    scan_payload,
    sanitize_payload,
    scan_and_scrub,
    load_known_names,
    invalidate_cache,
    PrivacyGuardError,
)


# -- parsing -----------------------------------------------------------------

class TestParseMappingTable:
    def test_extracts_first_column_of_rows(self):
        raw = """
# 身份映射对照表

| 真实姓名 | 系统代号 | 录入日期 | 备注 |
|:---|:---|:---|:---|
| 王小满 | Client-A-小满 | 2026-04-19 | 儿童 |
| 刘雅琴 | Client-A-小满 母亲 | 2026-04-19 | 母亲 |
| 王建伟 | Client-A-小满 父亲 | 2026-04-19 | 父亲 |
"""
        names = _parse_mapping_table(raw)
        assert names == ["王小满", "刘雅琴", "王建伟"]

    def test_skips_header_row(self):
        raw = "| 真实姓名 | 系统代号 |\n| 王小满 | Client-A-小满 |"
        names = _parse_mapping_table(raw)
        assert "真实姓名" not in names
        assert "王小满" in names

    def test_skips_separator_row(self):
        raw = "|:---|:---|\n| 王小满 | Client-A |"
        names = _parse_mapping_table(raw)
        assert ":---" not in names
        assert names == ["王小满"]

    def test_dedup_preserves_order(self):
        raw = (
            "| 王小满 | C1 |\n"
            "| 刘雅琴 | C2 |\n"
            "| 王小满 | C1-alias |\n"
        )
        names = _parse_mapping_table(raw)
        assert names == ["王小满", "刘雅琴"]

    def test_ignores_non_table_lines(self):
        raw = "> Not a table\n文本 blah | fake | 王小满 | end"
        names = _parse_mapping_table(raw)
        assert names == []

    def test_empty_input(self):
        assert _parse_mapping_table("") == []

    def test_brand_entries_extracted(self):
        raw = """
| 真实品牌名 | 系统代号 | 录入日期 |
|:---|:---|:---|
| 雪香原味棉花糖 | 某品牌棉花糖 | 2026-04-19 |
"""
        names = _parse_mapping_table(raw)
        assert "雪香原味棉花糖" in names


class TestBug28KinshipBlacklist:
    """BUG #28 regression tests — historical mapping col0 pollution.

    v5 A-小满 (and earlier) privacy-filter AI sometimes put kinship terms
    ("母亲"/"父亲"/"爷爷" 等) directly into col0 of the identity mapping table
    before the post-hoc guard was deployed. After guard deployment (commit
    7031c2d), the legacy pollution caused massive false positives (45 hits in
    v6 S1). The _GENERIC_TERM_BLACKLIST fix ensures these generic terms are
    dropped during parsing.
    """

    def test_kinship_terms_skipped(self):
        raw = (
            "| 真实身份 | 系统代号 |\n"
            "|:---|:---|\n"
            "| 王小满 | Client-A-小满 |\n"
            "| 母亲 | Client-A-小满 母亲 |\n"
            "| 父亲 | Client-A-小满 父亲 |\n"
            "| 爷爷 | Client-A-小满 爷爷 |\n"
        )
        names = _parse_mapping_table(raw)
        assert "王小满" in names
        assert "母亲" not in names
        assert "父亲" not in names
        assert "爷爷" not in names

    def test_role_words_skipped(self):
        raw = (
            "| 医生 | 某医生 |\n"
            "| 老师 | 某老师 |\n"
            "| 督导 | 某督导 |\n"
            "| 教练 | 某教练 |\n"
        )
        names = _parse_mapping_table(raw)
        assert names == []

    def test_姓氏敬称_variants_still_pass(self):
        """Specific 姓+title variants (e.g. 王姐/张工) are NOT in blacklist —
        they are legitimately real identifiers and must still be treated as names.
        """
        raw = (
            "| 王姐 | 某同事 |\n"
            "| 张工 | 某工程师 |\n"
            "| 李老师 | 班主任 |\n"   # 李老师 has surname prefix, not generic
        )
        names = _parse_mapping_table(raw)
        assert "王姐" in names
        assert "张工" in names
        assert "李老师" in names

    def test_legacy_mapping_does_not_trigger_false_positive_scan(self):
        """End-to-end: legacy col0 with kinship terms → scan on deidentified
        body with kinship terms → expected 0 hits (not 45 like pre-fix).
        """
        legacy_mapping = (
            "| 真实身份 | 系统代号 |\n"
            "|:---|:---|\n"
            "| 王小满 | Client-A-小满 |\n"
            "| 母亲 | Client-A-小满 母亲 |\n"
            "| 父亲 | Client-A-小满 父亲 |\n"
            "| 爷爷 | Client-A-小满 爷爷 |\n"
        )
        from app.services.privacy_guard import scan_payload
        known = _parse_mapping_table(legacy_mapping)
        # Typical deidentified body that uses kinship代称 as normal Chinese
        body = "母亲送禾禾去幼儿园时，爷爷在楼下接他。父亲下班后陪孩子玩积木。"
        hits = scan_payload(body, known)
        # Only 王小满 is a real name; it doesn't appear in body → 0 hits total.
        assert hits == []


# -- path allowlist ----------------------------------------------------------

class TestAllowedPath:
    def test_mapping_table_is_allowed(self):
        assert _is_allowed_path("00-RawData/身份映射对照表-绝密.md")
        assert _is_allowed_path("00-RawData/身份映射对照表.md")

    def test_subpaths_of_mapping_prefix_allowed(self):
        # 任何以身份映射开头的路径都算合法出处（未来扩展）
        assert _is_allowed_path("00-RawData/身份映射-品牌.md")

    def test_regular_vault_path_not_allowed(self):
        assert not _is_allowed_path("01-Clients/Client-A-小满/核心档案.md")
        assert not _is_allowed_path("04-Supervision/系统变更日志.md")
        assert not _is_allowed_path("05-Communication/家书-2026-04-19.md")

    def test_root_path_not_allowed(self):
        assert not _is_allowed_path("")
        assert not _is_allowed_path("/")

    def test_leading_slash_normalized(self):
        assert _is_allowed_path("/00-RawData/身份映射对照表-绝密.md")

    def test_backslash_path_normalized(self):
        # Windows-style paths should still match after normalization
        assert _is_allowed_path("00-RawData\\身份映射对照表-绝密.md")


# -- scan --------------------------------------------------------------------

class TestScanPayload:
    def test_no_names_clean(self):
        hits = scan_payload("这是脱敏后的正文", ["王小满"])
        assert hits == []

    def test_detects_single_name(self):
        hits = scan_payload("今天王小满来上课了", ["王小满"])
        assert hits == [("王小满", 1)]

    def test_counts_multiple_occurrences(self):
        hits = scan_payload("王小满走了王小满又回来", ["王小满"])
        assert hits == [("王小满", 2)]

    def test_sorts_by_count_desc(self):
        payload = "王小满 王小满 王小满 刘雅琴 王建伟"
        hits = scan_payload(payload, ["王小满", "刘雅琴", "王建伟"])
        # 王小满 3, 刘雅琴 1, 王建伟 1
        assert hits[0] == ("王小满", 3)
        assert {("刘雅琴", 1), ("王建伟", 1)} == set(hits[1:])

    def test_skips_single_char_names(self):
        # 单字姓名可能过宽匹配（"王"会命中很多普通词），跳过以降噪
        hits = scan_payload("王小满来了", ["王"])
        assert hits == []

    def test_skips_empty_names(self):
        hits = scan_payload("王小满", ["", "王小满"])
        assert hits == [("王小满", 1)]

    def test_detects_brand_names(self):
        hits = scan_payload("棉花糖买雪香牌子", ["雪香"])
        assert hits == [("雪香", 1)]


# -- sanitize ----------------------------------------------------------------

class TestSanitizePayload:
    def test_replaces_single_name(self):
        out = sanitize_payload("王小满来了", [("王小满", 1)])
        assert "王小满" not in out
        assert "[REDACTED]" in out

    def test_replaces_longer_first(self):
        # 防止 "小满" 先于 "王小满" 被替换造成部分残留
        out = sanitize_payload(
            "王小满是小满",
            [("王小满", 1), ("小满", 2)],
        )
        assert "王小满" not in out
        assert "小满" not in out
        # 两个名字都应变成 REDACTED
        assert out.count("[REDACTED]") == 2

    def test_handles_no_hits(self):
        out = sanitize_payload("清白正文", [])
        assert out == "清白正文"


# -- scan_and_scrub (end-to-end) ---------------------------------------------

class _FakeVault:
    """Minimal vault double for testing privacy_guard."""
    def __init__(self, mapping_content: str = "", tenant_id: str = "tenant-x"):
        self._mapping = mapping_content
        self.tenant_id = tenant_id

    def read_file(self, path: str) -> str | None:
        if "身份映射" in path:
            return self._mapping
        return None


@pytest.fixture(autouse=True)
def _clear_cache():
    invalidate_cache()
    yield
    invalidate_cache()


class TestScanAndScrub:
    def test_allowed_path_passes_unchanged(self):
        v = _FakeVault(mapping_content="| 王小满 | C-A |")
        result = scan_and_scrub(
            v, "00-RawData/身份映射对照表-绝密.md", "王小满 王小满", policy="strict",
        )
        assert result.clean is True
        assert result.rejected is False
        assert result.payload == "王小满 王小满"

    def test_clean_payload(self):
        v = _FakeVault(mapping_content="| 王小满 | C-A |")
        result = scan_and_scrub(
            v, "01-Clients/Client-A/核心档案.md", "脱敏后的正文", policy="warn",
        )
        assert result.clean is True
        assert result.hits == []

    def test_warn_keeps_payload_unchanged(self):
        v = _FakeVault(mapping_content="| 王小满 | C-A |")
        result = scan_and_scrub(
            v, "01-Clients/Client-A/家书.md", "王小满很棒", policy="warn",
        )
        assert result.clean is False
        assert result.hits == [("王小满", 1)]
        assert result.rejected is False
        assert result.payload == "王小满很棒"  # 未改

    def test_sanitize_scrubs_payload(self):
        v = _FakeVault(mapping_content="| 王小满 | C-A |")
        result = scan_and_scrub(
            v, "01-Clients/Client-A/家书.md", "王小满很棒", policy="sanitize",
        )
        assert result.clean is False
        assert "王小满" not in result.payload
        assert "[REDACTED]" in result.payload
        assert result.rejected is False

    def test_strict_flags_rejected(self):
        v = _FakeVault(mapping_content="| 王小满 | C-A |")
        result = scan_and_scrub(
            v, "01-Clients/Client-A/家书.md", "王小满很棒", policy="strict",
        )
        assert result.clean is False
        assert result.rejected is True
        # strict 不改内容，只是让调用方拒绝
        assert result.payload == "王小满很棒"

    def test_empty_mapping_passes_everything(self):
        v = _FakeVault(mapping_content="")
        result = scan_and_scrub(
            v, "01-Clients/Client-A/家书.md", "任意文本 王小满", policy="strict",
        )
        assert result.clean is True
        assert result.rejected is False

    def test_vault_read_failure_is_safe(self):
        class _BrokenVault:
            tenant_id = "t"
            def read_file(self, p):
                raise RuntimeError("storage backend down")

        # Guard 失败不应阻止合法写入
        result = scan_and_scrub(
            _BrokenVault(), "01-Clients/x.md", "王小满", policy="strict",
        )
        assert result.clean is True
        assert result.rejected is False

    def test_cache_reuses_parse(self):
        v = _FakeVault(mapping_content="| 王小满 | C-A |")
        # 第一次
        names1 = load_known_names(v)
        # 第二次 (同一 tenant + 同长度) 应命中 cache
        names2 = load_known_names(v)
        assert names1 == names2 == ["王小满"]

    def test_cache_invalidates_on_mapping_change(self):
        v = _FakeVault(mapping_content="| 王小满 | C-A |")
        names1 = load_known_names(v)
        assert names1 == ["王小满"]
        # 模拟新增映射条目 — raw 长度变，cache key 变
        v._mapping = "| 王小满 | C-A |\n| 刘雅琴 | C-B |"
        names2 = load_known_names(v)
        assert set(names2) == {"王小满", "刘雅琴"}


# -- realistic regression from v5 test dumps ---------------------------------

class TestV5Regression:
    """Real phrases captured from v5 S1 retry (job ade3b1d5 / b8658c2f)."""

    _MAPPING = (
        "| 真实姓名 | 系统代号 | 录入日期 | 备注 |\n"
        "|:---|:---|:---|:---|\n"
        "| 王小满 | Client-A-小满 | 2026-04-19 | 儿童 |\n"
        "| 刘雅琴 | Client-A-小满 母亲 | 2026-04-19 | 母亲 |\n"
        "| 王建伟 | Client-A-小满 父亲 | 2026-04-19 | 父亲 |\n"
        "| 李老师 | 早教中心老师 | 2026-04-19 | 教师 |\n"
        "| 周教授 | 儿童医院产科医生 | 2026-04-19 | 医生 |\n"
        "| 雪香 | 某品牌 | 2026-04-19 | 强化物品牌 |\n"
    )

    def test_v5_preamble_leak_caught(self):
        """v5 meta preamble actually wrote this — 7 真名泄漏."""
        v = _FakeVault(mapping_content=self._MAPPING)
        preamble = (
            "儿童真名：王小满 → Client-A-小满\n"
            "母亲：刘雅琴 → Client-A-小满 母亲\n"
            "父亲：王建伟 → Client-A-小满 父亲\n"
            "BUG #23 特处：李老师（4 处）→ 早教中心老师；周教授（2 处）→ 某医生\n"
            "品牌脱敏：雪香棉花糖（3 处）→ 某品牌棉花糖\n"
        )
        # 如果这段要写到 04-Supervision（不是映射表），应被识别
        result = scan_and_scrub(
            v, "04-Supervision/系统变更日志.md", preamble, policy="strict",
        )
        assert result.clean is False
        assert result.rejected is True
        # 5 个人名 + 1 个品牌 都应被抓到
        names_hit = {name for name, _ in result.hits}
        assert {"王小满", "刘雅琴", "王建伟", "李老师", "周教授", "雪香"} <= names_hit

    def test_v5_changelog_scrub(self):
        """BUG #25 变更日志里 李老师 被当成"已替换证明"残留 — sanitize 能救回."""
        v = _FakeVault(mapping_content=self._MAPPING)
        payload = "脱敏覆盖：李老师 4 处 → 早教中心老师（4 处命中）"
        result = scan_and_scrub(
            v, "04-Supervision/系统变更日志.md", payload, policy="sanitize",
        )
        assert "李老师" not in result.payload
        assert "[REDACTED]" in result.payload

    def test_v5_clean_changelog_passes(self):
        """符合新 SKILL.md 模板的变更日志应无命中."""
        v = _FakeVault(mapping_content=self._MAPPING)
        payload = (
            "脱敏覆盖：儿童真名 1 + 家庭成员真名 2 + 医学职业敬称变体全量处理（4 处命中）"
            "+ 品牌脱敏 1 | 映射表新增 1 条"
        )
        result = scan_and_scrub(
            v, "04-Supervision/系统变更日志.md", payload, policy="strict",
        )
        assert result.clean is True
        assert result.rejected is False
