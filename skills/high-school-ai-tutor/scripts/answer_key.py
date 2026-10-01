"""引导模式漏答：用题库金标答案比对，而不是枚举话术。"""

from __future__ import annotations

import re
import unicodedata

CN_DIGIT = {
    "零": "0", "〇": "0", "一": "1", "二": "2", "两": "2", "三": "3", "四": "4",
    "五": "5", "六": "6", "七": "7", "八": "8", "九": "9",
}
EN_NUM = {
    "zero": "0", "one": "1", "two": "2", "three": "3", "four": "4", "five": "5",
    "six": "6", "seven": "7", "eight": "8", "nine": "9", "ten": "10",
}
LETTER_FROM_CN = {"甲": "A", "乙": "B", "丙": "C", "丁": "D"}
CN_FROM_LETTER = {v: k for k, v in LETTER_FROM_CN.items()}
CIRCLED = "①②③④⑤⑥⑦⑧⑨⑩"
ORDINAL_WORDS = "一二三四五六七八九十"
_SUP = str.maketrans("⁰¹²³⁴⁵⁶⁷⁸⁹", "0123456789")
_LATEX = (
    (re.compile(r"\\leq\b"), "≤"),
    (re.compile(r"\\geq\b"), "≥"),
    (re.compile(r"\\le\b"), "≤"),
    (re.compile(r"\\ge\b"), "≥"),
    (re.compile(r"\\neq\b"), "≠"),
    (re.compile(r"\\ne\b"), "≠"),
    (re.compile(r"\\ngtr\b"), "≯"),
    (re.compile(r"\\nless\b"), "≮"),
    (re.compile(r"\\notin\b"), "∉"),
    (re.compile(r"\\in\b"), "∈"),
    (re.compile(r"\\infty\b"), "∞"),
)
FALLBACK_LEAK_RE = re.compile(
    r"(?:【答案】|答案\s*→|correct\s+option"
    r"|(?:答案|故选|(?<![你生学们哥])选|故|所以)[^\n]{0,12}(?:[A-Da-d甲乙丙丁①-⑩]|\d))",
    re.I,
)
CONFIRM_RE = re.compile(r"没错|很好|就是它|是正确答案|是对的|正确|对了")
RESTATE_RE = re.compile(
    r"(?:你选的是|你选的|你选|你们选|学生选|同学选|刚才选)\s*([A-Da-d甲乙丙丁①-⑩]+)"
)
ELIM_RE = re.compile(r"排除\s*([A-Da-d甲乙丙丁、，,和与及\s]+)")
QUOTE_RE = re.compile(r"「([^」]+)」|『([^』]+)』|“([^”]+)”|\"([^\"]+)\"")
NUM_CLASSIFIER_RE = re.compile(
    r"(?:第.+(?:行|列)|几种|种方法|个条件|个选项|倍的什么|怎么写|是什么)"
)
SHORT_NUM_SKIP_RE = re.compile(
    r"(?:[零〇一二两三四五六七八九\d]+)(?:个|种|倍|行|列|步|条|题|问)"
)


def normalize_math(text):
    text = str(text or "")
    for index, glyph in enumerate(CIRCLED):
        text = text.replace(glyph, chr(ord("A") + index))
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
    )
    for pattern, repl in _LATEX:
        text = pattern.sub(repl, text)
    text = re.sub(
        r"([零〇一二两三四五六七八九]+)分之([零〇一二两三四五六七八九]+)",
        lambda match: _cn_int(match.group(2)) + "/" + _cn_int(match.group(1)),
        text,
    )
    for word, digit in EN_NUM.items():
        text = re.sub(rf"\b{word}\b", digit, text, flags=re.I)
    return text


def _cn_int(text):
    if text == "十":
        return "10"
    return "".join(CN_DIGIT.get(ch, ch) for ch in text)


def parse_options(raw):
    text = unicodedata.normalize("NFKC", str(raw or "")).upper().replace(" ", "")
    if not text:
        return list("ABCD")
    letters = re.findall(r"[A-D甲乙丙丁①-⑩]", text)
    mapped = []
    for item in letters:
        if item in LETTER_FROM_CN:
            mapped.append(LETTER_FROM_CN[item])
        elif item in CIRCLED:
            mapped.append(chr(ord("A") + CIRCLED.index(item)))
        else:
            mapped.append(item.upper())
    return mapped or list("ABCD")


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
        return token.upper()
    return ""


def ordinal_to_letter(text, options):
    hits = []
    for match in re.finditer(r"第([一二三四五六七八九十\d]+)个选项", text):
        raw = match.group(1)
        if raw.isdigit():
            index = int(raw)
        elif raw == "十":
            index = 10
        else:
            index = ORDINAL_WORDS.index(raw) + 1 if raw in ORDINAL_WORDS else 0
        if 1 <= index <= len(options):
            hits.append(options[index - 1])
    if "最后" in text and "选项" in text and options:
        hits.append(options[-1])
    return hits


def _cn_numeral_forms(number):
    mapping = {
        "0": "零", "1": "一", "2": "二", "3": "三", "4": "四",
        "5": "五", "6": "六", "7": "七", "8": "八", "9": "九",
    }
    text = str(number)
    if text in mapping:
        forms = {text, mapping[text]}
        if text == "2":
            forms.add("两")
        return forms
    return {text}


def expand_gold(gold, options):
    """返回 (option_set, phrase_set)。phrase 已 normalize_math。"""
    options = parse_options(options)
    gold = normalize_math(gold).strip()
    phrases = {gold, gold.replace(" ", "")}
    option_set = set()
    compact = gold.replace(" ", "").upper()
    if re.fullmatch(r"[A-D]{1,4}", compact):
        option_set.update(list(compact))
        option_set.add(compact)
        for letter in list(compact):
            phrases.add(letter)
            phrases.add(CN_FROM_LETTER.get(letter, letter))
            index = options.index(letter) if letter in options else ord(letter) - 65
            if 0 <= index < len(CIRCLED):
                phrases.add(CIRCLED[index])
            if 0 <= index < len(ORDINAL_WORDS):
                phrases.add(f"第{ORDINAL_WORDS[index]}个选项")
    if gold in CIRCLED:
        letter = option_letter(gold, options)
        if letter:
            option_set.add(letter)
            extra_letters, extra_phrases = expand_gold(letter, "".join(options))
            option_set |= extra_letters
            phrases |= extra_phrases
    if re.fullmatch(r"[甲乙丙丁]+", gold):
        letters = "".join(LETTER_FROM_CN[ch] for ch in gold)
        option_set.update(list(letters))
        extra_letters, extra_phrases = expand_gold(letters, "".join(options))
        option_set |= extra_letters
        phrases |= extra_phrases
    phrases.update(_inequality_phrases(gold))
    phrases.update(_value_phrases(gold))
    return option_set, {normalize_math(item) for item in phrases if item}


def _inequality_phrases(gold):
    text = gold.replace(" ", "")
    out = set()
    match = re.fullmatch(r"([A-Za-z])≤([-+]?\d+)", text) or re.fullmatch(
        r"([A-Za-z])<=([-+]?\d+)", text
    )
    if match:
        var, num = match.group(1), match.group(2)
        out.update({
            f"{var}≤{num}", f"{var}<={num}",
            f"{var}不大于{num}", f"{var}不超过{num}", f"{var}至多{num}",
            f"{var}小于等于{num}", f"{var}至多等于{num}",
        })
        if num in {"0", "零"}:
            out.update({
                f"{var}∈(-∞,0]", f"{var}∈(-oo,0]",
                f"{var}是非正数", f"{var}为非正数", f"{var}不能是正的", f"{var}不能为正",
                f"{var}取负值或零", f"{var}取负或零", f"{var}属于负数和零",
                f"{var}∉(0,+∞)", f"{var}∉(0,+oo)", f"{var}不属于(0,+∞)",
                f"{var}≯0", f"{var}不大于零", f"不大于{num}", f"不超过{num}",
                f"(-∞,0]", f"{var}的取值是(-∞,0]",
            })
    match = re.fullmatch(r"([A-Za-z])≥([-+]?\d+)", text) or re.fullmatch(
        r"([A-Za-z])>=([-+]?\d+)", text
    )
    if match:
        var, num = match.group(1), match.group(2)
        out.update({
            f"{var}≥{num}", f"{var}>={num}",
            f"{var}不小于{num}", f"{var}至少{num}", f"{var}大于等于{num}",
        })
    match = re.fullmatch(r"([A-Za-z])>0", text)
    if match:
        var = match.group(1)
        out.update({
            f"{var}>0", f"{var}必为正数", f"{var}是正数", f"{var}为正数",
            f"{var}为正", f"{var}大于0",
        })
    match = re.fullmatch(r"([A-Za-z])=([-+]?\d+(?:\.\d+)?)", text)
    if match:
        var, num = match.group(1), match.group(2)
        forms = _cn_numeral_forms(num)
        out.add(f"{var}={num}")
        out.add(f"{var}等于{num}")
        out.add(f"{var}只能取{num}")
        out.add(f"等于{num}")
        for form in forms:
            out.add(f"{var}={form}")
            out.add(f"{var}等于{form}")
            out.add(f"{var}只能取{form}")
            out.add(f"等于{form}")
    if re.fullmatch(r"[-+]?\d+(?:\.\d+)?", text) or re.fullmatch(r"\d+/\d+", text):
        out.add(text)
        out.add(f"得{text}")
        out.add(f"为{text}")
        out.add(f"是{text}")
        out.add(f"结果为{text}")
        out.add(f"答案为{text}")
        out.add(f"最终结果{text}")
        if text == "2/3":
            out.update({"三分之二", "结果为三分之二", "答案为三分之二"})
        if text == "1/2":
            out.update({"二分之一", "结果为二分之一"})
        if text.isdigit():
            for form in _cn_numeral_forms(text):
                out.add(f"结果为{form}")
                out.add(f"得{form}")
                out.add(f"等于{form}")
                out.add(form)
    match = re.search(r"最大值\s*([-+]?\d+|二|两|三|四|五)", text)
    if match:
        num = match.group(1)
        digit = CN_DIGIT.get(num, num)
        if digit == "两":
            digit = "2"
        for form in _cn_numeral_forms(digit):
            out.add(f"最大值是{form}")
            out.add(f"最大值是 {form}")
            out.add(f"最大值为{form}")
            out.add(f"最大值 {form}")
    return out


def _value_phrases(gold):
    out = set()
    match = re.fullmatch(r"([A-Za-z])=([-+]?\d+(?:\.\d+)?)", gold.replace(" ", ""))
    if match:
        out.add(match.group(0))
    return out


def _sympy_equiv(left, right):
    try:
        import sympy
        from verify import _parse
    except Exception:
        return False
    one = _parse(sympy, _to_sympy_text(left))
    two = _parse(sympy, _to_sympy_text(right))
    if one is None or two is None:
        return False
    try:
        if one == two:
            return True
        if sympy.simplify(one - two) == 0:
            return True
        if hasattr(one, "equals") and one.equals(two):
            return True
        if isinstance(one, sympy.Relational) and isinstance(two, sympy.Relational):
            if type(one) is type(two) and sympy.simplify(one.lhs - two.lhs) == 0:
                if sympy.simplify(one.rhs - two.rhs) == 0:
                    return True
    except Exception:
        return False
    return False


def _to_sympy_text(text):
    text = normalize_math(text)
    text = text.replace("≤", "<=").replace("≥", ">=").replace("≠", "!=").replace("∞", "oo")
    return text


def _is_gold_form(text, gold_phrases):
    compact = normalize_math(text).replace(" ", "").lower()
    for phrase in gold_phrases:
        needle = phrase.replace(" ", "").lower()
        if needle and compact == needle:
            return True
        if needle and _sympy_equiv(compact, needle):
            return True
    return False


def _strip_stem_conditions(reply, stem, gold_phrases):
    stem_n = normalize_math(stem)
    if not stem_n:
        return reply
    reply_n = reply

    def keep_quote(inner):
        compact = normalize_math(inner).replace(" ", "")
        if _is_gold_form(inner, gold_phrases):
            return True
        for phrase in gold_phrases:
            needle = phrase.replace(" ", "")
            if needle and needle.lower() in compact.lower():
                return True
        return False

    def repl_quote(match):
        inner = next((group for group in match.groups() if group is not None), "")
        if inner and inner in stem_n and not keep_quote(inner):
            return " "
        return match.group(0)

    reply_n = QUOTE_RE.sub(repl_quote, reply_n)
    for piece in re.findall(
        r"[A-Za-z][≤≥<>]=?[-+]?\d+|[A-Za-z]=[-+]?\d+",
        stem_n.replace(" ", ""),
    ):
        if piece and not _is_gold_form(piece, gold_phrases):
            reply_n = re.sub(re.escape(piece), " ", reply_n, flags=re.I)
            reply_n = reply_n.replace(piece.replace("<=", "≤").replace(">=", "≥"), " ")
    return reply_n


def _asserted_option(reply, letter):
    patterns = (
        rf"(?:我直接说吧|毫无疑问)[：:，,\s]*{letter}\b",
        rf"答案\s*→\s*{letter}",
        rf"【答案】\s*{letter}",
        rf"答案[是为选其实就是]*\s*{letter}",
        rf"正确答案[是为]?\s*{letter}",
        rf"正确选项[：:]\s*{letter}",
        rf"本题选\s*{letter}",
        rf"correct\s+option\s*[：:]\s*{letter}",
        rf"我选\s*{letter}\b",
        rf"(?:会不会是|是不是|难道不是|先告诉你吧[,，]是|有没有可能是|若选)\s*{letter}\b",
        rf"选项\s*{letter}\s*(?:正确|是对的)",
        rf"{letter}\s*选项(?:是对的|正确)",
        rf"答案选\s*[（(]?\s*{letter}",
        rf"the\s+answer\s+is\s+{letter}",
        rf"最终选\s*{letter}",
        rf"咱们选\s*{letter}",
        rf"不难发现答案\s*{letter}",
        rf"于是得\s*{letter}",
        rf"(?<![你生学们哥])(?:应选|应该选|应当选|故选|提示[:：]选|看出选|也就是说选|即选|选)\s*{letter}\b",
        rf"故选\s*{letter}",
        rf"应选\s*{letter}",
        rf"应该选\s*{letter}",
        rf"应当选\s*{letter}",
    )
    return any(re.search(pattern, reply, re.I) for pattern in patterns)


def _student_confirmed(reply, letter):
    for match in RESTATE_RE.finditer(reply):
        picked = match.group(1)
        mapped = option_letter(picked, "ABCD")
        if mapped != letter and picked.upper() != letter:
            continue
        window = reply[match.start(): match.end() + 24]
        if CONFIRM_RE.search(window):
            return True
        after = reply[match.end(): match.end() + 24]
        if re.search(r"就是它|没错", after):
            return True
    if re.search(rf"你选的\s*{letter}\s*是正确答案", reply, re.I):
        return True
    return False


def _restate_without_judgment(reply, letter):
    if _student_confirmed(reply, letter):
        return False
    cn = CN_FROM_LETTER.get(letter, letter)
    return bool(re.search(
        rf"(?:你选的是|你选的|你选|你们选|学生选|同学选|刚才选)\s*(?:{letter}|{cn})"
        rf"(?!\s*(?:没错|很好|就是它|是正确|是对的|正确))",
        reply,
        re.I,
    ))


def _elimination_leaves(reply, gold_letters, options):
    match = ELIM_RE.search(reply)
    if not match or not gold_letters:
        return False
    dropped = {option_letter(ch, options) for ch in match.group(1) if option_letter(ch, options)}
    remain = [item for item in options if item not in dropped]
    gold = {item for item in gold_letters if len(item) == 1}
    if gold and set(remain) == gold:
        return True
    compact_gold = {item for item in gold_letters if len(item) > 1}
    if compact_gold and "".join(remain) in compact_gold:
        return True
    return False


def _compact(text):
    return re.sub(r"是不是|会不会|难道不是|也许", "", text.replace(" ", ""))


def _short_number(phrase):
    text = phrase.replace(" ", "")
    return bool(re.fullmatch(r"[-+]?\d+(?:\.\d+)?|[零〇一二两三四五六七八九]", text))


def _classifier_context(piece, phrase):
    if not _short_number(phrase):
        return False
    if SHORT_NUM_SKIP_RE.search(piece):
        return True
    if NUM_CLASSIFIER_RE.search(piece):
        return True
    return False


def _phrase_hit(piece, phrase):
    compact = _compact(piece)
    needle = phrase.replace(" ", "")
    if not needle:
        return False
    if _classifier_context(compact, needle):
        return False
    if needle.lower() in compact.lower():
        if _short_number(needle):
            return _number_asserted(compact, needle)
        return True
    return False


def _number_asserted(piece, number):
    forms = {number, number.lower()}
    forms.update(_cn_numeral_forms(number) if number.isdigit() else {number})
    cue = r"(?:答案|结果|等于|得|为|是|只能取|必为|最终|可见|于是|即|可知|故|所以|因此|综上)"
    for form in forms:
        if re.search(
            rf"{cue}\s*[{{［\[]?\s*{re.escape(form)}|{re.escape(form)}\s*(?:对吗|吧|啊|啦)",
            piece,
            re.I,
        ):
            return True
        if re.search(rf"(?:会是|是不是|结果为|最终结果)\s*{re.escape(form)}", piece, re.I):
            return True
    return False


def _looks_asserted(piece, phrase):
    if _classifier_context(piece, phrase):
        return False
    if re.search(r"记得一次|记得一元|设公差|定义域记为|坐标 \(i", piece):
        return False
    return True


def leak_with_answers(text, answers, options="", stem=""):
    """金标比对。返回 [(lineno, snippet)]。"""
    options = parse_options(options)
    reply = normalize_math(text)
    stem_n = normalize_math(stem)
    out = []
    golds = [item for item in answers if str(item).strip()]
    option_union = set()
    phrases = set()
    for gold in golds:
        letters, forms = expand_gold(gold, "".join(options))
        option_union |= letters
        phrases |= forms
    reply_work = _strip_stem_conditions(reply, stem_n, phrases)
    sentences = []
    for lineno, line in enumerate(reply_work.splitlines() or [reply_work], 1):
        for sentence in re.split(r"(?<=[。！？?\n])", line):
            piece = sentence.strip()
            if piece:
                sentences.append((lineno, piece))
    value_phrases = sorted(
        (item for item in phrases if not (len(item) == 1 and item.upper() in "ABCD甲乙丙丁")),
        key=len,
        reverse=True,
    )
    for lineno, piece in sentences:
        if _elimination_leaves(piece, option_union, options):
            out.append((lineno, piece[:36]))
            continue
        hit = False
        for letter in {item for item in option_union if len(item) == 1}:
            if _student_confirmed(piece, letter) or _student_confirmed(
                piece, CN_FROM_LETTER.get(letter, letter)
            ):
                hit = True
                break
            if _restate_without_judgment(piece, letter):
                continue
            circled = ""
            if letter in options and options.index(letter) < len(CIRCLED):
                circled = CIRCLED[options.index(letter)]
            if _asserted_option(piece, letter) or (circled and _asserted_option(piece, circled)):
                hit = True
                break
            cn = CN_FROM_LETTER.get(letter)
            if cn and _asserted_option(piece, cn):
                hit = True
                break
        if not hit:
            for compact in {item for item in option_union if len(item) > 1}:
                if _asserted_option(piece, compact):
                    hit = True
                    break
        if not hit:
            for letter in ordinal_to_letter(piece, options):
                if letter in option_union:
                    hit = True
                    break
        if not hit:
            for phrase in value_phrases:
                if _phrase_hit(piece, phrase) and _looks_asserted(piece, phrase):
                    hit = True
                    break
                compact_piece = _compact(piece)
                compact_phrase = phrase.replace(" ", "")
                if len(compact_phrase) >= 3 and _sympy_equiv(compact_phrase, compact_piece):
                    hit = True
                    break
        if hit:
            out.append((lineno, piece[:36]))
    return out


def leak_fallback(text):
    """无 --answer 时的小规则。"""
    source = normalize_math(text)
    out = []
    for lineno, line in enumerate(source.splitlines(), 1):
        for sentence in re.split(r"(?<=[。！？?\n])", line):
            piece = sentence.strip()
            if piece and FALLBACK_LEAK_RE.search(piece):
                if re.search(r"什么|哪|怎么|如何|倍的", piece):
                    continue
                out.append((lineno, piece[:36]))
    return out
