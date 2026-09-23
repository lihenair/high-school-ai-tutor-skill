#!/usr/bin/env python3
"""仓库结构与插件清单校验：CI 与本地跑同一份逻辑。用法：python3 tests/check.py"""

import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SKILL_DIR = ROOT / "skills" / "high-school-ai-tutor"
SKILL_NAME = "high-school-ai-tutor"


def fail(msg):
    print(f"✗ {msg}")
    sys.exit(1)


def main():
    # 1. 插件清单存在且是合法 JSON
    for rel in (".claude-plugin/marketplace.json", ".claude-plugin/plugin.json"):
        path = ROOT / rel
        if not path.exists():
            fail(f"缺少 {rel}")
        try:
            json.loads(path.read_text(encoding="utf-8"))
        except json.JSONDecodeError as e:
            fail(f"{rel} 不是合法 JSON：{e}")
        print(f"OK {rel}")

    market = json.loads((ROOT / ".claude-plugin/marketplace.json").read_text(encoding="utf-8"))
    plugin = json.loads((ROOT / ".claude-plugin/plugin.json").read_text(encoding="utf-8"))

    # 2. 两份清单交叉一致：插件名、source 指向、技能目录存在
    entry = market["plugins"][0]
    if entry["name"] != plugin["name"]:
        fail(f"插件名不一致：marketplace={entry['name']} plugin.json={plugin['name']}")
    if entry["source"] != "./":
        fail(f"单插件仓库 source 应为 ./，当前是 {entry['source']}")
    if plugin.get("version") != entry.get("version") or plugin.get("version") != market.get("version"):
        fail(
            "版本不一致："
            f"plugin.json={plugin.get('version')} "
            f"marketplace 插件={entry.get('version')} "
            f"marketplace={market.get('version')}"
        )
    if plugin.get("version") != "1.2.0":
        fail(f"plugin.json 版本应为 1.2.0，当前是 {plugin.get('version')}")
    if not (SKILL_DIR / "SKILL.md").exists():
        fail(f"缺少 {SKILL_DIR.relative_to(ROOT)}/SKILL.md")
    print("OK 清单交叉一致，技能目录存在")

    # 3. SKILL.md frontmatter：name 与目录名一致、description 非空
    text = (SKILL_DIR / "SKILL.md").read_text(encoding="utf-8")
    m = re.match(r"^---\n(.*?)\n---\n", text, re.S)
    if not m:
        fail("SKILL.md 缺少 YAML frontmatter")
    fm = m.group(1)
    name = re.search(r"^name:\s*(\S+)", fm, re.M)
    desc = re.search(r"^description:\s*(.+)", fm, re.M)
    if not name or name.group(1) != SKILL_NAME:
        fail(f"frontmatter name 应为 {SKILL_NAME}，当前是 {name.group(1) if name else '缺失'}")
    if SKILL_DIR.name != SKILL_NAME:
        fail(f"技能目录名应为 {SKILL_NAME}，当前是 {SKILL_DIR.name}")
    if not desc or len(desc.group(1).strip()) < 20:
        fail("frontmatter description 缺失或过短（少于 20 字）")
    print("OK SKILL.md frontmatter 与目录名一致")

    # 4. SKILL.md 引用的分科文件都存在
    for ref in re.findall(r"references/([a-z]+\.md)", text):
        if not (SKILL_DIR / "references" / ref).exists():
            fail(f"SKILL.md 引用的 references/{ref} 不存在")
    print("OK SKILL.md 引用的分科文件齐全")

    # 5. 自学知识图谱：触发、边类型、做题时不整张贴出
    required = ("知识图谱", "mermaid", "直接前置", "同章衔接", "常考组合")
    missing = [w for w in required if w not in text]
    if missing:
        fail(f"SKILL.md 缺少知识图谱规则用语：{ '、'.join(missing) }")
    if "不要把整张图谱贴出来" not in text:
        fail("SKILL.md 应写明做题时不要把整张图谱贴出来")
    if "答题时怎么用" not in text or "拼盘题" not in text:
        fail("SKILL.md 应写明答题时怎么用图谱，并区分拼盘题与换考点")
    if "本题图谱" not in text:
        fail("SKILL.md 应要求总结第 9 节附本题图谱")
    sys.path.insert(0, str(SKILL_DIR / "scripts"))
    import guard
    if guard.PEP_CHEM_BX1_CH1_MARKER not in text:
        fail("SKILL.md 应含人教版化学必修第一册（2019）第一章的整章图标记")
    chapter_problems = guard.check_pep_chem_chapter(text) + guard.check_mermaid_edges(text)
    if chapter_problems:
        fail("SKILL.md 里的图谱未通过守卫：" + "；".join(chapter_problems))
    print("OK SKILL.md 含知识图谱规则")

    print("全部通过。")


if __name__ == "__main__":
    main()
