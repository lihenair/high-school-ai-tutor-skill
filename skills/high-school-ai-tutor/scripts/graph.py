#!/usr/bin/env python3
"""章节图。内容资产在仓库 data/graph.db，用户数据不进这个文件。

    python3 graph.py init --db <skill目录>/data/graph.db
    python3 graph.py topo --chapter chem-bx1-ch1 --db <skill目录>/data/graph.db
    python3 graph.py prereq --node kp_ion_eq --db <skill目录>/data/graph.db
    python3 graph.py grey --chapter chem-bx1-ch1 --db <skill目录>/data/graph.db
"""

import argparse
import sqlite3
import sys
from pathlib import Path

SKILL_DIR = Path(__file__).resolve().parent.parent
STUDY_PAGES = SKILL_DIR / "references" / "study-pages"
ORDER_KINDS = ("直接前置", "同章衔接")

def _load_seeds():
    """读取 data/graph-seeds.py。缺文件即失败，不回退到内联常量。"""
    import importlib.util

    seeds_path = SKILL_DIR / "data" / "graph-seeds.py"
    sys.dont_write_bytecode = True
    if not seeds_path.is_file():
        print(f"缺少 {seeds_path}", file=sys.stderr)
        raise SystemExit(2)
    spec = importlib.util.spec_from_file_location("graph_seeds", seeds_path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module.SEED_NODES, module.SEED_EDGES




def default_db():
    return SKILL_DIR / "data" / "graph.db"


def connect(path):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    return sqlite3.connect(path)


def init_db(path):
    conn = connect(path)
    conn.executescript(
        """
        DROP TABLE IF EXISTS edges;
        DROP TABLE IF EXISTS nodes;
        CREATE TABLE nodes (
            id TEXT PRIMARY KEY,
            subject TEXT NOT NULL,
            display_name TEXT NOT NULL,
            chapter_id TEXT NOT NULL,
            grey INTEGER NOT NULL DEFAULT 0
        );
        CREATE TABLE edges (
            src TEXT NOT NULL,
            dst TEXT NOT NULL,
            kind TEXT NOT NULL
        );
        """
    )
    seed_nodes, seed_edges = _load_seeds()
    conn.executemany(
        "INSERT INTO nodes (id, subject, display_name, chapter_id, grey) VALUES (?, ?, ?, ?, ?)",
        seed_nodes,
    )
    conn.executemany("INSERT INTO edges (src, dst, kind) VALUES (?, ?, ?)", seed_edges)
    conn.commit()
    conn.close()
    return Path(path)


def _nodes(conn, chapter):
    rows = conn.execute(
        "SELECT id, display_name, grey FROM nodes WHERE chapter_id = ? ORDER BY id",
        (chapter,),
    ).fetchall()
    return rows


def topo_order(chapter, path=None):
    """直接前置和同章衔接排成学习顺序。常考组合不参与排序。"""
    conn = connect(path or default_db())
    rows = _nodes(conn, chapter)
    ids = [row[0] for row in rows if not row[2]]
    names = {row[0]: row[1] for row in rows}
    incoming = {node_id: set() for node_id in ids}
    outgoing = {node_id: set() for node_id in ids}
    if ids:
        query = (
            "SELECT src, dst FROM edges WHERE kind IN (?, ?) AND src IN ({}) AND dst IN ({})"
        ).format(",".join("?" * len(ids)), ",".join("?" * len(ids)))
        for src, dst in conn.execute(query, (*ORDER_KINDS, *ids, *ids)):
            incoming[dst].add(src)
            outgoing[src].add(dst)
    ready = sorted(node_id for node_id in ids if not incoming[node_id])
    ordered = []
    while ready:
        node_id = ready.pop(0)
        ordered.append(node_id)
        for dst in sorted(outgoing[node_id]):
            incoming[dst].discard(node_id)
            if not incoming[dst] and dst not in ordered and dst not in ready:
                ready.append(dst)
        ready.sort()
    conn.close()
    return [(node_id, names.get(node_id, node_id)) for node_id in ordered]


def prereq(node_id, path=None):
    conn = connect(path or default_db())
    rows = conn.execute(
        "SELECT src FROM edges WHERE dst = ? AND kind = ? ORDER BY src",
        (node_id, "直接前置"),
    ).fetchall()
    conn.close()
    return [row[0] for row in rows]


def _has_page(chapter, node_id):
    return (STUDY_PAGES / chapter / f"{node_id}.md").exists()


def grey_nodes(chapter, path=None):
    """章末预告：从本章指出去的后续章节节点。"""
    conn = connect(path or default_db())
    rows = conn.execute(
        """
        SELECT DISTINCT n.id, n.display_name, n.chapter_id
        FROM edges e
        JOIN nodes src ON src.id = e.src
        JOIN nodes n ON n.id = e.dst
        WHERE src.chapter_id = ? AND (n.grey = 1 OR n.chapter_id != ?)
        ORDER BY n.display_name
        """,
        (chapter, chapter),
    ).fetchall()
    conn.close()
    preview = []
    for node_id, display, chapter_id in rows:
        preview.append({
            "id": node_id,
            "display_name": display,
            "chapter_id": chapter_id,
            "asset": _has_page(chapter_id, node_id),
        })
    return preview


def format_grey(items):
    if not items:
        return "下一章：暂无预告"
    lines = ["下一章：后续章节"]
    for item in items:
        mark = "有讲解页" if item["asset"] else "仅正典，现场生成"
        lines.append(f"- {item['display_name']}（{mark}）")
    return "\n".join(lines)


def main(argv=None):
    parser = argparse.ArgumentParser(description="章节拓扑、前置和章末预告")
    shared = argparse.ArgumentParser(add_help=False)
    shared.add_argument("--db", type=Path, default=None)
    sub = parser.add_subparsers(dest="cmd", required=True)
    sub.add_parser("init", parents=[shared])
    topo = sub.add_parser("topo", parents=[shared])
    topo.add_argument("--chapter", required=True)
    pre = sub.add_parser("prereq", parents=[shared])
    pre.add_argument("--node", required=True)
    grey = sub.add_parser("grey", parents=[shared])
    grey.add_argument("--chapter", required=True)
    args = parser.parse_args(argv)
    path = args.db or default_db()
    if args.cmd == "init":
        init_db(path)
        print(f"已写入 {path}")
        return 0
    if not path.exists():
        print("缺少 graph.db，先运行 init。", file=sys.stderr)
        return 2
    if args.cmd == "topo":
        for node_id, name in topo_order(args.chapter, path):
            print(f"{node_id}\t{name}")
        return 0
    if args.cmd == "prereq":
        found = prereq(args.node, path)
        print("\n".join(found))
        return 0
    print(format_grey(grey_nodes(args.chapter, path)))
    return 0


if __name__ == "__main__":
    sys.exit(main())
