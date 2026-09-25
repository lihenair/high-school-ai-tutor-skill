#!/usr/bin/env python3
"""画像、开场五场景、掌握度迁移表。"""

import io
import json
import contextlib
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "skills" / "high-school-ai-tutor" / "scripts"))

import notebook  # noqa: E402
import profile as student_profile  # noqa: E402
import routing  # noqa: E402


class ProfileTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.path = Path(self.tmp.name) / "student_profile.json"
        self.records = Path(self.tmp.name) / "records.jsonl"
        self.db = Path(self.tmp.name) / "tutor.db"

    def tearDown(self):
        self.tmp.cleanup()

    def test_skip_writes_default_and_missing_confirmed_reads_as_true(self):
        self.assertTrue(student_profile.needs_onboarding(None))
        created = student_profile.create_from_answers({"grade": "高二", "exam_type": "跳过"})
        self.assertEqual(created["grade"], {"value": "高二", "confirmed": True})
        self.assertFalse(created["exam_type"]["confirmed"])
        self.assertEqual(created["exam_type"]["value"], "高考")
        self.assertFalse(created["textbook_version"]["confirmed"])
        self.assertIn("不得作为页码", created["textbook_version"]["note"])
        self.assertFalse(student_profile.needs_onboarding(created))
        created["grade"].pop("confirmed")
        self.assertTrue(student_profile._field_confirmed(created["grade"]))

    def test_opening_five_scenes_and_resume_question(self):
        onboarded = student_profile.create_from_answers({"grade": "高一", "exam_type": "高考", "textbook_version": "人教版"})
        student_profile.set_progress(onboarded, "chem-bx1-ch1", "kp_electrolyte")
        scenes = [
            (onboarded, "学第三章", "study_chapter", False),
            (onboarded, "题目：已知 2 mol 氢气完全燃烧", "solve", True),
            (onboarded, "继续", "resume", False),
            (None, "自学：第三章", "onboard", False),
            (None, "题目：已知氧气的物质的量", "solve", False),
        ]
        for profile, text, action, ask in scenes:
            got = routing.route_opening(profile, text, student_profile.needs_onboarding(profile))
            self.assertEqual(got["action"], action, text)
            self.assertEqual(got["ask_resume"], ask, text)
        interrupted = routing.route_opening(
            onboarded, "题目：已知氯化钠溶液导电", student_profile.needs_onboarding(onboarded),
        )
        self.assertEqual(interrupted["sentence"], "回到 电解质与电离 节点吗")
        self.assertEqual(routing.resume_prompt("氧化还原反应"), "回到 氧化还原反应 节点吗")

    def test_mastery_table_and_diagnosis_does_not_create(self):
        profile = student_profile.create_from_answers({})
        student_profile.mastery_apply(profile, "kp_redox", "解题错题", "解题", "2026-09-26")
        self.assertIsNone(student_profile.mastery_get(profile, "kp_redox"))

        student_profile.mastery_apply(profile, "kp_redox", "自测答错", "自测", "2026-09-26")
        self.assertEqual(student_profile.mastery_get(profile, "kp_redox"), "未掌握")
        frozen = json.dumps(profile["mastery"]["kp_redox"], ensure_ascii=False)
        student_profile.mastery_apply(profile, "kp_redox", "解题错题", "解题", "2026-09-27")
        self.assertEqual(json.dumps(profile["mastery"]["kp_redox"], ensure_ascii=False), frozen)

        student_profile.mastery_apply(profile, "kp_redox", "自测首次答对", "自测", "2026-09-26")
        self.assertEqual(student_profile.mastery_get(profile, "kp_redox"), "模糊")
        student_profile.mastery_apply(profile, "kp_redox", "连续两次答对", "自测", "2026-09-26")
        self.assertEqual(student_profile.mastery_get(profile, "kp_redox"), "已掌握")

        student_profile.mastery_apply(profile, "kp_redox", "解题错题", "解题", "2026-09-26")
        self.assertEqual(student_profile.mastery_get(profile, "kp_redox"), "模糊")
        student_profile.mastery_apply(profile, "kp_redox", "解题错题", "解题", "2026-09-26")
        self.assertEqual(student_profile.mastery_get(profile, "kp_redox"), "未掌握")

        buf = io.StringIO()
        with contextlib.redirect_stderr(buf):
            student_profile.mastery_apply(profile, "kp_ion_eq", "诊断答错", "诊断", "2026-09-26")
        self.assertIsNone(student_profile.mastery_get(profile, "kp_ion_eq"))
        self.assertIn("不创建不迁移", buf.getvalue())
        with contextlib.redirect_stderr(io.StringIO()):
            student_profile.mastery_apply(profile, "kp_redox", "诊断答对", "诊断", "2026-09-26")
        self.assertEqual(student_profile.mastery_get(profile, "kp_redox"), "未掌握")

    def test_question_flow_keeps_diagnosis_out_of_the_notebook(self):
        profile = student_profile.create_from_answers({})
        student_profile.apply_question_result(
            profile, "诊断题", "化学", "kp_redox", "诊断快诊", "做错", "概念",
            self.records, self.db, "2026-09-26",
        )
        row = json.loads(self.records.read_text(encoding="utf-8").strip())
        self.assertEqual(row["context"], "自学诊断")
        self.assertEqual(row["node_id"], "kp_redox")
        self.assertFalse(self.db.exists())
        self.assertIsNone(student_profile.mastery_get(profile, "kp_redox"))

        student_profile.apply_question_result(
            profile, "自测题", "化学", "kp_redox", "自测谁是氧化剂", "做错", "概念",
            self.records, self.db, "2026-09-26",
        )
        self.assertTrue(self.db.exists())
        self.assertEqual(student_profile.mastery_get(profile, "kp_redox"), "未掌握")
        listed = notebook.due_cards(self.db, "2026-09-27")
        self.assertTrue(any("氧化剂" in item["stem"] for item in listed))

        before = self.records.read_text(encoding="utf-8")
        student_profile.apply_question_result(
            profile, "例题", "化学", "kp_redox", "例题不入库", "做错", "概念",
            self.records, self.db, "2026-09-26",
        )
        self.assertEqual(self.records.read_text(encoding="utf-8"), before)

    def test_textbook_change_lists_nodes_and_blocks_until_confirmed(self):
        profile = student_profile.create_from_answers({"textbook_version": "人教版"})
        student_profile.set_progress(profile, "chem-bx1-ch1", "kp_redox")
        profile["mastery"]["kp_missing"] = {"state": "模糊", "since": "2026-09-26", "last_source": "自测"}
        lines = student_profile.validate_textbook_change(profile, "苏教版")
        text = "\n".join(lines)
        self.assertIn("确认前不自学相关章", text)
        self.assertIn("kp_redox", text)
        self.assertIn("失联节点：kp_missing", text)
        self.assertEqual(profile["textbook_version"]["value"], "人教版")
        self.assertEqual(profile["pending_textbook"], "苏教版")
        student_profile.confirm_textbook_change(profile)
        self.assertEqual(profile["textbook_version"]["value"], "苏教版")
        self.assertNotIn("pending_textbook", profile)

    def test_same_turn_cannot_teach_a_node_and_solve_a_new_problem(self):
        got = routing.route_turn("节点", "讲这个节点。题目：已知氢气的物质的量")
        self.assertEqual(got["sentence"], "节点讲解请单独发一次")
        repair = routing.route_turn("节点", "再试一次", wrong_streak=2)
        self.assertEqual(repair["action"], "repair")
        self.assertEqual(repair["label"], "节点")

    def test_round_trip_save(self):
        profile = student_profile.create_from_answers({"grade": "高一"})
        student_profile.save(profile, self.path)
        loaded = student_profile.load(self.path)
        self.assertEqual(loaded["grade"]["value"], "高一")


if __name__ == "__main__":
    unittest.main()
