#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
parse_jindaishi_docx.py — 「中国近现代史纲要」学习通导出的 docx → Exam Practice JSON

输入格式特点（学习通新版导出，按章节组织）:
  - 章节标题: 「中国近现代史纲要」
  - 子标题: 「期末复习（单选题）」 / 「期末复习（多选题）」 / 「后三个专题专项作业（填空题）」
  - 元信息: 「题量: 235  满分: 100」「作答时间:06-25 09:25至07-06 20:25」「智能分析」「100分」
  - 题型分组: 「一. 单选题（共235题，100分）」
  - 题目格式:
      题号. (题型)题干
      A. 选项1
      B. 选项2
      C. 选项3
      D. 选项4
      我的答案:X:选项;正确答案:X:选项;
      0.4分
      AI讲解
  - 判断题格式（理论相同）:
      我的答案:T/F:...
  - 填空题格式（无选项）:
      题号. (填空题)题干（题干中含 N 个 ____ 标记空位）
      我的答案：
      2.1分
      (1) 平均主义
      正确答案：
      (1) 平均主义
      AI讲解

输出:  Exam Practice JSON（SKILL.md schema，含 explanation）
"""
import sys
import json
import re
import argparse
from collections import Counter
from docx import Document


# ─── 正则 ─────────────────────────────────────────────────────────
QNUM_RE       = re.compile(r'^\d{1,3}\.\s*[(（](.+?)[)）]\s*(.*)$', re.DOTALL)  # 题号. (题型)题干
OPT_RE        = re.compile(r'^[A-Z][.。、，,．]\s*(.+)$')                       # A. XXX
MY_ANS_RE     = re.compile(r'^我的答案[：:]\s*(.*?)$')                         # 单选/多选 我的答案:X:...
MY_ANS_BLANK  = re.compile(r'^我的答案[：:]\s*$')                              # 填空 我的答案：
ANS_PAIR_RE   = re.compile(r'([A-Z]+|[对错]|正确|错误|T|F|true|false):([^;]+);', re.IGNORECASE)
SCORE_RE      = re.compile(r'^(\d+(?:\.\d+)?)\s*分\s*$')
BLANK_LABEL_RE = re.compile(r'^\(\d+\)\s+(.+)$')                               # (1) 平均主义
SECTION_RE    = re.compile(r'^[一二三四五六七八九十]+[.、．]\s*(单选题|多选题|判断题|单选|多选|判断|填空题|填空)')

JUDGE_MAP = {
    '对': 0, '正确': 0, '是': 0, 'T': 0, 'true': 0, '√': 0, '✓': 0,
    '错': 1, '错误': 1, '否': 1, 'F': 1, 'false': 1, '×': 1, '✕': 1,
}

ANSWER_TEXT_HEADERS = {'正确答案', '考题解答', '题目解答'}  # 填空题的「正确答案：」标记


def parse_blank_answers(text_block_lines):
    """从连续多段 [(1) 答案 (2) 答案 ...] 中提取所有空答案列表"""
    blanks = []
    for line in text_block_lines:
        line = line.strip()
        m = BLANK_LABEL_RE.match(line)
        if m:
            blanks.append(m.group(1).strip())
    return blanks


def parse(docx_path):
    """核心解析：docx → 题目列表（dict）"""
    doc = Document(docx_path)
    paras = [p.text.strip() for p in doc.paragraphs]
    N = len(paras)

    questions = []
    cur = None  # 当前题目累积：{qno, qtype, qtext, options, answers(mixed), score, in_correct_zone}
    skip_until_section = False

    def commit():
        nonlocal cur
        if not cur:
            return
        qtype = cur['qtype']
        opts = cur['options']
        qtext = cur['qtext']
        ans = cur.get('answers')  # 可能是 list[int] / list[str]

        if qtype == 'single':
            # answers 应是 [idx]
            if not ans or not isinstance(ans[0], int):
                cur = None
                return
            questions.append({
                "id": f"q{len(questions)+1}",
                "type": "single",
                "question": qtext,
                "options": opts,
                "answer": ans,
            })
        elif qtype == 'multiple':
            if not ans or any(not isinstance(a, int) for a in ans):
                cur = None
                return
            questions.append({
                "id": f"q{len(questions)+1}",
                "type": "multiple",
                "question": qtext,
                "options": opts,
                "answer": sorted(set(ans)),
            })
        elif qtype == 'judge':
            if not ans or not isinstance(ans[0], int):
                cur = None
                return
            questions.append({
                "id": f"q{len(questions)+1}",
                "type": "judge",
                "question": qtext,
                "answer": ans,
            })
        elif qtype == 'blank':
            # answers 是 list[str]，每个对应一个空
            if not ans or any(not isinstance(a, str) for a in ans):
                cur = None
                return
            # 题干里 ____ 的数量
            n_blanks = qtext.count('____')
            if n_blanks != len(ans):
                # 兜底：用答案数对齐题干
                if len(ans) > n_blanks:
                    ans = ans[:n_blanks]
                elif n_blanks > len(ans):
                    # 缺答案时填空填「（待填）」
                    while len(ans) < n_blanks:
                        ans.append('（待填）')
            questions.append({
                "id": f"q{len(questions)+1}",
                "type": "blank",
                "question": qtext,
                "blanks": [[a] for a in ans],
            })
        cur = None

    i = 0
    while i < N:
        p = paras[i]

        if not p:
            i += 1
            continue

        # 章节/题型分组标题：「一. 单选题（共235题，100分）」
        mg = SECTION_RE.match(p)
        if mg:
            commit()
            kind = mg.group(1)
            current_type_map = {
                '单选题': 'single', '单选': 'single',
                '多选题': 'multiple', '多选': 'multiple',
                '判断题': 'judge', '判断': 'judge',
                '填空题': 'blank', '填空': 'blank',
            }
            cur = None
            cur_type = current_type_map[kind]
            i += 1
            continue

        # 题号. (题型)题干
        mq = QNUM_RE.match(p)
        if mq and not p.startswith('第') and '作答' not in p:
            commit()
            kind_zh = mq.group(1)
            qtext = mq.group(2).strip()
            kind_map = {
                '单选题': 'single', '单选': 'single',
                '多选题': 'multiple', '多选': 'multiple',
                '判断题': 'judge', '判断': 'judge',
                '填空题': 'blank', '填空': 'blank',
            }
            if kind_zh in kind_map:
                cur_type = kind_map[kind_zh]
                cur = {
                    'qno': p.split('.')[0],
                    'qtype': cur_type,
                    'qtext': qtext,
                    'options': [],
                    'answers': None,
                    'score': None,
                    'in_correct_zone': False,  # 填空题：是否进入「正确答案：」区
                    'blank_buffer': [],       # 填空题当前累积的 (n) 答案块
                }
            i += 1
            continue

        # 选项 A. XXX（A. 或 A、 或 A,）
        mo = OPT_RE.match(p)
        if mo and cur is not None and cur['qtype'] in ('single', 'multiple'):
            cur['options'].append(mo.group(1).strip())
            i += 1
            continue

        # 跨段选项补正：「A.」「B.」等 label 单独成段，下一段才是选项内容
        # 检测格式：A. (中间只有 label)，下段为选项文本
        LABEL_ONLY_RE = re.compile(r'^([A-Z])[.。、，,．]\s*$')
        ml = LABEL_ONLY_RE.match(p)
        if ml and cur is not None and cur['qtype'] in ('single', 'multiple') and i + 1 < N:
            nxt = paras[i + 1].strip()
            if nxt and not OPT_RE.match(nxt) and not LABEL_ONLY_RE.match(nxt) \
                    and not MY_ANS_RE.match(nxt) and not MY_ANS_BLANK.match(nxt) \
                    and not SCORE_RE.match(nxt) and nxt != 'AI讲解' \
                    and not QNUM_RE.match(nxt) and not SECTION_RE.match(nxt):
                # 拼接成「A. {内容}」格式，重新走 OPT_RE
                cur['options'].append(nxt)
                i += 2
                continue

        # 「我的答案:ABD:选项;正确答案:ABD:选项;」（单选/多选）
        if cur is not None and cur['qtype'] in ('single', 'multiple'):
            ma = MY_ANS_RE.match(p)
            if ma:
                line = ma.group(1)
                # 解析 (字母:|true/false):文本;
                pairs = re.findall(r'([A-Z]+|[对错]|正确|错误|T|F|true|false):([^;]+);', line, re.IGNORECASE)
                # 第一个 pair 是「我的答案：」的字母，第二个是「正确答案：」的字母
                # 取「正确答案」更保险（0.0 分题学习通不显示我的答案正确选项）
                correct_letters = None
                my_letters = None
                if len(pairs) >= 2:
                    correct_letters = pairs[1][0]
                    my_letters = pairs[0][0]
                elif len(pairs) == 1:
                    my_letters = pairs[0][0]

                # 学习通的格式很可能是「我的答案:X:...;正确答案:X:...;」 → pairs[0]=我的, pairs[1]=正确答案
                # 但有的 docx 只有「我的答案:X:...;」无正确答案段，按用户的来

                letters = correct_letters or my_letters
                if letters:
                    upper = letters.upper()
                    if not upper.isalpha() or any(c not in 'ABCDEFGHIJ' for c in upper):
                        pass
                    else:
                        idxs = [ord(c) - ord('A') for c in upper if 'A' <= c <= 'Z']
                        cur['answers'] = idxs
                i += 1
                continue

        # 跨段题干补正：QNUM_RE 解析后 qtext 为空（如「175. (单选题)」+换段+真正题干）
        # 在进入选项/答案之前，把下一段非空文本塞进 cur['qtext']
        if cur is not None and not cur['qtext'] and cur['qtype'] in ('single', 'multiple', 'judge'):
            if p and not OPT_RE.match(p) \
                    and not MY_ANS_RE.match(p) and not MY_ANS_BLANK.match(p) \
                    and not SCORE_RE.match(p) and p != 'AI讲解' \
                    and not QNUM_RE.match(p) and not SECTION_RE.match(p) \
                    and not BLANK_LABEL_RE.match(p) \
                    and not p.startswith('题量') and not p.startswith('作答时间') \
                    and not re.match(r'^满分', p) and not re.match(r'^\d+(?:\.\d+)?分$', p) \
                    and p not in ('智能分析', '重做'):
                cur['qtext'] = p
                i += 1
                continue

        # 「我的答案：」（填空题）
        if cur is not None and cur['qtype'] == 'blank':
            ma = MY_ANS_BLANK.match(p)
            if ma:
                # 用户的填空答案紧跟在「我的答案：」下面，若与「正确答案」不同则采用正确答案
                # 进入子模式：从下一个非空段开始累积 (n) xxx 直到 「正确答案：」 或 「AI讲解」
                j = i + 1
                buf = []
                while j < N:
                    nxt = paras[j].strip()
                    if not nxt:
                        j += 1
                        continue
                    if nxt == '正确答案：' or nxt == '正确答案:':
                        cur['in_correct_zone'] = False
                        cur['my_blank_answers'] = parse_blank_answers(buf)
                        j += 1
                        # 继续累积正确答案到 AI讲解 / 题号
                        buf2 = []
                        while j < N:
                            nxt = paras[j].strip()
                            if not nxt:
                                j += 1
                                continue
                            if nxt == 'AI讲解' or QNUM_RE.match(nxt):
                                break
                            buf2.append(nxt)
                            j += 1
                        correct = parse_blank_answers(buf2)
                        cur['correct_blank_answers'] = correct
                        # 优先用正确答案（0.0 分题用此），否则用 my
                        if cur.get('correct_blank_answers'):
                            cur['answers'] = cur['correct_blank_answers']
                        else:
                            cur['answers'] = cur.get('my_blank_answers') or []
                        i = j
                        break
                    if nxt == 'AI讲解' or QNUM_RE.match(nxt):
                        cur['answers'] = cur.get('my_blank_answers') or []
                        i = j
                        break
                    buf.append(nxt)
                    j += 1
                else:
                    i = j
                continue

        # 填空题偶尔格式：用户答案与正确答案挨在一起（无「我的答案：」独立行）
        # 一些 docx 中可能是连续 "(1) 平均主义 (2) 制度自信 ..." 的格式
        if cur is not None and cur['qtype'] == 'blank' and BLANK_LABEL_RE.match(p):
            # 累积进 buffer，主答案提取在前面「我的答案：」分支中处理
            i += 1
            continue

        # 分数行（0.4 分 / 33.3 分 / 0.0 分）- 0.0 分也算有效
        ms = SCORE_RE.match(p)
        if ms and cur is not None:
            cur['score'] = float(ms.group(1))
            commit()
            i += 1
            continue

        # 「AI讲解」标签 - 后面的内容都是讲解（一般为空，我们用后处理填充）
        if p == 'AI讲解':
            i += 1
            continue

        # 章节里的元信息（章节名、子标题、题量、作答时间、智能分析、智能分析+数字分）
        if p in ('智能分析', '重做') or p.startswith('题量') or p.startswith('作答时间'):
            i += 1
            continue
        # 「满分: 100」行偶尔独立
        if re.match(r'^满分\s*[：:]\s*\d+', p):
            i += 1
            continue
        # 「97.9分」（纯分数）跳过
        if re.match(r'^\d+(?:\.\d+)?分$', p):
            i += 1
            continue

        i += 1

    commit()  # 收尾

    # 清洗
    cleaned = []
    skipped = []
    for q in questions:
        # 末尾「（）」剥掉
        q['question'] = re.sub(r'（\s*）\s*$', '', q['question']).strip()
        if not q['question']:
            skipped.append(q)
            continue
        cleaned.append(q)
    return cleaned, skipped


def report(questions, skipped):
    types = Counter(q['type'] for q in questions)
    print(f"📊 解析报告")
    print(f"   总题数: {len(questions)}")
    print(f"   跳过空题干: {len(skipped)}")
    print(f"   题型分布: single={types.get('single', 0)} / multiple={types.get('multiple', 0)} "
          f"/ judge={types.get('judge', 0)} / blank={types.get('blank', 0)}")


def main():
    ap = argparse.ArgumentParser(description='中国近现代史纲要 → Exam Practice JSON')
    ap.add_argument('docx')
    ap.add_argument('output')
    ap.add_argument('--exam-id', required=True)
    ap.add_argument('--title', required=True)
    ap.add_argument('--subject', required=True)
    ap.add_argument('--duration', type=int, default=120)
    args = ap.parse_args()

    qs, skp = parse(args.docx)
    # 重编号
    for i, q in enumerate(qs, 1):
        q['id'] = f'q{i}'

    report(qs, skp)

    exam = {
        "id": args.exam_id,
        "title": args.title,
        "subject": args.subject,
        "examDate": "",
        "duration": args.duration,
        "description": "来源：学习通导出的 docx（中国近现代史纲要期末复习）",
        "questions": qs,
    }
    with open(args.output, 'w', encoding='utf-8') as f:
        json.dump(exam, f, ensure_ascii=False, indent=2)
    print(f"✅ 已写入 {args.output}")
    if skp:
        print(f"⚠️  跳过 {len(skp)} 道空题干题")


if __name__ == '__main__':
    main()
