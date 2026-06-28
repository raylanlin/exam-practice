# 考前刷题 · Exam Practice

GitHub Pages 部署的考前刷题 PWA，支持多套题库切换 + 下载离线试卷。

## 功能

- **多套题库**：首页展示所有套题，点击即可在线练习
- **三种题型**：单选、多选、填空
- **两种练习模式**：
  - **练习模式**（默认）：答完一题立即显示对错 + 正确答案 + 解析；点击「显示答案」可揭题查看参考答案（不计入答错）
  - **考试模式**：不显示反馈，全部答完才看结果
- **分题型统计**：结果页除了总正确率，还展示单选/多选/填空各自的正确率（绿色=≥80%、红色=<60%）
- **错题重做**：结果页一键「重做错题」，只加载上次的错题（橙色 banner 提示），重做完同样有详细结果
- **历史记录**：每次练习结果保存在浏览器 localStorage，含每题答题详情
- **下载离线版**：每套试卷可下载为独立 HTML 文件，离线也能刷（同样支持两种模式 + 即时反馈）
- **双人共用**：同一链接 Raylan 和咪大王都能用，历史各存各的浏览器

## 在线地址

https://raylanlin.github.io/exam-practice/

## 如何更新题目

### 1. 在 `data/` 目录下创建/编辑 JSON 文件

每套题一个 JSON 文件，格式：

```json
{
  "id": "monash-fit1045-midterm-2026-s1",
  "title": "FIT1045 期中模拟",
  "subject": "FIT1045",
  "examDate": "2026-07-15",
  "duration": 60,
  "description": "Monash FIT1045 期中模拟卷，覆盖前 4 周内容",
  "questions": [
    {
      "id": "q1",
      "type": "single",
      "question": "以下哪个是合法的 Python 变量名？",
      "options": ["2var", "_var", "var-name", "var name"],
      "answer": [1],
      "explanation": "Python 变量名不能以数字开头（排除 A），不能包含连字符（C）或空格（D）。"
    },
    {
      "id": "q2",
      "type": "multiple",
      "question": "以下哪些是 Python 内置数据类型？（多选）",
      "options": ["list", "dict", "array", "custom"],
      "answer": [0, 1],
      "explanation": "list 和 dict 是内置类型；array 需要 import array 模块；custom 不是类型。"
    },
    {
      "id": "q3",
      "type": "blank",
      "question": "Python 中定义函数使用关键字___，打印输出使用函数___。",
      "blanks": [["def"], ["print"]],
      "explanation": "def 定义函数，print 打印输出。"
    }
  ]
}
```

**字段说明：**

| 字段 | 说明 |
|------|------|
| `id` | 唯一 ID，不要和已有的重复 |
| `title` | 标题，显示在卡片上 |
| `subject` | 科目名（可选） |
| `examDate` | 考试日期（可选），传空字符串就行 |
| `duration` | 建议时长（分钟，可选） |
| `description` | 简短说明 |
| `questions` | 题目数组 |
| `q.id` | 每题唯一 ID，建议 q1/q2/... |
| `q.type` | `single` 单选 / `multiple` 多选 / `blank` 填空 |
| `q.options` | 选项列表，只有单选/多选需要 |
| `q.answer` | **单选/多选**：选项索引数组（如单选正确答案是 B 则 `[1]`） |
| `q.blanks` | **填空**：每个位置的接受答案数组（可接受多个等价答案） |
| `q.explanation` | 解析（可选） |

### 2. 注册到 `data/manifest.json`

在 `manifest.json` 的 `exams` 数组里加一项：

```json
{
  "id": "monash-fit1045-midterm-2026-s1",
  "file": "fit1045-midterm.json",
  "title": "FIT1045 期中模拟",
  "subject": "FIT1045",
  "examDate": "2026-07-15",
  "duration": 60,
  "questionCount": 0,
  "description": "Monash FIT1045 期中模拟卷"
}
```

> `questionCount` 填 0 就行，前端会自动读取显示。

### 3. 推送到 GitHub

```bash
cd ~/.openclaw/workspace/projects/exam-practice
git add .
git commit -m "更新题目：FIT1045 期中模拟"
git push
```

GitHub Pages 自动部署，通常 1-2 分钟生效。

## 项目结构

```
exam-practice/
├── index.html          # 主页面（SPA，包含所有功能）
├── data/
│   ├── manifest.json   # 题库清单
│   └── demo.json       # 演示题库（可删除）
└── README.md           # 本文件
```

## 技术栈

纯前端，零依赖。数据存在 `data/` 目录的 JSON 文件里，答题记录存浏览器 localStorage。离线版本用 JS 动态生成自包含 HTML。
