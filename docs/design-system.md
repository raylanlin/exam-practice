# 考前刷题 · 设计系统（Claude Design System）

> 本文件是「考前刷题」项目的唯一设计规范来源（single source of truth）。
> 所有页面、离线版、未来新增功能都必须遵循这里定义的 token、组件与交互模式。
> 实现位于 `index.html` 的 `<style id="app-css">`（CSS 变量）与 `<script id="engine-js">`（答题引擎）。

---

## 1. 设计原则

1. **护眼优先（Calm & low-strain）**：不用纯黑纯白、不用高饱和色。浅色是中性灰白、深色是石墨深灰，主色是清亮翠绿（emerald）。长时间刷题不刺眼。页面底加极淡网点纹理 + 顶部柔光，避免单调。
2. **零依赖、单文件可部署**：纯前端，`index.html` 一个文件即可部署到 GitHub Pages；题库走 `data/*.json`。不引入框架、构建步骤或外部 CSS/JS。
3. **答题流为中心**：界面服务于「读题 → 作答 → 反馈 → 下一题」。装饰元素最少，信息密度克制。
4. **多端一致**：手机竖屏、平板、桌面、横屏共用同一套布局规则，靠断点和吸顶栏适配，而非另写页面。
5. **键盘 / 触控 / 鼠标平权**：每个核心操作都同时支持点击、键盘、手势。
6. **深浅色手动可切**：主题是用户的明确选择，记忆在 `localStorage`，首次跟随系统。

---

## 2. 颜色 Token

颜色全部以 CSS 变量定义在 `:root`（浅色）与 `[data-theme="dark"]`（深色）。**禁止在组件里写死十六进制色值**，一律引用变量。

### 2.1 浅色（Light，默认）

| Token | 值 | 用途 |
|---|---|---|
| `--bg` | `#f4f5f7` | 页面底色（中性灰白） |
| `--surface` | `#ffffff` | 卡片 / 输入框底色 |
| `--surface-2` | `#eceef0` | 次级面（进度槽、分段控件、chip） |
| `--surface-3` | `#e1e4e7` | 三级面（hover、统计卡内块） |
| `--border` | `#e0e2e5` | 常规描边 |
| `--border-strong` | `#cbced3` | 强调描边 / hover |
| `--text` | `#191c20` | 主文字（石墨近黑） |
| `--text-2` | `#555b62` | 次要文字 |
| `--text-3` | `#8a8f98` | 辅助 / 占位文字 |
| `--primary` | `#0f9d63` | 品牌主色（翠绿 emerald） |
| `--primary-strong` | `#0b8052` | 主色 hover / 描边强调 |
| `--on-primary` | `#ffffff` | 主色之上的文字 |
| `--success` | `#18925a` | 答对 / 正确（比主色略深，便于区分） |
| `--danger` | `#d6584e` | 答错 / 错误 |
| `--warning` | `#cf9015` | 标记 / 揭题 / 错题重做（琥珀） |

### 2.2 深色（Dark）

| Token | 值 |
|---|---|
| `--bg` | `#121315` |
| `--surface` | `#1c1e21` |
| `--surface-2` | `#26282c` |
| `--surface-3` | `#313438` |
| `--border` | `#303237` |
| `--border-strong` | `#43464c` |
| `--text` | `#e8e9eb` |
| `--text-2` | `#a7abb1` |
| `--text-3` | `#767a81` |
| `--primary` | `#34c98a` |
| `--primary-strong` | `#4dd69b` |
| `--on-primary` | `#06140d` |
| `--success` | `#3fc287` |
| `--danger` | `#e07b6f` |
| `--warning` | `#d8b063` |

### 2.3 语义柔光（soft / ring）

每个语义色都有一个低透明度版本，用于填充背景，保证文字仍可读：

- `--primary-soft` / `--success-soft` / `--danger-soft` / `--warning-soft`：约 12–18% 透明度的同色填充。
- `--primary-ring`：聚焦光环（`box-shadow` 0 0 0 3px），约 24–30% 透明度。

### 2.4 背景纹理（texture）

- `--dot`：页面底纹网点色（浅色 `rgba(25,28,34,.05)` / 深色 `rgba(255,255,255,.04)`），`body` 用 `radial-gradient` 平铺成 22px 网点。
- `--glow`：顶部柔光，`color-mix` 取 `--primary` 6–11% 叠在背景顶部。
- 规则：纹理只出现在 `--bg` 露出的区域（卡片是实色 surface），保持克制、不喧宾夺主。

> **规则**：状态色块一律「soft 背景 + 实色描边 / 文字」，不要用实色大面积填充（除了徽章、按钮、导航单元格这类小元素）。

---

## 3. 字体与排版

```
font-family: -apple-system, BlinkMacSystemFont, "Segoe UI",
             "PingFang SC", "Hiragino Sans GB", "Microsoft YaHei",
             system-ui, sans-serif;
```

- **不引入 web font**（保持零依赖、首屏即排版）。等宽场景用 `.mono`（`ui-monospace, "SF Mono", "JetBrains Mono", Menlo`）。
- `line-height` 正文 `1.6`，选项 `1.5`。
- `-webkit-font-smoothing: antialiased`，`text-rendering: optimizeLegibility`。

### 字号阶梯

| 角色 | 字号 | 字重 |
|---|---|---|
| 页面大标题 H1 | `clamp(22px, 5vw, 29px)` | 700 |
| 卡片标题 | 18px | 650 |
| 题干 question-text | 17.5px（手机 16.5px） | 550 |
| 选项 option-text | 15.5px | — |
| 正文 / 描述 | 14–15px | — |
| 次要说明 / chip | 12.5px | 500 |
| 徽章 / 标签 | 11.5–12px | 700 |
| 键盘提示 | 11.5px | — |

> 中文字重多用 550 / 650（介于 regular 与 bold），避免过粗发糊。

---

## 4. 间距、圆角、阴影、层级

### 圆角
| Token | 值 | 用途 |
|---|---|---|
| `--radius` | `16px` | 卡片、抽屉块、score 卡 |
| `--radius-sm` | `11px` | 按钮、选项、输入框、chip 容器 |
| `--radius-xs` | `8px` | 解析块、内嵌小块 |
| 全圆 | `999px` | chip、分段控件、进度条、徽章、toast |

### 阴影
- `--shadow-sm`：卡片静止态（极轻）。
- `--shadow`：hover / 浮起。
- `--shadow-lg`：抽屉、toast、悬浮层。
> 深色下阴影更深（已在 `[data-theme="dark"]` 重定义）。

### 间距
- 卡片内边距：桌面 `20–24px`，手机 `17–20px`。
- 元素间 `gap`：紧凑 `8–9px`，常规 `12–14px`，区块间 `16–22px`。
- **优先用 flex/grid + `gap`**，不要用裸 margin 堆间距。

### z-index 层级
| 层 | z-index |
|---|---|
| 吸顶 header | 40 |
| 吸底 action-bar | 30 |
| 抽屉遮罩 scrim | 60 |
| 抽屉 drawer | 61 |
| toast | 90 |

### 安全区
- `--safe-b: env(safe-area-inset-bottom)`，吸底栏、抽屉底、toast 都要叠加，适配刘海 / 手势条。
- viewport：`viewport-fit=cover`，高度用 `100dvh`。

---

## 5. 组件目录

每个组件的权威实现都在 `index.html`，这里只规范用法与状态。

### 5.1 按钮 `.btn`
- 变体：`.btn`（主色实心）、`.ghost`（描边）、`.subtle`（灰底）、`.warn`（琥珀）、`.success`（绿）。尺寸：默认 / `.sm`。
- 最小高度 **44px**（`.sm` 38px），满足触控热区。
- `:active` 缩放 `.97`；`:disabled` 透明度 `.4` 且 `pointer-events:none`。

### 5.2 图标按钮 `.icon-btn`
- 38×38 圆角方块，用于主题切换、关闭、导航开关。

### 5.3 套题卡 `.exam-card`
- 标题 + 右上角最高分环 + chip 元信息 + 描述 + 操作按钮组。
- hover 上浮 `translateY(-2px)` + 描边加强。
- 列表 `.exam-grid`：手机 1 列，`≥600px` 2 列，单套题时 `.solo` 占满整行。

### 5.4 Chip `.chip`
- 全圆灰底小标签，承载科目 / 题数 / 时长 / 记录数。**不加 emoji 图标**，纯文字。

### 5.5 题卡 `.question-card`
- 题型徽章 `.q-type`（single=绿、multiple=琥珀、blank=绿）+ 右上标记旗 `.q-flag` + 题干 + 作答区 + 反馈区。

### 5.6 选项 `.option`
- 自定义控件 `.ctrl`：单选 `.radio`（圆）、多选 `.check`（方），选中填主色 + ✓。
- 结构：`label.option > span.ctrl + span.option-body(.option-key + .option-text)`。
- 状态类：`.selected`、`.locked`、`.correct-opt`、`.wrong-opt`。
- 整个 `.option` 可点（不用裸 `<input>` 的点击，统一 JS `selectOption`）。

### 5.7 填空 `.blank-area`
- 每空一行：圆形序号 `.blank-index` + `.blank-input`。下方 `.blank-preview` 把题干里的 `___` 渲染成 `[1] [2]` 占位。
- 输入框 `font-size:16px`（防 iOS 聚焦缩放）。状态：`.correct-blank` / `.wrong-blank`。
- Enter 键跳下一空，最后一空触发主操作。

### 5.8 反馈区 `.feedback`
- 三态：`.correct`（答对）/ `.wrong`（答错）/ `.revealed`（仅揭题参考）。
- 结构：标题 `.fb-title` + 你的/正确答案 `.fb-line` + 解析 `.fb-explain`。
- 仅「练习模式」出现；「考试模式」作答时不显示。

### 5.9 进度条 `.progress-wrap`
- `.progress-track` 槽 + `.progress-fill` 主色填充，宽度 = 已完成 / 总数。
- 下方 `.progress-meta`：左「第 X / N 题」，右「已完成 X / N」。

### 5.10 分段控件 `.seg`（练习 / 考试）
- 全圆灰底，激活项白底浮起。切换考试模式会清掉已揭示的反馈。

### 5.11 吸底操作栏 `.action-bar`
- `position:sticky; bottom:0`，毛玻璃 + 顶边线。
- 左区：上一题、显示答案（仅练习）；右区：下一题箭头、主按钮（确认 / 下一题 / 提交，随状态变形）。

### 5.12 题目导航抽屉 `.drawer` + 遮罩 `.scrim`
- 右侧滑入，含图例 + 题号网格 `.nav-grid` + 底部「跳到标记 / 提交」。
- 单元格状态：`.empty`（未答）/ `.answered`（已选）/ `.correct` / `.wrong` / `.current`（光环），右上 `⚑` 标记点。
- **关键规则**：未展开时 `.scrim` 与 `.drawer` 必须 `pointer-events:none`，只有 `.show` 时才接管点击——否则透明遮罩会挡住整页交互。

### 5.13 成绩卡 `.score-card` + 环形 `.score-dial`
- 左侧 SVG 环形进度（`stroke-dasharray` 表示正确率），右侧答对数 + 评级徽章。
- 评级阈值：`≥85%` 优秀（绿）/ `≥60%` 及格（琥珀）/ `<60%` 继续加油（红）。

### 5.14 分题型统计 `.stats-card`
- 单选 / 多选 / 填空各自正确率，`≥80%` 绿、`<60%` 红、之间中性。

### 5.15 逐题回顾 `.result-q`
- 左边框按对错染色，含题号 + 题型 + 对错徽章 + 你的/正确答案 + 解析。

### 5.16 Toast `.toast`
- 底部居中胶囊，`window.__toast(msg, ms)` 触发，2 秒自动消失。

---

## 6. 交互模式

### 6.1 两种模式
- **练习模式（默认）**：作答后点「确认」立即判对错并展示解析；可「显示答案」揭题（不计错）。
- **考试模式**：作答时不反馈，全部完成后「提交」才出结果。切到考试模式会清空已揭示的反馈。

### 6.2 主按钮状态机
练习且未确认 → **确认**；已确认 / 考试模式且非末题 → **下一题**；末题 → **提交答卷**（有未答会二次确认）。

### 6.3 键盘映射（焦点不在输入框时生效）
| 键 | 行为 |
|---|---|
| `1`–`9` | 选 / 切对应选项 |
| `←` `→` | 上 / 下一题 |
| `Enter` | 触发主按钮（确认 / 下一题 / 提交） |
| `F` | 标记 / 取消标记本题 |
| `R` | 显示答案（仅练习、未判定时） |
| `Esc` | 关闭导航抽屉 |

### 6.4 触控手势
- 题卡区域左右滑动（位移 >60px 且横向为主）切上/下一题。

### 6.5 进度自动保存
- 答题状态（答案 / 当前题 / 模式 / 已判 / 已揭 / 标记）实时写 `localStorage`，重进自动恢复并提示「已自动恢复上次进度 · 从头开始」。提交后清除。
- 错题重做不参与自动恢复（独立临时会话）。

### 6.6 错题重做
- 结果页「重做错题」只加载本卷答错的题；重做完单独出结果与统计。

---

## 7. 响应式断点

| 条件 | 规则 |
|---|---|
| 默认 | 单列，`--maxw:760px` 居中 |
| `min-width:600px` | 套题列表 2 列 |
| `min-width:880px` | `--maxw:820px` |
| `max-width:599px` | 收紧内边距，题干 16.5px，成绩卡纵向堆叠，按钮隐藏 `.label-full` |
| `max-height:500px and landscape` | 压缩纵向留白，隐藏键盘提示 |
| `prefers-reduced-motion` | 关闭所有过渡 / 动画 |

> 所有热区 ≥44px；输入框字号 ≥16px 防 iOS 缩放。

---

## 8. 数据契约

题库 JSON（`data/<file>.json`）与清单（`data/manifest.json`）格式见 `README.md`。题型三种：

- `single` 单选：`options` + `answer:[idx]`
- `multiple` 多选：`options` + `answer:[idx,...]`
- `blank` 填空：题干用 `___` 占位 + `blanks:[[可接受答案,...], ...]`（大小写/首尾空格不敏感）

每题可选 `explanation` 解析。判分逻辑见 `engine-js` 的 `gradeQuestion()`。

---

## 9. 架构与扩展约定

- **单文件**：所有 CSS 在 `<style id="app-css">`，引擎在 `<script type="text/plain" id="engine-js">`（被主程序注入执行，并原样嵌入离线版，保证在线 / 离线同源同款）。
- **离线版** 通过 `buildOfflineHTML()` 复用同一份 CSS + 引擎，只换数据与启动脚本——**改样式或答题逻辑只需改一处**。
- 新增组件时：先在本文件登记 token / 状态，再在 `app-css` 实现，引用现有变量。
- 不写死颜色、不引外部资源、不破坏单文件可部署性。
- 改动核对清单：① 深 / 浅色都验过；② 手机竖屏 / 平板 / 桌面 / 横屏都验过；③ 键盘 + 触控 + 鼠标都能操作；④ 离线版同步生效。

---

_最后更新：2026-06-28 · 与 `index.html` 实现保持同步。_
