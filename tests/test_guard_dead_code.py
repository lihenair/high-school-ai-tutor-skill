"""guard.py 顶层死代码对抗：跑 tests/adversarial/guard_dead_code.py。"""

import subprocess
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SCRIPT = ROOT / "tests" / "adversarial" / "guard_dead_code.py"


class GuardDeadCodeTests(unittest.TestCase):
    def test_guard_dead_code_ok(self):
        proc = subprocess.run(
            [sys.executable, str(SCRIPT), str(ROOT)],
            capture_output=True,
            text=True,
            check=False,
        )
        self.assertNotIn("Traceback", proc.stderr)
        self.assertEqual(proc.stdout.strip(), "OK", proc.stdout + proc.stderr)
        self.assertEqual(proc.returncode, 0, proc.stdout + proc.stderr)


if __name__ == "__main__":
    unittest.main()
