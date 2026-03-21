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
