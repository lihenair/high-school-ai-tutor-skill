#!/usr/bin/env python3
"""check.py 咬合自测：每条钉子被拆掉时，必须因这一条失败，而不是静默放过。

每个用例复制整仓再变异，子进程跑副本里的 tests/check.py。
不改真实工作树，也不在同一目录里来回写 .pyc。
"""

import re
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SCRIPTS = ROOT / "skills" / "high-school-ai-tutor" / "scripts"
sys.path.insert(0, str(SCRIPTS))

import guard  # noqa: E402

SKILL_REL = Path("skills") / "high-school-ai-tutor" / "SKILL.md"
VERIFY_REL = Path("skills") / "high-school-ai-tutor" / "scripts" / "verify.py"
# 与 tests/check.py 同一条正则，flag 名从 guard.py 源头读，不在测试里另抄一份清单。
FLAG_RE = re.compile(r'add_argument\(\s*["\'](--[a-z0-9-]+)["\']')
SUBJECT_FLAG = "--subject"


def guard_flags():
    src = (SCRIPTS / "guard.py").read_text(encoding="utf-8")
    return sorted(set(FLAG_RE.findall(src)))


class CheckBiteTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.copy = Path(self.tmp.name) / "repo"
        shutil.copytree(
            ROOT,
            self.copy,
            ignore=shutil.ignore_patterns(".git", "__pycache__", "*.pyc", ".venv"),
        )

    def tearDown(self):
        self.tmp.cleanup()

    def run_check(self):
        return subprocess.run(
            [sys.executable, "tests/check.py"],
            cwd=self.copy,
            capture_output=True,
            text=True,
            encoding="utf-8",
        )

    def test_baseline_copy_passes(self):
        result = self.run_check()
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)

    def test_dropping_subject_flag_line_fails_on_that_flag(self):
        self.assertIn(SUBJECT_FLAG, guard_flags())
        skill = self.copy / SKILL_REL
        lines = skill.read_text(encoding="utf-8").splitlines(keepends=True)
        kept = [ln for ln in lines if not ("guard.py" in ln and SUBJECT_FLAG in ln)]
        self.assertLess(len(kept), len(lines))
        skill.write_text("".join(kept), encoding="utf-8")

        result = self.run_check()
        self.assertNotEqual(result.returncode, 0, result.stdout)
        self.assertIn(f"guard.py 用法未覆盖参数：{SUBJECT_FLAG}", result.stdout)

    def test_renamed_pass_status_fails_on_that_word(self):
        verify = self.copy / VERIFY_REL
        src = verify.read_text(encoding="utf-8")
        old, new = '"通过": 0', '"通过_X": 0'
        self.assertEqual(src.count(old), 1)
        verify.write_text(src.replace(old, new, 1), encoding="utf-8")

        result = self.run_check()
        self.assertNotEqual(result.returncode, 0, result.stdout)
        self.assertIn("缺少机验状态词：通过_X", result.stdout)

    def test_deleted_last_marker_fails_on_that_sentence(self):
        marker = guard.VERIFY_MARKERS[-1]
        skill = self.copy / SKILL_REL
        text = skill.read_text(encoding="utf-8")
        self.assertIn(marker, text)
        skill.write_text(text.replace(marker, ""), encoding="utf-8")

        result = self.run_check()
        self.assertNotEqual(result.returncode, 0, result.stdout)
        self.assertIn(f"缺少机验标记：{marker}", result.stdout)

    def test_dropping_study_dir_flag_fails_on_that_flag(self):
        self.assertIn("--dir", guard_flags())
        skill = self.copy / SKILL_REL
        lines = skill.read_text(encoding="utf-8").splitlines(keepends=True)
        kept = [ln for ln in lines if not ("guard.py" in ln and "--dir" in ln)]
        self.assertLess(len(kept), len(lines))
        skill.write_text("".join(kept), encoding="utf-8")

        result = self.run_check()
        self.assertNotEqual(result.returncode, 0, result.stdout)
        self.assertIn("guard.py 用法未覆盖参数：--dir", result.stdout)

    def test_reading_explore_log_from_records_fails_the_audit(self):
        records = self.copy / "skills" / "high-school-ai-tutor" / "scripts" / "records.py"
        records.write_text(records.read_text(encoding="utf-8") + "\nexplore_log = 'blocked'\n", encoding="utf-8")
        result = self.run_check()
        self.assertNotEqual(result.returncode, 0, result.stdout)
        self.assertIn("explore_log", result.stdout)


if __name__ == "__main__":
    unittest.main()
