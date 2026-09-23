#!/usr/bin/env python3
"""数学机验：只判定已经抽好的式子。未安装 SymPy 时跳过真算例。"""

import sys
import unittest
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "skills" / "high-school-ai-tutor" / "scripts"))

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
    def test_unparsed_natural_language_and_open_expression(self):
        self.assertEqual(verify.check_math("不是式子").status, "无法解析")
        self.assertEqual(verify.check_math("a <= 0", "在 [0,3] 单调递增").status, "无法解析")
        self.assertEqual(verify.check_math("x + 1").status, "无法解析")


if __name__ == "__main__":
    unittest.main()
