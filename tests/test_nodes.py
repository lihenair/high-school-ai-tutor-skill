#!/usr/bin/env python3
"""节点正典：科目封闭枚举，别名收成标准名。"""

import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "skills" / "high-school-ai-tutor" / "scripts"))

import nodes  # noqa: E402


class NodeTests(unittest.TestCase):
    def test_subjects_match_files_and_catalog_has_no_problems(self):
        self.assertEqual(
            [filename for _subject, filename in nodes.SUBJECT_FILES],
            ["math.md", "physics.md", "chemistry.md", "biology.md", "chinese.md", "english.md", "history.md", "politics.md", "geography.md"],
        )
        self.assertEqual(nodes.audit(), [])

    def test_alias_hits_standard_name_and_keeps_original(self):
        subject, node, raw, hit = nodes.normalize("数学", "必修一 函数单调性")
        self.assertEqual((subject, node, raw, hit), ("数学", "函数单调性", "必修一 函数单调性", True))
        subject, node, raw, hit = nodes.normalize(" 数学 ", "函数单调性")
        self.assertEqual((subject, node, hit), ("数学", "函数单调性", True))

    def test_unknown_subject_or_node_misses(self):
        self.assertFalse(nodes.normalize("体育", "函数单调性")[3])
        subject, node, raw, hit = nodes.normalize("化学", "电石除杂")
        self.assertEqual((subject, node, raw, hit), ("化学", "电石除杂", "电石除杂", False))

    def test_empty_node_with_known_subject_is_a_hit(self):
        self.assertEqual(nodes.normalize("数学", "  ")[3], True)
        self.assertEqual(nodes.normalize("数学", "")[1], "")

    def test_suggestion_picks_the_longest_contained_standard_name(self):
        self.assertEqual(nodes.suggest("数学", "第三章 函数单调性"), "函数单调性")
        self.assertEqual(nodes.suggest("化学", "完全没见过的考点"), "")

    def test_duplicate_alias_is_reported(self):
        entries = [
            ("函数单调性", ["单调性"], "函数"),
            ("单调区间", ["单调性"], "函数"),
        ]
        problems = nodes.collision_problems("数学", entries)
        self.assertEqual(problems, ["正典别名重复：数学 · 单调性"])

    def test_bad_line_is_a_format_error(self):
        _entries, problems = nodes.parse_lines("math.md", "只有两段 | 没有章\n")
        self.assertEqual(problems, ["正典格式错误：math.md:1"])


if __name__ == "__main__":
    unittest.main()
