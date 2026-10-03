"""E11/E12 adversarial cases from tests/adversarial/e12_cases.jsonl."""

import json
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SCRIPTS = ROOT / "skills" / "high-school-ai-tutor" / "scripts"
sys.path.insert(0, str(SCRIPTS))

import guard

CASES_PATH = ROOT / "tests" / "adversarial" / "e12_cases.jsonl"
WATCH_CODES = {"E11", "E12", "E13"}


def _load_cases():
    cases = []
    with CASES_PATH.open(encoding="utf-8") as fh:
        for line in fh:
            line = line.strip()
            if line:
                cases.append(json.loads(line))
    return cases


def _error_codes(text):
    return {item[1] for item in guard.check("socratic", text, False) if item[0] == "ERROR"}


class E12AdversarialTests(unittest.TestCase):
    def test_jsonl_has_forty_cases(self):
        cases = _load_cases()
        self.assertEqual(len(cases), 40)
        self.assertEqual(sum(1 for case in cases if case["expect"] == "block"), 28)
        self.assertEqual(sum(1 for case in cases if case["expect"] == "pass"), 12)

    def test_each_case_matches_expect(self):
        for case in _load_cases():
            with self.subTest(id=case["id"], why=case["why"]):
                codes = _error_codes(case["input"])
                watched = codes & WATCH_CODES
                if case["expect"] == "block":
                    self.assertIn(
                        case["code"],
                        codes,
                        f"{case['id']} should emit {case['code']}, got {sorted(codes)}",
                    )
                else:
                    self.assertFalse(
                        watched,
                        f"{case['id']} should pass E11/E12/E13, got {sorted(watched)}",
                    )


if __name__ == "__main__":
    unittest.main()
