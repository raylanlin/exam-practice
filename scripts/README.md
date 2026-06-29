# scripts/

放 exam-practice 项目的辅助脚本工具。当前：

## `parse_xuexitong_docx.py`

把学习通网页版导出的 Word 题库（`.docx`）转成符合本项目 schema 的 JSON 题库。

**为什么有这个脚本：** 学习通网页版复制下来的 docx 有固定格式（章节+题号+【】题型+选项+我的答案+分数+AI讲解），手工转 JSON 很烦，写一份通用解析器省事。

**依赖：**
```bash
pip install python-docx
```

**用法：**
```bash
python3 parse_xuexitong_docx.py <docx_path> <output_json> \
  --exam-id <id> \
  --title <title> \
  --subject <subject> \
  --duration 120
```

**示例：** 把咪大王军事理论 docx 转成 JSON：
```bash
python3 scripts/parse_xuexitong_docx.py \
  ~/Downloads/军事理论.docx \
  /tmp/junshililun_new.json \
  --exam-id gdufe-junshililun-2026-summer-quiz1 \
  --title "军事理论 复习题集" \
  --subject "军事理论" \
  --duration 120
```

**处理的学习通 docx 特殊格式：**

| 格式 | 处理 |
|------|------|
| 章节标题 `1.1 国防的内涵` | 跳过 |
| 题型分组 `一. 单选题（共2题）` | 切换 current_type |
| 题号 `1`/`2`/`3` 单独一段 | 开始新题 |
| 选项 `A、xxx` | 加入 options |
| `我的答案：` + 下一段是答案 | 取下一段作为答案 |
| 分数 `33.3 分` / `0.0 分` | 提交题；0.0 分也算有效（错题保留） |
| `AI讲解` | 跳过 |
| **判断题跨段**：`【判断题】`+ 换行 + 真题干 | 跨段补正合并题干 |
| **判断题题干末尾** `（）` | 自动剥掉 |

**⚠️ 解析后必须人工核对：**

1. docx 里 `本次成绩 < 100` 的章节 = 章节里有错题，需要从学习通网页版对照正确答案
2. 解析器保留「我的答案」字段（即用户原答），错题需要手动改 answer 字段
3. 检查空题干 / 题干含【】前缀 / 题干末尾带「（）」 三项必须 = 0

**输出 JSON 格式：** 见仓库根 `SKILL.md` 「一、识别材料 + 提取题目」节。

**替换原字段：** 题库 id 保持不变 = 覆盖现有题库；id 改了 = 新增一套题库。