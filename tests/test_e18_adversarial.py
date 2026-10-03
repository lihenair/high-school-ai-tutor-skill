#!/usr/bin/env python3
"""E17a / E18 对抗集：逐条对照 tests/adversarial/e18_cases.jsonl。"""

import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
GUARD = ROOT / "skills" / "high-school-ai-tutor" / "scripts" / "guard.py"
CASES = ROOT / "tests" / "adversarial" / "e18_cases.jsonl"


def load_cases():
    rows = []
    for raw in CASES.read_text(encoding="utf-8").splitlines():
        if raw.strip():
            rows.append(json.loads(raw))
    return rows


class E18AdversarialTests(unittest.TestCase):
    def test_corpus_has_forty_three_cases(self):
        rows = load_cases()
        self.assertEqual(len(rows), 43)
        self.assertEqual(sum(1 for row in rows if row["expect"] == "block"), 28)
        self.assertEqual(sum(1 for row in rows if row["expect"] == "pass"), 15)

    def test_each_case_matches_expect(self):
        rows = load_cases()
        self.assertTrue(rows)
        with tempfile.TemporaryDirectory() as tmp:
            reply = Path(tmp) / "reply.txt"
            for case in rows:
                with self.subTest(case["id"]):
                    reply.write_text(case["input"] + "\n", encoding="utf-8")
                    result = subprocess.run(
                        [sys.executable, str(GUARD), "--mode", "study", str(reply)],
                        capture_output=True, text=True, encoding="utf-8",
                    )
                    crash = "Traceback" in result.stderr
                    self.assertFalse(crash, case["id"] + "\n" + result.stderr)
                    if case["expect"] == "block":
                        self.assertEqual(result.returncode, 1, case["id"] + "\n" + result.stdout)
                        if case.get("code"):
                            self.assertIn(
                                f"{case['code']} [ERROR]",
                                result.stdout,
                                case["id"] + "\n" + result.stdout,
                            )
                    else:
                        self.assertEqual(result.returncode, 0, case["id"] + "\n" + result.stdout)
                        self.assertNotIn("[ERROR]", result.stdout, case["id"] + "\n" + result.stdout)


if __name__ == "__main__":
    unittest.main()
