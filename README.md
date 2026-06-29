# 考前刷题 · Exam Practice

GitHub Pages 部署的考前刷题 PWA：纯前端、零依赖、单文件即可上线。支持多套题库切换、深浅色主题、题目导航、键盘与手势操作、进度自动保存，并可下载自包含离线版。

> 🎨 完整设计规范见 **[`docs/design-system.md`](docs/design-system.md)**（颜色 / 字体 / 组件 / 交互 / 响应式的唯一标准）。
> 🤖 项目硬性约束见 **[`CLAUDE.md`](CLAUDE.md)**。
> 🖥 后端 / 部署说明见 **[`backend/README.md`](backend/README.md)**。

## 两种运行方式

1. **本地预览（无后端）**：`index.html` 顶部 `DEMO_MODE = true`，用内置演示账号 `student / exam2026` 登录，题库读本地 `data/`。
2. **服务器部署（前后端分离）**：前端 `index.html` 放 GitHub Pages（或后端同源托管），后端 `backend/app.py`（Flask + 文件夹题库 + 登录）跑在阿里云上。把 `index.html` 顶部改成 `DEMO_MODE = false`、`API_BASE`=后端 https 地址。详见 `backend/README.md`。

> 登录后才能进入首页 / 答题 / 下载离线版；登录后可在「管理题库」页增删题库（写到服务器的 `banks/` 文件夹）。

### 🔐 隐私与安全

公开仓库里**不含任何敏感内容**：账号密码存服务器的 `backend/users.json`（已 .gitignore，代码里没有真实密码），真实题库只上传到服务器的 `backend/banks/`（已 .gitignore，仓库里只留 `demo.json` 做样例）。前端是 https，后端也必须用 https 并把 CORS 限定到你的 Pages 域名。详见 `backend/README.md` 的「隐私与安全」一节。

## 在线地址

https://raylanlin.github.io/exam-practice/

---

## 功能

- **多套题库**：首页列出所有套题，点击在线练习，并显示历史最高分与记录数。
- **三种题型**：单选、多选、填空（填空大小写 / 首尾空格不敏感，可配置多个等价答案）。
- **两种练习模式**
  - **练习模式（默认）**：作答后点「确认」立即判对错 + 正确答案 + 解析；可「显示答案」揭题参考（不计错）。
  - **考试模式**：作答时不反馈，全部完成后「提交」才出结果。
- **题目导航抽屉**：题号网格总览，按未答 / 已选 / 对 / 错配色，可一键跳题、跳到标记、直接交卷。
- **键盘 & 手势**：`1–9` 选项、`←/→` 翻题、`Enter` 确认/下一题、`F` 标记、`R` 显答案、`Esc` 关导航；题卡左右滑动切题。
- **单题标记**：`⚑` 标记存疑题，导航里高亮、可一键跳转。
- **进度自动保存**：答题状态实时存浏览器，刷新 / 退出后自动恢复（可「从头开始」）。
- **深浅色主题**：右上角一键切换，记忆选择，首次跟随系统，护眼低饱和配色。
- **分题型统计**：结果页含环形正确率仪表 + 评级，及单选 / 多选 / 填空各自正确率。
- **错题重做**：结果页一键只重做本卷错题，重做后单独出结果。
- **历史记录**：每次结果存 `localStorage`，可在套题卡「历史」里回看。
- **下载离线版**：每套卷可导出为单个自包含 HTML，离线同样支持上述全部功能（深浅色 / 导航 / 键盘 / 进度恢复 / 重做错题）。
- **多端适配**：手机竖屏、平板、桌面、横屏共用一套响应式布局，热区 ≥44px。

---

## 如何更新题目

### 1. 在 `data/` 目录下创建 / 编辑 JSON 文件

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
      "explanation": "Python 变量名不能以数字开头、不能含连字符或空格。"
    },
    {
      "id": "q2",
      "type": "multiple",
      "question": "以下哪些是 Python 内置数据类型？（多选）",
      "options": ["list", "dict", "array", "custom"],
      "answer": [0, 1],
      "explanation": "list 和 dict 是内置类型。"
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
| `q.id` | 每题唯一 ID，建议 q1 / q2 / … |
| `q.type` | `single` 单选 / `multiple` 多选 / `blank` 填空 |
| `q.options` | 选项列表（单选 / 多选需要） |
| `q.answer` | 单选 / 多选：正确选项索引数组（B 为 `[1]`） |
| `q.blanks` | 填空：每个空位的可接受答案数组（可多个等价答案）；题干用 `___` 标记空位 |
| `q.explanation` | 解析（可选） |

### 2. 注册到 `data/manifest.json`

在 `exams` 数组里加一项（`questionCount` 填 0 即可，前端会自动读取真实题数）：

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

### 3. 推送到 GitHub

```bash
git add .
git commit -m "更新题目：FIT1045 期中模拟"
git push
```

GitHub Pages 自动部署，通常 1–2 分钟生效。

---

## 项目结构

```
exam-practice/
├── index.html              # 主页面（SPA，含全部功能 + 离线版生成器）
├── data/
│   ├── manifest.json       # 题库清单
│   └── demo.json           # 演示题库（可删除）
├── docs/
│   ├── design-system.md    # 设计系统规范（唯一标准）
│   └── CHANGELOG.md         # 变更记录
├── CLAUDE.md               # 项目硬性约束
└── README.md               # 本文件
```

## 技术栈

前端零依赖单文件 `index.html`（CSS 变量 + 单份答题引擎），通过 `fetch` 调后端 API 取题库；答题记录与进度存浏览器 `localStorage`。后端 `backend/app.py` 为 Flask + 文件夹题库（一套题一个 `.json`），负责登录鉴权、题库增删、并托管前端。离线版是自包含单文件，双击即可打开。

## 本地预览

因为题库走 `fetch`，需用本地服务器（直接双击打开会被浏览器跨域拦截）：

```bash
python3 -m http.server 8000
# 然后访问 http://localhost:8000
```

离线版是自包含单文件，双击即可打开，无需服务器。
