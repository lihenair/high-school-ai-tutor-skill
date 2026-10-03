#!/usr/bin/env python3
"""
回复守卫：把要发给学生的回复先交给本脚本检查，过了再发送。

用法：
    python3 guard.py --mode socratic reply.txt     # 引导模式（苏格拉底）
    python3 guard.py --mode full reply.txt         # 完整模式 / 总结阶段（summary 同 full）
    python3 guard.py --mode socratic --no-student-answer reply.txt
    python3 guard.py --mode full --subject math reply.txt   # 数学完整模式额外查机验标记
    python3 guard.py --mode study reply.txt                 # 自学模式
    python3 guard.py --mode study --dir tests/guard-cases/self-study/
    cat reply.txt | python3 guard.py --mode full -

退出码：0 = 无 ERROR（可含 WARN，仍可发送，与 SKILL.md「退出码为 0 才发送」一致）；1 存在 ERROR，按清单修改后重检；2 用法错误。

守卫只机检红线（漏答案、缺九段标题、缺本题 mermaid 图谱、边标签、人教版化学必修第一册第一章节点、非法用词、加权算错、编造「我的错误」、
数学完整模式缺机验标记 --subject math），查不出内容对错——验算仍按各科 reference 的清单做。
"""

import argparse
import re
import sys
from decimal import ROUND_HALF_UP, Decimal
from pathlib import Path

DIFFICULTY_LEVELS = ("基础", "中等", "压轴", "竞赛")
WEIGHTS = (0.30, 0.25, 0.20, 0.15, 0.10)  # 未点名维度时按位置；点名时用各科 reference 表
_REF_DIR = Path(__file__).resolve().parent.parent / "references"
_DIM_REF_FILES = ("math.md", "physics.md", "chemistry.md", "biology.md", "humanities.md")
SUMMARY_HEADINGS = (
    "难度判断", "讲解", "解题思维链", "一题多解", "解法对比",
    "变式题", "错因诊断", "错题本沉淀", "总结",
)
RULE_GUIDED = "SKILL.md「每轮输出总则 → 引导模式本轮只输出」"
RULE_SUMMARY_FMT = "modes/full.md「题目完成后的总结格式」"
RULE_DIFFICULTY = "modes/full.md「难度总则」"
RULE_NOTEBOOK = "modes/records.md「错题本何时生成」；modes/full.md「核心规则」"
RULE_VERIFY = "modes/math-verify.md「数学机验」"
# 数学完整模式第 2 节末尾只能用这五句机验标记之一，方便家长和老师按固定规则筛。
VERIFY_MARKERS = ("已机验：通过", "未机验：无法解析", "未机验：超时", "未机验：未安装 SymPy", "此结果未通过机验")
VERIFY_MARKER_HINT = " / ".join(VERIFY_MARKERS)
# 出现「机验」二字但不是上面五句之一，视为句式漂移。
VERIFY_LOOSE_RE = re.compile(r"机验")

# 引导模式疑似给出最终结果的写法
ANSWER_LEAK_PATTERNS = [
    (r"答案[是为：:]\s*\S", "直接给出「答案为…」"),
    (r"(?:所以|因此|综上|故|∴)[^。！？\n]{0,40}(?:[=≤≥<>]|等于)\s*[-+]?[\d.]", "推到具体数值/不等式"),
    (r"(?:取值范围|解集|值域)[是为：:]\s*[{\[（(]?[-+]?[\d.]", "给出范围/解集"),
    (r"答案?是\s*[A-D]\b", "直接报选择题选项"),
    (r"(?<![你他她谁咱刚学生])(?:故选|选)\s*[A-D](?:[选项]|[.。、]|$)", "直接报选择题选项"),
]
# 引导模式不该先说破的关键公式（常见形状）
FORMULA_PATTERNS = [
    (r"[fF]\s*=\s*m\s*a\b", "牛顿第二定律"),
    (r"x\s*=\s*-\s*b\s*/\s*\(?\s*2\s*a", "抛物线对称轴公式"),
    (r"[pP]\s*V\s*=\s*n\s*R\s*T", "理想气体状态方程"),
    (r"v\s*=\s*v[₀0]\s*[+＋]", "匀变速速度公式"),
    (r"[sS]\s*=\s*v[₀0]\s*t\s*[+＋]", "匀变速位移公式"),
]
BAD_DIFFICULTY_RE = re.compile(r"偏难|偏易|中等偏上|中等偏下|较难|较易|很难|太简单|太容易")
HEADING_RE = re.compile(r"^#{2,3}\s*([0-9０-９])\s*[\.、．]\s*(\S+)")
SCORES_RE = re.compile(r"([1-5])\s*[、,，]\s*([1-5])\s*[、,，]\s*([1-5])\s*[、,，]\s*([1-5])\s*[、,，]\s*([1-5])\s*分")
WEIGHTED_EXPANSION_RE = re.compile(r"0\.30\s*[×x*]")
MERMAID_RE = re.compile(r"```[ \t]*mermaid[^\n]*\n(.*?)```", re.S)
ARROW_TOKEN = r"(?:-\.->|-.-|o--o|x--x|-->|---|==>|===|--o|--x|o--|x--)"
LABELED_EDGE_RE = re.compile(rf"({ARROW_TOKEN})\s*\|([^|\n]+)\|")
UNLABELED_EDGE_RE = re.compile(ARROW_TOKEN)
_NODE_ID_RE = re.compile(r"[\w]+(?:-[\w]+)*")
# Longest Mermaid flowchart shapes first so inner brackets are not the label.
_NODE_SHAPES = (
    ("(((", ")))"),
    ("((", "))"),
    ("([", "])"),
    ("[[", "]]"),
    ("[(", ")]"),
    ("{{", "}}"),
    ("[/", "\\]"),
    ("[\\", "/]"),
    ("[/", "/]"),
    ("[\\", "\\]"),
    (">", "]"),
    ("{", "}"),
    ("(", ")"),
    ("[", "]"),
)
NODE_DIRECTIVE_RE = re.compile(
    r"^(?:classDef|class|click|style|linkStyle|subgraph|end|flowchart|graph|direction)\b"
)
TRAILING_PAREN_RE = re.compile(r"(?:\([^()]*\)|（[^（）]*）)+\s*$")
HTML_BR_RE = re.compile(r"<br\s*/?>", re.IGNORECASE)
HTML_TAG_RE = re.compile(r"<[^>]+>")
EMOJI_RE = re.compile(
    "["
    "\U0001F300-\U0001FAFF"
    "\U00002700-\U000027BF"
    "\U00002600-\U000026FF"
    "\U0001F1E0-\U0001F1FF"
    "\U0000FE0F"
    "\U0000200D"
    "]+"
)
NODE_TOKEN_SPLIT_RE = re.compile(r"[/／、，,；;：:·・+＋\s]+")
CANON_PART_RE = re.compile(r"[/／、，,；;：:\s与]+")
EDGE_TEXT_RE = re.compile(r"--\s+[^-|\n]+-->")
MAX_REQUIRED_NAMES_PER_NODE = 6
MIN_REQUIRED_NODE_LABELS = 10
EDGE_LABELS = {"直接前置", "同章衔接", "常考组合"}
SOLID_LABELS = {"直接前置", "同章衔接"}
# 只核这一册这一章的整章图。本题切片不要写这一行。
PEP_CHEM_BX1_CH1_MARKER = "整章图：人教版《化学 必修 第一册》（2019）第一章"
PEP_CHEM_BX1_CH1_REQUIRED = (
    "纯净物", "混合物", "单质", "化合物", "氧化物", "酸", "碱", "盐",
    "交叉分类", "分散系", "丁达尔", "物质的转化",
    "电解质", "电离", "离子方程式", "离子反应发生的条件",
    "化合价", "氧化剂", "还原剂", "四种基本反应类型",
)
PEP_CHEM_BX1_CH1_FORBIDDEN = ("电石", "PH₃", "PH3", "Cu₃P", "Cu3P")


def fullwidth_int(ch):
    o = ord(ch)
    if 0xFF10 <= o <= 0xFF19:
        return o - 0xFF10
    return int(ch)


def hits(pattern, text):
    """返回 [(行号, 行文本)]。"""
    out = []
    for i, line in enumerate(text.splitlines(), 1):
        if re.search(pattern, line):
            out.append((i, line.strip()))
    return out


def check_bad_difficulty(lines):
    out = []
    for i, line in enumerate(lines, 1):
        if "难度" in line and BAD_DIFFICULTY_RE.search(line):
            out.append((i, line.strip()))
    return out


def check_summary_headings(lines):
    """完整模式：九个标题按 1-9 齐全。返回缺失的序号列表。"""
    found = set()
    for line in lines:
        m = HEADING_RE.match(line)
        if not m:
            continue
        num = fullwidth_int(m.group(1))
        if 1 <= num <= 9 and m.group(2).startswith(SUMMARY_HEADINGS[num - 1]):
            found.add(num)
    return [n for n in range(1, 10) if n not in found]


def parse_dimension_tables(md_text):
    """从 reference markdown 抽出「维度 | 权重」表，每张表是 [(名, 权重), ...]。"""
    tables = []
    rows = []
    header_ok = False
    for raw in md_text.splitlines():
        line = raw.strip()
        if not line.startswith("|"):
            if header_ok and len(rows) == 5:
                tables.append(rows)
            rows = []
            header_ok = False
            continue
        cells = [c.strip() for c in line.strip("|").split("|")]
        if not cells:
            continue
        if all(re.fullmatch(r":?-{3,}:?", c.replace(" ", "") or "-") for c in cells):
            continue
        if cells[0] == "维度" and len(cells) >= 2 and "权重" in cells[1]:
            header_ok = True
            rows = []
            continue
        if header_ok and len(cells) >= 2:
            m = re.match(r"(\d+(?:\.\d+)?)\s*%", cells[1])
            if m:
                rows.append((cells[0], float(m.group(1)) / 100.0))
    if header_ok and len(rows) == 5:
        tables.append(rows)
    return tables


def load_dimension_tables(ref_dir=None):
    root = Path(ref_dir) if ref_dir else _REF_DIR
    out = []
    for name in _DIM_REF_FILES:
        path = root / name
        if not path.is_file():
            continue
        for rows in parse_dimension_tables(path.read_text(encoding="utf-8")):
            out.append({k: v for k, v in rows})
    return out


DIMENSION_TABLES = load_dimension_tables()


def _compile_dim_score_re(tables):
    names = sorted({n for t in tables for n in t}, key=len, reverse=True)
    if not names:
        return None
    alt = "|".join(re.escape(n) for n in names)
    return re.compile(
        rf"({alt})"
        rf"(?:\s*[（(][^)）]*[)）])?"
        rf"\s*[：:]?\s*"
        rf"({_DIGIT_1_5})(?:\s*/\s*5)?(?:\s*分)?"
    )


def _table_for_names(names):
    key = frozenset(names)
    hits = [t for t in DIMENSION_TABLES if frozenset(t) == key]
    if len(hits) != 1:
        return None
    return hits[0]


# 加权分抽取：只认引入关键字后的等号链，不扫回复其余部分。
_WEIGHTED_LABEL_RE = re.compile(r"加权(?:总分|得分|分(?!别))?")
_WEIGHTED_CONT_RE = re.compile(r"^\s*[=＝≈]")
_WEIGHTED_FIRST_CONN_RE = re.compile(r"^(?:[=＝:：≈]|为|是)\s*")
_WEIGHTED_SENTENCE_END_RE = re.compile(r"[。！？]")
_WEIGHTED_MOD_RE = re.compile(r"^(后|结果|约|计算|所得|得到|出来|值|的)\s*")
_CHAIN_OPEN_TAIL_RE = re.compile(r"[=＝≈＋+−\-×x*·/÷（(]\s*$")
_DIGIT_1_5 = r"[1-5１-５]"
_FIVE_COMMA_RE = re.compile(
    rf"({_DIGIT_1_5})\s*[、,，]\s*({_DIGIT_1_5})\s*[、,，]\s*"
    rf"({_DIGIT_1_5})\s*[、,，]\s*({_DIGIT_1_5})\s*[、,，]\s*({_DIGIT_1_5})"
)
_FIVE_SLASH_RE = re.compile(
    rf"({_DIGIT_1_5})\s*/\s*({_DIGIT_1_5})\s*/\s*"
    rf"({_DIGIT_1_5})\s*/\s*({_DIGIT_1_5})\s*/\s*({_DIGIT_1_5})"
)
_PER_ITEM_OVER_FIVE_RE = re.compile(rf"({_DIGIT_1_5})\s*/\s*5")
_OUT_OF_FIVE_RE = re.compile(
    r"(?:\s*[（(]\s*满分\s*5(?:\.0+)?\s*[)）]|\s*满分\s*5(?:\.0+)?)\s*$"
)
_TRAIL_FEN_RE = re.compile(r"分\s*$")
_TRAIL_PAREN_RE = re.compile(r"[（(][^)）]*[)）]\s*$")
_ASCII_NUM_RE = re.compile(r"^[0-9]*\.?[0-9]+(?:[eE][+-]?[0-9]+)?$")
_LEAD_NUM_RE = re.compile(r"^([0-9]*\.?[0-9]+(?:[eE][+-]?[0-9]+)?)(.*)$")
_FRAC_RE = re.compile(r"^([0-9]+(?:\.[0-9]+)?)\s*/\s*([0-9]+(?:\.[0-9]+)?)$")
_FW_TRANS = str.maketrans("０１２３４５６７８９．", "0123456789.")
_CN_DIGIT = {
    "零": "0", "〇": "0", "一": "1", "二": "2", "两": "2", "三": "3",
    "四": "4", "五": "5", "六": "6", "七": "7", "八": "8", "九": "9",
}
_CLAUSE_PUNCT = "，,；;"
_CHAIN_OPS = "=＝≈"
_DIM_SCORE_RE = _compile_dim_score_re(DIMENSION_TABLES)
_RUBRIC_HINT_RE = re.compile(r"档位|档|锚点|依次|分别表示|越高越|为中位")
_GRADE_INTERVAL_RE = re.compile(
    r"等级区间|[≤＜<＞>]\s*\d+\.\d+|\d+\.\d+\s*[–\-]\s*\d+\.\d+"
)
_ANCHOR_EQ_RE = re.compile(r"[1-5１-５]\s*分\s*[=＝]")
_ANCHOR_PAREN_RE = re.compile(r"[1-5１-５]\s*分\s*[（(]")
_LEGEND_TABLE_RE = re.compile(r"\|\s*[1-5１-５]\s*分")
_WEIGHTED_SKIP_HEAD_RE = re.compile(
    r"^(?:"
    r"也就是|约等于|"
    r"得到|得出|后得|算得|所得|"
    r"等于|"
    r"得|计|为|是|即|约|"
    r"后|结果|计算|出来|值|的|"
    r"[,，:：]"
    r")\s*"
)
_RESP_HEAD_RE = re.compile(r"^(?:分别为|分别是)\s*[：:]?\s*")
_RESP_SPLIT_RE = re.compile(r"\s*(?:和|与|、|,|，)\s*")


def _skip_paren(text):
    if not text or text[0] not in "(（":
        return text
    closer = ")" if text[0] == "(" else "）"
    idx = text.find(closer, 1)
    if idx < 0:
        return text[1:]
    return text[idx + 1:]


def _split_paren(text):
    if not text or text[0] not in "(（":
        return None, text
    closer = ")" if text[0] == "(" else "）"
    idx = text.find(closer, 1)
    if idx < 0:
        return text[1:], ""
    return text[1:idx], text[idx + 1:]


def _paren_unwrap_value(inner):
    """括号里只有一个数（可带 = / 即）时返回可解析文本，否则 None。"""
    s = inner.strip()
    if not s or re.search(r"满分|权重", s):
        return None
    s = re.sub(r"^(?:[=＝≈]|即)\s*", "", s).strip()
    if _parse_plain_number(s) is None:
        return None
    return s


def _skip_modifiers(text):
    """关键字后跳过同一小句里的短修饰词和括号，再读分隔符或数值。"""
    s = text
    for _ in range(12):
        s = s.lstrip()
        if not s:
            return s
        if s[0] in "(（":
            inner, after = _split_paren(s)
            if inner is None:
                return s
            unwrapped = _paren_unwrap_value(inner)
            if unwrapped is not None:
                return unwrapped + after
            s = after
            continue
        m = _WEIGHTED_SKIP_HEAD_RE.match(s)
        if m:
            s = s[m.end():]
            continue
        m = _WEIGHTED_MOD_RE.match(s)
        if m:
            s = s[m.end():]
            continue
        return s
    return s


def _span_end_with_fen(line, end):
    after = line[end:]
    stripped = after.lstrip()
    if stripped.startswith("分"):
        return end + len(after) - len(stripped) + 1
    return end


def _overlaps(a0, a1, b0, b1):
    return a0 < b1 and b0 < a1


def _is_scale_legend_scores(scores):
    return set(scores) == {1, 2, 3, 4, 5} and len(scores) == 5


def _line_has_rubric_hint(line):
    return bool(
        _RUBRIC_HINT_RE.search(line)
        or _ANCHOR_EQ_RE.search(line)
        or _ANCHOR_PAREN_RE.search(line)
        or ("|" in line and _LEGEND_TABLE_RE.search(line) and re.search(r"5\s*分", line))
    )


def _skip_positional_span(line, scores):
    return _line_has_rubric_hint(line) and _is_scale_legend_scores(scores)


def _named_hits_on_line(line):
    if not _DIM_SCORE_RE:
        return []
    out = []
    for m in _DIM_SCORE_RE.finditer(line):
        out.append((m.start(), m.end(), m.group(1), fullwidth_int(m.group(2))))
    return out


def _try_named_chunk(hits):
    if len(hits) != 5:
        return None
    names = [h[2] for h in hits]
    table = _table_for_names(names)
    if table is None:
        return "reject"
    scores = [h[3] for h in hits]
    weights = tuple(table[n] for n in names)
    return scores, weights, hits[0][0], hits[-1][1]


def _parse_five_scores(line):
    """抽出一行里的五项 1-5 分；认顿号/逗号、5/4/3/2/1、x/5、全角数字。"""
    groups = _positional_spans(line, occupied=[])
    return groups[0][2] if groups else None


def _positional_spans(line, occupied):
    """返回 [(start, end, scores), ...]，避开 occupied 区间。"""
    found = []

    def take(start, end, scores):
        if any(_overlaps(start, end, a, b) for a, b in occupied):
            return
        if any(_overlaps(start, end, a, b) for a, b, _ in found):
            return
        if _skip_positional_span(line, scores):
            return
        found.append((start, _span_end_with_fen(line, end), scores))

    if "标准" not in line:
        for m in _FIVE_SLASH_RE.finditer(line):
            take(m.start(), m.end(), [fullwidth_int(g) for g in m.groups()])
        items = list(_PER_ITEM_OVER_FIVE_RE.finditer(line))
        if len(items) == 5:
            take(items[0].start(), items[-1].end(), [fullwidth_int(m.group(1)) for m in items])
    for m in _FIVE_COMMA_RE.finditer(line):
        after = line[m.end():].lstrip()
        before = line[:m.start()]
        if after.startswith("分") or "各项" in before:
            take(m.start(), m.end(), [fullwidth_int(g) for g in m.groups()])
    for m in SCORES_RE.finditer(line):
        take(m.start(), m.end(), [fullwidth_int(g) for g in m.groups()])
    found.sort(key=lambda x: x[0])
    return found


def _collect_score_groups(lines):
    """按出现位置列出五项分组：(pos, end_pos, scores, weights)。"""
    groups = []
    occupied = [[] for _ in lines]
    i = 0
    n = len(lines)
    while i < n:
        line = lines[i]
        if _GRADE_INTERVAL_RE.search(line) and "加权" not in line:
            i += 1
            continue
        hits = _named_hits_on_line(line)
        if len(hits) >= 5:
            j = 0
            consumed = False
            while j + 5 <= len(hits):
                chunk = hits[j:j + 5]
                result = _try_named_chunk(chunk)
                if result == "reject":
                    for h in chunk:
                        occupied[i].append((h[0], h[1]))
                    j += 5
                    consumed = True
                    continue
                if result:
                    scores, weights, start, end = result
                    groups.append(((i, start), (i, end), scores, weights))
                    occupied[i].append((start, end))
                    j += 5
                    consumed = True
                    continue
                j += 1
            if consumed:
                for start, end, scores in _positional_spans(line, occupied[i]):
                    groups.append(((i, start), (i, end), scores, WEIGHTS))
                    occupied[i].append((start, end))
                i += 1
                continue
        if len(hits) == 1:
            run = [(i, hits[0])]
            k = i + 1
            while k < n and len(run) < 5:
                nxt = lines[k]
                if not nxt.strip() or HEADING_RE.match(nxt):
                    break
                more = _named_hits_on_line(nxt)
                if len(more) != 1:
                    break
                run.append((k, more[0]))
                k += 1
            if len(run) == 5:
                chunk = [h for _, h in run]
                result = _try_named_chunk(chunk)
                if result == "reject":
                    for li, h in run:
                        occupied[li].append((h[0], h[1]))
                    i = run[-1][0] + 1
                    continue
                if result:
                    scores, weights, _, _ = result
                    start_li, start_h = run[0]
                    end_li, end_h = run[-1]
                    groups.append((
                        (start_li, start_h[0]),
                        (end_li, end_h[1]),
                        scores,
                        weights,
                    ))
                    for li, h in run:
                        occupied[li].append((h[0], h[1]))
                    i = end_li + 1
                    continue
        for start, end, scores in _positional_spans(line, occupied[i]):
            groups.append(((i, start), (i, end), scores, WEIGHTS))
            occupied[i].append((start, end))
        i += 1
    groups.sort(key=lambda g: g[0])
    return groups


def _expect_weighted(scores, weights):
    return round(sum(s * w for s, w in zip(scores, weights)), 2)


def _leading_respectively(text):
    s = text.lstrip()
    for _ in range(6):
        s = s.lstrip()
        if not s:
            return None
        if s[0] in "，,、；;：:":
            s = s[1:]
            continue
        m = _RESP_HEAD_RE.match(s)
        if m:
            return s[m.end():]
        return None
    return None


def _parse_resp_values(body):
    clipped = re.sub(r"^[\s:：=＝≈]+", "", _cut_clause(body))
    parts = [p.strip() for p in _RESP_SPLIT_RE.split(clipped) if p.strip()]
    values = []
    for part in parts:
        val = _parse_plain_number(part)
        if val is None:
            return []
        values.append(val)
    return values


def _paragraph_bounds(lines, line_i):
    start = line_i
    while start > 0 and lines[start - 1].strip() and not HEADING_RE.match(lines[start - 1]):
        start -= 1
    end = line_i + 1
    while end < len(lines) and lines[end].strip() and not HEADING_RE.match(lines[end]):
        end += 1
    return start, end


def _cut_clause(text):
    """在，,；;处截断，除非其后（空白后）是 =/＝/≈。"""
    depth = 0
    i = 0
    while i < len(text):
        ch = text[i]
        if ch in "(（":
            depth += 1
        elif ch in ")）":
            depth = max(0, depth - 1)
        elif depth == 0 and ch in _CLAUSE_PUNCT:
            j = i + 1
            while j < len(text) and text[j] in " \t":
                j += 1
            if j < len(text) and text[j] in _CHAIN_OPS:
                i += 1
                continue
            return text[:i]
        elif depth == 0 and ch in "。！？":
            return text[:i]
        i += 1
    return text


def _split_chain_segments(text):
    parts, seps, buf, depth = [], [], [], 0
    last_sep = ""
    for ch in text:
        if ch in "(（":
            depth += 1
            buf.append(ch)
        elif ch in ")）":
            depth = max(0, depth - 1)
            buf.append(ch)
        elif depth == 0 and ch in _CHAIN_OPS:
            parts.append("".join(buf))
            seps.append(last_sep)
            buf = []
            last_sep = ch
        else:
            buf.append(ch)
    parts.append("".join(buf))
    seps.append(last_sep)
    return list(zip(seps, parts))


def _parse_chinese_number(text):
    if not text or any(ch not in _CN_DIGIT and ch != "点" for ch in text):
        return None
    if "点" in text:
        left, right = text.split("点", 1)
        if not right or (left and not all(ch in _CN_DIGIT for ch in left)):
            return None
        if not all(ch in _CN_DIGIT for ch in right):
            return None
        whole = "".join(_CN_DIGIT[ch] for ch in left) if left else "0"
        frac = "".join(_CN_DIGIT[ch] for ch in right)
        return float(f"{whole}.{frac}")
    if len(text) != 1:
        return None
    return float(_CN_DIGIT[text])


def _frac_or_out_of_five(num, den):
    if den == 0:
        return None
    if den == 5.0 and num <= 5.0:
        return num
    return num / den


def _parse_plain_number(segment):
    """一段若整体是一个数（可带分、/5、括号注释）则返回 float，否则 None。"""
    s = segment.strip()
    if not s:
        return None
    s = _OUT_OF_FIVE_RE.sub("", s).strip()
    s = _TRAIL_FEN_RE.sub("", s).strip()
    s = _OUT_OF_FIVE_RE.sub("", s).strip()
    s = _TRAIL_PAREN_RE.sub("", s).strip()
    s = _TRAIL_FEN_RE.sub("", s).strip()
    s = s.translate(_FW_TRANS).strip()
    if not s:
        return None
    if _ASCII_NUM_RE.match(s):
        return float(s)
    m = _FRAC_RE.match(s)
    if m:
        return _frac_or_out_of_five(float(m.group(1)), float(m.group(2)))
    cn = _parse_chinese_number(s)
    if cn is not None:
        return cn
    m = _LEAD_NUM_RE.match(s)
    if not m:
        return None
    rest = m.group(2).lstrip()
    if rest and rest[0] in "+-×x*·/÷()=＝≈":
        return None
    return float(m.group(1))


def _approx_places(segment):
    s = segment.translate(_FW_TRANS)
    m = re.search(r"\.([0-9]+)", s)
    if m:
        return len(m.group(1))
    return 0


def _round_half_up(value, places):
    q = Decimal(1) if places <= 0 else Decimal(1).scaleb(-places)
    return float(Decimal(str(value)).quantize(q, rounding=ROUND_HALF_UP))


def _is_rounding_of(exact, approx, approx_seg):
    places = _approx_places(approx_seg)
    return abs(_round_half_up(exact, places) - approx) < 1e-9


def _is_weight_description(text):
    """权重/百分比说明，不是账面加权分。"""
    plain = re.sub(r"[（(][^)）]*[)）]", "", text)
    return bool(re.search(r"\d+\s*%", plain) or "权重" in plain)


def _line_opens_chain(text):
    return bool(_CHAIN_OPEN_TAIL_RE.search(_cut_clause(text).rstrip()))


def _weighted_chain_body(lines, start, after_label):
    head = _WEIGHTED_SENTENCE_END_RE.split(after_label, maxsplit=1)[0]
    chunks = [head]
    opened = _line_opens_chain(head)
    for nxt in lines[start + 1:]:
        if not (_WEIGHTED_CONT_RE.match(nxt) or opened):
            break
        piece = _WEIGHTED_SENTENCE_END_RE.split(nxt, maxsplit=1)[0]
        chunks.append(piece)
        opened = _line_opens_chain(piece)
    body = "\n".join(chunks).lstrip()
    body = _cut_clause(body)
    return _WEIGHTED_FIRST_CONN_RE.sub("", body, count=1)


def _claimed_from_chain(body, first_sep=""):
    """返回 (用来核对的终值, 需核对的其它纯数字段)。无法解析则为 (None, [])。"""
    pairs = _split_chain_segments(body)
    while pairs and not pairs[0][1].strip():
        pairs.pop(0)
    if not pairs:
        return None, []
    if first_sep and pairs[0][0] == "":
        pairs[0] = (first_sep, pairs[0][1])
    parsed = [(sep, seg, _parse_plain_number(seg)) for sep, seg in pairs]
    exact = None
    exact_first = True
    compare = []
    last_val = None
    for sep, seg, val in parsed:
        if val is None:
            continue
        is_approx = sep == "≈"
        if is_approx and exact is not None and _is_rounding_of(exact, val, seg):
            last_val = exact
            continue
        if is_approx and exact is None:
            last_val = val
            compare.append(val)
            if exact_first:
                exact = val
            continue
        last_val = val
        compare.append(val)
        exact = val
        exact_first = False
    if last_val is None:
        return None, []
    plains = [v for v in compare[:-1]]
    return last_val, plains


def check_weighted(lines):
    """报了五项评分时核对加权。返回 (五项分, 账面加权, 应得加权) 或 None。"""
    score_events = _collect_score_groups(lines)
    claim_events = []
    resp_events = []
    for i, line in enumerate(lines):
        if _GRADE_INTERVAL_RE.search(line) and not _WEIGHTED_LABEL_RE.search(line):
            continue
        for m in _WEIGHTED_LABEL_RE.finditer(line):
            rest = line[m.end():]
            pos = (i, m.start())
            resp_rest = _leading_respectively(rest)
            if resp_rest is not None:
                body = _weighted_chain_body(lines, i, resp_rest)
                values = _parse_resp_values(body)
                if not values:
                    continue
                resp_events.append((pos, values))
                continue
            skipped = _skip_modifiers(rest)
            if _is_weight_description(skipped):
                continue
            body = _weighted_chain_body(lines, i, skipped)
            lead = skipped.lstrip()
            first_sep = lead[0] if lead and lead[0] in _CHAIN_OPS else ""
            claimed, plains = _claimed_from_chain(body, first_sep=first_sep)
            if claimed is None:
                continue
            claim_events.append((pos, claimed, plains))
    if not score_events:
        return None
    assigned = {gi: [] for gi in range(len(score_events))}
    for pos, values in resp_events:
        p_start, p_end = _paragraph_bounds(lines, pos[0])
        before = [
            gi for gi, (sp, ep, scores, weights) in enumerate(score_events)
            if sp < pos and p_start <= sp[0] < p_end
        ]
        if len(before) != len(values):
            before = [gi for gi, (sp, ep, scores, weights) in enumerate(score_events) if sp < pos]
        if len(before) != len(values):
            gi = before[0] if before else 0
            scores, weights = score_events[gi][2], score_events[gi][3]
            expect = _expect_weighted(scores, weights)
            return scores, expect + 1.0, expect
        for gi, val in zip(before, values):
            assigned[gi].append((val, []))
    last_window = []
    last_scores = score_events[-1][2]
    last_expect = _expect_weighted(last_scores, score_events[-1][3])
    for gi, (sp, ep, scores, weights) in enumerate(score_events):
        expect = _expect_weighted(scores, weights)
        next_start = score_events[gi + 1][0] if gi + 1 < len(score_events) else None
        if assigned[gi]:
            window = assigned[gi]
        else:
            window = [
                (c, p) for (cp, c, p) in claim_events
                if cp >= ep and (next_start is None or cp < next_start)
            ]
        last_window = window
        last_scores, last_expect = scores, expect
        if not window:
            return scores, None, expect
        for claimed, plains in window:
            for value in (claimed, *plains):
                if abs(value - expect) > 0.005:
                    return scores, value, expect
    last_claim = last_window[-1][0]
    return last_scores, last_claim, last_expect


def weighted_error(scores, claimed, expect):
    """五项分已抽出时，缺加权或加权算错都要报。"""
    if claimed is None:
        return f"报了五项分 {scores} 但没有写出加权分，应得 {expect:.2f}"
    if abs(claimed - expect) > 0.005:
        return f"加权与五项分不一致：{scores} 应得 {expect:.2f}，写的是 {claimed:.2f}"
    return None


def mermaid_blocks(text):
    return MERMAID_RE.findall(text)


def check_mermaid_edges(text):
    """每条边的标签只能是三种，线型要和标签一致。返回问题说明。"""
    problems = []
    for block in mermaid_blocks(text):
        for arrow, label in LABELED_EDGE_RE.findall(block):
            label = label.strip()
            if label not in EDGE_LABELS:
                problems.append(f"边标签「{label}」不在直接前置、同章衔接、常考组合之中")
                continue
            if label in SOLID_LABELS and arrow != "-->":
                problems.append(f"「{label}」要用实线 -->")
            if label == "常考组合" and arrow != "-.->":
                problems.append("「常考组合」要用虚线 -.->")
        leftover = LABELED_EDGE_RE.sub("", block)
        if UNLABELED_EDGE_RE.search(leftover):
            problems.append("mermaid 里有未标注类型的边")
    return problems


def chapter_mermaid(text):
    """标记行之后的第一张 mermaid。没有标记则返回 None。"""
    idx = text.find(PEP_CHEM_BX1_CH1_MARKER)
    if idx < 0:
        return None
    found = MERMAID_RE.search(text[idx:])
    if not found:
        return ""
    return found.group(1)


def check_mermaid_style(text):
    """概念、技能、实验、后续章节用固定配色，避免默认灰图。"""
    problems = []
    for block in mermaid_blocks(text):
        if "classDef concept " not in block:
            problems.append("mermaid 缺少概念配色 classDef concept")
        if "classDef skill " not in block:
            problems.append("mermaid 缺少技能配色 classDef skill")
        if "（实验）" in block and "classDef experiment " not in block:
            problems.append("有实验节点但缺少 classDef experiment")
        if "第二章" in block and "classDef later " not in block:
            problems.append("有后续章节节点但缺少 classDef later")
        if "（概念）" in block and ":::concept" not in block:
            problems.append("概念节点未标 :::concept")
        if "（技能）" in block and ":::skill" not in block:
            problems.append("技能节点未标 :::skill")
        if "（实验）" in block and ":::experiment" not in block:
            problems.append("实验节点未标 :::experiment")
    return problems


def mermaid_node_labels(block):
    """Only real node definitions. Comments, directives, and edge labels are ignored."""
    labels = []
    for raw in block.splitlines():
        line = raw.strip()
        if not line or line.startswith("%%"):
            continue
        comment_at = line.find("%%")
        if comment_at >= 0:
            line = line[:comment_at].rstrip()
            if not line:
                continue
        if NODE_DIRECTIVE_RE.match(line):
            continue
        line = LABELED_EDGE_RE.sub(" ", line)
        line = EDGE_TEXT_RE.sub(" ", line)
        pos = 0
        while pos < len(line):
            found = _NODE_ID_RE.search(line, pos)
            if not found:
                break
            inner, consumed = _shape_label_at(line, found.end())
            if inner is None:
                pos = found.start() + 1
                continue
            inner = inner.strip()
            if inner:
                labels.append(inner)
            pos = consumed
    return labels


def _shape_label_at(line, start):
    rest = line[start:]
    for opener, closer in _NODE_SHAPES:
        if not rest.startswith(opener):
            continue
        inner_at = start + len(opener)
        if inner_at >= len(line):
            continue
        quote = line[inner_at] if line[inner_at] in "\"'" else ""
        if quote:
            end_quote = line.find(quote, inner_at + 1)
            if end_quote < 0 or not line.startswith(closer, end_quote + 1):
                continue
            return line[inner_at + 1:end_quote], end_quote + 1 + len(closer)
        close_at = line.find(closer, inner_at)
        if close_at < 0:
            continue
        return line[inner_at:close_at], close_at + len(closer)
    return None, start


def _chem_topic_entries():
    import nodes
    path = nodes.NODES_DIR / "chemistry.md"
    if not path.is_file():
        return []
    entries, _problems = nodes.parse_lines(path.name, path.read_text(encoding="utf-8"))
    return entries


def _allowed_labels_for_required(required, entries):
    allowed = {required}
    exact = []
    owned = []
    for standard, aliases, _chapter in entries:
        if standard == required:
            exact.append((standard, aliases))
        elif _standard_owns_required(standard, required):
            owned.append((standard, aliases))
    chosen = exact[0] if exact else (owned[0] if len(owned) == 1 else None)
    if chosen:
        standard, aliases = chosen
        allowed.add(standard)
        required_set = set(PEP_CHEM_BX1_CH1_REQUIRED)
        for alias in aliases:
            if alias in required_set and alias != required:
                continue
            allowed.add(alias)
    return allowed


def _standard_owns_required(standard, required):
    if standard.startswith(required):
        return True
    return required in (part for part in CANON_PART_RE.split(standard) if part)


def _normalize_label_text(label):
    text = str(label or "").strip().strip("`")
    text = text.replace("`", "")
    text = HTML_BR_RE.sub("\n", text)
    text = text.replace("\\n", "\n")
    text = HTML_TAG_RE.sub("", text)
    text = EMOJI_RE.sub("", text).strip()
    while True:
        stripped = TRAILING_PAREN_RE.sub("", text).strip()
        if stripped == text:
            break
        text = stripped
    return text


def _label_cores(label):
    text = _normalize_label_text(label)
    cores = set()
    if not text:
        return cores
    cores.add(text)
    for chunk in text.split("\n"):
        chunk = chunk.strip()
        if chunk:
            cores.add(chunk)
        for token in NODE_TOKEN_SPLIT_RE.split(chunk):
            token = token.strip()
            if token:
                cores.add(token)
    return cores


def _label_satisfies(label, allowed):
    return bool(_label_cores(label) & allowed)


def check_pep_chem_chapter(text):
    """整章图标记出现时，核这一章的节点是否齐全，并拒绝电石题里的物质。"""
    block = chapter_mermaid(text)
    if block is None:
        return []
    if block == "":
        return ["写了人教版化学必修第一册（2019）第一章的整章图标记，但后面没有 mermaid"]
    problems = []
    labels = mermaid_node_labels(block)
    entries = _chem_topic_entries()
    allowed_by_name = {
        name: _allowed_labels_for_required(name, entries) for name in PEP_CHEM_BX1_CH1_REQUIRED
    }

    def covers(label, name):
        return _label_satisfies(label, allowed_by_name[name])

    missing = [name for name in PEP_CHEM_BX1_CH1_REQUIRED if not any(covers(label, name) for label in labels)]
    if missing:
        problems.append("这一章整章图缺少节点：" + "、".join(missing))
    stuffed = [
        label for label in labels
        if sum(1 for name in PEP_CHEM_BX1_CH1_REQUIRED if covers(label, name)) > MAX_REQUIRED_NAMES_PER_NODE
    ]
    if stuffed:
        problems.append("整章图把过多必需节点塞进了同一个节点")
    covering = [label for label in labels if any(covers(label, name) for name in PEP_CHEM_BX1_CH1_REQUIRED)]
    if covering and len(covering) < MIN_REQUIRED_NODE_LABELS:
        problems.append("整章图把必需节点收进了过少的节点")
    present = [name for name in PEP_CHEM_BX1_CH1_FORBIDDEN if any(name in label for label in labels)]
    if present:
        problems.append("这一章整章图写入了题目物质：" + "、".join(present))
    return problems


STUDY_STATES = ("章览", "诊断", "节点", "章末")
STUDY_LABEL_RE = re.compile(r"^【模式：自学 · 状态：([^·】]+?)(?: · 节点：([^】]+))?】\s*$")
SLOT_MARKERS = (
    "一句话定义", "为什么重要", "最小例子", "易错点",
    "易混辨析", "判别自测", "拓展入口",
)
QUESTION_LINE_RE = re.compile(r"^\s*(?:（\d+）|\(\d+\)|\d+[.、．])")
STEP_LINE_RE = re.compile(r"^\s*(Step\s*[1-7]|第[一二三四五六七1-7]步)\s*$")
_SLOT_ALT = "|".join(re.escape(name) for name in SLOT_MARKERS)
SLOT_HEAD_RE = re.compile(
    rf"^\s*(?:[-*]\s+|\d+[.、．]\s*)?(?:\*\*)?({_SLOT_ALT})(?:\*\*)?\s*(?:[：:](.*))?$"
)
SLOT_HEAD_BOLD_COLON_RE = re.compile(
    rf"^\s*(?:[-*]\s+|\d+[.、．]\s*)?\*\*({_SLOT_ALT})\s*[：:](.*)\*\*\s*$"
)
TOPO_HEAD_RE = re.compile(r"^\s*(拓扑学习顺序|拓扑顺序)")
JUDGE_HEAD_RE = re.compile(r"^\s*(判定：|判定结果|判定:)")
REPAIR_HEAD_RE = re.compile(r"^\s*补步(?:\s*[：:—–-]|$)")
NEXT_CH_HEAD_RE = re.compile(r"^\s*下一章")
DASH_ITEM_RE = re.compile(r"^\s*-\s+\S")
STAR_ITEM_RE = re.compile(r"^\s*\*\s+\S")
NUM_ITEM_RE = re.compile(r"^\s*\d+[.、．]\s+\S")
INLINE_QNUM_RE = re.compile(r"（\d+）|\(\d+\)")
LEAD_QNUM_RE = re.compile(r"^\s*\d+[.、．]")
NEXT_Q_RE = re.compile(r"^\s*(下一题|再来一题|下一道)")
ARROW_SPLIT_RE = re.compile(r"\s*(?:→|->|⟶)\s*")
NUMBERED_Q_LINE_RE = re.compile(r"^\s*(?:（\d+）|\(\d+\)|\d+[.、．]).*[？?]\s*$")
QMARK_RE = re.compile(r"[？?]")
TOPO_PLACEHOLDERS = ("略", "待补", "之后再说")
EXTEND_MARK_RE = re.compile(r"L3|拓展|延伸")
NOTEBOOK_HEADING = "【错题本条目】"
UNCOVERED_MARK = "此章正典待补录"
RULE_STUDY = "modes/self-study.md"
RULE_LABEL = "SKILL.md「全局模式」状态标签"


def canon_display(name):
    """节点名落到任一科目的正典显示名时返回该显示名，否则空串。"""
    import nodes
    text = str(name or "").strip()
    if not text:
        return ""
    for subject in nodes.SUBJECTS:
        _subject, standard, _raw, hit = nodes.normalize(subject, text)
        if hit and standard:
            return standard
    return ""


def _slot_header(line):
    """行首槽名（可带列表/编号/加粗）及冒号后的同行内容。"""
    bold = SLOT_HEAD_BOLD_COLON_RE.match(line)
    if bold:
        return bold.group(1), (bold.group(2) or "").strip()
    match = SLOT_HEAD_RE.match(line)
    if not match:
        return None
    return match.group(1), (match.group(2) or "").strip()


def _slot_names_on_line(line):
    return [name for name in SLOT_MARKERS if name in line]


def _following_dash_list(lines, index):
    nxt = index + 1
    if nxt < len(lines) and not lines[nxt].strip():
        nxt += 1
    return nxt < len(lines) and DASH_ITEM_RE.match(lines[nxt])


def has_study_structure(text):
    """E17a：这一轮是自学结构，不能凭「难度：」免标。"""
    if "【模式：自学" in text or "快诊" in text:
        return True
    lines = text.splitlines() or [""]
    for index, line in enumerate(lines):
        if STEP_LINE_RE.match(line) or _slot_header(line):
            return True
        if TOPO_HEAD_RE.match(line) or JUDGE_HEAD_RE.match(line) or REPAIR_HEAD_RE.match(line):
            return True
        if NEXT_CH_HEAD_RE.match(line) and _following_dash_list(lines, index):
            return True
    return False


def _label_elsewhere(lines):
    return any(STUDY_LABEL_RE.match(line.strip()) for line in lines[1:])


def _question_sentence_count(text):
    pieces = QMARK_RE.split(text)
    return sum(1 for piece in pieces[:-1] if piece.strip())


def _selftest_has_question(body):
    if any(QUESTION_LINE_RE.match(line) for line in body.splitlines()):
        return True
    return _question_sentence_count(body) >= 1


def _collect_slot_entries(lines):
    crowded = []
    entries = []
    for index, line in enumerate(lines):
        if len(_slot_names_on_line(line)) >= 2:
            crowded.append(index)
        header = _slot_header(line)
        if header:
            entries.append((index, header[0], header[1]))
    return entries, crowded


def _slot_body(lines, entries, idx):
    line_i, _name, rest = entries[idx]
    end = entries[idx + 1][0] if idx + 1 < len(entries) else len(lines)
    chunks = [rest] if rest else []
    for raw in lines[line_i + 1:end]:
        if STEP_LINE_RE.match(raw):
            continue
        if raw.strip():
            chunks.append(raw.strip())
    return "\n".join(chunks).strip()


def _seven_slot_problem(lines):
    entries, crowded = _collect_slot_entries(lines)
    if crowded:
        return "同一行出现了两个及以上槽名"
    names = [item[1] for item in entries]
    if names != list(SLOT_MARKERS):
        return "节点轮既不是七槽，也不是补步问答"
    for idx, (_line_i, name, _rest) in enumerate(entries):
        body = _slot_body(lines, entries, idx)
        if not body:
            return f"「{name}」槽为空"
        if name == "判别自测" and not _selftest_has_question(body):
            return "判别自测里没有题"
    return None


def _repair_problem(lines, text):
    if any(_slot_header(line) for line in lines):
        return "补步轮不要写七槽"
    if any(STEP_LINE_RE.match(line) for line in lines):
        return "补步轮不要写 Step 行"
    if _question_sentence_count(text) != 1:
        return "补步轮只能问一个问题"
    return None


def _topo_placeholder(text):
    stripped = text.strip().strip("。．.！!").strip()
    if not stripped:
        return True
    if stripped in TOPO_PLACEHOLDERS:
        return True
    return any(stripped.startswith(token) for token in TOPO_PLACEHOLDERS)


def _topo_nodes_from_text(text):
    stripped = text.strip().strip("。．.")
    if not stripped or _topo_placeholder(stripped):
        return []
    if ARROW_SPLIT_RE.search(stripped):
        parts = [part.strip() for part in ARROW_SPLIT_RE.split(stripped) if part.strip()]
    elif "、" in stripped:
        parts = [part.strip() for part in stripped.split("、") if part.strip()]
    else:
        parts = [stripped]
    nodes = []
    for part in parts:
        part = part.strip().strip("。．.")
        if part and not _topo_placeholder(part):
            nodes.append(part)
    return nodes


def _item_text(line):
    if NUM_ITEM_RE.match(line):
        return NUM_ITEM_RE.sub("", line, count=1).strip()
    return re.sub(r"^\s*[-*]\s+", "", line).strip()


def _topo_node_count(lines):
    for index, line in enumerate(lines):
        match = TOPO_HEAD_RE.match(line)
        if not match:
            continue
        rest = line[match.end():].strip().lstrip("：:").strip()
        nodes = _topo_nodes_from_text(rest)
        cursor = index + 1
        while cursor < len(lines):
            nxt = lines[cursor]
            if not nxt.strip():
                cursor += 1
                continue
            if NUM_ITEM_RE.match(nxt) or DASH_ITEM_RE.match(nxt) or STAR_ITEM_RE.match(nxt):
                nodes.extend(_topo_nodes_from_text(_item_text(nxt)))
                cursor += 1
                continue
            break
        return len(nodes)
    return 0


def _diagnosis_question_count(lines):
    judge = {index for index, line in enumerate(lines) if JUDGE_HEAD_RE.match(line)}
    numbered = 0
    next_extra = 0
    for index, line in enumerate(lines):
        if index in judge:
            continue
        numbered += len(INLINE_QNUM_RE.findall(line))
        stripped = line.lstrip()
        if LEAD_QNUM_RE.match(line) and not INLINE_QNUM_RE.match(stripped):
            numbered += 1
        if NEXT_Q_RE.match(line) and not INLINE_QNUM_RE.search(line) and not LEAD_QNUM_RE.match(line):
            next_extra += 1
    if numbered:
        return numbered + next_extra
    body = "\n".join(line for index, line in enumerate(lines) if index not in judge)
    questions = _question_sentence_count(body)
    unmarked_next = 0
    for index, line in enumerate(lines):
        if index in judge:
            continue
        if NEXT_Q_RE.match(line) and not QMARK_RE.search(line):
            unmarked_next += 1
    return questions + unmarked_next


def _has_summary_heading(lines):
    for line in lines:
        match = HEADING_RE.match(line)
        if not match:
            continue
        num = fullwidth_int(match.group(1))
        if 1 <= num <= 9 and match.group(2).startswith(SUMMARY_HEADINGS[num - 1]):
            return True
    return False


def check_study(text):
    """自学红线。返回 (severity, code, lineno, message, hint)。"""
    text = str(text or "").lstrip("\ufeff")
    issues = []
    lines = text.splitlines() or [""]
    first = lines[0].strip()
    label = STUDY_LABEL_RE.match(first)
    state = node_name = None
    if label:
        state, node_name = label.group(1).strip(), (label.group(2) or "").strip()
        if state not in STUDY_STATES:
            issues.append(("ERROR", "E17b", 1,
                           f"状态词「{state}」不在封闭集（章览、诊断、节点、章末）",
                           "改成封闭集里的状态词后重发"))
            state = None
    elif first.startswith("【模式：自学 · 状态："):
        issues.append(("ERROR", "E17b", 1, "状态词不在封闭集（章览、诊断、节点、章末）",
                       "改成封闭集里的状态词后重发"))
    elif first.startswith(("难度：", "难度:")):
        if has_study_structure(text):
            message = "自学轮缺状态标签"
            if _label_elsewhere(lines):
                message += "；标签必须写在第一行"
            issues.append(("ERROR", "E17a", 1, message, "补状态标签重发"))
    else:
        message = "自学轮缺状态标签"
        if _label_elsewhere(lines):
            message += "；标签必须写在第一行"
        issues.append(("ERROR", "E17a", 1, message, "补状态标签重发"))

    if state == "节点":
        hit = canon_display(node_name)
        if not hit:
            if UNCOVERED_MARK in text:
                issues.append(("WARN", "E17c", 1,
                               f"节点名「{node_name}」未命中正典，{UNCOVERED_MARK}",
                               "正典补录前保留这句标注"))
            else:
                issues.append(("ERROR", "E17c", 1,
                               f"节点名「{node_name or '（空）'}」未命中正典显示名",
                               "改为正典显示名后重发；本章若未覆盖，正文标注「此章正典待补录」"))

    mermaid_at = next((index for index, line in enumerate(lines, 1) if "```mermaid" in line), None)
    if state in ("诊断", "节点", "章末") and mermaid_at:
        issues.append(("ERROR", "R1a", mermaid_at, "非章览轮出现了 mermaid 整章图",
                       "删掉 mermaid；章末预告改成文本列表"))
    if state == "章览" and mermaid_at is None:
        issues.append(("WARN", "R1b", 1, "章览轮缺少整章 mermaid", "补上整章图"))

    notebook_at = next((index for index, line in enumerate(lines, 1) if NOTEBOOK_HEADING in line), None)
    if notebook_at:
        blob = "\n".join(lines[notebook_at - 1:])
        if EXTEND_MARK_RE.search(blob):
            issues.append(("ERROR", "R2", notebook_at, "错题本条目含拓展标记词（L3、拓展或延伸）",
                           "拓展只留在节点第七槽，不要写入错题本"))

    if state and _has_summary_heading(lines):
        issues.append(("ERROR", "E18", 1, "自学轮不要套九段标题",
                       "自学轮按章览/诊断/七槽或补步/章末写，不要套完整模式九段标题"))

    if state == "章览":
        if _topo_node_count(lines) < 2:
            issues.append(("ERROR", "E18", 1, "章览缺少拓扑学习顺序",
                           "写出拓扑学习顺序，并用箭头、顿号或列表给出至少两个节点"))
        for index, line in enumerate(lines, 1):
            if NUMBERED_Q_LINE_RE.match(line):
                issues.append(("ERROR", "E18", index, "章览不出编号题",
                               "章览只写拓扑和入口；编号题留给诊断轮"))
                break
    if state == "诊断":
        count = _diagnosis_question_count(lines)
        judged = any(JUDGE_HEAD_RE.match(line) for line in lines)
        has_slot = any(_slot_header(line) for line in lines)
        if judged:
            ok = count == 0
        else:
            ok = count == 1 and not has_slot
        if not ok:
            issues.append(("ERROR", "E18", 1,
                           "诊断轮须是恰一题的出题形态，或不再出题的判定形态",
                           "出题轮只留一道题；判定轮写判定、记录和下一跳，不要出新题"))
    if state == "节点":
        if any(REPAIR_HEAD_RE.match(line) for line in lines):
            problem = _repair_problem(lines, text)
        else:
            problem = _seven_slot_problem(lines)
        if problem:
            issues.append(("ERROR", "E18", 1, problem,
                           "按七槽输出，或在连错两次后只写补步问答"))
    if state == "章末":
        has_list = any(
            NEXT_CH_HEAD_RE.match(line) and _following_dash_list(lines, index)
            for index, line in enumerate(lines)
        )
        if not has_list:
            issues.append(("ERROR", "E18", 1, "章末预告不是文本列表",
                           "用「下一章」加紧随其后的「- 」列表，不要画图"))

    for problem in check_mermaid_edges(text):
        issues.append(("ERROR", "E11", mermaid_at or 1, problem, "边标签只用直接前置、同章衔接、常考组合，并配上对应线型"))
    for problem in check_mermaid_style(text):
        issues.append(("ERROR", "E13", mermaid_at or 1, problem, "补上概念、技能、实验、后续章节的配色"))
    for problem in check_pep_chem_chapter(text):
        issues.append(("ERROR", "E12", mermaid_at or 1, problem, "整章图按人教版化学必修第一册第一章的节点名单改"))
    weighted = check_weighted(lines)
    if weighted:
        scores, claimed, expect = weighted
        msg = weighted_error(scores, claimed, expect)
        if msg:
            issues.append(("ERROR", "E8", 1, msg, "按 0.30、0.25、0.20、0.15、0.10 重算"))
    return issues


def check(mode, text, no_student_answer, subject=None):
    issues = []  # (severity, code, message, evidence lineno or None)
    text = str(text or "").lstrip("\ufeff")

    lines = text.splitlines()
    has_level = any(lv in text for lv in DIFFICULTY_LEVELS)

    if not has_level:
        issues.append(("WARN", "W6",
                       "未检出难度等级（基础/中等/压轴/竞赛）；科目确认轮或同一题后续轮次（难度未变不重报）可忽略", None))

    for ln in check_bad_difficulty(lines):
        issues.append(("ERROR", "E5" if mode == "socratic" else "E7",
                       f"难度用词非法（第 {ln[0]} 行：「{ln[1][:30]}」），只能用 基础/中等/压轴/竞赛", ln[0]))

    if mode == "socratic":
        for pat, why in ANSWER_LEAK_PATTERNS:
            for ln in hits(pat, text):
                issues.append(("ERROR", "E1", f"引导模式疑似泄露答案（{why}，第 {ln[0]} 行：「{ln[1][:36]}」）", ln[0]))
        for ln in hits(r"^#{1,6}[^\n]*(难度判断|解题思维链|一题多解|解法对比|错因诊断|错题本沉淀)", text):
            issues.append(("ERROR", "E2", f"引导模式输出了总结阶段标题（第 {ln[0]} 行：「{ln[1][:30]}」）", ln[0]))
        if hits(r"【错题本条目】", text):
            issues.append(("ERROR", "E3", "引导模式输出了错题本条目，只能一句话提示「完成后可生成」", None))
        elif re.search(r"变式题", text) and re.search(r"变式答案", text):
            issues.append(("ERROR", "E3", "引导模式输出了变式题和变式答案", None))
        if hits(r"加权|五项|评分(?!标准)", text) or WEIGHTED_EXPANSION_RE.search(text) or SCORES_RE.search(text):
            issues.append(("ERROR", "E4", "引导模式报了五项分数或加权分；默认只给等级和理由", None))
        n_questions = text.count("？") + text.count("?")
        if n_questions > 2:
            issues.append(("WARN", "W1", f"问号共 {n_questions} 个；引导模式一轮只问一个问题（核对/确认除外）", None))
        for pat, name in FORMULA_PATTERNS:
            for ln in hits(pat, text):
                issues.append(("WARN", "W2", f"疑似先说破关键公式（{name}，第 {ln[0]} 行）", ln[0]))
        if re.search(r"【学段常规】|【竞赛】|【大学知识下放", text):
            issues.append(("WARN", "W3", "引导模式出现一题多解标注；多解只在完整模式输出", None))
    else:
        missing = check_summary_headings(lines)
        if missing:
            names = "、".join(f"{n}.{SUMMARY_HEADINGS[n-1]}" for n in missing)
            issues.append(("ERROR", "E6",
                           f"总结格式缺标题：{names}；不适用也要保留标题并写原因", None))
        w = check_weighted(lines)
        if w:
            scores, claimed, expect = w
            msg = weighted_error(scores, claimed, expect)
            if msg:
                issues.append(("ERROR", "E8", msg, None))
        if not mermaid_blocks(text):
            issues.append(("ERROR", "E10", "完整模式或总结阶段缺少本题 mermaid 图谱", None))
        if re.search(r"超纲|【大学知识下放", text) and not re.search(r"慎用|不给分", text):
            issues.append(("WARN", "W4", "出现超纲标注但未附「考试慎用，可能不给分」提醒", None))
        for ln in hits(r"粗心|马虎", text):
            issues.append(("WARN", "W5", f"错因写「{ln[1][:12]}…」；要给具体改进动作，不要只说粗心（第 {ln[0]} 行）", ln[0]))
        if subject == "math":
            has_marker = any(marker in text for marker in VERIFY_MARKERS)
            if not has_marker:
                if VERIFY_LOOSE_RE.search(text):
                    issues.append(("ERROR", "E14",
                                   f"机验标记句式不对；只能用「{VERIFY_MARKER_HINT}」之一", None))
                else:
                    issues.append(("ERROR", "E14",
                                   f"数学完整模式缺少机验标记；第 2 节末尾必须写「{VERIFY_MARKER_HINT}」之一", None))

    for problem in check_mermaid_edges(text):
        issues.append(("ERROR", "E11", problem, None))
    for problem in check_mermaid_style(text):
        issues.append(("ERROR", "E13", problem, None))
    for problem in check_pep_chem_chapter(text):
        issues.append(("ERROR", "E12", problem, None))

    if no_student_answer and hits(r"我的错误[：:]", text):
        issues.append(("ERROR", "E9",
                       "上下文没有学生作答却写了「我的错误：」；只能写「典型易错（推测）」", None))

    rule_of = {"E1": RULE_GUIDED, "E2": RULE_SUMMARY_FMT, "E3": RULE_GUIDED + " " + RULE_NOTEBOOK,
               "E4": RULE_GUIDED, "E5": RULE_DIFFICULTY, "E6": RULE_SUMMARY_FMT, "E7": RULE_DIFFICULTY,
               "E8": RULE_DIFFICULTY + " 计分规则", "E9": RULE_NOTEBOOK,
               "E10": RULE_SUMMARY_FMT + " 第 9 节本题图谱",
               "E11": "modes/chapter-map.md「边类型」",
               "E13": "modes/chapter-map.md「节点配色」",
               "E12": "modes/chapter-map.md 人教版化学必修第一册（2019）第一章",
               "E14": RULE_VERIFY,
               "W1": RULE_GUIDED, "W2": "各科 reference「苏格拉底不要先说的内容」", "W3": RULE_GUIDED,
               "W4": "modes/full.md「核心规则」", "W5": "modes/records.md「错因与错题本」", "W6": RULE_DIFFICULTY}
    return [(sev, code, msg, rule_of.get(code, "")) for sev, code, msg, _ in issues]


def _read_reply(path):
    if path == "-":
        return sys.stdin.read()
    with open(path, encoding="utf-8") as handle:
        return handle.read()


def _print_study(path, issues):
    for sev, code, lineno, message, hint in issues:
        print(f"{path}:{lineno or 1} {code} [{sev}] {message} 修复：{hint}")
    errors = [item for item in issues if item[0] == "ERROR"]
    warns = [item for item in issues if item[0] == "WARN"]
    if errors:
        print(f"\n未通过：{len(errors)} 项 ERROR，修改后重检。")
        return 1
    if warns:
        print(f"\n通过（注意 {len(warns)} 项 WARN）。")
    else:
        print("通过。")
    return 0


def main():
    ap = argparse.ArgumentParser(description="回复守卫：发送前机检教学红线")
    ap.add_argument("reply", nargs="?", default=None, help="回复文本文件路径，- 表示 stdin")
    ap.add_argument("--mode", required=True, choices=["socratic", "full", "summary", "study"],
                    help="socratic=引导模式；full/summary=完整模式与总结阶段；study=自学模式")
    ap.add_argument("--dir", default=None, help="自学模式：逐个检查目录里的 txt")
    ap.add_argument("--no-student-answer", action="store_true",
                    help="上下文中没有学生作答（拦截编造「我的错误」）")
    ap.add_argument("--subject", choices=["math"],
                    help="科目；填 math 时，完整模式会额外要求第 2 节末尾出现固定机验标记")
    args = ap.parse_args()

    if args.mode == "study" and args.dir:
        from pathlib import Path
        folder = Path(args.dir)
        if not folder.is_dir():
            sys.exit(f"不是目录：{args.dir}")
        worst = 0
        files = sorted(folder.glob("*.txt"))
        if not files:
            sys.exit(f"目录里没有 txt：{args.dir}")
        for path in files:
            text = path.read_text(encoding="utf-8")
            if not text.strip():
                print(f"{path}:1 E17a [ERROR] 回复为空 修复：补状态标签重发")
                worst = 1
                continue
            code = _print_study(path, check_study(text))
            worst = max(worst, code)
        sys.exit(worst)

    if not args.reply:
        sys.exit("缺少回复文件。自学目录检查请加 --dir。")

    text = _read_reply(args.reply)
    if not text.strip():
        sys.exit("回复为空。")

    if args.mode == "study":
        sys.exit(_print_study(args.reply, check_study(text)))

    mode = "full" if args.mode == "summary" else args.mode
    issues = check(mode, text, args.no_student_answer, args.subject)

    errors = [i for i in issues if i[0] == "ERROR"]
    warns = [i for i in issues if i[0] == "WARN"]
    for sev, code, msg, rule in issues:
        print(f"[{sev}] {code} {msg}")
        if rule:
            print(f"     规则：{rule}")
    if errors:
        print(f"\n未通过：{len(errors)} 项 ERROR，修改后重检。")
        sys.exit(1)
    if warns:
        print(f"\n通过（注意 {len(warns)} 项 WARN）。")
    else:
        print("通过。")


if __name__ == "__main__":
    main()
