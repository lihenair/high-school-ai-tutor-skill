#!/usr/bin/env python3
"""自学守卫：16 条用例按编号对退出码和违规号。"""

import subprocess
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
GUARD = ROOT / "skills" / "high-school-ai-tutor" / "scripts" / "guard.py"
CASES = ROOT / "tests" / "guard-cases" / "self-study"

EXPECT = {
    "01-missing-label.txt": (1, ["E17a"]),
    "02-bad-state.txt": (1, ["E17b"]),
    "03-unknown-node.txt": (1, ["E17c"]),
    "04-uncovered-chapter.txt": (0, ["E17c"]),
    "05-node-mermaid.txt": (1, ["R1a"]),
    "06-end-mermaid.txt": (1, ["R1a"]),
    "07-overview-no-map.txt": (0, ["R1b"]),
    "08-overview-ok.txt": (0, []),
    "09-selftest-marked.txt": (0, []),
    "10-selftest-unmarked.txt": (1, ["R3"]),
    "11-example-without-marker.txt": (0, []),
    "12-notebook-extension.txt": (1, ["R2"]),
    "13-diagnosis-ask.txt": (0, []),
    "14-diagnosis-judge.txt": (0, []),
    "15-repair-step.txt": (0, []),
    "16-solve-unlabeled.txt": (0, []),
}


class StudyGuardTests(unittest.TestCase):
    def test_each_case_matches_the_checklist(self):
        self.assertEqual(sorted(EXPECT), sorted(path.name for path in CASES.glob("*.txt")))
        for name, (code, needles) in EXPECT.items():
            result = subprocess.run(
                [sys.executable, str(GUARD), "--mode", "study", str(CASES / name)],
                capture_output=True, text=True, encoding="utf-8",
            )
            self.assertEqual(result.returncode, code, name + "\n" + result.stdout + result.stderr)
            for needle in needles:
                self.assertIn(needle, result.stdout, name + "\n" + result.stdout)
            if code == 1:
                self.assertIn("修复：", result.stdout, name)
            if not needles:
                self.assertNotIn("[ERROR]", result.stdout, name + "\n" + result.stdout)

    def test_directory_mode_fails_when_any_case_is_an_error(self):
        result = subprocess.run(
            [sys.executable, str(GUARD), "--mode", "study", "--dir", str(CASES)],
            capture_output=True, text=True, encoding="utf-8",
        )
        self.assertEqual(result.returncode, 1, result.stdout)
        self.assertIn("E17a", result.stdout)

    def test_chapter_one_pages_have_no_study_errors(self):
        folder = ROOT / "skills" / "high-school-ai-tutor" / "references" / "study-pages" / "chem-bx1-ch1"
        for path in sorted(folder.glob("*.md")):
            result = subprocess.run(
                [sys.executable, str(GUARD), "--mode", "study", str(path)],
                capture_output=True, text=True, encoding="utf-8",
            )
            self.assertEqual(result.returncode, 0, path.name + "\n" + result.stdout + result.stderr)
            self.assertNotIn("[ERROR]", result.stdout, path.name + "\n" + result.stdout)


if __name__ == "__main__":
    unittest.main()
