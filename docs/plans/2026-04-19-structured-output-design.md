# 结构化输出架构设计 — v6+ 路线图

**提出日期**：2026-04-19（v5 测试后）
**起因**：BUG #25 v5 两轮 retry 证明 prompt 层无法可靠约束 AI 的 meta-commentary 真名泄漏 — 需要从架构层拆掉"FILE marker 之间 vs 之外"的灰色地带。
**状态**：设计草案；暂不实施（v5 结束时用户与 AI 一致同意 mark 这个方向）

---

## 现有架构的缺陷

`skill_executor.execute()` 产出的 `output_content` 是 **半结构化 Markdown**：

```markdown
[preamble — AI 任意叙事]

<!-- FILE: 00-RawData/脱敏存档/... -->
[file 1 content]

<!-- FILE: 04-Supervision/... | APPEND -->
[file 2 content]

[trailing text — AI 任意建议 / 变更日志自述]
```

后端 `vault_service.write_output_to_vault` 用 regex 抽取 `<!-- FILE: ... -->` 标记之间的内容。

### 灰色地带

| 区域 | 是否落盘 | 问题 |
|:---|:---|:---|
| FILE marker 之前（preamble） | **部分**：整段 `output_content` 存入 `jobs.output_content` 列 → 前端 review 页面展示 + 下游 skill 可能读到 | AI 会在这里写"真名→代号"对照（BUG #25 v5 实证 7 处） |
| FILE marker 包含内容 | **是**：写入 vault 对应文件 | 受 vault_service 路径改写保护；v5 已达 0 真名 |
| 两个 FILE marker 之间 | **部分**：同 preamble | 同上问题 |
| 最后 FILE marker 之后 | **部分**：同 preamble | 同上问题 |

**本质**：LLM 自由输出 vs 后端结构提取 之间的不对齐。prompt 规则无法让 AI 稳定"只在 FILE 内写事情"。

---

## 方案 1：Envelope 包裹（推荐起步，v6 目标）

### 设计

在 SKILL.md 输出规范段强制要求：

```markdown
<!-- BEGIN_OUTPUT -->

<!-- FILE: <path> [| APPEND / SECTION_REPLACE: ...] -->
<file content>

<!-- FILE: <path2> -->
<file content>

<!-- END_OUTPUT -->

<!-- BEGIN_SUPERVISOR_NOTE -->
<不落盘的叙述：给督导解释、建议下一步 skill、自检清单摘要>
<!-- END_SUPERVISOR_NOTE -->
```

### 后端改动

`api/app/services/vault_service.py::write_output_to_vault`：

```python
def write_output_to_vault(vault, skill_name, client_code, output_content):
    # 1. 抽 BEGIN_OUTPUT / END_OUTPUT
    m = re.search(r'<!-- BEGIN_OUTPUT -->(.*?)<!-- END_OUTPUT -->', output_content, re.DOTALL)
    if m:
        vault_payload = m.group(1)  # 只有这段进入落盘逻辑
    else:
        # fallback: 老逻辑，防止 AI 没遵守 envelope
        vault_payload = output_content
        logger.warning(f"skill {skill_name} 未使用 envelope 格式，走兼容模式")

    # 2. 从 vault_payload 里抽 FILE markers（现有逻辑）
    files = parse_file_markers(vault_payload)
    for path, content, mode in files:
        _write_one(vault, path, content, mode, client_code)

def get_supervisor_note(output_content):
    """前端 review 展示用；不落盘。"""
    m = re.search(r'<!-- BEGIN_SUPERVISOR_NOTE -->(.*?)<!-- END_SUPERVISOR_NOTE -->',
                  output_content, re.DOTALL)
    return m.group(1).strip() if m else ""
```

### 17 个 SKILL.md 的改动

每个文件加一段标准"输出 envelope 规范"（可以从 `_config.md` 注入，避免 17 处重复）：

```markdown
## 📦 输出 envelope 规范（强制）

你的回答**必须**用以下 envelope 结构，否则后端会走兼容模式（仍写盘但不保证安全）：

<!-- BEGIN_OUTPUT -->
<!-- FILE: <path> -->
[正式落盘内容]
<!-- END_OUTPUT -->

<!-- BEGIN_SUPERVISOR_NOTE -->
[给督导看的叙述：建议下一步、自检摘要、观察说明]
<!-- END_SUPERVISOR_NOTE -->

**规则**：
- `BEGIN_OUTPUT ... END_OUTPUT` 之间只放 FILE marker + 文件正文
- 不能在两个 FILE 之间写自由叙事（走 SUPERVISOR_NOTE）
- SUPERVISOR_NOTE 里允许有 known_names（它不落盘），但仍建议避免
```

### 优势

- **从架构上消除** meta preamble 灰色地带
- **向后兼容**：AI 没遵守 envelope 时 fallback 到老逻辑 + 打 warning
- **最小侵入**：SKILL.md 加一段通用模板 + `_config.md` 统一规定 + vault_service.py 加 20 行 envelope 解析

### 代价

- AI 训练了 N 轮的老写法要改，前几轮 v6 需要重点观察 envelope 遵守率
- 需要给 prompt 加足够多正例/反例让 AI 稳定遵守

---

## 方案 2：XML 完全结构化（v7-v8 目标）

### 设计

AI 输出完整 XML：

```xml
<?xml version="1.0" encoding="utf-8"?>
<skill_output skill="privacy-filter" version="v6">
  <files>
    <file path="00-RawData/脱敏存档/Client-A-小满-脱敏原始数据.md" mode="write">
      <content><![CDATA[
[正式档案内容]
      ]]></content>
    </file>
    <file path="04-Supervision/系统变更日志.md" mode="append">
      <content><![CDATA[
[追加段落]
      ]]></content>
    </file>
  </files>

  <metadata>
    <privacy_scan_passed>true</privacy_scan_passed>
    <sensitive_categories_handled>儿童,母亲,父亲,医学团队,教育团队,品牌</sensitive_categories_handled>
    <skill_specific>
      <mapping_table_rows_added>1</mapping_table_rows_added>
      <brand_redactions>1</brand_redactions>
    </skill_specific>
  </metadata>

  <next_skills>
    <suggestion priority="high">intake-interview</suggestion>
    <suggestion priority="medium">profile-builder</suggestion>
  </next_skills>

  <supervisor_note>
[给督导的自由叙事]
  </supervisor_note>
</skill_output>
```

### 后端改动

```python
import xml.etree.ElementTree as ET
# 或更稳的 lxml
tree = ET.fromstring(output_content)
for f in tree.findall('.//file'):
    path = f.attrib['path']
    mode = f.attrib.get('mode', 'write')
    content = f.find('content').text
    _write_one(vault, path, content, mode, client_code)

metadata = parse_metadata(tree.find('metadata'))  # 前端可直接用
next_skills = [s.text for s in tree.findall('.//suggestion')]
```

### 优势

- **0 歧义**：XML 解析器处理所有 edge case（转义、嵌套、换行）
- **丰富 metadata**：可在 frontend 展示 privacy_scan_passed / skill_specific / next_skills 变按钮
- **可验证**：用 XML Schema (XSD) 验证输出合法性，不合法直接 fail 让 AI 重试
- **跨 skill 一致性**：所有 skill 产出同一 schema

### 代价

- **17 个 SKILL.md 大改**
- AI 对 CDATA 内嵌 Markdown 可能有编辑错误（多引号、`]]>` 冲突）
- 需要在 `_config.md` 写一份公共 XML schema 规范

---

## 方案 3：Function Calling (v8+)

切 Max 订阅 CLI → Anthropic API 模式，使用 `tool_use` blocks：

```python
tools = [
    {
        "name": "write_file",
        "description": "写入 vault 文件（overwrite 模式）",
        "input_schema": {
            "type": "object",
            "properties": {
                "path": {"type": "string"},
                "content": {"type": "string"},
            },
            "required": ["path", "content"]
        }
    },
    {
        "name": "append_to_file",
        "input_schema": {...}
    },
    {
        "name": "add_identity_mapping",
        "description": "在身份映射表新增一行",
        "input_schema": {
            "type": "object",
            "properties": {
                "real_name": {"type": "string"},
                "code": {"type": "string"},
                "category": {"enum": ["child", "mother", "father", "medical", "brand"]},
            }
        }
    },
    {
        "name": "return_summary",
        "input_schema": {...}
    }
]

response = client.messages.create(
    model="claude-opus-4-7",
    tools=tools,
    messages=[...]
)

for block in response.content:
    if block.type == "tool_use":
        if block.name == "write_file":
            vault.write(**block.input)
        ...
```

### 优势

- **最 agentic**：AI 真的在"调用系统"，不是写 Markdown 给人看
- **结构完全由代码决定**：AI 不可能绕过 tool schema 做自由输出
- **Anthropic 官方推的 agentic 模式**，未来 Claude 系列对这种模式持续优化

### 代价

- **架构重写**：从 CLI 模式切 API 模式（MEMORY.md 里有 opus CLI 的 Max 订阅记录 → 改 API 要重新考虑成本）
- **17 个 SKILL.md 全部重写**为 tool 调用形式
- **前端 review 页面**也要改：展示 tool call 序列而不是 Markdown

---

## 路线图建议

| 阶段 | 方案 | 投入 | 预期效果 |
|:---|:---|:---|:---|
| **v5 后立刻** | Post-hoc privacy guard（代码层拦截真名进 vault） | 0.5 天 | 封死落盘真名 P1 风险 |
| **v6 起步** | 方案 1 Envelope 包裹 | 0.5-1 天 | 架构层消除 meta preamble 灰色地带 |
| **v7-v8** | 方案 2 XML 结构化 | 3-5 天 | 0 歧义 + frontend 丰富 metadata |
| **v9+** | 方案 3 Function Calling | 1-2 周 + 切 API | agentic 架构终极形态 |

## 未决问题

1. **SUPERVISOR_NOTE 是否进 job.output_content**？
   - 方案 A：进，前端 review 展示 + 下游 skill 可读
   - 方案 B：只存 logs + 内部分析，不进数据库
   - 倾向：A（保留临床沟通价值）

2. **Envelope 遵守率怎么保证**？
   - SKILL.md prompt + `_config.md` 通用规范 + 跨轮测试（看 v6 的 envelope 遵守率能不能 ≥ 95%）
   - 后备：fallback 兼容模式 + warning 日志

3. **方案 2/3 是否需要在 review 页面改 UI**？
   - 是。从"读 Markdown"变成"读 XML / tool_calls"，前端需要 renderer
   - v7 前单独做一轮前端设计

---

## 放弃原因（为什么不一次到位方案 3）

1. **Max 订阅**的 CLI 模式是当前成本优势来源 — v5 测试 ~$6/轮，切 API 估算 > $15/轮（opus 按 token 计费）
2. **17 个 SKILL.md 存量**是最大沉没成本 — 它们承载了跨 5 轮积累的 prompt 工程
3. **渐进式比革命式稳定** — v5 测试已经证明"跨轮观察 → 改 prompt → 验证"这个闭环可靠

---

## 参考

- v5 lifecycle report: `docs/testing/A-小满-lifecycle-report.md`
- BUG #25 v5 retry 证据: `docs/testing/bugs/2026-04-20-bug-log.md`
- v5 S1 retry dump: `docs/testing/A-小满-dump/S1-privacy-output-BUG25-27-RETRY.md`
