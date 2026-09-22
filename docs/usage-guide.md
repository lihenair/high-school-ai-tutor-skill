# 使用指南

## 一、ZCode（推荐）

1. 把本仓库的 `SKILL.md`、`references/`、`templates/` 拷到 `~/.zcode/skills/high-school-ai-tutor/`
2. 设置 → 技能 → 刷新，打开开关
3. 输入框输入 `$`，选 `high-school-ai-tutor`，再贴题目

测科目时每次都打 `$high-school-ai-tutor`，不要赌自动触发。数学、物理、化学、生物会加载 `references/` 里对应文件；语文、英语、文综只用入口里的简表。

远程 SSH / WSL 工作区要再做一次「同步 Skill」。

## 二、Claude Code

拷到 `~/.claude/skills/high-school-ai-tutor/`，用 `/high-school-ai-tutor` 或发题触发。

## 三、ChatGPT / DeepSeek / Kimi

这些产品不会读 `references/`。入口贴 `SKILL.md` 后，再按科目追加一份：

- 数学：`references/math.md`
- 物理：`references/physics.md`
- 化学：`references/chemistry.md`
- 生物：`references/biology.md`

## 四、发题模板

```text
年级：高一
科目：数学
教材版本：人教版
当前风格：苏格拉底
题目：已知 f(x)=x²-2ax+3 在 [1,2] 上单调递增，求 a 的取值范围。
我的答案/卡点：我算出来 a≤1.5，但不确定对不对。
是否需要错题本：做完再生成
```

## 五、风格

当前只用两种。不填就是苏格拉底。只把题目贴过去，也不会改成直接给答案。

- “苏格拉底” → 只引导，不给答案
- “直接讲解” → 完整解法

费曼、范例学习、脚手架、对比教学、探究式先不用。

## 六、生成错题本

1. 「是」：完整模式或总结阶段输出条目；「做完再生成」：学生做对或说出「生成错题本」再输出；「否」则不生成
2. 没写「我的答案/卡点」时，不要编造「我的错误」
3. 复制条目，或运行 `python templates/wrong-notebook-generator.py`

## 七、常见问题

**Q：AI 编造教材章节怎么办？**
A：回复「请确认章节，不确定就写对应主题」。

**Q：变式题超纲怎么办？**
A：回复「变式题禁止超纲，核心考点必须与原题一致」。

**Q：苏格拉底模式下还是给答案？**
A：回复「切回苏格拉底，只给第一个问题，不要给完整解法」。

**Q：ZCode 里技能开着但不讲题？**
A：先打 `$high-school-ai-tutor` 再发题。设置页确认开关打开，description 未被丢弃。
