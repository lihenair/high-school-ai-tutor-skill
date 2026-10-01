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

DIFFICULTY_LEVELS = ("基础", "中等", "压轴", "竞赛")
WEIGHTS = (0.30, 0.25, 0.20, 0.15, 0.10)  # 各科五维权重相同，见各 reference
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


# 加权引入句上的链式运算符（与原先同一组）；续行只认行首的 = / ＝。
_WEIGHTED_CHAIN_OP_RE = re.compile(r"[=＝为是：:]")
_WEIGHTED_CONT_RE = re.compile(r"^\s*[=＝]")
_WEIGHTED_NUM_RE = re.compile(r"[0-9]+(?:\.[0-9]+)?")
_WEIGHTED_SENTENCE_END_RE = re.compile(r"[。！？]")
_WEIGHTED_ARITH = set("+-×x*·/÷()")


def _weighted_chain_text(lines, start):
    """引入行从「加权」起到句末，加上随后以 = 开头的续行。不扫回复其余部分。"""
    line = lines[start]
    label = line.find("加权")
    rest = line[label + len("加权"):] if label >= 0 else line
    rest = _WEIGHTED_SENTENCE_END_RE.split(rest, maxsplit=1)[0]
    chunks = [rest]
    for nxt in lines[start + 1:]:
        if not _WEIGHTED_CONT_RE.match(nxt):
            break
        chunks.append(_WEIGHTED_SENTENCE_END_RE.split(nxt, maxsplit=1)[0])
    return "\n".join(chunks)


def _final_chain_number(chain):
    """等号链的终值：仅当某段是独立数字（其后不再接运算）才采纳，并在此处截断。"""
    m = _WEIGHTED_CHAIN_OP_RE.search(chain)
    if not m:
        return None
    pos = m.start()
    while pos < len(chain):
        op = _WEIGHTED_CHAIN_OP_RE.search(chain, pos)
        if not op:
            return None
        k = op.end()
        while k < len(chain) and chain[k] in " \t\r\n":
            k += 1
        num = _WEIGHTED_NUM_RE.match(chain, k)
        if num is None:
            pos = op.end() + 1
            continue
        j = num.end()
        while j < len(chain) and chain[j] in " \t\r\n":
            j += 1
        if j < len(chain) and chain[j] in _WEIGHTED_ARITH:
            pos = j
            continue
        return float(num.group(0))
    return None


def check_weighted(lines):
    """报了五项评分时核对加权。返回 (五项分, 账面加权, 应得加权) 或 None。"""
    scores = claimed = None
    for i, line in enumerate(lines):
        m = SCORES_RE.search(line)
        if m:
            scores = [int(g) for g in m.groups()]
        if "加权" not in line:
            continue
        parsed = _final_chain_number(_weighted_chain_text(lines, i))
        if parsed is not None:
            claimed = parsed
    if scores is None:
        return None
    expect = round(sum(s * w for s, w in zip(scores, WEIGHTS)), 2)
    if claimed is None:
        return scores, None, expect
    return scores, claimed, expect


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


def looks_like_solving(text):
    """解题轮免标。七槽或判别自测出现时不再当成解题轮。"""
    if "判别自测" in text or "一句话定义" in text:
        return False
    first = next((line.strip() for line in text.splitlines() if line.strip()), "")
    return first.startswith("难度：") or first.startswith("难度:")


def question_lines(lines):
    numbered = [index for index, line in enumerate(lines, 1) if QUESTION_LINE_RE.match(line)]
    if numbered:
        return numbered
    return [index for index, line in enumerate(lines, 1) if ("？" in line or "?" in line)]


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
    elif not looks_like_solving(text):
        issues.append(("ERROR", "E17a", 1, "自学轮缺状态标签", "补状态标签重发"))

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

    slot_at = next((index for index, line in enumerate(lines, 1) if "判别自测" in line), None)
    if slot_at:
        end = len(lines) + 1
        for index in range(slot_at, len(lines)):
            if "拓展入口" in lines[index] or re.match(r"^Step\s*7\b", lines[index].strip()):
                end = index + 1
                break
        block = lines[slot_at - 1:end - 1]
        cursor = 0
        while cursor < len(block):
            if not QUESTION_LINE_RE.match(block[cursor]):
                cursor += 1
                continue
            nxt = cursor + 1
            while nxt < len(block) and not QUESTION_LINE_RE.match(block[nxt]):
                nxt += 1
            cursor = nxt

    if state == "章览" and "拓扑" not in text:
        issues.append(("ERROR", "E18", 1, "章览缺少拓扑学习顺序", "在整章图后写出拓扑学习顺序"))
    if state == "诊断":
        bodies = lines[1:]
        count = len(question_lines(bodies))
        judged = "判定" in text
        if judged and count == 0:
            pass
        elif not judged and count == 1:
            pass
        else:
            issues.append(("ERROR", "E18", 1,
                           "诊断轮须是恰一题的出题形态，或不再出题的判定形态",
                           "出题轮只留一道题；判定轮写判定、记录和下一跳，不要出新题"))
    if state == "节点":
        has_slots = all(marker in text for marker in SLOT_MARKERS)
        if not has_slots and "补步" not in text:
            issues.append(("ERROR", "E18", 1, "节点轮既不是七槽，也不是补步问答",
                           "按七槽输出，或在连错两次后只写补步问答"))
    if state == "章末":
        has_list = "下一章" in text and any(re.match(r"\s*-\s+\S", line) for line in lines)
        if not has_list:
            issues.append(("ERROR", "E18", 1, "章末预告不是文本列表", "用「下一章」加「- 」列表，不要画图"))

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
