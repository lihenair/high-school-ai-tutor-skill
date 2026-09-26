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
    if plugin.get("version") != "1.7.0":
        fail(f"plugin.json 版本应为 1.7.0，当前是 {plugin.get('version')}")
    if not (SKILL_DIR / "SKILL.md").exists():
        fail(f"缺少 {SKILL_DIR.relative_to(ROOT)}/SKILL.md")
    if not (SKILL_DIR / "modes" / "self-study.md").exists():
        fail("缺少 modes/self-study.md")
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
    map_path = SKILL_DIR / "references" / "pep-chem-bx1-ch1.md"
    if "references/pep-chem-bx1-ch1.md" not in text:
        fail("SKILL.md 应指向人教版化学必修第一册（2019）第一章的整章图文件")
    if not map_path.exists():
        fail("缺少 references/pep-chem-bx1-ch1.md")
    map_text = map_path.read_text(encoding="utf-8")
    if guard.PEP_CHEM_BX1_CH1_MARKER not in map_text:
        fail("整章图文件应含人教版化学必修第一册（2019）第一章的标记")
    bio_map_path = SKILL_DIR / "references" / "pep-bio-bx1-ch1.md"
    if "references/pep-bio-bx1-ch1.md" not in text:
        fail("SKILL.md 应指向人教版生物学必修1（2019）第一章的整章图文件")
    if not bio_map_path.exists():
        fail("缺少 references/pep-bio-bx1-ch1.md")
    bio_map_text = bio_map_path.read_text(encoding="utf-8")
    if "整章图：人教版《生物学 必修1 分子与细胞》（2019）第一章" not in bio_map_text:
        fail("整章图文件应含人教版生物学必修1（2019）第一章的标记")
    chapter_problems = guard.check_pep_chem_chapter(map_text) + guard.check_mermaid_edges(map_text)
    chapter_problems += guard.check_mermaid_edges(bio_map_text)
    chapter_problems += guard.check_mermaid_edges(text)
    if chapter_problems:
        fail("图谱未通过守卫：" + "；".join(chapter_problems))
    print("OK SKILL.md 含知识图谱规则")

    # 6. 判完一题落一条记录，下次按脚本回答薄弱点
    record_bits = ("scripts/records.py", "还没有判过的题。", "目前没有薄弱点。", "--outcome 做错", "--outcome 跳过")
    missing_bits = [w for w in record_bits if w not in text]
    if missing_bits:
        fail(f"SKILL.md 缺少判题记录规则：{'、'.join(missing_bits)}")
    if not (SKILL_DIR / "scripts" / "records.py").exists():
        fail("缺少 scripts/records.py")
    print("OK SKILL.md 含判题记录与薄弱点规则")

    if "tutor.db" not in text or "SM-2" not in text or "notebook.py review" not in text:
        fail("SKILL.md 应写明错题本数据库、SM-2 和复习命令")
    if not (SKILL_DIR / "scripts" / "notebook.py").exists():
        fail("缺少 scripts/notebook.py")
    print("OK SKILL.md 含 SM-2 错题本")
    if "已记入错题本" not in text or "漏跑这条" not in text:
        fail("SKILL.md 应写明判题记录与错题本各自的写入时机和失败条件")
    print("OK SKILL.md 写明两个库的写入时机")

    import verify
    verify_py = SKILL_DIR / "scripts" / "verify.py"
    if not verify_py.exists():
        fail("缺少 scripts/verify.py")
    verify_src = verify_py.read_text(encoding="utf-8")
    if '--expr' not in verify_src or '__main__' not in verify_src:
        fail("verify.py 应提供命令行入口（--expr 与 __main__）")

    # 非词表锚点：兜住删除类漂移（词表本身由下面两个正典遍历钉）
    for bit in ("check_math", "verify.py --expr", "退出码"):
        if bit not in text:
            fail(f"SKILL.md 缺少数学机验用语：{bit}")
    # 标记句正典住在 guard.py，逐句钉进 SKILL.md（含「未机验：未安装 SymPy」）
    for marker in guard.VERIFY_MARKERS:
        if marker not in text:
            fail(f"SKILL.md 缺少机验标记：{marker}")
    # 状态词正典住在 verify.py，逐词钉进 SKILL.md（verify 改名即红）
    for status in verify.STATUSES:
        if status not in text:
            fail(f"SKILL.md 缺少机验状态词：{status}")
    print("OK SKILL.md 含数学机验")

    # 每个脚本的命令行 flag 都要出现在 SKILL.md 里含该脚本文件名的行上。
    # 按文件名切开，避免 records.py 与 guard.py 共用 --subject 时互相放水。
    flag_re = re.compile(r'add_argument\(\s*["\'](--[a-z0-9-]+)["\']')
    saw_flags = False
    for script in sorted((SKILL_DIR / "scripts").glob("*.py")):
        flags = sorted(set(flag_re.findall(script.read_text(encoding="utf-8"))))
        if not flags:
            continue
        saw_flags = True
        doc = "\n".join(line for line in text.splitlines() if script.name in line)
        missing_flags = [flag for flag in flags if flag not in doc]
        if missing_flags:
            fail(f"SKILL.md 的 {script.name} 用法未覆盖参数：{'、'.join(missing_flags)}")
    if not saw_flags:
        fail("scripts/ 下没有命令行参数可钉")
    print("OK SKILL.md 覆盖全部脚本的命令行参数")

    import nodes
    if "modes/self-study.md" not in text:
        fail("SKILL.md 应指向 modes/self-study.md")
    for bit in ("补状态标签重发", "节点讲解请单独发一次", "此章正典待补录"):
        if bit not in text and bit not in (SKILL_DIR / "modes" / "self-study.md").read_text(encoding="utf-8"):
            fail(f"自学规则缺少用语：{bit}")
    if not (SKILL_DIR / "data" / "graph.db").exists():
        fail("缺少 skills/high-school-ai-tutor/data/graph.db")
    explore_import = re.compile(r"(^|\n)\s*(?:import|from)\s+(?:records|notebook|profile)\b")
    explore_call = re.compile(
        r"\b(?:records|notebook|profile)\s*\.\s*(?:mastery_apply|mastery_get|weak_points|add_entry|add_record)\s*\("
    )
    for script in sorted((SKILL_DIR / "scripts").glob("*.py")):
        source = script.read_text(encoding="utf-8")
        if "explore_log" not in source:
            continue
        if script.name in ("records.py", "notebook.py", "profile.py"):
            fail(f"{script.name} 把 explore_log 接到了掌握度、错题本或判题记录")
        if explore_import.search(source) or explore_call.search(source):
            fail(f"{script.name} 把 explore_log 接到了掌握度、错题本或判题记录")
    print("OK explore_log 未接入掌握度")

    canon_problems = nodes.check_nodes()
    if canon_problems:
        fail("节点正典未通过：" + "；".join(canon_problems))
    examples = re.findall(r'--subject\s+(\S+)\s+--node\s+"([^"]+)"', text)
    for subject, node in examples:
        _canon_subject, _canon_node, _raw, hit = nodes.normalize(subject, node)
        if not hit:
            fail(f"SKILL.md 示例节点不在正典：{subject} · {node}")
    if not examples:
        fail("SKILL.md 应有一条带 --subject 与 --node 的判题记录示例")
    print("OK 节点正典，SKILL.md 示例节点落在正典内")

    print("全部通过。")


if __name__ == "__main__":
    main()
