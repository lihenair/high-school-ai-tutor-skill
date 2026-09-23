#!/usr/bin/env python3
"""错题本主库。同一题只留一行，复习间隔用 SM-2。只使用标准库。

默认数据库：~/.high-school-ai-tutor/tutor.db

    python3 notebook.py add entry.json
    python3 notebook.py review --id 1 --result 已掌握
    python3 notebook.py due
    python3 notebook.py export -o 错题本.xlsx
"""

import argparse
import json
import sqlite3
import sys
from datetime import date, datetime, timedelta
from pathlib import Path

import nodes

ERROR_CATEGORIES = ("审题", "概念", "计算", "方法", "表达", "心态")
MASTERY_STATES = ("未掌握", "模糊", "已掌握")
QUALITY = {"未掌握": 2, "模糊": 3, "已掌握": 5}

ENTRY_COLUMNS = {
    "年级": "grade",
    "科目": "subject",
    "教材版本": "textbook",
    "章节/知识点": "node",
    "题目摘要": "stem",
    "我的错误": "my_error",
    "错因分类": "error_type",
    "错因细化": "error_detail",
    "正确思路": "correct_approach",
    "关键步骤": "key_steps",
    "易错点提醒": "pitfall",
    "变式题": "variant",
    "变式答案": "variant_answer",
    "备注": "note",
}


class NotebookError(ValueError):
    pass


def default_path():
    return Path.home() / ".high-school-ai-tutor" / "tutor.db"


def sm2(ease, interval, reps, quality):
    """经典 SM-2。quality 0–5，3 分及以上算记住。间隔先用旧难度系数，再更新系数。"""
    ease = float(ease)
    interval = int(interval)
    reps = int(reps)
    if quality >= 3:
        if reps == 0:
            interval = 1
        elif reps == 1:
            interval = 6
        else:
            interval = int(round(interval * ease))
        reps += 1
    else:
        reps = 0
        interval = 1
    ease = ease + (0.1 - (5 - quality) * (0.08 + (5 - quality) * 0.02))
    if ease < 1.3:
        ease = 1.3
    return round(ease, 2), interval, reps


def add_entry(path, entry, when=None):
    if not isinstance(entry, dict):
        raise NotebookError("条目应为一个对象")
    unknown = [key for key in entry if key not in ENTRY_COLUMNS and key not in ("日期", "编号", "掌握标记", "复习次数")]
    if unknown:
        raise NotebookError("未知字段：" + "、".join(unknown))
    subject = str(entry.get("科目") or "").strip()
    stem = str(entry.get("题目摘要") or "").strip()
    if not subject or not stem:
        raise NotebookError("科目和题目摘要都要有")
    error_type = str(entry.get("错因分类") or "").strip()
    if error_type and error_type not in ERROR_CATEGORIES:
        raise NotebookError("错因分类只能是审题、概念、计算、方法、表达、心态")
    mastery = str(entry.get("掌握标记") or "").strip()
    if mastery and mastery not in MASTERY_STATES:
        raise NotebookError("掌握标记只能是未掌握、模糊、已掌握")
    raw_node = str(entry.get("章节/知识点") or "").strip()
    canon_subject, canon_node, raw_node, hit = nodes.normalize(subject, raw_node)
    if hit:
        subject, node = canon_subject, canon_node
    else:
        node = raw_node
        nodes.warn_miss(subject, raw_node)
    created = _parse_day(entry.get("日期") or when or date.today().isoformat())
    conn = _connect(path)
    try:
        row = conn.execute(
            "SELECT * FROM cards WHERE subject = ? AND node = ? AND stem = ?",
            (subject, node, stem),
        ).fetchone()
        if row is None:
            due = (created + timedelta(days=1)).isoformat()
            columns = {
                "created": created.isoformat(),
                "subject": subject,
                "node": node,
                "raw_node": raw_node,
                "verify_status": "",
                "stem": stem,
                "mastery": mastery or "未掌握",
                "ease": 2.5,
                "interval_days": 1,
                "reps": 0,
                "due": due,
            }
            for key, column in ENTRY_COLUMNS.items():
                if key in entry and key not in ("科目", "章节/知识点", "题目摘要"):
                    columns[column] = str(entry[key])
            if error_type:
                columns["error_type"] = error_type
            names = ", ".join(columns)
            marks = ", ".join("?" for _ in columns)
            cur = conn.execute(
                f"INSERT INTO cards ({names}) VALUES ({marks})",
                tuple(columns.values()),
            )
            conn.commit()
            return _card(conn, cur.lastrowid)
        updates = {}
        for key, column in ENTRY_COLUMNS.items():
            if key in entry and key not in ("科目", "章节/知识点", "题目摘要"):
                updates[column] = str(entry[key])
        if error_type:
            updates["error_type"] = error_type
        if mastery:
            reviewed = _apply_review(dict(row), mastery, created)
            updates.update(reviewed)
        if "章节/知识点" in entry:
            updates["node"] = node
            updates["raw_node"] = raw_node
        if updates:
            sets = ", ".join(f"{name} = ?" for name in updates)
            conn.execute(
                f"UPDATE cards SET {sets} WHERE id = ?",
                (*updates.values(), row["id"]),
            )
            conn.commit()
        return _card(conn, row["id"])
    finally:
        conn.close()


def review(path, card_id, result, when=None):
    if result not in QUALITY:
        raise NotebookError("复习结果只能是未掌握、模糊、已掌握")
    day = _parse_day(when or date.today().isoformat())
    conn = _connect(path)
    try:
        row = conn.execute("SELECT * FROM cards WHERE id = ?", (card_id,)).fetchone()
        if row is None:
            raise NotebookError(f"没有编号 {card_id}")
        updates = _apply_review(dict(row), result, day)
        sets = ", ".join(f"{name} = ?" for name in updates)
        conn.execute(f"UPDATE cards SET {sets} WHERE id = ?", (*updates.values(), card_id))
        conn.commit()
        return _card(conn, card_id)
    finally:
        conn.close()


def list_cards(path):
    conn = _connect(path)
    try:
        rows = conn.execute("SELECT * FROM cards ORDER BY id").fetchall()
        return [_public(row) for row in rows]
    finally:
        conn.close()


def due_cards(path, when=None):
    day = _parse_day(when or date.today().isoformat()).isoformat()
    conn = _connect(path)
    try:
        rows = conn.execute(
            "SELECT * FROM cards WHERE due <= ? ORDER BY due, id",
            (day,),
        ).fetchall()
        return [_public(row) for row in rows]
    finally:
        conn.close()


def format_due(cards):
    if not cards:
        return "今天没有到期的错题。"
    lines = ["到期复习"]
    for index, card in enumerate(cards, 1):
        node = card["node"] or "未标考点"
        lines.append(f"{index}. {card['subject']} · {node}：{card['stem']}（下次 {card['due']}）")
    return "\n".join(lines)


def _apply_review(row, result, day):
    ease, interval, reps = sm2(row["ease"], row["interval_days"], row["reps"], QUALITY[result])
    return {
        "ease": ease,
        "interval_days": interval,
        "reps": reps,
        "due": (day + timedelta(days=interval)).isoformat(),
        "mastery": result,
        "last_review": day.isoformat(),
    }


def _card(conn, card_id):
    row = conn.execute("SELECT * FROM cards WHERE id = ?", (card_id,)).fetchone()
    return _public(row)


def _public(row):
    card = dict(row)
    card["ease"] = round(float(card["ease"]), 2)
    card["interval_days"] = int(card["interval_days"])
    card["reps"] = int(card["reps"])
    return card


def _parse_day(value):
    try:
        return datetime.strptime(str(value), "%Y-%m-%d").date()
    except ValueError as exc:
        raise NotebookError("日期格式应为 YYYY-MM-DD") from exc


def _connect(path):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(path)
    conn.row_factory = sqlite3.Row
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS cards (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            created TEXT NOT NULL,
            grade TEXT DEFAULT '',
            subject TEXT NOT NULL,
            textbook TEXT DEFAULT '',
            node TEXT DEFAULT '',
            raw_node TEXT DEFAULT '',
            verify_status TEXT DEFAULT '',
            stem TEXT NOT NULL,
            my_error TEXT DEFAULT '',
            error_type TEXT DEFAULT '',
            error_detail TEXT DEFAULT '',
            correct_approach TEXT DEFAULT '',
            key_steps TEXT DEFAULT '',
            pitfall TEXT DEFAULT '',
            variant TEXT DEFAULT '',
            variant_answer TEXT DEFAULT '',
            mastery TEXT NOT NULL,
            ease REAL NOT NULL,
            interval_days INTEGER NOT NULL,
            reps INTEGER NOT NULL,
            due TEXT NOT NULL,
            last_review TEXT DEFAULT '',
            note TEXT DEFAULT '',
            UNIQUE (subject, node, stem)
        )
        """
    )
    columns = {row[1] for row in conn.execute("PRAGMA table_info(cards)")}
    if "raw_node" not in columns:
        conn.execute("ALTER TABLE cards ADD COLUMN raw_node TEXT DEFAULT ''")
    if "verify_status" not in columns:
        conn.execute("ALTER TABLE cards ADD COLUMN verify_status TEXT DEFAULT ''")
    return conn


def main(argv=None):
    parser = argparse.ArgumentParser(description="错题本 SQLite 与 SM-2")
    sub = parser.add_subparsers(dest="cmd", required=True)
    shared = argparse.ArgumentParser(add_help=False)
    shared.add_argument("--db", type=Path, default=None)

    add = sub.add_parser("add", parents=[shared])
    add.add_argument("entry")

    review_cmd = sub.add_parser("review", parents=[shared])
    review_cmd.add_argument("--id", type=int, required=True)
    review_cmd.add_argument("--result", required=True)
    review_cmd.add_argument("--date", default=None)

    due = sub.add_parser("due", parents=[shared])
    due.add_argument("--date", default=None)

    export_cmd = sub.add_parser("export", parents=[shared])
    export_cmd.add_argument("-o", "--output", default="错题本.xlsx")

    args = parser.parse_args(argv)
    path = args.db or default_path()
    try:
        if args.cmd == "add":
            if args.entry == "-":
                entry = json.load(sys.stdin)
            else:
                with open(args.entry, encoding="utf-8") as fh:
                    entry = json.load(fh)
            card = add_entry(path, entry)
            print(f"已记下错题 {card['id']}：{card['subject']} · {card['node'] or '未标考点'}，下次复习 {card['due']}")
        elif args.cmd == "review":
            card = review(path, args.id, args.result, args.date)
            print(f"已更新错题 {card['id']}：{card['mastery']}，下次复习 {card['due']}，间隔 {card['interval_days']} 天")
        elif args.cmd == "due":
            print(format_due(due_cards(path, args.date)))
        else:
            _export(path, args.output)
            print(f"已导出：{args.output}")
    except NotebookError as exc:
        print(str(exc), file=sys.stderr)
        return 2
    return 0


def _export(path, output):
    import importlib.util

    gen_path = Path(__file__).resolve().parent.parent / "templates" / "wrong-notebook-generator.py"
    spec = importlib.util.spec_from_file_location("wrong_notebook_generator", gen_path)
    gen = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(gen)
    gen.workbook_from_cards(list_cards(path)).save(output)


if __name__ == "__main__":
    sys.exit(main())
