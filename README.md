# High School AI Tutor Skill

一套面向中国初高中生的 AI 辅导系统提示词，含错题本、变式题、测试标准与验证记录表。

## 这是什么

一个可直接导入 Claude Code / ChatGPT / DeepSeek / Kimi 等大模型的 **system prompt skill**。它让 AI 按中国课标和主流教材讲题，同时生成结构化错题本，帮助孩子沉淀错题、分析错因、验证学习效果。

## 包含内容

- `SKILL.md`：核心系统提示词，含难度量化、一题多解、变式设计、错题本沉淀
- `templates/wrong-notebook-generator.py`：一键生成带格式的错题本 Excel
- `templates/wrong-notebook-template.csv`：错题本 CSV 模板，可直接导入
- `templates/validation-tracker.csv`：学习效果验证记录表
- `docs/testing-criteria.md`：测试标准，含五维难度、正确率、复发率
- `docs/validation-guide.md`：家庭验证方法，2-4 周可执行方案
- `docs/usage-guide.md`：使用指南，含各平台导入方法

## 快速开始

1. 下载 `SKILL.md`，复制全文
2. 粘贴到你的 AI 工具 system prompt / 自定义指令中
3. 按 SKILL.md 末尾的模板填写年级、科目、教材版本、题目
4. 完整模式下自动输出错题本条目
5. 运行 `python wrong-notebook-generator.py` 生成 Excel 错题本

## 生成错题本 Excel

```bash
pip install openpyxl
python templates/wrong-notebook-generator.py
```

生成的 `错题本.xlsx` 含三个工作表：错题记录、复习计划、统计看板。
