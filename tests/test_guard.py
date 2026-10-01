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


def socratic_issues(text, answers=(), options="ABCD", stem="", require_gold=False):
    return guard.check(
        "socratic", text, False,
        answers=answers, options=options, stem=stem, require_gold=require_gold,
    )


def has_e1(issues):
    return any(item[0] == "ERROR" and item[1] == "E1" for item in issues)


class LeakAndDifficultyTests(unittest.TestCase):
    def test_missing_gold_is_error_not_warning(self):
        issues = socratic_issues("难度：中等。开口朝哪边？", require_gold=True)
        self.assertTrue(has_e1(issues), issues)
        self.assertTrue(any("未提供金标" in item[2] for item in issues), issues)

    def test_choice_letter_and_therefore_are_leaks(self):
        choice = socratic_issues("难度：中等。选 C。", answers=["C"])
        self.assertTrue(has_e1(choice), choice)
        therefore = socratic_issues("难度：中等。∴ a ≤ 0", answers=["a≤0"])
        self.assertTrue(has_e1(therefore), therefore)

    def test_simple_substitution_is_not_illegal_difficulty(self):
        issues = socratic_issues("难度：基础，只需简单代入。开口朝哪边？")
        self.assertFalse(any(item[1] in ("E5", "E7") for item in issues), issues)

    def test_restating_student_choice_is_not_a_leak(self):
        issues = socratic_issues("难度：中等。你选 B。说说依据？", answers=["B"])
        self.assertFalse(has_e1(issues), issues)

    def test_teacher_stating_own_choice_is_a_leak(self):
        issues = socratic_issues("难度：中等。我选 B。", answers=["B"])
        self.assertTrue(has_e1(issues), issues)

    def test_therefore_equals_in_chinese_is_a_leak(self):
        issues = socratic_issues("难度：中等。所以 x 等于 3。开口朝哪边？", answers=["x=3"])
        self.assertTrue(has_e1(issues), issues)

    def test_scoring_standard_is_not_a_score_report(self):
        issues = socratic_issues("难度：中等。先看评分标准里的采分点。开口朝哪边？")
        self.assertFalse(any(item[1] == "E4" for item in issues), issues)

    def test_incidental_step_number_is_not_a_leak(self):
        issues = socratic_issues("难度：中等。第 3 步先看定义。开口朝哪边？", answers=["3"])
        self.assertFalse(has_e1(issues), issues)

    def test_stem_verbatim_passes_unless_it_is_gold(self):
        stem = "已知 x>0，求最小值。"
        ok = socratic_issues("难度：中等。题目说「已知 x>0，求最小值。」下一步看什么？",
                             answers=["x=2"], stem=stem)
        self.assertFalse(has_e1(ok), ok)
        leak_hit = socratic_issues("难度：中等。题目说「x>0」。", answers=["x>0"], stem=stem)
        self.assertTrue(has_e1(leak_hit), leak_hit)

    def test_fallback_no_gold_is_at_least_as_strong_as_main(self):
        issues = socratic_issues("难度：中等。答案是 12。", require_gold=False)
        self.assertTrue(has_e1(issues), issues)
        range_hit = socratic_issues("难度：中等。范围应当是 a≤0。", require_gold=False)
        self.assertTrue(has_e1(range_hit), range_hit)

    def test_confirming_student_gold_choice_is_a_leak(self):
        issues = socratic_issues("难度：中等。你选丙，没错。", answers=["丙"], options="甲乙丙丁")
        self.assertTrue(has_e1(issues), issues)

    def test_elimination_leaving_gold_is_a_leak(self):
        issues = socratic_issues("难度：中等。排除甲、乙、丁。", answers=["丙"], options="甲乙丙丁")
        self.assertTrue(has_e1(issues), issues)


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
        issues = guard.check("socratic", CHAPTER_OK.replace("-->|直接前置|", "-->|相关|"), False,
                             require_gold=False)
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

    def test_slash_scores_are_extracted(self):
        text = (ROOT / "tests" / "guard-cases" / "full-ok.txt").read_text(encoding="utf-8")
        text = text.replace("本题结论是 a≤1", "五项评分 5/4/3/2/1 分。加权 3.50。本题结论是 a≤1")
        issues = guard.check("full", text, False)
        self.assertFalse(any(item[1] == "E8" for item in issues), issues)

    def test_weighted_1_00_is_inconsistent_not_missing(self):
        text = (ROOT / "tests" / "guard-cases" / "full-ok.txt").read_text(encoding="utf-8")
        text = text.replace("本题结论是 a≤1", "4、3、2、2、3 分。加权 1.00。本题结论是 a≤1")
        issues = guard.check("full", text, False)
        e8 = [item for item in issues if item[1] == "E8"]
        self.assertTrue(e8, issues)
        self.assertIn("不一致", e8[0][2])

    def test_empty_slot_is_e18(self):
        body = (ROOT / "tests" / "guard-cases" / "self-study" / "09-selftest-marked.txt").read_text(encoding="utf-8")
        empty = body.replace("有电子转移的反应是氧化还原反应。", "略")
        issues = guard.check_study(empty)
        self.assertTrue(any(item[1] == "E18" for item in issues), issues)

    def test_difficulty_first_line_does_not_skip_slot_label(self):
        body = (ROOT / "tests" / "guard-cases" / "self-study" / "09-selftest-marked.txt").read_text(encoding="utf-8")
        text = "难度：中等。\n" + "\n".join(body.splitlines()[1:])
        issues = guard.check_study(text)
        self.assertTrue(any(item[1] == "E17a" for item in issues), issues)

    def test_jammed_eleven_nodes_are_e12(self):
        names = list(guard.PEP_CHEM_BX1_CH1_REQUIRED)
        lines = [
            "整章图：人教版《化学 必修 第一册》（2019）第一章",
            "```mermaid",
            "flowchart TD",
            "  classDef concept fill:#E8F1FF,stroke:#3B6FB6,color:#1A1A1A",
            "  classDef skill fill:#E7F6EE,stroke:#2E7D4F,color:#1A1A1A",
        ]
        for index in range(11):
            left = names[index]
            right = names[index + 8] if index + 8 < len(names) else names[index - 1]
            lines.append(f'  n{index}["{left}{right}（概念）"]:::concept')
        lines.append("```")
        problems = guard.check_pep_chem_chapter("\n".join(lines))
        self.assertTrue(problems, problems)

    def test_comment_and_subgraph_titles_do_not_cover(self):
        required = "、".join(guard.PEP_CHEM_BX1_CH1_REQUIRED)
        text = (
            "整章图：人教版《化学 必修 第一册》（2019）第一章\n"
            "```mermaid\nflowchart TD\n"
            "  classDef concept fill:#E8F1FF,stroke:#3B6FB6,color:#1A1A1A\n"
            "  classDef skill fill:#E7F6EE,stroke:#2E7D4F,color:#1A1A1A\n"
            f"  %% {required}\n"
            f'  subgraph s1["{required}"]\n'
            '    x["无关节点（概念）"]:::concept\n'
            "  end\n```\n"
        )
        problems = guard.check_pep_chem_chapter(text)
        self.assertTrue(problems, problems)


class AdversarialCorpusTests(unittest.TestCase):
    def _load(self, name):
        path = ROOT / "tests" / "adversarial" / name
        rows = []
        for raw in path.read_text(encoding="utf-8").splitlines():
            if not raw.strip() or raw.startswith("#"):
                continue
            rows.append(raw.split("\t"))
        return rows

    def test_leak_corpus(self):
        rows = self._load("leak.tsv")
        self.assertGreaterEqual(len(rows), 80)
        blocked = allowed = 0
        for row in rows:
            expect, reply, answer, options, stem, rationale = (row + [""] * 6)[:6]
            issues = socratic_issues(reply, answers=[answer], options=options, stem=stem)
            leaked = has_e1(issues)
            if expect == "BLOCK":
                blocked += 1
                self.assertTrue(leaked, f"{rationale}: {reply} gold={answer} {issues}")
            else:
                allowed += 1
                self.assertFalse(leaked, f"{rationale}: {reply} gold={answer} {issues}")
        self.assertGreaterEqual(blocked, 40)
        self.assertGreaterEqual(allowed, 40)

    def test_weighted_corpus(self):
        rows = self._load("weighted.tsv")
        self.assertGreaterEqual(len(rows), 8)
        template = (ROOT / "tests" / "guard-cases" / "full-ok.txt").read_text(encoding="utf-8")
        for row in rows:
            expect, snippet, rationale = (row + ["", "", ""])[:3]
            text = template.replace("本题结论是 a≤1", snippet + " 本题结论是 a≤1")
            issues = guard.check("full", text, False)
            hit = any(item[1] == "E8" for item in issues)
            if expect == "BLOCK":
                self.assertTrue(hit, rationale)
            else:
                self.assertFalse(hit, f"{rationale} {issues}")

    def test_slots_corpus(self):
        rows = self._load("slots.tsv")
        self.assertGreaterEqual(len(rows), 6)
        for row in rows:
            expect, path, rationale = (row + ["", "", ""])[:3]
            text = (ROOT / "tests" / "adversarial" / "slots" / path).read_text(encoding="utf-8")
            issues = guard.check_study(text)
            hit = any(item[1] == "E18" for item in issues)
            if expect == "BLOCK":
                self.assertTrue(hit, rationale)
            else:
                self.assertFalse(hit, f"{rationale} {issues}")


if __name__ == "__main__":
    unittest.main()
