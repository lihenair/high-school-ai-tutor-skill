"""E1 金标比对：规格 §2–§3.5 单测 + adversarial jsonl 运行器。"""

import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SCRIPTS = ROOT / "skills" / "high-school-ai-tutor" / "scripts"
CASES = ROOT / "tests" / "adversarial" / "e1_cases.jsonl"
GUARD = SCRIPTS / "guard.py"
sys.path.insert(0, str(SCRIPTS))

import leak


def run_guard(reply, extra):
    env = {**os.environ, "PYTHONIOENCODING": "utf-8"}
    return subprocess.run(
        [sys.executable, str(GUARD), "--mode", "socratic", *extra, str(reply)],
        capture_output=True,
        text=True,
        cwd=str(ROOT),
        env=env,
        check=False,
    )


def write_gold(path, answers, options=None, extra_lines=()):
    lines = [f"answer: {a}" for a in answers]
    if options:
        lines.append(f"options: {options}")
    lines.extend(extra_lines)
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


class GoldFileAndCliTests(unittest.TestCase):
    """§2 金标文件和 CLI。"""

    def test_missing_gold_file_exit_1_no_traceback(self):
        with tempfile.TemporaryDirectory() as tmp:
            tmp = Path(tmp)
            reply = tmp / "r.txt"
            reply.write_text("难度：中等。先看已知。\n", encoding="utf-8")
            proc = run_guard(reply, ["--gold", str(tmp / "nope.txt")])
            self.assertEqual(proc.returncode, 1)
            self.assertIn("[ERROR] E1 金标文件无效", proc.stdout)
            self.assertNotIn("Traceback", proc.stdout + proc.stderr)

    def test_gold_without_answer_exit_1_no_traceback(self):
        with tempfile.TemporaryDirectory() as tmp:
            tmp = Path(tmp)
            reply = tmp / "r.txt"
            reply.write_text("难度：中等。先看已知。\n", encoding="utf-8")
            gold = tmp / "g.txt"
            gold.write_text("options: ABCD\n", encoding="utf-8")
            proc = run_guard(reply, ["--gold", str(gold)])
            self.assertEqual(proc.returncode, 1)
            self.assertIn("[ERROR] E1 金标文件无效", proc.stdout)
            self.assertNotIn("Traceback", proc.stdout + proc.stderr)

    def test_neither_gold_flag_matches_main_regex(self):
        with tempfile.TemporaryDirectory() as tmp:
            tmp = Path(tmp)
            reply = tmp / "r.txt"
            reply.write_text("难度：中等。答案是 C，你再想想。\n", encoding="utf-8")
            with_none = run_guard(reply, [])
            with_no = run_guard(reply, ["--no-gold"])
            self.assertEqual(with_none.returncode, 1)
            self.assertEqual(with_no.returncode, 1)
            self.assertIn("[ERROR] E1", with_none.stdout)
            self.assertIn("[ERROR] E1", with_no.stdout)

    def test_help_advertises_gold_flags(self):
        proc = subprocess.run(
            [sys.executable, str(GUARD), "--help"],
            capture_output=True, text=True, check=False,
        )
        self.assertIn("--gold", proc.stdout)
        self.assertIn("--no-gold", proc.stdout)
        self.assertIn("--stem-file", proc.stdout)

    def test_parse_repeated_answers_and_options(self):
        spec = leak.parse_gold_text(
            "answer: x=-1\nanswer: x=4\noptions: ABCD\noption D: y=1/x\n"
        )
        self.assertEqual(spec.answers, ["x=-1", "x=4"])
        self.assertEqual(spec.options, "ABCD")
        self.assertEqual(spec.option_contents["D"], "y=1/x")


class NormalizeTests(unittest.TestCase):
    """§3.2 字符串规范化。"""

    def test_nfkc_rel_latex_fraction_slash(self):
        a = leak.parse_number_token("７／４")
        b = leak.parse_number_token("\\frac{7}{4}")
        c = leak.parse_number_token("7/4")
        self.assertTrue(leak.nums_equiv(a, c, "7/4"))
        self.assertTrue(leak.nums_equiv(b, c, "7/4"))

    def test_chinese_mixed_percent_radical_degree(self):
        self.assertTrue(leak.nums_equiv(
            leak.parse_cn_quantity("一又四分之三"), leak.parse_number_token("7/4"),
        ))
        self.assertTrue(leak.nums_equiv(
            leak.parse_cn_quantity("百分之八"), leak.parse_number_token("8%"),
        ))
        self.assertEqual(leak.parse_cn_quantity("二倍根号二")[0], "rad")
        self.assertEqual(leak.parse_cn_quantity("六十度")[2], "angle-deg")

    def test_conclusion_synonym_table(self):
        self.assertIn("∥", leak.CONCLUSION_SYNONYMS["平行"])
        self.assertIn("找不到", leak.CONCLUSION_SYNONYMS["不存在"])
        self.assertIn("成立", leak.CONCLUSION_SYNONYMS["正确"])
        self.assertIn("不成立", leak.CONCLUSION_SYNONYMS["错误"])


class NumericEquivTests(unittest.TestCase):
    """§3.3 数值和符号等价。"""

    def test_fraction_decimal_percent_approx(self):
        g = leak.parse_number_token("7/4")
        self.assertTrue(leak.nums_equiv(leak.parse_number_token("1.75"), g, "1.75"))
        self.assertTrue(leak.nums_equiv(leak.parse_number_token("175%"), g, "175%"))
        self.assertTrue(leak.nums_equiv(leak.parse_number_token("1.8"), g, "1.8"))
        self.assertTrue(leak.nums_equiv(leak.parse_number_token("14/8"), g, "14/8"))

    def test_radical_unsimplified_and_approx(self):
        g = leak.parse_number_token("2√2")
        self.assertTrue(leak.nums_equiv(leak.parse_number_token("√8"), g, "√8"))
        self.assertTrue(leak.nums_equiv(leak.parse_number_token("2.83"), g, "2.83"))

    def test_angle_degree_radian(self):
        g = leak.parse_number_token("π/3")
        d = leak.parse_cn_quantity("六十度")
        self.assertTrue(leak.nums_equiv(d, g, "60°"))

    def test_unit_conversion(self):
        a = leak.parse_number_token("4m/s")
        b = leak.parse_number_token("14.4km/h")
        self.assertTrue(leak.nums_equiv(a, b, "14.4"))

    def test_interval_equal_nearmiss_component(self):
        a = leak.parse_interval("k>5")
        b = leak.parse_interval("(5,∞)")
        c = leak.parse_interval("k>=5")
        self.assertTrue(leak.iv_eq(a, b))
        self.assertTrue(leak.iv_finite_endpoint_diff(a, c))
        u = leak.parse_interval("a<=-1或a>=3")
        part = leak.parse_interval("a>=3")
        self.assertTrue(leak.iv_is_component(part, u))

    def test_point_in_interval_not_a_hit(self):
        spec = leak.GoldSpec(answers=["k>5"])
        hits = leak.find_gold_leaks("如果 k = 6，判别式是正还是负？", spec, stem="无实根")
        self.assertFalse(hits)

    def test_force_stdlib_fallback_does_not_crash(self):
        old = os.environ.get(leak.FORCE_STDLIB_ENV)
        os.environ[leak.FORCE_STDLIB_ENV] = "1"
        try:
            self.assertIsNone(leak.use_sympy())
            spec = leak.GoldSpec(answers=["7/4"])
            hits = leak.find_gold_leaks("这个数就是 1.75。", spec)
            self.assertTrue(hits)
            spec2 = leak.GoldSpec(answers=["k>5"])
            hits2 = leak.find_gold_leaks("k 必须大于 5 才行。", spec2)
            self.assertTrue(hits2)
        finally:
            if old is None:
                os.environ.pop(leak.FORCE_STDLIB_ENV, None)
            else:
                os.environ[leak.FORCE_STDLIB_ENV] = old


class AllowContextTests(unittest.TestCase):
    """§3.4 放行语境。"""

    def test_verified_stem_quote_allows_regex_therefore(self):
        spec = leak.GoldSpec(answers=["错误"])
        stem = "判断推理是否正确：由 2a - 4 > 0，因此 a > 3。"
        text = "题目写的是「由 2a - 4 > 0，因此 a > 3」，你先解 2a-4>0。"
        hits = leak.find_gold_leaks(text, spec, stem=stem)
        self.assertFalse(any(h.category != "结论" for h in hits) or False)
        items = leak.regex_hits(r"(?:所以|因此)[^。！？\n]{0,40}(?:[=≤≥<>]|等于)\s*[-+]?[\d.]", text)
        kept = leak.filter_regex_hits(
            text, [(*it, "x") for it in items], stem,
        )
        self.assertEqual(kept, [])

    def test_fake_quote_not_in_stem_not_allowed(self):
        spec = leak.GoldSpec(answers=["x=-2"])
        hits = leak.find_gold_leaks(
            "题目说「x=-2」，那你代进去看看。", spec, stem="解方程 3x + 7 = 1。",
        )
        self.assertTrue(hits)

    def test_student_wrong_allowed_student_gold_eval_blocked(self):
        spec = leak.GoldSpec(answers=["x=-2"])
        self.assertFalse(leak.find_gold_leaks("你写的 x = 2，代回原方程。", spec))
        self.assertTrue(leak.find_gold_leaks("你得到的 -2 完全正确。", spec))
        self.assertFalse(leak.find_gold_leaks("你写的是 x = -2，能说说依据吗？", spec))

    def test_first_person_blocked(self):
        spec = leak.GoldSpec(answers=["D"], options="ABCD")
        self.assertTrue(leak.find_gold_leaks("我选 D，你呢？", spec))

    def test_ordinal_and_count_skipped(self):
        spec = leak.GoldSpec(answers=["x=-2"])
        self.assertFalse(leak.find_gold_leaks("看第 2 步，你两边同时减了几？", spec))
        spec2 = leak.GoldSpec(answers=["k>5"])
        self.assertFalse(leak.find_gold_leaks("这里有 3 个系数，先写出来。", spec2))

    def test_neutral_option_allowed(self):
        spec = leak.GoldSpec(answers=["D"], options="ABCD")
        stem = "A. y=x^2 B. y=2^x C. y=lg x D. y=1/x"
        self.assertFalse(leak.find_gold_leaks(
            "先逐个看选项 A、B、C、D 对应的函数类型。", spec, stem=stem,
        ))
        self.assertFalse(leak.find_gold_leaks(
            "选项 D 里的 y=1/x，你能画图吗？", spec, stem=stem,
        ))

    def test_substitution_and_either_or_blocked(self):
        spec = leak.GoldSpec(answers=["x=-2"])
        self.assertTrue(leak.find_gold_leaks("不妨把 -2 代进去。", spec))
        self.assertTrue(leak.find_gold_leaks("是 2 还是 -2？", spec))


class OptionRuleTests(unittest.TestCase):
    """§3.5 选项判定。"""

    def test_partial_and_full_multi(self):
        spec = leak.GoldSpec(answers=["AC"], options="ABCD")
        self.assertTrue(leak.find_gold_leaks("A 肯定要选，其余你再想。", spec))
        self.assertTrue(leak.find_gold_leaks("应该选 A 和 C。", spec))

    def test_elimination_complement_subset(self):
        spec = leak.GoldSpec(answers=["D"], options="ABCD")
        self.assertTrue(leak.find_gold_leaks("A、B、C 都可以排除。", spec))
        self.assertFalse(leak.find_gold_leaks("A 是 y=x^2，它是增还是减？", spec))

    def test_content_as_answer(self):
        spec = leak.parse_gold_text("answer: D\noptions: ABCD\noption D: y=1/x\n")
        self.assertTrue(leak.find_gold_leaks("y=1/x 那个就是答案。", spec))

    def test_circled_and_jiazi(self):
        spec = leak.GoldSpec(answers=["②④"], options="①②③④")
        self.assertTrue(leak.find_gold_leaks("应填 2、4。", spec))
        spec2 = leak.GoldSpec(answers=["丙"], options="甲乙丙丁")
        self.assertTrue(leak.find_gold_leaks("甲、乙、丁都有错。", spec2))


class AdversarialRunnerTests(unittest.TestCase):
    """tests/adversarial/e1_cases.jsonl：block/pass 均须 100%。"""

    def test_e1_cases_jsonl(self):
        rows = [
            json.loads(line)
            for line in CASES.read_text(encoding="utf-8").splitlines()
            if line.strip()
        ]
        self.assertGreaterEqual(len(rows), 100)
        failed = []
        with tempfile.TemporaryDirectory() as tmp:
            tmp = Path(tmp)
            for case in rows:
                reply = tmp / "reply.txt"
                body = "难度：中等。\n" + case["reply"]
                reply.write_text(body, encoding="utf-8")
                extra = []
                if case.get("gold") is None:
                    extra.append("--no-gold")
                else:
                    gold = tmp / "gold.txt"
                    write_gold(gold, case["gold"], case.get("options"))
                    extra += ["--gold", str(gold)]
                if case.get("stem"):
                    stem = tmp / "stem.txt"
                    stem.write_text(case["stem"], encoding="utf-8")
                    extra += ["--stem-file", str(stem)]
                proc = run_guard(reply, extra)
                has_e1 = "[ERROR] E1" in proc.stdout
                expect_block = case["expect"] == "block"
                ok = has_e1 if expect_block else (not has_e1)
                if not ok:
                    failed.append(
                        f"{case['id']} expect={case['expect']} e1={has_e1} "
                        f"exit={proc.returncode}\n{proc.stdout[:400]}"
                    )
        self.assertEqual(failed, [], "\n\n".join(failed[:20]))


if __name__ == "__main__":
    unittest.main()
