#!/usr/bin/env python3
"""错题本：同一题改一行，复习间隔按 SM-2 伸缩。"""

import contextlib
import io
import sqlite3
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "skills" / "high-school-ai-tutor" / "scripts"))

import notebook  # noqa: E402


class NotebookTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.db = Path(self.tmp.name) / "tutor.db"

    def tearDown(self):
        self.tmp.cleanup()

    def test_new_card_is_one_row_due_tomorrow(self):
        card = notebook.add_entry(self.db, {
            "日期": "2026-09-23",
            "科目": "数学",
            "章节/知识点": "函数单调性",
            "题目摘要": "求参数 a",
            "错因分类": "概念",
            "掌握标记": "未掌握",
        })
        self.assertEqual(card["due"], "2026-09-24")
        self.assertEqual(card["ease"], 2.5)
        self.assertEqual(card["interval_days"], 1)
        self.assertEqual(card["reps"], 0)
        again = notebook.add_entry(self.db, {
            "日期": "2026-09-23",
            "科目": "数学",
            "章节/知识点": "函数单调性",
            "题目摘要": "求参数 a",
            "我的错误": "把中点当边界",
        })
        self.assertEqual(again["id"], card["id"])
        self.assertEqual(len(notebook.list_cards(self.db)), 1)
        self.assertEqual(again["my_error"], "把中点当边界")
        self.assertEqual(again["due"], "2026-09-24")

    def test_failed_review_resets_interval_and_lowers_ease(self):
        notebook.add_entry(self.db, {
            "日期": "2026-09-23",
            "科目": "化学",
            "章节/知识点": "氧化还原反应",
            "题目摘要": "电石除杂",
        })
        card = notebook.review(self.db, 1, "未掌握", when="2026-09-24")
        self.assertEqual(card["reps"], 0)
        self.assertEqual(card["interval_days"], 1)
        self.assertEqual(card["due"], "2026-09-25")
        self.assertEqual(card["ease"], 2.18)

    def test_successful_reviews_follow_sm2_intervals(self):
        notebook.add_entry(self.db, {
            "日期": "2026-09-23",
            "科目": "数学",
            "章节/知识点": "函数单调性",
            "题目摘要": "求参数 a",
        })
        first = notebook.review(self.db, 1, "已掌握", when="2026-09-24")
        self.assertEqual((first["reps"], first["interval_days"], first["due"], first["ease"]), (1, 1, "2026-09-25", 2.6))
        second = notebook.review(self.db, 1, "已掌握", when="2026-09-25")
        self.assertEqual((second["reps"], second["interval_days"], second["due"], second["ease"]), (2, 6, "2026-10-01", 2.7))
        third = notebook.review(self.db, 1, "已掌握", when="2026-10-01")
        self.assertEqual(third["reps"], 3)
        self.assertEqual(third["interval_days"], 16)
        self.assertEqual(third["due"], "2026-10-17")
        self.assertEqual(third["ease"], 2.8)

    def test_due_lists_only_cards_whose_date_has_arrived(self):
        notebook.add_entry(self.db, {
            "日期": "2026-09-23",
            "科目": "数学",
            "章节/知识点": "函数单调性",
            "题目摘要": "求参数 a",
        })
        self.assertEqual(notebook.due_cards(self.db, "2026-09-23"), [])
        due = notebook.due_cards(self.db, "2026-09-24")
        self.assertEqual(len(due), 1)
        self.assertIn("函数单调性", notebook.format_due(due))

    def test_readd_with_same_mastery_still_advances_schedule(self):
        notebook.add_entry(self.db, {
            "日期": "2026-09-23",
            "科目": "数学",
            "章节/知识点": "函数单调性",
            "题目摘要": "求参数 a",
            "掌握标记": "模糊",
        })
        again = notebook.add_entry(self.db, {
            "日期": "2026-09-24",
            "科目": "数学",
            "章节/知识点": "函数单调性",
            "题目摘要": "求参数 a",
            "掌握标记": "模糊",
        })
        self.assertEqual(again["mastery"], "模糊")
        self.assertEqual(again["reps"], 1)
        self.assertEqual(again["interval_days"], 1)
        self.assertEqual(again["due"], "2026-09-25")
        self.assertEqual(again["ease"], 2.36)

    def test_fuzzy_review_counts_as_pass_and_drops_ease(self):
        notebook.add_entry(self.db, {
            "日期": "2026-09-23",
            "科目": "数学",
            "章节/知识点": "函数单调性",
            "题目摘要": "求参数 a",
        })
        card = notebook.review(self.db, 1, "模糊", when="2026-09-24")
        self.assertEqual(card["reps"], 1)
        self.assertEqual(card["interval_days"], 1)
        self.assertEqual(card["ease"], 2.36)

    def test_alias_collapses_to_one_card_and_keeps_raw_node(self):
        card = notebook.add_entry(self.db, {
            "日期": "2026-09-23",
            "科目": "数学",
            "章节/知识点": "必修一 函数单调性",
            "题目摘要": "求参数 a",
        })
        self.assertEqual(card["node"], "函数单调性")
        self.assertEqual(card["raw_node"], "必修一 函数单调性")
        self.assertEqual(card["verify_status"], "")
        again = notebook.add_entry(self.db, {
            "日期": "2026-09-24",
            "科目": "数学",
            "章节/知识点": "函数单调性",
            "题目摘要": "求参数 a",
        })
        self.assertEqual(again["id"], card["id"])
        self.assertEqual(len(notebook.list_cards(self.db)), 1)

    def test_unknown_node_warns_and_keeps_the_original(self):
        err = io.StringIO()
        with contextlib.redirect_stderr(err):
            card = notebook.add_entry(self.db, {
                "日期": "2026-09-23",
                "科目": "化学",
                "章节/知识点": "电石除杂",
                "题目摘要": "除杂试剂",
            })
        self.assertEqual(card["node"], "电石除杂")
        self.assertEqual(card["raw_node"], "电石除杂")
        self.assertIn("WARN 未命中节点正典：化学 · 电石除杂", err.getvalue())

    def test_existing_database_gains_reserved_columns(self):
        conn = sqlite3.connect(self.db)
        conn.execute(
            """
            CREATE TABLE cards (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                created TEXT NOT NULL,
                grade TEXT DEFAULT '',
                subject TEXT NOT NULL,
                textbook TEXT DEFAULT '',
                node TEXT DEFAULT '',
                stem TEXT NOT NULL,
                my_error TEXT DEFAULT '',
                error_type TEXT DEFAULT '',
                error_detail TEXT DEFAULT '',
                correct_approach TEXT DEFAULT '',
                key_steps TEXT DEFAULT '',
                pitfall TEXT DEFAULT '',
                variant TEXT DEFAULT '',
                variant_answer TEXT DEFAULT '',
                mastery TEXT NOT NULL,
                ease REAL NOT NULL,
                interval_days INTEGER NOT NULL,
                reps INTEGER NOT NULL,
                due TEXT NOT NULL,
                last_review TEXT DEFAULT '',
                note TEXT DEFAULT ''
            )
            """
        )
        conn.commit()
        conn.close()
        card = notebook.add_entry(self.db, {
            "日期": "2026-09-23",
            "科目": "数学",
            "章节/知识点": "函数单调性",
            "题目摘要": "求参数 a",
        })
        self.assertEqual(card["verify_status"], "")
        self.assertEqual(card["raw_node"], "函数单调性")


if __name__ == "__main__":
    unittest.main()
