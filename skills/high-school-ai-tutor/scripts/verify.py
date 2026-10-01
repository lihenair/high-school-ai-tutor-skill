#!/usr/bin/env python3
"""数学机验。只判定已经抽好的式子，不读整篇回复，也不送中文大题原文。

Python 接口：

    from verify import check_math
    check_math("a <= 0", "2*a <= 0")

命令行（只接收抽好的式子，同样不读整篇回复）：

    python3 verify.py --expr "a <= 0" --where "2*a <= 0"
    python3 verify.py --expr "2 + 2 == 4"

status 为 通过、矛盾、超时、无法解析、未安装（正典见 STATUSES），五态分别对应退出码
0、1、1、3、4（2 留给命令行用法错误）。命令行 stdout 第一行必为状态词，有 detail 时
第二行以 `detail:` 前缀另起一行；权威信号只看第一行。
「矛盾」和「超时」（退出码 1）拦住发送；无法解析、未安装都不拦。

物理里已经抽成式子的计算调用同一个函数。化学守恒和生物概念不在这里。
"""

import ast
import atexit
import io
import json
import math
import re
import subprocess
import sys
import threading
import tokenize
import unicodedata
from dataclasses import dataclass
from decimal import Decimal
from pathlib import Path


@dataclass(frozen=True)
class VerifyResult:
    status: str
    detail: str = ""


VERIFY_TIMEOUT_SEC = 1.5
VERIFY_RETRY_TIMEOUT_SEC = 12.0
_MAX_INT_DIGITS = 16
_FORMULA = re.compile(r"^[0-9A-Za-z+\-*/^=<>!().,\s_]+$")
_NUMBER_LIT = re.compile(
    r"(?<![A-Za-z0-9_])(\d+\.\d+(?:[eE][+-]?\d+)?|\d+[eE][+-]?\d+)"
)
_ATTR_DOT = re.compile(r"(?<!\d)\.|\.(?!\d)")
_ASSIGN_LHS = re.compile(r"^([A-Za-z][A-Za-z0-9_]*)\s*=")
_FUNCTIONS = {
    "sqrt": "sqrt",
    "sin": "sin",
    "cos": "cos",
    "tan": "tan",
    "log": "log",
    "ln": "log",
    "lg": "log",
    "exp": "exp",
    "abs": "Abs",
    "Abs": "Abs",
    "max": "Max",
    "min": "Min",
    "expand": "expand",
}
_CALLABLE_NAMES = frozenset({"Eq", "Rational", *_FUNCTIONS})
_KEEP_IDENTIFIERS = _CALLABLE_NAMES | {"pi", "e", "oo", "zoo", "nan", "inf"}
_LETTER_JUXTAPOSE = re.compile(r"^[a-z]{2,3}$")
_SUP_DIGITS = str.maketrans("⁰¹²³⁴⁵⁶⁷⁸⁹", "0123456789")
_VULGAR_FRACTIONS = {
    "½": "(1/2)", "⅓": "(1/3)", "⅔": "(2/3)", "¼": "(1/4)", "¾": "(3/4)",
    "⅕": "(1/5)", "⅖": "(2/5)", "⅗": "(3/5)", "⅘": "(4/5)", "⅙": "(1/6)",
    "⅚": "(5/6)", "⅛": "(1/8)", "⅜": "(3/8)", "⅝": "(5/8)", "⅞": "(7/8)",
}

_worker_lock = threading.Lock()
_worker_proc = None


def _import_sympy():
    try:
        import sympy
        from sympy.core.relational import Relational
    except ImportError:
        return None

    sympy.Relational = Relational
    return sympy


def check_math(expr, where=""):
    if _import_sympy() is None:
        return VerifyResult("未安装", "未安装 SymPy")
    result = _ask_worker(expr, where, VERIFY_TIMEOUT_SEC)
    if result.status == "超时":
        result = _ask_worker(expr, where, VERIFY_RETRY_TIMEOUT_SEC)
    return result


def _ask_worker(expr, where, seconds):
    with _worker_lock:
        try:
            proc = _ensure_worker()
        except Exception:
            return VerifyResult("无法解析", "计算失败")
        try:
            payload = json.dumps({"expr": expr, "where": where}, ensure_ascii=False)
            proc.stdin.write(payload + "\n")
            proc.stdin.flush()
        except Exception:
            _shutdown_worker()
            return VerifyResult("无法解析", "计算失败")
        line = _readline_timeout(proc, seconds)
        if line is None:
            _shutdown_worker()
            return VerifyResult("超时", "计算超时")
        try:
            data = json.loads(line)
        except json.JSONDecodeError:
            _shutdown_worker()
            return VerifyResult("无法解析", "计算失败")
        status = data.get("status")
        if status not in EXIT_CODES:
            return VerifyResult("无法解析", "计算失败")
        return VerifyResult(status, data.get("detail") or "")


def _ensure_worker():
    global _worker_proc
    if _worker_proc is not None and _worker_proc.poll() is None:
        return _worker_proc
    _shutdown_worker()
    _worker_proc = subprocess.Popen(
        [sys.executable, str(Path(__file__).resolve()), "--worker"],
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.DEVNULL,
        text=True,
        bufsize=1,
    )
    ready = _worker_proc.stdout.readline()
    if ready.strip() != "ready":
        _shutdown_worker()
        raise RuntimeError("verify worker failed to start")
    return _worker_proc


def _readline_timeout(proc, seconds):
    bucket = []

    def reader():
        try:
            bucket.append(proc.stdout.readline())
        except Exception:
            bucket.append("")

    thread = threading.Thread(target=reader)
    thread.daemon = True
    thread.start()
    thread.join(seconds)
    if thread.is_alive():
        return None
    if not bucket:
        return ""
    return bucket[0]


def _shutdown_worker():
    global _worker_proc
    proc = _worker_proc
    _worker_proc = None
    if proc is None:
        return
    try:
        if proc.poll() is None:
            proc.kill()
        proc.stdin.close()
        proc.stdout.close()
        proc.wait(timeout=1)
    except Exception:
        pass


atexit.register(_shutdown_worker)


def _run_worker():
    sympy = _import_sympy()
    print("ready", flush=True)
    for line in sys.stdin:
        line = line.strip()
        if not line:
            continue
        try:
            job = json.loads(line)
        except json.JSONDecodeError:
            print(json.dumps({"status": "无法解析", "detail": "计算失败"}, ensure_ascii=False), flush=True)
            continue
        if job.get("stop"):
            break
        if sympy is None:
            result = VerifyResult("未安装", "未安装 SymPy")
        else:
            try:
                result = _check_math(sympy, job.get("expr", ""), job.get("where", ""))
            except Exception:
                result = VerifyResult("无法解析", "计算失败")
        print(json.dumps({"status": result.status, "detail": result.detail}, ensure_ascii=False), flush=True)
    return 0


def _bound_names(where):
    names = set()
    for part in _split_where(where or ""):
        raw = part.replace("＝", "=").replace("≤", "<=").replace("≥", ">=")
        match = _ASSIGN_LHS.match(raw)
        if match:
            names.add(match.group(1))
    return names


def _check_math(sympy, expr, where):
    bound = _bound_names(where)
    ulp = _half_unit_limit(f"{expr}\n{where or ''}")
    claim = _parse(sympy, expr, bound)
    if claim is None:
        return VerifyResult("无法解析", "最终式无法解析")
    condition = str(where or "").strip()
    if not condition:
        if _has_undefined(sympy, claim):
            return VerifyResult("无法解析", "式子含未定义值")
        return _closed(sympy, claim, ulp)
    parts = _split_where(condition)
    parsed = [_parse(sympy, part, bound) for part in parts]
    if any(item is None for item in parsed):
        return VerifyResult("无法解析", "条件无法解析")
    if all(_is_assignment(sympy, item) for item in parsed):
        conflict = _assignment_conflict(sympy, parsed)
        if conflict is not None:
            return conflict
        chained = _resolve_assignment_chain(sympy, parsed)
        return _substitute(sympy, claim, chained, ulp)
    if len(parsed) == 1 and _is_expr(sympy, claim) and _is_expr(sympy, parsed[0]):
        return _expressions_equal(sympy, claim, parsed[0])
    if len(parsed) == 1 and _is_constraint(sympy, claim) and _is_constraint(sympy, parsed[0]):
        where_eq = isinstance(parsed[0], sympy.Equality) and not _is_assignment(sympy, parsed[0])
        if where_eq and isinstance(claim, sympy.Equality):
            return VerifyResult("无法解析", "条件不是赋值")
        return _relations_equal(sympy, claim, parsed[0])
    return VerifyResult("无法解析", "这组式子无法比对")


def _parse(sympy, text, bound=()):
    raw = str(text or "").strip()
    if not raw:
        return None
    raw = re.sub(
        r"[⁰¹²³⁴⁵⁶⁷⁸⁹]+",
        lambda match: "**" + match.group(0).translate(_SUP_DIGITS),
        raw,
    )
    for glyph, repl in _VULGAR_FRACTIONS.items():
        raw = raw.replace(glyph, repl)
    raw = re.sub(r"√\s*(\d+(?:\.\d+)?)", r"sqrt(\1)", raw)
    raw = re.sub(r"√\s*\(", "sqrt(", raw)
    raw = (
        raw.replace("√", "sqrt")
        .replace("·", "*")
        .replace("×", "*")
        .replace("÷", "/")
        .replace("⋅", "*")
        .replace("²", "**2")
        .replace("³", "**3")
        .replace("¹", "**1")
    )
    raw = unicodedata.normalize("NFKC", raw)
    raw = (
        raw.replace("≤", "<=")
        .replace("≥", ">=")
        .replace("≠", "!=")
        .replace("−", "-")
        .replace("＝", "=")
    )
    if "__" in raw or not _FORMULA.fullmatch(raw):
        return None
    if _ATTR_DOT.search(_NUMBER_LIT.sub("", raw)):
        return None
    raw = raw.replace("^", "**")
    if _bare_equals(raw):
        left, right = raw.split("=", 1)
        raw = f"Eq({left.strip()}, {right.strip()})"
    raw = _NUMBER_LIT.sub(lambda match: f'Rational("{match.group(1)}")', raw)
    raw = _insert_implicit_mul(raw)
    try:
        tree = ast.parse(raw, mode="eval")
    except SyntaxError:
        return None
    try:
        return _from_ast(sympy, tree, bound)
    except (ValueError, TypeError, OverflowError, SyntaxError):
        return None


def _insert_implicit_mul(text):
    pieces = []
    prev = None
    try:
        tokens = tokenize.generate_tokens(io.StringIO(text).readline)
    except tokenize.TokenError:
        return text
    for tok in tokens:
        if tok.type in (tokenize.ENCODING, tokenize.ENDMARKER):
            continue
        if tok.type in (tokenize.NL, tokenize.NEWLINE, tokenize.COMMENT):
            continue
        if tok.type == tokenize.NAME:
            parts = _expand_identifier(tok.string)
            for index, part in enumerate(parts):
                fake = tokenize.TokenInfo(tokenize.NAME, part, tok.start, tok.end, tok.line)
                if index == 0 and prev is not None and _needs_mul(prev, tok):
                    pieces.append("*")
                elif index > 0:
                    pieces.append("*")
                pieces.append(part)
                prev = fake
            continue
        if prev is not None and _needs_mul(prev, tok):
            pieces.append("*")
        pieces.append(tok.string)
        prev = tok
    return "".join(pieces)


def _expand_identifier(name):
    if name in _KEEP_IDENTIFIERS:
        return [name]
    if _LETTER_JUXTAPOSE.fullmatch(name):
        return list(name)
    return [name]


def _needs_mul(prev, curr):
    prev_value = prev.type == tokenize.NUMBER or prev.type == tokenize.NAME or prev.string == ")"
    curr_value = curr.type == tokenize.NUMBER or curr.type == tokenize.NAME or curr.string == "("
    if not prev_value or not curr_value:
        return False
    if prev.type == tokenize.NAME and prev.string in _CALLABLE_NAMES and curr.string == "(":
        return False
    return True


def _bare_equals(text):
    if any(token in text for token in ("==", "<=", ">=", "!=", "Eq(")):
        return False
    return text.count("=") == 1


def _rational_literal(sympy, text):
    number = Decimal(str(text))
    numerator, denominator = number.as_integer_ratio()
    return sympy.Rational(numerator, denominator)


def _from_ast(sympy, node, bound=()):
    bound = set(bound or ())
    if isinstance(node, ast.Expression):
        return _from_ast(sympy, node.body, bound)
    if isinstance(node, ast.Constant):
        if isinstance(node.value, bool) or node.value is None:
            raise ValueError("bad constant")
        if isinstance(node.value, int):
            if abs(node.value) >= 10 ** _MAX_INT_DIGITS:
                raise ValueError("integer too large")
            return sympy.Integer(node.value)
        if isinstance(node.value, float):
            return _rational_literal(sympy, node.value)
        if isinstance(node.value, str):
            return node.value
        raise ValueError("bad constant")
    if isinstance(node, ast.Name):
        if node.id.startswith("_") or node.id in _CALLABLE_NAMES:
            raise ValueError("bad name")
        if node.id in bound:
            return sympy.Symbol(node.id)
        if node.id == "pi":
            return sympy.pi
        if node.id == "e":
            return sympy.E
        if node.id in ("oo", "inf"):
            return sympy.oo
        if node.id == "zoo":
            return sympy.zoo
        if node.id == "nan":
            return sympy.nan
        return sympy.Symbol(node.id)
    if isinstance(node, ast.UnaryOp) and isinstance(node.op, (ast.UAdd, ast.USub)):
        value = _from_ast(sympy, node.operand, bound)
        return value if isinstance(node.op, ast.UAdd) else -value
    if isinstance(node, ast.BinOp):
        left = _from_ast(sympy, node.left, bound)
        right = _from_ast(sympy, node.right, bound)
        if isinstance(node.op, ast.BitAnd):
            return sympy.And(left, right)
        if isinstance(node.op, ast.Pow):
            _reject_huge_pow(left, right)
        ops = {
            ast.Add: lambda a, b: a + b,
            ast.Sub: lambda a, b: a - b,
            ast.Mult: lambda a, b: a * b,
            ast.Div: lambda a, b: a / b,
            ast.Pow: lambda a, b: a ** b,
        }
        fn = ops.get(type(node.op))
        if fn is None:
            raise ValueError("bad operator")
        return fn(left, right)
    if isinstance(node, ast.BoolOp) and isinstance(node.op, ast.And):
        args = [_from_ast(sympy, value, bound) for value in node.values]
        return sympy.And(*args)
    if isinstance(node, ast.Compare):
        terms = [_from_ast(sympy, node.left, bound)]
        terms.extend(_from_ast(sympy, comparator, bound) for comparator in node.comparators)
        rels = []
        for left, op, right in zip(terms, node.ops, terms[1:]):
            rels.append(_compare(sympy, op, left, right))
        return rels[0] if len(rels) == 1 else sympy.And(*rels)
    if isinstance(node, ast.Call):
        if not isinstance(node.func, ast.Name) or node.keywords:
            raise ValueError("bad call")
        args = [_from_ast(sympy, arg, bound) for arg in node.args]
        if node.func.id == "Eq" and len(args) == 2:
            return sympy.Eq(args[0], args[1], evaluate=False)
        if node.func.id == "Rational" and len(args) == 1 and isinstance(args[0], str):
            return _rational_literal(sympy, args[0])
        if node.func.id == "lg" and len(args) == 1:
            return sympy.log(args[0], 10)
        fn_name = _FUNCTIONS.get(node.func.id)
        if fn_name is None or not args:
            raise ValueError("bad call")
        return getattr(sympy, fn_name)(*args)
    raise ValueError("bad ast")


def _compare(sympy, op, left, right):
    mapping = {
        ast.Eq: lambda a, b: sympy.Eq(a, b, evaluate=False),
        ast.NotEq: lambda a, b: sympy.Ne(a, b, evaluate=False),
        ast.Lt: lambda a, b: sympy.Lt(a, b, evaluate=False),
        ast.LtE: lambda a, b: sympy.Le(a, b, evaluate=False),
        ast.Gt: lambda a, b: sympy.Gt(a, b, evaluate=False),
        ast.GtE: lambda a, b: sympy.Ge(a, b, evaluate=False),
    }
    fn = mapping.get(type(op))
    if fn is None:
        raise ValueError("bad compare")
    return fn(left, right)


def _reject_huge_pow(base, exp):
    if not getattr(exp, "is_Integer", False):
        return
    exponent = int(exp)
    if exponent > 256:
        raise ValueError("exponent too large")
    if getattr(base, "is_Integer", False):
        magnitude = abs(int(base))
        if magnitude > 1 and exponent * math.log10(magnitude) > _MAX_INT_DIGITS:
            raise ValueError("power too large")


def _split_where(text):
    for sep in ("；", ";", "且"):
        text = text.replace(sep, "\n")
    return [part.strip() for part in text.split("\n") if part.strip()]


def _is_assignment(sympy, expr):
    return isinstance(expr, sympy.Equality) and expr.lhs.is_Symbol and expr.lhs not in expr.rhs.free_symbols


def _is_relational(sympy, expr):
    return isinstance(expr, sympy.Relational)


def _is_constraint(sympy, expr):
    if _is_relational(sympy, expr):
        return True
    if isinstance(expr, sympy.And):
        return all(_is_constraint(sympy, arg) for arg in expr.args)
    return False


def _is_expr(sympy, expr):
    return isinstance(expr, sympy.Expr) and not _is_relational(sympy, expr) and not isinstance(expr, sympy.And)


def _decimal_literals(text):
    return [match.group(1) for match in _NUMBER_LIT.finditer(str(text or "")) if "." in match.group(1)]


def _literal_ulp(text):
    body = str(text).strip().lower()
    exp = 0
    if "e" in body:
        mant, exp_s = body.split("e", 1)
        exp = int(exp_s)
    else:
        mant = body
    if "." in mant:
        frac = mant.split(".", 1)[1]
        return Decimal(10) ** (exp - len(frac))
    return Decimal(10) ** exp


def _half_unit_limit(text):
    ulps = [_literal_ulp(literal) for literal in _decimal_literals(text)]
    if not ulps:
        return None
    return min(ulps) / 2


def _truth(sympy, value):
    if value in (True, sympy.true):
        return "通过"
    if value in (False, sympy.false):
        return "矛盾"
    return None


def _numeric_pass(sympy, claim, ulp=None):
    if ulp is None or not _is_relational(sympy, claim) or claim.free_symbols:
        return None
    try:
        limit = sympy.Rational(*Decimal(str(ulp)).as_integer_ratio())
        if isinstance(claim, sympy.Equality):
            delta = sympy.simplify(abs(claim.lhs - claim.rhs))
            if getattr(delta, "is_number", False) is False:
                return None
            if delta.is_rational or getattr(delta, "is_Rational", False):
                passed = delta < limit
            else:
                passed = sympy.N(delta, 50) < sympy.N(limit, 50)
            if passed:
                return VerifyResult("通过", "数值近似")
            return None
        exact = _truth(sympy, sympy.simplify(claim))
        if exact == "通过":
            return VerifyResult("通过")
        delta = sympy.N(abs(claim.lhs - claim.rhs), 50)
        if delta < sympy.N(limit, 50):
            return VerifyResult("通过", "数值近似")
    except Exception:
        return None
    return None


def _closed(sympy, claim, ulp=None):
    if _has_undefined(sympy, claim):
        return VerifyResult("无法解析", "式子含未定义值")
    if isinstance(claim, sympy.Equality):
        status = _truth(sympy, sympy.simplify(claim))
        if status == "通过":
            return VerifyResult("通过")
        if status == "矛盾":
            approx = _numeric_pass(sympy, claim, ulp)
            if approx is not None:
                return approx
            return VerifyResult("矛盾", f"化简为 {_relation_text(sympy, claim)}")
        if claim.lhs.free_symbols and claim.rhs.free_symbols:
            return _expressions_equal(sympy, claim.lhs, claim.rhs)
        approx = _numeric_pass(sympy, claim, ulp)
        if approx is not None:
            return approx
        return VerifyResult("无法解析", "这个式子不是恒真或恒假")
    if not _is_relational(sympy, claim):
        return VerifyResult("无法解析", "没有条件时只能判断恒真或恒假的式子")
    status = _truth(sympy, sympy.simplify(claim))
    if status == "通过":
        return VerifyResult("通过")
    approx = _numeric_pass(sympy, claim, ulp)
    if approx is not None:
        return approx
    if status == "矛盾":
        return VerifyResult("矛盾", f"化简为 {_relation_text(sympy, claim)}")
    return VerifyResult("无法解析", "这个式子不是恒真或恒假")


def _assignment_conflict(sympy, assignments):
    seen = {}
    for item in assignments:
        previous = seen.get(item.lhs)
        if previous is not None:
            try:
                if sympy.simplify(previous - item.rhs) != 0:
                    return VerifyResult("矛盾", f"条件自相矛盾：{item.lhs} 不能同时为 {previous} 与 {item.rhs}")
            except Exception:
                return VerifyResult("无法解析", "条件无法解析")
        seen[item.lhs] = item.rhs
    return None


def _resolve_assignment_chain(sympy, assignments):
    env = {item.lhs: item.rhs for item in assignments}
    keys = list(env)
    for _ in range(len(keys) + 1):
        changed = False
        for key in keys:
            new_rhs = env[key]
            for other, value in env.items():
                if other != key:
                    new_rhs = new_rhs.subs(other, value)
            if new_rhs != env[key]:
                env[key] = new_rhs
                changed = True
        if not changed:
            break
    return [sympy.Eq(key, env[key], evaluate=False) for key in keys]


def _has_undefined(sympy, expr):
    try:
        atoms = (sympy.zoo, sympy.nan, sympy.oo, -sympy.oo, sympy.S.ComplexInfinity)
        return bool(expr.has(*atoms))
    except Exception:
        return False


def _is_real_closed(sympy, value):
    if getattr(value, "free_symbols", set()):
        return False
    try:
        if value.is_real is False:
            return False
        numeric = complex(sympy.N(value, 30))
    except Exception:
        return False
    return abs(numeric.imag) <= 1e-12 and math.isfinite(numeric.real)


def _determined_unknown(sympy, original, replaced, assignments):
    """unknown == f(given)：未知数未赋值、where 里至少有一个符号被代入、右侧为实数。"""
    if not isinstance(replaced, sympy.Equality):
        return False
    assigned = [item.lhs for item in assignments]
    introduced = set()
    for item in assignments:
        introduced |= set(getattr(item.rhs, "free_symbols", set()))
    if not any(symbol in original.free_symbols for symbol in assigned):
        return False
    leftover = replaced.free_symbols
    if len(leftover) != 1:
        return False
    symbol = next(iter(leftover))
    if symbol in assigned or symbol in introduced:
        return False
    if replaced.lhs != symbol or replaced.rhs.free_symbols:
        return False
    if _has_undefined(sympy, replaced.rhs):
        return False
    return _is_real_closed(sympy, replaced.rhs)


def _apply_assignments(sympy, expr, assignments):
    replaced = expr
    for item in assignments:
        if isinstance(replaced, sympy.Equality):
            replaced = sympy.Eq(
                replaced.lhs.subs(item.lhs, item.rhs),
                replaced.rhs.subs(item.lhs, item.rhs),
                evaluate=False,
            )
        else:
            replaced = replaced.subs(item.lhs, item.rhs)
    return replaced


def _substitute(sympy, claim, assignments, ulp=None):
    replaced = _apply_assignments(sympy, claim, assignments)
    if _has_undefined(sympy, replaced):
        return VerifyResult("无法解析", "代入后出现未定义值")
    try:
        simplified = sympy.simplify(replaced)
    except Exception:
        return VerifyResult("无法解析", "代入后仍无法判断")
    if _has_undefined(sympy, simplified):
        return VerifyResult("无法解析", "代入后出现未定义值")
    status = _truth(sympy, simplified)
    if status == "通过":
        return VerifyResult("通过")
    if status == "矛盾":
        approx = _numeric_pass(sympy, replaced, ulp)
        if approx is not None:
            return approx
        values = "，".join(f"{item.lhs} = {item.rhs}" for item in assignments)
        return VerifyResult("矛盾", f"代入 {values} 后为 {_relation_text(sympy, claim, assignments)}")
    approx = _numeric_pass(sympy, replaced, ulp)
    if approx is not None:
        return approx
    if _determined_unknown(sympy, claim, replaced, assignments):
        return VerifyResult("通过")
    if replaced.free_symbols:
        return VerifyResult("无法解析", "代入后仍有未赋值符号")
    return VerifyResult("无法解析", "代入后仍无法判断")


def _expressions_equal(sympy, left, right):
    diff = sympy.simplify(sympy.expand(left - right))
    if diff == 0:
        return VerifyResult("通过")
    try:
        same = diff.equals(0)
    except Exception:
        return VerifyResult("无法解析", "两个式子无法判断是否相同")
    if same is True:
        return VerifyResult("通过")
    if same is False:
        return VerifyResult("矛盾", f"化简差为 {diff}")
    return VerifyResult("无法解析", "两个式子无法判断是否相同")


def _solution_set(sympy, expr, symbol, domain):
    if isinstance(expr, sympy.And):
        result = domain
        for arg in expr.args:
            piece = _solution_set(sympy, arg, symbol, domain)
            if piece is None:
                return None
            result = result.intersect(piece)
        return result
    try:
        found = sympy.solveset(expr, symbol, domain)
    except Exception:
        return None
    if isinstance(found, sympy.ConditionSet):
        return None
    return found


def _relations_equal(sympy, claim, reference):
    symbols = list(claim.free_symbols | reference.free_symbols)
    if len(symbols) != 1:
        return VerifyResult("无法解析", "解集比对只处理一个未知数")
    symbol = symbols[0]
    domain = sympy.S.Reals
    got = _solution_set(sympy, claim, symbol, domain)
    expected = _solution_set(sympy, reference, symbol, domain)
    if got is None or expected is None:
        return VerifyResult("无法解析", "解集无法求出")
    if got == expected:
        return VerifyResult("通过")
    return VerifyResult("矛盾", f"解集 {got} 与 {expected}")


def _relation_text(sympy, expr, assignments=()):
    if not _is_relational(sympy, expr):
        value = expr
        for item in assignments:
            value = value.subs(item.lhs, item.rhs)
        return str(sympy.simplify(value))
    lhs, rhs = expr.lhs, expr.rhs
    for item in assignments:
        lhs = lhs.subs(item.lhs, item.rhs)
        rhs = rhs.subs(item.lhs, item.rhs)
    return f"{sympy.simplify(lhs)} {expr.rel_op} {sympy.simplify(rhs)}"


# 五态退出码；2 留给 argparse 的用法错误。
EXIT_CODES = {"通过": 0, "矛盾": 1, "超时": 1, "无法解析": 3, "未安装": 4}
# 状态词正典：check.py 遍历它比对 SKILL.md，避免 verify 单方面改名后文档漂移。
STATUSES = tuple(EXIT_CODES)


def _glue_leading_minus(argv):
    """让 `--expr -1.6e-19` 不被 argparse 当成新开关；也可用 `--expr=`。"""
    flags = {"--expr", "--where"}
    out = []
    index = 0
    while index < len(argv):
        token = argv[index]
        if token in flags and index + 1 < len(argv):
            nxt = argv[index + 1]
            if re.match(r"^-[0-9.]", nxt):
                out.append(f"{token}={nxt}")
                index += 2
                continue
        out.append(token)
        index += 1
    return out


def main(argv=None):
    argv = list(sys.argv[1:] if argv is None else argv)
    if argv[:1] == ["--worker"]:
        return _run_worker()
    import argparse

    parser = argparse.ArgumentParser(
        description="数学机验：只判定抽好的式子。返回五态并按 通过0/矛盾1/超时1/无法解析3/未安装4 退出。",
    )
    parser.add_argument("--expr", required=True, help="抽好的最终式。负数请写 --expr=-1.6e-19 或 --expr -1.6e-19")
    parser.add_argument("--where", default="", help="条件或参照式，例如 '2*a <= 0'、'a = 1'、'x**2 + 2*x + 1'")
    args = parser.parse_args(_glue_leading_minus(argv))

    result = check_math(args.expr, args.where)
    print(result.status)
    if result.detail:
        print(f"detail: {result.detail}")
    return EXIT_CODES.get(result.status, 3)


if __name__ == "__main__":
    sys.exit(main())
