---
name: exam-practice-filler
description: 当用户提供试卷材料（图片 / PDF / 文本 / 已有 JSON / Word / Excel / 微信聊天截图）要填充到「考前刷题」系统时使用。教 agent 规范化识别题目、转为 JSON 格式，并通过「网页管理题库」或「服务器 banks 文件夹」上线。也覆盖账号管理。
user-invocable: true
---

# Exam Practice 题目填充 Skill（前后端版）

把用户给的任何形态的「试卷 / 题库」材料，准确、规范地转成一套题库 JSON，再通过两种方式之一上线，让 https://raylanlin.github.io/exam-practice/ 登录后能刷。

> **首次使用前必读**：`CLAUDE.md`（项目硬性约束）+ `docs/design-system.md`（设计规范）+ `backend/README.md`（后端 / 部署 / 隐私）。
> 本文件覆盖「题目识别 + 题库 JSON + 上线 + 账号管理」工作流；视觉/UI 修改不归这里。

---

## 架构速览（先搞清楚数据在哪）

```
浏览器 → GitHub Pages（前端 index.html，开源、无密钥）
           ↓ 登录拿 token，带 Bearer 调 API
阿里云 nginx → Flask(backend/app.py)
           ↓ 读/写
backend/banks/*.json  ← 真实题库就在这个文件夹（每套一个文件）
backend/users.json    ← 账号密码
```

**关键变化（和旧版完全不同）：**

1. **题库不再放 `data/`、不再 git push 到 Pages**。题库是**服务器上 `backend/banks/` 文件夹里的 json 文件**。
2. **不用再手工维护 manifest**。后端扫描 `banks/` 自动生成题库清单。
3. **`data/` 只剩 `demo.json`**，是公开预览样例，别往里加真实题库（会进开源仓库、泄露）。
4. **要登录才能用**。账号在服务器 `backend/users.json`。
5. git push 只更新**前端**（Pages）；**题库 / 账号变更在服务器上即时生效**，和 git 无关。

---

## Quick map

| 位置 | 用途 | 是否修改 |
|------|------|---------|
| `backend/banks/<id>.json`（服务器）| 单套题库（题目 + 答案）| ✅ 主要 |
| 网页「管理题库」| 登录后增删题库（写到上面那个文件夹）| ✅ 首选入口 |
| `backend/users.json`（服务器）| 账号密码 | ⚠️ 改账号时 |
| `backend/app.py` | 后端逻辑 | ❌ 不要碰（除非修 bug）|
| `index.html` | 前端 SPA | ❌ 不要碰（除非修 bug）|
| `data/demo.json` / `data/manifest.json` | 公开演示样例 | ❌ 不要碰 |
| `docs/CHANGELOG.md` | 变更记录 | ⚠️ 加新功能时 |
| `CLAUDE.md` / `docs/design-system.md` | 约束 / 规范 | ❌ 不要碰 |

---

## 一、识别材料 + 提取题目（和旧版一致）

### 0. 学习通 docx 快路入口

如果用户给的是**学习通网页版导出的 docx**（最常见），直接用 `scripts/parse_xuexitong_docx.py`：

```bash
pip install python-docx
python3 scripts/parse_xuexitong_docx.py <docx> <output.json> \
  --exam-id gdufe-junshililun-2026-summer-quiz1 \
  --title "军事理论 复习题集" \
  --subject "军事理论" \
  --duration 120
```

脚本已处理学习通 docx 的所有特殊格式（章节题型分组、跨段判断题、0.0 分错题、题干末尾（）等）。输出后**必须**人工核对 0.0 分的错题（脚本会提示「接下来你需要做的」）。详见 `scripts/README.md`。

### 1. 接收材料，识别来源

| 形态 | 识别方式 |
|------|---------|
| 图片（jpg/png/webp）| `mmx vision describe` 或 vision 工具 |
| PDF | pdf 工具 |
| 纯文本 / Markdown | 直接读 |
| 已有 JSON / YAML | 解析后规范化 |
| Word（.docx）| **学习通网页版导出的** → `scripts/parse_xuexitong_docx.py` 一键转换；其他来源 → 转文本 / 转 PDF 后再读 |
| Excel / CSV | 转表格后逐题读 |
| 微信聊天截图 / 笔记截图 | vision 提取文字 |

多张图片 / 多页 PDF：**逐个读完后合并**，按题号顺序排列。

### 2. 逐题提取五个字段

1. **题干**（不含题号、保留原文标点和换行）
2. **选项**（按顺序，去掉「A.」「B.」前缀）
3. **题型**：`single` / `multiple` / `judge` / `blank`
4. **答案**：
   - 选择题 → 选项**索引**数组（**从 0 开始**）
   - 判断题（`judge`）→ **不写 `options`**；`answer:[0]`=正确、`answer:[1]`=错误（前端自动渲染「✓ 正确 / ✕ 错误」）
   - 填空题 → `[["等价1","等价2"], ...]`，每空一个数组
5. **解析**（有则保留；没有就**不写**该字段，别留空字符串）

⚠️ **绝不能猜答案**。看不清 / 用户没给的，**跳过该题**，最后报告里说明。

### 3. 题库 JSON schema

```json
{
  "id": "<slug>",
  "title": "可读标题",
  "subject": "科目",
  "examDate": "YYYY-MM-DD",
  "duration": 60,
  "description": "说明文字",
  "questions": [
    { "id": "q1", "type": "single",   "question": "题干", "options": ["选项1","选项2","选项3","选项4"], "answer": [1], "explanation": "解析（可选）" },
    { "id": "q3", "type": "multiple", "question": "题干（多选）", "options": ["A","B","C","D","E"], "answer": [0,3] },
    { "id": "q5", "type": "judge",    "question": "判断题题干（无 options）。", "answer": [0], "explanation": "[0]=正确，[1]=错误" },
    { "id": "q7", "type": "blank",    "question": "中国首都是___，有___个直辖市。", "blanks": [["北京","北京市"],["4","四个"]] }
  ]
}
```

### 4. 命名约定

| 字段 | 规则 | 示例 |
|------|------|------|
| `id` | **只能含字母数字、`-`、`_`**（后端会校验，否则拒收）；全小写连字符，`<来源>-<科目>-<学期>-<类型>` | `monash-fit1045-2026-s1-midterm` |
| `title` | 可读中文 | `Monash FIT1045 算法 2026 S1 期中模拟` |
| `q.id` | `q1`、`q2`、… 顺序连续 | `q1`, `q2`, `q15` |

`id` 同名 = **覆盖**已有题库，注意别误覆盖。

---

## 二、上线题库（二选一）

### 方式 A：网页「管理题库」（首选，最省事）

1. 打开 https://raylanlin.github.io/exam-practice/ ，用账号登录。
2. 顶栏 `＋` 或首页「管理题库」进入。
3. **粘贴整套题库 JSON**，或点「选择 .json 文件」导入。
4. 点「保存题库」→ 后端写入服务器 `banks/<id>.json`，**立即生效**，回首页即可看到新卡。
5. 删除题库：在「管理题库」列表点对应「删除」。

> 适合临时加题、用户自己操作。无需碰服务器、无需 git。

### 方式 B：直接放服务器的 banks 文件夹（批量 / agent 部署）

把生成好的 `<id>.json` 上传到服务器题库目录（默认 `backend/banks/`）：

```bash
# 本地先校验（见下），再上传。推荐 base64 + scp，避免 SSH heredoc 转义炸：
base64 -i <id>.json -o /tmp/b64.txt
scp /tmp/b64.txt root@<服务器IP>:/tmp/
ssh root@<服务器IP> 'base64 -d /tmp/b64.txt > /root/exam-practice/backend/banks/<id>.json'
# manifest 后端自动扫描，无需重启、无需改其他文件
```

> 真实题库**已 .gitignore**，不会进开源仓库（仓库里只保留 `demo.json` 样例）。

### 上线前本地校验（两种方式都要做）

```bash
# 1. JSON 合法
python3 -m json.tool <id>.json > /dev/null
# 2. 选择题答案索引不越界：max(answer) < len(options)
# 3. 判断题：answer 是 [0] 或 [1]，且无 options
# 4. 填空：blanks 长度 == 题干中 ___ 的数量
# 5. id 只含 [A-Za-z0-9_-]
```

后端保存时也会校验 `id / title / questions` 三项，不合法会报错拒收。

---

## 三、账号管理

账号在**服务器**上的 `backend/users.json`（已 .gitignore，**代码里没有真实密码**）。

```bash
# 服务器上编辑：
cd /root/exam-practice/backend
cat users.json
# 形如： { "raylan": "Raylan1234", "scarlett": "Scarlett1234" }
```

- **加 / 改 / 删账号**：编辑 `users.json`（明文，设强密码），保存后**重启服务**生效：
  ```bash
  systemctl restart exam-practice   # 或你的服务名
  ```
- 也可用环境变量替代文件：`EXAM_USERS='{"raylan":"密码"}'`（写在 systemd 的 `Environment=`）。
- 改了密码后，老 token 仍在有效期内可用（30 天）；要立即失效所有登录，删掉服务器上的 `backend/secret.key` 再重启（会重签密钥，所有人需重新登录）。
- **不要**把真实密码写进 `app.py` 或提交到仓库。

---

## 四、前端 / 后端代码改动后的部署

| 改了什么 | 怎么上线 |
|---------|---------|
| 题库内容 | 方式 A/B，**即时生效**，与 git 无关 |
| 账号密码 | 改服务器 `users.json` → `systemctl restart` |
| 前端 `index.html`（UI / 功能）| `git push` → GitHub Pages 1–2 分钟生效 |
| 后端 `app.py` | 同步到服务器 → `systemctl restart` |

> 前端顶部两个配置别动错：`DEMO_MODE=false`、`API_BASE='https://47.250.40.117.sslip.io/exam-practice/api'`。
> 本地预览前端时可临时把 `DEMO_MODE=true`（用内置演示账号、读本地 `data/`），但**别提交这个改动上线**。

---

## 五、报告模板

```
✅ 已上线：<title>（方式：网页管理 / 服务器 banks）
📊 共 N 题（单选 X / 多选 Y / 判断 W / 填空 Z）
⚠️ 跳过 / 缺答案：q5, q12（用户原卷缺答案）
🌐 登录后查看：https://raylanlin.github.io/exam-practice/
```

---

## 关键规则（容易踩坑）

1. **选项索引从 0 开始**：A=0,B=1,C=2,D=3。多选答案排序去重：`[2,0,1]`→`[0,1,2]`。
2. **填空大小写 / 首尾空格不敏感**，同一空位可多个等价答案。题干用 `___` 标记空位，数量 = `blanks.length`。
3. **判断题不写 `options`**，`answer` 只能 `[0]`（正确）或 `[1]`（错误）。
4. **`id` 唯一且只含 `[A-Za-z0-9_-]`**；同名 = 覆盖，先确认。
5. **绝不猜答案 / 不瞎凑选项数**；图片模糊就停下问用户。
6. **真实题库只进服务器，不进 `data/`、不进仓库**（开源会泄露）。
7. **不碰 `index.html` / `app.py` 的逻辑**；判分逻辑都在前端 `engine-js` 一份。
8. **commit 用中文**，且仅当改的是前端/后端代码 —— 题库变更不走 git。

---

## 失败 / 不确定的处理

| 情况 | 处理 |
|------|------|
| 图片模糊 / 截断 | 让用户重发，不瞎填 |
| 部分题没答案 | 跳过该题，报告里列出 |
| 选项数量不确定 | 按用户给的写，不凑数 |
| 同 id 已存在 | 先问用户：覆盖 / 改名 / 取消 |
| 题型判断不准 | 严格按原话；判断不了就问 |
| 网页保存报错 | 看错误提示（多半是 id 不合法 / questions 为空 / 未登录过期）|

---

## 本地预览（用户测试用）

把前端 `index.html` 顶部临时改 `DEMO_MODE=true`，再起静态服务器：

```bash
cd ~/.openclaw/workspace/projects/exam-practice
python3 -m http.server 8000   # 访问 http://localhost:8000
# 演示账号 student / exam2026，题库读本地 data/（只有 demo）
```

`file://` 会被跨域拦截，必须用本地服务器。**测试完把 `DEMO_MODE` 改回 false 再提交。**
