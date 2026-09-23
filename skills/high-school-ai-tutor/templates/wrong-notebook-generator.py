"""
生成带格式的错题本 Excel，并支持追加或更新错题条目。

用法：
    pip install openpyxl
    python wrong-notebook-generator.py                 # 生成空白模板 错题本.xlsx（含一条示例与统计公式）
    python wrong-notebook-generator.py add entry.json  # 写入 SQLite，并导出 Excel
    python wrong-notebook-generator.py add -           # 从 stdin 读条目 JSON

选项：
    -o PATH    导出的 Excel 路径，默认当前目录的 错题本.xlsx
    --db PATH  错题本数据库，默认 ~/.high-school-ai-tutor/tutor.db

条目 JSON 的键与「错题记录」表的列名一致（示例见 entry-example.json）：
- 必填：科目、题目摘要
- 同一科目、考点、题目摘要再次 add 会改这一行，不另起一条
- 错因分类 给出时必须是 审题/概念/计算/方法/表达/心态 之一
- 新错题的下次复习是记录日的后一天。复习结果用 notebook.py review，间隔按 SM-2 伸缩
"""

import argparse
import json
import os
import sys
from datetime import date, datetime, timedelta

from openpyxl import Workbook, load_workbook
from openpyxl.styles import Font, PatternFill, Alignment, Border, Side
from openpyxl.utils import get_column_letter

RECORD_HEADERS = [
    "编号", "日期", "年级", "科目", "教材版本", "章节/知识点",
    "题目摘要", "我的错误", "错因分类", "错因细化",
    "正确思路", "关键步骤", "易错点提醒",
    "变式题", "变式答案", "掌握标记", "复习次数", "备注",
]
PLAN_HEADERS = ["编号", "题目摘要", "首次记录", "下次复习", "间隔天数", "难度系数", "连续记住", "掌握标记"]
ERROR_CATEGORIES = ("审题", "概念", "计算", "方法", "表达", "心态")
MASTERY_STATES = ("未掌握", "模糊", "已掌握")

# ---------- 样式 ----------
header_font = Font(bold=True, color="FFFFFF", size=11)
header_fill = PatternFill("solid", fgColor="4472C4")
thin = Side(style="thin", color="BFBFBF")
border = Border(left=thin, right=thin, top=thin, bottom=thin)
wrap = Alignment(wrap_text=True, vertical="top")
center = Alignment(horizontal="center", vertical="center", wrap_text=True)


def style_header(ws, row, ncols):
    for c in range(1, ncols + 1):
        cell = ws.cell(row=row, column=c)
        cell.font = header_font
        cell.fill = header_fill
        cell.alignment = center
        cell.border = border


def style_body(ws, start_row, end_row, ncols):
    for r in range(start_row, end_row + 1):
        for c in range(1, ncols + 1):
            cell = ws.cell(row=r, column=c)
            cell.alignment = wrap
            cell.border = border


def build_template(include_sample=True):
    wb = Workbook()

    # ---------- Sheet 1: 错题记录 ----------
    ws1 = wb.active
    ws1.title = "错题记录"
    ws1.append(RECORD_HEADERS)
    style_header(ws1, 1, len(RECORD_HEADERS))

    if include_sample:
        sample = [
            "001", "2026-09-22", "高一", "数学", "人教版",
            "必修一 函数单调性", "f(x)=x²-2ax+3在[1,2]递增，求a",
            "得 a≤1.5", "概念", "忽略对称轴与区间左端点的关系，并把区间中点当成边界",
            "开口向上，递增区间在对称轴右侧", "对称轴 x=a，左端点为1，需 a≤1",
            "先画图，再比较对称轴和区间左端点，并检查等号", "f(x)=x²-2ax+3 在[0,3]递增，求a",
            "a≤0", "未掌握", "1", "注意等号",
        ]
        ws1.append(sample)
        style_body(ws1, 2, 2, len(RECORD_HEADERS))

    widths1 = [6, 12, 8, 8, 10, 18, 22, 18, 10, 18, 22, 22, 18, 22, 12, 10, 8, 12]
    for i, w in enumerate(widths1, 1):
        ws1.column_dimensions[get_column_letter(i)].width = w
    ws1.freeze_panes = "A2"

    # ---------- Sheet 2: 复习计划 ----------
    ws2 = wb.create_sheet("复习计划")
    ws2.append(PLAN_HEADERS)
    style_header(ws2, 1, len(PLAN_HEADERS))
    if include_sample:
        ws2.append(["001", "二次函数递增求参数", "2026-09-22", "2026-09-23", 1, 2.5, 0, "未掌握"])
        style_body(ws2, 2, 2, len(PLAN_HEADERS))
    widths2 = [8, 24, 12, 12, 10, 10, 10, 10]
    for i, w in enumerate(widths2, 1):
        ws2.column_dimensions[get_column_letter(i)].width = w
    ws2.freeze_panes = "A2"

    # ---------- Sheet 3: 统计看板 ----------
    ws3 = wb.create_sheet("统计看板")
    stats = [
        ["指标", "数值", "说明"],
        ["总错题数", "=COUNTA(错题记录!A2:A1000)", "错题记录表自动统计"],
        ["未掌握", '=COUNTIF(错题记录!P2:P1000,"未掌握")', "需重点复习"],
        ["模糊", '=COUNTIF(错题记录!P2:P1000,"模糊")', "需巩固"],
        ["已掌握", '=COUNTIF(错题记录!P2:P1000,"已掌握")', "可降低复习频率"],
        ["审题错误", '=COUNTIF(错题记录!I2:I1000,"审题")', "错因分布"],
        ["概念错误", '=COUNTIF(错题记录!I2:I1000,"概念")', "错因分布"],
        ["计算错误", '=COUNTIF(错题记录!I2:I1000,"计算")', "错因分布"],
        ["方法错误", '=COUNTIF(错题记录!I2:I1000,"方法")', "错因分布"],
        ["表达错误", '=COUNTIF(错题记录!I2:I1000,"表达")', "错因分布"],
        ["心态错误", '=COUNTIF(错题记录!I2:I1000,"心态")', "错因分布"],
        ["掌握率", '=IF(B2=0,0,B5/B2)', "已掌握/总数"],
    ]
    for row in stats:
        ws3.append(row)
    style_header(ws3, 1, 3)
    style_body(ws3, 2, len(stats), 3)
    ws3.column_dimensions["A"].width = 14
    ws3.column_dimensions["B"].width = 32
    ws3.column_dimensions["C"].width = 24

    return wb


def open_notebook(path):
    """打开已有错题本；不存在则新建不含示例的模板。"""
    if os.path.exists(path):
        wb = load_workbook(path)
        ws = wb["错题记录"]
        actual = [ws.cell(row=1, column=c).value for c in range(1, len(RECORD_HEADERS) + 1)]
        if actual != RECORD_HEADERS:
            sys.exit(f"{path} 的「错题记录」表头与模板不一致，拒绝写入以免损坏文件。")
        return wb
    return build_template(include_sample=False)


def next_id(ws):
    mx = 0
    for r in range(2, ws.max_row + 1):
        v = str(ws.cell(row=r, column=1).value or "")
        if v.isdigit():
            mx = max(mx, int(v))
    return str(mx + 1).zfill(3)


def normalize_entry(entry, ws1):
    """补默认值并校验，返回按 RECORD_HEADERS 排好序的 18 项列表。"""
    row = {h: "" for h in RECORD_HEADERS}
    for k, v in entry.items():
        if k not in RECORD_HEADERS:
            sys.exit(f"未知字段：「{k}」。字段名必须与错题记录表的列名一致。")
        row[k] = v
    for req in ("科目", "题目摘要"):
        if not str(row[req]).strip():
            sys.exit(f"必填字段缺失：{req}")
    if not row["日期"]:
        row["日期"] = date.today().isoformat()
    try:
        first = datetime.strptime(str(row["日期"]), "%Y-%m-%d").date()
    except ValueError:
        sys.exit("「日期」格式应为 YYYY-MM-DD，例如 2026-09-23。")
    if row["编号"] in ("", None):
        row["编号"] = next_id(ws1)
    else:
        digits = str(row["编号"]).split(".")[0]
        if not digits.isdigit():
            sys.exit("「编号」应为数字，例如 002。")
        row["编号"] = digits.zfill(3)
    if row["错因分类"] and row["错因分类"] not in ERROR_CATEGORIES:
        sys.exit(f"「错因分类」只能是 {'/'.join(ERROR_CATEGORIES)} 之一。")
    if row["掌握标记"] and row["掌握标记"] not in MASTERY_STATES:
        sys.exit(f"「掌握标记」只能是 {'/'.join(MASTERY_STATES)} 之一。")
    if row["复习次数"] in ("", None):
        row["复习次数"] = 0
    try:
        row["复习次数"] = int(row["复习次数"])
    except (TypeError, ValueError):
        sys.exit("「复习次数」应为整数。")
    return [row[h] for h in RECORD_HEADERS], first


def find_row_by_id(ws, entry_id):
    for r in range(2, ws.max_row + 1):
        if str(ws.cell(row=r, column=1).value) == entry_id:
            return r
    return None


def workbook_from_cards(cards):
    """按数据库里的卡片重写三张表。下次复习日来自 SM-2。"""
    wb = build_template(include_sample=False)
    ws1, ws2 = wb["错题记录"], wb["复习计划"]
    for card in cards:
        record = [
            str(card["id"]).zfill(3),
            card["created"],
            card.get("grade") or "",
            card["subject"],
            card.get("textbook") or "",
            card.get("node") or "",
            card["stem"],
            card.get("my_error") or "",
            card.get("error_type") or "",
            card.get("error_detail") or "",
            card.get("correct_approach") or "",
            card.get("key_steps") or "",
            card.get("pitfall") or "",
            card.get("variant") or "",
            card.get("variant_answer") or "",
            card.get("mastery") or "",
            card.get("reps") or 0,
            card.get("note") or "",
        ]
        ws1.append(record)
        ws2.append([
            record[0], card["stem"], card["created"], card["due"],
            card["interval_days"], card["ease"], card["reps"], card["mastery"],
        ])
    if cards:
        style_body(ws1, 2, 1 + len(cards), len(RECORD_HEADERS))
        style_body(ws2, 2, 1 + len(cards), len(PLAN_HEADERS))
    return wb


def add_entry(wb, entry):
    """保留给直接改 Excel 的旧调用。新错题的下次复习是记录日的后一天。"""
    ws1, ws2 = wb["错题记录"], wb["复习计划"]
    record, first = normalize_entry(entry, ws1)
    r1 = find_row_by_id(ws1, record[0])
    is_update = r1 is not None
    if r1 is None:
        ws1.append(record)
        r1 = ws1.max_row
    else:
        for c, v in enumerate(record, 1):
            ws1.cell(row=r1, column=c, value=v)
    style_body(ws1, r1, r1, len(RECORD_HEADERS))
    due = (first + timedelta(days=1)).isoformat()
    plan = [record[0], record[6], record[1], due, 1, 2.5, record[16], record[15]]
    r2 = find_row_by_id(ws2, record[0])
    if r2 is None:
        ws2.append(plan)
        r2 = ws2.max_row
    else:
        for c, v in enumerate(plan, 1):
            ws2.cell(row=r2, column=c, value=v)
    style_body(ws2, r2, r2, len(PLAN_HEADERS))
    return record, due, is_update


def main():
    parser = argparse.ArgumentParser(description="错题本生成与维护")
    parser.add_argument("-o", "--output", default="错题本.xlsx", help="导出的 Excel 路径")
    parser.add_argument("--db", default=None, help="错题本数据库，默认 ~/.high-school-ai-tutor/tutor.db")
    sub = parser.add_subparsers(dest="command")
    p_add = sub.add_parser("add", help="写入数据库并导出 Excel")
    p_add.add_argument("entry", help="条目 JSON 文件路径，- 表示 stdin")
    p_add.add_argument("-o", "--output", default=argparse.SUPPRESS, help="导出的 Excel 路径")
    p_add.add_argument("--db", default=argparse.SUPPRESS, help="错题本数据库")
    args = parser.parse_args()

    if args.command != "add":
        build_template().save(args.output)
        print(f"已生成：{args.output}")
        return

    if args.entry == "-":
        entry = json.load(sys.stdin)
    else:
        with open(args.entry, encoding="utf-8") as f:
            entry = json.load(f)
    if not isinstance(entry, dict):
        sys.exit("条目 JSON 应为一个对象（一组「列名: 值」）。")

    import importlib.util
    nb_path = os.path.join(os.path.dirname(__file__), "..", "scripts", "notebook.py")
    spec = importlib.util.spec_from_file_location("tutor_notebook", os.path.abspath(nb_path))
    nb = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(nb)
    db = args.db or nb.default_path()
    try:
        card = nb.add_entry(db, entry)
    except nb.NotebookError as exc:
        sys.exit(str(exc))
    workbook_from_cards(nb.list_cards(db)).save(args.output)
    print(f"已写入 {db}：编号 {card['id']}（{card['subject']}）"
          f"「{str(card['stem'])[:20]}」 下次复习 {card['due']}，并导出 {args.output}")


if __name__ == "__main__":
    main()
