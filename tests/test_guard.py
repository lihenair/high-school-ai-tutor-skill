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


def _complete_map(line_for):
    lines = [
        "整章图：人教版《化学 必修 第一册》（2019）第一章",
        "```mermaid",
        "flowchart TD",
        "  classDef concept fill:#E8F1FF,stroke:#3B6FB6,color:#1A1A1A",
        "  classDef skill fill:#E7F6EE,stroke:#2E7D4F,color:#1A1A1A",
    ]
    for index, name in enumerate(guard.PEP_CHEM_BX1_CH1_REQUIRED):
        lines.append(line_for(index, name))
    lines.append("```")
    return "\n".join(lines)


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
        self.assertEqual(guard.check_pep_chem_chapter(_complete_map(
            lambda i, name: f'  n{i}>"{name}（概念）"]:::concept'
        )), [])

    def test_every_flowchart_node_shape_counts_as_present(self):
        shapes = {
            "stadium": lambda i, name: f'  n{i}(["{name}（概念）"]):::concept',
            "subroutine": lambda i, name: f'  n{i}[["{name}（概念）"]]:::concept',
            "cylinder": lambda i, name: f'  n{i}[("{name}（概念）")]:::concept',
            "hexagon": lambda i, name: f'  n{i}{{{{"{name}（概念）"}}}}:::concept',
            "double_circle": lambda i, name: f'  n{i}((("{name}（概念）"))):::concept',
            "parallelogram": lambda i, name: f'  n{i}[/{name}（概念）/]:::concept',
            "inverse_parallelogram": lambda i, name: f"  n{i}[\\{name}（概念）\\]:::concept",
            "trapezoid": lambda i, name: f"  n{i}[/{name}（概念）\\]:::concept",
            "inverse_trapezoid": lambda i, name: f"  n{i}[\\{name}（概念）/]:::concept",
        }
        for shape_name, line_for in shapes.items():
            with self.subTest(shape=shape_name):
                self.assertEqual(guard.check_pep_chem_chapter(_complete_map(line_for)), [])

    def test_halfwidth_and_annotation_suffixes_are_stripped(self):
        self.assertEqual(guard.check_pep_chem_chapter(_complete_map(
            lambda i, name: f'  n{i}["{name}(概念)"]:::concept'
        )), [])
        self.assertEqual(guard.check_pep_chem_chapter(_complete_map(
            lambda i, name: f'  n{i}["{name}（注：课堂）"]:::concept'
        )), [])

    def test_backticks_html_and_emoji_are_normalized(self):
        self.assertEqual(guard.check_pep_chem_chapter(_complete_map(
            lambda i, name: f'  n{i}["`{name}`"]:::concept'
        )), [])
        self.assertEqual(guard.check_pep_chem_chapter(_complete_map(
            lambda i, name: f'  n{i}["<b>{name}</b>"]:::concept'
        )), [])
        self.assertEqual(guard.check_pep_chem_chapter(_complete_map(
            lambda i, name: f'  n{i}["{name}🔬"]:::concept'
        )), [])

    def test_dot_plus_br_and_newline_split_into_names(self):
        names = list(guard.PEP_CHEM_BX1_CH1_REQUIRED)
        rest = names[1:]
        splits = [
            f"{names[0]}·{names[1]}",
            f"{names[0]}+{names[1]}",
            f"{names[0]}・{names[1]}",
            f"{names[0]}＋{names[1]}",
            f"{names[0]}<br/>{names[1]}",
            f"{names[0]}\\n{names[1]}",
        ]
        for combined in splits:
            with self.subTest(combined=combined):
                labels = [combined, *rest[1:]]
                self.assertEqual(guard.check_pep_chem_chapter(_pep_map(labels)), [])

    def test_chinese_cjk_digit_and_hyphen_node_ids_count(self):
        cases = {
            "chinese": lambda i, name: f'  节点{i}["{name}（概念）"]:::concept',
            "cjk_digit": lambda i, name: f'  点{i}["{name}（概念）"]:::concept',
            "hyphen": lambda i, name: f'  mix-{i}["{name}（概念）"]:::concept',
        }
        for case_name, line_for in cases.items():
            with self.subTest(ids=case_name):
                self.assertEqual(guard.check_pep_chem_chapter(_complete_map(line_for)), [])

    def test_hyphenated_arrow_is_not_parsed_as_a_node_id(self):
        labels = [name for name in guard.PEP_CHEM_BX1_CH1_REQUIRED if name not in ("纯净物", "混合物")]
        extra = ('  src-->["纯净物（概念）"]',)
        problems = guard.check_pep_chem_chapter(_pep_map(labels, extra=extra))
        self.assertTrue(any("缺少节点" in item and "纯净物" in item for item in problems), problems)

    def test_borrowed_canon_title_does_not_satisfy_alias_required_name(self):
        labels = _required_labels_replacing("氧化物", "单质 / 化合物")
        problems = guard.check_pep_chem_chapter(_pep_map(labels))
        self.assertTrue(any("缺少节点" in item and "氧化物" in item for item in problems), problems)

    def test_tyndall_phenomenon_alias_satisfies_required_node(self):
        labels = _required_labels_replacing("丁达尔", "丁达尔现象")
        self.assertEqual(guard.check_pep_chem_chapter(_pep_map(labels)), [])


FULL_OK = (ROOT / "tests" / "guard-cases" / "full-ok.txt").read_text(encoding="utf-8")


def full_reply_with_score_line(score_line):
    """Inject a five-item score / weighted line into an otherwise valid full reply."""
    return FULL_OK.replace(
        "- 能力层级：掌握。\n",
        "- 能力层级：掌握。\n" + score_line + "\n",
        1,
    )


def e8_issues(issues):
    return [item for item in issues if item[1] == "E8"]


class StudyAndScoreTests(unittest.TestCase):
    def test_bom_does_not_hide_study_label(self):
        body = (ROOT / "tests" / "guard-cases" / "self-study" / "08-overview-ok.txt").read_text(encoding="utf-8")
        issues = guard.check_study("\ufeff" + body)
        self.assertFalse(any(item[0] == "ERROR" for item in issues), issues)

    def test_difficulty_in_body_does_not_skip_study_label(self):
        issues = guard.check_study("先看这章的难度：比上一章更综合。\n拓扑学习顺序：先分类。")
        self.assertTrue(any(item[1] == "E17a" for item in issues), issues)

    def test_scores_without_weighted_total_are_an_error(self):
        text = FULL_OK.replace("本题结论是 a≤1", "五项评分 4、3、2、2、3 分。本题结论是 a≤1")
        issues = guard.check("full", text, False)
        self.assertTrue(any(item[1] == "E8" for item in issues), issues)

    def test_later_equals_after_weighted_sentence_does_not_override(self):
        text = full_reply_with_score_line(
            "- 五项评分 4、3、2、2、3 分。加权总分 = 2.95。"
            "跟进：若把对称轴改成 x = 1，区间还单调吗？"
        )
        issues = guard.check("full", text, False)
        self.assertFalse(e8_issues(issues), issues)

    def test_later_equals_on_following_question_line_does_not_override(self):
        text = full_reply_with_score_line(
            "- 五项评分 4、3、2、2、3 分。加权分 = 2.95。\n"
            "- 追问：令 k = 0 时图像怎么变？"
        )
        issues = guard.check("full", text, False)
        self.assertFalse(e8_issues(issues), issues)

    def test_wrong_weighted_value_still_blocked_despite_later_equals(self):
        text = full_reply_with_score_line(
            "- 五项评分 4、3、2、2、3 分。加权 = 1.00。"
            "对照：展开里某一项写成 0.30×4 = 1.20，并不改总分。"
        )
        issues = guard.check("full", text, False)
        self.assertTrue(e8_issues(issues), issues)

    def test_multiline_equals_continuation_uses_final_value(self):
        text = full_reply_with_score_line(
            "- 五项评分 4、3、2、2、3 分。加权 =\n"
            "  = 0.30×4 + 0.25×3 + 0.20×2 + 0.15×2 + 0.10×3 =\n"
            "  = 1.20 + 0.75 + 0.40 + 0.30 + 0.30 =\n"
            "  = 2.95"
        )
        issues = guard.check("full", text, False)
        self.assertFalse(e8_issues(issues), issues)

    def test_multiline_equals_continuation_wrong_final_is_blocked(self):
        text = full_reply_with_score_line(
            "- 五项评分 4、3、2、2、3 分。加权 = 0.30×4 + 0.25×3 + 0.20×2 + 0.15×2 + 0.10×3 =\n"
            "  = 9.99"
        )
        issues = guard.check("full", text, False)
        self.assertTrue(e8_issues(issues), issues)

    def test_non_equals_following_line_is_not_a_chain(self):
        text = full_reply_with_score_line(
            "- 五项评分 4、3、2、2、3 分。加权 = 0.30×4 + 0.25×3 + 0.20×2 + 0.15×2 + 0.10×3\n"
            "合计 = 2.95，到这里才写出总数。"
        )
        issues = guard.check("full", text, False)
        self.assertTrue(e8_issues(issues), issues)

    def _e8(self, score_line):
        return e8_issues(guard.check("full", full_reply_with_score_line(score_line), False))

    def test_prose_weighted_mention_does_not_override_score(self):
        issues = self._e8(
            "- 五项评分 4、3、2、2、3 分。加权总分 = 2.95。\n"
            "- 加权后难度等级：3，只是档位不是总分。"
        )
        self.assertFalse(issues, issues)

    def test_wrong_then_recheck_line_still_blocks(self):
        issues = self._e8(
            "- 五项评分 4、3、2、2、3 分。加权 = 1.10。\n"
            "- 复核加权总分 = 2.95。"
        )
        self.assertTrue(issues, issues)

    def test_two_score_lines_any_wrong_blocks(self):
        issues = self._e8(
            "- 五项评分 4、3、2、2、3 分。加权分 = 2.95。\n"
            "- 加权得分 = 3.80。"
        )
        self.assertTrue(issues, issues)

    def test_whitespace_form_without_separator_passes(self):
        issues = self._e8("- 五项评分 4、3、2、2、3 分。加权 2.95")
        self.assertFalse(issues, issues)

    def test_whitespace_form_wrong_value_blocks(self):
        issues = self._e8("- 五项评分 4、3、2、2、3 分。加权总分 1.10")
        self.assertTrue(issues, issues)

    def test_approx_and_natural_multiline_chain_passes(self):
        issues = self._e8(
            "- 五项评分 4、3、2、2、3 分。加权 = 1.20 + 0.75 + 0.40 + 0.30 + 0.30\n"
            "  = 2.95"
        )
        self.assertFalse(issues, issues)
        issues = self._e8("- 五项评分 4、3、2、2、3 分。加权 ≈ 2.95")
        self.assertFalse(issues, issues)

    def test_approx_wrong_value_blocks(self):
        issues = self._e8("- 五项评分 4、3、2、2、3 分。加权 ≈ 3.10")
        self.assertTrue(issues, issues)

    def test_inconsistent_chain_blocks_even_if_final_matches(self):
        issues = self._e8("- 五项评分 4、3、2、2、3 分。加权 = 3.95 = 2.95")
        self.assertTrue(issues, issues)
        issues = self._e8("- 五项评分 4、3、2、2、3 分。加权 = 2.95 = 3.95")
        self.assertTrue(issues, issues)

    def test_out_of_five_suffix_is_not_the_value(self):
        for extra in (" / 5", "/5", "/5.00", "（满分 5）", "满分5"):
            issues = self._e8(f"- 五项评分 4、3、2、2、3 分。加权：2.95{extra}")
            self.assertFalse(issues, extra)

    def test_fraction_value_not_out_of_five(self):
        issues = self._e8("- 五项评分 4、3、2、2、3 分。加权 = 59/20")
        self.assertFalse(issues, issues)
        issues = self._e8("- 五项评分 4、3、2、2、3 分。加权 = 21/20")
        self.assertTrue(issues, issues)

    def test_fullwidth_and_chinese_value_forms(self):
        issues = self._e8("- 五项评分 4、3、2、2、3 分。加权 = ２．９５")
        self.assertFalse(issues, issues)
        issues = self._e8("- 五项评分 4、3、2、2、3 分。加权 = 两点九五")
        self.assertFalse(issues, issues)
        issues = self._e8("- 五项评分 4、3、2、2、3 分。加权 = ３．１０")
        self.assertTrue(issues, issues)

    def test_slash_and_xiang_subscore_formats_are_checked(self):
        ok = self._e8("- 各项：4、3、2、2、3。加权 = 2.95")
        self.assertFalse(ok, ok)
        bad = self._e8("- 各项：4、3、2、2、3。加权 = 1.00")
        self.assertTrue(bad, bad)
        expect_350 = round(5 * 0.30 + 4 * 0.25 + 3 * 0.20 + 2 * 0.15 + 1 * 0.10, 2)
        self.assertEqual(expect_350, 3.50)
        slash_ok = self._e8("- 评分 5/4/3/2/1。加权 = 3.50")
        self.assertFalse(slash_ok, slash_ok)
        slash_bad = self._e8("- 评分 5/4/3/2/1。加权 = 2.95")
        self.assertTrue(slash_bad, slash_bad)

    def test_clause_boundary_stops_same_line_equation(self):
        issues = self._e8("- 五项评分 4、3、2、2、3 分。加权 = 2.95，若 a = 1")
        self.assertFalse(issues, issues)
        issues = self._e8("- 五项评分 4、3、2、2、3 分。加权 = 2.95；参考 x=2")
        self.assertFalse(issues, issues)
        issues = self._e8("- 五项评分 4、3、2、2、3 分。加权 = 1.00，若 a = 2.95")
        self.assertTrue(issues, issues)

    def test_modifiers_between_keyword_and_value(self):
        for line in (
            "- 五项评分 4、3、2、2、3 分。加权后为 2.95",
            "- 五项评分 4、3、2、2、3 分。加权结果：2.95",
            "- 五项评分 4、3、2、2、3 分。加权约 2.95",
            "- 五项评分 4、3、2、2、3 分。加权得分是 2.95",
            "- 五项评分 4、3、2、2、3 分。加权（满分 5）：2.95",
        ):
            issues = self._e8(line)
            self.assertFalse(issues, line)
        issues = self._e8("- 五项评分 4、3、2、2、3 分。加权后为 1.00")
        self.assertTrue(issues, issues)

    def test_approx_rounding_of_exact_is_not_compared(self):
        issues = self._e8("- 五项评分 4、3、2、2、3 分。加权 = 2.95 ≈ 3")
        self.assertFalse(issues, issues)
        issues = self._e8("- 五项评分 4、3、2、2、3 分。加权 = 2.95 ≈ 3.0")
        self.assertFalse(issues, issues)
        issues = self._e8("- 五项评分 4、3、2、2、3 分。加权 = 2.95 ≈ 4")
        self.assertTrue(issues, issues)

    def test_weight_percent_line_is_not_a_score(self):
        issues = self._e8(
            "- 五项评分 4、3、2、2、3 分。加权总分 = 2.95。\n"
            "- 加权是 30%/25%/20%/15%/10%。"
        )
        self.assertFalse(issues, issues)
        issues = self._e8("- 五项评分 4、3、2、2、3 分。加权是 30%/25%/20%/15%/10%。")
        self.assertTrue(issues, issues)

    def test_legend_slash_is_not_subscores_item_over_five_is(self):
        issues = self._e8(
            "- 评分标准：5/4/3/2/1 分锚点。五项评分 4、3、2、2、3 分。加权 = 2.95"
        )
        self.assertFalse(issues, issues)
        issues = self._e8(
            "- 评分标准：5/4/3/2/1 分锚点。五项评分 4、3、2、2、3 分。加权 = 1.00"
        )
        self.assertTrue(issues, issues)
        issues = self._e8(
            "- 知识点层级 4/5、思维跨度 3/5、综合程度 2/5、计算复杂度 2/5、出现频率 3/5。"
            "加权 = 2.95"
        )
        self.assertFalse(issues, issues)
        issues = self._e8(
            "- 知识点层级 4/5、思维跨度 3/5、综合程度 2/5、计算复杂度 2/5、出现频率 3/5。"
            "加权 = 1.00"
        )
        self.assertTrue(issues, issues)

    def test_multiple_question_score_groups_are_paired(self):
        text = full_reply_with_score_line(
            "- 第一问：4、3、2、2、3 分。加权 = 2.95\n"
            "- 第二问：5、4、3、2、1 分。加权 = 3.50"
        )
        issues = e8_issues(guard.check("full", text, False))
        self.assertFalse(issues, issues)
        text = full_reply_with_score_line(
            "- 第一问：4、3、2、2、3 分。加权 = 1.00\n"
            "- 第二问：5、4、3、2、1 分。加权 = 3.50"
        )
        issues = e8_issues(guard.check("full", text, False))
        self.assertTrue(issues, issues)
        text = full_reply_with_score_line(
            "- 第一问：4、3、2、2、3 分。加权 = 2.95\n"
            "- 第二问：5、4、3、2、1 分。加权 = 1.00"
        )
        issues = e8_issues(guard.check("full", text, False))
        self.assertTrue(issues, issues)

    def test_open_equals_line_then_expansion_then_total(self):
        issues = self._e8(
            "- 五项评分 4、3、2、2、3 分。加权 =\n"
            "0.30×4 + 0.25×3 + 0.20×2 + 0.15×2 + 0.10×3\n"
            "= 2.95"
        )
        self.assertFalse(issues, issues)
        issues = self._e8(
            "- 五项评分 4、3、2、2、3 分。加权 =\n"
            "0.30×4 + 0.25×3 + 0.20×2 + 0.15×2 + 0.10×3\n"
            "= 9.99"
        )
        self.assertTrue(issues, issues)

    def test_scientific_and_n_over_five_greater_than_five(self):
        issues = self._e8("- 五项评分 4、3、2、2、3 分。加权 = .295e1")
        self.assertFalse(issues, issues)
        issues = self._e8("- 五项评分 4、3、2、2、3 分。加权 = .3e1")
        self.assertTrue(issues, issues)
        issues = self._e8("- 各项：1、1、2、1、1。加权 = 6/5")
        self.assertFalse(issues, issues)
        issues = self._e8("- 各项：1、1、2、1、1。加权 = 2.95/5")
        self.assertTrue(issues, issues)


if __name__ == "__main__":
    unittest.main()
