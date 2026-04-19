---
description: Skill 调度索引。当用户请求不明确时，Claude 应参考本文件判断应该调用哪个 Skill。
---

# 📋 Skill 调度索引

## 关键词 → Skill 映射表

| 用户关键词 | 应触发的 Skill | 说明 |
|:---|:---|:---|
| 原始资料、脱敏、真实姓名、隐私 | `privacy-filter` | 处理含真实姓名的原始数据 |
| 初访、新个案、建档、新来的孩子 | `intake-interview` | 新个案的首次处理 |
| 新老师、新员工、入职、师资建档 | `staff-onboarding` | 新老师入职，初始化教师档案及目录 |
| 核心档案、完善档案、Master File | `profile-builder` | 深化核心档案内容 |
| 评估、VB-MAPP、ABLLS、得分 | `assessment-logger` | 录入专业评估结果 |
| 行为分析、ABC、功能分析、FBA、问题行为原因 | `fba-analyzer` | 分析问题行为功能 |
| 强化物、偏好、饱和、奖励没用了 | `reinforcer-tracker` | 更新强化物偏好清单 |
| 方案、IEP、BIP、目标制定、计划 | `plan-generator` | 制定干预方案 |
| 拆解、切片、教学步骤、PT、DI、怎么教 | `program-slicer` | 将目标拆解为教学切片 |
| 课后卡、课后记录、老师填的表 | `session-reviewer` | 处理老师的课后记录 |
| 听课、观察老师、督导反馈、看了老师上课 | `staff-supervision` | 处理督导听课观察 |
| 实操单、实操小抄、准备下节课 | `teacher-guide` | 生成老师实操指引 |
| 家书、家长反馈、家长沟通、微光信 | `parent-update` | 生成家长周反馈 |
| 里程碑、阶段报告、结业、喜报 | `milestone-report` | 生成阶段性报告 |
| 简报、开会前、家长会、速览 | `quick-summary` | 生成战前电梯简报 |
| 复盘、周总结、本周回顾 | `clinical-reflection` | 每周临床复盘 |
| 转衔、移交、换老师、换机构 | `transfer-protocol` | 生成移交协议 |

## ⚠️ 易混淆场景澄清

### "实操单"相关 — 三个 Skill 都能生成
| 场景 | 正确 Skill | 判断依据 |
|:---|:---|:---|
| 督导说"帮我给小李准备下节课的实操单" | `teacher-guide` | 无新输入，纯基于已有 IEP 生成 |
| 督导说"我刚看完小李上课，帮我整理反馈和实操单" | `staff-supervision` | 有新的督导观察随笔作为输入 |
| 督导说"帮我把 IEP 的目标3拆解成教学步骤" | `program-slicer` | 有新的 IEP 目标需要拆解 |

### "处理老师提交的内容" vs "督导自己观察"
| 输入来源 | 正确 Skill |
|:---|:---|
| **老师**填的《课后记录与求助卡》 | `session-reviewer` |
| **督导**自己的听课随笔/观察记录 | `staff-supervision` |

### "看孩子情况" — 两个 Skill 都涉及
| 场景 | 正确 Skill |
|:---|:---|
| 开会前快速了解全貌（只读不写） | `quick-summary` |
| 老师刚交课后记录，需要分析+反馈 | `session-reviewer` |

### "给家长发消息"
| 场景 | 正确 Skill |
|:---|:---|
| 常规周反馈家书 | `parent-update` |
| 达到里程碑/结业的喜报 | `milestone-report` |

## 🔗 标准工作流链路

```
=== 师资 HR 支线 ===
A. staff-onboarding (新老师入职建档树)
       ↓
(等待进入日常听课督导循环)

=== 个案临床主线 ===
1. privacy-filter (脱敏原始资料)
       ↓
2. intake-interview (建档+目录初始化)
       ↓
3. profile-builder (深化核心档案)
       ↓
4. assessment-logger (录入评估) + fba-analyzer (行为分析)
       ↓
5. plan-generator (制定 IEP/BIP)
       ↓
6. program-slicer (拆解教学切片) → teacher-guide (生成实操单)
       ↓
   ┌──────── 日常循环 ────────┐
   │  session-reviewer (处理课后记录)   │
   │      ↕                              │
   │  staff-supervision (督导听课反馈)   │
   │      ↓                              │
   │  teacher-guide (更新实操单)         │
   └──────────────────────────────────────┘
       ↓
7. parent-update (每周家书)
8. reinforcer-tracker (每双周强化物评估)
9. clinical-reflection (每周复盘)
       ↓
10. milestone-report (阶段报告/结业)
       ↓
11. transfer-protocol (转衔移交)
```

## 📋 推荐执行链（手动触发顺序建议）

### 新个案标准链（通常跨 2-3 周）
1. **privacy_filter**（脱敏）— 随到随跑
2. **intake**（建骨架）— 脱敏后立即
3. **profile_builder**（填档案）— intake approved 后
4. **assessment**（能力基线）— ⏰ 需留出 **2-3 周正式施测窗口**
5. **fba**（如有问题行为）— ⏰ 至少 **2 周 ABC 记录**后（OBS-05 门槛）
6. **plan_generator**（IEP/BIP）— assessment + fba 都有数据后
7. **program_slicer**（为每个 Teacher 拆实操单）

### 每周维护链
1. **session_review**（每节课后）
2. **reinforcer_tracker**（每 2 周 — 需 ≥ 3 节课数据）
3. **parent_letter**（每周家书）
4. **clinical_reflection**（每周末）

### 阶段评估链（每月 / 每季）
1. 数据收集（session_review × N）
2. **milestone_report**（阶段总结）
3. **plan_generator**（IEP 修订，若需要）

### 转衔链（结业 / 转校）
1. 确认最近 1 次 **milestone_report** 已完成
2. 最终 **staff_supervision** 总结（给接手教师的交棒）
3. **transfer_protocol**（⚠️ 不可逆 — 前置数据门槛见 SKILL.md）

## ⛔ Skill 前置条件表（数据门槛）

| Skill | 前置条件 | 不满足时应给建议 |
|:---|:---|:---|
| `intake-interview` | 脱敏存档已存在 | 先跑 `privacy-filter` |
| `profile-builder` | 初访信息表 > 500 字 | 先跑 `intake-interview` |
| `assessment-logger` | 有上传评估数据（文件或口述）| 补充数据源 |
| `fba-analyzer` | ≥ 10 个 ABC event 或 ≥ 2 周日志 | 先积累 `session-reviewer` 输出 |
| `plan-generator` | 能力评估 + (若有问题行为) FBA 都非骨架 | 先跑前置 skill |
| `program_slicer` | IEP 已定稿（> 3000 字）| 先跑 `plan-generator` |
| `reinforcer-tracker` | ≥ 3 节课观察数据（OBS-05 延伸）| 先积累 `session-reviewer` 输出 |
| `milestone-report` | 能力评估 + 近 2 周日志 ≥ 3 篇 | 先跑前置 skill |
| `transfer-protocol` | **课后日志 ≥ 8 + 里程碑 ≥ 1 + 周期 ≥ 30 天**（OBS-04 门槛）| 补齐数据 **或** 在 transfer_reason 标"紧急"越过 |

**触发规则**：当用户直接请求某个需前置条件的 skill 但前置缺失时，Claude 应：
1. 明确指出缺失的前置
2. 建议先执行对应的前置 skill
3. 除非用户明确声明"跳过前置要求"（含"紧急"/"强制"/"我知道数据不足"等关键字），否则不执行
