"""Post-hoc privacy guard for vault writes.

This module is the last line of defense against real-name leakage. It sits
between the LLM's output and the vault's write_file. When the LLM (despite
prompt rules) produces content that contains real names from the tenant's
identity mapping table, this module either strips / flags / rejects the write.

Background (v5 测试):
- BUG #22/#23: real names in payload content — fixed mostly at prompt level
- BUG #24/#25: AI meta-commentary / self-certification phrases reintroduce real
  names ("已替换：王小满 → Client-A-小满" 等) into downstream files despite
  explicit SKILL.md rules. Prompt-level fixes get us 90% of the way; this
  module closes the remaining gap deterministically.

Design choices:
- Guard is OPT-IN per skill via the tenant's identity mapping file.
- Mapping file is parsed lazily + cached per (tenant_id, mtime) to keep cost low.
- "Real name" is defined as the verbatim contents of the "真实姓名" / "真实品牌名"
  column of 身份映射对照表-绝密.md. Nothing else.
- When a real name is detected inside a vault payload, the configured policy
  decides: strict (raise), sanitize (replace with category tag), or warn.
- The guard NEVER reads content back after writing — it only inspects what is
  about to be written.

Public API:
    scan_and_scrub(vault, path, payload, *, policy="warn") -> ScrubResult
"""

from __future__ import annotations

import logging
import re
from dataclasses import dataclass, field
from typing import Iterable, Literal

logger = logging.getLogger(__name__)


MAPPING_FILE_PATH = "00-RawData/身份映射对照表-绝密.md"


Policy = Literal["strict", "sanitize", "warn"]


@dataclass
class ScrubResult:
    """Outcome of a privacy scan on a single vault write.

    Attributes:
        clean: True iff the payload contained zero known real names.
        hits: list of (real_name, count) tuples.
        payload: the (possibly sanitized) payload to actually write.
        rejected: True iff policy=strict and hits≠[] — caller MUST abort write.
    """
    clean: bool
    hits: list[tuple[str, int]] = field(default_factory=list)
    payload: str = ""
    rejected: bool = False


# Paths under which real names are legally allowed to appear.
# These are the identity mapping table itself, and the 00-RawData scratch space
# that is never shown to downstream skills or dashboards.
_ALLOWED_PATH_PREFIXES: tuple[str, ...] = (
    "00-RawData/身份映射对照表",
    "00-RawData/身份映射",
)


def _is_allowed_path(path: str) -> bool:
    """True iff `path` is a legal home for real names (mapping table)."""
    p = path.replace("\\", "/").lstrip("/")
    return any(p.startswith(prefix) for prefix in _ALLOWED_PATH_PREFIXES)


# Category tag used when sanitizing. Generic enough not to leak structure.
_SANITIZE_REPLACEMENT = "[REDACTED]"


# BUG #28 (v6 A-小禾 2026-04-20):
# Historical mapping tables (v1-v5 era) accidentally put kinship terms / generic
# role words into col0 (真实身份). Once guard was deployed (v5 末尾 commit
# 7031c2d) it started reading those col0 entries as "known names" and matching
# them against deidentified archive bodies, which naturally contain many kinship
# terms like 爷爷/母亲/父亲 — resulting in massive false positives (45 hits in
# one v6 S1 run, all kinship terms).
#
# This blacklist ensures that even if col0 contains these generic words (from
# legacy pollution or future AI mis-classification), the guard will not treat
# them as real names. Real people using 姓+title variants (e.g. 王姐 / 张工)
# bypass this blacklist because their col0 is the姓+specific variant, not the
# bare generic word.
_GENERIC_TERM_BLACKLIST: frozenset[str] = frozenset({
    # 家庭称谓
    "父亲", "母亲", "爸爸", "妈妈",
    "爷爷", "奶奶", "外公", "外婆", "姥姥", "姥爷",
    "叔叔", "舅舅", "阿姨", "姑姑",
    "哥哥", "姐姐", "弟弟", "妹妹",
    "兄长", "表哥", "表姐", "堂哥", "堂姐",
    # 通用角色
    "儿童", "孩子", "本人", "家长", "监护人", "双方",
    "医生", "主任", "主治", "专家",
    "老师", "班主任", "配班", "主班",
    "督导", "教练", "顾问",
    # AI 历史误填的代称通词
    "某同事", "某朋友", "某邻居", "某同学",
})


def _parse_mapping_table(raw: str) -> list[str]:
    """Extract the first column (真实姓名 / 真实品牌名) from a Markdown table.

    The mapping file contains multiple tables of the form:

        | 真实姓名 | 系统代号 | 录入日期 | 备注 |
        |:---|:---|:---|:---|
        | 王小满 | Client-A-小满 | 2026-04-19 | ... |
        | 刘雅琴 | Client-A-小满 母亲 | 2026-04-19 | ... |

    Each non-header row's first cell is collected. Empty / header / separator
    rows are skipped. Results are deduplicated while preserving order.

    Generic terms (kinship / role words) listed in _GENERIC_TERM_BLACKLIST are
    also skipped to prevent historical mapping pollution from producing false
    positives (see BUG #28).
    """
    names: list[str] = []
    seen: set[str] = set()
    for line in raw.splitlines():
        stripped = line.strip()
        if not stripped.startswith("|") or not stripped.endswith("|"):
            continue
        # Split by | and ignore leading/trailing empties
        cells = [c.strip() for c in stripped.strip("|").split("|")]
        if not cells:
            continue
        first = cells[0]
        # Skip header-like rows.
        # Heuristic: header cells contain "真实" / "系统代号" keywords, or
        # are separator rows like ":---" / "---".
        if not first:
            continue
        if first.startswith(":") or first.startswith("-"):
            continue
        if "真实" in first or "系统" in first or "aliases" in first.lower():
            continue
        # BUG #28: drop generic kinship/role terms that cannot be real names.
        if first in _GENERIC_TERM_BLACKLIST:
            continue
        if first in seen:
            continue
        seen.add(first)
        names.append(first)
    return names


# In-process cache keyed by (tenant_id, mtime-or-None). The vault may be either
# LocalVaultService (filesystem) or VaultService (S3). We don't have a direct
# mtime for S3 objects, so we use the raw content length as a weak cache key.
_mapping_cache: dict[tuple[str, int], list[str]] = {}


def load_known_names(vault) -> list[str]:
    """Load the tenant's real-name list from the identity mapping file.

    Returns an empty list if the file doesn't exist (new tenant, no clients).
    Results are cached in-process for the life of the API worker.
    """
    tenant_id = getattr(vault, "tenant_id", None) or getattr(
        vault, "_tenant_id", None
    ) or "unknown"
    raw = vault.read_file(MAPPING_FILE_PATH) or ""
    cache_key = (str(tenant_id), len(raw))
    if cache_key in _mapping_cache:
        return _mapping_cache[cache_key]
    names = _parse_mapping_table(raw)
    _mapping_cache[cache_key] = names
    return names


def scan_payload(payload: str, known_names: Iterable[str]) -> list[tuple[str, int]]:
    """Count literal occurrences of each known name in payload.

    Returns list of (name, count) for names with count > 0, sorted by count desc.
    Pure function — no side effects. Case-sensitive exact substring match (names
    in the mapping table are already in their canonical form).
    """
    hits: list[tuple[str, int]] = []
    for name in known_names:
        if not name or len(name) < 2:
            # Ignore degenerate entries (e.g. single-char names) to avoid mass
            # false positives. If a tenant really has a single-char real name
            # they should use the 2-char姓氏敬称 variant (e.g. "王姐").
            continue
        count = payload.count(name)
        if count > 0:
            hits.append((name, count))
    hits.sort(key=lambda t: t[1], reverse=True)
    return hits


def sanitize_payload(payload: str, hits: Iterable[tuple[str, int]]) -> str:
    """Replace each known-name occurrence with the sanitize replacement tag.

    Longer names replaced first to avoid partial-overlap issues (e.g. if both
    "王小满" and "小满" are in the mapping — the longer one takes precedence).
    """
    # Sort by name length desc so longer patterns consume first.
    ordered = sorted({name for name, _ in hits}, key=len, reverse=True)
    out = payload
    for name in ordered:
        out = out.replace(name, _SANITIZE_REPLACEMENT)
    return out


class PrivacyGuardError(Exception):
    """Raised when policy=strict and real names were found in a payload."""


def scan_and_scrub(
    vault,
    path: str,
    payload: str,
    *,
    policy: Policy = "warn",
) -> ScrubResult:
    """Run the post-hoc privacy guard on a single vault payload.

    Args:
        vault: VaultService or LocalVaultService — used to read the mapping file.
        path: target vault path the payload is about to be written to.
        payload: the content about to be written.
        policy: what to do on a hit.
            - "strict": set rejected=True; caller MUST abort write.
            - "sanitize": replace hits with REDACTED tag and proceed.
            - "warn" (default): log warning, proceed unchanged.

    Returns:
        ScrubResult with hits / payload / rejected fields set per policy.
    """
    if _is_allowed_path(path):
        # Mapping table itself is the one place real names legally live.
        return ScrubResult(clean=True, payload=payload)

    try:
        known = load_known_names(vault)
    except Exception as exc:
        logger.warning("privacy_guard: failed to load mapping table: %s", exc)
        return ScrubResult(clean=True, payload=payload)

    if not known:
        return ScrubResult(clean=True, payload=payload)

    hits = scan_payload(payload, known)
    if not hits:
        return ScrubResult(clean=True, payload=payload)

    if policy == "strict":
        logger.error(
            "privacy_guard STRICT: %d real-name hit(s) in payload for '%s': %s",
            sum(c for _, c in hits), path, hits[:5],
        )
        return ScrubResult(
            clean=False, hits=hits, payload=payload, rejected=True,
        )

    if policy == "sanitize":
        new_payload = sanitize_payload(payload, hits)
        logger.warning(
            "privacy_guard SANITIZE: scrubbed %d hit(s) in '%s': %s",
            sum(c for _, c in hits), path, hits[:5],
        )
        return ScrubResult(
            clean=False, hits=hits, payload=new_payload, rejected=False,
        )

    # Default: warn only. This is the safest rollout mode — it logs without
    # changing behavior, so we can observe baseline before enabling sanitize.
    logger.warning(
        "privacy_guard WARN: %d real-name hit(s) in payload for '%s': %s",
        sum(c for _, c in hits), path, hits[:5],
    )
    return ScrubResult(clean=False, hits=hits, payload=payload, rejected=False)


def invalidate_cache() -> None:
    """Clear the in-process mapping cache. Useful in tests."""
    _mapping_cache.clear()
