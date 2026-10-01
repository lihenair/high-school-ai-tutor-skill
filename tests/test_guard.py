#!/usr/bin/env python3
"""回复守卫：漏答案、难度误拦、mermaid 围栏与整章图节点。"""

import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SCRIPTS = ROOT / "skills" / "high-school-ai-tutor" / "scripts"
sys.path.insert(0, str(SCRIPTS))

import guard  # noqa: E402


CHAPTER_OK = (ROOT / "tests" / "guard-cases" / "chapter-map-ok.txt").read_text(encoding="utf-8")


def socratic_issues(text, stem=""):
    return guard.check("socratic", text, False, stem=stem)


class LeakAndDifficultyTests(unittest.TestCase):
    def test_choice_letter_and_therefore_are_leaks(self):
        choice = socratic_issues("难度：中等。选 C。")
        self.assertTrue(any(item[0] == "ERROR" and item[1] == "E1" for item in choice), choice)
        therefore = socratic_issues("难度：中等。∴ a ≤ 0")
        self.assertTrue(any(item[0] == "ERROR" and item[1] == "E1" for item in therefore), therefore)

    def test_simple_substitution_is_not_illegal_difficulty(self):
        issues = socratic_issues("难度：基础，只需简单代入。开口朝哪边？")
        self.assertFalse(any(item[1] in ("E5", "E7") for item in issues), issues)

    def test_restating_student_choice_is_not_a_leak(self):
        issues = socratic_issues("难度：中等。你选 B。说说依据？")
        self.assertFalse(any(item[1] == "E1" for item in issues), issues)

    def test_teacher_stating_own_choice_is_a_leak(self):
        issues = socratic_issues("难度：中等。我选 B。")
        self.assertTrue(any(item[0] == "ERROR" and item[1] == "E1" for item in issues), issues)

    def test_therefore_equals_in_chinese_is_a_leak(self):
        issues = socratic_issues("难度：中等。所以 x 等于 3。开口朝哪边？")
        self.assertTrue(any(item[1] == "E1" for item in issues), issues)

    def test_scoring_standard_is_not_a_score_report(self):
        issues = socratic_issues("难度：中等。先看评分标准里的采分点。开口朝哪边？")
        self.assertFalse(any(item[1] == "E4" for item in issues), issues)


class MermaidTests(unittest.TestCase):
    def test_space_after_fence_still_checks_edges_and_style(self):
        spaced = CHAPTER_OK.replace("```mermaid\n", "```mermaid \n")
        self.assertTrue(guard.mermaid_blocks(spaced))
        self.assertEqual(guard.check_mermaid_edges(spaced), [])
        self.assertEqual(guard.check_mermaid_style(spaced), [])
        self.assertEqual(guard.check_pep_chem_chapter(spaced), [])

        broken = spaced.replace("-->|直接前置|", "==>|直接前置|")
        problems = guard.check_mermaid_edges(broken)
        self.assertTrue(problems, problems)

    def test_thick_and_plain_lines_need_labels(self):
        thick = """```mermaid
flowchart TD
  a["A（概念）"]:::concept ==> b["B（概念）"]:::concept
```"""
        plain = """```mermaid
flowchart TD
  a["A（概念）"]:::concept --- b["B（概念）"]:::concept
```"""
        self.assertTrue(any("未标注" in item for item in guard.check_mermaid_edges(thick)))
        self.assertTrue(any("未标注" in item for item in guard.check_mermaid_edges(plain)))

    def test_required_names_cannot_share_one_node(self):
        names = "".join(guard.PEP_CHEM_BX1_CH1_REQUIRED)
        stuffed = (
            "整章图：人教版《化学 必修 第一册》（2019）第一章\n"
            "```mermaid\n"
            "flowchart TD\n"
            "  classDef concept fill:#E8F1FF,stroke:#3B6FB6,color:#1A1A1A\n"
            "  classDef skill fill:#E7F6EE,stroke:#2E7D4F,color:#1A1A1A\n"
            f'  x["{names}（概念）"]:::concept\n'
            "```\n"
        )
        problems = guard.check_pep_chem_chapter(stuffed)
        self.assertTrue(problems, problems)

    def test_canonical_chapter_map_still_passes(self):
        self.assertEqual(guard.check_pep_chem_chapter(CHAPTER_OK), [])

    def test_circular_nodes_count_as_present(self):
        lines = [
            "整章图：人教版《化学 必修 第一册》（2019）第一章",
            "```mermaid",
            "flowchart TD",
            "  classDef concept fill:#E8F1FF,stroke:#3B6FB6,color:#1A1A1A",
            "  classDef skill fill:#E7F6EE,stroke:#2E7D4F,color:#1A1A1A",
        ]
        for index, name in enumerate(guard.PEP_CHEM_BX1_CH1_REQUIRED):
            lines.append(f'  n{index}(("{name}（概念）")):::concept')
        lines.append("```")
        self.assertEqual(guard.check_pep_chem_chapter("\n".join(lines)), [])

    def test_rounded_and_diamond_nodes_count_as_present(self):
        lines = [
            "整章图：人教版《化学 必修 第一册》（2019）第一章",
            "```mermaid",
            "flowchart TD",
            "  classDef concept fill:#E8F1FF,stroke:#3B6FB6,color:#1A1A1A",
            "  classDef skill fill:#E7F6EE,stroke:#2E7D4F,color:#1A1A1A",
        ]
        names = list(guard.PEP_CHEM_BX1_CH1_REQUIRED)
        for index, name in enumerate(names):
            if index % 2 == 0:
                lines.append(f'  n{index}("{name}（概念）"):::concept')
            else:
                lines.append(f'  n{index}{{"{name}（概念）"}}:::concept')
        lines.append("```")
        self.assertEqual(guard.check_pep_chem_chapter("\n".join(lines)), [])

    def test_circle_marker_edge_needs_a_label(self):
        text = """```mermaid
flowchart TD
  a["A（概念）"]:::concept --o b["B（概念）"]:::concept
```"""
        self.assertTrue(any("未标注" in item for item in guard.check_mermaid_edges(text)))
        crossed = text.replace("--o", "--x")
        self.assertTrue(any("未标注" in item for item in guard.check_mermaid_edges(crossed)))

    def test_required_names_cannot_hide_in_a_few_nodes(self):
        names = list(guard.PEP_CHEM_BX1_CH1_REQUIRED)
        chunks = ["".join(names[i:i + 5]) for i in range(0, len(names), 5)]
        lines = [
            "整章图：人教版《化学 必修 第一册》（2019）第一章",
            "```mermaid",
            "flowchart TD",
            "  classDef concept fill:#E8F1FF,stroke:#3B6FB6,color:#1A1A1A",
            "  classDef skill fill:#E7F6EE,stroke:#2E7D4F,color:#1A1A1A",
        ]
        for index, chunk in enumerate(chunks):
            lines.append(f'  n{index}["{chunk}（概念）"]:::concept')
        lines.append("```")
        problems = guard.check_pep_chem_chapter("\n".join(lines))
        self.assertTrue(problems, problems)

    def test_full_mode_detects_spaced_mermaid_fence(self):
        text = CHAPTER_OK.replace("```mermaid\n", "``` mermaid\n")
        issues = guard.check("full", text, False)
        self.assertFalse(any(item[1] == "E10" for item in issues), issues)

    def test_hint_points_at_existing_chapter_map(self):
        issues = guard.check("socratic", CHAPTER_OK.replace("-->|直接前置|", "-->|相关|"), False)
        rules = " ".join(item[3] for item in issues if item[1] == "E11")
        self.assertIn("chapter-map.md", rules)
        self.assertNotIn("自学知识图谱", rules)


class StudyAndScoreTests(unittest.TestCase):
    def test_bom_does_not_hide_study_label(self):
        body = (ROOT / "tests" / "guard-cases" / "self-study" / "08-overview-ok.txt").read_text(encoding="utf-8")
        issues = guard.check_study("\ufeff" + body)
        self.assertFalse(any(item[0] == "ERROR" for item in issues), issues)

    def test_difficulty_in_body_does_not_skip_study_label(self):
        issues = guard.check_study("先看这章的难度：比上一章更综合。\n拓扑学习顺序：先分类。")
        self.assertTrue(any(item[1] == "E17a" for item in issues), issues)

    def test_scores_without_weighted_total_are_an_error(self):
        text = (ROOT / "tests" / "guard-cases" / "full-ok.txt").read_text(encoding="utf-8")
        text = text.replace("本题结论是 a≤1", "五项评分 4、3、2、2、3 分。本题结论是 a≤1")
        issues = guard.check("full", text, False)
        self.assertTrue(any(item[1] == "E8" for item in issues), issues)

    def test_slash_scores_and_bare_weighted_total(self):
        text = (ROOT / "tests" / "guard-cases" / "full-ok.txt").read_text(encoding="utf-8")
        text = text.replace("本题结论是 a≤1", "五项评分 5/4/3/2/1 分。加权 1.00。本题结论是 a≤1")
        issues = guard.check("full", text, False)
        e8 = [item for item in issues if item[1] == "E8"]
        self.assertTrue(e8, issues)
        self.assertIn("加权与五项分不一致", e8[0][2])
        self.assertNotIn("没有写出加权分", e8[0][2])

    def test_space_separated_scores_and_approx_weighted_wording(self):
        text = (ROOT / "tests" / "guard-cases" / "full-ok.txt").read_text(encoding="utf-8")
        text = text.replace("本题结论是 a≤1", "五项评分 5 4 3 2 1 分。加权约为 2.9。本题结论是 a≤1")
        issues = guard.check("full", text, False)
        e8 = [item for item in issues if item[1] == "E8"]
        self.assertTrue(e8, issues)
        self.assertIn("加权与五项分不一致", e8[0][2])

    def test_empty_seven_slot_lines_are_not_a_node_page(self):
        lines = ["【模式：自学 · 状态：节点 · 节点：氧化还原反应】"]
        lines.extend(f"{marker}：" for marker in guard.SLOT_MARKERS)
        issues = guard.check_study("\n".join(lines))
        self.assertTrue(any(item[1] == "E18" for item in issues), issues)

    def test_empty_ellipsis_slot_lines_fail(self):
        lines = ["【模式：自学 · 状态：节点 · 节点：氧化还原反应】"]
        lines.extend(f"{marker}：…" for marker in guard.SLOT_MARKERS)
        issues = guard.check_study("\n".join(lines))
        self.assertTrue(any(item[1] == "E18" for item in issues), issues)

    def test_score_colon_is_not_the_weighted_total(self):
        text = (ROOT / "tests" / "guard-cases" / "full-ok.txt").read_text(encoding="utf-8")
        text = text.replace("本题结论是 a≤1", "评分：5、4、3、2、1 分，加权 3.50。本题结论是 a≤1")
        issues = guard.check("full", text, False)
        self.assertFalse(any(item[1] == "E8" for item in issues), issues)

    def test_named_dimension_scores_are_checked(self):
        text = (ROOT / "tests" / "guard-cases" / "full-ok.txt").read_text(encoding="utf-8")
        text = text.replace(
            "本题结论是 a≤1",
            "知识点数5 思维跨度4 综合程度3 运算2 频率1，加权 2.00。本题结论是 a≤1",
        )
        issues = guard.check("full", text, False)
        e8 = [item for item in issues if item[1] == "E8"]
        self.assertTrue(e8, issues)
        self.assertIn("加权与五项分不一致", e8[0][2])
        self.assertNotIn("5.00", e8[0][2])

    def test_difficulty_on_first_line_still_needs_study_label(self):
        issues = guard.check_study("难度：中等。先看这章怎么学。\n拓扑学习顺序：先分类。")
        self.assertTrue(any(item[1] == "E17a" for item in issues), issues)

    def test_seven_slots_on_one_line_are_not_a_node_page(self):
        slots = "一句话定义 为什么重要 最小例子 易错点 易混辨析 判别自测 拓展入口"
        text = "【模式：自学 · 状态：节点 · 节点：氧化还原反应】\n" + slots
        issues = guard.check_study(text)
        self.assertTrue(any(item[1] == "E18" for item in issues), issues)


class Issue33GuardReproTests(unittest.TestCase):
    def test_eleven_covering_nodes_do_not_satisfy_required_names(self):
        names = list(guard.PEP_CHEM_BX1_CH1_REQUIRED)
        chunks = []
        for i in range(11):
            start = i * len(names) // 11
            end = (i + 1) * len(names) // 11
            chunks.append("".join(names[start:end] or names[i:i + 1]))
        lines = [
            "整章图：人教版《化学 必修 第一册》（2019）第一章",
            "```mermaid",
            "flowchart TD",
            "  classDef concept fill:#E8F1FF,stroke:#3B6FB6,color:#1A1A1A",
            "  classDef skill fill:#E7F6EE,stroke:#2E7D4F,color:#1A1A1A",
        ]
        for index, chunk in enumerate(chunks):
            lines.append(f'  n{index}["{chunk}（概念）"]:::concept')
        lines.append("```")
        problems = guard.check_pep_chem_chapter("\n".join(lines))
        self.assertTrue(problems, problems)

    def test_labeled_bidirectional_edge_is_rejected(self):
        text = """```mermaid
flowchart TD
  a["A（概念）"]:::concept <-->|直接前置| b["B（概念）"]:::concept
```"""
        problems = guard.check_mermaid_edges(text)
        self.assertTrue(any("直接前置" in item or "实线" in item or "未标注" in item for item in problems), problems)

    def test_generic_quoted_node_shapes_still_cover_required_names(self):
        original = 'mix["纯净物 / 混合物（概念）"]'
        shapes = [
            'mix(["纯净物 / 混合物（概念）"])',
            'mix[["纯净物 / 混合物（概念）"]]',
            'mix[("纯净物 / 混合物（概念）")]',
            'mix{{"纯净物 / 混合物（概念）"}}',
            'mix((("纯净物 / 混合物（概念）")))',
        ]
        for wrapped in shapes:
            problems = guard.check_pep_chem_chapter(CHAPTER_OK.replace(original, wrapped, 1))
            self.assertEqual(problems, [], wrapped)

    def test_canon_aliases_and_common_phrasing_cover_required_names(self):
        tyndall = CHAPTER_OK.replace("丁达尔效应", "丁达尔现象")
        self.assertEqual(guard.check_pep_chem_chapter(tyndall), [])
        oxide = CHAPTER_OK.replace("氧化物、酸、碱、盐", "常见氧化物、酸、碱、盐")
        self.assertEqual(guard.check_pep_chem_chapter(oxide), [])

    def test_asymmetric_quoted_nodes_count_as_present(self):
        lines = [
            "整章图：人教版《化学 必修 第一册》（2019）第一章",
            "```mermaid",
            "flowchart TD",
            "  classDef concept fill:#E8F1FF,stroke:#3B6FB6,color:#1A1A1A",
            "  classDef skill fill:#E7F6EE,stroke:#2E7D4F,color:#1A1A1A",
        ]
        for index, name in enumerate(guard.PEP_CHEM_BX1_CH1_REQUIRED):
            lines.append(f'  n{index}>"{name}（概念）"]:::concept')
        lines.append("```")
        self.assertEqual(guard.check_pep_chem_chapter("\n".join(lines)), [])

    def test_range_and_choice_leaks_are_caught(self):
        rang = socratic_issues("难度：中等。范围应当是 a≤0")
        self.assertTrue(any(item[1] == "E1" for item in rang), rang)
        choice = socratic_issues("难度：中等。我选C，你呢")
        self.assertTrue(any(item[1] == "E1" for item in choice), choice)

    def test_quoted_stem_and_probe_question_are_not_leaks(self):
        stem = "已知因此 x>0，答案是 B。"
        quoted = socratic_issues("难度：中等。题干给出「因此 x>0」。开口朝哪边？", stem=stem)
        self.assertFalse(any(item[1] == "E1" for item in quoted), quoted)
        probe = socratic_issues("难度：中等。所以它等于 2 倍的什么？")
        self.assertFalse(any(item[1] == "E1" for item in probe), probe)
        open_range = socratic_issues("难度：中等。这个范围是什么？")
        self.assertFalse(any(item[1] == "E1" for item in open_range), open_range)
        stem_given = socratic_issues("难度：中等。题干给出「答案是 B」。开口朝哪边？", stem=stem)
        self.assertTrue(any(item[1] == "E1" for item in stem_given), stem_given)
        bare_write = socratic_issues("难度：中等。题干写「因此 x>0」。开口朝哪边？")
        self.assertTrue(any(item[1] == "E1" for item in bare_write), bare_write)

    def test_confirmation_and_unmarked_quotes_are_still_leaks(self):
        cases = [
            "难度：中等。答案是 B，对吗？",
            "难度：中等。所以 x = 3，对吗？",
            "难度：中等。答案为 12，你算出来是多少？",
            "难度：中等。老师觉得「答案是 B」。",
            "难度：中等。取值范围是 a≤0，对吗？",
            "难度：中等。故选 D，你同意吗？",
            '难度：中等。这里"所以 x=3"。',
            "难度：中等。你看，「故选 C」。",
            "难度：中等。范围应当是 a≤0，你看对吗？",
        ]
        for text in cases:
            issues = socratic_issues(text)
            self.assertTrue(
                any(item[1] == "E1" for item in issues),
                f"expected E1 for {text!r}: {issues}",
            )

    def test_fix_hints_point_at_real_sections(self):
        self.assertNotIn("SKILL.md「难度总则」", guard.RULE_DIFFICULTY)
        self.assertIn("full.md", guard.RULE_DIFFICULTY)
        self.assertIn("full.md", guard.RULE_SUMMARY_FMT)
        issues = guard.check("socratic", CHAPTER_OK.replace("-->|直接前置|", "-->|相关|"), False)
        rules = " ".join(item[3] for item in issues if item[1] == "E11")
        self.assertIn("chapter-map.md「边类型」", rules)


def _load_tsv(path):
    rows = []
    for raw in path.read_text(encoding="utf-8").splitlines():
        if not raw.strip() or raw.startswith("#"):
            continue
        rows.append(raw.split("\t"))
    return rows


class AdversarialCorpusTests(unittest.TestCase):
    def test_leak_corpus(self):
        path = ROOT / "tests" / "adversarial" / "leak.tsv"
        rows = _load_tsv(path)
        self.assertGreaterEqual(len(rows), 50, "leak corpus too small")
        for row in rows:
            text, expect, stem, rationale = (row + ["", "", "", ""])[:4]
            issues = socratic_issues(text, stem=stem)
            has_e1 = any(item[1] == "E1" for item in issues)
            if expect == "E1":
                self.assertTrue(has_e1, f"{rationale}: {text!r} {issues}")
            else:
                self.assertFalse(has_e1, f"{rationale}: {text!r} {issues}")

    def test_chapter_map_corpus(self):
        folder = ROOT / "tests" / "adversarial" / "chapter_map"
        rows = _load_tsv(folder / "index.tsv")
        self.assertGreaterEqual(len(rows), 10)
        for row in rows:
            name, expect, rationale = (row + ["", "", ""])[:3]
            text = (folder / name).read_text(encoding="utf-8")
            problems = guard.check_pep_chem_chapter(text)
            if expect == "E12":
                self.assertTrue(problems, f"{rationale}: {name} passed")
            else:
                self.assertEqual(problems, [], f"{rationale}: {name} {problems}")

    def test_weighted_corpus(self):
        path = ROOT / "tests" / "adversarial" / "weighted.tsv"
        base = (ROOT / "tests" / "guard-cases" / "full-ok.txt").read_text(encoding="utf-8")
        rows = _load_tsv(path)
        self.assertGreaterEqual(len(rows), 8)
        for row in rows:
            snippet, expect, rationale = (row + ["", "", ""])[:3]
            snippet = snippet.replace("\\n", "\n")
            text = base.replace("本题结论是 a≤1", snippet + "本题结论是 a≤1")
            issues = guard.check("full", text, False)
            has_e8 = any(item[1] == "E8" for item in issues)
            if expect == "E8":
                self.assertTrue(has_e8, f"{rationale}: {snippet!r} {issues}")
                if "misleading-total" in rationale:
                    msg = " ".join(item[2] for item in issues if item[1] == "E8")
                    self.assertIn("写的是", msg)
                    self.assertNotIn("没有写出加权分", msg)
            else:
                self.assertFalse(has_e8, f"{rationale}: {snippet!r} {[i for i in issues if i[1]=='E8']}")

    def test_reference_weighted_examples_pass(self):
        base = (ROOT / "tests" / "guard-cases" / "full-ok.txt").read_text(encoding="utf-8")
        refs = (ROOT / "skills" / "high-school-ai-tutor" / "references").glob("*.md")
        found = 0
        for path in refs:
            for line in path.read_text(encoding="utf-8").splitlines():
                if "加权" in line and "0.30" in line and "=" in line:
                    found += 1
                    text = base.replace("本题结论是 a≤1", line.strip() + "本题结论是 a≤1")
                    issues = guard.check("full", text, False)
                    e8 = [item for item in issues if item[1] == "E8"]
                    self.assertFalse(e8, f"{path.name}: {line!r} {e8}")
        self.assertGreaterEqual(found, 4)

    def test_slot_corpus(self):
        path = ROOT / "tests" / "adversarial" / "slots.tsv"
        rows = _load_tsv(path)
        self.assertGreaterEqual(len(rows), 10)
        for row in rows:
            filler, expect, rationale = (row + ["", "", ""])[:3]
            lines = ["【模式：自学 · 状态：节点 · 节点：氧化还原反应】"]
            lines.extend(f"{marker}：{filler}" for marker in guard.SLOT_MARKERS)
            issues = guard.check_study("\n".join(lines))
            has_e18 = any(item[1] == "E18" for item in issues)
            if expect == "E18":
                self.assertTrue(has_e18, f"{rationale}: {filler!r} {issues}")
            else:
                self.assertFalse(has_e18, f"{rationale}: {filler!r} {issues}")


if __name__ == "__main__":
    unittest.main()
