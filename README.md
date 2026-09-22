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
- `templates/wrong-notebook-generator.py`：生成带格式的错题本 Excel
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

若工具不会按路径加载 `references/`，发题时把该科目的 `references/*.md` 与 `SKILL.md` 一并提供。

在本仓库里直接对话时，`SKILL.md` 不会自动出现在 Agent 的已安装技能列表里。学生发题、发照片或说自己选了哪个选项，都要先读根目录的 `SKILL.md`，数理化生再读对应的 `references/`。文件在仓库里，不等于这套讲题规则已经启用。

## 生成错题本 Excel

```bash
pip install openpyxl
python templates/wrong-notebook-generator.py
```

生成的 `错题本.xlsx` 含三个工作表：错题记录、复习计划、统计看板。
