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
import os
import sqlite3
import sys
import tempfile
from datetime import date, datetime, timedelta
from pathlib import Path

# 错题本生成器按文件路径加载本模块，sys.path 里没有 scripts/，要先补上才能找到 nodes。
_SCRIPTS = Path(__file__).resolve().parent
if str(_SCRIPTS) not in sys.path:
    sys.path.insert(0, str(_SCRIPTS))
import nodes

ERROR_CATEGORIES = ("审题", "概念", "计算", "方法", "表达", "心态")
MASTERY_STATES = ("未掌握", "模糊", "已掌握")
QUALITY = {"未掌握": 2, "模糊": 3, "已掌握": 5}
SCHEMA_VERSION = 1
REQUIRED_CARD_COLUMNS = ("due", "ease", "interval_days", "reps", "subject", "stem", "mastery")
BUSY_TIMEOUT = 1.0

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


class NotebookUnavailable(Exception):
    """错题本库不可用，命令行退出码 3。"""


class NotebookRowError(NotebookUnavailable):
    """库能打开，但有行数据非法。due 仍可带上合法到期行。"""

    def __init__(self, message, cards=None, bad_ids=None):
        super().__init__(message)
        self.cards = list(cards or [])
        self.bad_ids = list(bad_ids or [])


class MissingDependency(Exception):
    """缺第三方库，命令行退出码 4。"""


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
    conn = _connect(path, writable=True, create=True)
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
    except sqlite3.Error as exc:
        conn.rollback()
        raise _sqlite_to_unavailable(path, exc) from exc
    finally:
        conn.close()


def review(path, card_id, result, when=None):
    if result not in QUALITY:
        raise NotebookError("复习结果只能是未掌握、模糊、已掌握")
    day = _parse_day(when or date.today().isoformat())
    conn = _connect(path, writable=True, create=False)
    try:
        row = conn.execute("SELECT * FROM cards WHERE id = ?", (card_id,)).fetchone()
        if row is None:
            raise NotebookError(f"没有编号 {card_id}")
        updates = _apply_review(dict(row), result, day)
        sets = ", ".join(f"{name} = ?" for name in updates)
        conn.execute(f"UPDATE cards SET {sets} WHERE id = ?", (*updates.values(), card_id))
        conn.commit()
        return _card(conn, card_id)
    except sqlite3.Error as exc:
        conn.rollback()
        raise _sqlite_to_unavailable(path, exc) from exc
    finally:
        conn.close()


def list_cards(path):
    cards, bad_ids = _read_cards(path)
    if bad_ids:
        raise NotebookRowError(_bad_rows_message(path, bad_ids), cards=[], bad_ids=bad_ids)
    return cards


def due_cards(path, when=None):
    day = _parse_day(when or date.today().isoformat()).isoformat()
    cards, bad_ids = _read_cards(path)
    due = [card for card in cards if card["due"] <= day]
    if bad_ids:
        raise NotebookRowError(_bad_rows_message(path, bad_ids), cards=due, bad_ids=bad_ids)
    return due


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
    card.setdefault("raw_node", "")
    card.setdefault("verify_status", "")
    card["ease"] = round(float(card["ease"]), 2)
    card["interval_days"] = int(card["interval_days"])
    card["reps"] = int(card["reps"])
    return card


def _parse_day(value):
    try:
        return datetime.strptime(str(value), "%Y-%m-%d").date()
    except ValueError as exc:
        raise NotebookError("日期格式应为 YYYY-MM-DD") from exc


def _hint(path):
    return (
        f"错题本文件：{path}\n"
        "请先备份这个文件，再确认路径是否选对；本命令不会删除或重建错题本。"
    )


def _sqlite_to_unavailable(path, exc):
    text = str(exc).lower()
    if "locked" in text or "busy" in text:
        return NotebookUnavailable(
            f"错题本正被占用，暂时打不开。\n{_hint(path)}"
        )
    if "readonly" in text or "read-only" in text or "permission" in text:
        return NotebookUnavailable(
            f"错题本文件无法写入（只读或没有权限）。\n{_hint(path)}"
        )
    if "malformed" in text or "not a database" in text or "file is not a database" in text:
        return NotebookUnavailable(
            f"错题本文件已损坏或不是 SQLite 数据库。\n{_hint(path)}"
        )
    return NotebookUnavailable(
        f"错题本数据库不可用：{exc}\n{_hint(path)}"
    )


def _path_kind(path):
    path = Path(path)
    if path.is_dir():
        raise NotebookUnavailable(
            f"错题本路径是一个目录，不是数据库文件。\n{_hint(path)}"
        )
    if not path.exists():
        return "missing"
    try:
        size = path.stat().st_size
    except OSError as exc:
        raise NotebookUnavailable(
            f"没有权限读取错题本文件。\n{_hint(path)}"
        ) from exc
    if size == 0:
        return "empty"
    return "file"


def _open_sqlite(path, *, readonly):
    path = Path(path)
    try:
        if readonly:
            uri = path.resolve().as_uri() + "?mode=ro"
            conn = sqlite3.connect(uri, uri=True, timeout=BUSY_TIMEOUT)
            conn.execute("PRAGMA query_only = ON")
        else:
            conn = sqlite3.connect(str(path), timeout=BUSY_TIMEOUT)
    except sqlite3.Error as exc:
        raise _sqlite_to_unavailable(path, exc) from exc
    except OSError as exc:
        raise NotebookUnavailable(
            f"无法打开错题本文件。\n{_hint(path)}"
        ) from exc
    conn.row_factory = sqlite3.Row
    return conn


def _quick_check(conn, path):
    try:
        rows = conn.execute("PRAGMA quick_check").fetchall()
    except sqlite3.Error as exc:
        raise _sqlite_to_unavailable(path, exc) from exc
    if not rows or str(rows[0][0]).lower() != "ok":
        detail = "；".join(str(row[0]) for row in rows[:5])
        raise NotebookUnavailable(
            f"错题本文件页损坏（{detail}）。\n{_hint(path)}"
        )


def _table_names(conn):
    return {
        row[0]
        for row in conn.execute("SELECT name FROM sqlite_master WHERE type='table'")
    }


def _schema_version(conn, path):
    tables = _table_names(conn)
    if "meta" not in tables:
        return 0
    try:
        row = conn.execute("SELECT value FROM meta WHERE key = 'schema_version'").fetchone()
    except sqlite3.Error as exc:
        raise _sqlite_to_unavailable(path, exc) from exc
    if row is None:
        return 0
    raw = row[0]
    try:
        if isinstance(raw, bool) or raw is None:
            raise ValueError
        version = int(str(raw).strip())
        if str(version) != str(raw).strip():
            raise ValueError
    except (TypeError, ValueError) as exc:
        raise NotebookUnavailable(
            f"错题本 schema_version 不是整数（当前值：{raw!r}），版本不兼容。\n{_hint(path)}"
        ) from exc
    if version < 0:
        raise NotebookUnavailable(
            f"错题本 schema_version 为负数（{version}），版本不兼容。\n{_hint(path)}"
        )
    if version > SCHEMA_VERSION:
        raise NotebookUnavailable(
            f"错题本 schema_version 为 {version}，高于当前脚本支持的 {SCHEMA_VERSION}。\n{_hint(path)}"
        )
    return version


def _inspect_schema(conn, path):
    tables = _table_names(conn)
    if "cards" not in tables:
        raise NotebookUnavailable(
            f"这个文件不是错题本结构（缺少 cards 表）。\n{_hint(path)}"
        )
    columns = {row[1] for row in conn.execute("PRAGMA table_info(cards)")}
    missing = [name for name in REQUIRED_CARD_COLUMNS if name not in columns]
    if missing:
        raise NotebookUnavailable(
            f"错题本表结构不完整，缺少列：{'、'.join(missing)}。\n{_hint(path)}"
        )
    version = _schema_version(conn, path)
    return columns, version


def _init_schema(conn):
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
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS meta (
            key TEXT PRIMARY KEY,
            value TEXT NOT NULL
        )
        """
    )
    conn.execute(
        "INSERT INTO meta(key, value) VALUES ('schema_version', ?) "
        "ON CONFLICT(key) DO UPDATE SET value = excluded.value",
        (str(SCHEMA_VERSION),),
    )
    conn.commit()


def _migrate_if_needed(conn, path, columns, version):
    if version >= SCHEMA_VERSION:
        return
    if "raw_node" not in columns:
        conn.execute("ALTER TABLE cards ADD COLUMN raw_node TEXT DEFAULT ''")
    if "verify_status" not in columns:
        conn.execute("ALTER TABLE cards ADD COLUMN verify_status TEXT DEFAULT ''")
    if "meta" not in _table_names(conn):
        conn.execute(
            """
            CREATE TABLE meta (
                key TEXT PRIMARY KEY,
                value TEXT NOT NULL
            )
            """
        )
    conn.execute(
        "INSERT INTO meta(key, value) VALUES ('schema_version', ?) "
        "ON CONFLICT(key) DO UPDATE SET value = excluded.value",
        (str(SCHEMA_VERSION),),
    )
    conn.commit()


def _row_is_illegal(row):
    try:
        if row["ease"] is None:
            return True
        float(row["ease"])
    except (TypeError, ValueError, KeyError):
        return True
    try:
        if row["interval_days"] is None:
            return True
        int(row["interval_days"])
    except (TypeError, ValueError, KeyError):
        return True
    try:
        if row["reps"] is None:
            return True
        int(row["reps"])
    except (TypeError, ValueError, KeyError):
        return True
    try:
        due = row["due"]
    except (KeyError, IndexError):
        return True
    if due is None or str(due).strip() == "":
        return True
    try:
        date.fromisoformat(str(due))
    except ValueError:
        return True
    return False


def _bad_rows_message(path, bad_ids):
    ids = "、".join(str(i) for i in bad_ids)
    return (
        f"错题本有记录数据不合法（编号：{ids}），"
        "合法记录已照常处理，非法行未写入也未导出。\n"
        f"{_hint(path)}"
    )


def _collect_cards(conn):
    rows = conn.execute("SELECT * FROM cards ORDER BY id").fetchall()
    cards = []
    bad_ids = []
    for row in rows:
        if _row_is_illegal(row):
            bad_ids.append(row["id"])
            continue
        cards.append(_public(row))
    return cards, bad_ids


def _read_cards(path):
    path = Path(path)
    kind = _path_kind(path)
    if kind in ("missing", "empty"):
        return [], []
    conn = _connect(path, writable=False, create=False)
    try:
        return _collect_cards(conn)
    finally:
        conn.close()


def _connect(path, *, writable=True, create=True):
    path = Path(path)
    kind = _path_kind(path)
    if kind == "missing":
        if not writable or not create:
            raise NotebookError("错题本不存在或为空")
        path.parent.mkdir(parents=True, exist_ok=True)
        conn = _open_sqlite(path, readonly=False)
        try:
            _init_schema(conn)
        except sqlite3.Error as exc:
            conn.close()
            raise _sqlite_to_unavailable(path, exc) from exc
        return conn
    if kind == "empty":
        if not writable or not create:
            raise NotebookError("错题本不存在或为空")
        conn = _open_sqlite(path, readonly=False)
        try:
            _init_schema(conn)
        except sqlite3.Error as exc:
            conn.close()
            raise _sqlite_to_unavailable(path, exc) from exc
        return conn

    conn = _open_sqlite(path, readonly=not writable)
    try:
        _quick_check(conn, path)
        columns, version = _inspect_schema(conn, path)
        _, bad_ids = _collect_cards(conn)
        if bad_ids and writable:
            raise NotebookRowError(_bad_rows_message(path, bad_ids), cards=[], bad_ids=bad_ids)
        if writable:
            _migrate_if_needed(conn, path, columns, version)
    except (NotebookError, NotebookUnavailable, MissingDependency):
        conn.close()
        raise
    except sqlite3.Error as exc:
        conn.close()
        raise _sqlite_to_unavailable(path, exc) from exc
    except OSError as exc:
        conn.close()
        raise NotebookUnavailable(
            f"无法使用错题本文件。\n{_hint(path)}"
        ) from exc
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
            try:
                if args.entry == "-":
                    entry = json.load(sys.stdin)
                else:
                    with open(args.entry, encoding="utf-8") as fh:
                        entry = json.load(fh)
            except FileNotFoundError:
                print(f"找不到条目文件：{args.entry}", file=sys.stderr)
                return 2
            except json.JSONDecodeError:
                print("条目 JSON 无法解析", file=sys.stderr)
                return 2
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
    except NotebookRowError as exc:
        if args.cmd == "due":
            print(format_due(exc.cards))
        print(str(exc), file=sys.stderr)
        return 3
    except NotebookError as exc:
        print(str(exc), file=sys.stderr)
        return 2
    except MissingDependency as exc:
        print(str(exc), file=sys.stderr)
        return 4
    except NotebookUnavailable as exc:
        print(str(exc), file=sys.stderr)
        return 3
    except sqlite3.Error as exc:
        print(_sqlite_to_unavailable(path, exc), file=sys.stderr)
        return 3
    except OSError as exc:
        print(f"无法访问错题本或输出路径：{exc}\n{_hint(path)}", file=sys.stderr)
        return 3
    return 0


def _require_openpyxl():
    try:
        import openpyxl  # noqa: F401
    except ImportError as exc:
        raise MissingDependency(
            "导出需要 openpyxl。请先运行：pip install openpyxl"
        ) from exc


def _check_export_output(output):
    output = Path(output)
    if output.exists() and output.is_dir():
        raise NotebookError(f"输出路径是目录，无法写入：{output}")
    parent = output.parent if str(output.parent) else Path(".")
    if not parent.exists():
        raise NotebookError(f"输出目录不存在：{parent}")
    if parent.exists() and not parent.is_dir():
        raise NotebookError(f"输出路径不可写：{output}")
    return output


def _export(path, output):
    import importlib.util

    output = _check_export_output(output)
    _require_openpyxl()
    kind = _path_kind(path)
    if kind in ("missing", "empty"):
        raise NotebookError("错题本不存在或为空，无法导出")
    cards = list_cards(path)
    if not cards:
        raise NotebookError("错题本不存在或为空，无法导出")

    gen_path = Path(__file__).resolve().parent.parent / "templates" / "wrong-notebook-generator.py"
    spec = importlib.util.spec_from_file_location("wrong_notebook_generator", gen_path)
    gen = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(gen)

    fd, tmp_name = tempfile.mkstemp(prefix=".notebook-export-", suffix=".xlsx", dir=str(output.parent))
    os.close(fd)
    tmp_path = Path(tmp_name)
    try:
        gen.workbook_from_cards(cards).save(str(tmp_path))
        os.replace(tmp_path, output)
    except Exception as exc:
        tmp_path.unlink(missing_ok=True)
        raise NotebookUnavailable(f"导出失败：{exc}\n{_hint(path)}") from exc


if __name__ == "__main__":
    sys.exit(main())
