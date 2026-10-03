#!/usr/bin/env python3
"""E8 加权少见写法对抗集：把完整模式模板的评分行换成 jsonl 用例，只断言 E8。"""

import json
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SCRIPTS = ROOT / "skills" / "high-school-ai-tutor" / "scripts"
sys.path.insert(0, str(SCRIPTS))

import guard  # noqa: E402

CASES = ROOT / "tests" / "adversarial" / "e8_cases.jsonl"
TEMPLATE = (ROOT / "tests" / "adversarial" / "e8_full_template.txt").read_text(encoding="utf-8")
ANCHOR = "- 评分：4、3、2、2、3 分，加权 2.95"
REF_DIR = ROOT / "skills" / "high-school-ai-tutor" / "references"


def _load_cases():
    rows = []
    for raw in CASES.read_text(encoding="utf-8").splitlines():
        if raw.strip():
            rows.append(json.loads(raw))
    return rows


def _e8(text):
    return [item for item in guard.check("full", text, False) if item[1] == "E8"]


class DimensionTableTests(unittest.TestCase):
    def test_reference_tables_match_runtime_constants(self):
        loaded = guard.load_dimension_tables(REF_DIR)
        self.assertEqual(loaded, guard.DIMENSION_TABLES)
        self.assertEqual(len(loaded), 7)
        names = [frozenset(t) for t in loaded]
        self.assertEqual(len(names), len(set(names)), "五维表不能同名")
        math = next(t for t in loaded if "知识点层级" in t)
        bio = next(t for t in loaded if "概念层级" in t)
        self.assertEqual(math["综合程度"], 0.20)
        self.assertEqual(bio["综合程度"], 0.25)
        for table in loaded:
            self.assertEqual(len(table), 5)
            self.assertAlmostEqual(sum(table.values()), 1.0, places=6)


class E8AdversarialCorpusTests(unittest.TestCase):
    def test_template_contains_anchor(self):
        self.assertIn(ANCHOR, TEMPLATE)

    def test_corpus_size(self):
        rows = _load_cases()
        self.assertEqual(len(rows), 47)
        self.assertEqual(sum(1 for r in rows if r["expect"] == "block"), 22)
        self.assertEqual(sum(1 for r in rows if r["expect"] == "pass"), 25)

    def test_each_case_e8_only(self):
        self.assertIn(ANCHOR, TEMPLATE)
        for case in _load_cases():
            with self.subTest(id=case["id"], why=case["why"]):
                text = TEMPLATE.replace(ANCHOR, case["line"], 1)
                issues = _e8(text)
                if case["expect"] == "block":
                    self.assertTrue(issues, f"{case['id']} 应拦 E8：{case['why']}")
                else:
                    self.assertFalse(issues, f"{case['id']} 不应拦 E8：{case['why']} {issues}")


if __name__ == "__main__":
    unittest.main()
