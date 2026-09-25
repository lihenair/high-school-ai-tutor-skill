#!/usr/bin/env python3
"""化学必修一第一章：拓扑、直接前置、章末灰节点。"""

import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "skills" / "high-school-ai-tutor" / "scripts"))

import graph  # noqa: E402


class GraphTests(unittest.TestCase):
    def test_ion_equation_comes_after_its_prerequisite(self):
        order = [node_id for node_id, _name in graph.topo_order("chem-bx1-ch1")]
        self.assertIn("kp_electrolyte", order)
        self.assertLess(order.index("kp_electrolyte"), order.index("kp_ion_eq"))
        self.assertEqual(graph.prereq("kp_ion_eq"), ["kp_electrolyte"])

    def test_grey_preview_is_a_text_list_without_assets(self):
        items = graph.grey_nodes("chem-bx1-ch1")
        names = [item["display_name"] for item in items]
        self.assertIn("第二章 钠和氯", names)
        self.assertTrue(all(item["asset"] is False for item in items))
        text = graph.format_grey(items)
        self.assertIn("下一章：", text)
        self.assertIn("- ", text)
        self.assertNotIn("```", text)


if __name__ == "__main__":
    unittest.main()
