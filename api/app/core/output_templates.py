"""
Output template definitions.
Controls how Claude's Markdown output is rendered into final delivery format.
"""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(frozen=True)
class OutputTemplate:
    id: str
    format: str  # "markdown" | "pdf" | "html"
    title: str
    sections: list[str] = field(default_factory=list)
    branding: bool = False


OUTPUT_TEMPLATES: dict[str, OutputTemplate] = {
    "deidentified_record": OutputTemplate(
        id="deidentified_record",
        format="markdown",
        title="脱敏存档",
        sections=["隐私声明", "脱敏后的完整原始记录"],
    ),
    "intake_report": OutputTemplate(
        id="intake_report",
        format="pdf",
        title="个案初访报告",
        sections=["基本信息", "发育史", "家庭泛化资源", "建议下一步"],
        branding=True,
    ),
    "session_feedback": OutputTemplate(
        id="session_feedback",
        format="markdown",
        title="课后反馈",
        sections=["数据摘要", "正向反馈", "改进建议", "每日外挂"],
    ),
    "teacher_guide": OutputTemplate(
        id="teacher_guide",
        format="markdown",
        title="实操指引单",
        sections=["目标清单", "教学策略", "注意事项"],
    ),
    "parent_letter": OutputTemplate(
        id="parent_letter",
        format="html",
        title="给家长的微光反馈信",
        sections=["本周亮点", "家庭泛化建议", "温馨提醒"],
        branding=True,
    ),
    "supervision_feedback": OutputTemplate(
        id="supervision_feedback",
        format="markdown",
        title="听课反馈",
        sections=["教学观察", "改进建议", "实操外挂"],
    ),
    "quick_summary": OutputTemplate(
        id="quick_summary",
        format="markdown",
        title="战前简报",
        sections=["核心情报", "近期趋势", "注意事项"],
    ),
    "iep_plan": OutputTemplate(
        id="iep_plan",
        format="pdf",
        title="个别化教育计划 (IEP)",
        sections=["长期目标", "短期目标", "教学策略", "评估标准"],
        branding=True,
    ),
    "profile_report": OutputTemplate(
        id="profile_report",
        format="markdown",
        title="核心档案",
        sections=["能力画像", "强化物", "行为备忘"],
    ),
    "assessment_report": OutputTemplate(
        id="assessment_report",
        format="pdf",
        title="评估分析报告",
        sections=["评估概要", "优势分析", "短板分析", "建议"],
        branding=True,
    ),
    "fba_report": OutputTemplate(
        id="fba_report",
        format="pdf",
        title="功能行为分析报告",
        sections=["行为描述", "功能假设", "干预建议"],
        branding=True,
    ),
    "program_slice": OutputTemplate(
        id="program_slice",
        format="markdown",
        title="教学切片",
        sections=["目标分解", "教学步骤", "判定标准"],
    ),
    "reinforcer_report": OutputTemplate(
        id="reinforcer_report",
        format="markdown",
        title="强化物评估",
        sections=["偏好变化", "建议清单"],
    ),
    "milestone_report": OutputTemplate(
        id="milestone_report",
        format="pdf",
        title="阶段报告",
        sections=["基线对比", "成果亮点", "下一阶段建议"],
        branding=True,
    ),
    "reflection_report": OutputTemplate(
        id="reflection_report",
        format="markdown",
        title="临床复盘",
        sections=["本周回顾", "共性经验", "SOP更新"],
    ),
    "staff_onboarding": OutputTemplate(
        id="staff_onboarding",
        format="markdown",
        title="教师建档",
        sections=["教师简介", "成长档案"],
    ),
    "transfer_report": OutputTemplate(
        id="transfer_report",
        format="pdf",
        title="转衔移交协议",
        sections=["个案概况", "干预历程", "当前状态", "移交建议"],
        branding=True,
    ),
}
