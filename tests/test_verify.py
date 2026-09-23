#!/usr/bin/env python3
"""数学机验：只判定已经抽好的式子。未安装 SymPy 时跳过真算例。"""

import contextlib
import io
import subprocess
import sys
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


class CliTests(unittest.TestCase):
    """命令行入口：四态退出码 通过0/矛盾1/无法解析3/未安装4，用法错误交给 argparse 的 2。"""

    def _run_main(self, argv):
        out = io.StringIO()
        with contextlib.redirect_stdout(out):
            code = verify.main(argv)
        return code, out.getvalue()

    def test_exit_code_table(self):
        self.assertEqual(verify.EXIT_CODES,
                         {"通过": 0, "矛盾": 1, "无法解析": 3, "未安装": 4})

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
        self.assertEqual(stdout.splitlines()[0], "矛盾")
        self.assertIn("化简差为 2*x", stdout)

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


if __name__ == "__main__":
    unittest.main()
