# High School AI Tutor Skill

面向中国初高中的讲题 skill。默认苏格拉底式提问；需要完整结果时再切直接讲解。数学、物理、化学、生物已拆成按需加载的分科说明。

## 这是什么

一个可安装到 **ZCode / Claude Code**，也可粘贴进 ChatGPT、DeepSeek、Kimi 的辅导 skill。它按课标和主流教材讲题，生成结构化错题本，并在完整模式下给出变式。

仓库根目录就是 skill 包：`SKILL.md` 是入口，`references/` 是分科说明。

## 包含内容

- `SKILL.md`：入口。含 YAML 头、风格判定、错题本规则；语文、英语、文综暂用简表
- `references/math.md`：数学难度、加权评分、定义域与端点验算
- `references/physics.md`：物理难度、方向与单位验算
- `references/chemistry.md`：化学难度、配平与守恒验算
- `references/biology.md`：生物难度、术语与实验核对
- `templates/wrong-notebook-generator.py`：生成带格式的错题本 Excel
- `templates/wrong-notebook-template.csv`：错题本 CSV
- `templates/validation-tracker.csv`：学习效果记录表
- `docs/testing-criteria.md`、`docs/validation-guide.md`、`docs/usage-guide.md`

## 在 ZCode 里安装

```bash
mkdir -p ~/.zcode/skills/high-school-ai-tutor
cp SKILL.md ~/.zcode/skills/high-school-ai-tutor/
cp -r references templates ~/.zcode/skills/high-school-ai-tutor/
```

打开 ZCode → 设置 → 技能 → 刷新，打开该技能。测题时输入：

```text
$high-school-ai-tutor
年级：高一
科目：数学
当前风格：苏格拉底
题目：……
```

## 在 Claude Code 里安装

```bash
mkdir -p ~/.claude/skills/high-school-ai-tutor
cp SKILL.md ~/.claude/skills/high-school-ai-tutor/
cp -r references templates ~/.claude/skills/high-school-ai-tutor/
```

对话里用 `/high-school-ai-tutor`，或把题目发给它让 description 触发。

## 仍然可以当长提示词

把 `SKILL.md` 贴进自定义指令后，模型不会自动读 `references/`。数、理、化、生请把对应 `references/*.md` 一并贴上。ZCode / Claude Code 的 `$` 或 `/` 调用才会按需加载分科文件。

## 生成错题本 Excel

```bash
pip install openpyxl
python templates/wrong-notebook-generator.py
```

生成的 `错题本.xlsx` 含三个工作表：错题记录、复习计划、统计看板。
