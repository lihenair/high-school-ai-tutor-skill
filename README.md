# High School AI Tutor Skill

[![CI](https://github.com/lihenair/high-school-ai-tutor-skill/actions/workflows/ci.yml/badge.svg)](https://github.com/lihenair/high-school-ai-tutor-skill/actions/workflows/ci.yml)

面向中国初高中的讲题 skill，版本 1.7.0。默认苏格拉底提问；学生要求直接讲解时给完整解法。显式说自学某一章时进入自学模式。两个模式共用考点正典、错题本和回复守卫。

规则正文在 `skills/high-school-ai-tutor/SKILL.md`。使用说明、测试标准和效果记录在 `docs/`。

## 两种模式

解题是默认。贴题就提问，不给完整答案。说「直接讲解」或「给我解析」才进入完整模式。做完或要求总结时用九段式，第 9 节是本题切片，不是整章图。判完一题记一条；苏格拉底的每一小步不记。

自学要显式说，例如「自学：第三章」「学第三章」「这一章怎么学」。一轮只处一个状态：章览、诊断、节点、章末。细则在 `modes/self-study.md`。自学回复第一行写状态标签，发送前跑 `guard.py --mode study`。贴题不会打开首次三问。有画像时，题做完再问要不要回到刚才的节点。

学生点名要某一章的图时，用 mermaid 只画这一章。蓝是概念，绿是技能，橙是实验，灰是后续章节。边只用直接前置、同章衔接、常考组合。人教版《化学 必修 第一册》（2019）第一章的图在 `references/pep-chem-bx1-ch1.md`。做题时不贴整章图。

教材版本只对齐正典里的章节名和顺序。没有课标或教材原文可引用时写不确定或「待补录」，不编页码、考频和原文。现在不做教材或考纲检索。课程标准划范围，有使用权的教材段落才供自学引用；两份材料不放进同一个向量库。图谱检索和兴趣推荐仍未启用。

## 安装

Claude Code：

```text
/plugin marketplace add lihenair/high-school-ai-tutor-skill
/plugin install high-school-ai-tutor@lihenair
```

或把 `skills/high-school-ai-tutor/` 拷到 `~/.claude/skills/`，或拷到 `~/.agents/skills/`。目录名与 `SKILL.md` 里的 `name: high-school-ai-tutor` 一致。

在本仓库里直接对话时，先读 `skills/high-school-ai-tutor/SKILL.md`，数理化生再读对应的 `references/`。文件在仓库里，不等于这套规则已经启用。

## 目录

技能在 `skills/high-school-ai-tutor/`。

| 路径 | 作用 |
|---|---|
| `SKILL.md` | 入口：模式判定、解题规则、错题本和守卫用法 |
| `modes/self-study.md` | 自学四子状态、七槽、诊断两轮、超纲四类 |
| `references/` | 分科验算与难度。文科难度在 `humanities.md` |
| `references/nodes/` | 九科正典。六列：显示名、别名、章节、L1、L2、L3。没有依据写「待补录」 |
| `references/study-pages/` | 节点页。化学必修一第一章已有，其余章按七槽现场生成 |
| `references/pep-chem-bx1-ch1.md` | 化学必修一第一章整章图 |
| `data/graph.db` | 这一章的学习顺序、直接前置和章末预告 |
| `scripts/` | 正典、画像、记录、错题本、守卫、机验、兴趣日志、章节图 |
| `templates/` | 错题本条目示例、CSV 和 Excel 导出 |
| `docs/` | 使用指南、测试标准、效果验证 |
| `tests/` | 守卫用例和脚本测试 |

## 本机数据

用户数据在 `~/.high-school-ai-tutor/`，不进仓库。

| 文件 | 用途 |
|---|---|
| `student_profile.json` | 年级、考试类型、教材版本、自学进度、掌握度 |
| `records.jsonl` | 判题记录。诊断题带 `context=自学诊断` |
| `tutor.db` | 错题本。自测错题进 SM-2；诊断错题不进 |
| `explore_log.jsonl` | 超纲原问。不参与掌握度、薄弱点、变式和复习 |

掌握度和 `records.py weak` 分开看，各写来源。只有自测能新建掌握度。解题错题只改已经存在的条目。

```bash
python3 skills/high-school-ai-tutor/scripts/records.py add --subject 化学 --node "氧化还原反应" --stem "电石除杂" --outcome 做错 --error 概念
python3 skills/high-school-ai-tutor/scripts/records.py weak
python3 skills/high-school-ai-tutor/scripts/notebook.py add entry.json
python3 skills/high-school-ai-tutor/scripts/notebook.py due
python3 skills/high-school-ai-tutor/scripts/guard.py --mode socratic reply.txt
python3 skills/high-school-ai-tutor/scripts/guard.py --mode full reply.txt
python3 skills/high-school-ai-tutor/scripts/guard.py --mode study reply.txt
python3 skills/high-school-ai-tutor/scripts/verify.py --expr "2 + 2 == 4"
```

错题本同一科目、考点和题目摘要只留一行，复习间隔用 SM-2。导出 Excel 需要 `openpyxl`，命令是 `notebook.py export -o 错题本.xlsx`。守卫退出码 0 才发送，只查红线，不查内容对错。数学完整模式把抽好的式子交给 `verify.py`；只有「矛盾」拦住发送。标记句、退出码和分科清单以 `SKILL.md` 为准。

## 本地检查

与 CI 相同，最后一项 `test_nodes.py` 只在本地跑，正典已由 `tests/check.py` 覆盖。

```bash
bash tests/run.sh
python3 tests/check.py
python3 tests/test_check_bites.py
python3 tests/test_records.py
python3 tests/test_guard_study.py
python3 tests/test_profile.py
python3 tests/test_graph.py
python3 tests/test_notebook.py
pip install 'sympy==1.13.3'
python3 tests/test_verify.py
python3 tests/test_nodes.py
```
