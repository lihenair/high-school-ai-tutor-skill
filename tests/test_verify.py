#!/usr/bin/env python3
"""数学机验：只判定已经抽好的式子。未安装 SymPy 时跳过真算例。"""

import contextlib
import io
import json
import subprocess
import sys
import threading
import unittest
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parent.parent
SCRIPTS = ROOT / "skills" / "high-school-ai-tutor" / "scripts"
sys.path.insert(0, str(SCRIPTS))

import verify  # noqa: E402


def sympy_ready():
    return verify._import_sympy() is not None


class VerifyTests(unittest.TestCase):
    def test_missing_sympy_reports_not_installed(self):
        with patch.object(verify, "_import_sympy", return_value=None):
            result = verify.check_math("2 + 2 == 4")
        self.assertEqual(result.status, "未安装")

    @unittest.skipUnless(sympy_ready(), "未安装 SymPy")
    def test_true_and_false_equations(self):
        self.assertEqual(verify.check_math("2 + 2 == 4").status, "通过")
        self.assertEqual(verify.check_math("2 + 2 == 5").status, "矛盾")

    @unittest.skipUnless(sympy_ready(), "未安装 SymPy")
    def test_equivalent_expressions_and_solution_sets(self):
        self.assertEqual(verify.check_math("(x + 1)**2", "x**2 + 2*x + 1").status, "通过")
        self.assertEqual(verify.check_math("(x + 1)**2", "x**2 + 1").status, "矛盾")
        self.assertEqual(verify.check_math("a <= 0", "2*a <= 0").status, "通过")
        self.assertEqual(verify.check_math("a <= 1", "a <= 0").status, "矛盾")

    @unittest.skipUnless(sympy_ready(), "未安装 SymPy")
    def test_non_assignment_where_compares_solution_sets(self):
        self.assertEqual(
            verify.check_math("(x - 2)*(x + 2) == 0", "x**2 - 4 == 0").status, "通过"
        )
        lost = verify.check_math("x - 2 == 0", "x**2 - 4 == 0")
        self.assertEqual(lost.status, "矛盾", lost)
        extra = verify.check_math("x**2 - 4 == 0", "x - 2 == 0")
        self.assertEqual(extra.status, "矛盾", extra)
        self.assertEqual(verify.check_math("2*a <= 0", "a <= 0").status, "通过")
        mismatch = verify.check_math("a < 0", "a <= 0")
        self.assertEqual(mismatch.status, "矛盾", mismatch)

    @unittest.skipUnless(sympy_ready(), "未安装 SymPy")
    def test_substitution(self):
        self.assertEqual(verify.check_math("a + 1 == 2", "a = 1").status, "通过")
        self.assertEqual(verify.check_math("a + 1 == 2", "a = 0").status, "矛盾")

    @unittest.skipUnless(sympy_ready(), "未安装 SymPy")
    def test_contradiction_includes_evidence(self):
        closed = verify.check_math("2 + 2 == 5")
        self.assertEqual(closed.status, "矛盾")
        self.assertEqual(closed.detail, "化简为 4 == 5")

        diff = verify.check_math("(x + 1)**2", "x**2 + 1")
        self.assertEqual(diff.status, "矛盾")
        self.assertEqual(diff.detail, "化简差为 2*x")

        substituted = verify.check_math("a + 1 == 2", "a = 0")
        self.assertEqual(substituted.status, "矛盾")
        self.assertEqual(substituted.detail, "代入 a = 0 后为 1 == 2")

        sets = verify.check_math("a <= 1", "a <= 0")
        self.assertEqual(sets.status, "矛盾")
        self.assertEqual(sets.detail, "解集 Interval(-oo, 1) 与 Interval(-oo, 0)")

        self.assertEqual(verify.check_math("2 + 2 == 4").detail, "")
        self.assertEqual(verify.check_math("a + 1 == 2", "a = 1").detail, "")

    @unittest.skipUnless(sympy_ready(), "未安装 SymPy")
    def test_unparsed_natural_language_and_open_expression(self):
        self.assertEqual(verify.check_math("不是式子").status, "无法解析")
        self.assertEqual(verify.check_math("a <= 0", "在 [0,3] 单调递增").status, "无法解析")
        self.assertEqual(verify.check_math("x + 1").status, "无法解析")

    @unittest.skipUnless(sympy_ready(), "未安装 SymPy")
    def test_decimal_identities_are_not_false_contradictions(self):
        self.assertEqual(verify.check_math("1.2*3 == 3.6").status, "通过")
        self.assertEqual(verify.check_math("0.1+0.2 == 0.3").status, "通过")
        self.assertEqual(verify.check_math("1.2*3 == 3.7").status, "矛盾")

    @unittest.skipUnless(sympy_ready(), "未安装 SymPy")
    def test_chained_inequality_keeps_every_bound(self):
        sympy = verify._import_sympy()
        parsed = verify._parse(sympy, "0 < a < 1")
        self.assertIsNotNone(parsed)
        self.assertNotEqual(str(parsed), "0 < a")
        self.assertEqual(verify.check_math("0 < a < 1", "0 < a").status, "矛盾")
        self.assertEqual(verify.check_math("0 < a < 1", "0 < a < 1").status, "通过")

    @unittest.skipUnless(sympy_ready(), "未安装 SymPy")
    def test_false_identity_is_contradiction(self):
        self.assertEqual(verify.check_math("(a+b)**2 == a**2+b**2").status, "矛盾")
        self.assertEqual(verify.check_math("(a+b)**2 == a**2 + 2*a*b + b**2").status, "通过")

    @unittest.skipUnless(sympy_ready(), "未安装 SymPy")
    def test_conflicting_assignments_are_contradiction(self):
        self.assertEqual(verify.check_math("a == 1", "a=1; a=2").status, "矛盾")
        self.assertEqual(verify.check_math("a == a", "a=1; a=2").status, "矛盾")
        self.assertEqual(verify.check_math("a == 1", "a=1; a=1").status, "通过")

    @unittest.skipUnless(sympy_ready(), "未安装 SymPy")
    def test_attribute_access_is_not_evaluated(self):
        self.assertEqual(verify.check_math("(1).__class__").status, "无法解析")
        self.assertEqual(verify.check_math("().__class__.__name__").status, "无法解析")

    @unittest.skipUnless(sympy_ready(), "未安装 SymPy")
    def test_huge_power_does_not_hang(self):
        import time
        start = time.monotonic()
        result = verify.check_math("9**9**9 == 0")
        elapsed = time.monotonic() - start
        self.assertLess(elapsed, 2.5)
        self.assertIn(result.status, ("无法解析", "矛盾"))

    @unittest.skipUnless(sympy_ready(), "未安装 SymPy")
    def test_whitelist_functions_and_constants(self):
        self.assertEqual(verify.check_math("sqrt(2)**2 == 2").status, "通过")
        self.assertEqual(verify.check_math("sin(pi/6) == 1/2").status, "通过")
        self.assertEqual(verify.check_math("cos(0) == 1").status, "通过")
        self.assertEqual(verify.check_math("tan(0) == 0").status, "通过")
        self.assertEqual(verify.check_math("log(e) == 1").status, "通过")
        self.assertEqual(verify.check_math("exp(0) == 1").status, "通过")
        self.assertEqual(verify.check_math("Abs(-3) == 3").status, "通过")
        self.assertEqual(verify.check_math("sqrt(2)**2 == 3").status, "矛盾")
        self.assertEqual(verify.check_math("sin(pi/6) == 1").status, "矛盾")
        self.assertEqual(verify.check_math("foo(1) == 1").status, "无法解析")

    @unittest.skipUnless(sympy_ready(), "未安装 SymPy")
    def test_implicit_multiplication_and_moderate_powers(self):
        self.assertEqual(verify.check_math("2x+3x == 5x").status, "通过")
        self.assertEqual(verify.check_math("2x+3x == 6x").status, "矛盾")
        self.assertEqual(verify.check_math("2**20 == 1048576").status, "通过")
        self.assertEqual(verify.check_math("2**20 == 1").status, "矛盾")
        self.assertEqual(verify.check_math("2ab == 2*a*b").status, "通过")
        self.assertEqual(verify.check_math("2ab == 2*a").status, "矛盾")

    @unittest.skipUnless(sympy_ready(), "未安装 SymPy")
    def test_check_math_from_worker_thread(self):
        holder = {}

        def worker():
            holder["status"] = verify.check_math("2 + 2 == 4").status

        thread = threading.Thread(target=worker)
        thread.start()
        thread.join()
        self.assertEqual(holder.get("status"), "通过")

    @unittest.skipUnless(sympy_ready(), "未安装 SymPy")
    def test_physics_E_is_not_euler_number(self):
        result = verify.check_math("E == F/q", "F=6; q=2")
        self.assertNotEqual(result.status, "矛盾", result)

    @unittest.skipUnless(sympy_ready(), "未安装 SymPy")
    def test_concurrent_contradictions_are_not_timeouts(self):
        holder = []

        def worker():
            holder.append(verify.check_math("2 + 2 == 5").status)

        threads = [threading.Thread(target=worker) for _ in range(32)]
        for thread in threads:
            thread.start()
        for thread in threads:
            thread.join()
        self.assertEqual(holder.count("矛盾"), 32, holder)
        self.assertNotIn("超时", holder)
        self.assertNotIn("无法解析", holder)

    @unittest.skipUnless(sympy_ready(), "未安装 SymPy")
    def test_scientific_notation_parses_and_checks(self):
        self.assertEqual(verify.check_math("1.6e-19*2 == 3.2e-19").status, "通过")
        self.assertEqual(verify.check_math("3.0e8 == 300000000").status, "通过")
        self.assertEqual(verify.check_math("2.5e3 == 2500").status, "通过")
        self.assertEqual(verify.check_math("2*6.02e23 == 1.204e24").status, "通过")
        self.assertEqual(verify.check_math("1.6e-19*2 == 3.2e-18").status, "矛盾")

    @unittest.skipUnless(sympy_ready(), "未安装 SymPy")
    def test_short_function_names_are_not_split_into_products(self):
        self.assertEqual(verify.check_math("abs(-3) == 3").status, "通过")
        self.assertEqual(verify.check_math("ln(e) == 1").status, "通过")
        self.assertEqual(verify.check_math("lg(100) == 2").status, "通过")
        self.assertEqual(verify.check_math("max(1, 3) == 3").status, "通过")
        self.assertEqual(verify.check_math("abs(-3) == 4").status, "矛盾")

    @unittest.skipUnless(sympy_ready(), "未安装 SymPy")
    def test_heavy_expand_identity_does_not_timeout(self):
        result = verify.check_math("(x+1)**200 == expand((x+1)**200)")
        self.assertEqual(result.status, "通过", result)

    @unittest.skipUnless(sympy_ready(), "未安装 SymPy")
    def test_assigned_e_is_elementary_charge_not_euler(self):
        result = verify.check_math("q == n*e", "n=2; e=1.6")
        self.assertEqual(result.status, "通过", result)
        self.assertEqual(verify.check_math("q == n*e", "n=2; e=1.6; q=3").status, "矛盾")

    @unittest.skipUnless(sympy_ready(), "未安装 SymPy")
    def test_field_strength_E_substitutes_as_variable(self):
        self.assertEqual(verify.check_math("E == F/q", "F=6; q=2").status, "通过")
        self.assertEqual(verify.check_math("E == F/q", "F=6; q=2; E=4").status, "矛盾")

    @unittest.skipUnless(sympy_ready(), "未安装 SymPy")
    def test_numeric_approximations_are_not_contradictions(self):
        third = verify.check_math("1/3 == 0.3333333333333333")
        self.assertEqual(third.status, "通过", third)
        pi_approx = verify.check_math("pi == 3.14")
        self.assertEqual(pi_approx.status, "通过", pi_approx)
        e_approx = verify.check_math("e == 2.718")
        self.assertEqual(e_approx.status, "通过", e_approx)
        self.assertEqual(third.detail, "数值近似")
        self.assertEqual(pi_approx.detail, "数值近似")
        self.assertEqual(e_approx.detail, "数值近似")
        self.assertEqual(verify.check_math("pi == 3").status, "矛盾")
        self.assertEqual(verify.check_math("1.2*3 == 3.7").status, "矛盾")
        self.assertEqual(verify.check_math("2 + 2 == 5").status, "矛盾")

    @unittest.skipUnless(sympy_ready(), "未安装 SymPy")
    def test_leftover_symbols_after_where_are_unparsed_unless_determined(self):
        cases = [
            ("x**2 == -1", "y = 2"),
            ("0 == 1 + y**2", "x = 1"),
            ("sqrt(y) == -1", "x = 0"),
            ("2*y == 4", "x = 1"),
            ("x == 2*y", "x = 3"),
            ("F == m*a", "m = 2"),
        ]
        for expr, where in cases:
            result = verify.check_math(expr, where)
            self.assertEqual(result.status, "无法解析", (expr, where, result))
        determined = verify.check_math("E == F/q", "F=6; q=2")
        self.assertEqual(determined.status, "通过", determined)
        identity = verify.check_math("x+1 == x", "y = 1")
        self.assertEqual(identity.status, "矛盾", identity)

    @unittest.skipUnless(sympy_ready(), "未安装 SymPy")
    def test_exact_rationals_do_not_use_relative_tolerance(self):
        cases = [
            "2**10 == 1025",
            "3003 == 3004",
            "1000 == 999",
            "100000 == 100099",
            "2 == 2.001",
            "1.6e-19 == 1.601e-19",
            "1000 == 1001",
        ]
        for expr in cases:
            result = verify.check_math(expr)
            self.assertEqual(result.status, "矛盾", (expr, result))
        assigned = verify.check_math("x == 1000", "x = 1001")
        self.assertEqual(assigned.status, "矛盾", assigned)
        self.assertEqual(assigned.detail.find("数值近似"), -1)

    @unittest.skipUnless(sympy_ready(), "未安装 SymPy")
    def test_chained_where_and_undefined(self):
        self.assertEqual(verify.check_math("x == 3", "x=y").status, "无法解析")
        self.assertEqual(verify.check_math("x == 3", "y=2;x=y+1").status, "通过")
        self.assertEqual(verify.check_math("x == 1/y", "y=0").status, "无法解析")
        self.assertEqual(verify.check_math("E == F/q", "q=0").status, "无法解析")
        self.assertEqual(verify.check_math("E == F/q", "F=6; q=0").status, "无法解析")
        self.assertEqual(verify.check_math("2 × 3 == 6").status, "通过")
        self.assertEqual(verify.check_math("8 ÷ 2 == 4").status, "通过")
        self.assertEqual(verify.check_math("3² == 9").status, "通过")
        self.assertEqual(verify.check_math("2³ == 8").status, "通过")
        self.assertEqual(verify.check_math("1/8 == 0.13").status, "矛盾")

    @unittest.skipUnless(sympy_ready(), "未安装 SymPy")
    def test_concurrent_contradictions_stay_safe_under_64_workers(self):
        holder = []

        def worker():
            holder.append(verify.check_math("2 + 2 == 5").status)

        threads = [threading.Thread(target=worker) for _ in range(64)]
        for thread in threads:
            thread.start()
        for thread in threads:
            thread.join()
        self.assertEqual(holder.count("矛盾"), 64, holder)
        self.assertNotIn("超时", holder)
        self.assertNotIn("无法解析", holder)


class CliTests(unittest.TestCase):
    """命令行入口：五态退出码 通过0/矛盾1/超时1/无法解析3/未安装4，用法错误交给 argparse 的 2。"""

    def _run_main(self, argv):
        out = io.StringIO()
        with contextlib.redirect_stdout(out):
            code = verify.main(argv)
        return code, out.getvalue()

    def test_exit_code_table(self):
        self.assertEqual(verify.EXIT_CODES,
                         {"通过": 0, "矛盾": 1, "超时": 1, "无法解析": 3, "未安装": 4})

    def test_statuses_are_the_exit_code_keys(self):
        # 单一事实源：STATUSES 由退出码表派生，check.py 遍历它比对 SKILL.md。
        self.assertEqual(verify.STATUSES, tuple(verify.EXIT_CODES))
        self.assertEqual(verify.STATUSES, ("通过", "矛盾", "超时", "无法解析", "未安装"))

    def test_missing_sympy_returns_four(self):
        with patch.object(verify, "_import_sympy", return_value=None):
            code, stdout = self._run_main(["--expr", "2 + 2 == 4"])
        self.assertEqual(code, 4)
        self.assertEqual(stdout.splitlines()[0], "未安装")

    def test_usage_error_is_two(self):
        with self.assertRaises(SystemExit) as ctx:
            with contextlib.redirect_stderr(io.StringIO()):
                verify.main([])
        self.assertEqual(ctx.exception.code, 2)

    @unittest.skipUnless(sympy_ready(), "未安装 SymPy")
    def test_pass_and_contradiction_exit_codes(self):
        code, stdout = self._run_main(["--expr", "2 + 2 == 4"])
        self.assertEqual(code, 0)
        self.assertEqual(stdout.splitlines()[0], "通过")

        code, stdout = self._run_main(["--expr", "(x + 1)**2", "--where", "x**2 + 2*x + 1"])
        self.assertEqual(code, 0)

        code, stdout = self._run_main(["--expr", "(x + 1)**2", "--where", "x**2 + 1"])
        self.assertEqual(code, 1)
        lines = stdout.splitlines()
        self.assertEqual(lines[0], "矛盾")
        self.assertEqual(lines[1], "detail: 化简差为 2*x")

    @unittest.skipUnless(sympy_ready(), "未安装 SymPy")
    def test_unparsable_exit_code_is_three(self):
        code, stdout = self._run_main(["--expr", "不是式子"])
        self.assertEqual(code, 3)
        self.assertEqual(stdout.splitlines()[0], "无法解析")

    @unittest.skipUnless(sympy_ready(), "未安装 SymPy")
    def test_end_to_end_subprocess(self):
        proc = subprocess.run(
            [sys.executable, str(SCRIPTS / "verify.py"), "--expr", "2 + 2 == 5"],
            capture_output=True, text=True,
        )
        self.assertEqual(proc.returncode, 1)
        self.assertEqual(proc.stdout.splitlines()[0], "矛盾")

    @unittest.skipUnless(sympy_ready(), "未安装 SymPy")
    def test_cli_leading_minus_expr(self):
        code, stdout = self._run_main(["--expr", "-1.6e-19 == -1.6e-19"])
        self.assertEqual(code, 0, stdout)
        self.assertEqual(stdout.splitlines()[0], "通过")
        proc = subprocess.run(
            [sys.executable, str(SCRIPTS / "verify.py"), "--expr", "-1.6e-19 == -1.6e-19"],
            capture_output=True, text=True, check=False,
        )
        self.assertEqual(proc.returncode, 0, proc.stderr)
        self.assertEqual(proc.stdout.splitlines()[0], "通过")


class AdversarialVerifyNotationJsonlTests(unittest.TestCase):
    """tests/adversarial/verify_cases.jsonl：写法缺口对抗集，状态须落在 expect 列表内。"""

    @unittest.skipUnless(sympy_ready(), "未安装 SymPy")
    def test_verify_cases_jsonl(self):
        path = Path(__file__).resolve().parent / "adversarial" / "verify_cases.jsonl"
        rows = []
        for raw in path.read_text(encoding="utf-8").splitlines():
            if not raw.strip():
                continue
            rows.append(json.loads(raw))
        self.assertEqual(len(rows), 50)
        for case in rows:
            result = verify.check_math(case["expr"], case.get("where") or "")
            self.assertIn(
                result.status,
                case["expect"],
                f"{case['id']}: {case['expr']} where {case.get('where')!r} "
                f"-> {result.status} detail={result.detail!r} expect={case['expect']}",
            )
            if case["id"] == "e12":
                self.assertNotIn("E", result.detail.replace("detail:", ""))


class AdversarialVerifyCorpusTests(unittest.TestCase):
    @unittest.skipUnless(sympy_ready(), "未安装 SymPy")
    def test_verify_corpus(self):
        path = Path(__file__).resolve().parent / "adversarial" / "verify.tsv"
        rows = []
        for raw in path.read_text(encoding="utf-8").splitlines():
            if not raw.strip() or raw.startswith("#"):
                continue
            rows.append(raw.split("\t"))
        self.assertGreaterEqual(len(rows), 40)
        for row in rows:
            expr, where, expect, detail, rationale = (row + ["", "", "", "", ""])[:5]
            result = verify.check_math(expr, where)
            self.assertEqual(result.status, expect, f"{rationale}: {expr} where {where} -> {result}")
            if detail:
                self.assertEqual(result.detail, detail, f"{rationale}: {expr} {result}")


if __name__ == "__main__":
    unittest.main()
