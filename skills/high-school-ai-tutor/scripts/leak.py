#!/usr/bin/env python3
"""E1 金标比对（引导模式兜底）。无金标时不要调用本模块。

字符串规范化与结论同义表、单位表都是封闭常量，见下方注释，不要按用例加特判。
"""
# ruff: noqa: SIM102

from __future__ import annotations

import os
import re
import unicodedata
from dataclasses import dataclass, field
from fractions import Fraction
from math import pi as PI

# ---------------------------------------------------------------------------
# 封闭表（规格 §3.2 / §3.3）
# ---------------------------------------------------------------------------

# 结论同义：只在「结论短语」比对时使用。左边是规范义项，右边是可互换写法。
# 「不相交」仅当句中出现同平面/共面时才并入「平行」。
CONCLUSION_SYNONYMS = {
    "平行": frozenset({"平行", "∥", "||"}),
    "不存在": frozenset({"不存在", "找不到", "没有这样的"}),
    "正确": frozenset({"正确", "成立"}),
    "错误": frozenset({"错误", "不对", "不成立"}),
    "是": frozenset({"是"}),
    "否": frozenset({"否"}),
    "能": frozenset({"能"}),
    "不能": frozenset({"不能"}),
}
# 「对」单独列出：过短，只在「是对的/完全对」这类谓语里认，不扫「对顶角」。
CONCLUSION_YES_SHORT = frozenset({"对", "没错"})

# 单位 → (量纲, 乘到 SI 的因子)。角度用弧度。
UNIT_TABLE = {
    "m/s": ("speed", Fraction(1)),
    "m/s^2": ("accel", Fraction(1)),
    "m/s²": ("accel", Fraction(1)),
    "km/h": ("speed", Fraction(1, 1) / Fraction(36, 10)),
    "m": ("length", Fraction(1)),
    "cm": ("length", Fraction(1, 100)),
    "km": ("length", Fraction(1000)),
    "s": ("time", Fraction(1)),
    "min": ("time", Fraction(60)),
    "h": ("time", Fraction(3600)),
    "kg": ("mass", Fraction(1)),
    "g": ("mass", Fraction(1, 1000)),
    "n": ("force", Fraction(1)),
    "j": ("energy", Fraction(1)),
    "w": ("power", Fraction(1)),
    "°": ("angle", "pi180"),
    "deg": ("angle", "pi180"),
    "rad": ("angle", "rad"),
}

CN_DIGIT = {
    "零": 0, "〇": 0, "一": 1, "二": 2, "两": 2, "三": 3, "四": 4,
    "五": 5, "六": 6, "七": 7, "八": 8, "九": 9,
}
CN_ORDINAL = {
    "第一": 1, "第二": 2, "第三": 3, "第四": 4, "第五": 5,
    "第六": 6, "第七": 7, "第八": 8, "第九": 9, "第十": 10,
}
EN_ORDINAL = {
    "first": 1, "second": 2, "third": 3, "fourth": 4, "fifth": 5,
    "sixth": 6, "seventh": 7, "eighth": 8, "ninth": 9, "tenth": 10,
}
CIRCLED = "①②③④⑤⑥⑦⑧⑨⑩⑪⑫⑬⑭⑮⑯⑰⑱⑲⑳"
JIAZI = "甲乙丙丁戊己庚辛壬癸"
LATIN_OPTS = "ABCDEFGHIJKLMNOPQRSTUVWXYZ"

SUP_TRANS = str.maketrans("⁰¹²³⁴⁵⁶⁷⁸⁹₊₋", "0123456789+-")
SUB_TRANS = str.maketrans("₀₁₂₃₄₅₆₇₈₉", "0123456789")
VULGAR = {
    "½": "1/2", "⅓": "1/3", "⅔": "2/3", "¼": "1/4", "¾": "3/4",
    "⅕": "1/5", "⅖": "2/5", "⅗": "3/5", "⅘": "4/5", "⅙": "1/6",
    "⅚": "5/6", "⅛": "1/8", "⅜": "3/8", "⅝": "5/8", "⅞": "7/8",
    "⁷⁄₄": "7/4",
}

REL_REPL = [
    (r"\\leq", "<="), (r"\\le\b", "<="), (r"\\geq", ">="), (r"\\ge\b", ">="),
    (r"\\neq", "!="), (r"\\ne\b", "!="), (r"\\lt", "<"), (r"\\gt", ">"),
    (r"\\in\b", "∈"), (r"\\cup", "∪"), (r"\\cap", "∩"), (r"\\infty", "∞"),
    (r"\\pi\b", "π"), (r"\\mid", "|"), (r"\\\{", "{"), (r"\\\}", "}"),
    ("≤", "<="), ("≥", ">="), ("≠", "!="), ("＜", "<"), ("＞", ">"),
    ("⩽", "<="), ("⩾", ">="),
]

STUDENT_RE = re.compile(
    r"你(?:写的|算的|得到|选了|的结果|刚才|认为|选的)|"
    r"your (?:answer|result|choice)"
)
FIRST_PERSON_RE = re.compile(
    r"(?:我|我们|老师)(?:算出来|选|倾向于|猜|得到|会得到)|"
    r"\bI (?:choose|got|think|guess)\b"
)
EVAL_RE = re.compile(r"完全正确|正确|没错|就是|很好|完全(?!平方)|✓|✅|(?<![对顶])对的|(?<![对顶])对了")
SUBST_RE = re.compile(r"代进去|代入|不妨把|plug in")
LEADING_RE = re.compile(
    r"会不会是|是不是|难道不是|难道.{0,24}不|对吗|对不对|right\?|"
    r"should be|is the (?:correct )?answer"
)
EITHER_RE = re.compile(r"还是| or ")
ORDINAL_SKIP_RE = re.compile(
    r"第\s*[0-9一二三四五六七八九十]+\s*(?:步|题|问|行|次|个选项|个)|"
    r"式\s*[（(]?\s*[0-9]+\s*[)）]?|"
    r"[0-9]+\s*(?:个|种|条)(?!选项)"
)
METHOD_RE = re.compile(
    r"怎么做|如何|哪几种方法|判定.{0,8}平行|平行有哪|公式是什么|"
    r"先把|先想|列出|形如|一般先|你会怎么|定理\？|定理?"
)
STEM_CUE_RE = re.compile(r"(?:题目|题干|已知|条件)(?:说|写|给|里)")
OPTION_NEUTRAL_RE = re.compile(
    r"选项\s*.{0,4}里|逐个看|各看一遍|先看\s*[A-D甲乙丙丁①-⑩]|"
    r"四个选项|到④逐条|compare [ab]|difference between|"
    r"先找第一处|你最先想排除哪一个"
)
CHOICE_ASSERT_RE = re.compile(
    r"(?:选(?!项)\s*[A-Da-d甲乙丙丁①-⑳]|答案(?:是|应该是|：|:)|正确选项|"
    r"正确的是|故选|应填|应选|肯定要选|才是对的|就是答案|肯定是真|是真命题|"
    r"fits here|the correct one|option\s+[a-d].*correct|"
    r"答案应该|做法是对的)"
)
ELIM_RE = re.compile(r"排除|都是错|都有错|都可以排除|都不是|只剩")
PROBE_RE = re.compile(r"(?:如果|取|试试|代回|左边|相等吗)")

FORCE_STDLIB_ENV = "E1_FORCE_STDLIB"


class GoldFileError(ValueError):
    """金标文件无效。由 CLI 转成 E1 错误，不得变成 Traceback。"""


@dataclass
class GoldSpec:
    answers: list[str]
    options: str = ""
    option_contents: dict[str, str] = field(default_factory=dict)


@dataclass
class LeakHit:
    lineno: int
    category: str
    snippet: str


def use_sympy():
    if os.environ.get(FORCE_STDLIB_ENV) == "1":
        return None
    try:
        import sympy
        return sympy
    except ImportError:
        return None


def load_gold_file(path):
    try:
        with open(path, encoding="utf-8") as handle:
            raw = handle.read()
    except OSError as exc:
        raise GoldFileError(str(exc)) from None
    except UnicodeError as exc:
        raise GoldFileError(str(exc)) from None
    return parse_gold_text(raw)


def parse_gold_text(raw):
    answers = []
    options = ""
    contents = {}
    for line in str(raw or "").splitlines():
        s = line.strip()
        if not s or s.startswith("#"):
            continue
        if ":" not in s:
            continue
        key, _, val = s.partition(":")
        key, val = key.strip(), val.strip()
        low = key.lower()
        if low == "answer":
            if val:
                answers.append(val)
        elif low == "options":
            options = val.replace(" ", "")
        elif low.startswith("option "):
            lab = key.split(None, 1)[1].strip()
            contents[_norm_label(lab)] = val
    if not answers:
        raise GoldFileError("没有 answer: 行")
    return GoldSpec(answers=answers, options=options, option_contents=contents)


def parse_options_from_stem(stem, labels):
    """从题干切 A. / A、 / (A) 选项正文。"""
    if not stem or not labels:
        return {}
    text = stem
    found = []
    for lab in labels:
        pats = [
            re.compile(rf"(?:^|[\s　;；]){re.escape(lab)}[.、．]\s*"),
            re.compile(rf"（{re.escape(lab)}）\s*"),
            re.compile(rf"\({re.escape(lab)}\)\s*"),
        ]
        best = None
        for pat in pats:
            m = pat.search(text)
            if m and (best is None or m.start() < best[0]):
                best = (m.start(), m.end(), lab)
        if best:
            found.append(best)
    found.sort()
    out = {}
    for i, (_s, end, lab) in enumerate(found):
        nxt = found[i + 1][0] if i + 1 < len(found) else len(text)
        chunk = text[end:nxt]
        out[_norm_label(lab)] = compact(chunk).strip(" .。;；,，")
    return out


def option_labels(spec: GoldSpec):
    raw = spec.options
    if raw:
        return _split_option_alphabet(raw)
    joined = "".join(spec.answers)
    if joined and all(ch in CIRCLED for ch in joined):
        return list(CIRCLED[:4])
    if joined and all(ch in JIAZI for ch in joined):
        return list(JIAZI[:4])
    if joined and all(ch.upper() in LATIN_OPTS for ch in joined if ch.isalpha()):
        return list("ABCD")
    return []


def _split_option_alphabet(raw):
    if any(ch in CIRCLED for ch in raw):
        return [ch for ch in raw if ch in CIRCLED]
    if any(ch in JIAZI for ch in raw):
        return [ch for ch in raw if ch in JIAZI]
    letters = [ch.upper() for ch in raw if ch.isalpha() and ch.upper() in LATIN_OPTS]
    if letters:
        return letters
    return list(raw)


def gold_label_set(spec: GoldSpec):
    labels = option_labels(spec)
    got = set()
    for ans in spec.answers:
        got |= extract_labels(ans, labels)
    return got, labels


def extract_labels(text, labels):
    """抽出与题型字母表一致的选项标签（含圈码↔数字、甲乙丙丁↔ABCD）。"""
    if not labels:
        return set()
    ntext = nfkc_ws(text)
    found = set()
    labset = list(labels)
    # 直接标签
    for lab in labset:
        if lab in ntext or lab.lower() in ntext.lower():
            # 避免把函数 C= 里的 C 当选项：要求像选项的用法
            found.add(_norm_label(lab))
    # 圈码 ↔ 阿拉伯
    if labset and labset[0] in CIRCLED:
        for i, ch in enumerate(CIRCLED, 1):
            if ch in labset:
                if re.search(rf"(?<!\d){i}(?!\d)", ntext) or ch in ntext:
                    if ch in ntext or re.search(
                        rf"(?:[、,，和与]\s*){i}(?:\s*[、,，和与]|$)|应填\s*{i}|^{i}[、,，]",
                        ntext,
                    ):
                        found.add(ch)
        # 「2、4」这类
        nums = re.findall(r"[0-9]+", ntext)
        if "、" in ntext or "," in ntext or "，" in ntext or "和" in ntext:
            for n in nums:
                k = int(n)
                if 1 <= k <= len(CIRCLED) and CIRCLED[k - 1] in labset:
                    found.add(CIRCLED[k - 1])
    # 甲乙丙丁 ↔ ABCD
    if labset and labset[0] in JIAZI:
        for i, ch in enumerate(JIAZI):
            if ch in labset and ch in ntext:
                found.add(ch)
            if i < 26 and ch in labset and LATIN_OPTS[i] in ntext.upper():
                found.add(ch)
    if labset and labset[0] in LATIN_OPTS:
        for i, ch in enumerate(JIAZI):
            if ch in ntext and i < len(labset):
                found.add(labset[i] if labset[i] in LATIN_OPTS else labset[0])
        # 乙 → B if ABCD
        for i, jch in enumerate(JIAZI):
            if jch in ntext and i < len(labset) and labset[i] in LATIN_OPTS:
                found.add(labset[i])
        for ch in re.findall(r"[A-Da-d]", ntext):
            u = ch.upper()
            if u in labset:
                found.add(u)
        ntext_l = ntext.lower()
        m = re.search(r"\boption\s+([a-d])\b", ntext_l)
        if m and m.group(1).upper() in labset:
            found.add(m.group(1).upper())
        m = re.search(r"\bthe\s+(first|second|third|fourth|fifth)\s+one\b", ntext_l)
        if m:
            idx = EN_ORDINAL[m.group(1)] - 1
            if 0 <= idx < len(labset):
                found.add(labset[idx])
        m = re.search(r"（\s*([A-Da-d])\s*）|\(\s*([A-Da-d])\s*\)", ntext)
        if m:
            found.add((m.group(1) or m.group(2)).upper())
    # 序数「第四个」
    for word, idx in CN_ORDINAL.items():
        if word in ntext and 0 <= idx - 1 < len(labset):
            if "选项" in ntext or "个" in ntext:
                found.add(labset[idx - 1])
    return {_norm_label(x) for x in found}


def _norm_label(lab):
    s = nfkc_ws(lab)
    if len(s) == 1 and s.lower() in "abcdefghijklmnopqrstuvwxyz":
        return s.upper()
    return s


def _hold_circled(text):
    s = str(text or "")
    held = []
    for i, ch in enumerate(CIRCLED):
        if ch in s:
            tok = f"<<C{i}>>"
            held.append((tok, ch))
            s = s.replace(ch, tok)
    return s, held


def _restore_held(s, held):
    for tok, ch in held:
        s = s.replace(tok, ch)
    return s


def nfkc_ws(text):
    s, held = _hold_circled(text)
    s = unicodedata.normalize("NFKC", s)
    s = _restore_held(s, held)
    s = re.sub(r"([⁰¹²³⁴⁵⁶⁷⁸⁹]+)", lambda m: "**" + m.group(1).translate(SUP_TRANS), s)
    s = s.translate(SUB_TRANS)
    for src, dst in VULGAR.items():
        s = s.replace(src, dst)
    s = s.replace("⁄", "/")
    s = re.sub(r"\s+", "", s)
    return s


def compact(text):
    s, held = _hold_circled(text)
    for src, dst in VULGAR.items():
        s = s.replace(src, dst)
    s = re.sub(r"([⁰¹²³⁴⁵⁶⁷⁸⁹]+)", lambda m: "**" + m.group(1).translate(SUP_TRANS), s)
    s = unicodedata.normalize("NFKC", s)
    s = _restore_held(s, held)
    s = s.translate(SUB_TRANS)
    for src, dst in VULGAR.items():
        s = s.replace(src, dst)
    s = s.replace("⁄", "/")
    s = s.replace("$", "")
    for pat, repl in REL_REPL:
        s = re.sub(pat, repl, s) if pat.startswith("\\") else s.replace(pat, repl)
    s = re.sub(r"\\frac\s*\{([^{}]+)\}\s*\{([^{}]+)\}", r"(\1)/(\2)", s)
    s = re.sub(r"\\sqrt\s*\{([^{}]+)\}", r"√(\1)", s)
    s = re.sub(r"\\sqrt\s+([0-9A-Za-zπ]+)", r"√(\1)", s)
    s = s.replace("\\", "")
    s = re.sub(r"[ \t]+", "", s)
    return s


def normalize_for_stem(text):
    s = compact(text)
    s = s.replace("\n", "")
    return s


def strip_latex_noise(s):
    return compact(s)


# ---------- 中文数字 ----------

def cn_int(s):
    s = s.strip()
    if not s:
        return None
    if s.isascii() and s.isdigit():
        return int(s)
    if all(ch in CN_DIGIT for ch in s) and "十" not in s and "百" not in s:
        if len(s) == 1:
            return CN_DIGIT[s]
        # 不把「一二」拼成 12
        return None
    total = 0
    if "百" in s:
        a, b = s.split("百", 1)
        total += (CN_DIGIT.get(a, 1) if a else 1) * 100
        s = b
        s = s.removeprefix("零")
    if "十" in s:
        a, b = s.split("十", 1)
        total += (CN_DIGIT.get(a, 1) if a else 1) * 10
        if b:
            if b in CN_DIGIT:
                total += CN_DIGIT[b]
            elif b.isdigit():
                total += int(b)
            else:
                return None
        return total
    if s in CN_DIGIT:
        return total + CN_DIGIT[s]
    if s.isascii() and s.isdigit():
        return total + int(s)
    if total:
        return total
    return None


def parse_cn_quantity(text):
    """解析汉字数字、分数、百分数、倍根号、度数。成功则返回 ('num', Fraction) 等。"""
    s = compact(text)
    sign = 1
    if s.startswith("负"):
        sign = -1
        s = s[1:]
    if s.endswith(("度", "°")):
        core = s[:-1]
        n = cn_int(core) if not re.search(r"\d", core) else _try_frac(core)
        if n is None and isinstance(core, str):
            n = cn_int(core)
        if n is not None:
            val = Fraction(n) if not isinstance(n, Fraction) else n
            return ("qty", sign * val, "angle-deg")
    m = re.fullmatch(r"百分之(.+)", s)
    if m:
        n = cn_int(m.group(1)) or _try_frac(m.group(1))
        if n is not None:
            return ("num", sign * Fraction(n) / 100)
    m = re.fullmatch(r"(.+)又(.+)分之(.+)", s)
    if m:
        w, den, num = cn_int(m.group(1)), cn_int(m.group(2)), cn_int(m.group(3))
        if None not in (w, den, num) and den:
            return ("num", sign * (Fraction(w) + Fraction(num, den)))
    m = re.fullmatch(r"(.+)分之(.+)", s)
    if m:
        a, b = cn_int(m.group(1)), cn_int(m.group(2))
        # 「四分之七」= 7/4 ；分母在「分之」前
        if None not in (a, b) and a:
            return ("num", sign * Fraction(b, a))
    m = re.fullmatch(r"(.+)倍根号(.+)", s)
    if m:
        k, n = cn_int(m.group(1)), cn_int(m.group(2))
        if None not in (k, n):
            return ("rad", sign * Fraction(k), n)
    m = re.fullmatch(r"根号(.+)", s)
    if m:
        n = cn_int(m.group(1))
        if n is not None:
            return ("rad", sign * Fraction(1), n)
    n = cn_int(s)
    if n is not None:
        return ("num", sign * Fraction(n))
    return None


def _try_frac(s):
    try:
        if "/" in s:
            a, b = s.split("/", 1)
            return Fraction(a) / Fraction(b)
        if "." in s:
            return Fraction(s)
        return Fraction(int(s))
    except (ValueError, ZeroDivisionError):
        return None


# ---------- 数值 / 区间 / 方程 ----------

def simplify_radical(coeff: Fraction, inside: int):
    if inside < 0:
        return coeff, inside
    n = inside
    k = 1
    p = 2
    while p * p <= n:
        while n % (p * p) == 0:
            n //= p * p
            k *= p
        p += 1
    return coeff * k, n


def parse_number_token(raw):
    """把一个候选收成内部值。失败返回 None。"""
    s = compact(raw)
    s = s.replace("（", "(").replace("）", ")")
    while s.startswith("(") and s.endswith(")") and s.count("(") == 1:
        s = s[1:-1]
    s = re.sub(r"\((\-?[0-9.]+)\)/\((\-?[0-9.]+)\)", r"\1/\2", s)
    if not s:
        return None
    cn = parse_cn_quantity(s)
    if cn:
        return cn
    # 百分数
    m = re.fullmatch(r"(-?[0-9.]+)%", s)
    if m:
        return ("num", Fraction(m.group(1)) / 100)
    # 单位量
    um = re.fullmatch(
        r"(-?[0-9.]+(?:/[0-9.]+)?)\s*(m/s²|m/s\^2|m/s|km/h|cm|km|kg|min|rad|deg|[msNhJWjg°])",
        s,
        flags=re.IGNORECASE,
    )
    if um:
        val = _try_frac(um.group(1))
        unit = um.group(2)
        if val is None:
            return None
        key = unit if unit in UNIT_TABLE else unit.lower()
        if key in UNIT_TABLE:
            dim, fac = UNIT_TABLE[key]
            if fac == "pi180":
                return ("qty", val, "angle-deg")
            if fac == "rad":
                return ("qty", val, "angle-rad")
            return ("qty", val * fac, dim)
        if unit in ("°",):
            return ("qty", val, "angle-deg")
    # π 有理倍数
    m = re.fullmatch(r"(-)?(?:(\d+)/)?π(?:/(\d+))?", s)
    if m and "π" in s and re.fullmatch(r"-?(?:\d+/)?π(?:/\d+)?", s):
        sign = -1 if m.group(1) else 1
        num = int(m.group(2) or 1)
        den = int(m.group(3) or 1)
        return ("qty", Fraction(sign * num, den), "angle-pi")
    m = re.fullmatch(r"-?\\frac\{π\}\{(\d+)\}", compact(raw))
    if m:
        return ("qty", Fraction(1, int(m.group(1))), "angle-pi")
    # 根式 k√n 或 √n
    m = re.fullmatch(r"(-)?(?:(\d+(?:\.\d+)?))?√(?:\()?([0-9]+)(?:\))?", s)
    if m:
        sign = -1 if m.group(1) else 1
        coeff = Fraction(m.group(2)) if m.group(2) else Fraction(1)
        inside = int(m.group(3))
        coeff, inside = simplify_radical(sign * coeff, inside)
        if inside == 1:
            return ("num", coeff)
        return ("rad", coeff, inside)
    # (1/2)^3 或 (1/2)**3
    m = re.fullmatch(r"\((-?\d+)/(-?\d+)\)\*\*(-?\d+)", s.replace("^", "**"))
    if m:
        base = Fraction(int(m.group(1)), int(m.group(2)))
        exp = int(m.group(3))
        return ("num", base ** exp)
    # 普通分数 / 小数 / 整数
    frac = _try_frac(s)
    if frac is not None and re.fullmatch(r"-?[0-9]+(?:\.[0-9]+)?(?:/[0-9]+(?:\.[0-9]+)?)?", s):
        return ("num", frac)
    return None


def decimal_places(token):
    m = re.search(r"(?<![0-9])-?[0-9]*\.([0-9]+)(?!%)", token)
    if m:
        return len(m.group(1))
    return None


def nums_equiv(a, b, reply_token=""):
    if a is None or b is None:
        return False
    if a[0] == "qty" and b[0] == "qty":
        return _qty_equiv(a, b, reply_token)
    aa = _to_float_num(a)
    bb = _to_float_num(b)
    if aa is None or bb is None:
        if a[0] == "rad" and b[0] == "rad":
            ca, ia = simplify_radical(a[1], a[2])
            cb, ib = simplify_radical(b[1], b[2])
            return ca == cb and ia == ib
        return False
    d = decimal_places(reply_token)
    if d is not None:
        return abs(aa - bb) <= 0.5 * (10 ** (-d)) + 1e-15
    return abs(aa - bb) < 1e-10


def _qty_equiv(a, b, reply_token):
    da, va = a[2], a[1]
    db, vb = b[2], b[1]
    fa = _qty_si(va, da)
    fb = _qty_si(vb, db)
    if fa is None or fb is None:
        return False
    d = decimal_places(reply_token)
    if d is not None:
        return abs(fa - fb) <= 0.5 * (10 ** (-d)) + 1e-12
    return abs(fa - fb) < 1e-9


def _qty_si(val, dim):
    v = float(val)
    if dim == "angle-deg":
        return v * PI / 180.0
    if dim == "angle-rad":
        return v
    if dim == "angle-pi":
        return float(val) * PI
    if dim in {"speed", "length", "time", "mass", "force", "energy", "power", "accel"}:
        return float(val)
    return None


def _to_float_num(tag):
    if tag[0] == "num":
        return float(tag[1])
    if tag[0] == "rad":
        coeff, inside = tag[1], tag[2]
        if inside < 0:
            return None
        return float(coeff) * (inside ** 0.5)
    if tag[0] == "qty":
        return _qty_si(tag[1], tag[2])
    return None


@dataclass
class Interval:
    parts: list  # list of (lo, lo_incl, hi, hi_incl); None = inf


def iv_eq(a: Interval, b: Interval):
    return _iv_norm(a) == _iv_norm(b)


def iv_finite_endpoint_diff(a: Interval, b: Interval):
    """只在有限个边界点上不同（开闭不同）。"""
    pa, pb = _iv_norm(a), _iv_norm(b)
    if len(pa) != len(pb):
        return False
    close = True
    for x, y in zip(pa, pb):
        if x[0] != y[0] or x[2] != y[2]:
            return False
        if x[1] != y[1] or x[3] != y[3]:
            # 端点开闭不同
            if x[0] is None or x[2] is None:
                # 无穷端点开闭无所谓
                continue
            close = True
        if abs((x[0] or 0) - (y[0] or 0)) > 1e-12 and x[0] is not None:
            return False
        if abs((x[2] or 0) - (y[2] or 0)) > 1e-12 and x[2] is not None:
            return False
    return close


def iv_is_component(part: Interval, whole: Interval):
    pn = _iv_norm(part)
    wn = _iv_norm(whole)
    if len(pn) != 1:
        return False
    return pn[0] in wn


def _iv_norm(iv: Interval):
    out = []
    for lo, li, hi, hi_i in iv.parts:
        out.append((
            None if lo is None else float(lo),
            bool(li),
            None if hi is None else float(hi),
            bool(hi_i),
        ))
    out.sort(key=lambda t: (t[0] is None, t[0] or 0))
    return out


def parse_interval(raw):
    s = compact(raw)
    s = s.replace("+∞", "∞").replace("+infty", "∞").replace("infty", "∞")
    s = s.replace("-∞", "-∞").replace("-infty", "-∞")
    s = s.replace("inf", "∞")
    # 集合 {k|k>5} / {x: ...}
    m = re.search(r"\{[a-zA-Z]\s*[|｜:：]\s*(.+)\}", s)
    if m:
        s = m.group(1)
    parts = re.split(r"∪|或|或者", s)
    ivs = []
    for p in parts:
        one = _parse_one_interval(p)
        if one is None:
            return None
        ivs.extend(one.parts)
    return Interval(ivs) if ivs else None


def _parse_one_interval(p):
    p = compact(p)
    p = re.sub(r"^[a-zA-Z]∈", "", p)
    # 标准括号区间 (1,3]  (5,∞)
    m = re.fullmatch(r"([\(\[])([^,，]+)[,，]([^)\]\]]+)([\)\]])", p)
    if m:
        lo_s, hi_s = m.group(2), m.group(3)
        lo = None if "∞" in lo_s and "-" in lo_s else (None if "∞" in lo_s else _try_frac(lo_s))
        hi = None if "∞" in hi_s else _try_frac(hi_s)
        if "∞" in lo_s and "-" not in lo_s:
            lo = None
        if lo is None and lo_s not in ("∞", "-∞") and "∞" not in lo_s:
            if _try_frac(lo_s) is None and "∞" not in lo_s:
                return None
        li = m.group(1) == "["
        hi_i = m.group(4) == "]"
        if "∞" in lo_s:
            lo, li = None, False
        if "∞" in hi_s:
            hi, hi_i = None, False
        return Interval([(lo, li, hi, hi_i)])
    # 链式 1<x<=3 或 3>=x>1
    m = re.fullmatch(
        r"(-?[0-9.π]+)\s*(<=|<|>=|>)\s*[a-zA-Z]\s*(<=|<|>=|>)\s*(-?[0-9.π]+)",
        p,
    )
    if m:
        return _chain_to_iv(m.group(1), m.group(2), m.group(3), m.group(4))
    m = re.fullmatch(
        r"(-?[0-9.π]+)\s*(<=|<|>=|>)\s*[a-zA-Z]\s*(<=|<|>=|>)\s*(-?[0-9.π]+)",
        re.sub(r"([0-9])([≤≥<>])", r"\1\2", p),
    )
    # k>5 / 5<k / k>=5
    m = re.fullmatch(r"[a-zA-Z]\s*(<=|>=|<|>)\s*(-?[0-9.π∞]+)", p)
    if m:
        return _rel_to_iv(m.group(1), m.group(2), var_left=True)
    m = re.fullmatch(r"(-?[0-9.π∞]+)\s*(<=|>=|<|>)\s*[a-zA-Z]", p)
    if m:
        rel = m.group(2)
        flip = {">": "<", "<": ">", ">=": "<=", "<=": ">="}[rel]
        return _rel_to_iv(flip, m.group(1), var_left=True)
    # 中文
    w = _parse_cn_ineq(p)
    if w:
        return w
    return None


def _chain_to_iv(a, op1, op2, b):
    lo, hi = _try_frac(a), _try_frac(b)
    if lo is None or hi is None:
        return None
    # a op1 x op2 b
    if op1 in (">", ">=") and op2 in (">", ">="):
        # 3>=x>1 → swap
        lo, hi = hi, lo
        return Interval([(lo, op2 in (">=", "<="), hi, op1 in (">=", "<="))])
    if float(lo) > float(hi):
        lo, hi = hi, lo
        op1, op2 = op2, op1
        flip = {">": "<", "<": ">", ">=": "<=", "<=": ">="}
        op1, op2 = flip[op1], flip[op2]
    # a < x : lo open if <
    if op1 == "<" or op1 == "<=":
        pass
    elif op1 == ">":
        # a > x > b  handled above
        pass
    elif op1 == ">=":
        pass
    if op2 == "<" or op2 == "<=":
        pass
    return Interval([(lo, op1 in ("<=", ">="), hi, op2 in ("<=", ">="))])


def _rel_to_iv(op, bound_s, var_left=True):
    if "∞" in bound_s:
        return None
    b = _try_frac(bound_s)
    if b is None:
        return None
    if op == ">":
        return Interval([(b, False, None, False)])
    if op == ">=":
        return Interval([(b, True, None, False)])
    if op == "<":
        return Interval([(None, False, b, False)])
    if op == "<=":
        return Interval([(None, False, b, True)])
    return None


def _parse_cn_ineq(p):
    """k必须大于5 / 大于1且不超过3 / 小于等于-1 / 大于等于3"""
    s = p
    s = s.replace("必须", "").replace("要满足", "").replace("应当是", "")
    s = s.replace("才行", "").replace("才没有实根", "")
    and_parts = re.split(r"且|并且", s)
    if len(and_parts) == 2:
        a = _one_cn_rel(and_parts[0])
        b = _one_cn_rel(and_parts[1])
        if a and b:
            return _intersect_iv(a, b)
    return _one_cn_rel(s)


def _one_cn_rel(s):
    s = compact(s)
    s = re.sub(r"^[a-zA-Z]", "", s)
    pairs = [
        (r"不小于(-?.+)", ">="),
        (r"不大于(-?.+)|不超过(-?.+)", "<="),
        (r"大于等于(-?.+)", ">="),
        (r"小于等于(-?.+)", "<="),
        (r"大于(-?.+)", ">"),
        (r"小于(-?.+)", "<"),
        (r"greaterthan(-?.+)", ">"),
        (r"lessthan(-?.+)", "<"),
    ]
    for pat, op in pairs:
        m = re.search(pat, s)
        if m:
            bound = next(g for g in m.groups() if g)
            bound = bound.replace("度", "")
            n = parse_cn_quantity(bound) or parse_number_token(bound)
            if n and n[0] == "num":
                return _rel_to_iv(op, str(n[1]))
            if _try_frac(bound) is not None:
                return _rel_to_iv(op, bound)
    # greater than 5
    m = re.search(r"greaterthan(\d+)", compact(s.lower().replace(" ", "")))
    if m:
        return _rel_to_iv(">", m.group(1))
    return None


def _intersect_iv(a: Interval, b: Interval):
    # 只处理各一段
    if len(a.parts) != 1 or len(b.parts) != 1:
        return None
    lo = a.parts[0][0] if a.parts[0][0] is not None else b.parts[0][0]
    hi = a.parts[0][2] if a.parts[0][2] is not None else b.parts[0][2]
    li = a.parts[0][1] if a.parts[0][0] is not None else b.parts[0][1]
    hi_i = a.parts[0][3] if a.parts[0][2] is not None else b.parts[0][3]
    if a.parts[0][0] is not None and b.parts[0][0] is not None:
        if float(b.parts[0][0]) > float(a.parts[0][0]):
            lo, li = b.parts[0][0], b.parts[0][1]
        elif float(b.parts[0][0]) == float(a.parts[0][0]):
            li = a.parts[0][1] and b.parts[0][1]
    if a.parts[0][2] is not None and b.parts[0][2] is not None:
        if float(b.parts[0][2]) < float(a.parts[0][2]):
            hi, hi_i = b.parts[0][2], b.parts[0][3]
        elif float(b.parts[0][2]) == float(a.parts[0][2]):
            hi_i = a.parts[0][3] and b.parts[0][3]
    return Interval([(lo, li, hi, hi_i)])


def gold_intervals(spec: GoldSpec):
    out = []
    for ans in spec.answers:
        iv = parse_interval(compact(ans))
        if iv:
            out.append(iv)
        else:
            # k>5 写在 answer 里
            iv = parse_interval(ans)
            if iv:
                out.append(iv)
    return out


# ---------- 方程 / 表达式 ----------

def linear_factors_eq(s):
    """(x+1)(x-4)=0 → 根列表。"""
    t = compact(s)
    m = re.fullmatch(r"\(([^()]+)\)\(([^()]+)\)=0", t)
    if not m:
        return None
    roots = []
    for fac in m.groups():
        r = _linear_root(fac)
        if r is None:
            return None
        roots.append(r)
    return roots


def _linear_root(fac):
    fac = compact(fac)
    m = re.fullmatch(r"([a-zA-Z])([+-])([0-9./]+)", fac)
    if m:
        sign = 1 if m.group(2) == "-" else -1
        return sign * float(Fraction(m.group(3)))
    m = re.fullmatch(r"([+-]?[0-9./]+)([a-zA-Z])([+-][0-9./]+)", fac)
    if m:
        a = Fraction(m.group(1))
        b = Fraction(m.group(3))
        if a == 0:
            return None
        return float(-b / a)
    return None


def parse_equation(raw):
    s = compact(raw)
    s = s.replace("等于", "=")
    if "=" not in s:
        return None
    left, right = s.split("=", 1)
    return left, right


def sympy_eq_equiv(a, b):
    sp = use_sympy()
    if sp is None:
        return _stdlib_eq_equiv(a, b)
    try:
        ea = _sp_eq(sp, a)
        eb = _sp_eq(sp, b)
        if ea is None or eb is None:
            return _stdlib_eq_equiv(a, b)
        d1 = sp.expand(ea.lhs - ea.rhs)
        d2 = sp.expand(eb.lhs - eb.rhs)
        if d1 == 0 and d2 == 0:
            return True
        ratio = sp.simplify(d1 / d2)
        if ratio.is_number and ratio != 0 and ratio.is_finite and (d1.free_symbols & d2.free_symbols):
            return True
        if sp.simplify(d1 - d2) == 0:
            return True
        vars_ = sorted(ea.free_symbols | eb.free_symbols, key=str)
        if len(vars_) == 1:
            xa = sp.solveset(ea, vars_[0], domain=sp.S.Reals)
            xb = sp.solveset(eb, vars_[0], domain=sp.S.Reals)
            return xa == xb
        if not (ea.free_symbols & eb.free_symbols):
            return False
    except (TypeError, ValueError, ZeroDivisionError, AttributeError):
        return _stdlib_eq_equiv(a, b)
    return _stdlib_eq_equiv(a, b)


def _sp_eq(sp, pair):
    left, right = pair
    try:
        expr = sp.Eq(sp.sympify(_to_sp_str(left)), sp.sympify(_to_sp_str(right)))
        return expr
    except (sp.SympifyError, TypeError, ValueError):
        return None


def _to_sp_str(s):
    t = compact(s)
    t = t.replace("π", "pi")
    t = t.replace("√", "sqrt")
    t = t.replace("^", "**")
    t = re.sub(r"(\d)([a-zA-Z])", r"\1*\2", t)
    t = re.sub(r"([a-zA-Z])(\d)", r"\1*\2", t)
    t = t.replace("sqrt(", "sqrt(")
    t = re.sub(r"sqrt(?!\()", "sqrt", t)
    t = re.sub(r"sqrt(\d+)", r"sqrt(\1)", t)
    return t


def _stdlib_eq_equiv(a, b):
    """一次式 ax+by+c=0 系数成比例；赋值 x=值。"""
    fa = linear_form(a)
    fb = linear_form(b)
    if fa and fb:
        return _proportional(fa, fb)
    # 赋值
    va = assignment(a)
    vb = assignment(b)
    if va and vb:
        if va[0] == vb[0]:
            return nums_equiv(("num", va[1]), ("num", vb[1]))
        return False
    if va and fb:
        return False
    roots_a = linear_factors_eq("=".join(a) if isinstance(a, tuple) else str(a))
    roots_b = linear_factors_eq("=".join(b) if isinstance(b, tuple) else str(b))
    if roots_a and roots_b:
        return sorted(roots_a) == sorted(roots_b)
    return False


def assignment(pair):
    left, right = pair
    if re.fullmatch(r"[a-zA-Z]", left):
        n = parse_number_token(right)
        if n and n[0] in {"num", "rad", "qty"}:
            val = _to_float_num(n)
            if val is not None:
                return left, Fraction(str(n[1])) if n[0] == "num" else val
    if re.fullmatch(r"[a-zA-Z]", right):
        n = parse_number_token(left)
        if n and n[0] == "num":
            return right, n[1]
    return None


def linear_form(pair):
    """把等式收到 ax+by+c=0 的系数。优先 SymPy，否则标准库一次项扫描。"""
    left, right = compact(pair[0]), compact(pair[1])
    sp = use_sympy()
    if sp is not None:
        try:
            x, y = sp.symbols("x y")
            e = sp.expand(sp.sympify(_to_sp_str(left)) - sp.sympify(_to_sp_str(right)))
            if e.free_symbols <= {x, y}:
                poly = sp.Poly(e, x, y)
                if poly.total_degree() <= 1:
                    return (
                        Fraction(str(poly.coeff_monomial(x))),
                        Fraction(str(poly.coeff_monomial(y))),
                        Fraction(str(poly.coeff_monomial(1))),
                    )
        except (TypeError, ValueError, AttributeError):
            pass
    expr = left if right in {"0", "0.0"} else f"{left}-({right})"
    expr = compact(expr).replace("−", "-")
    expr = re.sub(r"(?<![0-9])-(?=\()", "+-(", expr)
    if not expr.startswith(("+", "-")):
        expr = "+" + expr
    coeffs = {"x": Fraction(0), "y": Fraction(0), "c": Fraction(0)}
    for m in re.finditer(r"([+-])(\d+(?:\.\d+)?(?:/\d+)?)?(x|y)?", expr):
        sign = -1 if m.group(1) == "-" else 1
        num = Fraction(m.group(2)) if m.group(2) else Fraction(1)
        var = m.group(3)
        if var:
            coeffs[var] += sign * num
        else:
            coeffs["c"] += sign * num
    if coeffs["x"] == 0 and coeffs["y"] == 0:
        return None
    return coeffs["x"], coeffs["y"], coeffs["c"]


def _proportional(fa, fb):
    ax, ay, ac = fa
    bx, by, bc = fb
    # 找非零比
    pairs = [(ax, bx), (ay, by), (ac, bc)]
    ratio = None
    for a, b in pairs:
        if a == 0 and b == 0:
            continue
        if a == 0 or b == 0:
            return False
        r = a / b
        if ratio is None:
            ratio = r
        elif r != ratio:
            return False
    return ratio is not None


def sympy_rel_equiv(sa, sb):
    sp = use_sympy()
    iv_a, iv_b = parse_interval(sa), parse_interval(sb)
    if iv_a and iv_b:
        if iv_eq(iv_a, iv_b) or iv_finite_endpoint_diff(iv_a, iv_b):
            return True
        if iv_is_component(iv_a, iv_b) or iv_is_component(iv_b, iv_a):
            # 只认「回复是金标并集的连通分支」
            return iv_is_component(iv_a, iv_b)
    if sp is None:
        return False
    try:
        xa = sp.symbols("x")
        # 把主元换成 x
        ta = _prep_rel(sa)
        _prep_rel(sb)
        sp.sympify(_to_sp_str(ta).replace("<=", "<="))
        # 用 solveset 需要关系
        def _set(t):
            t = compact(t)
            t = re.sub(r"[a-zA-Z]", "x", t, count=1) if re.match(r"^[a-zA-Z](?:<|>|=)", t) else t
            t = _prep_rel(t)
            for op in ("<=", ">=", "!=", "<", ">"):
                if op in t:
                    L, R = t.split(op, 1)
                    node = {
                        "<=": sp.Le, ">=": sp.Ge, "<": sp.Lt, ">": sp.Gt,
                    }[op](sp.sympify(_to_sp_str(L)), sp.sympify(_to_sp_str(R)))
                    return sp.solveset(node, xa, domain=sp.S.Reals)
            if "=" in t and "==" not in t:
                L, R = t.split("=", 1)
                return sp.solveset(sp.Eq(sp.sympify(_to_sp_str(L)), sp.sympify(_to_sp_str(R))), xa, domain=sp.S.Reals)
            return None
        A, B = _set(sa), _set(sb)
        if A is None or B is None:
            return False
        if A == B:
            return True
        # 对称差有限
        try:
            d = sp.Union(sp.Complement(A, B), sp.Complement(B, A))
            if d.is_FiniteSet or (hasattr(d, "is_finite_set") and d.is_finite_set):
                return True
            if d == sp.EmptySet:
                return True
        except (TypeError, ValueError, AttributeError):
            return False
    except (TypeError, ValueError, ZeroDivisionError, AttributeError):
        return False
    return False


def _prep_rel(s):
    t = compact(s)
    t = t.replace("∈", "")
    return t


# ---------- 切句与放行语境 ----------

def iter_units(text):
    """切成 (lineno, unit_text, abs_start, abs_end)。"""
    units = []
    # 先掏代码围栏和行内代码
    pieces = []
    pos = 0
    fence = re.compile(r"```.*?```", re.DOTALL)
    for m in fence.finditer(text):
        if m.start() > pos:
            pieces.append(("p", pos, m.start(), text[pos:m.start()]))
        pieces.append(("c", m.start(), m.end(), m.group(0)))
        pos = m.end()
    if pos < len(text):
        pieces.append(("p", pos, len(text), text[pos:]))
    expanded = []
    for kind, a, b, chunk in pieces:
        if kind == "c":
            expanded.append((a, b, chunk))
            continue
        p2 = 0
        sub = chunk
        for m in re.finditer(r"`[^`]+`", sub):
            if m.start() > p2:
                expanded.append((a + p2, a + m.start(), sub[p2:m.start()]))
            expanded.append((a + m.start(), a + m.end(), m.group(0)))
            p2 = m.end()
        if p2 < len(sub):
            expanded.append((a + p2, a + len(sub), sub[p2:]))
    for a, b, chunk in expanded:
        if chunk.startswith(("```", "`")):
            inner = chunk.strip("`")
            ln = text[:a].count("\n") + 1
            units.append((ln, inner, a, b))
            continue
        # 表格与句子
        buf = []
        depth = 0
        i = 0
        while i <= len(chunk):
            ch = chunk[i] if i < len(chunk) else None
            if ch is not None and ch in "([{（":
                depth += 1
                buf.append(ch)
                i += 1
                continue
            if ch is not None and ch in ")]}）":
                depth = max(0, depth - 1)
                buf.append(ch)
                i += 1
                continue
            if ch is None or (depth == 0 and ch in "。！？；\n|，"):
                piece = "".join(buf).strip()
                if piece:
                    st = a + (i - len(buf))
                    ln = text[:st].count("\n") + 1
                    units.append((ln, piece, st, a + i))
                buf = []
                i += 1
                continue
            buf.append(ch)
            i += 1
    return units


def quote_spans(text):
    spans = []
    pairs = [("「", "」"), ("“", "”"), ('"', '"')]
    for lo, hi in pairs:
        i = 0
        while True:
            a = text.find(lo, i)
            if a < 0:
                break
            b = text.find(hi, a + 1)
            if b < 0:
                break
            spans.append((a + len(lo), b, a, b + len(hi)))
            i = b + len(hi)
    return spans


def verified_quote_spans(text, stem):
    if not stem:
        return []
    stem_n = normalize_for_stem(stem)
    out = []
    for inner_a, inner_b, outer_a, outer_b in quote_spans(text):
        inner = text[inner_a:inner_b]
        if normalize_for_stem(inner) and normalize_for_stem(inner) in stem_n:
            out.append((outer_a, outer_b))
    # 紧跟「题目说」无引号
    for m in STEM_CUE_RE.finditer(text):
        rest = text[m.end():]
        # 若紧跟引号，已由上面覆盖
        if rest.lstrip()[:1] in "「“\"":
            continue
        cut = re.split(r"[，。！？\n]", rest, maxsplit=1)[0]
        if normalize_for_stem(cut) and normalize_for_stem(cut) in stem_n:
            out.append((m.start(), m.end() + len(cut)))
    return out


def span_inside(start, end, spans):
    return any(s <= start and end <= e for s, e in spans)


def unit_context(unit, full_text, start, end, stem):
    ctx = {
        "student": bool(STUDENT_RE.search(unit)),
        "first_person": bool(FIRST_PERSON_RE.search(unit)),
        "eval": bool(EVAL_RE.search(unit)),
        "subst": bool(SUBST_RE.search(unit)),
        "leading": bool(LEADING_RE.search(unit)),
        "either": bool(EITHER_RE.search(unit)),
        "method": bool(METHOD_RE.search(unit)) and not CHOICE_ASSERT_RE.search(unit),
        "ordinal": bool(ORDINAL_SKIP_RE.search(unit)),
        "neutral_opt": bool(OPTION_NEUTRAL_RE.search(unit)) and not CHOICE_ASSERT_RE.search(unit),
        "probe": bool(PROBE_RE.search(unit)),
        "assert": False,
        "stem_quote": False,
    }
    vq = verified_quote_spans(full_text, stem) if stem else []
    if span_inside(start, end, vq):
        ctx["stem_quote"] = True
    else:
        # 单位整体在引号内
        for s, e in vq:
            if start >= s and end <= e:
                ctx["stem_quote"] = True
    ctx["assert"] = bool(
        CHOICE_ASSERT_RE.search(unit)
        or ctx["subst"] or ctx["leading"] or ctx["either"] or ctx["first_person"]
        or re.search(r"应当是|要满足|必须|结果是|等于|解集|取值范围|最后得|所以|因此|故", unit)
    )
    return ctx


# ---------- 候选抽出 ----------

NUM_TOKEN_RE = re.compile(
    r"负?[零〇一二两三四五六七八九十百]+又[零〇一二两三四五六七八九十]+分之[零〇一二两三四五六七八九十]+|"
    r"[零〇一二两三四五六七八九十]+分之[零〇一二两三四五六七八九十]+|"
    r"百分之[零〇一二两三四五六七八九十百]+|"
    r"[零〇一二两三四五六七八九十]+倍根号[零〇一二两三四五六七八九十]+|"
    r"根号[零〇一二两三四五六七八九十]+|"
    r"负?[零〇一二两三四五六七八九十]+度|"
    r"负?[零〇一二两三四五六七八九十]+|"
    r"-?\d+\.?\d*\s*%|"
    r"-?\d+\.?\d*\s*(?:km/h|m/s²|m/s\^2|m/s|cm|km|min|kg|rad|deg|[msNhJWjg°])|"
    r"-?\d*\.?\d*√(?:\([^)]+\)|\d+)|"
    r"√(?:\([^)]+\)|\d+)|"
    r"-?(?:\d+/)?π(?:/\d+)?|"
    r"\(\-?\d+\)/\(\-?\d+\)|"
    r"\(-?\d+/-?\d+\)\s*\*\*\s*\d+|"
    r"\(-?\d+/-?\d+\)\s*[\^]?\s*(?:\{?\d\}?|\d)|"
    r"-?\d+\s*/\s*\d+|"
    r"-?\d+\.\d+|"
    r"-?\d+"
)

INEQ_TOKEN_RE = re.compile(
    r"[a-zA-Z]\s*(?:∈\s*)?[\[\(][^\]\)]+[\]\)]|"
    r"[\[\(][^\[\]\(\)]+[,，][^\[\]\(\)]+[\]\)]|"
    r"[a-zA-Z]\s*(?:<=|>=|<|>|≤|≥|＜|＞)\s*[-+0-9.∞π\\]+|"
    r"[-+0-9.∞π]+\s*(?:<=|>=|<|>|≤|≥)\s*[a-zA-Z](?:\s*(?:<=|>=|<|>|≤|≥)\s*[-+0-9.∞π]+)?|"
    r"[a-zA-Z]\s*(?:必须)?(?:大于等于|小于等于|不小于|不大于|不超过|大于|小于)\s*[-+0-9.零〇一二两三四五六七八九十π]+|"
    r"(?:大于等于|小于等于|不超过|大于|小于)\s*[-+0-9.零〇一二两三四五六七八九十]+(?:且(?:不超过|不大于|小于等于|大于)\s*[-+0-9.零〇一二两三四五六七八九十]+)?|"
    r"[^{}]+∪[^{}]+|"
    r"\{[^}]+\|"
    r"[a-zA-Z]\s*(?:<=|>=|<|>)[^。；]{0,20}(?:或|或者)[^。；]{0,20}(?:<=|>=|<|>)"
)

EQ_TOKEN_RE = re.compile(
    r"[a-zA-Z]\s*=\s*[-+0-9./π√()\\a-zA-Z]{1,48}|"
    r"[-+0-9./π√()\\a-zA-Z]{1,48}\s*=\s*[a-zA-Z]|"
    r"\([^()]+\)\s*\([^()]+\)\s*=\s*0|"
    r"[0-9a-zA-Zπ+\-*/√().]{1,40}\s*=\s*[0-9a-zA-Zπ+\-*/√().]{1,40}"
)

SET_TOKEN_RE = re.compile(r"\{[^{}|]{1,40}\}")


def conclusion_hits_in(unit, gold_answers):
    """用封闭同义表。"""
    hits = []
    nunit = compact(unit)
    for ans in gold_answers:
        key = _conclusion_key(ans)
        if not key:
            continue
        syns = set(CONCLUSION_SYNONYMS.get(key, {key}))
        if key == "平行" and re.search(r"同平面|共面", unit):
            syns.add("不相交")
        if key == "正确":
            # 短词「对」只认谓语
            if re.search(r"(?:是)?对的|对了", unit) and not re.search(r"对顶", unit):
                hits.append(ans)
                continue
        # 方法名「判定两直线平行」放行
        if key == "平行" and re.search(r"判定.{0,6}平行|平行有哪几种|判定两直线平行", unit):
            if not re.search(r"所以|因此|得到|是不是|难道", unit):
                continue
        for syn in syns:
            if syn and syn in nunit:
                # 修辞双否：难道不平行 → 仍算断言平行
                hits.append(ans)
                break
        if key == "不存在" and re.search(r"找不到|没有这样的|不存在", unit):
            hits.append(ans)
    return hits


def _conclusion_key(ans):
    s = compact(ans)
    if "平行" in s or s in {"∥", "||"}:
        return "平行"
    if s in {"不存在", "找不到"} or "不存在" in s:
        return "不存在"
    if s in {"正确", "对", "成立"}:
        return "正确"
    if s in {"错误", "不对", "不成立"}:
        return "错误"
    if s in {"是", "否", "能", "不能"}:
        return s
    return None


# ---------- 主比对 ----------

def find_gold_leaks(text, spec: GoldSpec, stem=None):
    text = str(text or "")
    hits = []
    vq = verified_quote_spans(text, stem)
    labels = option_labels(spec)
    gold_labs, _ = gold_label_set(spec)
    contents = dict(spec.option_contents)
    if stem and labels:
        for k, v in parse_options_from_stem(stem, labels).items():
            contents.setdefault(k, v)

    # 选项：选择 / 排除 / 内容
    hits.extend(_option_leaks(text, spec, labels, gold_labs, contents, vq, stem))

    gold_nums = []
    gold_ivs = []
    gold_eqs = []
    gold_sets = []
    for ans in spec.answers:
        compact_ans = compact(ans)
        if compact_ans and all(ch in CIRCLED + JIAZI + LATIN_OPTS for ch in compact_ans):
            continue
        iv = parse_interval(ans)
        if iv and re.search(r"[<>≤≥∈∪\[\(]|大于|小于|范围", compact(ans)):
            gold_ivs.append((ans, iv))
            continue
        eq = parse_equation(ans)
        if eq:
            gold_eqs.append((ans, eq))
            n = parse_number_token(eq[1]) if re.fullmatch(r"[a-zA-Z]", eq[0]) else None
            if n:
                gold_nums.append((ans, n, eq[0]))
            continue
        st = _parse_finite_set(ans)
        if st:
            gold_sets.append((ans, st))
            continue
        n = parse_number_token(ans) or parse_cn_quantity(ans)
        if n:
            gold_nums.append((ans, n, None))

    for lineno, unit, a, b in iter_units(text):
        if span_inside(a, b, vq):
            continue
        ctx = unit_context(unit, text, a, b, stem)
        if ctx["stem_quote"]:
            continue
        snippet = unit.replace("\n", " ")[:36]

        if ctx["ordinal"]:
            unit_wo = ORDINAL_SKIP_RE.sub(" ", unit)
        else:
            unit_wo = unit
        scan = compact(unit_wo)

        # 结论
        for _ans in conclusion_hits_in(unit, spec.answers):
            if ctx["method"] and _conclusion_key(_ans) == "平行":
                continue
            if _allow_student(ctx, True):
                continue
            hits.append(LeakHit(lineno, "结论", snippet))

        # 代入提示：值≡金标一律拦
        # 方程
        for m in EQ_TOKEN_RE.finditer(scan):
            tok = m.group(0)
            if _skip_formula_letters(tok):
                continue
            eq = parse_equation(tok)
            fac = linear_factors_eq(compact(tok))
            matched = False
            if fac:
                gold_roots = _gold_roots(spec)
                if gold_roots and set(fac) & set(gold_roots):
                    matched = True
                if gold_roots and sorted(fac) == sorted(gold_roots):
                    matched = True
            if eq:
                for _ans, geq in gold_eqs:
                    if sympy_eq_equiv(eq, geq):
                        matched = True
                # x=-2 与裸值
                asg = assignment(eq) if eq else None
                if asg:
                    for _ans, gn, gvar in gold_nums:
                        if nums_equiv(("num", asg[1]), gn, tok) or nums_equiv(("num", Fraction(str(asg[1]))), gn, tok):
                            matched = True
            if matched:
                if ctx["probe"] and _is_point_vs_interval(tok, gold_ivs):
                    continue
                if _allow_student(ctx, True):
                    continue
                if ctx["neutral_opt"]:
                    continue
                hits.append(LeakHit(lineno, "方程", snippet))

        # 区间
        whole_iv = parse_interval(scan) or _parse_cn_ineq(scan)
        if whole_iv and gold_ivs:
            for _ans, giv in gold_ivs:
                if iv_eq(whole_iv, giv) or iv_finite_endpoint_diff(whole_iv, giv) or iv_is_component(whole_iv, giv):
                    if not ctx["probe"] and not _allow_student(ctx, True):
                        hits.append(LeakHit(lineno, "区间", snippet))
                    break
        for m in INEQ_TOKEN_RE.finditer(scan):
            tok = m.group(0)
            iv = parse_interval(tok)
            if iv is None:
                # 中文整句
                iv = parse_interval(unit_wo)
            if iv is None:
                if ctx["assert"] and use_sympy() is None and gold_ivs:
                    # 拿不准就拦：断言里像范围
                    if re.search(r"大于|小于|范围|解集|∈", tok):
                        if not ctx["probe"] and not ctx["student"]:
                            hits.append(LeakHit(lineno, "区间", snippet))
                continue
            for _ans, giv in gold_ivs:
                if iv_eq(iv, giv) or iv_finite_endpoint_diff(iv, giv) or iv_is_component(iv, giv):
                    if ctx["probe"]:
                        continue
                    if _allow_student(ctx, True):
                        continue
                    hits.append(LeakHit(lineno, "区间", snippet))
                    break
            if sympy_rel_equiv(tok, gold_ivs[0][0] if gold_ivs else ""):
                if gold_ivs and not ctx["probe"] and not _allow_student(ctx, True):
                    hits.append(LeakHit(lineno, "区间", snippet))

        # 有限集
        for m in SET_TOKEN_RE.finditer(scan):
            tok = m.group(0)
            if "|" in tok or "mid" in tok:
                continue
            st = _parse_finite_set(tok)
            gold_roots = _gold_roots(spec)
            if st and gold_roots and set(st) == set(gold_roots):
                if not _allow_student(ctx, True):
                    hits.append(LeakHit(lineno, "数值", snippet))

        # 数值（含单位、根式、百分数、汉字）
        for m in NUM_TOKEN_RE.finditer(scan):
            tok = m.group(0)
            if _inside_ordinal(unit, tok):
                continue
            n = parse_number_token(tok) or parse_cn_quantity(tok)
            if n is None:
                continue
            # 单独的个位数若只是系数/题干数字：仍要比对金标，不等则自然不中
            hit_num = False
            for _ans, gn, _gvar in gold_nums:
                if nums_equiv(n, gn, tok):
                    hit_num = True
            # 根/值匹配多根金标中的一条
            gold_roots = _gold_roots(spec)
            if n[0] == "num" and gold_roots:
                if any(abs(float(n[1]) - r) < 1e-10 for r in gold_roots):
                    hit_num = True
            if hit_num:
                # 点落在区间金标 → 不算
                if gold_ivs and not gold_nums:
                    continue
                if gold_ivs and _point_in_ivs(n, gold_ivs) and not gold_eqs:
                    # 既有区间金标又没有等式金标时，点值是试探
                    if not any(nums_equiv(n, gn, tok) for _a, gn, _v in gold_nums):
                        continue
                if ctx["probe"] and gold_ivs:
                    continue
                if _allow_student(ctx, True):
                    continue
                if ctx["neutral_opt"]:
                    continue
                # 7 和 4 拆开不应等于 7/4：NUM_TOKEN 是分开的，nums_equiv 不会把 7 比成 7/4
                hits.append(LeakHit(lineno, "数值", snippet))

        # 英语 / 中文 greater than
        if gold_ivs and re.search(r"greater than\s+\d+|必须大于|要满足", unit, re.IGNORECASE):
            iv = parse_interval(unit) or _parse_cn_ineq(compact(unit))
            if iv:
                for _ans, giv in gold_ivs:
                    if iv_eq(iv, giv) or iv_finite_endpoint_diff(iv, giv):
                        if not _allow_student(ctx, True) and not ctx["probe"]:
                            hits.append(LeakHit(lineno, "区间", snippet))

    return _dedupe(hits)


def _inside_ordinal(unit, tok):
    for m in ORDINAL_SKIP_RE.finditer(unit):
        if tok in m.group(0):
            return True
    return False


def _skip_formula_letters(tok):
    t = compact(tok)
    if re.fullmatch(r"[abcxyz]=[abcxyz+\-*/0-9]+", t) and not re.search(r"\d", t.split("=")[1] if "=" in t else t):
        return True
    return bool("Δ" in tok or "b^2-4ac" in compact(tok).replace("²", "^2"))


def _gold_roots(spec: GoldSpec):
    roots = []
    for ans in spec.answers:
        eq = parse_equation(ans)
        if eq and re.fullmatch(r"[a-zA-Z]", eq[0]):
            n = parse_number_token(eq[1])
            if n and n[0] == "num":
                roots.append(float(n[1]))
        else:
            n = parse_number_token(ans)
            if n and n[0] == "num":
                roots.append(float(n[1]))
    return roots


def _parse_finite_set(raw):
    s = compact(raw)
    m = re.fullmatch(r"\{([^{}|]+)\}", s)
    if not m:
        return None
    inner = m.group(1)
    if any(op in inner for op in "<>≤≥|"):
        return None
    parts = re.split(r"[,，、]", inner)
    nums = []
    for p in parts:
        n = parse_number_token(p)
        if n is None or n[0] != "num":
            return None
        nums.append(float(n[1]))
    return nums


def _point_in_ivs(n, gold_ivs):
    val = _to_float_num(n)
    if val is None:
        return False
    for _ans, iv in gold_ivs:
        for lo, li, hi, hi_i in iv.parts:
            ok_lo = lo is None or (val > float(lo) or (li and abs(val - float(lo)) < 1e-12))
            ok_hi = hi is None or (val < float(hi) or (hi_i and abs(val - float(hi)) < 1e-12))
            if ok_lo and ok_hi:
                return True
    return False


def _is_point_vs_interval(tok, gold_ivs):
    eq = parse_equation(tok)
    if not eq or not gold_ivs:
        return False
    asg = assignment(eq)
    return bool(asg)


def _allow_student(ctx, value_is_gold):
    if ctx["first_person"]:
        return False
    if ctx["subst"] or ctx["either"] or ctx["leading"]:
        return False
    if not ctx["student"]:
        return False
    if not value_is_gold:
        return True
    return not ctx["eval"]


def _dedupe(hits):
    seen = set()
    out = []
    for h in hits:
        key = (h.lineno, h.category, h.snippet)
        if key in seen:
            continue
        seen.add(key)
        out.append(h)
    return out


def _option_leaks(text, spec, labels, gold_labs, contents, vq, stem):
    if not gold_labs and not contents:
        # 无 options 时仍可按答案字母
        if not labels:
            return []
    hits = []
    for lineno, unit, a, b in iter_units(text):
        if span_inside(a, b, vq):
            continue
        ctx = unit_context(unit, text, a, b, stem)
        snippet = unit.replace("\n", " ")[:36]
        if ctx["neutral_opt"] and not CHOICE_ASSERT_RE.search(unit) and not ELIM_RE.search(unit):
            continue
        found = extract_labels(unit, labels) if labels else extract_labels(unit, list("ABCD") if gold_labs <= set("ABCD") else [])
        # 内容作答
        for lab, body in contents.items():
            if body and compact(body) and compact(body) in compact(unit):
                if re.search(r"就是答案|is the answer|fill in|正确答案|那个就是", unit, re.IGNORECASE):
                    found.add(_norm_label(lab))
        # 选择断言
        choosing = bool(
            CHOICE_ASSERT_RE.search(unit) or ctx["first_person"] or ctx["leading"]
            or ctx["eval"] or "✅" in unit or "✓" in unit
            or re.search(r"就是答案|is the answer|fill in|那个就是", unit, re.IGNORECASE)
        )
        if choosing and found and (found & gold_labs):
            if ctx["student"] and not ctx["eval"] and found <= gold_labs:
                # 学生中性复述金标选项
                if not ctx["first_person"]:
                    continue
            if ctx["first_person"] or not ctx["student"] or ctx["eval"]:
                hits.append(LeakHit(lineno, "选项", snippet))
                continue
        # 部分多选：断言金标任一标签
        if choosing and found and found <= gold_labs and found:
            if not (ctx["student"] and not ctx["eval"]):
                hits.append(LeakHit(lineno, "选项", snippet))
        # 排除
        if ELIM_RE.search(unit) and labels:
            excluded = extract_labels(unit, labels)
            # 「A、B、C 都可以排除」
            remain = set(labels) - excluded
            if remain and remain <= gold_labs and not ctx["neutral_opt"]:
                hits.append(LeakHit(lineno, "排除", snippet))
            # 「所以只剩一个」且前面连续点名非金标
            if re.search(r"只剩", unit) and excluded and (set(labels) - excluded) <= gold_labs:
                hits.append(LeakHit(lineno, "排除", snippet))
        # 英语 B fits / Option D
        if labels and re.search(r"\bfits here\b|option\s+[a-d]\s+is", unit, re.IGNORECASE):
            found2 = extract_labels(unit, labels)
            if found2 & gold_labs:
                hits.append(LeakHit(lineno, "选项", snippet))
    if labels and gold_labs and ELIM_RE.search(text):
        excluded = extract_labels(text, labels)
        remain = {_norm_label(x) for x in labels} - excluded
        if remain and remain <= gold_labs:
            ln = 1
            for i, line in enumerate(text.splitlines(), 1):
                if ELIM_RE.search(line) or extract_labels(line, labels):
                    ln = i
            hits.append(LeakHit(ln, "排除", text.splitlines()[ln - 1][:36] if text.splitlines() else text[:36]))
    return hits


def filter_regex_hits(text, items, stem):
    """items: (lineno, line, start, end, why)。完全落在已核验题干引用里的撤掉。

    现行 ANSWER_LEAK 里「因此…> 数字」是贪婪匹配，可能吃到引号外。
    起点落在已核验引用内时视为题干引用，不拦。
    """
    vq = verified_quote_spans(text, stem)
    kept = []
    for item in items:
        _lineno, _line, start, end, _why = item
        if span_inside(start, end, vq) or any(s <= start < e for s, e in vq):
            continue
        kept.append(item)
    return kept


def regex_hits(pattern, text):
    out = []
    for m in re.finditer(pattern, text):
        lineno = text[:m.start()].count("\n") + 1
        line = text.splitlines()[lineno - 1].strip() if text.splitlines() else ""
        out.append((lineno, line, m.start(), m.end()))
    return out
