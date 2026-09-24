#!/usr/bin/env python3
"""节点正典。科目是封闭枚举，考点只从 references/nodes/ 解析。"""

import re
import sys
from pathlib import Path

NODES_DIR = Path(__file__).resolve().parent.parent / "references" / "nodes"

# 与 references/nodes/<file> 一一对应，顺序跟 SKILL.md 科目分流表。
SUBJECT_FILES = (
    ("数学", "math.md"),
    ("物理", "physics.md"),
    ("化学", "chemistry.md"),
    ("生物", "biology.md"),
    ("语文", "chinese.md"),
    ("英语", "english.md"),
    ("历史", "history.md"),
    ("政治", "politics.md"),
    ("地理", "geography.md"),
)
SUBJECTS = tuple(name for name, _ in SUBJECT_FILES)

_ALIAS_SEP = "、"
_SPACE = re.compile(r"\s+")


def _fold(text):
    return _SPACE.sub("", str(text or "").strip())


def parse_lines(filename, text):
    """一行一个节点：标准名 | 别名列表 | 所属章。别名用顿号分隔，可以留空。"""
    entries = []
    problems = []
    for lineno, raw in enumerate(text.splitlines(), 1):
        line = raw.strip()
        if not line:
            continue
        parts = [part.strip() for part in line.split("|")]
        if len(parts) != 3 or not parts[0] or not parts[2]:
            problems.append(f"正典格式错误：{filename}:{lineno}")
            continue
        aliases = [alias for alias in (part.strip() for part in parts[1].split(_ALIAS_SEP)) if alias]
        entries.append((parts[0], aliases, parts[2]))
    return entries, problems


def collision_problems(subject, entries):
    problems = []
    keys = {}
    for standard, aliases, _chapter in entries:
        for label in (standard, *aliases):
            key = _fold(label)
            if not key:
                continue
            if key in keys:
                problems.append(f"正典别名重复：{subject} · {label}")
            else:
                keys[key] = standard
    return problems


def audit():
    """正典格式、科目与文件双向覆盖、别名查重。空列表表示通过。"""
    problems = []
    if not NODES_DIR.is_dir():
        return ["缺少 references/nodes/"]
    found = set()
    for path in sorted(NODES_DIR.iterdir()):
        if path.name.startswith("."):
            continue
        found.add(path.name)
        if path.suffix != ".md":
            problems.append(f"孤儿正典文件 {path.name}")
    expected = {filename for _, filename in SUBJECT_FILES}
    for subject, filename in SUBJECT_FILES:
        if filename not in found:
            problems.append(f"科目 {subject} 缺少正典文件 {filename}")
    for filename in sorted(found - expected):
        if filename.endswith(".md"):
            problems.append(f"孤儿正典文件 {filename}")
    for subject, filename in SUBJECT_FILES:
        path = NODES_DIR / filename
        if not path.exists():
            continue
        entries, parse_problems = parse_lines(filename, path.read_text(encoding="utf-8"))
        problems.extend(parse_problems)
        if not entries:
            problems.append(f"科目 {subject} 的正典文件没有节点")
        problems.extend(collision_problems(subject, entries))
    return problems


def _catalog():
    index = {}
    standards = {}
    for subject, filename in SUBJECT_FILES:
        path = NODES_DIR / filename
        mapping = {}
        names = []
        if path.exists():
            entries, _problems = parse_lines(filename, path.read_text(encoding="utf-8"))
            for standard, aliases, _chapter in entries:
                names.append(standard)
                for label in (standard, *aliases):
                    key = _fold(label)
                    if key and key not in mapping:
                        mapping[key] = standard
        index[subject] = mapping
        standards[subject] = names
    return index, standards


def normalize(subject, node):
    """返回（标准科目，标准节点，原文，是否命中）。

    科目必须落在 SUBJECTS 里。节点命中标准名或别名时，标准节点用正典名，原文保持输入。
    节点为空且科目合法时视为命中到空节点，方便错题本允许不填考点。
    """
    original_subject = str(subject or "").strip()
    original_node = str(node or "").strip()
    if original_subject not in SUBJECTS:
        return original_subject, original_node, original_node, False
    if not original_node:
        return original_subject, "", "", True
    index, _standards = _catalog()
    standard = index[original_subject].get(_fold(original_node))
    if standard is None:
        return original_subject, original_node, original_node, False
    return original_subject, standard, original_node, True


def suggest(subject, raw_node):
    """原文里若只含一个最长的标准名，建议补成它的别名。对不上就留空。"""
    _index, standards = _catalog()
    names = standards.get(str(subject or "").strip())
    if not names:
        return ""
    raw_key = _fold(raw_node)
    hits = []
    for name in names:
        name_key = _fold(name)
        if name_key and name_key != raw_key and name_key in raw_key:
            hits.append((len(name_key), name))
    if not hits:
        return ""
    hits.sort(key=lambda item: item[0], reverse=True)
    if len(hits) == 1 or hits[0][0] > hits[1][0]:
        return hits[0][1]
    return ""


def warn_miss(subject, node):
    print(f"WARN 未命中节点正典：{subject} · {node}", file=sys.stderr)
