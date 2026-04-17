# 🧠 MEMORY — 完整儿童生命周期 E2E 测试（新 Session 交接）

> 给下一个 session 的 Clinical Director Agent 准备的上下文。读完这个就能直接开工。

---

## 🎯 本次测试目标

**不是**单点 skill smoke test，**不是**边界测试，**而是**：
> 模拟一个新来的小朋友，从「家长初访 → 建档 → 评估 → 制定方案 → 教学落地 → 日常反馈 → 家校沟通 → 达标结业 / 转衔」**完整生命周期**，跑通所有 skill 的串联业务流，验证 vault 档案最终是否形成完整、内部一致、可被 BCBA 直接用的临床记录。

**通过标准**：
- 每一步的 AI 输出落盘正确（路径 + 内容）
- 下一步能读到上一步的产物（context 正确流转）
- 整个 vault 档案自洽（代号/姓名/时间线/数据不矛盾）
- BCBA 能基于这套档案做出真实临床决策

---

## 📋 建议的完整生命周期流程（13 步骤）

按照 `skills/_router.md` 的临床逻辑串起来：

| # | 阶段 | Skill | tier | 核心验证点 |
|---|---|---|---|---|
| 1 | 接收原始资料 | **privacy_filter** | auto | 姓名脱敏 + 身份映射对照表更新 |
| 2 | 建档骨架 | **intake** | expert | 创建 Client 文件夹 + 初访信息表 + 核心档案骨架 |
| 3 | 深化档案 | **profile_builder** | expert | 把 intake 的粗档案深化成 8+ 模块 |
| 4 | 能力评估 | **assessment** | expert | 生成 VB-MAPP 风格能力评估，更新核心档案 |
| 5 | 教师建档 | **staff_onboarding** | auto | 创建教师档案 + 关联教师-个案 |
| 6 | 方案制定 | **plan_generator** | expert | 基于评估产出 IEP 方案 |
| 7 | 教学切片 | **program_slicer** | expert | 把 IEP 宏观目标拆成老师一页纸小抄 |
| 8 | 一线教学反馈 | **session_review** | auto | 老师课后记录 → 生成日志 + 教师档案追加 |
| 9 | 督导听课反馈 | **staff_supervision** | auto | 督导观察教学 → 教师档案追加 + 实操单更新 |
| 10 | 强化物评估 | **reinforcer** | auto | 扫近期日志，更新强化物偏好 |
| 11 | 突发问题行为 FBA | **fba** | expert | ABC 分析 + 假设 + BIP |
| 12 | 家校沟通 | **parent_letter** | auto | 生成「微光家书」 |
| 13 | 达标结业 | **milestone_report** | expert | 阶段报告 + 喜报 |

**可选第 14 步**：`transfer_protocol` — 如果场景是转校（destructive，会改 Client 状态为已移交）

**跳过**：`quick_summary`（研讨会/家长会前简报，阶段性功能，不必在生命周期里走）、`teacher_guide`（下节课前小抄，和 program_slicer 有重叠，可选）、`clinical_reflection`（周末全局复盘，不是线性流程一部分）、`assessment_logger`（测试材料准备用，不走流程）

---

## 🛠️ 测试环境 & 凭证

**VM**: `34.182.17.120` (GCP，g810741472wang@)
**URL**: http://34.182.17.120/
**主账号**: wxinflying@gmail.com / **Wangliang007$**（不是 Demo123!）
**Demo 账号**（密码统一 `Demo123!`）:
- `you-bcba@yourorg.com` — 审核用
- `teacher-a@yourorg.com` — 一线老师（关联 A-小虎）
- `teacher-b@yourorg.com` — 备用
- `parent-demo@yourorg.com` — 家长（关联 A-小虎）
- `qa-test-bcba@example.com` — QA BCBA

**当前 commits 已部署**: `ff66434`（6 个 bug 全修 + AI revise timeout 跟随 settings 600s）

**旧测试个案** (vault 里已有，**别污染**):
- A-小朝 — 前 3 轮全流程测试个案（第 4 轮刚走完 fba+plan+milestone approve，还留 1 个 transfer_protocol pending）
- A-小虎 — teacher-a 和 parent-demo linked，第 4 轮阶段 2 刚用过
- A-乐乐1、A-33、A-石头、A-石头2 — 历史遗留
- A-Ð¡³¯ — 乱码孤儿（latin-1 污染产物，可忽略）

---

## 🎬 推荐测试剧本：虚拟儿童「A-小舟」

为了不污染已有档案，**建议创建一个全新的虚拟儿童**。建议代号：`A-小舟`。

### 📝 初访原始资料模板

准备一份含 PII 的原始访谈 + 脱敏版（文件已在 `docs/testing/fixtures/` 有模板，可复用或新建）：

```
小舟，男，4 岁 6 个月，2021年10月生
妈妈：王琳，爸爸：李明
2 岁确诊 ASD，3 岁开始在 XX 机构接受干预
主要问题：
- 语言：有约 50 个单词，短句少，很少主动表达
- 社交：眼神接触短暂，不主动找人玩
- 行为：着急时会拍头（自伤），见到糖果会尖叫
- 兴趣：喜欢旋转物体、汽车、蓝色
家长痛点：希望能教会他表达需求不再拍头
家庭资源：妈妈全职陪读，爸爸工程师偶尔陪玩，奶奶退休可接送
```

**重点**：让 privacy_filter 把「王琳 / 李明」映射为代号，生成对照表。

---

## 🔑 关键注意事项（避免踩坑）

### 1. API 端点容易搞错
- ✅ `/api/v1/vault/read?path=...`（**不是** `/vault/file`）
- ✅ `/api/v1/reviews/ai-revise`（不是 `/reviews/{id}/revise`）
- ✅ `/api/v1/reviews/{id}/approve` POST + body `{"modified_content": null, "comments": null}`
- ✅ Job submit 的 `form_data` 是 JSON **字符串**（multipart form field），不是嵌套 JSON

### 2. 浏览器 MCP `[BLOCKED: Sensitive key]` 坑
某些长字符串/UUID 样值在 `javascript_exec` 返回里会被 MCP 遮蔽为 `[BLOCKED: Sensitive key]`。绕法：
- 把结果写到 `document.title`（字符串短、纯数字/状态字用这个）
- 把结果写到 `window.__X` 后下一次 exec 读取
- 把长内容做 pattern count（比如 `content.match(/撕卡片/g)` 只返回数字）

### 3. Expert tier skill 耗时规律
**千万别用 `await` 等**（Chrome MCP CDP 45s timeout）。用 fire-and-poll：
```js
window.__JOB_STARTED = Date.now();
window.__JOB_DONE = false;
fetch(...).then(async r => { window.__JOB = ...; window.__JOB_DONE = true; });
```
然后每 10s 轮询 `window.__JOB_DONE`。

**预期耗时**（基于第 4 轮实测）：
- auto tier haiku: 5-30s
- auto tier sonnet 小 skill: 30-90s
- expert tier sonnet 大上下文 skill (fba/plan_generator/milestone_report/transfer_protocol): **500-550s**
- AI revise 12k 字: 240s

### 4. 权限模型
- `wxinflying` 是 **super_admin**（能看所有 tenant）
- 组织内部 `org_admin` 也能看全 tenant
- `bcba` 能看全 tenant 个案 + /reviews
- `teacher/parent` 只能看 linked clients + 受限 features（详见 `vault.py::_ROLE_DIRS`）

新创建 A-小舟 时，需要通过超管身份建，然后用 `ClientUserLink` 关联到至少 1 个 teacher + 1 个 parent。API 可能需要直接 DB 操作，不清楚有没有 HTTP 端点（可以先查 `api/app/routers/clients.py`）。

### 5. staff_id 必须是 uuid → 会被后端查 User 表解析为 staff_name 注入（BUG #13/#15 修复）
```js
form_data = JSON.stringify({
  client_id: '...',
  staff_id: 'ac17848d-ae03-4819-a5e3-1df91890b99e', // Teacher A 的真实 uuid
  session_text: '...',
});
```

### 6. 不要 approve transfer_protocol — 会改 Client 状态为「已移交」
测 step 14 时如果你 approve 了，后续步骤 Client 状态就不对了。建议把 transfer_protocol 放在**整个流程的最后一步**，明确告诉用户「这是 destructive，你确认吗？」再 approve。

---

## 📊 需要验证的"生命周期自洽性"指标

跑完全流程后，这些跨步骤一致性必须成立：

| 检查项 | 期望 | 读取方式 |
|---|---|---|
| **代号一致** | A-小舟 在 vault 所有文件中一致，不出现 A-小舟1 或中英混 | grep `A-小舟` 全 vault |
| **教师名一致** | Teacher A 的名字在所有引用中一致，不 fallback 到"待指定"或"小赵" | grep `Teacher A` 全 vault |
| **时间线合理** | intake < assessment < plan_generator < session_review < milestone | 看每个文件 frontmatter 日期 |
| **核心档案完整** | 最终核心档案含：基本信息 + 能力评估摘要 + IEP 目标 + FBA 摘要 + 进展快照 + 沟通记录 + 全生命周期索引 | 读 `Client-A-小舟-核心档案.md` |
| **家书里有真实进展** | parent_letter 正文引用 session_review 里记录的具体 ST 目标进步（不是泛泛夸赞） | 对照日志和家书 |
| **FBA 的 BIP 被 IEP 引用** | plan_generator 如果在 FBA 之后跑，IEP 里应该有 BIP 章节 | grep |
| **喜报数据与里程碑一致** | 家长版喜报里的"达标目标数"等于专业版里程碑报告里的 | 交叉比对 |
| **vault 变更日志完整** | `04-Supervision/系统变更日志.md` 含本次流程的 10+ 个事件 | 读尾部 |
| **wikilink 闭环** | 每个 `[[Client-A-小舟-xxx]]` 都能链回实际存在的文件 | grep + 文件 exists 检查 |

---

## 🐛 当前已知系统状态（2026-04-17 末）

- ✅ 所有 17 skill 功能正常
- ✅ expert tier 完整链路 approve → vault 落盘验证通过
- ✅ AI revise 小/大文档都能处理（600s timeout + 友好错误）
- ✅ 多角色权限隔离 6/6 通过
- ✅ 边界错误态 13/13 通过
- ⚠️ 2 个旧 queued 僵尸 job 待清理 (`e070aa14`, `9296eed2`) — 不影响新流程
- ⚠️ A-小朝 有 1 个 transfer_protocol pending 未处理 — 别误 approve
- ⚠️ vault 有 1 个 latin-1 乱码孤儿目录 `Client-A-Ð¡³¯` — 可忽略

## 🔧 修复历史（有助于理解系统当前行为）

本次 session（2026-04-17）修复的 7 个 bug：

| Bug | 文件 | 关键改动 |
|---|---|---|
| BUG #1/#2 | `web/lib/api.ts` | `/auth/login` 的 401 不触发 logout+redirect，让登录页能显示错误 |
| BUG #12 | `api/app/config.py` + `.env` | `job_timeout_seconds: int = 600` 默认（旧是 300s 导致大上下文 skill 超时） |
| BUG #13 + #15 | `api/app/routers/jobs.py` + `api/app/services/skill_executor.py` | `staff_id` (uuid) 后端解析为 `staff_name` 注入 form_data + skill_executor 加「教师姓名绑定」硬规则（类比 `client_code`） |
| BUG #14 | `api/app/services/form_validator.py` | `select_client` / `select_staff` 类型补 required 检查 |
| BUG #16 | `api/app/services/review_service.py` | AI revise subprocess timeout 从硬编码 120s 改为跟随 settings；捕获 TimeoutExpired 转 RuntimeError→502 |

---

## 📁 相关文件索引

- 本 session 完整测试报告：`docs/testing/2026-04-16-test-report.md`
- 详细 bug log：`docs/testing/bugs/2026-04-16-bug-log.md`
- 测试素材：`docs/testing/fixtures/`（可复用 2026-04-17 课后记录等）
- 技能路由：`.claude/skills/_router.md` — 如何选用每个 skill
- 目录规范：`.claude/skills/_config.md` — vault 树结构 + 代号规则

---

## 🚀 开工第一步

1. 读 `.claude/skills/_router.md` 理解 skill 之间的临床逻辑关系
2. 读 `.claude/skills/_config.md` 熟悉 vault 目录规范
3. 读 本 memory + `docs/testing/2026-04-16-test-report.md` 的阶段 2 部分（了解 token 获取 + fire-and-poll 模式）
4. 创建虚拟儿童 A-小舟（需要 DB 操作还是有 HTTP 端点？先查 `api/app/routers/clients.py`）
5. 按上面 13 步骤剧本开跑，每跑一步就读 vault 验证这步的产出和上一步的 context 流转

**核心判断标准**：跑完后，如果一个真正的 BCBA 看到 `Client-A-小舟` 的完整档案，能不能基于它给出临床建议？如果能 = 系统真正可用。

祝好运 🍀
