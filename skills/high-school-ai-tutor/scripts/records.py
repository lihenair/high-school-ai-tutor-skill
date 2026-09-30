#!/usr/bin/env python3
"""判完一题写一条记录，下次按考点汇总薄弱点。只使用标准库。

默认写到 ~/.high-school-ai-tutor/records.jsonl，不进仓库。

    python3 records.py add --subject 化学 --node 氧化还原反应 --stem 电石除杂 --outcome 做错 --error 概念
    python3 records.py add --subject 化学 --node 氧化还原反应 --stem 诊断快诊 --outcome 做错 --error 概念 --context 自学诊断
    python3 records.py weak
    python3 records.py unmatched
"""

import argparse
import json
import os
import sys
import threading
from contextlib import contextmanager
from datetime import date
from pathlib import Path

try:
    import fcntl
except ImportError:
    fcntl = None

try:
    import msvcrt
except ImportError:
    msvcrt = None

_SCRIPTS = Path(__file__).resolve().parent
if str(_SCRIPTS) not in sys.path:
    sys.path.insert(0, str(_SCRIPTS))
import nodes

OUTCOMES = ("做对", "做错", "跳过")
ERRORS = ("审题", "概念", "计算", "方法", "表达", "心态")
CONTEXTS = ("", "自学诊断", "自学自测")
STEM_MARKERS = ("答案", "解析", "配平", "解：", "所以", "因此")


class RecordError(ValueError):
    pass


def default_path():
    return Path.home() / ".high-school-ai-tutor" / "records.jsonl"


def clean_stem(stem):
    text = " ".join(str(stem or "").split())
    for sep in "。！？\n":
        text = text.split(sep)[0]
    for marker in STEM_MARKERS:
        if marker in text:
            text = text.split(marker)[0]
    text = text.strip(" ，,;；:：")
    if not text:
        raise RecordError("题目摘要不能只写答案或解法")
    return text[:40]


def add_record(path, subject, node, stem, outcome, error="", when=None, context="", node_id=""):
    path = Path(path)
    subject = str(subject or "").strip()
    node = str(node or "").strip()
    if not subject or not node:
        raise RecordError("科目和核心考点都要有")
    if outcome not in OUTCOMES:
        raise RecordError("结果只能是做对、做错或跳过")
    error = str(error or "").strip()
    if outcome == "做错":
        if error not in ERRORS:
            raise RecordError("做错时错因只能是审题、概念、计算、方法、表达、心态")
    elif error:
        raise RecordError("做对或跳过不要写错因")
    context = str(context or "").strip()
    if context not in CONTEXTS:
        raise RecordError("context 只能是自学诊断或自学自测")
    node_id = str(node_id or "").strip()
    stem = clean_stem(stem)
    when = when or date.today().isoformat()
    canon_subject, canon_node, raw_node, hit = nodes.normalize(subject, node)
    if hit:
        stored_subject, stored_node = canon_subject, canon_node
    else:
        stored_subject, stored_node = subject, node
        nodes.warn_miss(stored_subject, raw_node)
    row = {
        "date": when,
        "subject": stored_subject,
        "node": stored_node,
        "raw_node": raw_node,
        "verify_status": "",
        "stem": stem,
        "outcome": outcome,
        "error": error,
    }
    if context:
        row["context"] = context
    if node_id:
        row["node_id"] = node_id
    path.parent.mkdir(parents=True, exist_ok=True)
    with _exclusive_lock(path) as fh:
        fh.seek(0)
        existing = _read_lines(fh)
        ids = [int(item["id"]) for item in existing if str(item.get("id", "")).isdigit()]
        row["id"] = (max(ids) + 1) if ids else 1
        fh.seek(0, os.SEEK_END)
        fh.write(json.dumps(row, ensure_ascii=False) + "\n")
        fh.flush()
        os.fsync(fh.fileno())
    return row


def weak_points(path):
    rows = _read(path)
    if not rows:
        return None
    grouped = {}
    for row in rows:
        raw = row.get("raw_node") or row.get("node") or ""
        subject = row.get("subject") or ""
        canon_subject, canon_node, _original, hit = nodes.normalize(subject, raw)
        if hit:
            key = (canon_subject, canon_node)
        else:
            key = (str(subject).strip(), str(row.get("node") or raw).strip())
        bucket = grouped.setdefault(key, {"subject": key[0], "node": key[1], "wrong": 0, "skipped": 0, "correct": 0})
        if row["outcome"] == "做错":
            bucket["wrong"] += 1
        elif row["outcome"] == "跳过":
            bucket["skipped"] += 1
        else:
            bucket["correct"] += 1
    weak = [item for item in grouped.values() if item["wrong"] + item["skipped"] > item["correct"]]
    weak.sort(key=lambda item: (-(item["wrong"] + item["skipped"] - item["correct"]), -item["wrong"], item["subject"], item["node"]))
    return weak


def format_weak(items):
    if items is None:
        return "还没有判过的题。"
    if not items:
        return "目前没有薄弱点。"
    lines = ["薄弱点"]
    for index, item in enumerate(items, 1):
        lines.append(
            f"{index}. {item['subject']} · {item['node']}：做错 {item['wrong']}，跳过 {item['skipped']}，做对 {item['correct']}"
        )
    return "\n".join(lines)


def unmatched_rows(path):
    counts = {}
    for row in _read(path):
        raw = str(row.get("raw_node") or row.get("node") or "").strip()
        subject = str(row.get("subject") or "").strip()
        _canon_subject, _canon_node, _original, hit = nodes.normalize(subject, raw)
        if hit:
            continue
        bucket = counts.setdefault((subject, raw), {"count": 0, "subject": subject, "raw": raw})
        bucket["count"] += 1
    rows = []
    for bucket in counts.values():
        bucket["suggest"] = nodes.suggest(bucket["subject"], bucket["raw"])
        rows.append(bucket)
    rows.sort(key=lambda item: (-item["count"], item["subject"], item["raw"]))
    return rows


def format_unmatched(rows):
    if not rows:
        return "没有未命中的考点。"
    lines = ["频次 | 原文 | 建议补录为"]
    for item in rows:
        lines.append(f"{item['count']} | {item['subject']} · {item['raw']} | {item['suggest']}")
    return "\n".join(lines)


def _read(path):
    path = Path(path)
    if not path.exists():
        return []
    with path.open(encoding="utf-8") as fh:
        return _read_lines(fh)


def _read_lines(fh):
    rows = []
    for line in fh:
        line = line.strip()
        if not line:
            continue
        try:
            rows.append(json.loads(line))
        except json.JSONDecodeError:
            print("WARN 跳过无法解析的记录行", file=sys.stderr)
    return rows


_THREAD_LOCK = threading.Lock()


@contextmanager
def _exclusive_lock(path):
    """锁数据文件本身，不另建 sidecar .lock。同进程用线程锁，跨进程用 flock / msvcrt。"""
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with _THREAD_LOCK:
        handle = path.open("a+", encoding="utf-8")
        win_locked = False
        try:
            if fcntl is not None:
                fcntl.flock(handle.fileno(), fcntl.LOCK_EX)
            elif msvcrt is not None:
                handle.seek(0, os.SEEK_END)
                if handle.tell() == 0:
                    handle.write("\n")
                    handle.flush()
                handle.seek(0)
                msvcrt.locking(handle.fileno(), msvcrt.LK_LOCK, 1)
                win_locked = True
            yield handle
        finally:
            try:
                if fcntl is not None:
                    fcntl.flock(handle.fileno(), fcntl.LOCK_UN)
                elif win_locked:
                    handle.seek(0)
                    msvcrt.locking(handle.fileno(), msvcrt.LK_UNLCK, 1)
            finally:
                handle.close()


def main(argv=None):
    parser = argparse.ArgumentParser(description="判题记录与薄弱点")
    shared = argparse.ArgumentParser(add_help=False)
    shared.add_argument("--file", type=Path, default=None)
    sub = parser.add_subparsers(dest="cmd", required=True)

    add = sub.add_parser("add", parents=[shared])
    add.add_argument("--subject", required=True)
    add.add_argument("--node", required=True)
    add.add_argument("--stem", required=True)
    add.add_argument("--outcome", required=True)
    add.add_argument("--error", default="")
    add.add_argument("--date", default=None)
    add.add_argument("--context", default="", help="自学诊断或自学自测；解题记录留空")
    add.add_argument("--node-id", default="", help="正典 kp_*；显示名仍写在 --node")

    sub.add_parser("weak", parents=[shared])
    sub.add_parser("unmatched", parents=[shared])

    args = parser.parse_args(argv)
    path = args.file or default_path()
    try:
        if args.cmd == "add":
            row = add_record(
                path, args.subject, args.node, args.stem, args.outcome, args.error, args.date,
                context=args.context, node_id=getattr(args, "node_id", ""),
            )
            print(f"已记下：{row['subject']} · {row['node']}，{row['outcome']}")
        elif args.cmd == "unmatched":
            print(format_unmatched(unmatched_rows(path)))
        else:
            print(format_weak(weak_points(path)))
    except RecordError as exc:
        print(str(exc), file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    sys.exit(main())
