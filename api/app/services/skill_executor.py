"""
SkillExecutor — the heart of the system.

Supports two execution modes:
  - "cli"  (dev):  pipes prompt to `claude` CLI, uses your Max plan quota
  - "api"  (prod): calls Anthropic Messages API with API key

Phase 1: Context Assembly
  - Load CLAUDE.md (role identity)
  - Load _config.md (global rules)
  - Load target SKILL.md (skill instructions)
  - Load vault context files specified by FeatureModule._context_files

Phase 2: Claude Call (CLI or API)

Phase 3: Output Parsing
  - Extract business content from Claude's response
  - Strip any leaked system prompt content (IP protection)
"""

from __future__ import annotations

import json
import logging
import re
import subprocess
import tempfile
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from app.config import get_settings
from app.core.feature_registry import FeatureModule
from app.services.vault_service import VaultService, LocalVaultService

logger = logging.getLogger(__name__)
settings = get_settings()

# Model mapping for API mode
MODEL_MAP = {
    "haiku": "claude-haiku-4-5-20251001",
    "sonnet": "claude-sonnet-4-6",
}

# Model mapping for CLI mode (claude --model flag)
CLI_MODEL_MAP = {
    "haiku": "haiku",
    "sonnet": "sonnet",
}


@dataclass
class SkillResult:
    output_content: str
    input_tokens: int
    output_tokens: int
    model_used: str


class SkillExecutor:
    """Execute a Skill via Claude CLI (dev) or API (prod)."""

    def __init__(self, vault: VaultService | LocalVaultService):
        self.vault = vault
        self._skill_cache: dict[str, str] = {}
        self._mode = settings.claude_mode  # "cli" or "api"

        if self._mode == "api":
            import anthropic
            base_url = settings.litellm_proxy_url or None
            self._api_client = anthropic.Anthropic(
                api_key=settings.anthropic_api_key,
                base_url=base_url,
            )

    def _load_skill_file(self, skill_name: str) -> str:
        """Load SKILL.md from the skills directory."""
        if skill_name in self._skill_cache:
            return self._skill_cache[skill_name]

        skill_path = Path(settings.skills_base_path) / skill_name / "SKILL.md"
        if not skill_path.exists():
            raise FileNotFoundError(f"Skill file not found: {skill_path}")

        content = skill_path.read_text(encoding="utf-8")
        self._skill_cache[skill_name] = content
        return content

    def _load_system_file(self, path_setting: str) -> str:
        """Load a system file (CLAUDE.md or _config.md)."""
        path = Path(path_setting)
        if not path.exists():
            logger.warning("System file not found: %s", path)
            return ""
        return path.read_text(encoding="utf-8")

    def _load_vault_context(self, feature: FeatureModule, client_code: str | None) -> str:
        """Load vault context files specified in FeatureModule._context_files."""
        context_parts = []

        for ctx_name in feature._context_files:
            content = self._resolve_context_file(ctx_name, client_code)
            if content:
                context_parts.append(f"--- {ctx_name} ---\n{content}")
            else:
                context_parts.append(f"--- {ctx_name} ---\n[文件不存在或为空，标记为待补充]")

        return "\n\n".join(context_parts)

    def _resolve_context_file(self, ctx_name: str, client_code: str | None) -> str | None:
        """Resolve a context file name to a vault path and read it."""
        if not client_code:
            return None

        path_map = {
            "核心档案": f"01-Clients/Client-{client_code}/Client-{client_code}-核心档案.md",
            "初访信息表": f"01-Clients/Client-{client_code}/Client-{client_code}-初访信息表.md",
            "IEP": f"01-Clients/Client-{client_code}/Client-{client_code}-IEP.md",
            "FBA档案": f"01-Clients/Client-{client_code}/Client-{client_code}-FBA分析.md",
            "评估": f"01-Clients/Client-{client_code}/Client-{client_code}-能力评估.md",
            "强化物清单": f"01-Clients/Client-{client_code}/Client-{client_code}-核心档案.md",
            "近期日志": f"02-Sessions/Client-{client_code}-日志库/",
            "教师成长档案": "03-Staff/",
            "督导记录": "04-Supervision/",
            "身份映射对照表": "00-RawData/身份映射对照表-绝密.md",
        }

        path = path_map.get(ctx_name)
        if not path:
            return None

        # For directory references, list recent files
        if path.endswith("/"):
            items = self.vault.list_directory(path)
            if not items:
                return None
            # list_directory now returns list[dict]; pick file entries only
            file_entries = [
                it for it in items
                if isinstance(it, dict) and it.get("type") == "file"
            ]
            # Stable sort by name then take the 5 most recent (lexicographic on date-prefixed names works well here)
            file_entries.sort(key=lambda it: it.get("name", ""))
            parts = []
            for entry in file_entries[-5:]:
                rel_path = entry.get("path") or (path + entry.get("name", ""))
                content = self.vault.read_file(rel_path)
                if content:
                    parts.append(content)
            return "\n\n---\n\n".join(parts) if parts else None

        return self.vault.read_file(path)

    def execute(
        self,
        feature: FeatureModule,
        form_data: dict[str, Any],
        parsed_uploads: list[str],
        client_code: str | None = None,
    ) -> SkillResult:
        """Execute a skill and return the result."""
        # --- Phase 1: Context Assembly ---
        claude_md = self._load_system_file(settings.claude_md_path)
        config_md = self._load_system_file(settings.config_md_path)
        skill_md = self._load_skill_file(feature._skill_name)

        system_prompt = self._build_system_prompt(claude_md, config_md, skill_md)
        vault_context = self._load_vault_context(feature, client_code)
        user_message = self._build_user_message(form_data, parsed_uploads, vault_context, client_code)

        # --- Phase 2: Call Claude ---
        if self._mode == "cli":
            result = self._execute_via_cli(feature, system_prompt, user_message)
        else:
            result = self._execute_via_api(feature, system_prompt, user_message)

        # --- Phase 3: Output Parsing ---
        result.output_content = self._sanitize_output(result.output_content)
        return result

    # -----------------------------------------------------------------------
    # Mode A: Claude Code CLI (dev — uses your Max plan)
    # -----------------------------------------------------------------------

    def _execute_via_cli(
        self,
        feature: FeatureModule,
        system_prompt: str,
        user_message: str,
    ) -> SkillResult:
        """
        Execute via `claude` CLI in print mode (-p).
        Uses your logged-in Max plan session — no API key needed.

        Strategy: combine system_prompt + user_message into a single prompt
        piped via stdin to avoid Windows command-line length limits.
        """
        model = CLI_MODEL_MAP.get(feature._model, "sonnet")

        logger.info(
            "[CLI mode] Executing skill '%s' with model '%s'",
            feature._skill_name, model,
        )

        # Combine system prompt and user message into a single user prompt.
        # This avoids --system-prompt arg length limits on Windows.
        combined_prompt = (
            f"<system-instructions>\n{system_prompt}\n</system-instructions>\n\n"
            f"---\n\n"
            f"{user_message}"
        )

        # Write to temp file and use pipe
        with tempfile.NamedTemporaryFile(
            mode="w", suffix=".md", delete=False, encoding="utf-8"
        ) as tmp:
            tmp.write(combined_prompt)
            prompt_path = tmp.name

        try:
            # Pipe the prompt file content via stdin
            cmd = [
                settings.claude_cli_path,
                "-p",
                "--model", model,
                "--output-format", "json",
                "--no-session-persistence",
            ]

            with open(prompt_path, "r", encoding="utf-8") as f:
                prompt_text = f.read()

            proc = subprocess.run(
                cmd,
                input=prompt_text,
                capture_output=True,
                text=True,
                timeout=int(getattr(settings, "job_timeout_seconds", 600)),
                encoding="utf-8",
            )

            if proc.returncode != 0:
                error_msg = proc.stderr.strip() or proc.stdout.strip() or "Unknown CLI error"
                logger.error("[CLI mode] claude failed (rc=%d): %s", proc.returncode, error_msg)
                raise RuntimeError(f"Claude CLI failed: {error_msg}")

            # Parse JSON output
            # Claude CLI JSON shape: { "result": "...", "usage": { "input_tokens": N, "output_tokens": N, "cache_read_input_tokens": N, "cache_creation_input_tokens": N }, ... }
            try:
                output_data = json.loads(proc.stdout)
                raw_output = output_data.get("result", "")
                usage = output_data.get("usage") or {}
                input_tokens = int(usage.get("input_tokens", 0) or 0)
                output_tokens = int(usage.get("output_tokens", 0) or 0)
                # Cache tokens still count toward quota, include them
                input_tokens += int(usage.get("cache_read_input_tokens", 0) or 0)
                input_tokens += int(usage.get("cache_creation_input_tokens", 0) or 0)
            except (json.JSONDecodeError, KeyError, TypeError):
                raw_output = proc.stdout.strip()
                input_tokens = 0
                output_tokens = 0

            return SkillResult(
                output_content=raw_output,
                input_tokens=input_tokens,
                output_tokens=output_tokens,
                model_used=f"cli:{model}",
            )

        finally:
            Path(prompt_path).unlink(missing_ok=True)

    # -----------------------------------------------------------------------
    # Mode B: Anthropic API (prod — uses API key)
    # -----------------------------------------------------------------------

    def _execute_via_api(
        self,
        feature: FeatureModule,
        system_prompt: str,
        user_message: str,
    ) -> SkillResult:
        """Execute via Anthropic Messages API."""
        model = MODEL_MAP.get(feature._model, MODEL_MAP["sonnet"])

        logger.info(
            "[API mode] Executing skill '%s' with model '%s'",
            feature._skill_name, model,
        )

        response = self._api_client.messages.create(
            model=model,
            max_tokens=8192,
            system=system_prompt,
            messages=[{"role": "user", "content": user_message}],
        )

        return SkillResult(
            output_content=response.content[0].text,
            input_tokens=response.usage.input_tokens,
            output_tokens=response.usage.output_tokens,
            model_used=model,
        )

    # -----------------------------------------------------------------------
    # Shared helpers
    # -----------------------------------------------------------------------

    def _build_system_prompt(self, claude_md: str, config_md: str, skill_md: str) -> str:
        """Assemble the system prompt from three components."""
        parts = []
        if claude_md:
            parts.append(claude_md)
        if config_md:
            parts.append(config_md)
        # Cloud mode override goes BEFORE skill to take priority
        parts.append(self._cloud_mode_supplement())
        parts.append(skill_md)
        return "\n\n---\n\n".join(parts)

    def _cloud_mode_supplement(self) -> str:
        """Additional instructions for cloud execution mode."""
        return """
# 云端执行模式说明

你现在运行在 **云端 SaaS API 模式**下。你的所有文件操作由服务端自动执行，你不需要也无法直接操作文件系统。

## 工作方式
1. **读取**：你需要的个案上下文（核心档案、IEP、近期日志等）已在下方"个案上下文"中提供给你。
2. **写入**：你需要生成所有文件的完整内容。服务端根据你的输出自动写入 vault 对应路径。
3. **追加**：如果技能要求追加到某个文件（如变更日志），一并输出追加内容。

## 输出格式（关键）
如果技能只生成**一个文件**，直接输出 Markdown 内容即可。

如果技能需要生成**多个文件**，使用以下分隔格式：

```
<!-- FILE: 03-Staff/督导-XX-成长档案-张三.md -->
（第一个文件的完整内容）

<!-- FILE: 04-Supervision/系统变更日志.md | APPEND -->
（追加到该文件的内容）
```

规则：
- `<!-- FILE: 路径 -->` 标记新文件（Write 覆盖写入）
- `<!-- FILE: 路径 | APPEND -->` 标记追加内容
- 路径使用 vault 标准目录（01-Clients, 02-Sessions, 03-Staff, 04-Supervision, 05-Communication）
- 路径中的 `[教师姓名]`、`[儿童昵称]` 等占位符替换为实际值
- `{{当前日期}}` 替换为实际日期

## ⚠️ 数据优先级（冲突时的取舍原则）
当上传的原始资料与下方「表单信息」/「档案代号绑定」存在冲突时，按以下优先级处理：

1. **档案代号、文件路径 → 以表单 / 绑定值为准**（不可协商）
2. **儿童昵称、年龄等身份字段 → 以表单为准**，原始资料里的不同昵称仅作"备注"保留
3. **临床观察内容（如发育史、行为描述、强化物）→ 以原始资料为准**

即：**路径和代号 100% 跟随表单，内容 100% 跟随原始资料，冲突点在文末「备注」标注即可，不要改路径。**

## ⚠️ 输出强制约束（覆盖 CLAUDE.md 中的"人工在环"规则）
本次执行运行在云端无状态模式，**没有 chat 上下文可以等待用户二次确认**。即使技能 SKILL.md 或 CLAUDE.md 提到"先发预览给用户确认再写入"，在云端模式下你必须：

1. **直接生成最终的、可落盘的文件内容**，使用 `<!-- FILE: 路径 -->` 标记
2. **禁止输出**「让我先给你看预览/确认/请回复 y」这种对话式文案
3. **禁止输出**纯解释性段落而不带任何 FILE marker
4. 如果你认为产出存在敏感问题（如脱敏歧义），可以在文档末尾「⚠️ 临床备注」章节里标注，但**主要内容必须照常写入**
5. 服务端会把你的 FILE marker 内容直接落盘并交付，无任何中间审核步骤（expert tier 的审核也只看你给的 marker 内容）

**违反此约束的输出 = 整个 job 视为失败。**

## 注意
- 不要讨论路径是否存在、环境配置等问题 — 服务端会自动创建目录
- 不要输出 Shell 指令或 Claude Code 工具调用
- 专注生成高质量的业务文档内容
""".strip()

    def _build_user_message(
        self,
        form_data: dict[str, Any],
        parsed_uploads: list[str],
        vault_context: str,
        client_code: str | None = None,
    ) -> str:
        """Assemble the user message from form data, uploads, and vault context."""
        parts = [
            "请根据技能要求生成业务文档。如需创建多个文件，使用 `<!-- FILE: 路径 -->` 分隔。"
        ]

        # Hard-bind the client code so Claude cannot infer a different one from the raw uploads.
        # This prevents cases like: form says "石头2" but upload body mentions "乐乐" → output goes to wrong folder.
        if client_code:
            parts.append(
                "## ⚠️ 档案代号绑定（强制规则）\n\n"
                f"本次任务的档案代号**必须**使用：`Client-{client_code}`\n\n"
                "- 所有 `<!-- FILE: 路径 -->` 标记中的路径占位符 `[代号]` 一律替换为 "
                f"`{client_code}`。\n"
                f"- 文档正文中所有 `Client-[代号]` 或 `[[Client-代号-xxx]]` 的占位符也替换为 `Client-{client_code}`。\n"
                "- **即使上传的原始资料正文里出现其他昵称/代号，也必须以表单传入的代号为准**；"
                "如发现正文与表单冲突，在文档末尾的"
                "「备注」中标注该差异即可，切勿修改路径/档案代号。\n"
            )

        # BUG #13/#15: Hard-bind staff name (resolved from staff_id uuid in jobs.py).
        # 没有这条规则，AI 会拿 vault 里已知的教师名 fallback，或写"教师待指定"。
        if (staff_name := form_data.get("staff_name")):
            parts.append(
                "## ⚠️ 教师姓名绑定（强制规则）\n\n"
                f"本次任务的执行教师**必须**使用：`{staff_name}`\n\n"
                f"- 所有 `<!-- FILE: 路径 -->` 标记中的 `[姓名]` / `教师-[姓名]` 占位符一律替换为 `{staff_name}`。\n"
                f"- 文档正文中的 `[[教师-XX]]` wikilink 也使用 `[[教师-{staff_name}]]`。\n"
                f"- 路径 `03-Staff/教师-[姓名]/` 一律写成 `03-Staff/教师-{staff_name}/`。\n"
                "- **即使 vault 上下文里出现其他教师名，也必须以表单传入的姓名为准**。\n"
            )

        if vault_context:
            parts.append(f"## 个案上下文\n\n{vault_context}")

        if parsed_uploads:
            parts.append("## 上传文件内容\n\n" + "\n\n---\n\n".join(parsed_uploads))

        if form_data:
            form_text = "\n".join(
                f"- **{k}**: {v}"
                for k, v in form_data.items()
                if v and not k.endswith("_id") and not k.endswith("_file")
            )
            if form_text:
                parts.append(f"## 表单信息\n\n{form_text}")

        return "\n\n".join(parts) if parts else "请执行此技能。"

    def _sanitize_output(self, raw: str) -> str:
        """
        IP Protection: strip any content that might leak system prompts.
        Remove references to SKILL.md, _config.md, internal instructions.
        """
        patterns = [
            r"(?i)skill\.md",
            r"(?i)_config\.md",
            r"(?i)claude\.md",
            r"(?i)_router\.md",
            r"操作指令[：:]",
            r"目标路径[：:]",
            r"执行步骤",
        ]
        lines = raw.split("\n")
        cleaned = []
        for line in lines:
            if any(re.search(p, line) for p in patterns):
                continue
            cleaned.append(line)

        return "\n".join(cleaned).strip()
