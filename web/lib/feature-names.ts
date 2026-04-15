/** Feature ID to Chinese display name mapping. */
export const FEATURE_NAMES: Record<string, string> = {
  privacy_filter: "隐私脱敏",
  intake: "新个案建档",
  profile_builder: "核心档案构建",
  session_review: "课后记录分析",
  teacher_guide: "实操指引单",
  program_slicer: "教学切片",
  parent_letter: "生成家书",
  staff_supervision: "听课反馈",
  staff_onboarding: "新教师建档",
  quick_summary: "战前简报",
  assessment_logger: "评估记录",
  fba: "功能分析",
  plan_generator: "方案生成",
  reinforcer_tracker: "强化物追踪",
  clinical_reflection: "临床复盘",
  milestone_report: "阶段报告",
  transfer_protocol: "移交协议",
};

export function getFeatureName(featureId: string): string {
  return FEATURE_NAMES[featureId] || featureId;
}
