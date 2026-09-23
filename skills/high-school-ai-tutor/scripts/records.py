#!/usr/bin/env python3
"""判完一题写一条记录，下次按考点汇总薄弱点。只使用标准库。

默认写到 ~/.high-school-ai-tutor/records.jsonl，不进仓库。

    python3 records.py add --subject 化学 --node 氧化还原反应 --stem 电石除杂 --outcome 做错 --error 概念
    python3 records.py weak
"""

import argparse
import json
import sys
from datetime import date
from pathlib import Path

OUTCOMES = ("做对", "做错", "跳过")
ERRORS = ("审题", "概念", "计算", "方法", "表达", "心态")
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


def add_record(path, subject, node, stem, outcome, error="", when=None):
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
    stem = clean_stem(stem)
    when = when or date.today().isoformat()
    existing = _read(path)
    row = {
        "id": len(existing) + 1,
        "date": when,
        "subject": subject,
        "node": node,
        "stem": stem,
        "outcome": outcome,
        "error": error,
    }
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as fh:
        fh.write(json.dumps(row, ensure_ascii=False) + "\n")
    return row


def weak_points(path):
    rows = _read(path)
    if not rows:
        return None
    grouped = {}
    for row in rows:
        key = (row["subject"], row["node"])
        bucket = grouped.setdefault(key, {"subject": row["subject"], "node": row["node"], "wrong": 0, "skipped": 0, "correct": 0})
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


def _read(path):
    path = Path(path)
    if not path.exists():
        return []
    rows = []
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if line:
            rows.append(json.loads(line))
    return rows


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

    sub.add_parser("weak", parents=[shared])

    args = parser.parse_args(argv)
    path = args.file or default_path()
    try:
        if args.cmd == "add":
            row = add_record(path, args.subject, args.node, args.stem, args.outcome, args.error, args.date)
            print(f"已记下：{row['subject']} · {row['node']}，{row['outcome']}")
        else:
            print(format_weak(weak_points(path)))
    except RecordError as exc:
        print(str(exc), file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    sys.exit(main())
