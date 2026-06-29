#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
parse_xuexitong_docx.py — 学习通导出的 Word 题库 → Exam Practice JSON

学习通网页版导出的 docx 格式特点（按章节组织）：
- 章节标题: 「1.1 国防的内涵」
- 题量声明: 「题量: 3 满分: 100.0」
- 答题记录: 「第1次作答 本次成绩100分」
- 题型分组: 「一. 单选题（共2题）」 / 「二. 多选题」 / 「三. 判断题」
- 题目格式:
    题号 (1/2/3 单独一段)
    【单选题】题干
    窗体顶端
    A、选项1
    B、选项2
    ...
    窗体底端
    我的答案：
    <字母或"对"/"错">
    <分数，如 33.3分 或 0.0分（错题）>
    AI讲解
- 判断题特殊格式 A: 「【判断题】题干。」（单行）
- 判断题特殊格式 B: 「【判断题】」+ 换行 + 「真正题干」（跨段，本工具已支持）
- 0.0 分 = Raylan 答错，学习通不显示正确答案 → 需要人工补正
- 「AI讲解」后面通常为空（学习通不导出讲解内容）

输出 JSON 格式（符合 SKILL.md § 题库 JSON schema）：
{
  "id": "<slug>",
  "title": "...",
  "subject": "...",
  "duration": 60,
  "questions": [
    { "id": "q1", "type": "single", "question": "...", "options": ["..."], "answer": [idx] },
    { "id": "q2", "type": "multiple", "question": "...", "options": ["..."], "answer": [idx1, idx2] },
    { "id": "q3", "type": "judge", "question": "...", "answer": [0] }   # 0=对 1=错
  ]
}

用法：
  python3 parse_xuexitong_docx.py <docx_path> <output_json> [--exam-id <id>] [--title <title>] [--subject <subject>] [--duration 120]

如果用户原卷里有「0.0 分」的错题，会被正常解析（用用户原答案），但需要人工核对或补正。
"""
import sys
import json
import re
import argparse
from collections import Counter
from docx import Document


def parse(docx_path):
    """核心解析逻辑：docx → 题目列表"""
    doc = Document(docx_path)
    paras = [p.text.strip() for p in doc.paragraphs]
    N = len(paras)

    # ─── 正则 ─────────────────────────────────────────────────────────
    qnum_re    = re.compile(r'^\d{1,3}$')                                  # 题号 1/2/3
    type_re    = re.compile(r'^【(.+?)】\s*(.*?)\s*$')                      # 【单选题】题干 / 【判断题】（单独段）
    opt_re     = re.compile(r'^[A-Z][、，．\.]\s*(.+)$')                  # A、XXX
    window_re  = re.compile(r'^窗体(顶端|底端)$')
    ans_label  = re.compile(r'^我的答案[：:]\s*$')
    score_re   = re.compile(r'^(\d+(?:\.\d+)?)\s*分\s*$')

    questions = []
    current_type = None
    cur = None  # {qno, qtext, options, ans_text, score}

    def commit():
        nonlocal cur
        if not cur:
            return
        raw = cur['ans_text']
        if raw is None:
            cur = None
            return
        raw = raw.strip()
        qtype = current_type
        opts = cur['options']
        qtext = cur['qtext']

        if qtype == 'single':
            m = re.fullmatch(r'([A-Z])', raw)
            if not m:
                cur = None
                return
            idx = ord(m.group(1)) - ord('A')
            if idx >= len(opts):
                cur = None
                return
            questions.append({
                "id": f"q{len(questions)+1}",
                "type": "single",
                "question": qtext,
                "options": opts,
                "answer": [idx],
            })
        elif qtype == 'multiple':
            m = re.fullmatch(r'([A-Z]+)', raw)
            if not m:
                cur = None
                return
            idxs = sorted({ord(c) - ord('A') for c in m.group(1)})
            for idx in idxs:
                if idx >= len(opts):
                    cur = None
                    return
            if not idxs:
                cur = None
                return
            questions.append({
                "id": f"q{len(questions)+1}",
                "type": "multiple",
                "question": qtext,
                "options": opts,
                "answer": idxs,
            })
        elif qtype == 'judge':
            ans_map = {'对': 0, '正确': 0, '是': 0, 'T': 0, 'true': 0, '√': 0, '✓': 0,
                       '错': 1, '错误': 1, '否': 1, 'F': 1, 'false': 1, '×': 1, '✕': 1}
            if raw not in ans_map:
                cur = None
                return
            questions.append({
                "id": f"q{len(questions)+1}",
                "type": "judge",
                "question": qtext,
                "answer": [ans_map[raw]],
            })
        cur = None

    # ─── 状态机 ───────────────────────────────────────────────────────
    i = 0
    while i < N:
        p = paras[i]

        if not p:
            i += 1
            continue

        # 题型分组标题：「一. 单选题（共2题）」
        mg = re.match(r'^[一二三四五六七八九十]+[.、．]\s*(单选题|多选题|判断题|单选|多选|判断)', p)
        if mg:
            commit()
            kind = mg.group(1)
            current_type = {'单选题': 'single', '单选': 'single',
                            '多选题': 'multiple', '多选': 'multiple',
                            '判断题': 'judge', '判断': 'judge'}[kind]
            i += 1
            continue

        # 题号（纯数字，1-3 位）
        if qnum_re.match(p):
            commit()
            cur = {'qno': p, 'qtext': '', 'options': [], 'ans_text': None, 'score': None}
            i += 1
            continue

        # 【单选题】xxx / 【多选题】xxx / 【判断题】xxx
        mt = type_re.match(p)
        if mt and cur is not None and not cur['qtext']:
            kind = mt.group(1)
            if kind in ('单选题', '单选'):
                current_type = 'single'
            elif kind in ('多选题', '多选'):
                current_type = 'multiple'
            elif kind in ('判断题', '判断'):
                current_type = 'judge'
            qtext = mt.group(2).strip()
            cur['qtext'] = qtext
            i += 1
            continue

        # 窗体顶端/底端
        if window_re.match(p):
            i += 1
            continue

        # 选项 A、XXX
        mo = opt_re.match(p)
        if mo and cur is not None and current_type in ('single', 'multiple'):
            cur['options'].append(mo.group(1))
            i += 1
            continue

        # 「我的答案：」 → 下一段是答案值
        if ans_label.match(p):
            if i + 1 < N:
                cur['ans_text'] = paras[i + 1]
                i += 2
            else:
                i += 1
            continue

        # 分数行（33.3 分 / 0.0 分 / 50.0 分）— 0.0 分也算有效（错题）
        ms = score_re.match(p)
        if ms and cur is not None:
            cur['score'] = float(ms.group(1))
            commit()
            i += 1
            continue

        # 「AI讲解」标签
        if p == 'AI讲解':
            i += 1
            continue

        # 判断题题干跨段补正：docx 里某些判断题格式是「【判断题】」+换行+真正题干
        if cur is not None and current_type == 'judge' and not cur['ans_text']:
            if p not in ('', 'AI讲解') and not window_re.match(p) \
                    and not ans_label.match(p) and not score_re.match(p) \
                    and not qnum_re.match(p) and not re.match(r'^[一二三四五六七八九十]+[.、．]', p) \
                    and not p.startswith('第') and not p.startswith('题量') \
                    and not re.match(r'^\d+\.\d+\s+', p):
                cur['qtext'] = (cur['qtext'] + p).strip() if cur['qtext'] else p
                i += 1
                continue

        # 其他段落：防御性跳过
        if p.startswith('第') and '作答' in p:
            i += 1
            continue
        if p.startswith('题量'):
            i += 1
            continue
        if re.match(r'^\d+\.\d+\s+', p) and i + 1 < N and '题量' in (paras[i + 1] or ''):
            commit()
            i += 2  # 跳过章节行 + 题量行
            continue

        i += 1

    commit()  # 收尾

    return questions


def clean(questions):
    """清理：所有题型题干剥末尾「（）」，去空题干"""
    cleaned = []
    skipped = []
    for q in questions:
        # 所有题型题干末尾的「（）」都是 docx 的题号标记残留，需要剥掉
        q['question'] = re.sub(r'（\s*）\s*$', '', q['question']).strip()
        if not q['question']:
            skipped.append(q)
            continue
        cleaned.append(q)
    return cleaned, skipped


def report(questions):
    """打印解析报告"""
    types = Counter(q['type'] for q in questions)
    empty = sum(1 for q in questions if not q['question'])
    bad_prefix = sum(1 for q in questions if q['question'].startswith('【'))
    bad_suffix = sum(1 for q in questions if q['question'].endswith('（）'))
    print(f"📊 解析报告")
    print(f"   总题数: {len(questions)}")
    print(f"   题型分布: single={types.get('single', 0)} / multiple={types.get('multiple', 0)} / judge={types.get('judge', 0)}")
    print(f"   空题干: {empty}")
    print(f"   题干含【】前缀: {bad_prefix}")
    print(f"   题干末尾带「（）」: {bad_suffix}")


def main():
    ap = argparse.ArgumentParser(description='学习通导出的 Word 题库 → Exam Practice JSON')
    ap.add_argument('docx', help='docx 文件路径')
    ap.add_argument('output', help='输出 JSON 路径')
    ap.add_argument('--exam-id', default='', help='题库 id（slug，如 monash-fit1045-2026-s1）')
    ap.add_argument('--title', default='', help='题库标题')
    ap.add_argument('--subject', default='', help='科目')
    ap.add_argument('--duration', type=int, default=120, help='考试时长（分钟）')
    args = ap.parse_args()

    questions = parse(args.docx)
    questions, skipped = clean(questions)

    if skipped:
        print(f"⚠️  跳过 {len(skipped)} 道空题干题")

    # 重新编号
    for i, q in enumerate(questions, 1):
        q['id'] = f'q{i}'

    report(questions)

    exam = {
        "id": args.exam_id or "exam",
        "title": args.title or "未命名题库",
        "subject": args.subject or "",
        "examDate": "",
        "duration": args.duration,
        "description": "来源：学习通导出的 docx。",
        "questions": questions,
    }

    with open(args.output, 'w', encoding='utf-8') as f:
        json.dump(exam, f, ensure_ascii=False, indent=2)
    print(f"✅ 已写入 {args.output}")

    # 错题警告
    print()
    print("⚠️  接下来你需要做的：")
    print("  1. 检查每章节题量是否正确（docx 里章节末尾有「本次成绩 < 100」的章节 = 有错题）")
    print("  2. 找出「0.0 分」的错题（我的答案字段），从学习通网页版对照正确答案")
    print("  3. 修正这些错题后，POST 到服务器 /api/exam 上线")
    print("  4. 见 SKILL.md「二、上线题库」")


if __name__ == '__main__':
    main()