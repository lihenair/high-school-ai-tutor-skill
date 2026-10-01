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


def socratic_issues(text):
    return guard.check("socratic", text, False)


def _pep_map(labels, extra=()):
    lines = [
        "整章图：人教版《化学 必修 第一册》（2019）第一章",
        "```mermaid",
        "flowchart TD",
        "  classDef concept fill:#E8F1FF,stroke:#3B6FB6,color:#1A1A1A",
        "  classDef skill fill:#E7F6EE,stroke:#2E7D4F,color:#1A1A1A",
        *extra,
    ]
    for index, label in enumerate(labels):
        lines.append(f'  n{index}["{label}（概念）"]:::concept')
    lines.append("```")
    return "\n".join(lines)


def _required_labels_replacing(target, replacement):
    return [replacement if name == target else name for name in guard.PEP_CHEM_BX1_CH1_REQUIRED]


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

    def test_own_canon_alias_satisfies_required_node(self):
        labels = _required_labels_replacing("分散系", "胶体")
        self.assertEqual(guard.check_pep_chem_chapter(_pep_map(labels)), [])

    def test_sibling_canon_alias_does_not_satisfy_required_node(self):
        labels = _required_labels_replacing("丁达尔", "胶体")
        problems = guard.check_pep_chem_chapter(_pep_map(labels))
        self.assertTrue(any("缺少节点" in item and "丁达尔" in item for item in problems), problems)

    def test_comment_text_does_not_count_as_a_node(self):
        labels = [name for name in guard.PEP_CHEM_BX1_CH1_REQUIRED if name not in ("纯净物", "混合物")]
        extra = ('  %% parked["纯净物（概念）"]',)
        problems = guard.check_pep_chem_chapter(_pep_map(labels, extra=extra))
        self.assertTrue(any("缺少节点" in item and "纯净物" in item for item in problems), problems)

    def test_style_class_and_click_text_do_not_count_as_nodes(self):
        labels = [name for name in guard.PEP_CHEM_BX1_CH1_REQUIRED if name not in ("纯净物", "混合物")]
        extra = (
            '  classDef deco fill:#E8F1FF,stroke:#3B6FB6,color:#1A1A1A',
            '  style deco["纯净物（概念）"] fill:#E8F1FF',
            '  class deco["纯净物（概念）"] concept',
            '  click deco["纯净物（概念）"] "https://example.invalid/node"',
        )
        problems = guard.check_pep_chem_chapter(_pep_map(labels, extra=extra))
        self.assertTrue(any("缺少节点" in item and "纯净物" in item for item in problems), problems)

    def test_edge_label_text_does_not_count_as_a_node(self):
        labels = [name for name in guard.PEP_CHEM_BX1_CH1_REQUIRED if name not in ("纯净物", "混合物")]
        extra = (
            '  src["离子方程式（概念）"] -->|["纯净物（概念）"]| dst["单质（概念）"]',
            "  src -- 纯净物 --> dst",
        )
        problems = guard.check_pep_chem_chapter(_pep_map(labels, extra=extra))
        self.assertTrue(any("缺少节点" in item and "纯净物" in item for item in problems), problems)

    def test_asymmetric_node_shape_counts_as_present(self):
        names = list(guard.PEP_CHEM_BX1_CH1_REQUIRED)
        lines = [
            "整章图：人教版《化学 必修 第一册》（2019）第一章",
            "```mermaid",
            "flowchart TD",
            "  classDef concept fill:#E8F1FF,stroke:#3B6FB6,color:#1A1A1A",
            "  classDef skill fill:#E7F6EE,stroke:#2E7D4F,color:#1A1A1A",
            '  n0>"纯净物（概念）"]:::concept',
        ]
        for index, name in enumerate(names[1:], 1):
            lines.append(f'  n{index}["{name}（概念）"]:::concept')
        lines.append("```")
        self.assertEqual(guard.check_pep_chem_chapter("\n".join(lines)), [])


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


if __name__ == "__main__":
    unittest.main()
