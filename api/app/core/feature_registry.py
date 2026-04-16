"""
Feature Registry — the public shell for each Skill.

Frontend only ever sees: display_name, description, icon, category, form_schema.
Fields prefixed with _ are SERVER-ONLY and never serialized to the client.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass(frozen=True)
class FormField:
    name: str
    label: str
    type: str  # text, number, textarea, file, select, select_client, select_staff
    required: bool = True
    accept: list[str] = field(default_factory=list)  # for file fields
    options: list[dict[str, str]] = field(default_factory=list)  # for select fields
    placeholder: str = ""
    help_text: str = ""

    def to_public_dict(self) -> dict[str, Any]:
        d: dict[str, Any] = {
            "name": self.name,
            "label": self.label,
            "type": self.type,
            "required": self.required,
        }
        if self.accept:
            d["accept"] = self.accept
        if self.options:
            d["options"] = self.options
        if self.placeholder:
            d["placeholder"] = self.placeholder
        if self.help_text:
            d["help_text"] = self.help_text
        return d


@dataclass(frozen=True)
class ExpectedOutput:
    """Describes a file the Skill will create/edit/append, shown to user before submit."""
    op: str  # "create" | "edit" | "append"
    path: str  # vault path with placeholders, e.g. "01-Clients/Client-[代号]/Client-[代号]-IEP.md"
    description: str  # human-readable explanation

    def to_public_dict(self) -> dict[str, str]:
        return {"op": self.op, "path": self.path, "description": self.description}


@dataclass(frozen=True)
class FeatureModule:
    id: str
    display_name: str
    description: str
    icon: str
    category: str
    form_schema: list[FormField]
    output_template: str

    # --- server-only (never exposed to frontend) ---
    _skill_name: str
    _review_tier: str  # "auto" | "expert"
    _model: str  # "haiku" | "sonnet"
    _context_files: list[str] = field(default_factory=list)

    # --- public, optional (added in Batch B/C) ---
    expected_outputs: list[ExpectedOutput] = field(default_factory=list)
    is_destructive: bool = False  # marks irreversible operations (status change, transfer)

    def to_public_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "display_name": self.display_name,
            "description": self.description,
            "icon": self.icon,
            "category": self.category,
            "form_schema": {
                "fields": [f.to_public_dict() for f in self.form_schema],
            },
            "output_template": self.output_template,
            "expected_outputs": [o.to_public_dict() for o in self.expected_outputs],
            "is_destructive": self.is_destructive,
        }


# ---------------------------------------------------------------------------
# Registry — all 17 features (P1 activates 3, rest marked for later phases)
# ---------------------------------------------------------------------------

_FILE_ACCEPT = [".docx", ".pdf", ".txt", ".md", ".jpg", ".png"]
_MEDIA_ACCEPT = [".docx", ".pdf", ".txt", ".md", ".jpg", ".png", ".mp3", ".m4a"]

FEATURE_REGISTRY: dict[str, FeatureModule] = {

    # ===== P1: MVP (3 skills) =====

    "privacy_filter": FeatureModule(
        id="privacy_filter",
        display_name="隐私脱敏",
        description="对包含真实姓名的原始资料进行脱敏，自动维护身份映射表",
        icon="shield-check",
        category="数据安全",
        form_schema=[
            FormField(name="raw_file", label="原始资料", type="file", accept=_FILE_ACCEPT),
            FormField(name="known_names", label="已知需脱敏的人名/学校/地名", type="textarea", required=False,
                      help_text="每行一个，可大幅提升脱敏准确率"),
            FormField(name="suggested_code_name", label="建议代号", type="text", required=False,
                      placeholder="如 A-小虎；不填则自动顺延分配"),
            FormField(name="source_description", label="资料来源说明", type="textarea", required=False),
        ],
        output_template="deidentified_record",
        expected_outputs=[
            ExpectedOutput(op="create", path="00-RawData/脱敏存档/[代号]-脱敏原始数据.md",
                           description="净化后的原始资料"),
            ExpectedOutput(op="append", path="00-RawData/身份映射对照表-绝密.md",
                           description="新增一行真实姓名↔代号映射"),
        ],
        _skill_name="privacy-filter",
        _review_tier="auto",
        _model="haiku",
        _context_files=["身份映射对照表"],
    ),

    "intake": FeatureModule(
        id="intake",
        display_name="新个案建档",
        description="接收脱敏后的初访记录，自动创建儿童文件夹 + 初访表 + 核心档案骨架",
        icon="user-plus",
        category="建档与评估",
        form_schema=[
            FormField(name="child_alias", label="儿童昵称", type="text",
                      placeholder="如 小虎、兜兜（用于生成代号）"),
            FormField(name="intake_file", label="初访记录 (脱敏后)", type="file", accept=_FILE_ACCEPT),
            FormField(name="parent_note", label="家长补充说明", type="textarea", required=False),
        ],
        output_template="intake_report",
        expected_outputs=[
            ExpectedOutput(op="create", path="01-Clients/Client-[代号]/Client-[代号]-初访信息表.md",
                           description="结构化初访信息表（发育史/家庭生态/家长痛点）"),
            ExpectedOutput(op="create", path="01-Clients/Client-[代号]/Client-[代号]-核心档案.md",
                           description="核心档案骨架（待 profile-builder 深化）"),
        ],
        _skill_name="intake-interview",
        _review_tier="expert",
        _model="sonnet",
        _context_files=["核心档案"],
    ),

    "session_review": FeatureModule(
        id="session_review",
        display_name="课后记录分析",
        description="分析老师提交的课后记录，生成反馈日志 + 教师档案追加 (文字或文件二选一)",
        icon="clipboard-check",
        category="日常教学",
        form_schema=[
            FormField(name="client_id", label="选择个案", type="select_client"),
            FormField(name="staff_id", label="选择老师", type="select_staff"),
            FormField(name="session_text", label="课后记录文字 (推荐直接粘贴)", type="textarea", required=False),
            FormField(name="session_file", label="课后记录文件 (可选)", type="file", accept=_MEDIA_ACCEPT, required=False),
            FormField(name="extra_note", label="补充说明", type="textarea", required=False),
        ],
        output_template="session_feedback",
        expected_outputs=[
            ExpectedOutput(op="create", path="02-Sessions/Client-[代号]-日志库/{{日期}}-Client-[代号]-[教师]记录.md",
                           description="督导反馈日志"),
            ExpectedOutput(op="append", path="03-Staff/教师-[姓名]/督导-[姓名]-成长档案.md",
                           description="追加本次督导记录到教师档案"),
        ],
        _skill_name="session-reviewer",
        _review_tier="auto",
        _model="sonnet",
        _context_files=["核心档案", "IEP", "教师成长档案", "强化物清单"],
    ),

    # ===== P2: Daily functions (4 skills) =====

    "teacher_guide": FeatureModule(
        id="teacher_guide",
        display_name="实操指引单",
        description="为实操老师生成下节课的「一页纸实操小抄」（覆盖旧版）",
        icon="book-open",
        category="日常教学",
        form_schema=[
            FormField(name="client_id", label="选择个案", type="select_client"),
            FormField(name="staff_id", label="选择老师", type="select_staff"),
            FormField(name="focus_note", label="本次重点说明", type="textarea", required=False),
        ],
        output_template="teacher_guide",
        expected_outputs=[
            ExpectedOutput(op="create", path="03-Staff/教师-[姓名]/实操单-Client-[代号]-[姓名].md",
                           description="老师实操小抄（覆盖该教师×个案的旧版）"),
        ],
        _skill_name="teacher-guide",
        _review_tier="auto",
        _model="haiku",
        _context_files=["核心档案", "IEP", "近期日志"],
    ),

    "parent_letter": FeatureModule(
        id="parent_letter",
        display_name="生成家书",
        description="基于近 7 天日志，生成本周给家长的「微光家书」",
        icon="mail-heart",
        category="家校沟通",
        form_schema=[
            FormField(name="client_id", label="选择个案", type="select_client"),
            FormField(name="week_highlights", label="本周亮点补充", type="textarea", required=False),
            FormField(name="parent_concern", label="家长近期关心的问题", type="textarea", required=False),
        ],
        output_template="parent_letter",
        expected_outputs=[
            ExpectedOutput(op="create", path="05-Communication/Client-[代号]-沟通记录/家书-{{日期}}.md",
                           description="本周家长反馈信"),
            ExpectedOutput(op="append", path="01-Clients/Client-[代号]/Client-[代号]-核心档案.md",
                           description="追加一行沟通记录到核心档案末尾"),
        ],
        _skill_name="parent-update",
        _review_tier="auto",
        _model="sonnet",
        _context_files=["核心档案", "近期日志", "IEP", "强化物清单"],
    ),

    "staff_supervision": FeatureModule(
        id="staff_supervision",
        display_name="听课反馈",
        description="整理督导听课观察，产出教师成长档案追加 + 实操单更新（文字或文件二选一）",
        icon="eye",
        category="师资管理",
        form_schema=[
            FormField(name="client_id", label="选择个案", type="select_client"),
            FormField(name="staff_id", label="选择老师", type="select_staff"),
            FormField(name="observation_text", label="听课随笔 (推荐直接打字)", type="textarea", required=False),
            FormField(name="observation_file", label="听课记录文件 (可选)", type="file", accept=_MEDIA_ACCEPT, required=False),
        ],
        output_template="supervision_feedback",
        expected_outputs=[
            ExpectedOutput(op="append", path="03-Staff/教师-[姓名]/督导-[姓名]-成长档案.md",
                           description="追加本次督导观察 + BST 阶段标注"),
            ExpectedOutput(op="create", path="03-Staff/教师-[姓名]/实操单-Client-[代号]-[姓名].md",
                           description="同步更新该教师实操单（覆盖旧版）"),
        ],
        _skill_name="staff-supervision",
        _review_tier="auto",
        _model="sonnet",
        _context_files=["核心档案", "IEP", "教师成长档案"],
    ),

    "quick_summary": FeatureModule(
        id="quick_summary",
        display_name="战前简报",
        description="5 秒聚合个案全库情报，生成 30 秒速览简报",
        icon="zap",
        category="日常教学",
        form_schema=[
            FormField(name="client_id", label="选择个案", type="select_client"),
            FormField(name="purpose", label="用途", type="select", required=False, options=[
                {"value": "case_meeting", "label": "个案研讨会"},
                {"value": "parent_meeting", "label": "家长会"},
                {"value": "school_communication", "label": "校方沟通"},
                {"value": "internal", "label": "内部速查"},
            ]),
        ],
        output_template="quick_summary",
        expected_outputs=[
            ExpectedOutput(op="create", path="05-Communication/Client-[代号]-沟通记录/电梯简报-Client-[代号]-{{日期}}.md",
                           description="30 秒速览简报（核心痛点/杀手锏强化物/主跑目标）"),
        ],
        _skill_name="quick-summary",
        _review_tier="auto",
        _model="haiku",
        _context_files=["核心档案", "近期日志", "IEP"],
    ),

    # ===== P3: Full suite (10 skills) =====

    "profile_builder": FeatureModule(
        id="profile_builder",
        display_name="深化核心档案",
        description="基于初访信息深度构建核心档案（⚠️ 覆盖现有核心档案）",
        icon="file-text",
        category="建档与评估",
        form_schema=[
            FormField(name="client_id", label="选择个案", type="select_client"),
            FormField(name="additional_context", label="补充背景信息 (可选)", type="textarea", required=False,
                      help_text="督导可补充未在初访表中体现的关键信息"),
        ],
        output_template="profile_report",
        expected_outputs=[
            ExpectedOutput(op="edit", path="01-Clients/Client-[代号]/Client-[代号]-核心档案.md",
                           description="覆盖核心档案（从骨架变完整版，旧版本备份至变更日志）"),
        ],
        is_destructive=True,
        _skill_name="profile-builder",
        _review_tier="expert",
        _model="sonnet",
        _context_files=["核心档案", "初访信息表"],
    ),

    "assessment": FeatureModule(
        id="assessment",
        display_name="评估记录",
        description="将专业评估（VB-MAPP/ABLLS-R 等）转化为文字版优劣势分析 + 更新核心档案能力画像",
        icon="bar-chart",
        category="建档与评估",
        form_schema=[
            FormField(name="client_id", label="选择个案", type="select_client"),
            FormField(name="tool_name", label="评估工具", type="select", options=[
                {"value": "VB-MAPP", "label": "VB-MAPP"},
                {"value": "ABLLS-R", "label": "ABLLS-R"},
                {"value": "PEP-3", "label": "PEP-3"},
                {"value": "ESDM", "label": "ESDM 课程清单"},
                {"value": "其他", "label": "其他工具"},
            ]),
            FormField(name="assessment_file", label="评估数据 (得分表/原始记录)", type="file", accept=_FILE_ACCEPT),
        ],
        output_template="assessment_report",
        expected_outputs=[
            ExpectedOutput(op="create", path="01-Clients/Client-[代号]/Client-[代号]-能力评估.md",
                           description="完整评估报告（按工具标准域逐项分析）"),
            ExpectedOutput(op="edit", path="01-Clients/Client-[代号]/Client-[代号]-核心档案.md",
                           description="替换 🧩 核心能力画像 章节"),
        ],
        _skill_name="assessment-logger",
        _review_tier="expert",
        _model="sonnet",
        _context_files=["核心档案"],
    ),

    "fba": FeatureModule(
        id="fba",
        display_name="功能行为分析",
        description="自动扫描日志库 ABC 记录，生成 FBA 报告 + 更新核心档案问题行为预警",
        icon="search",
        category="建档与评估",
        form_schema=[
            FormField(name="client_id", label="选择个案", type="select_client"),
            FormField(name="time_range", label="分析时间范围", type="select", required=False, options=[
                {"value": "1w", "label": "近 1 周"},
                {"value": "2w", "label": "近 2 周（默认）"},
                {"value": "1m", "label": "近 1 个月"},
                {"value": "3m", "label": "近 3 个月"},
            ]),
            FormField(name="focus_behavior", label="重点关注行为 (可选)", type="textarea", required=False,
                      help_text="如不填，AI 将自动从日志中识别高频行为"),
            FormField(name="abc_file", label="补充 ABC 记录文件 (可选)", type="file", accept=_FILE_ACCEPT, required=False),
        ],
        output_template="fba_report",
        expected_outputs=[
            ExpectedOutput(op="create", path="01-Clients/Client-[代号]/Client-[代号]-FBA分析.md",
                           description="完整 FBA 报告（功能假设 + 竞争行为模型 + 干预策略）"),
            ExpectedOutput(op="edit", path="01-Clients/Client-[代号]/Client-[代号]-核心档案.md",
                           description="替换 🚨 历史问题行为备忘 章节"),
        ],
        _skill_name="fba-analyzer",
        _review_tier="expert",
        _model="sonnet",
        _context_files=["核心档案", "近期日志", "FBA档案"],
    ),

    "plan_generator": FeatureModule(
        id="plan_generator",
        display_name="制定IEP/BIP",
        description="汇总初访/评估/FBA 数据，生成个别化教育计划",
        icon="target",
        category="方案制定",
        form_schema=[
            FormField(name="client_id", label="选择个案", type="select_client"),
            FormField(name="plan_type", label="方案类型", type="select", options=[
                {"value": "IEP", "label": "IEP（个别化教育计划）"},
                {"value": "BIP", "label": "BIP（行为干预计划）"},
                {"value": "IEP+BIP", "label": "IEP + BIP（综合方案）"},
            ]),
            FormField(name="focus_areas", label="重点关注领域", type="textarea", required=False,
                      help_text="如：mand 训练、社交起始、问题行为替代"),
        ],
        output_template="iep_plan",
        expected_outputs=[
            ExpectedOutput(op="create", path="01-Clients/Client-[代号]/Client-[代号]-IEP.md",
                           description="完整 IEP/BIP 方案（含 SMART 短期目标矩阵）"),
            ExpectedOutput(op="edit", path="01-Clients/Client-[代号]/Client-[代号]-核心档案.md",
                           description="更新「当前阶段」字段 + 索引追加 IEP 链接"),
        ],
        _skill_name="plan-generator",
        _review_tier="expert",
        _model="sonnet",
        _context_files=["核心档案", "评估", "FBA"],
    ),

    "program_slicer": FeatureModule(
        id="program_slicer",
        display_name="教学切片",
        description="将 IEP 目标拆解为微小教学步骤，并产出对应教师的实操单",
        icon="scissors",
        category="方案制定",
        form_schema=[
            FormField(name="client_id", label="选择个案", type="select_client"),
            FormField(name="staff_id", label="目标执行教师", type="select_staff"),
            FormField(name="target_goal", label="目标名称/编号", type="text",
                      placeholder="如 ST 1 或目标全称"),
            FormField(name="detail", label="补充说明", type="textarea", required=False),
        ],
        output_template="program_slice",
        expected_outputs=[
            ExpectedOutput(op="append", path="01-Clients/Client-[代号]/Client-[代号]-IEP.md",
                           description="在目标章节追加完整教学切片剧本"),
            ExpectedOutput(op="create", path="03-Staff/教师-[姓名]/实操单-Client-[代号]-[姓名].md",
                           description="生成对应教师的实操小抄"),
        ],
        _skill_name="program-slicer",
        _review_tier="expert",
        _model="sonnet",
        _context_files=["核心档案", "IEP"],
    ),

    "reinforcer": FeatureModule(
        id="reinforcer",
        display_name="强化物评估",
        description="扫描近期日志，更新强化物偏好清单 + 核心档案同步",
        icon="star",
        category="日常教学",
        form_schema=[
            FormField(name="client_id", label="选择个案", type="select_client"),
            FormField(name="period", label="评估周期", type="select", required=False, options=[
                {"value": "1w", "label": "近 1 周"},
                {"value": "2w", "label": "近 2 周（默认）"},
                {"value": "1m", "label": "近 1 个月"},
            ]),
            FormField(name="observation_note", label="观察记录补充", type="textarea", required=False),
        ],
        output_template="reinforcer_report",
        expected_outputs=[
            ExpectedOutput(op="create", path="01-Clients/Client-[代号]/Client-[代号]-强化物评估-{{日期}}.md",
                           description="强化物偏好动态评估报告"),
            ExpectedOutput(op="edit", path="01-Clients/Client-[代号]/Client-[代号]-核心档案.md",
                           description="替换 🧸 强化物偏好清单 章节"),
        ],
        _skill_name="reinforcer-tracker",
        _review_tier="auto",
        _model="sonnet",
        _context_files=["核心档案", "近期日志"],
    ),

    "milestone_report": FeatureModule(
        id="milestone_report",
        display_name="阶段报告",
        description="生成专业版里程碑报告 + 家长版微光喜报 + 切换核心档案状态",
        icon="trophy",
        category="家校沟通",
        form_schema=[
            FormField(name="client_id", label="选择个案", type="select_client"),
            FormField(name="milestone_type", label="报告类型", type="select", options=[
                {"value": "stage_assessment", "label": "阶段评估"},
                {"value": "quarterly_summary", "label": "季度小结"},
                {"value": "graduation", "label": "结业报告"},
            ]),
            FormField(name="highlights", label="重点成果补充", type="textarea", required=False),
        ],
        output_template="milestone_report",
        expected_outputs=[
            ExpectedOutput(op="create", path="01-Clients/Client-[代号]/Client-[代号]-里程碑报告-{{日期}}.md",
                           description="专业版里程碑报告（含基线对比与数据来源）"),
            ExpectedOutput(op="create", path="05-Communication/Client-[代号]-沟通记录/喜报-里程碑-{{日期}}.md",
                           description="家长版微光喜报"),
            ExpectedOutput(op="edit", path="01-Clients/Client-[代号]/Client-[代号]-核心档案.md",
                           description="切换档案状态（如「方案执行中」→「进阶/泛化期」）"),
        ],
        _skill_name="milestone-report",
        _review_tier="expert",
        _model="sonnet",
        _context_files=["核心档案", "IEP", "近期日志", "评估"],
    ),

    "clinical_reflection": FeatureModule(
        id="clinical_reflection",
        display_name="周复盘",
        description="自动扫描本周所有日志/督导记录，提取共性经验并追踪上周 Action Items",
        icon="brain",
        category="督导管理",
        form_schema=[
            FormField(name="week_note", label="本周总结补充", type="textarea", required=False,
                      help_text="可选；不填则纯靠 AI 扫描"),
        ],
        output_template="reflection_report",
        expected_outputs=[
            ExpectedOutput(op="create", path="04-Supervision/复盘-{{日期}}.md",
                           description="本周临床督导复盘"),
            ExpectedOutput(op="append", path="04-Supervision/督导灵感与SOP迭代库.md",
                           description="（可选）追加重大临床洞察至灵感库"),
        ],
        _skill_name="clinical-reflection",
        _review_tier="auto",
        _model="sonnet",
        _context_files=["近期日志", "督导记录"],
    ),

    "staff_onboarding": FeatureModule(
        id="staff_onboarding",
        display_name="新教师建档",
        description="新老师入职，初始化教师工作目录 + 成长档案骨架",
        icon="user-check",
        category="师资管理",
        form_schema=[
            FormField(name="staff_name", label="教师姓名", type="text",
                      placeholder="如 小李、张三"),
            FormField(name="background", label="背景信息", type="textarea", required=False,
                      help_text="如：幼教转行 / 无经验白纸 / 有某机构 1 年经验等"),
        ],
        output_template="staff_onboarding",
        expected_outputs=[
            ExpectedOutput(op="create", path="03-Staff/教师-[姓名]/",
                           description="新建教师工作目录"),
            ExpectedOutput(op="create", path="03-Staff/督导-[你的名字]-成长档案-[姓名].md",
                           description="成长档案骨架（含基线盘点 + 培训里程碑表）"),
        ],
        _skill_name="staff-onboarding",
        _review_tier="auto",
        _model="haiku",
        _context_files=[],
    ),

    "transfer_protocol": FeatureModule(
        id="transfer_protocol",
        display_name="转衔协议",
        description="生成移交协议，汇总全生命周期数据（⚠️ 不可逆：档案状态会改为「已移交」）",
        icon="arrow-right-circle",
        category="建档与评估",
        form_schema=[
            FormField(name="client_id", label="选择个案", type="select_client"),
            FormField(name="transfer_reason", label="转衔原因", type="textarea"),
            FormField(name="receiving_org", label="接收机构 (可选)", type="text", required=False),
        ],
        output_template="transfer_report",
        expected_outputs=[
            ExpectedOutput(op="create", path="01-Clients/Client-[代号]/Client-[代号]-转衔移交协议-{{日期}}.md",
                           description="完整转衔移交协议（医疗/破冰/红线/未竟事业）"),
            ExpectedOutput(op="edit", path="01-Clients/Client-[代号]/Client-[代号]-核心档案.md",
                           description="档案状态改为「🟠 已移交」（不可逆）"),
        ],
        is_destructive=True,
        _skill_name="transfer-protocol",
        _review_tier="expert",
        _model="sonnet",
        _context_files=["核心档案", "IEP", "评估", "FBA", "近期日志"],
    ),
}


def get_feature(feature_id: str) -> FeatureModule | None:
    return FEATURE_REGISTRY.get(feature_id)


def get_all_feature_ids() -> list[str]:
    return list(FEATURE_REGISTRY.keys())


def get_public_features(feature_ids: list[str]) -> list[dict]:
    """Return public-facing feature data for a set of allowed feature IDs."""
    return [
        FEATURE_REGISTRY[fid].to_public_dict()
        for fid in feature_ids
        if fid in FEATURE_REGISTRY
    ]
