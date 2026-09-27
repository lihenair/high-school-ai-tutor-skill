#!/usr/bin/env python3
"""正典是章节点名的唯一真源。

从 references/nodes/ 的 pipeline 块生成非灰种子行，以及生物整章图里的本章节点骨架，
与 data/graph-seeds.py、references/pep-bio-*.md 对账。不一致则退出码 1。

章号写在 `# pipeline:begin <slug>`。slug 必须带学科前缀（生物 bio-、化学 chem-），
这样 `study-pages/<slug>/` 与 `pep-<slug>.md` 不会在选必册上撞名。
灰节点（grey=1）不进正典，只留在种子里做章末预告。
"""

import importlib.util
import re
import sys
from pathlib import Path

import nodes

SKILL_DIR = Path(__file__).resolve().parent.parent
SEEDS_PATH = SKILL_DIR / "data" / "graph-seeds.py"
REFS = SKILL_DIR / "references"
STUDY_PAGES = REFS / "study-pages"

# 与现有目录 chem-、bio- 对齐。物理选必铺开时用 phy-，不要写成裸的 xbx1-ch1。
SUBJECT_PREFIX = {
    "数学": "math",
    "物理": "phy",
    "化学": "chem",
    "生物": "bio",
    "语文": "chinese",
    "英语": "english",
    "历史": "history",
    "政治": "politics",
    "地理": "geography",
}

_BEGIN = re.compile(r"^#\s*pipeline:begin\s+(\S+)\s*$")
_END = re.compile(r"^#\s*pipeline:end\s+(\S+)\s*$")
_ID = re.compile(r"^#\s*id\s+(\S+)\s+(.+)$")
# mermaid 类标记是三个冒号。subgraph 的 ch["章名"] 没有类标记，不计入节点骨架。
_DEF = re.compile(
    r'([A-Za-z_][A-Za-z0-9_]*)\["([^"]+)"\](?::::(concept|skill|experiment|later))?'
)
_KIND = re.compile(r"（(?:概念|技能|实验)）$")


def load_pipeline():
    """返回 ([(id, subject, display, chapter, 0), ...], problems)。"""
    rows = []
    problems = []
    seen_ids = {}
    for subject, filename in nodes.SUBJECT_FILES:
        path = nodes.NODES_DIR / filename
        if not path.exists():
            continue
        prefix = SUBJECT_PREFIX[subject]
        chapter = None
        pending = None
        for lineno, raw in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
            line = raw.strip()
            begin = _BEGIN.match(line)
            if begin:
                if chapter:
                    problems.append(f"{filename}:{lineno} pipeline 未闭合就开了新章 {begin.group(1)}")
                chapter = begin.group(1)
                if not chapter.startswith(prefix + "-"):
                    problems.append(
                        f"{filename}:{lineno} 章号 {chapter} 缺少学科前缀，应为 {prefix}-…"
                    )
                continue
            end = _END.match(line)
            if end:
                if end.group(1) != chapter:
                    problems.append(f"{filename}:{lineno} pipeline:end 与 begin 不一致")
                chapter = None
                pending = None
                continue
            ident = _ID.match(line)
            if ident:
                if pending:
                    problems.append(f"{filename}:{lineno} 上一条 # id 没有节点行")
                pending = (ident.group(1), ident.group(2).strip(), lineno)
                continue
            if not line or line.startswith("#"):
                continue
            if pending is None:
                continue
            node_id, display, id_line = pending
            pending = None
            name = line.split("|", 1)[0].strip()
            if name != display:
                problems.append(f"{filename}:{id_line} # id 显示名与节点行不一致：{display} / {name}")
                continue
            if not chapter:
                problems.append(f"{filename}:{id_line} # id {node_id} 不在 pipeline 块内，无法生成章号")
                continue
            if node_id in seen_ids:
                problems.append(f"正典 id 重复：{node_id}（{seen_ids[node_id]} 与 {chapter}）")
            seen_ids[node_id] = chapter
            rows.append((node_id, subject, display, chapter, 0))
        if chapter:
            problems.append(f"{filename} pipeline 未闭合：{chapter}")
        if pending:
            problems.append(f"{filename} 文件末尾的 # id 没有节点行")
    return rows, problems


def load_seeds():
    spec = importlib.util.spec_from_file_location("graph_seeds", SEEDS_PATH)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return list(module.SEED_NODES), list(module.SEED_EDGES)


def diff_rows(expected, actual):
    """集合差。返回 (missing, extra)，元素保持元组。"""
    exp = set(expected)
    act = set(actual)
    return sorted(exp - act), sorted(act - exp)


def skeleton_from_mermaid(text):
    """本章节点（非 :::later）与跨章灰节点。id -> 去掉种类后缀的显示名。"""
    grouped = {}
    for match in _DEF.finditer(text):
        node_id, label, kind = match.group(1), match.group(2), match.group(3) or ""
        grouped.setdefault(node_id, []).append((_KIND.sub("", label), kind))
    owned = {}
    later = {}
    for node_id, items in grouped.items():
        own = [display for display, kind in items if kind in ("concept", "skill", "experiment")]
        grey = [display for display, kind in items if kind == "later"]
        if own:
            owned[node_id] = own[0]
        elif grey:
            later[node_id] = grey[0]
    return owned, later


def _fmt_row(row):
    node_id, subject, display, chapter, grey = row
    return f"    ('{node_id}', '{subject}', '{display}', '{chapter}', {grey}),"


def audit():
    problems = []
    expected, parse_problems = load_pipeline()
    problems.extend(parse_problems)
    if not SEEDS_PATH.is_file():
        problems.append(f"缺少 {SEEDS_PATH}")
        return problems
    seeds, edges = load_seeds()
    canon_ids = {row[0]: row for row in expected}
    non_grey = []
    grey_rows = []
    seed_ids = {}
    for row in seeds:
        if len(row) != 5:
            problems.append(f"种子行不是五元组：{row!r}")
            continue
        node_id = row[0]
        if node_id in seed_ids:
            problems.append(f"种子 id 重复：{node_id}")
        seed_ids[node_id] = row
        if row[4] == 0:
            non_grey.append(tuple(row))
        elif row[4] == 1:
            grey_rows.append(tuple(row))
            if node_id in canon_ids:
                problems.append(f"灰节点与正典 id 冲突：{node_id}")
        else:
            problems.append(f"种子 grey 只能是 0 或 1：{node_id}")
    missing, extra = diff_rows(expected, non_grey)
    for row in missing:
        problems.append("正典有、种子无：" + _fmt_row(row).strip())
    for row in extra:
        problems.append("种子有、正典无：" + _fmt_row(row).strip())

    for src, dst, _kind in edges:
        if src not in seed_ids:
            problems.append(f"种子边起点不在节点表：{src}")
        if dst not in seed_ids:
            problems.append(f"种子边终点不在节点表：{dst}")

    by_chapter = {}
    for row in expected:
        by_chapter.setdefault(row[3], []).append(row)

    pep_files = sorted(REFS.glob("pep-bio-*.md"))
    pep_slugs = {}
    for path in pep_files:
        slug = path.name[len("pep-"):-len(".md")]
        pep_slugs[slug] = path
    bio_chapters = {chapter for chapter, rows in by_chapter.items() if rows[0][1] == "生物"}
    for chapter in sorted(bio_chapters - set(pep_slugs)):
        problems.append(f"正典章 {chapter} 没有整章图 references/pep-{chapter}.md")
    for slug in sorted(set(pep_slugs) - bio_chapters):
        problems.append(f"整章图 pep-{slug}.md 没有对应的正典 pipeline 章")

    for chapter, path in sorted(pep_slugs.items()):
        if chapter not in bio_chapters:
            continue
        owned, later = skeleton_from_mermaid(path.read_text(encoding="utf-8"))
        expect_map = {row[0]: row[2] for row in by_chapter[chapter]}
        for node_id in sorted(set(expect_map) - set(owned)):
            problems.append(f"{path.name} 缺本章节点 {node_id}（{expect_map[node_id]}）")
        for node_id in sorted(set(owned) - set(expect_map)):
            problems.append(f"{path.name} 多了本章节点 {node_id}（{owned[node_id]}）")
        for node_id in sorted(set(expect_map) & set(owned)):
            if owned[node_id] != expect_map[node_id]:
                problems.append(
                    f"{path.name} 显示名不一致：{node_id} 正典「{expect_map[node_id]}」图「{owned[node_id]}」"
                )
        for node_id, display in sorted(later.items()):
            if node_id not in canon_ids:
                problems.append(f"{path.name} 跨章节点不在正典：{node_id}（{display}）")
                continue
            canon_display = canon_ids[node_id][2]
            if display != canon_display:
                problems.append(
                    f"{path.name} 跨章显示名不一致：{node_id} 正典「{canon_display}」图「{display}」"
                )

    if STUDY_PAGES.is_dir():
        slugs = set(by_chapter)
        for path in sorted(p for p in STUDY_PAGES.iterdir() if p.is_dir() and not p.name.startswith(".")):
            name = path.name
            if name not in slugs:
                problems.append(f"study-pages/{name} 不是正典章号（须为 <学科前缀>-<册>-<章>，如 bio-xbx1-ch3）")
            elif not any(name.startswith(prefix + "-") for prefix in SUBJECT_PREFIX.values()):
                problems.append(f"study-pages/{name} 缺少学科前缀")
    return problems


def main(argv=None):
    problems = audit()
    if problems:
        print(f"正典对齐失败（{len(problems)}）", file=sys.stderr)
        for item in problems:
            print(item, file=sys.stderr)
        return 1
    print("OK 正典、非灰种子行、生物整章图骨架、study-pages 章号一致")
    return 0


if __name__ == "__main__":
    sys.exit(main())
