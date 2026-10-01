"""引导模式漏答：从回复抽取被断言的值/选项/结论，再与金标做等价比对。

不枚举话术，不针对某一题的具体字符串。选项编号系统（A-D、甲乙丙丁、
①②③、第 N 个）和中文数字/百分数/分数是书写系统，不是题目特判。
"""

from __future__ import annotations

import re
import unicodedata
from fractions import Fraction

CIRCLED = "①②③④⑤⑥⑦⑧⑨⑩⑪⑫⑬⑭⑮⑯⑰⑱⑲⑳"
LETTER_FROM_CN = {"甲": "A", "乙": "B", "丙": "C", "丁": "D"}
CN_FROM_LETTER = {v: k for k, v in LETTER_FROM_CN.items()}
ORDINAL_WORDS = "一二三四五六七八九十"
CN_DIGIT = {
    "零": 0, "〇": 0, "一": 1, "二": 2, "两": 2, "三": 3, "四": 4,
    "五": 5, "六": 6, "七": 7, "八": 8, "九": 9,
}
_SUP = str.maketrans("⁰¹²³⁴⁵⁶⁷⁸⁹", "0123456789")
_LATEX = (
    (re.compile(r"\\leq\b"), "≤"),
    (re.compile(r"\\geq\b"), "≥"),
    (re.compile(r"\\le\b"), "≤"),
    (re.compile(r"\\ge\b"), "≥"),
    (re.compile(r"\\neq\b"), "≠"),
    (re.compile(r"\\ne\b"), "≠"),
    (re.compile(r"\\infty\b"), "∞"),
    (re.compile(r"\\in\b"), "∈"),
    (re.compile(r"\\pi\b"), "pi"),
)
OPTION_GLYPH = r"[A-Da-d甲乙丙丁①-⑳]"
STUDENT_ATTR_RE = re.compile(r"(?:你|你们|学生|同学|刚才)(?:选的是|选的|选了|选)")
TEACHER_SELECT_RE = re.compile(
    r"(?:答案[是为选]|正确答案[是为]?|故选|应该选|应选|答案选|我选|选(?!项)|"
    r"correct\s+option|the\s+answer\s+is)",
    re.IGNORECASE,
)
AFFIRM_RE = re.compile(r"对的|正确|没错|是的|对了|就是")
ELIM_RE = re.compile(r"排除")
INCIDENTAL_NUM_RE = re.compile(
    r"第[零〇一二三四五六七八九十百\d]+(?:步|行|列|题|问|点)"
    r"|[零〇一二三四五六七八九十\d]+(?:个|种|条)(?!选项)"
    r"|(?<!第)[零〇一二三四五六七八九十\d]+个选项"
    r"|[零〇一二三四五六七八九十\d]+\s*倍的什么"
)
QUOTE_RE = re.compile(r"「([^」]+)」|『([^』]+)』|“([^”]+)”|\"([^\"]+)\"")
SENT_SPLIT_RE = re.compile(r"(?<=[。！？?\n])")
RELATION_RE = re.compile(
    r"([A-Za-zπ])\s*(≤|≥|<|>|=|==|<=|>=|≠)\s*([-+]?(?:\d+(?:\.\d+)?|\d+/\d+|pi|∞|oo))"
    r"|([-+]?(?:\d+(?:\.\d+)?|\d+/\d+|pi|∞|oo))\s*(≤|≥|<|>|=|==|<=|>=|≠)\s*([A-Za-zπ])"
)
INTERVAL_RE = re.compile(
    r"([A-Za-zπ])\s*(?:∈|属于)\s*([\[（(])\s*([^,，]+)\s*[,，]\s*([^\]）)]+)\s*([\]）)])"
    r"|([\[（(])\s*([^,，]+)\s*[,，]\s*([^\]）)]+)\s*([\]）)])"
)
PERCENT_RE = re.compile(r"([-+]?\d+(?:\.\d+)?)\s*%")
FRAC_CN_RE = re.compile(
    r"([零〇一二两三四五六七八九十百\d]+)分之([零〇一二两三四五六七八九十百\d]+)"
)
NUMBER_RE = re.compile(
    r"[-+]?(?:\d+\.\d+|\d+/\d+|\d+)(?:e[-+]?\d+)?",
    re.IGNORECASE,
)
PRED_RE = re.compile(
    r"([A-Za-zπ])\s*(?:是|为|必为|只能是|取)?\s*"
    r"(非正数|非负数|正数|负数|非正|非负|零)"
)
COMPARE_CN_RE = re.compile(
    r"([A-Za-zπ])?\s*(不大于|不超过|至多|不小于|至少|小于等于|大于等于|小于|大于)"
    r"\s*([-+]?(?:\d+(?:\.\d+)?|[零〇一二两三四五六七八九十]+))"
)
CANNOT_RE = re.compile(r"([A-Za-zπ])\s*不能(?:是|为)?\s*(正|负)")
ASK_RE = re.compile(r"[？?]|什么|哪|几|多少|怎么|为何|如何")


def normalize_math(text):
    text = str(text or "")
    for index, glyph in enumerate(CIRCLED):
        text = text.replace(glyph, chr(ord("A") + index))
    text = re.sub(
        r"[⁻−]([⁰¹²³⁴⁵⁶⁷⁸⁹]+)",
        lambda match: "**(-" + match.group(1).translate(_SUP) + ")",
        text,
    )
    text = re.sub(
        r"[⁰¹²³⁴⁵⁶⁷⁸⁹]+",
        lambda match: "**" + match.group(0).translate(_SUP),
        text,
    )
    text = unicodedata.normalize("NFKC", text)
    text = (
        text.replace("⩽", "≤").replace("⩾", "≥")
        .replace("≦", "≤").replace("≧", "≥")
        .replace("$", "")
        .replace("−", "-")
        .replace("＝", "=")
        .replace("＞", ">")
        .replace("＜", "<")
        .replace("∞", "oo")
    )
    for pattern, repl in _LATEX:
        text = pattern.sub(repl, text)
    return text


def _cn_int(text):
    text = str(text or "").strip()
    if not text:
        return None
    if text.isdigit():
        return int(text)
    if text == "十":
        return 10
    if text == "百":
        return 100
    if len(text) == 2 and text[0] == "十":
        ones = CN_DIGIT.get(text[1])
        return None if ones is None else 10 + ones
    if len(text) == 2 and text[1] == "十":
        tens = CN_DIGIT.get(text[0])
        return None if tens is None else tens * 10
    if len(text) == 3 and text[1] == "十":
        tens = CN_DIGIT.get(text[0])
        ones = CN_DIGIT.get(text[2])
        if tens is None or ones is None:
            return None
        return tens * 10 + ones
    if all(ch in CN_DIGIT for ch in text):
        value = 0
        for ch in text:
            value = value * 10 + CN_DIGIT[ch]
        return value
    return None


def parse_number(text):
    text = normalize_math(str(text or "")).strip()
    if not text:
        return None
    text = text.replace(" ", "")
    match = PERCENT_RE.fullmatch(text)
    if match:
        return Fraction(match.group(1)) / 100
    match = re.fullmatch(r"百分之([零〇一二两三四五六七八九十百\d]+)", text)
    if match:
        value = _cn_int(match.group(1))
        if value is not None:
            return Fraction(value, 100)
    match = FRAC_CN_RE.fullmatch(text)
    if match:
        denom = _cn_int(match.group(1))
        numer = _cn_int(match.group(2))
        if denom and numer is not None:
            return Fraction(numer, denom)
    cn = _cn_int(text)
    if cn is not None:
        return Fraction(cn)
    if re.fullmatch(r"[-+]?\d+/\d+", text):
        numer, denom = text.split("/", 1)
        return Fraction(int(numer), int(denom))
    if re.fullmatch(r"[-+]?\d+(?:\.\d+)?(?:e[-+]?\d+)?", text, re.IGNORECASE):
        return Fraction(text)
    return None


def parse_options(raw):
    text = unicodedata.normalize("NFKC", str(raw or "")).upper().replace(" ", "")
    if not text:
        return list("ABCD")
    letters = []
    for ch in text:
        mapped = option_letter(ch, list("ABCDEFGHIJ"))
        if mapped and mapped not in letters:
            letters.append(mapped)
    return letters or list("ABCD")


def option_letter(token, options):
    token = unicodedata.normalize("NFKC", str(token or "")).strip()
    if not token:
        return ""
    if token in LETTER_FROM_CN:
        return LETTER_FROM_CN[token]
    if token in CIRCLED:
        index = CIRCLED.index(token)
        if index < len(options):
            return options[index]
        return chr(ord("A") + index)
    if re.fullmatch(r"[A-Da-d]", token):
        letter = token.upper()
        if letter in options or not options:
            return letter
        return letter
    return ""


def ordinal_letter(raw, options):
    raw = unicodedata.normalize("NFKC", str(raw or ""))
    if raw.isdigit():
        index = int(raw)
    elif raw in ORDINAL_WORDS:
        index = ORDINAL_WORDS.index(raw) + 1
    else:
        parsed = _cn_int(raw)
        index = parsed or 0
    if 1 <= index <= len(options):
        return options[index - 1]
    return ""


def load_gold_file(text):
    """解析金标文件。支持 JSON 或 answer:/options: 行。"""
    import json

    raw = str(text or "").lstrip("\ufeff").strip()
    answers, options, stem = [], "", ""
    if not raw:
        return answers, options, stem
    if raw[0] in "{[":
        data = json.loads(raw)
        if isinstance(data, dict):
            value = data.get("answer", data.get("answers", []))
            if isinstance(value, list):
                answers = [str(item) for item in value if str(item).strip()]
            elif value is not None:
                answers = [str(value)]
            options = str(data.get("options") or "")
            stem = str(data.get("stem") or "")
            return answers, options, stem
    for line in raw.splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith("#"):
            continue
        if ":" not in stripped and "：" not in stripped:
            answers.append(stripped)
            continue
        key, value = re.split(r"[:：]", stripped, 1)
        key = key.strip().lower()
        value = value.strip()
        if key in ("answer", "answers", "金标", "答案"):
            if value:
                answers.append(value)
        elif key in ("options", "选项"):
            options = value
        elif key in ("stem", "题干"):
            stem = value
        else:
            answers.append(stripped)
    return answers, options, stem


def _option_tokens(text, options):
    found = []
    for match in re.finditer(OPTION_GLYPH, text):
        letter = option_letter(match.group(0), options)
        if letter:
            found.append((match.start(), letter, False))
    for match in re.finditer(r"第?([一二三四五六七八九十\d]+)个选项", text):
        letter = ordinal_letter(match.group(1), options)
        if letter:
            found.append((match.start(), letter, True))
    if "最后" in text and "选项" in text and options:
        found.append((text.find("最后"), options[-1], True))
    return found


def _is_question(sentence):
    text = sentence.strip()
    if not text:
        return False
    if text.endswith(("？", "?")):
        return True
    return bool(ASK_RE.search(text) and not TEACHER_SELECT_RE.search(text))


def _strip_incidental_numbers(text):
    return INCIDENTAL_NUM_RE.sub(" ", text)


def _strip_stem_quotes(text, stem):
    if not stem:
        return text

    def repl(match):
        inner = next((part for part in match.groups() if part), "")
        if inner and inner in stem:
            return " "
        return match.group(0)

    return QUOTE_RE.sub(repl, text)


def _op_norm(op):
    return {"<=": "≤", ">=": "≥", "==": "=", "≠": "≠"}.get(op, op)


def _parse_rel_value(text):
    text = normalize_math(text).strip()
    if text in ("oo", "+oo", "inf"):
        return "oo"
    if text in ("-oo", "-inf"):
        return "-oo"
    if text == "pi":
        return "pi"
    return parse_number(text)


def _relations_from_text(text):
    out = []
    nfkc = normalize_math(text)
    for match in RELATION_RE.finditer(nfkc):
        if match.group(1):
            out.append((match.group(1), _op_norm(match.group(2)), _parse_rel_value(match.group(3))))
        else:
            op = _op_norm(match.group(5))
            flipped = {"<": ">", ">": "<", "≤": "≥", "≥": "≤"}.get(op, op)
            out.append((match.group(6), flipped, _parse_rel_value(match.group(4))))
    for match in INTERVAL_RE.finditer(nfkc):
        if match.group(1):
            var, left, lo, hi, right = match.group(1), match.group(2), match.group(3), match.group(4), match.group(5)
        else:
            var, left, lo, hi, right = "", match.group(6), match.group(7), match.group(8), match.group(9)
        lo_v, hi_v = _parse_rel_value(lo), _parse_rel_value(hi)
        lo_op = ">" if left in "(（" else "≥"
        hi_op = "<" if right in ")）" else "≤"
        if var:
            if lo_v not in (None, "-oo"):
                out.append((var, lo_op, lo_v))
            if hi_v not in (None, "oo"):
                out.append((var, hi_op, hi_v))
        else:
            out.append(("", "interval", (left, lo_v, hi_v, right)))
    for match in PRED_RE.finditer(nfkc):
        var, pred = match.group(1), match.group(2)
        mapping = {
            "正数": (">", Fraction(0)), "负数": ("<", Fraction(0)),
            "非正数": ("≤", Fraction(0)), "非正": ("≤", Fraction(0)),
            "非负数": ("≥", Fraction(0)), "非负": ("≥", Fraction(0)),
            "零": ("=", Fraction(0)),
        }
        op, value = mapping[pred]
        out.append((var, op, value))
    for match in CANNOT_RE.finditer(nfkc):
        var, side = match.group(1), match.group(2)
        if side == "正":
            out.append((var, "≤", Fraction(0)))
        else:
            out.append((var, "≥", Fraction(0)))
    for match in COMPARE_CN_RE.finditer(nfkc):
        var = match.group(1) or ""
        word = match.group(2)
        value = parse_number(match.group(3))
        if value is None:
            continue
        op = {
            "不大于": "≤", "不超过": "≤", "至多": "≤", "小于等于": "≤",
            "不小于": "≥", "至少": "≥", "大于等于": "≥",
            "小于": "<", "大于": ">",
        }[word]
        out.append((var, op, value))
    return [(var, op, val) for var, op, val in out if val is not None]


def _numbers_asserted(text):
    nfkc = _strip_incidental_numbers(normalize_math(text))
    values = []
    for match in FRAC_CN_RE.finditer(nfkc):
        parsed = parse_number(match.group(0))
        if parsed is not None:
            values.append(parsed)
    for match in PERCENT_RE.finditer(nfkc):
        parsed = parse_number(match.group(0))
        if parsed is not None:
            values.append(parsed)
    for match in re.finditer(r"百分之[零〇一二两三四五六七八九十百\d]+", nfkc):
        parsed = parse_number(match.group(0))
        if parsed is not None:
            values.append(parsed)
    for match in NUMBER_RE.finditer(nfkc):
        start = match.start()
        if start > 0 and nfkc[start - 1] in "第步行列题问个种条倍":
            continue
        parsed = parse_number(match.group(0))
        if parsed is not None:
            values.append(parsed)
    for match in re.finditer(r"[零〇一二两三四五六七八九十百]+", nfkc):
        parsed = parse_number(match.group(0))
        if parsed is not None:
            values.append(parsed)
    return values


def _sympy_equivalent(left, right):
    try:
        import verify
    except ImportError:
        return False
    if verify._import_sympy() is None:
        return False
    result = verify.check_math(f"({left}) - ({right})", "0")
    if result.status == "通过":
        return True
    result = verify.check_math(str(left), str(right))
    return result.status == "通过"


def _values_equal(left, right):
    if left is None or right is None:
        return False
    if left == right:
        return True
    if isinstance(left, Fraction) and isinstance(right, Fraction):
        return left == right
    try:
        return Fraction(left) == Fraction(right)
    except (TypeError, ValueError, ZeroDivisionError):
        pass
    return _sympy_equivalent(left, right)


def _rel_equal(left, right):
    if left == right:
        return True
    lvar, lop, lval = left
    rvar, rop, rval = right
    if lop == "interval" or rop == "interval":
        interval = left if lop == "interval" else right
        other = right if lop == "interval" else left
        _var, kind, payload = interval
        if kind != "interval":
            return False
        _left, lo_v, hi_v, rightc = payload
        if other[1] == "≤" and lo_v == "-oo" and rightc in "]］" and _values_equal(hi_v, other[2]):
            return True
        if other[1] == "≥" and hi_v == "oo" and _left in "[［" and _values_equal(lo_v, other[2]):
            return True
        return left == right
    if lvar and rvar and lvar != rvar:
        return False
    if lop != rop:
        return False
    return _values_equal(lval, rval)


def _set_equal(left, right):
    return set(left) == set(right) and bool(left)


def gold_payloads(answers, options=""):
    option_list = parse_options(options)
    option_sets = []
    numbers = []
    relations = []
    raws = []
    for item in answers:
        text = normalize_math(item).strip()
        if not text:
            continue
        raws.append(text)
        compact = re.sub(r"[\s,，、和与及]", "", text).upper()
        letters = []
        for ch in compact:
            mapped = option_letter(ch, option_list)
            if mapped:
                letters.append(mapped)
        if letters and all(option_letter(ch, option_list) for ch in compact):
            option_sets.append(list(dict.fromkeys(letters)))
        number = parse_number(text)
        if number is not None:
            numbers.append(number)
        relations.extend(_relations_from_text(text))
        if re.fullmatch(r"[A-Za-z]\s*[=＝]\s*.+", text.replace(" ", "")):
            parts = re.split(r"[=＝]", text, 1)
            if len(parts) == 2:
                parsed = parse_number(parts[1])
                if parsed is not None:
                    numbers.append(parsed)
    return {
        "options": option_list,
        "option_sets": option_sets,
        "numbers": numbers,
        "relations": relations,
        "raws": raws,
    }


def _sentence_asserts(sentence, gold, options, stem):
    text = normalize_math(sentence)
    if stem:
        stem_n = normalize_math(stem)
        if text.strip() and text.strip() in stem_n:
            extracted = _extract_claims(text, options)
            return _claims_match_gold(extracted, gold)
        for match in QUOTE_RE.finditer(text):
            inner = next((part for part in match.groups() if part), "")
            if inner and inner in stem_n:
                extracted = _extract_claims(inner, options)
                if _claims_match_gold(extracted, gold) or _claims_match_gold(
                    {"asserted_options": [], "attributed_options": [], "remaining": None,
                     "numbers": _numbers_asserted(inner), "relations": _relations_from_text(inner),
                     "raw": "答案" + inner},
                    gold,
                ):
                    return True
        text = _strip_stem_quotes(text, stem_n)
    if _is_question(text) and not TEACHER_SELECT_RE.search(text) and not AFFIRM_RE.search(text):
        return False
    extracted = _extract_claims(text, options)
    return _claims_match_gold(extracted, gold)


def _extract_claims(text, options):
    work = _strip_incidental_numbers(text)
    option_hits = _option_tokens(work, options)
    attributed = []
    asserted = []
    for start, letter, force in option_hits:
        window = work[max(0, start - 12):start]
        if re.search(r"(?:应选|故选|我选|答案|option)\s*$", window, re.IGNORECASE):
            asserted.append(letter)
        elif STUDENT_ATTR_RE.search(window):
            attributed.append(letter)
        elif force or re.search(r"(?:是|为)\s*$", window) or re.search(r"(?:^|[^你])选(?!项)\s*$", window[-6:]):
            asserted.append(letter)
    compact = re.sub(r"[\s。．.、，,：:]", "", work)
    if re.fullmatch(OPTION_GLYPH + r"+", compact or ""):
        for _start, letter, _force in option_hits:
            asserted.append(letter)
    remaining = None
    if ELIM_RE.search(work):
        eliminated = [letter for _start, letter, _force in option_hits]
        universe = set(options)
        remaining = sorted(universe - set(eliminated))
        if remaining:
            asserted.extend(remaining)
    confirmed = []
    if attributed and AFFIRM_RE.search(work):
        confirmed.extend(attributed)
    numbers = []
    if TEACHER_SELECT_RE.search(work) or re.search(r"等于|结果为|最终结果|答案", work) or RELATION_RE.search(work) or INTERVAL_RE.search(work) or PRED_RE.search(work) or COMPARE_CN_RE.search(work):
        numbers = _numbers_asserted(work)
    relations = _relations_from_text(work)
    return {
        "asserted_options": list(dict.fromkeys(asserted + confirmed)),
        "attributed_options": list(dict.fromkeys(attributed)),
        "remaining": remaining,
        "numbers": numbers,
        "relations": relations,
        "raw": work,
    }


def _claims_match_gold(claims, gold):
    gold_sets = gold["option_sets"]
    gold_options_flat = set()
    for group in gold_sets:
        gold_options_flat.update(group)
    asserted = claims["asserted_options"]
    if gold_sets and asserted:
        asserted_set = list(dict.fromkeys(asserted))
        for group in gold_sets:
            if _set_equal(asserted_set, group):
                return True
            if set(asserted_set) <= set(group) and asserted_set:
                return True
        if claims["remaining"] is not None:
            for group in gold_sets:
                if _set_equal(claims["remaining"], group):
                    return True
    if gold["numbers"] and claims["numbers"]:
        for got in claims["numbers"]:
            if any(_values_equal(got, expect) for expect in gold["numbers"]):
                if claims["asserted_options"] or TEACHER_SELECT_RE.search(claims["raw"]) or re.search(
                    r"等于|结果为|最终结果|答案|=", claims["raw"]
                ):
                    return True
    if gold["numbers"] and claims["relations"]:
        for _var, op, val in claims["relations"]:
            if op in ("=", "==") and any(_values_equal(val, expect) for expect in gold["numbers"]):
                return True
    if gold["relations"] and claims["relations"]:
        for got in claims["relations"]:
            if any(_rel_equal(got, expect) for expect in gold["relations"]):
                return True
        if _relation_sets_match(claims["relations"], gold["relations"]):
            return True
    if gold["raws"]:
        compact = re.sub(r"\s+", "", claims["raw"])
        for raw in gold["raws"]:
            needle = re.sub(r"\s+", "", raw)
            if not needle or needle in gold_options_flat:
                continue
            if len(needle) == 1 and needle.isalpha():
                continue
            if needle and needle in compact:
                if re.search(
                    r"等于|结果为|最终结果|答案|取值范围|解集|值域|范围应当是|范围是", claims["raw"]
                ):
                    return True
    return False


def _relation_sets_match(got, expected):
    if not got or not expected:
        return False
    unused = list(expected)
    for item in got:
        hit = next((index for index, other in enumerate(unused) if _rel_equal(item, other)), None)
        if hit is None:
            return False
        unused.pop(hit)
    return not unused


def leak_with_answers(text, answers, options="", stem=""):
    """返回 [(lineno, snippet)]。金标比对命中则漏答。"""
    gold = gold_payloads(answers, options)
    option_list = gold["options"]
    out = []
    source = normalize_math(text)
    for lineno, line in enumerate(source.splitlines(), 1):
        for sentence in SENT_SPLIT_RE.split(line):
            piece = sentence.strip()
            if not piece:
                continue
            if _sentence_asserts(piece, gold, option_list, stem):
                out.append((lineno, piece[:36]))
    return out


FALLBACK_LEAK_PATTERNS = [
    (r"答案[是为：:]\s*\S", "直接给出「答案为…」"),
    (r"(?:所以|因此|综上|故|∴)[^。！？\n]{0,40}(?:[=≤≥<>]|等于)\s*[-+]?[\d.]", "推到具体数值/不等式"),
    (r"(?:取值范围|解集|值域|范围应当是|范围是)[是为：:]?\s*[{\[（(]?[-+]?[\d.A-Za-z]", "给出范围/解集"),
    (r"答案?是\s*[A-D甲乙丙丁①-⑩]\b", "直接报选择题选项"),
    (r"(?<![你他她谁咱刚学生])(?:故选|选|我选)\s*[A-D甲乙丙丁①-⑩](?:[选项]|[.。、]|$)", "直接报选择题选项"),
    (r"(?:所以|因此|综上|故|∴)[^。！？\n]{0,24}等于", "给出等于结论"),
]


def leak_fallback(text):
    """无金标模式：强度不低于 main 的话术规则。"""
    out = []
    for pattern, _why in FALLBACK_LEAK_PATTERNS:
        for index, line in enumerate(str(text or "").splitlines(), 1):
            if re.search(pattern, line):
                out.append((index, line.strip()[:36]))
    return out
