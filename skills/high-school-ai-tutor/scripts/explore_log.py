#!/usr/bin/env python3
"""兴趣原问日志。只追加，不读掌握度、错题本或判题记录。

    python3 explore_log.py add --subject 化学 --node 氧化还原反应 --category 大学基础 --question "电极电势是什么" --file ~/.high-school-ai-tutor/explore_log.jsonl
"""

import argparse
import json
import sys
from datetime import date
from pathlib import Path

CATEGORIES = ("学段常规", "竞赛", "大学基础", "兴趣延伸")


class ExploreError(ValueError):
    pass


def default_path():
    return Path.home() / ".high-school-ai-tutor" / "explore_log.jsonl"


def add_entry(path, subject, node, category, question, when=None):
    subject = str(subject or "").strip()
    node = str(node or "").strip()
    question = " ".join(str(question or "").split())
    category = str(category or "").strip()
    if not subject or not node or not question:
        raise ExploreError("科目、节点和原问都要有")
    if category not in CATEGORIES:
        raise ExploreError("类别只能是学段常规、竞赛、大学基础或兴趣延伸")
    row = {
        "date": when or date.today().isoformat(),
        "subject": subject,
        "node": node,
        "category": category,
        "question": question,
    }
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(row, ensure_ascii=False) + "\n")
    return row


def main(argv=None):
    parser = argparse.ArgumentParser(description="兴趣原问日志")
    shared = argparse.ArgumentParser(add_help=False)
    shared.add_argument("--file", type=Path, default=None)
    sub = parser.add_subparsers(dest="cmd", required=True)
    add = sub.add_parser("add", parents=[shared])
    add.add_argument("--subject", required=True)
    add.add_argument("--node", required=True)
    add.add_argument("--category", required=True)
    add.add_argument("--question", required=True)
    add.add_argument("--date", default=None)
    args = parser.parse_args(argv)
    path = args.file or default_path()
    try:
        row = add_entry(path, args.subject, args.node, args.category, args.question, args.date)
    except ExploreError as exc:
        print(str(exc), file=sys.stderr)
        return 2
    print(f"已记下兴趣原问：{row['subject']} · {row['node']}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
