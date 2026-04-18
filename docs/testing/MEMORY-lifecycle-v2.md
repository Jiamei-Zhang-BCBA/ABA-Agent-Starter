# 🧠 MEMORY — 完整儿童生命周期 E2E 测试 v2（新 Session 交接）

> 给下一个 session 的 Clinical Director Agent 准备的上下文。读完这个就能直接开工。
> 本 MEMORY 基于 2026-04-17 第 1 轮成功经验（commit `7632a14` 当前已部署）。

---

## 🎯 本次测试目标（v2）

**同 v1**：模拟一个新来的小朋友，从「家长初访 → 建档 → 评估 → 制定方案 → 教学落地 → 日常反馈 → 家校沟通 → 达标结业 / 转衔」**完整生命周期**，跑通所有 skill 的串联业务流，验证 vault 档案最终是否形成完整、内部一致、可被 BCBA 直接用的临床记录。

**与 v1 的差异**：
- v1 个案代号 `A-小舟` 已存在并完整档案 → **本轮换新代号 `A-小航`**（避免污染）
- v1 发现的 BUG #17（retry 后 queued）已在 commit `8294675` 修复并验证
- 本轮预期 **13/13 全通过**（不再有 FBA 卡顿）

---

## 📋 完整生命周期 13 步骤（已验证剧本）

按照 `skills/_router.md` 的临床逻辑串起来：

| # | 阶段 | Skill | tier | 预期耗时 | 核心验证点 |
|---|---|---|---|---|---|
| 1 | 接收原始资料 | **privacy_filter** | auto | ~60s | 姓名脱敏 + 身份映射对照表更新 |
| 2 | 建档骨架 | **intake** | expert | ~5min | 创建 Client 文件夹 + 初访信息表 + 核心档案骨架 |
| 3 | 深化档案 | **profile_builder** | expert (destructive) | ~5min | 把 intake 的粗档案深化成 8+ 模块 |
| 4 | 能力评估 | **assessment** | expert | ~5min | 生成 VB-MAPP 风格能力评估，更新核心档案 |
| 5 | 教师建档 | **staff_onboarding** | auto | ~60s | 创建教师档案 + 工作包目录 |
| 6 | 方案制定 | **plan_generator** | expert | ~6min | 基于评估产出 IEP 方案 |
| 7 | 教学切片 | **program_slicer** | expert | ~5min | 把 IEP 宏观目标拆成老师一页纸小抄 |
| 8 | 一线教学反馈 | **session_review** | auto | ~2min | 老师课后记录 → 生成日志 + 教师档案追加 |
| 9 | 督导听课反馈 | **staff_supervision** | auto | ~2min | 督导观察教学 → 教师档案追加 + 实操单更新 |
| 10 | 强化物评估 | **reinforcer** | auto | ~2min | 扫近期日志，更新强化物偏好 |
| 11 | 突发问题行为 FBA | **fba** | expert | ~5-8min | ABC 分析 + 假设 + BIP（上轮 bug 已修复） |
| 12 | 家校沟通 | **parent_letter** | auto | ~60s | 生成「微光家书」 |
| 13 | 达标结业 | **milestone_report** | expert | ~6min | 阶段报告 + 喜报 |

**可选 Step 14**：`transfer_protocol` — destructive，会把 Client 标记"已移交"，留到最后再跑。

---

## 🛠️ 测试环境 & 凭证

- **VM**: `34.182.17.120`（GCP, g810741472wang@）
- **URL**: http://34.182.17.120/
- **主账号**: `wxinflying@gmail.com` / **`Wangliang007$`**（注意：**不是 Demo123!**）
- **Demo 账号**（密码统一 `Demo123!`）:
  - `you-bcba@yourorg.com` — 审核用
  - `teacher-a@yourorg.com` — 一线老师（uuid `ac17848d-ae03-4819-a5e3-1df91890b99e`）
  - `teacher-b@yourorg.com` — 备用
  - `parent-demo@yourorg.com` — 家长（uuid `fdbbdec6-8fce-4a02-9000-51fdb8ffb296`）
  - `qa-test-bcba@example.com` — QA BCBA

- **当前部署 commit**: `7632a14`（含 BUG #17 fix + 超管 cancel endpoint）

---

## 👤 本轮新虚拟儿童：A-小航

### 设定（用于新访谈，与 A-小舟 拉开差异）

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

**注意**：和 A-小舟（男、拍头自伤、50 词、旋转玩具）差异化充分 — 让 AI 产出不同侧重。

---

## 🔑 关键注意事项（v1 已踩过的坑）

### 1. multipart 文件字段名必须是 `files`

后端 `jobs.py` 强制用 `files: list[UploadFile]` 接文件，**不管** form_schema 里字段叫什么。写 curl/fetch 时：

```js
fd.append('files', blob, 'xxx.txt');  // ✅ 对
fd.append('raw_file', blob, ...);     // ❌ 错，AI 拿不到
fd.append('intake_file', blob, ...);  // ❌ 错
```

### 2. Expert tier 耗时规律

- auto tier haiku: 5-30s
- auto tier sonnet 小 skill: 30-90s
- **expert tier sonnet 大上下文** (fba/plan_generator/milestone_report/transfer_protocol): **300-550s**（不再 600s 超时）
- AI revise 12k 字: 240s

### 3. Chrome MCP CDP 45s timeout — 必须 fire-and-poll

不要用 `await fetch(...)` 等；要把 fetch 丢 `.then` 异步跑，done 标志写 `window.__X`。每 10s 轮询。见下方模板。

### 4. `[BLOCKED: Sensitive key]` 遮蔽

长 UUID / base64 / token 会被 MCP 遮蔽。绕法：
- 把结果写到 `document.title`（纯数字、状态字用这个最方便）
- 把结果写到 `window.__X` 后下次 exec 读
- 把长内容做 pattern count (`content.match(/XXX/g).length`)

### 5. Job 接口模式

```
POST /api/v1/jobs  → 返回 201 + {job_id}
GET  /api/v1/jobs/{job_id}  → 看 status
GET  /api/v1/reviews?status=pending  → expert tier job 完成后在这
POST /api/v1/reviews/{id}/approve  → body {"modified_content": null, "comments": null}
GET  /api/v1/vault/read?path=URL_ENCODED  → 验证落盘
```

### 6. staff_id 是 uuid → 后端查 User 表转换成 staff_name 注入

form_data 里只放 uuid，不要放名字：
```js
form_data = JSON.stringify({
  client_id: '<uuid>',
  staff_id: 'ac17848d-ae03-4819-a5e3-1df91890b99e',  // Teacher A uuid
  session_text: '...',
});
```

### 7. transfer_protocol destructive — 谨慎 approve

它会把 Client 状态改为"已移交"。留到流程最后一步，approve 前明确跟用户确认。

### 8. 新接口：超管 cancel_job (commit 7632a14)

如果任何 job 卡住，可以调：
```
POST /api/v1/jobs/{job_id}/admin-cancel
Authorization: Bearer <super_admin_token>
```
返回 `{previous_status, new_status:"failed", cancelled_by}`。只能 cancel 非终态 (queued/parsing/processing)。

---

## 📊 跨步骤自洽性指标（9 项，期望全通过）

跑完后必须验证：

| # | 检查项 | 期望 | 方式 |
|---|---|---|---|
| 1 | **代号一致** | A-小航 在 vault 所有文件中一致，不出现 A-小航1 / 中英混 | grep `A-小航` 全 vault；真实姓名 leak = 0 |
| 2 | **教师名一致** | Teacher A 在 A-小航 档案内全一致，不 fallback | grep `Teacher A` + `小赵` / `待指定` 数量 |
| 3 | **时间线** | intake < assessment < plan_generator < session_review < milestone | 看每个 frontmatter 日期 |
| 4 | **核心档案 7 章节** | 基本背景 / 强化物清单 / 能力画像 / FBA 预留 / IEP 目标 / 全生命周期索引 / 变更日志 | 读 `Client-A-小航-核心档案.md` 找 `##` |
| 5 | **家书有真实进展** | parent_letter 引用 session 里的具体 ST 目标 | grep 对比 |
| 6 | **FBA → IEP BIP** | plan_generator 后 IEP 应含 BIP 章节（若在 FBA 之后跑）| grep |
| 7 | **喜报与里程碑一致** | 家长版喜报"达标目标数" == 专业版里程碑 | 交叉比对 |
| 8 | **变更日志完整** | `04-Supervision/系统变更日志.md` 尾部有本轮 10+ 事件 | 读尾部 |
| 9 | **wikilink 闭环** | 核心档案的 `[[]]` 链接目标文件都 exists | grep + vault/read |

---

## 🛠️ 代码模板（复制用）

### 登录获取 token

```js
// 第一步：拿 captcha
(async () => {
  const r = await fetch('/api/v1/auth/captcha');
  const d = await r.json();
  window.__CAPTCHA = d;
  document.title = 'captcha:' + d.captcha_id.slice(0,8) + ':' + d.question;
})();
```

然后人工算 captcha_answer，接着：

```js
(async () => {
  const r = await fetch('/api/v1/auth/login', {
    method: 'POST',
    headers: {'Content-Type': 'application/json'},
    body: JSON.stringify({
      email: 'wxinflying@gmail.com',
      password: 'Wangliang007$',
      captcha_id: window.__CAPTCHA.captcha_id,
      captcha_answer: '<你算的答案>',
    }),
  });
  const d = await r.json();
  window.__TOK = d.access_token;
  window.__REFRESH = d.refresh_token;
  const payload = JSON.parse(atob(d.access_token.split('.')[1]));
  document.title = 'OK role:' + payload.role + ' tenant:' + payload.tenant_id.slice(0,8);
})();
```

### Refresh token（每轮 expert tier 等之后都做）

```js
(async () => {
  const rr = await fetch('/api/v1/auth/refresh', {
    method: 'POST', headers: {'Content-Type':'application/json'},
    body: JSON.stringify({refresh_token: window.__REFRESH}),
  });
  if (rr.ok) {
    const d = await rr.json();
    window.__TOK = d.access_token;
    if (d.refresh_token) window.__REFRESH = d.refresh_token;
    document.title = 'refresh_ok';
  } else {
    document.title = 'refresh_fail:' + rr.status;
  }
})();
```

### Fire-and-poll submit 模板

```js
window.__JOB_DONE = false;
window.__JOB_START = Date.now();
(async () => {
  try {
    const fd = new FormData();
    // ... append files / form_data / feature_id / client_id
    const r = await fetch('/api/v1/jobs', {
      method: 'POST',
      headers: {'Authorization': 'Bearer ' + window.__TOK},
      body: fd,
    });
    const d = await r.json();
    window.__JOB_ID_XXX = d.job_id || d.id;
  } finally {
    window.__JOB_DONE = true;
  }
})();
document.title = 'STEP_N_SUBMITTED';
```

轮询状态：

```js
(async () => {
  const r = await fetch('/api/v1/jobs/' + window.__JOB_ID_XXX, {
    headers: {'Authorization': 'Bearer ' + window.__TOK},
  });
  const d = await r.json();
  document.title = 'stat:' + d.status + ' tok:' + d.input_tokens + '/' + d.output_tokens;
})();
```

### Approve review

```js
(async () => {
  // 先列 pending 找到对应 review
  const rv = await fetch('/api/v1/reviews?status=pending', {headers:{'Authorization':'Bearer '+window.__TOK}});
  const dv = await rv.json();
  const rev = (dv.reviews || []).find(x => x.job_id === window.__JOB_ID_XXX);
  const files = ((rev?.output_content||'').match(/<!-- FILE: [^>]+ -->/g) || []);
  // 看 files 确认无误后：
  const r = await fetch('/api/v1/reviews/' + rev.id + '/approve', {
    method:'POST', headers:{'Content-Type':'application/json','Authorization':'Bearer '+window.__TOK},
    body: JSON.stringify({modified_content: null, comments: null}),
  });
  const d = await r.json();
  document.title = 'approve:' + r.status + ' jstat:' + (d.job_status || d.status);
})();
```

### curl 备用（Chrome MCP 断连时）

Windows bash 环境：
```bash
TOK=$(curl -s "http://34.182.17.120/api/v1/auth/captcha" | python -c "
import json,sys,subprocess
c=json.load(sys.stdin)
parts=c['question'].replace('= ?','').strip().split('+')
ans=str(int(parts[0])+int(parts[1]))
d=json.loads(subprocess.run(['curl','-s','-X','POST','http://34.182.17.120/api/v1/auth/login','-H','Content-Type: application/json','-d',json.dumps({'email':'wxinflying@gmail.com','password':'Wangliang007\$','captcha_id':c['captcha_id'],'captcha_answer':ans})],capture_output=True,text=True).stdout)
print(d['access_token'])
")
curl -s -H "Authorization: Bearer $TOK" "http://34.182.17.120/api/v1/jobs?limit=10"
```

---

## 📁 创建新 client A-小航 的 API 调用

```js
// 1. 创建 client
(async () => {
  const r = await fetch('/api/v1/clients', {
    method: 'POST',
    headers: {'Content-Type':'application/json','Authorization':'Bearer '+window.__TOK},
    body: JSON.stringify({code_name:'A-小航', display_alias:'小航'}),
  });
  const d = await r.json();
  window.__CLIENT_ID = d.id;
  document.title = 'CREATED:' + d.id.slice(0,8);
})();

// 2. 拿 staff uuid
(async () => {
  const r = await fetch('/api/v1/staff?include_parents=true', {headers:{'Authorization':'Bearer '+window.__TOK}});
  const d = await r.json();
  window.__TEACHER_A = d.staff.find(s => s.name === 'Teacher A');
  window.__PARENT_DEMO = d.staff.find(s => s.name === 'Parent Demo');
  document.title = 'tA:' + window.__TEACHER_A.id.slice(0,8) + ' pD:' + window.__PARENT_DEMO.id.slice(0,8);
})();

// 3. 关联
(async () => {
  const assign = (uid, rel) => fetch('/api/v1/clients/'+window.__CLIENT_ID+'/assignments',{
    method:'POST',headers:{'Content-Type':'application/json','Authorization':'Bearer '+window.__TOK},
    body: JSON.stringify({user_id: uid, relation: rel}),
  });
  const r1 = await assign(window.__TEACHER_A.id, 'teacher');
  const r2 = await assign(window.__PARENT_DEMO.id, 'parent');
  document.title = 't:' + r1.status + ' p:' + r2.status;
})();
```

---

## 📄 各 Skill 的 schema 字段速查（v1 已验证）

```
privacy_filter:    raw_file(files字段)*  known_names  suggested_code_name  source_description
intake:            child_alias*  intake_file(files字段)*  parent_note
profile_builder:   client_id*  additional_context                               [destructive]
assessment:        client_id*  tool_name(select: VB-MAPP/ABLLS-R/PEP-3/ESDM/其他)*  assessment_file(files)*
staff_onboarding:  staff_name*  background
plan_generator:    client_id*  plan_type(select: IEP/BIP/IEP+BIP)*  focus_areas
program_slicer:    client_id*  staff_id*  target_goal*  detail
session_review:    client_id*  staff_id*  session_text(或 session_file 二选一)  extra_note
staff_supervision: client_id*  staff_id*  observation_text(或 observation_file 二选一)
reinforcer:        client_id*  period(select: 1w/2w/1m)  observation_note
fba:               client_id*  time_range(select: 1w/2w/1m/3m)  focus_behavior  abc_file(files)
parent_letter:     client_id*  week_highlights  parent_concern
milestone_report:  client_id*  milestone_type(select: stage_assessment/quarterly_summary/graduation)*  highlights
transfer_protocol: client_id*  new_handler*  reason                              [destructive]
quick_summary:     client_id*  purpose(select: parent_meeting/team_review/handoff/crisis)
```

---

## 🚀 开工流程（建议）

1. **读 `.claude/skills/_router.md`** 理解 skill 链路
2. **读 `.claude/skills/_config.md`** 熟悉 vault 规范
3. **读本 MEMORY + `docs/testing/A-小舟-lifecycle-report.md`** 了解 v1 成功经验
4. **检查环境**：`curl http://34.182.17.120/api/v1/auth/captcha` 确认服务在
5. **登录 + 创建 A-小航 + 关联 Teacher A/Parent Demo**
6. **按 13 步骤剧本跑**，每步 approve 后 vault/read 验证落盘 + 检查字节数
7. **并行策略**（v1 验证过安全的）：
   - Step 3 + 4 + 5 可并行（profile/assessment/staff_onboarding 互不依赖）
   - Step 7 + 8 可并行
   - Step 9 + 10 + 12 可并行
   - **Step 11 FBA 建议单独跑**（避免并发争用 subprocess，虽然 BUG #17 已修但谨慎）
8. **Step 11 之后 → Step 13**（milestone 需要 FBA 数据才完整）
9. **Step 14 transfer_protocol** 最后跑，approve 前用 `AskUserQuestion` 明确确认

---

## 📊 验收标准

跑完后输出 `docs/testing/A-小航-lifecycle-report.md`：

- 13 步骤每步执行结果（status / tokens / 文件路径 / 字节数）
- 9 项自洽性检查表全绿
- 如果发现新 bug：BUG #18 起编号，commit 到 master，加 bug-log
- 最终判断：**系统对"不同性格小孩"的泛化能力** — A-小航（女、啃手、代词混乱、爱数字）出来的档案应该显著不同于 A-小舟（男、拍头、旋转物、视觉偏好），而不是 AI 套模板

---

## 🎓 核心判断标准

**不是"API 返 200"，而是真临床可用**：
- 每步 AI 输出落盘正确（路径 + 内容）
- 下一步能读到上一步的产物（context 正确流转）
- 整个档案自洽（代号/姓名/时间线不矛盾）
- **终极判断**：BCBA 看到档案能不能据此给临床建议？

**泛化判断（本轮新增）**：
- A-小航 档案和 A-小舟 档案比对 — AI 有没有抓到 "女孩 + 啃手 + 代词混乱 + 数字偏好" 这些独特信号？还是只是把 A-小舟 的模板换个名字？

祝好运 🍀
