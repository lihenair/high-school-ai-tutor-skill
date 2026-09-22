# High School AI Tutor Skill

面向中国初高中的讲题 skill。默认苏格拉底式提问；需要完整结果时再切直接讲解。数学、物理、化学、生物已拆成按需加载的分科说明，各科使用自己的难度加权。

## 这是什么

把本目录安装到支持 `SKILL.md` 的 Agent，或把入口和对应分科文件一并提供给对话。按课标和主流教材讲题，生成结构化错题本，并在完整模式下给出变式。

仓库根目录就是 skill 包：`SKILL.md` 是入口，`references/` 是分科说明。

## 包含内容

- `SKILL.md`：入口。含 YAML 头、风格判定、错题本规则；语文、英语、文综的难度表暂放在这里
- `references/math.md`：数学难度加权、定义域与端点验算
- `references/physics.md`：物理难度加权、方向与单位验算
- `references/chemistry.md`：化学难度加权、配平与守恒验算
- `references/biology.md`：生物难度加权、术语与实验核对
- `templates/wrong-notebook-generator.py`：生成并维护错题本 Excel（模板生成、追加与更新条目）
- `templates/entry-example.json`：`add` 子命令的条目写法示例
- `templates/wrong-notebook-template.csv`：错题本 CSV
- `templates/validation-tracker.csv`：学习效果记录表
- `docs/testing-criteria.md`、`docs/validation-guide.md`、`docs/usage-guide.md`

## 安装

把 `SKILL.md`、`references/`、`templates/` 拷到该 Agent 的 skills 目录，目录名用 `high-school-ai-tutor`。在设置里刷新并启用后，用该工具调用 skill 的方式点名 `high-school-ai-tutor`，再贴题目。

```bash
mkdir -p "<skills-dir>/high-school-ai-tutor"
cp SKILL.md "<skills-dir>/high-school-ai-tutor/"
cp -r references templates "<skills-dir>/high-school-ai-tutor/"
```

注意：直接 `git clone` 本仓库得到的目录名是 `high-school-ai-tutor-skill`，与 `SKILL.md` 里的 `name: high-school-ai-tutor` 不一致；部分 Agent 要求目录名与 name 一致，clone 后请把目录重命名为 `high-school-ai-tutor`，或按上面的命令拷贝。

若工具不会按路径加载 `references/`，发题时把该科目的 `references/*.md` 与 `SKILL.md` 一并提供。

## 生成与维护错题本 Excel

```bash
pip install openpyxl
python templates/wrong-notebook-generator.py                 # 生成空白模板（含示例与统计公式）
python templates/wrong-notebook-generator.py add entry.json  # 追加或更新一条错题
```

`add` 的条目 JSON 字段与「错题记录」表列名一致（写法见 `templates/entry-example.json`）：`科目`、`题目摘要` 必填；`日期` 缺省今天，`编号` 自动递增，`掌握标记` 缺省「未掌握」，`错因分类` 必须是 审题/概念/计算/方法/表达/心态 之一。追加时自动在「复习计划」表按日期排好第 1/3/7/15 天。同一 `编号` 再次 `add` 是更新该条，不产生重复行；复习后更新掌握标记也走 `add`。`-o PATH` 指定错题本路径，默认当前目录的 `错题本.xlsx`。

`错题本.xlsx` 含三个工作表：错题记录、复习计划、统计看板（公式自动统计到第 1000 行）。
