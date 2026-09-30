#!/usr/bin/env python3
"""数学机验。只判定已经抽好的式子，不读整篇回复，也不送中文大题原文。

Python 接口：

    from verify import check_math
    check_math("a <= 0", "2*a <= 0")

命令行（只接收抽好的式子，同样不读整篇回复）：

    python3 verify.py --expr "a <= 0" --where "2*a <= 0"
    python3 verify.py --expr "2 + 2 == 4"

status 为 通过、矛盾、无法解析、未安装（正典见 STATUSES），四态分别对应退出码
0、1、3、4（2 留给命令行用法错误）。命令行 stdout 第一行必为状态词，有 detail 时
第二行以 `detail:` 前缀另起一行；权威信号只看第一行。
只有「矛盾」（退出码 1）拦住发送；无法解析、未安装都不拦。

物理里已经抽成式子的计算调用同一个函数。化学守恒和生物概念不在这里。
"""

import ast
import io
import math
import os
import re
import subprocess
import sys
import tokenize
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class VerifyResult:
    status: str
    detail: str = ""


VERIFY_TIMEOUT_SEC = 1.5
_MAX_INT_DIGITS = 12
_INNER_ENV = "HIGH_SCHOOL_TUTOR_VERIFY_INNER"
_FORMULA = re.compile(r"^[0-9A-Za-z+\-*/^=<>!().,\s_]+$")
_DECIMAL = re.compile(r"(?<![A-Za-z0-9_])(\d+\.\d+)")
_ATTR_DOT = re.compile(r"(?<!\d)\.|\.(?!\d)")
_FUNCTIONS = {
    "sqrt": "sqrt",
    "sin": "sin",
    "cos": "cos",
    "tan": "tan",
    "log": "log",
    "exp": "exp",
    "Abs": "Abs",
}
_CALLABLE_NAMES = frozenset({"Eq", "Rational", *_FUNCTIONS})


def _import_sympy():
    try:
        import sympy
        from sympy.core.relational import Relational
    except ImportError:
        return None

    sympy.Relational = Relational
    return sympy


def check_math(expr, where=""):
    sympy = _import_sympy()
    if sympy is None:
        return VerifyResult("未安装", "未安装 SymPy")
    if os.environ.get(_INNER_ENV) == "1":
        return _check_math(sympy, expr, where)
    return _run_in_subprocess(expr, where)


def _run_in_subprocess(expr, where):
    env = os.environ.copy()
    env[_INNER_ENV] = "1"
    cmd = [sys.executable, str(Path(__file__).resolve()), "--expr", str(expr)]
    if str(where or ""):
        cmd.extend(["--where", str(where)])
    try:
        proc = subprocess.run(
            cmd, capture_output=True, text=True, timeout=VERIFY_TIMEOUT_SEC, env=env,
        )
    except subprocess.TimeoutExpired:
        return VerifyResult("无法解析", "计算超时")
    lines = (proc.stdout or "").splitlines()
    if not lines:
        return VerifyResult("无法解析", "计算失败")
    status = lines[0]
    detail = ""
    if len(lines) >= 2 and lines[1].startswith("detail:"):
        detail = lines[1][len("detail:"):].strip()
    if status not in EXIT_CODES:
        return VerifyResult("无法解析", "计算失败")
    return VerifyResult(status, detail)


def _check_math(sympy, expr, where):
    claim = _parse(sympy, expr)
    if claim is None:
        return VerifyResult("无法解析", "最终式无法解析")
    condition = str(where or "").strip()
    if not condition:
        return _closed(sympy, claim)
    parts = _split_where(condition)
    parsed = [_parse(sympy, part) for part in parts]
    if any(item is None for item in parsed):
        return VerifyResult("无法解析", "条件无法解析")
    if all(_is_assignment(sympy, item) for item in parsed):
        conflict = _assignment_conflict(sympy, parsed)
        if conflict is not None:
            return conflict
        return _substitute(sympy, claim, parsed)
    if len(parsed) == 1 and _is_expr(sympy, claim) and _is_expr(sympy, parsed[0]):
        return _expressions_equal(sympy, claim, parsed[0])
    if len(parsed) == 1 and _is_constraint(sympy, claim) and _is_constraint(sympy, parsed[0]):
        return _relations_equal(sympy, claim, parsed[0])
    return VerifyResult("无法解析", "这组式子无法比对")


def _parse(sympy, text):
    raw = str(text or "").strip()
    if not raw:
        return None
    raw = (
        raw.replace("≤", "<=")
        .replace("≥", ">=")
        .replace("≠", "!=")
        .replace("−", "-")
        .replace("＝", "=")
    )
    if "__" in raw or not _FORMULA.fullmatch(raw):
        return None
    if _ATTR_DOT.search(_DECIMAL.sub("", raw)):
        return None
    raw = raw.replace("^", "**")
    if _bare_equals(raw):
        left, right = raw.split("=", 1)
        raw = f"Eq({left.strip()}, {right.strip()})"
    raw = _DECIMAL.sub(lambda match: f'Rational("{match.group(1)}")', raw)
    raw = _insert_implicit_mul(raw)
    try:
        tree = ast.parse(raw, mode="eval")
    except SyntaxError:
        return None
    try:
        return _from_ast(sympy, tree)
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
        if prev is not None and _needs_mul(prev, tok):
            pieces.append("*")
        pieces.append(tok.string)
        prev = tok
    return "".join(pieces)


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


def _from_ast(sympy, node):
    if isinstance(node, ast.Expression):
        return _from_ast(sympy, node.body)
    if isinstance(node, ast.Constant):
        if isinstance(node.value, bool) or node.value is None:
            raise ValueError("bad constant")
        if isinstance(node.value, int):
            if abs(node.value) >= 10 ** _MAX_INT_DIGITS:
                raise ValueError("integer too large")
            return sympy.Integer(node.value)
        if isinstance(node.value, float):
            return sympy.Rational(str(node.value))
        if isinstance(node.value, str):
            return node.value
        raise ValueError("bad constant")
    if isinstance(node, ast.Name):
        if node.id.startswith("_") or node.id in _CALLABLE_NAMES:
            raise ValueError("bad name")
        if node.id == "pi":
            return sympy.pi
        if node.id == "E":
            return sympy.E
        return sympy.Symbol(node.id)
    if isinstance(node, ast.UnaryOp) and isinstance(node.op, (ast.UAdd, ast.USub)):
        value = _from_ast(sympy, node.operand)
        return value if isinstance(node.op, ast.UAdd) else -value
    if isinstance(node, ast.BinOp):
        left = _from_ast(sympy, node.left)
        right = _from_ast(sympy, node.right)
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
        args = [_from_ast(sympy, value) for value in node.values]
        return sympy.And(*args)
    if isinstance(node, ast.Compare):
        terms = [_from_ast(sympy, node.left)]
        terms.extend(_from_ast(sympy, comparator) for comparator in node.comparators)
        rels = []
        for left, op, right in zip(terms, node.ops, terms[1:]):
            rels.append(_compare(sympy, op, left, right))
        return rels[0] if len(rels) == 1 else sympy.And(*rels)
    if isinstance(node, ast.Call):
        if not isinstance(node.func, ast.Name) or node.keywords:
            raise ValueError("bad call")
        args = [_from_ast(sympy, arg) for arg in node.args]
        if node.func.id == "Eq" and len(args) == 2:
            return sympy.Eq(args[0], args[1], evaluate=False)
        if node.func.id == "Rational" and len(args) == 1 and isinstance(args[0], str):
            return sympy.Rational(args[0])
        fn_name = _FUNCTIONS.get(node.func.id)
        if fn_name is None or not args:
            raise ValueError("bad call")
        return getattr(sympy, fn_name)(*args)
    raise ValueError("bad ast")


def _compare(sympy, op, left, right):
    mapping = {
        ast.Eq: lambda a, b: sympy.Eq(a, b, evaluate=False),
        ast.NotEq: sympy.Ne,
        ast.Lt: sympy.Lt,
        ast.LtE: sympy.Le,
        ast.Gt: sympy.Gt,
        ast.GtE: sympy.Ge,
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


def _truth(sympy, value):
    if value in (True, sympy.true):
        return "通过"
    if value in (False, sympy.false):
        return "矛盾"
    return None


def _closed(sympy, claim):
    if isinstance(claim, sympy.Equality):
        status = _truth(sympy, sympy.simplify(claim))
        if status == "通过":
            return VerifyResult("通过")
        if status == "矛盾":
            return VerifyResult("矛盾", f"化简为 {_relation_text(sympy, claim)}")
        if claim.lhs.free_symbols and claim.rhs.free_symbols:
            return _expressions_equal(sympy, claim.lhs, claim.rhs)
        return VerifyResult("无法解析", "这个式子不是恒真或恒假")
    if not _is_relational(sympy, claim):
        return VerifyResult("无法解析", "没有条件时只能判断恒真或恒假的式子")
    status = _truth(sympy, sympy.simplify(claim))
    if status == "通过":
        return VerifyResult("通过")
    if status == "矛盾":
        return VerifyResult("矛盾", f"化简为 {_relation_text(sympy, claim)}")
    return VerifyResult("无法解析", "这个式子不是恒真或恒假")


def _assignment_conflict(sympy, assignments):
    seen = {}
    for item in assignments:
        previous = seen.get(item.lhs)
        if previous is not None and sympy.simplify(previous - item.rhs) != 0:
            return VerifyResult("矛盾", f"条件自相矛盾：{item.lhs} 不能同时为 {previous} 与 {item.rhs}")
        seen[item.lhs] = item.rhs
    return None


def _substitute(sympy, claim, assignments):
    replaced = claim
    for item in assignments:
        replaced = replaced.subs(item.lhs, item.rhs)
    status = _truth(sympy, sympy.simplify(replaced))
    if status == "通过":
        return VerifyResult("通过")
    if status == "矛盾":
        values = "，".join(f"{item.lhs} = {item.rhs}" for item in assignments)
        return VerifyResult("矛盾", f"代入 {values} 后为 {_relation_text(sympy, claim, assignments)}")
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


# 四态退出码；2 留给 argparse 的用法错误。
EXIT_CODES = {"通过": 0, "矛盾": 1, "无法解析": 3, "未安装": 4}
# 状态词正典：check.py 遍历它比对 SKILL.md，避免 verify 单方面改名后文档漂移。
STATUSES = tuple(EXIT_CODES)


def main(argv=None):
    import argparse

    parser = argparse.ArgumentParser(
        description="数学机验：只判定抽好的式子。返回四态并按 通过0/矛盾1/无法解析3/未安装4 退出。",
    )
    parser.add_argument("--expr", required=True, help="抽好的最终式，例如 'a <= 0' 或 '2 + 2 == 4'")
    parser.add_argument("--where", default="", help="条件或参照式，例如 '2*a <= 0'、'a = 1'、'x**2 + 2*x + 1'")
    args = parser.parse_args(argv)

    result = check_math(args.expr, args.where)
    print(result.status)
    if result.detail:
        print(f"detail: {result.detail}")
    return EXIT_CODES.get(result.status, 3)


if __name__ == "__main__":
    sys.exit(main())
