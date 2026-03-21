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
    type: str  # text, number, textarea, file, select_client, select_staff
    required: bool = True
    accept: list[str] = field(default_factory=list)  # for file fields
    options: list[dict[str, str]] = field(default_factory=list)  # for select fields

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
        return d


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
        }


# ---------------------------------------------------------------------------
# Registry — all 17 features (P1 activates 3, rest marked for later phases)
# ---------------------------------------------------------------------------

_FILE_ACCEPT = [".docx", ".pdf", ".txt", ".jpg", ".png"]
_MEDIA_ACCEPT = [".docx", ".pdf", ".txt", ".jpg", ".png", ".mp3", ".m4a"]

FEATURE_REGISTRY: dict[str, FeatureModule] = {

    # ===== P1: MVP (3 skills) =====

    "privacy_filter": FeatureModule(
        id="privacy_filter",
        display_name="隐私脱敏",
        description="对包含真实姓名的原始资料进行脱敏处理",
        icon="shield-check",
        category="数据安全",
        form_schema=[
            FormField(name="raw_file", label="原始资料", type="file", accept=_FILE_ACCEPT),
            FormField(name="source_description", label="资料来源说明", type="textarea", required=False),
        ],
        output_template="deidentified_record",
        _skill_name="privacy-filter",
        _review_tier="auto",
        _model="haiku",
        _context_files=["身份映射对照表"],
    ),

    "intake": FeatureModule(
        id="intake",
        display_name="新个案建档",
        description="接收初访记录，自动创建儿童档案",
        icon="user-plus",
        category="建档与评估",
        form_schema=[
            FormField(name="child_alias", label="儿童昵称", type="text"),
            FormField(name="age", label="年龄", type="number"),
            FormField(name="intake_file", label="初访记录", type="file", accept=_FILE_ACCEPT),
            FormField(name="parent_note", label="家长补充说明", type="textarea", required=False),
        ],
        output_template="intake_report",
        _skill_name="intake-interview",
        _review_tier="expert",
        _model="sonnet",
        _context_files=["核心档案"],
    ),

    "session_review": FeatureModule(
        id="session_review",
        display_name="课后记录分析",
        description="分析老师提交的课后记录，生成反馈和数据更新",
        icon="clipboard-check",
        category="日常教学",
        form_schema=[
            FormField(name="client_id", label="选择个案", type="select_client"),
            FormField(name="staff_id", label="选择老师", type="select_staff"),
            FormField(name="session_file", label="课后记录", type="file", accept=_MEDIA_ACCEPT),
            FormField(name="extra_note", label="补充说明", type="textarea", required=False),
        ],
        output_template="session_feedback",
        _skill_name="session-reviewer",
        _review_tier="auto",
        _model="sonnet",
        _context_files=["核心档案", "IEP", "教师成长档案", "强化物清单"],
    ),

    # ===== P2: Daily functions (4 skills) =====

    "teacher_guide": FeatureModule(
        id="teacher_guide",
        display_name="实操指引单",
        description="为实操老师生成下节课的指导方案",
        icon="book-open",
        category="日常教学",
        form_schema=[
            FormField(name="client_id", label="选择个案", type="select_client"),
            FormField(name="staff_id", label="选择老师", type="select_staff"),
            FormField(name="focus_note", label="本次重点说明", type="textarea", required=False),
        ],
        output_template="teacher_guide",
        _skill_name="teacher-guide",
        _review_tier="auto",
        _model="haiku",
        _context_files=["核心档案", "IEP", "近期日志"],
    ),

    "parent_letter": FeatureModule(
        id="parent_letter",
        display_name="生成家书",
        description="自动生成本周给家长的反馈信",
        icon="mail-heart",
        category="家校沟通",
        form_schema=[
            FormField(name="client_id", label="选择个案", type="select_client"),
            FormField(name="week_highlights", label="本周亮点补充", type="textarea", required=False),
            FormField(name="parent_concern", label="家长近期关心的问题", type="textarea", required=False),
        ],
        output_template="parent_letter",
        _skill_name="parent-update",
        _review_tier="auto",
        _model="sonnet",
        _context_files=["核心档案", "近期日志", "IEP", "强化物清单"],
    ),

    "staff_supervision": FeatureModule(
        id="staff_supervision",
        display_name="听课反馈",
        description="整理督导听课观察，生成教师反馈",
        icon="eye",
        category="师资管理",
        form_schema=[
            FormField(name="client_id", label="选择个案", type="select_client"),
            FormField(name="staff_id", label="选择老师", type="select_staff"),
            FormField(name="observation_file", label="听课记录", type="file", accept=_MEDIA_ACCEPT),
            FormField(name="extra_note", label="补充说明", type="textarea", required=False),
        ],
        output_template="supervision_feedback",
        _skill_name="staff-supervision",
        _review_tier="auto",
        _model="sonnet",
        _context_files=["核心档案", "IEP", "教师成长档案"],
    ),

    "quick_summary": FeatureModule(
        id="quick_summary",
        display_name="战前简报",
        description="快速聚合个案情报，5秒生成简报",
        icon="zap",
        category="日常教学",
        form_schema=[
            FormField(name="client_id", label="选择个案", type="select_client"),
            FormField(name="purpose", label="用途", type="text", required=False),
        ],
        output_template="quick_summary",
        _skill_name="quick-summary",
        _review_tier="auto",
        _model="haiku",
        _context_files=["核心档案", "近期日志", "IEP"],
    ),

    # ===== P3: Full suite (10 skills) =====

    "profile_builder": FeatureModule(
        id="profile_builder",
        display_name="深化核心档案",
        description="基于初访信息深度构建核心档案",
        icon="file-text",
        category="建档与评估",
        form_schema=[
            FormField(name="client_id", label="选择个案", type="select_client"),
            FormField(name="supplement_file", label="补充资料", type="file", accept=_FILE_ACCEPT, required=False),
        ],
        output_template="profile_report",
        _skill_name="profile-builder",
        _review_tier="expert",
        _model="sonnet",
        _context_files=["核心档案", "初访信息表"],
    ),

    "assessment": FeatureModule(
        id="assessment",
        display_name="评估记录",
        description="将专业评估转化为文字版优劣势分析",
        icon="bar-chart",
        category="建档与评估",
        form_schema=[
            FormField(name="client_id", label="选择个案", type="select_client"),
            FormField(name="assessment_file", label="评估数据", type="file", accept=_FILE_ACCEPT),
            FormField(name="tool_name", label="评估工具", type="text"),
        ],
        output_template="assessment_report",
        _skill_name="assessment-logger",
        _review_tier="expert",
        _model="sonnet",
        _context_files=["核心档案"],
    ),

    "fba": FeatureModule(
        id="fba",
        display_name="功能行为分析",
        description="对突发行为进行功能分析",
        icon="search",
        category="建档与评估",
        form_schema=[
            FormField(name="client_id", label="选择个案", type="select_client"),
            FormField(name="behavior_description", label="行为描述", type="textarea"),
            FormField(name="abc_file", label="ABC记录", type="file", accept=_FILE_ACCEPT, required=False),
        ],
        output_template="fba_report",
        _skill_name="fba-analyzer",
        _review_tier="expert",
        _model="sonnet",
        _context_files=["核心档案", "近期日志", "FBA档案"],
    ),

    "plan_generator": FeatureModule(
        id="plan_generator",
        display_name="制定IEP/BIP",
        description="汇总数据生成个别化教育计划",
        icon="target",
        category="方案制定",
        form_schema=[
            FormField(name="client_id", label="选择个案", type="select_client"),
            FormField(name="plan_type", label="方案类型", type="text"),
            FormField(name="focus_areas", label="重点领域", type="textarea", required=False),
        ],
        output_template="iep_plan",
        _skill_name="plan-generator",
        _review_tier="expert",
        _model="sonnet",
        _context_files=["核心档案", "评估", "FBA"],
    ),

    "program_slicer": FeatureModule(
        id="program_slicer",
        display_name="教学切片",
        description="将IEP目标拆解为微小教学步骤",
        icon="scissors",
        category="方案制定",
        form_schema=[
            FormField(name="client_id", label="选择个案", type="select_client"),
            FormField(name="target_goal", label="目标名称/编号", type="text"),
            FormField(name="detail", label="补充说明", type="textarea", required=False),
        ],
        output_template="program_slice",
        _skill_name="program-slicer",
        _review_tier="expert",
        _model="sonnet",
        _context_files=["核心档案", "IEP"],
    ),

    "reinforcer": FeatureModule(
        id="reinforcer",
        display_name="强化物评估",
        description="更新强化物偏好清单",
        icon="star",
        category="日常教学",
        form_schema=[
            FormField(name="client_id", label="选择个案", type="select_client"),
            FormField(name="observation_note", label="观察记录", type="textarea", required=False),
        ],
        output_template="reinforcer_report",
        _skill_name="reinforcer-tracker",
        _review_tier="auto",
        _model="sonnet",
        _context_files=["核心档案", "近期日志"],
    ),

    "milestone_report": FeatureModule(
        id="milestone_report",
        display_name="阶段报告",
        description="生成阶段性成果报告和家长喜报",
        icon="trophy",
        category="家校沟通",
        form_schema=[
            FormField(name="client_id", label="选择个案", type="select_client"),
            FormField(name="milestone_type", label="报告类型", type="text"),
            FormField(name="highlights", label="重点成果", type="textarea", required=False),
        ],
        output_template="milestone_report",
        _skill_name="milestone-report",
        _review_tier="expert",
        _model="sonnet",
        _context_files=["核心档案", "IEP", "近期日志", "评估"],
    ),

    "clinical_reflection": FeatureModule(
        id="clinical_reflection",
        display_name="周复盘",
        description="每周临床复盘，提取共性经验",
        icon="brain",
        category="督导管理",
        form_schema=[
            FormField(name="week_note", label="本周总结", type="textarea", required=False),
        ],
        output_template="reflection_report",
        _skill_name="clinical-reflection",
        _review_tier="auto",
        _model="sonnet",
        _context_files=["近期日志", "督导记录"],
    ),

    "staff_onboarding": FeatureModule(
        id="staff_onboarding",
        display_name="新教师建档",
        description="新老师入职，初始化教师档案",
        icon="user-check",
        category="师资管理",
        form_schema=[
            FormField(name="staff_name", label="教师姓名", type="text"),
            FormField(name="background", label="背景信息", type="textarea", required=False),
        ],
        output_template="staff_onboarding",
        _skill_name="staff-onboarding",
        _review_tier="auto",
        _model="haiku",
        _context_files=[],
    ),

    "transfer_protocol": FeatureModule(
        id="transfer_protocol",
        display_name="转衔协议",
        description="生成移交协议，汇总全生命周期数据",
        icon="arrow-right-circle",
        category="建档与评估",
        form_schema=[
            FormField(name="client_id", label="选择个案", type="select_client"),
            FormField(name="transfer_reason", label="转衔原因", type="textarea"),
            FormField(name="receiving_org", label="接收机构", type="text", required=False),
        ],
        output_template="transfer_report",
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
