#!/usr/bin/env python3
"""把正典从三列补成六列。已是六列的行保持不动。

没有课标或考频依据的格子写「待补录」，不编页码，不编考频。
化学必修第一册第一章用下面写好的三句话。

    python3 migrate_canon_columns.py --check
    python3 migrate_canon_columns.py --write
"""

import argparse
import sys
from pathlib import Path

SCRIPTS = Path(__file__).resolve().parent
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))
import nodes

PENDING = (
    "待补录：课标要求以现行课标为准",
    "待补录：高考要求有依据后再写",
    "待补录：延伸不在本节点展开",
)

# 显示名 → (id, L1, L2, L3)。只覆盖有现成章节图可核对的第一章。
CHEM_CH1 = {
    "纯净物 / 混合物": (
        "kp_mixture",
        "能区分纯净物和混合物",
        "能判断给定物质属于纯净物还是混合物",
        "待补录：延伸不在本节点展开",
    ),
    "单质 / 化合物": (
        "kp_compound",
        "能按元素种类把物质分成单质和化合物，并说出氧化物、酸、碱、盐",
        "能判断物质类别并用于后续离子反应",
        "待补录：延伸不在本节点展开",
    ),
    "交叉分类法": (
        "kp_cross",
        "能用两种标准给同一物质分类",
        "能说明一种物质为什么可以同时属于两类",
        "待补录：延伸不在本节点展开",
    ),
    "分散系": (
        "kp_dispersion",
        "能区分溶液、胶体和浊液",
        "能根据分散质粒子大小判断分散系",
        "待补录：延伸不在本节点展开",
    ),
    "丁达尔效应": (
        "kp_tyndall",
        "能说出胶体有丁达尔效应",
        "能用丁达尔效应把胶体和溶液区分开",
        "待补录：延伸不在本节点展开",
    ),
    "物质的转化": (
        "kp_transform",
        "能举出物质转化的例子并指出反应类型的方向",
        "能把分类和后面的反应联系起来",
        "待补录：延伸不在本节点展开",
    ),
    "电解质与电离": (
        "kp_electrolyte",
        "能判断电解质和非电解质，并说出电离",
        "能根据导电和电离判断电解质",
        "待补录：延伸不在本节点展开",
    ),
    "离子方程式": (
        "kp_ion_eq",
        "能书写简单离子方程式",
        "能拆写可溶强电解质并检查原子守恒和电荷守恒",
        "待补录：延伸不在本节点展开",
    ),
    "离子反应发生的条件": (
        "kp_ion_cond",
        "能说出生成沉淀、气体或弱电解质时离子反应可以发生",
        "能判断一个离子方程式能不能发生",
        "待补录：延伸不在本节点展开",
    ),
    "离子反应": (
        "kp_ion",
        "能说出离子反应是有离子参加的反应",
        "能把离子反应和离子方程式对应起来",
        "待补录：延伸不在本节点展开",
    ),
    "化合价升降与电子转移": (
        "kp_valence",
        "能根据化合价升降判断有没有电子转移",
        "能标出反应中化合价变化的元素",
        "待补录：延伸不在本节点展开",
    ),
    "氧化剂 / 还原剂": (
        "kp_agent",
        "能根据化合价变化指出氧化剂和还原剂",
        "能在给定反应里判断氧化剂和还原剂",
        "待补录：延伸不在本节点展开",
    ),
    "四种基本反应类型与氧化还原的关系": (
        "kp_basic4",
        "能说出置换反应都是氧化还原反应，复分解都不是",
        "能判断四种基本反应类型里哪些属于氧化还原",
        "待补录：延伸不在本节点展开",
    ),
    "氧化还原反应": (
        "kp_redox",
        "能判断一个反应是不是氧化还原反应",
        "能用化合价升降或电子转移完成常规判断",
        "延伸到电极电势（大学基础）",
    ),
}


def convert_text(text):
    out = []
    changed = False
    for raw in text.splitlines():
        line = raw.strip()
        if not line or line.startswith("#"):
            out.append(raw)
            continue
        parts = [part.strip() for part in line.split("|")]
        if len(parts) == 6:
            out.append(raw)
            continue
        if len(parts) != 3 or not parts[0] or not parts[2]:
            out.append(raw)
            continue
        spec = CHEM_CH1.get(parts[0])
        if spec:
            node_id, l1, l2, l3 = spec
            comment = f"# id {node_id} {parts[0]}"
            if not out or out[-1].strip() != comment:
                out.append(comment)
            out.append(" | ".join((parts[0], parts[1], parts[2], l1, l2, l3)))
        else:
            out.append(" | ".join((parts[0], parts[1], parts[2], *PENDING)))
        changed = True
    suffix = "\n" if text.endswith("\n") or out else ""
    return "\n".join(out) + suffix, changed


def main(argv=None):
    parser = argparse.ArgumentParser(description="正典三列补六列")
    parser.add_argument("--check", action="store_true", help="只报告还没补成六列的行")
    parser.add_argument("--write", action="store_true", help="写回 references/nodes")
    args = parser.parse_args(argv)
    if not args.check and not args.write:
        parser.error("指定 --check 或 --write")
    problems = []
    for _subject, filename in nodes.SUBJECT_FILES:
        path = nodes.NODES_DIR / filename
        original = path.read_text(encoding="utf-8")
        converted, changed = convert_text(original)
        if args.check and changed:
            problems.append(filename)
        if args.write and changed:
            path.write_text(converted, encoding="utf-8")
            print(f"已写 {filename}")
        elif args.write:
            print(f"跳过 {filename}")
    if args.check:
        if problems:
            print("仍有三列：" + "、".join(problems))
            return 1
        extra = nodes.check_nodes()
        if extra:
            print("正典未通过：" + "；".join(extra))
            return 1
        print("六列检查通过。")
    return 0


if __name__ == "__main__":
    sys.exit(main())
