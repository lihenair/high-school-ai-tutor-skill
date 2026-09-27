#!/usr/bin/env python3
"""正典生成的种子行、整章图骨架必须和仓库里的文件一致。"""

import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "skills" / "high-school-ai-tutor" / "scripts"))

import canon_sync  # noqa: E402


class CanonSyncTests(unittest.TestCase):
    def test_repo_matches_canon(self):
        problems = canon_sync.audit()
        self.assertEqual(problems, [], "\n".join(problems))

    def test_seed_diff_reports_both_sides(self):
        expected = [("kp_a", "生物", "甲", "bio-bx1-ch1", 0)]
        actual = [("kp_b", "生物", "乙", "bio-bx1-ch1", 0)]
        missing, extra = canon_sync.diff_rows(expected, actual)
        self.assertEqual(missing, expected)
        self.assertEqual(extra, actual)

    def test_mermaid_skeleton_ignores_later_nodes(self):
        text = """
        subgraph ch["第一章"]
          kp_a["甲（概念）"]:::concept
          kp_b["乙（技能）"]:::skill
        end
        kp_a -->|同章衔接| kp_b
        kp_b -.->|常考组合| kp_c["丙"]:::later
        """
        owned, later = canon_sync.skeleton_from_mermaid(text)
        self.assertEqual(owned, {"kp_a": "甲", "kp_b": "乙"})
        self.assertEqual(later, {"kp_c": "丙"})

    def test_pipeline_requires_subject_prefix(self):
        rows, problems = canon_sync.load_pipeline()
        self.assertTrue(rows)
        self.assertEqual(problems, [])
        for _node_id, subject, _display, chapter, grey in rows:
            prefix = canon_sync.SUBJECT_PREFIX[subject]
            self.assertTrue(chapter.startswith(prefix + "-"), chapter)
            self.assertEqual(grey, 0)
            self.assertFalse(chapter.startswith("xbx"))


if __name__ == "__main__":
    unittest.main()
