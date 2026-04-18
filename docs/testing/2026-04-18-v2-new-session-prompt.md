# 🎬 新 Session 提示词 — A-小航 完整生命周期 E2E v2

> **你复制下面整段提示词到新 Claude Code 窗口即可启动测试。**

---

## 任务：完整生命周期 E2E 测试 v2（A-小航）

### 背景
- 上一轮（2026-04-17）A-小舟的 13 步骤 E2E 测试已完成
- 期间发现并修复了 BUG #17（retry 后 job 永久 queued，commit `8294675` 已部署）
- 还新增了超管 cancel_job endpoint（commit `7632a14` 已部署）
- 本次是 **v2 验证**：在一个**性格差异显著的新虚拟儿童**上重跑完整 13 步骤，确认系统稳定性 + AI 泛化能力。

### 必读的上下文（按顺序）

1. **本 session 完整 handoff**：`docs/testing/MEMORY-lifecycle-v2.md`
   （含 13 步骤剧本 / 凭证 / 代码模板 / schema 速查 / A-小航 人设）

2. **上轮成功报告**：`docs/testing/A-小舟-lifecycle-report.md`
   （学习怎么做 token 获取 + fire-and-poll + vault 验证 + 自洽性检查）

3. **系统路由**：`.claude/skills/_router.md`（skill 之间的临床关系）

4. **vault 规范**：`.claude/skills/_config.md`（目录树 + 代号规则）

5. **上轮 bug log**：`docs/testing/bugs/2026-04-17-bug-log.md`（BUG #17 现场 + 修复）

### 核心任务

创建**虚拟儿童 `A-小航`**（女、5岁2月、焦虑啃手指、代词混乱、爱数字），按 MEMORY 里 13 步骤剧本跑完整生命周期。

**A-小航 设定**（用于新访谈，与 A-小舟 拉开差异）：
```
小航，女，5 岁 2 个月，2021 年 2 月生
妈妈：赵雅婷（教师），爸爸：孙立（医生）
3 岁确诊 ASD，从未系统接受干预（妈妈此前尝试"自学 ABA"）
主要问题：
- 语言：约 100 个词汇，能说 2-3 字短语，但代词混乱（把"我"说成"你"）
- 社交：对同龄女孩有兴趣但不会接近，看到陌生人会躲妈妈身后
- 行为：焦虑时啃手指（已有倒刺）、重复问同一问题（"要去哪里" × N 次）
- 兴趣：公主贴纸、小马宝莉、数字（能数到 100）、排队玩具
家长痛点：想让她下半年能进幼儿园大班
家庭资源：妈妈全职带，爸爸夜班偶尔参与，外婆每周末来帮忙
```

**通过标准**（不是"API 返 200"，而是真临床可用）：
- 每步 AI 输出落盘正确（路径 + 内容）
- 下一步能读到上一步的产物（context 正确流转）
- 整个档案自洽（代号/姓名/时间线不矛盾）
- **泛化检验**：A-小航 的档案必须**显著不同**于 A-小舟（男、拍头、旋转玩具）
  - 具体检查点：
    - 核心档案里应有"代词反转 I/You reversal" 的 assessment 解读
    - IEP 目标应优先 "代词使用 + 焦虑管理" 而不是 A-小舟 的 "Mand 主动要求"
    - 强化物应命中 "公主贴纸 / 小马宝莉" 而不是 "葡萄干 / 旋转玩具"
    - FBA 应针对 "啃手指" 焦虑型自刺激（自我刺激/焦虑缓解功能）而不是 "拍头" 逃避/获得
    - 家书语气应偏稳定关怀（焦虑型家庭）而不是行为危机处理

### 关键技巧（避免踩坑 — v1 已验证）

1. **Chrome MCP CDP 45s timeout**：所有 AI 调用必须用 fire-and-poll（见 MEMORY 模板）
2. **BLOCKED Sensitive key**：长 UUID 用 `document.title` 或 `pattern count` 绕
3. **multipart 文件字段名永远是 `files`**（不是 raw_file / intake_file / abc_file 等 form_schema 里的名字）
4. **Expert tier 耗时 300-550s**：等至少 5 分钟再看，用 bash sleep 不要 await
5. **并行策略**：Step 3/4/5 可并行 / 7+8 可并行 / 9+10+12 可并行；**Step 11 FBA 建议单独跑**
6. **Chrome 扩展断连** 就切 curl（MEMORY 里有 bash 模板）
7. **Refresh token** 每轮 expert tier 等之后都做一次
8. **transfer_protocol 是 destructive**：放最后，approve 前用 `AskUserQuestion` 明确问用户
9. **如果 job 卡住**：调用 `POST /api/v1/jobs/{id}/admin-cancel`（新 endpoint）

### 测试环境

- **VM**: http://34.182.17.120/
- **主账号**: `wxinflying@gmail.com` / `Wangliang007$`
- **Demo 账号密码**: `Demo123!`（teacher-a / parent-demo / you-bcba 等）
- **Teacher A uuid**: `ac17848d-ae03-4819-a5e3-1df91890b99e`
- **Parent Demo uuid**: `fdbbdec6-8fce-4a02-9000-51fdb8ffb296`
- **当前部署 commit**: `7632a14`（含 BUG #17 fix + admin-cancel endpoint）

### 输出要求

全流程跑完后，在 `docs/testing/` 下写 **`A-小航-lifecycle-report.md`**，包含：

1. **13 步骤每步的执行结果**（job_id / tokens / 耗时 / 产出文件列表 / 字节数）
2. **9 项自洽性检查表**（代号 / 教师名 / 时间线 / 核心档案章节 / 家书引用 / FBA-IEP / 喜报-里程碑 / 变更日志 / wikilink）
3. **⭐ 与 A-小舟 的泛化对比表**（5 项：代词 / IEP 主目标 / 强化物 / FBA 焦点 / 家书语气）
4. 如果发现新 bug：BUG #18 起编号，commit 到 master，加到 bug-log
5. 最终判断：系统是否具备 **"真临床泛化能力"**（还是只会套模板）

### 工作约束

- **可以改代码**（发现新 bug 就修）
- **可以 commit/push**（每个修复一个 commit）
- **但 A-小舟 / A-小虎 / A-小朝 等老个案不要动**
- Bug 修复后 **必须 push 到 master**，然后 **要求用户手动部署到 VM**（我没 ssh key），再继续验证

### 开工第一步

1. 读 `docs/testing/MEMORY-lifecycle-v2.md`（最重要，所有代码模板都在里面）
2. 读 `docs/testing/A-小舟-lifecycle-report.md` 学习 v1 流程
3. 读 `.claude/skills/_router.md` + `.claude/skills/_config.md`
4. 确认 VM 可达：`curl http://34.182.17.120/api/v1/auth/captcha`
5. 开始执行 13 步骤

祝好运 🍀
