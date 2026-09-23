#!/usr/bin/env python3
"""判题记录：一题一条，下次按考点汇总薄弱点。"""

import json
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "skills" / "high-school-ai-tutor" / "scripts"))

import records  # noqa: E402


class RecordTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.path = Path(self.tmp.name) / "records.jsonl"

    def tearDown(self):
        self.tmp.cleanup()

    def test_add_one_judged_problem_and_rank_weak_node(self):
        records.add_record(
            self.path,
            subject="化学",
            node="氧化还原反应",
            stem="电石除杂",
            outcome="做错",
            error="概念",
            when="2026-09-23",
        )
        records.add_record(
            self.path,
            subject="化学",
            node="离子反应",
            stem="离子方程式",
            outcome="做对",
            when="2026-09-23",
        )
        lines = self.path.read_text(encoding="utf-8").strip().splitlines()
        self.assertEqual(len(lines), 2)
        first = json.loads(lines[0])
        self.assertEqual(first["outcome"], "做错")
        self.assertNotIn("解析", first["stem"])
        weak = records.weak_points(self.path)
        self.assertEqual(weak[0]["node"], "氧化还原反应")
        self.assertEqual(weak[0]["wrong"], 1)
        text = records.format_weak(weak)
        self.assertIn("化学 · 氧化还原反应：做错 1，跳过 0，做对 0", text)

    def test_later_correct_answer_removes_node_from_weak_list(self):
        records.add_record(
            self.path, subject="化学", node="氧化还原反应", stem="电石除杂",
            outcome="做错", error="概念", when="2026-09-23",
        )
        records.add_record(
            self.path, subject="化学", node="氧化还原反应", stem="电子转移",
            outcome="做对", when="2026-09-24",
        )
        self.assertEqual(records.weak_points(self.path), [])
        self.assertEqual(records.format_weak([]), "目前没有薄弱点。")

    def test_empty_file_says_nothing_judged(self):
        self.assertEqual(records.format_weak(records.weak_points(self.path)), "还没有判过的题。")

    def test_skip_counts_as_weak_and_micro_step_is_not_a_second_record_type(self):
        records.add_record(
            self.path, subject="数学", node="函数单调性", stem="求参数",
            outcome="跳过", when="2026-09-23",
        )
        weak = records.weak_points(self.path)
        self.assertEqual(weak[0]["skipped"], 1)
        with self.assertRaises(records.RecordError):
            records.add_record(
                self.path, subject="数学", node="函数单调性", stem="求参数",
                outcome="小步答错", when="2026-09-23",
            )

    def test_wrong_without_error_category_is_rejected(self):
        with self.assertRaises(records.RecordError):
            records.add_record(
                self.path, subject="化学", node="氧化还原反应", stem="电石除杂",
                outcome="做错", when="2026-09-23",
            )

    def test_stem_does_not_keep_the_solution(self):
        saved = records.add_record(
            self.path, subject="化学", node="氧化还原反应",
            stem="电石除杂。答案是 C。配平 11PH3",
            outcome="做错", error="概念", when="2026-09-23",
        )
        self.assertNotIn("答案", saved["stem"])
        self.assertLessEqual(len(saved["stem"]), 40)


if __name__ == "__main__":
    unittest.main()
