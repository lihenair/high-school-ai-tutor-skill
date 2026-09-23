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

import re
from dataclasses import dataclass


@dataclass(frozen=True)
class VerifyResult:
    status: str
    detail: str = ""


def _import_sympy():
    try:
        import sympy
        from sympy.parsing.sympy_parser import (
            convert_xor,
            implicit_multiplication_application,
            parse_expr,
            standard_transformations,
        )
    except ImportError:
        return None
    from sympy.core.relational import Relational

    sympy.parse_expr = parse_expr
    sympy.Relational = Relational
    sympy._verify_transformations = standard_transformations + (
        implicit_multiplication_application,
        convert_xor,
    )
    return sympy


def check_math(expr, where=""):
    sympy = _import_sympy()
    if sympy is None:
        return VerifyResult("未安装", "未安装 SymPy")
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
        return _substitute(sympy, claim, parsed)
    if len(parsed) == 1 and _is_expr(sympy, claim) and _is_expr(sympy, parsed[0]):
        return _expressions_equal(sympy, claim, parsed[0])
    if len(parsed) == 1 and _is_relational(sympy, claim) and _is_relational(sympy, parsed[0]):
        return _relations_equal(sympy, claim, parsed[0])
    return VerifyResult("无法解析", "这组式子无法比对")


_FORMULA = re.compile(r"^[0-9A-Za-z+\-*/^=<>!().,\[\]{}\s_]+$")


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
    if not _FORMULA.fullmatch(raw):
        return None
    if _bare_equals(raw):
        left, right = raw.split("=", 1)
        raw = f"Eq({left.strip()}, {right.strip()})"
    try:
        return sympy.parse_expr(
            raw,
            transformations=sympy._verify_transformations,
            evaluate=False,
        )
    except Exception:
        return None


def _bare_equals(text):
    if any(token in text for token in ("==", "<=", ">=", "!=", "Eq(")):
        return False
    return text.count("=") == 1


def _split_where(text):
    for sep in ("；", ";", "且"):
        text = text.replace(sep, "\n")
    return [part.strip() for part in text.split("\n") if part.strip()]


def _is_assignment(sympy, expr):
    return isinstance(expr, sympy.Equality) and expr.lhs.is_Symbol and expr.lhs not in expr.rhs.free_symbols


def _is_relational(sympy, expr):
    return isinstance(expr, sympy.Relational)


def _is_expr(sympy, expr):
    return isinstance(expr, sympy.Expr) and not _is_relational(sympy, expr)


def _truth(sympy, value):
    if value in (True, sympy.true):
        return "通过"
    if value in (False, sympy.false):
        return "矛盾"
    return None


def _closed(sympy, claim):
    if not _is_relational(sympy, claim):
        return VerifyResult("无法解析", "没有条件时只能判断恒真或恒假的式子")
    status = _truth(sympy, sympy.simplify(claim))
    if status == "通过":
        return VerifyResult("通过")
    if status == "矛盾":
        return VerifyResult("矛盾", f"化简为 {_relation_text(sympy, claim)}")
    return VerifyResult("无法解析", "这个式子不是恒真或恒假")


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


def _relations_equal(sympy, claim, reference):
    symbols = list(claim.free_symbols | reference.free_symbols)
    if len(symbols) != 1:
        return VerifyResult("无法解析", "解集比对只处理一个未知数")
    symbol = symbols[0]
    domain = sympy.S.Reals
    try:
        got = sympy.solveset(claim, symbol, domain)
        expected = sympy.solveset(reference, symbol, domain)
    except Exception:
        return VerifyResult("无法解析", "解集无法求出")
    if isinstance(got, sympy.ConditionSet) or isinstance(expected, sympy.ConditionSet):
        return VerifyResult("无法解析", "解集无法比较")
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
    import sys

    sys.exit(main())
