---
name: exam-practice-filler
description: 当 Raylan 或咪大王提供试卷材料（图片 / PDF / 文本 / 已有 JSON / Word / Excel / 微信聊天截图）要填充到「考前刷题」系统时使用。教 agent 规范化识别题目、转为 JSON 格式、注册到题库、推送部署上线。
user-invocable: true
---

# Exam Practice 题目填充 Skill

把用户给的任何形态的「试卷 / 题库」材料，准确、规范地填进 `data/<exam-id>.json`，注册到 `data/manifest.json`，让网页 https://raylanlin.github.io/exam-practice/ 立刻能刷。

> **首次使用前必读**：`CLAUDE.md`（项目硬性约束）+ `docs/design-system.md`（设计规范）。
> 本文件只覆盖「题库填充 + 仓库操作」工作流；视觉/UI 修改不归这里。

---

## Quick map

| 文件 | 用途 | 是否修改 |
|------|------|---------|
| `data/<exam-id>.json` | 单套题库（题目 + 答案） | ✅ 主要 |
| `data/manifest.json` | 题库清单（首页展示） | ✅ 加新 exam |
| `data/demo.json` | 演示卷 | ❌ 不要碰 |
| `index.html` | 主页 SPA | ❌ 不要碰（除非修 bug） |
| `docs/CHANGELOG.md` | 变更记录 | ⚠️ 加新功能时 |
| `docs/design-system.md` | 设计规范 | ❌ 不要碰 |
| `CLAUDE.md` | 硬性约束 | ❌ 不要碰 |
| `README.md` | 用户文档 | ⚠️ 必要时更新题库说明 |

---

## 工作流程（严格按顺序）

### 1. 接收材料，识别来源

可能的输入：

| 形态 | 识别方式 |
|------|---------|
| 图片（jpg/png/webp）| `mmx vision describe` 或 OpenClaw `image` 工具 |
| PDF | OpenClaw `pdf` 工具 |
| 纯文本 / Markdown | 直接读 |
| 已有 JSON / YAML | 解析后规范化 |
| Word（.docx）| 转文本 / 转 PDF 后再读 |
| Excel / CSV | 转表格后逐题读 |
| 微信聊天截图 / 笔记截图 | `mmx vision describe` 提取文字 |

如果多张图片 / 多页 PDF，**逐个读完后合并**，按题号顺序排列。

### 2. 逐题提取

对每一道题，提取这五个字段：

1. **题干**（不含题号、保留原文标点和换行）
2. **选项**（A/B/C/D...，按顺序，去掉前缀「A.」「B.」等保留字母）
3. **题型**：`single` / `multiple` / `blank`
4. **答案**：
   - 选择题 → 转成选项**索引**数组（**从 0 开始**）
   - 填空题 → `[["等价1", "等价2"], ...]`，每个空位一个数组
5. **解析**（如有则保留；没有就**留空不写**字段）

⚠️ **绝不能猜答案**。看不清楚、用户没给的，**跳过该题**，在最后报告里告诉用户哪些题缺答案。

### 3. 生成 `data/<exam-id>.json`

完整 schema：

```json
{
  "id": "<slug>",
  "title": "可读标题",
  "subject": "科目",
  "examDate": "YYYY-MM-DD",
  "duration": 60,
  "description": "说明文字",
  "questions": [
    {
      "id": "q1",
      "type": "single",
      "question": "题干",
      "options": ["选项1", "选项2", "选项3", "选项4"],
      "answer": [1],
      "explanation": "解析（可选）"
    },
    {
      "id": "q3",
      "type": "multiple",
      "question": "题干（多选）",
      "options": ["A", "B", "C", "D", "E"],
      "answer": [0, 3],
      "explanation": "解析（可选）"
    },
    {
      "id": "q5",
      "type": "blank",
      "question": "中国首都是___，有___个直辖市。",
      "blanks": [["北京", "北京市"], ["4", "四个"]],
      "explanation": "解析（可选）"
    }
  ]
}
```

### 4. 命名约定（重要）

| 字段 | 规则 | 示例 |
|------|------|------|
| `id` | 全小写连字符，`<来源>-<科目>-<学期>-<类型>` | `monash-fit1045-2026-s1-midterm` |
| `file` | 与 id 同名 + `.json` | `monash-fit1045-2026-s1-midterm.json` |
| `title` | 可读中文 | `Monash FIT1045 算法与数据结构 2026 S1 期中模拟` |
| `q.id` | `q1`、`q2`、...，题号顺序连续 | `q1`, `q2`, `q15` |

如果用户给的是「咪大王某次小测」，建议命名：`gdufe-<科目>-<日期>-<类型>`，例如 `gdufe-jicheng-2026-06-15-quiz`。

### 5. 注册到 `data/manifest.json`

在 `exams` 数组里加一项，**`questionCount` 写 0**（前端会自动读真实题数）：

```json
{
  "id": "<slug>",
  "file": "<id>.json",
  "title": "可读标题",
  "subject": "科目",
  "examDate": "YYYY-MM-DD",
  "duration": 60,
  "questionCount": 0,
  "description": "说明"
}
```

放在数组**末尾**（保持历史顺序）。

### 6. 提交前校验（必做）

```bash
# 1. JSON 合法
python3 -m json.tool data/<id>.json > /dev/null

# 2. 答案索引未越界（手动或脚本）
# 对每个选择题：max(answer) < len(options)

# 3. 填空 blanks 长度 = 题干中 ___ 数量
# 用 grep 验证

# 4. manifest 中无重复 id
python3 -c "
import json
m = json.load(open('data/manifest.json'))
ids = [e['id'] for e in m['exams']]
assert len(ids) == len(set(ids)), 'duplicate id in manifest'
print('manifest OK,', len(ids), 'exams')
"
```

### 7. 部署

```bash
cd ~/.openclaw/workspace/projects/exam-practice
git add data/
git commit -m "新增题库：<title>"
git push
```

GitHub Pages 通常 1–2 分钟生效。完成后**必须**访问 https://raylanlin.github.io/exam-practice/ 验证：
- [ ] 新题卡出现在首页
- [ ] 题数正确
- [ ] 选 1-2 题验证判分逻辑（特别是多选 + 填空）

### 8. 报告

完成后给用户一个简短清单：

```
✅ 已部署：<title>
📊 共 N 题（单选 X / 多选 Y / 填空 Z）
⚠️ 跳过 / 缺答案：q5, q12（用户原卷缺答案）
🌐 https://raylanlin.github.io/exam-practice/
```

---

## 关键规则（容易踩坑）

1. **选项索引从 0 开始**：A=0, B=1, C=2, D=3。多选答案要排序去重：`[2, 0, 1]` → `[0, 1, 2]`。
2. **填空大小写不敏感、首尾空格忽略**：用户答案写「Beijing」也算对「beijing」。同一空位可写多个等价答案。
3. **填空题题干用 `___` 标记空位**：每个 `___` 对应 `blanks` 数组中的一项。如果一道题有 3 个空，`blanks.length === 3`。
4. **id 全小写、连字符分隔、唯一**。注册前先查 manifest 是否已存在。
5. **不要碰 `index.html`**。所有判分逻辑都在那里，**JSON 数据不要写死在 HTML**。
6. **commit 信息用中文**：`新增题库：FIT1045 期中` / `修正 q3 答案` / `更新题数说明`。
7. **不修改其他考试卷**：如果你在更新 `monash-fit1014` 的题库，不要碰 `data/demo.json`。
8. **图片模糊时停下来问用户**：不要靠模型猜测。

---

## 失败 / 不确定的处理

| 情况 | 处理 |
|------|------|
| 用户给的图片模糊 / 截断 | 让用户重发，不要瞎填 |
| 部分题没答案（用户原卷就缺） | `answer` 留 `[]` 或在 description 注明「第 X-X 题答案待补」 |
| 选项数量不确定（如多选可能是 2/3/4/5 个） | 按用户给的写，不要自作主张凑数 |
| manifest 已有同 id | 先问用户：覆盖 / 改名 / 取消 |
| 解析缺失 | 不写 `explanation` 字段，不要留空字符串 |
| 题型判断不准（如「下列哪个」其实是多选） | 严格按用户原话判断，无法判断就问 |

---

## 完整示例

**用户输入：** 咪大王发来一张小测截图，标题「数字逻辑 第3章 小测」，共 10 题，前 5 题单选，后 5 题多选，答案写在题目下方。

**Agent 流程：**

1. `mmx vision describe --image xxx.png` → 提取所有题干 + 选项 + 答案
2. 命名 `id = gdufe-shuzhiluoji-ch3-2026-quiz`，`file = gdufe-shuzhiluoji-ch3-2026-quiz.json`
3. 写 `data/gdufe-shuzhiluoji-ch3-2026-quiz.json`（10 道题）
4. 更新 `data/manifest.json`，加一项
5. 校验：JSON 合法、索引未越界、manifest 无重复
6. `git add + commit + push`
7. 访问网页验证
8. 报告给咪大王

---

## 本地预览（用户测试用）

```bash
cd ~/.openclaw/workspace/projects/exam-practice
python3 -m http.server 8000
# 访问 http://localhost:8000
```

注意：`file://` 协议会被浏览器跨域拦截，`fetch('./data/manifest.json')` 失败。