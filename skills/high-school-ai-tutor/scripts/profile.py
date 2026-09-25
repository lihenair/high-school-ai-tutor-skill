#!/usr/bin/env python3
"""学生画像。只使用标准库。默认文件在家目录，不进仓库。

    python3 profile.py show --file ~/.high-school-ai-tutor/student_profile.json
    python3 profile.py onboard --grade 高一 --exam 高考 --textbook 人教版 --file ~/.high-school-ai-tutor/student_profile.json
    python3 profile.py progress --chapter chem-bx1-ch1 --node kp_electrolyte --file ~/.high-school-ai-tutor/student_profile.json
    python3 profile.py mastery --node kp_redox --event 自测首次答对 --source 自测 --file ~/.high-school-ai-tutor/student_profile.json
    python3 profile.py validate-textbook --version 苏教版 --file ~/.high-school-ai-tutor/student_profile.json
"""

import argparse
import json
import sys
from datetime import date
from pathlib import Path

_SCRIPTS = Path(__file__).resolve().parent
if str(_SCRIPTS) not in sys.path:
    sys.path.insert(0, str(_SCRIPTS))
import nodes
import records
import notebook

DEFAULTS = {
    "grade": "高一",
    "exam_type": "高考",
    "textbook_version": "人教版",
}
TEXTBOOK_NOTE = "跳过默认值，可补问一次；仅用于对齐正典章节命名与顺序，不得作为页码/原文引用/任何 source 类字段的依据"
SOURCES = ("自测", "解题", "诊断")
STATES = ("未掌握", "模糊", "已掌握")
EVENTS = ("自测首次答对", "连续两次答对", "自测答错", "解题错题", "诊断答对", "诊断答错")

QUESTION_FLOW = {
    "例题": {"records": False, "notebook": False, "mastery": False, "context": ""},
    "诊断题": {"records": True, "notebook": False, "mastery": False, "context": "自学诊断"},
    "自测题": {"records": True, "notebook": True, "mastery": True, "context": "自学自测"},
}


class ProfileError(ValueError):
    pass


def default_path():
    return Path.home() / ".high-school-ai-tutor" / "student_profile.json"


def load(path=None):
    path = Path(path) if path else default_path()
    if not path.exists():
        return None
    return json.loads(path.read_text(encoding="utf-8"))


def save(profile, path=None):
    path = Path(path) if path else default_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(profile, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return path


def _field_confirmed(field):
    if not isinstance(field, dict) or "value" not in field:
        return False
    if "confirmed" not in field:
        return True
    return bool(field["confirmed"])


def needs_onboarding(profile):
    """没有画像，或年级、考试类型、教材版本三个值都空。"""
    if not profile:
        return True
    present = 0
    for key in DEFAULTS:
        field = profile.get(key)
        if isinstance(field, dict) and str(field.get("value") or "").strip():
            present += 1
    return present == 0


def _answer_field(raw, default, note=None):
    text = str(raw or "").strip()
    skipped = text in ("", "跳过", "不知道", "先不说")
    field = {"value": default if skipped else text, "confirmed": not skipped}
    if note and skipped:
        field["note"] = note
    return field


def create_from_answers(answers, when=None):
    answers = answers or {}
    profile = {
        "grade": _answer_field(answers.get("grade"), DEFAULTS["grade"]),
        "exam_type": _answer_field(answers.get("exam_type"), DEFAULTS["exam_type"]),
        "textbook_version": _answer_field(
            answers.get("textbook_version"), DEFAULTS["textbook_version"], TEXTBOOK_NOTE,
        ),
        "self_study_progress": {
            "current_chapter": "",
            "current_node": "",
            "completed_nodes": [],
            "last_session": when or date.today().isoformat(),
        },
        "mastery": {},
    }
    return profile


def get_progress(profile):
    progress = (profile or {}).get("self_study_progress") or {}
    chapter = progress.get("current_chapter") or ""
    node = progress.get("current_node") or None
    if node == "":
        node = None
    return chapter, node


def set_progress(profile, chapter_id, node_id, when=None):
    progress = profile.setdefault("self_study_progress", {})
    progress["current_chapter"] = chapter_id or ""
    progress["current_node"] = node_id or ""
    progress.setdefault("completed_nodes", [])
    progress["last_session"] = when or date.today().isoformat()
    return profile


def mastery_get(profile, node_id):
    entry = ((profile or {}).get("mastery") or {}).get(node_id)
    if not entry:
        return None
    return entry.get("state")


def _audit(message):
    print(message, file=sys.stderr)


def mastery_apply(profile, node_id, event, source, when=None):
    """按迁移表改一条掌握度。诊断只打审计日志。解题不创建新条目。"""
    if event not in EVENTS:
        raise ProfileError("未知掌握度事件")
    if source not in SOURCES:
        raise ProfileError("掌握度来源只能是自测、解题或诊断")
    node_id = str(node_id or "").strip()
    if not node_id:
        raise ProfileError("节点 ID 不能为空")
    mastery = profile.setdefault("mastery", {})
    current = mastery.get(node_id)
    when = when or date.today().isoformat()

    if source == "诊断" or event in ("诊断答对", "诊断答错"):
        _audit(f"AUDIT 诊断不创建不迁移：{node_id} {event}")
        return profile

    if event == "解题错题":
        if current is None:
            _audit(f"AUDIT 解题错题不创建：{node_id}")
            return profile
        state = current.get("state")
        if state == "未掌握":
            return profile
        nxt = "模糊" if state == "已掌握" else "未掌握"
        current["state"] = nxt
        current["since"] = when
        current["last_source"] = "解题"
        current["correct_streak"] = 0
        return profile

    if event == "自测首次答对":
        state = current.get("state") if current else "未掌握"
        if state != "未掌握":
            _audit(f"AUDIT 自测首次答对前提不符：{node_id} {state}")
            return profile
        mastery[node_id] = {"state": "模糊", "since": when, "last_source": "自测", "correct_streak": 1}
        return profile

    if event == "连续两次答对":
        if current is None or current.get("state") != "模糊":
            _audit(f"AUDIT 连续两次答对前提不符：{node_id}")
            return profile
        current["state"] = "已掌握"
        current["since"] = when
        current["last_source"] = "自测"
        current["correct_streak"] = 2
        return profile

    if event == "自测答错":
        if current is None:
            mastery[node_id] = {"state": "未掌握", "since": when, "last_source": "自测", "correct_streak": 0}
            return profile
        current["state"] = "未掌握"
        current["since"] = when
        current["last_source"] = "自测"
        current["correct_streak"] = 0
        return profile

    return profile


def self_test_event(profile, node_id, correct):
    """给自测结果选迁移表里的事件名。答错清零；连续第二次答对才升到已掌握。"""
    entry = ((profile or {}).get("mastery") or {}).get(node_id) or {}
    if not correct:
        return "自测答错"
    streak = int(entry.get("correct_streak") or 0)
    state = entry.get("state")
    if state == "模糊" and streak >= 1:
        return "连续两次答对"
    return "自测首次答对"


def validate_textbook_change(profile, new_version):
    """列出要人工确认的节点。确认前写入 pending_textbook，不改已确认的版本。"""
    new_version = str(new_version or "").strip()
    if not new_version:
        raise ProfileError("新教材版本不能为空")
    current = ((profile or {}).get("textbook_version") or {}).get("value") or ""
    if new_version == current and not profile.get("pending_textbook"):
        return []
    profile["pending_textbook"] = new_version
    lines = [f"确认前不自学相关章。待确认版本：{new_version}（当前：{current or '未填'}）"]
    seen = []
    progress = profile.get("self_study_progress") or {}
    for node_id in [progress.get("current_node"), *(progress.get("completed_nodes") or [])]:
        if node_id and node_id not in seen:
            seen.append(node_id)
    for node_id in (profile.get("mastery") or {}):
        if node_id not in seen:
            seen.append(node_id)
    if not seen:
        lines.append("画像里还没有节点。确认版本后从章览重新开始。")
        return lines
    for node_id in seen:
        display = nodes.display_for_id(node_id)
        if not display:
            lines.append(f"失联节点：{node_id}。正典没有这个 ID，确认前不要自学相关章。")
            continue
        _subject, standard, _raw, hit = nodes.normalize("化学", display)
        if not hit:
            for subject in nodes.SUBJECTS:
                _subject, standard, _raw, hit = nodes.normalize(subject, display)
                if hit:
                    break
        if not hit:
            lines.append(f"命名错位：{node_id} → {display}。正典对不上，确认前不要自学相关章。")
        else:
            lines.append(f"待确认：{node_id} → {standard}。换版本后核对章节命名，确认前不要自学相关章。")
    return lines


def confirm_textbook_change(profile):
    pending = str((profile or {}).get("pending_textbook") or "").strip()
    if not pending:
        raise ProfileError("没有待确认的教材版本")
    field = profile.setdefault("textbook_version", {})
    field["value"] = pending
    field["confirmed"] = True
    field.pop("note", None)
    profile.pop("pending_textbook", None)
    return profile


def apply_question_result(profile, kind, subject, node_id, stem, outcome, error="", records_path=None, notebook_path=None, when=None):
    """按题型矩阵写记录、错题本和掌握度。诊断错题不进错题本。"""
    if kind not in QUESTION_FLOW:
        raise ProfileError("题型只能是例题、诊断题或自测题")
    flow = QUESTION_FLOW[kind]
    display = nodes.display_for_id(node_id) or node_id
    if flow["records"]:
        records.add_record(
            records_path or records.default_path(),
            subject, display, stem, outcome, error, when,
            context=flow["context"], node_id=node_id,
        )
    if flow["notebook"] and outcome == "做错":
        notebook.add_entry(
            notebook_path or notebook.default_path(),
            {"科目": subject, "题目摘要": stem, "章节/知识点": display, "错因分类": error or "概念", "掌握标记": "未掌握"},
            when=when,
        )
    if flow["mastery"]:
        correct = outcome == "做对"
        event = self_test_event(profile, node_id, correct)
        mastery_apply(profile, node_id, event, "自测", when)
    elif kind == "诊断题":
        mastery_apply(profile, node_id, "诊断答对" if outcome == "做对" else "诊断答错", "诊断", when)
    return profile


def _skip_flag(args, name):
    return bool(getattr(args, name))


def main(argv=None):
    parser = argparse.ArgumentParser(description="学生画像与掌握度")
    shared = argparse.ArgumentParser(add_help=False)
    shared.add_argument("--file", type=Path, default=None)
    sub = parser.add_subparsers(dest="cmd", required=True)

    sub.add_parser("show", parents=[shared])

    onboard = sub.add_parser("onboard", parents=[shared])
    onboard.add_argument("--grade", default="")
    onboard.add_argument("--exam", default="")
    onboard.add_argument("--textbook", default="")
    onboard.add_argument("--skip-grade", action="store_true")
    onboard.add_argument("--skip-exam", action="store_true")
    onboard.add_argument("--skip-textbook", action="store_true")

    progress = sub.add_parser("progress", parents=[shared])
    progress.add_argument("--chapter", default="")
    progress.add_argument("--node", default="")

    mastery = sub.add_parser("mastery", parents=[shared])
    mastery.add_argument("--node", required=True)
    mastery.add_argument("--event", default="")
    mastery.add_argument("--source", default="")

    textbook = sub.add_parser("validate-textbook", parents=[shared])
    textbook.add_argument("--version", required=True)

    args = parser.parse_args(argv)
    path = args.file or default_path()
    try:
        if args.cmd == "show":
            profile = load(path)
            if profile is None:
                print("还没有学生画像。")
                return 0
            print(json.dumps(profile, ensure_ascii=False, indent=2))
            return 0
        if args.cmd == "onboard":
            answers = {
                "grade": "" if _skip_flag(args, "skip_grade") else args.grade,
                "exam_type": "" if _skip_flag(args, "skip_exam") else args.exam,
                "textbook_version": "" if _skip_flag(args, "skip_textbook") else args.textbook,
            }
            profile = create_from_answers(answers)
            save(profile, path)
            print(f"已写入画像：{path}")
            return 0
        profile = load(path) or create_from_answers({})
        if args.cmd == "progress":
            if args.chapter or args.node:
                set_progress(profile, args.chapter, args.node)
                save(profile, path)
            chapter, node = get_progress(profile)
            print(f"{chapter} {node or ''}".strip())
            return 0
        if args.cmd == "mastery":
            if args.event:
                mastery_apply(profile, args.node, args.event, args.source or "自测")
                save(profile, path)
            state = mastery_get(profile, args.node)
            print(state or "无")
            return 0
        lines = validate_textbook_change(profile, args.version)
        save(profile, path)
        print("\n".join(lines))
        return 0
    except (ProfileError, records.RecordError, notebook.NotebookError) as exc:
        print(str(exc), file=sys.stderr)
        return 2


if __name__ == "__main__":
    sys.exit(main())
