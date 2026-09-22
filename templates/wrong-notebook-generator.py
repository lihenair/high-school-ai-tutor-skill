"""
生成带格式的错题本 Excel，并支持追加或更新错题条目。

用法：
    pip install openpyxl
    python wrong-notebook-generator.py                 # 生成空白模板 错题本.xlsx（含一条示例与统计公式）
    python wrong-notebook-generator.py add entry.json  # 追加或更新一条错题
    python wrong-notebook-generator.py add -           # 从 stdin 读条目 JSON

选项：
    -o PATH    错题本路径，默认当前目录的 错题本.xlsx；放在 add 前后均可

条目 JSON 的键与「错题记录」表的列名一致（示例见 entry-example.json）：
- 必填：科目、题目摘要
- 日期 缺省为今天；编号 缺省自动递增；掌握标记 缺省「未掌握」；复习次数 缺省 0
- 错因分类 给出时必须是 审题/概念/计算/方法/表达/心态 之一
- 追加后自动在「复习计划」表按日期填好第 1/3/7/15 天
- 同一编号再次 add 视为更新该条，不产生重复行；复习后更新掌握标记也用 add
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
PLAN_HEADERS = ["编号", "题目摘要", "首次记录", "第1天", "第3天", "第7天", "第15天",
                "第1次结果", "第2次结果", "第3次结果", "第4次结果", "最终状态"]
ERROR_CATEGORIES = ("审题", "概念", "计算", "方法", "表达", "心态")
MASTERY_STATES = ("未掌握", "模糊", "已掌握")
REVIEW_OFFSETS = (1, 3, 7, 15)

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
        ws2.append(["001", "二次函数递增求参数", "2026-09-22", "2026-09-23",
                    "2026-09-25", "2026-09-29", "2026-10-07",
                    "未掌握", "", "", "", "复习中"])
        style_body(ws2, 2, 2, len(PLAN_HEADERS))
    widths2 = [6, 24, 12, 12, 12, 12, 12, 12, 12, 12, 12, 12]
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


def add_entry(wb, entry):
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

    review = [(first + timedelta(days=n)).isoformat() for n in REVIEW_OFFSETS]
    r2 = find_row_by_id(ws2, record[0])
    if r2 is None:
        ws2.append([record[0], record[6], record[1],
                    *review, "", "", "", "", "复习中"])
        r2 = ws2.max_row
    else:
        # 更新摘要与复习日期；复习结果与最终状态保留已填内容
        ws2.cell(row=r2, column=2, value=record[6])
        ws2.cell(row=r2, column=3, value=record[1])
        for c, v in zip((4, 5, 6, 7), review):
            ws2.cell(row=r2, column=c, value=v)
    style_body(ws2, r2, r2, len(PLAN_HEADERS))

    return record, review, is_update


def main():
    parser = argparse.ArgumentParser(description="错题本生成与维护")
    parser.add_argument("-o", "--output", default="错题本.xlsx", help="错题本路径")
    sub = parser.add_subparsers(dest="command")
    p_add = sub.add_parser("add", help="追加或更新一条错题")
    p_add.add_argument("entry", help="条目 JSON 文件路径，- 表示 stdin")
    p_add.add_argument("-o", "--output", default=argparse.SUPPRESS, help="错题本路径")
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

    wb = open_notebook(args.output)
    record, review, is_update = add_entry(wb, entry)
    wb.save(args.output)
    action = "已更新" if is_update else "已写入"
    print(f"{action} {args.output}：编号 {record[0]}（{record[3]}）"
          f"「{str(record[6])[:20]}…」 复习日 第1天 {review[0]} / 第3天 {review[1]} "
          f"/ 第7天 {review[2]} / 第15天 {review[3]}")


if __name__ == "__main__":
    main()
