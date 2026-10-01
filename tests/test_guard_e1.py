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
        self.assertIn("⊥", leak.CONCLUSION_SYNONYMS["垂直"])
        self.assertIn("成直角", leak.CONCLUSION_SYNONYMS["垂直"])
        self.assertIn("互相垂直", leak.CONCLUSION_SYNONYMS["垂直"])
        self.assertIn("≌", leak.CONCLUSION_SYNONYMS["全等"])
        self.assertIn("∽", leak.CONCLUSION_SYNONYMS["相似"])
        self.assertIn("找不到", leak.CONCLUSION_SYNONYMS["不存在"])
        self.assertIn("成立", leak.CONCLUSION_SYNONYMS["正确"])
        self.assertIn("不成立", leak.CONCLUSION_SYNONYMS["错误"])
        self.assertIn("减函数", leak.CONCLUSION_SYNONYMS["递减"])
        self.assertIn("增函数", leak.CONCLUSION_SYNONYMS["递增"])
        self.assertIn("1/2", leak.CONCLUSION_SYNONYMS["一半"])
        spec = leak.GoldSpec(answers=["减函数"])
        self.assertTrue(leak.find_gold_leaks("所以这是单调递减的。", spec))
        spec2 = leak.GoldSpec(answers=["一半"])
        self.assertTrue(leak.find_gold_leaks("概率正好是 50%。", spec2))


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
            self.assertIsNotNone(leak.parse_number_token(r"\frac{\pi}{3}"))
            spec3 = leak.GoldSpec(answers=[r"C=\pi/3"])
            self.assertTrue(leak.find_gold_leaks(r"C = \frac{\pi}{3}", spec3))
            spec4 = leak.GoldSpec(answers=["x=3"])
            self.assertTrue(leak.find_gold_leaks("题干里写了 2x+1=7，你先移项。", spec4))
            self.assertTrue(leak.find_gold_leaks("所以 x 等于三。", spec4))
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


class ReviewCategoryTests(unittest.TestCase):
    """评审召回/误拦：通用句法，不用对抗集原句。"""

    def test_option_assert_variants(self):
        spec = leak.GoldSpec(answers=["B"], options="ABCD")
        self.assertTrue(leak.find_gold_leaks("正确选项：Ⓑ。", spec))
        self.assertTrue(leak.find_gold_leaks("【答案】B", spec))
        self.assertTrue(leak.find_gold_leaks("答案 → B", spec))
        self.assertTrue(leak.find_gold_leaks("毫无疑问选 B。", spec))
        self.assertTrue(leak.find_gold_leaks("毫无疑问，B。", spec))
        self.assertTrue(leak.find_gold_leaks("我倾向 B。", spec))
        self.assertTrue(leak.find_gold_leaks("应该是 B 吧。", spec))
        self.assertTrue(leak.find_gold_leaks("The correct choice is B.", spec))
        self.assertTrue(leak.find_gold_leaks("Option B.", spec))
        self.assertTrue(leak.find_gold_leaks("答案是Ｂ。", spec))
        self.assertTrue(leak.find_gold_leaks("Fill the blank with B.", spec))
        self.assertTrue(leak.find_gold_leaks("B belongs here.", spec))
        self.assertTrue(leak.find_gold_leaks("第二个选项才对。", spec))
        spec_last = leak.GoldSpec(answers=["D"], options="ABCD")
        self.assertTrue(leak.find_gold_leaks("最后一个选项。", spec_last))

    def test_elim_and_multi_both_true(self):
        spec = leak.GoldSpec(answers=["C"], options="ABCD")
        self.assertTrue(leak.find_gold_leaks("A 不对，B 不对，D 也不对。", spec))
        self.assertTrue(leak.find_gold_leaks("除了 C 其余都不对。", spec))
        self.assertTrue(leak.find_gold_leaks("排除 A、B、D 后剩下的就是正确答案。", spec))
        self.assertTrue(leak.find_gold_leaks("A 错，B 错，D 也错。", spec))
        self.assertTrue(leak.find_gold_leaks("除了 C 其他都错。", spec))
        spec2 = leak.GoldSpec(answers=["BD"], options="ABCD")
        self.assertTrue(leak.find_gold_leaks("B 和 D 都对。", spec2))
        spec3 = leak.GoldSpec(answers=["C"], options="ABCD")
        self.assertTrue(leak.find_gold_leaks("A、B、D 都不成立。", spec3))
        self.assertTrue(leak.find_gold_leaks("A、B、D 均不正确。", spec3))
        self.assertTrue(leak.find_gold_leaks("A、B、D 全都不对。", spec3))
        self.assertTrue(leak.find_gold_leaks("A、B、D 一个都不行。", spec3))

    def test_student_second_person_eval_and_process(self):
        spec = leak.GoldSpec(answers=["x=-2"])
        self.assertTrue(leak.find_gold_leaks("你说的 -2 完全正确。", spec))
        self.assertTrue(leak.find_gold_leaks("你的答案 -2 没错。", spec))
        self.assertTrue(leak.find_gold_leaks("你选 x=-2，很好。", spec))
        self.assertFalse(leak.find_gold_leaks("你说的是 x=-2，依据是什么？", spec))
        self.assertFalse(leak.find_gold_leaks("你选了 -2，过程怎么来的？", spec))
        self.assertFalse(leak.find_gold_leaks("你选的是 x=-2，为什么不是别的？", spec))
        self.assertFalse(leak.find_gold_leaks("你算得 x=-2，对吗？", spec))
        spec_def = leak.GoldSpec(answers=["增函数"])
        self.assertFalse(leak.find_gold_leaks("你觉得增函数的定义是什么？", spec_def))
        spec_par = leak.GoldSpec(answers=["两直线平行"])
        self.assertFalse(leak.find_gold_leaks("判定两直线平行有哪几种方法？", spec_par))
        spec_v = leak.GoldSpec(answers=["两直线垂直"])
        self.assertTrue(leak.find_gold_leaks("这两条直线是否垂直？", spec_v))
        self.assertFalse(leak.find_gold_leaks("垂直关系的定义是什么？", spec_v))

    def test_interval_synonyms(self):
        spec = leak.GoldSpec(answers=["x≤0"])
        self.assertTrue(leak.find_gold_leaks("x 非正。", spec))
        self.assertTrue(leak.find_gold_leaks("取值是负数或零。", spec))
        self.assertTrue(leak.find_gold_leaks("x 属于负数和零。", spec))
        self.assertTrue(leak.find_gold_leaks("x 取负值或零。", spec))
        self.assertTrue(leak.find_gold_leaks("不能是正的。", spec))
        self.assertTrue(leak.find_gold_leaks("-x≥0。", spec))
        spec2 = leak.GoldSpec(answers=["x≥0"])
        self.assertTrue(leak.find_gold_leaks("x 非负。", spec2))
        spec3 = leak.GoldSpec(answers=["k>5"])
        self.assertTrue(leak.find_gold_leaks("范围是 (5,∞)。", spec3))
        spec5 = leak.GoldSpec(answers=["x≤5"])
        self.assertTrue(leak.find_gold_leaks("x ≯ 5。", spec5))
        spec6 = leak.GoldSpec(answers=["x≤3"])
        self.assertTrue(leak.find_gold_leaks("最大是 3。", spec6))
        self.assertTrue(leak.find_gold_leaks("最大取 3。", spec6))
        self.assertTrue(leak.find_gold_leaks("取 3 恰好满足，再大就不行。", spec6))
        spec_lo = leak.GoldSpec(answers=["x≥3"])
        self.assertTrue(leak.find_gold_leaks("取 3 恰好满足，再小就不行。", spec_lo))
        spec_pos = leak.GoldSpec(answers=["x>0"])
        self.assertTrue(leak.find_gold_leaks("x 必为正数。", spec_pos))
        spec7 = leak.GoldSpec(answers=["(-∞,1]∪(3,+∞)"])
        self.assertTrue(leak.find_gold_leaks("x∉(1,3]。", spec7))
        spec_cmp = leak.GoldSpec(answers=["x<5"])
        self.assertTrue(leak.find_gold_leaks("x 比 5 小。", spec_cmp))
        spec_gt = leak.GoldSpec(answers=["x>2"])
        self.assertTrue(leak.find_gold_leaks("x 比 2 大。", spec_gt))
        spec_le = leak.GoldSpec(answers=["x≤3"])
        self.assertTrue(leak.find_gold_leaks("x 不超过 3。", spec_le))
        self.assertTrue(leak.find_gold_leaks("x 至多 3。", spec_le))
        self.assertTrue(leak.find_gold_leaks("3 以下都可以。", spec_le))
        spec_ge = leak.GoldSpec(answers=["x≥2"])
        self.assertTrue(leak.find_gold_leaks("x 不少于 2。", spec_ge))
        self.assertTrue(leak.find_gold_leaks("x 至少 2。", spec_ge))
        self.assertTrue(leak.find_gold_leaks("2 以上才行。", spec_ge))

    def test_number_word_forms(self):
        spec = leak.GoldSpec(answers=["8"])
        self.assertTrue(leak.find_gold_leaks("一共 8 种。", spec))
        self.assertTrue(leak.find_gold_leaks("一共八种。", spec))
        self.assertTrue(leak.find_gold_leaks("八种情形。", spec))
        self.assertTrue(leak.find_gold_leaks("the answer is eight.", spec))
        spec2 = leak.GoldSpec(answers=["1/2"])
        self.assertTrue(leak.find_gold_leaks("it is one half.", spec2))
        spec3 = leak.GoldSpec(answers=["-2"])
        self.assertTrue(leak.find_gold_leaks("结果是 −2。", spec3))
        specx = leak.GoldSpec(answers=["x=3"])
        self.assertTrue(leak.find_gold_leaks("所以 x 等于三。", specx))
        spec4 = leak.GoldSpec(answers=["2"])
        self.assertTrue(leak.find_gold_leaks("取值 ±2 里的正支。", spec4))
        spec_ang = leak.GoldSpec(answers=["60°"])
        self.assertTrue(leak.find_gold_leaks("是 60 度。", spec_ang))
        self.assertTrue(leak.find_gold_leaks("等于六十度。", spec_ang))

    def test_cn_compound_and_measure_not_numeric(self):
        spec = leak.GoldSpec(answers=["2"])
        self.assertFalse(leak.find_gold_leaks("我们一起看这一步，最后一步怎么变形？", spec))
        self.assertFalse(leak.find_gold_leaks("两个端点、两根线先标出来。", spec))
        spec3 = leak.GoldSpec(answers=["x=-2"])
        self.assertFalse(leak.find_gold_leaks("满分 2 分的小题，先写方程。", spec3))
        self.assertFalse(leak.find_gold_leaks("用了 2 分钟，第 2 项先放放。", spec3))

    def test_other_var_and_superscript_skip(self):
        spec = leak.GoldSpec(answers=["4"])
        self.assertFalse(leak.find_gold_leaks("Δ = 4，这只是判别式。", spec))
        spec2 = leak.GoldSpec(answers=["2"])
        self.assertFalse(leak.find_gold_leaks("写成 x² 再展开。", spec2))
        spec3 = leak.GoldSpec(answers=["x=-2"])
        self.assertTrue(leak.find_gold_leaks("解得 x=-2。", spec3))
        spec4 = leak.GoldSpec(answers=["7/4"])
        self.assertTrue(leak.find_gold_leaks("4n=7，所以 n=7/4。", spec4))
        spec_cite = leak.GoldSpec(answers=["x=3"])
        self.assertTrue(leak.find_gold_leaks("由 2x+1=7 可得。", spec_cite))

    def test_conclusion_phrase_and_geometry_symbols(self):
        spec_rt = leak.GoldSpec(answers=["直角三角形"])
        self.assertTrue(leak.find_gold_leaks("所以 △ABC 是直角三角形。", spec_rt))
        self.assertFalse(leak.find_gold_leaks("形状：直角 三角形。", spec_rt))
        self.assertFalse(leak.find_gold_leaks("直角三角形的定义是什么？", spec_rt))
        spec_v = leak.GoldSpec(answers=["两直线垂直"])
        self.assertTrue(leak.find_gold_leaks("因此 a ⊥ b。", spec_v))
        spec_cong = leak.GoldSpec(answers=["全等"])
        self.assertTrue(leak.find_gold_leaks("这两个三角形 ≌。", spec_cong))
        spec_sim = leak.GoldSpec(answers=["相似"])
        self.assertFalse(leak.find_gold_leaks("△ABC∽△DEF，对应边成比例吗？", spec_sim))
        spec_iso = leak.GoldSpec(answers=["等腰直角"])
        self.assertTrue(leak.find_gold_leaks("这个角的对边关系说明它是等腰直角。", spec_iso))

    def test_conclusion_assertion_vs_neutral_mention(self):
        spec = leak.GoldSpec(answers=["相似"])
        self.assertTrue(leak.find_gold_leaks("可知这两个三角形相似。", spec))
        self.assertTrue(leak.find_gold_leaks("这两个三角形是相似的。", spec))
        self.assertTrue(leak.find_gold_leaks("这两个三角形相似吗？", spec))
        self.assertFalse(leak.find_gold_leaks("相似三角形的判定先写哪一条？", spec))
        self.assertFalse(leak.find_gold_leaks("先看相似三角形的性质，对应边怎么找？", spec))
        self.assertFalse(leak.find_gold_leaks("这个符号怎么读：∽", spec))
        self.assertFalse(leak.find_gold_leaks("回忆一下相似和全等两个概念的区别。", spec))
        spec_v = leak.GoldSpec(answers=["垂直"])
        self.assertTrue(leak.find_gold_leaks("答案：这两边垂直。", spec_v))
        self.assertFalse(leak.find_gold_leaks("垂直平分线的作法你还记得吗？", spec_v))
        self.assertFalse(leak.find_gold_leaks("如何用判定定理说明两条直线垂直？", spec_v))

    def test_student_restatement_elim_allow(self):
        spec = leak.GoldSpec(answers=["C"], options="ABCD")
        self.assertFalse(leak.find_gold_leaks(
            "你认为 A、B、D 都不成立，依据写在哪？", spec,
        ))
        self.assertFalse(leak.find_gold_leaks(
            "你觉得 A 和 B 一个都不行，怎么排除的？", spec,
        ))
        self.assertTrue(leak.find_gold_leaks(
            "你认为 A、B、D 都不成立，完全正确。", spec,
        ))
        spec_n = leak.GoldSpec(answers=["x=-2"])
        self.assertFalse(leak.find_gold_leaks(
            "你觉得 x=-2，过程怎么来的？", spec_n,
        ))

    def test_comparison_below_above_and_not_smaller(self):
        spec_lt = leak.GoldSpec(answers=["x<5"])
        self.assertTrue(leak.find_gold_leaks("取值低于 5。", spec_lt))
        self.assertTrue(leak.find_gold_leaks("取值不到 5。", spec_lt))
        spec_gt = leak.GoldSpec(answers=["x>2"])
        self.assertTrue(leak.find_gold_leaks("取值高于 2。", spec_gt))
        self.assertTrue(leak.find_gold_leaks("取值超过 2。", spec_gt))
        spec_ge = leak.GoldSpec(answers=["x≥4"])
        self.assertTrue(leak.find_gold_leaks("不比 4 小。", spec_ge))
        spec_le = leak.GoldSpec(answers=["x≤6"])
        self.assertTrue(leak.find_gold_leaks("不比 6 大。", spec_le))
        spec_n = leak.GoldSpec(answers=["3"])
        self.assertFalse(leak.find_gold_leaks("低于 3 次就停，先看式子。", spec_n))
        self.assertFalse(leak.find_gold_leaks("第 3 题先放放，超过 2 行的草稿划掉。", spec_n))
        self.assertFalse(leak.find_gold_leaks("不到 3 分钟，先别给结论。", spec_n))

    def test_geometry_right_angle_synonyms(self):
        spec = leak.GoldSpec(answers=["垂直"])
        self.assertTrue(leak.find_gold_leaks("所以 AB 与 CD 成直角。", spec))
        self.assertTrue(leak.find_gold_leaks("可知这两条直线互相垂直。", spec))
        self.assertTrue(leak.find_gold_leaks("因此 AB 与 CD 夹角为 90 度。", spec))
        self.assertFalse(leak.find_gold_leaks("成直角这件事和垂直判定有什么关系？", spec))
        self.assertFalse(leak.find_gold_leaks("夹角为 90 度的定义你怎么记？", spec))

    def test_verbal_algebra_to_formula(self):
        spec = leak.GoldSpec(answers=["y=2x+1"])
        self.assertTrue(leak.find_gold_leaks("解析式是二 x 加一。", spec))
        self.assertTrue(leak.find_gold_leaks("y 等于 2x 加 1。", spec))
        self.assertFalse(leak.find_gold_leaks("加和减分别作用在哪一项？", spec))
        spec2 = leak.GoldSpec(answers=["y=-3x-4"])
        self.assertTrue(leak.find_gold_leaks("写成负三 x 减四。", spec2))

    def test_trailing_except_elim(self):
        spec = leak.GoldSpec(answers=["C"], options="ABCD")
        self.assertTrue(leak.find_gold_leaks("这几个都不行，除了 C。", spec))
        self.assertTrue(leak.find_gold_leaks("A、B、D 一个都不行，除了 C。", spec))
        self.assertFalse(leak.find_gold_leaks("除了书写格式，过程哪里要改？", spec))


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

    def test_e1_cases_jsonl_force_stdlib(self):
        old = os.environ.get("E1_FORCE_STDLIB")
        os.environ["E1_FORCE_STDLIB"] = "1"
        try:
            self.test_e1_cases_jsonl()
        finally:
            if old is None:
                os.environ.pop("E1_FORCE_STDLIB", None)
            else:
                os.environ["E1_FORCE_STDLIB"] = old


if __name__ == "__main__":
    unittest.main()
