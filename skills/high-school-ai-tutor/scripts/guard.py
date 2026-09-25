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
RULE_SUMMARY_FMT = "SKILL.md「题目完成后的总结格式」"
RULE_DIFFICULTY = "SKILL.md「难度总则」"
RULE_NOTEBOOK = "SKILL.md「错题本何时生成」「核心规则 6」"
RULE_VERIFY = "SKILL.md「数学机验」"
# 数学完整模式第 2 节末尾只能用这四句机验标记之一，方便家长和老师按固定规则筛。
VERIFY_MARKERS = ("已机验：通过", "未机验：无法解析", "未机验：未安装 SymPy", "此结果未通过机验")
# 出现「机验」二字但不是上面四句之一，视为句式漂移。
VERIFY_LOOSE_RE = re.compile(r"机验")

# 引导模式疑似给出最终结果的写法
ANSWER_LEAK_PATTERNS = [
    (r"答案[是为：:]\s*\S", "直接给出「答案为…」"),
    (r"(?:所以|因此|综上|故)[^。！？\n]{0,40}[=≤≥<>]\s*[-+]?[\d.]", "推到具体数值/不等式"),
    (r"(?:取值范围|解集|值域)[是为：:]\s*[{\[（(]?[-+]?[\d.]", "给出范围/解集"),
    (r"答案?是\s*[A-D]\b", "直接报选择题选项"),
]
# 引导模式不该先说破的关键公式（常见形状）
FORMULA_PATTERNS = [
    (r"[fF]\s*=\s*m\s*a\b", "牛顿第二定律"),
    (r"x\s*=\s*-\s*b\s*/\s*\(?\s*2\s*a", "抛物线对称轴公式"),
    (r"[pP]\s*V\s*=\s*n\s*R\s*T", "理想气体状态方程"),
    (r"v\s*=\s*v[₀0]\s*[+＋]", "匀变速速度公式"),
    (r"[sS]\s*=\s*v[₀0]\s*t\s*[+＋]", "匀变速位移公式"),
]
BAD_DIFFICULTY_RE = re.compile(r"偏难|偏易|中等偏上|中等偏下|较难|较易|很难|太?简单|太?容易")
HEADING_RE = re.compile(r"^#{2,3}\s*([0-9０-９])\s*[\.、．]\s*(\S+)")
SCORES_RE = re.compile(r"([1-5])\s*[、,，]\s*([1-5])\s*[、,，]\s*([1-5])\s*[、,，]\s*([1-5])\s*[、,，]\s*([1-5])\s*分")
WEIGHTED_EXPANSION_RE = re.compile(r"0\.30\s*[×x*]")
MERMAID_RE = re.compile(r"```mermaid\n(.*?)```", re.S)
LABELED_EDGE_RE = re.compile(r"(-\.->|-->)\s*\|([^|\n]+)\|")
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


def check_weighted(lines):
    """报了五项评分时核对加权。返回 (五项分, 账面加权, 应得加权) 或 None。"""
    scores = claimed = None
    for line in lines:
        m = SCORES_RE.search(line)
        if m:
            scores = [int(g) for g in m.groups()]
        if "加权" in line:
            nums = re.findall(r"[=＝为是：:]\s*([0-9]+\.[0-9]{2}|[0-9]+)", line)
            if nums:
                claimed = float(nums[-1])  # 展开式取最后一个等号后的总数
    if scores is None or claimed is None:
        return None
    return scores, claimed, round(sum(s * w for s, w in zip(scores, WEIGHTS)), 2)


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
        if re.search(r"-\.->|-->", leftover):
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


def check_pep_chem_chapter(text):
    """整章图标记出现时，核这一章的节点是否齐全，并拒绝电石题里的物质。"""
    block = chapter_mermaid(text)
    if block is None:
        return []
    if block == "":
        return ["写了人教版化学必修第一册（2019）第一章的整章图标记，但后面没有 mermaid"]
    problems = []
    missing = [name for name in PEP_CHEM_BX1_CH1_REQUIRED if name not in block]
    if missing:
        problems.append("这一章整章图缺少节点：" + "、".join(missing))
    present = [name for name in PEP_CHEM_BX1_CH1_FORBIDDEN if name in block]
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
    if "难度：" in text or "难度:" in text:
        return True
    return False


def question_lines(lines):
    numbered = [index for index, line in enumerate(lines, 1) if QUESTION_LINE_RE.match(line)]
    if numbered:
        return numbered
    return [index for index, line in enumerate(lines, 1) if ("？" in line or "?" in line)]


def check_study(text):
    """自学红线。返回 (severity, code, lineno, message, hint)。"""
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
            span = "\n".join(block[cursor:nxt])
            if not any(marker in span for marker in VERIFY_MARKERS):
                issues.append(("ERROR", "R3", slot_at + cursor, "判别自测有题目但没有机验标记句",
                               "在该题下补一句「已机验：通过 / 未机验：无法解析 / 未机验：未安装 SymPy / 此结果未通过机验」"))
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
        if abs(claimed - expect) > 0.005:
            issues.append(("ERROR", "E8", 1,
                           f"加权与五项分不一致：{scores} 应得 {expect:.2f}，写的是 {claimed:.2f}",
                           "按 0.30、0.25、0.20、0.15、0.10 重算"))
    return issues


def check(mode, text, no_student_answer, subject=None):
    issues = []  # (severity, code, message, evidence lineno or None)

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
        if hits(r"加权|五项|评分", text) or WEIGHTED_EXPANSION_RE.search(text) or SCORES_RE.search(text):
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
            if abs(claimed - expect) > 0.005:
                issues.append(("ERROR", "E8",
                               f"加权与五项分不一致：{scores} 应得 {expect:.2f}，写的是 {claimed:.2f}", None))
        if "```mermaid" not in text:
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
                                   "机验标记句式不对；只能用「已机验：通过 / 未机验：无法解析 / 未机验：未安装 SymPy / 此结果未通过机验」之一", None))
                else:
                    issues.append(("ERROR", "E14",
                                   "数学完整模式缺少机验标记；第 2 节末尾必须写「已机验：通过 / 未机验：无法解析 / 未机验：未安装 SymPy / 此结果未通过机验」之一", None))

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
               "E11": "SKILL.md「自学知识图谱」边标签",
               "E13": "SKILL.md「自学知识图谱」节点配色",
               "E12": "SKILL.md「自学知识图谱」人教版化学必修第一册（2019）第一章",
               "E14": RULE_VERIFY,
               "W1": RULE_GUIDED, "W2": "各科 reference「苏格拉底不要先说的内容」", "W3": RULE_GUIDED,
               "W4": "SKILL.md「核心规则 2」", "W5": "SKILL.md「错因与错题本」", "W6": RULE_DIFFICULTY}
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
