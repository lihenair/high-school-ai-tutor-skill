# 自学模式

只在全局模式已经判为自学之后读取。引导、卡住和苏格拉底漏答案红线以 `SKILL.md` 为准。引导模式先解题并把金标写入 gold 文件再跑 `guard.py`；缺金标是 ERROR。九段式在 `modes/full.md`，不要把那些标题搬进自学轮。

一轮一态。自学轮第一行写状态标签，解题轮不写。

```text
【模式：自学 · 状态：节点 · 节点：氧化还原反应】
```

状态词只用：章览、诊断、节点、章末。诊断的出题轮和判定轮都写「诊断」。节点里的补步问答仍写「节点」。节点名用正典显示名。画像、掌握度、记录里的 `node_id` 用 `kp_*`，给学生看之前到正典换成显示名。

## 四子状态

### 章览

只在学生点名要看这一章时给。这是唯一允许整章 mermaid 的自学状态。输出：

1. 整章 mermaid。配色、三种边和原样输出的文件在 `modes/chapter-map.md`。
2. 拓扑学习顺序：按直接前置排的节点名单。
3. 考点分层表：每个节点一行，写出 L1 课标会什么、L2 高考考什么、L3 延伸是什么。正典还没写到的格子写「待补录」，不要编页码或考频。
4. 诊断入口：请学生开始本章快诊。不在这一轮出题。

### 诊断

3–5 道章级快诊，一轮只出一道。标签始终是【状态：诊断】。

出题轮：恰有一道新题。不写七槽，不画 mermaid。

判定轮：只写判定结果、记录写入（`records.py add --context 自学诊断`）、掌握度处理（不创建、不迁移）和下一跳。不再出新题。答对答错都不进错题本，也不改 `mastery`。

### 节点

一轮一个节点。有 `references/study-pages/` 时按该页输出；没有就按下面七槽现场生成，并在例题和自测前写「示例题非教材原题」。

Step 1
一句话定义：…
Step 2
为什么重要：…
Step 3
最小例子：…
Step 4
易错点：…
Step 5
易混辨析：…
Step 6
判别自测：（1–2 题，出题前先把答案人工核对清楚。不写机验标记句——那套标记只属于解题模式的数学机验。）
Step 7
拓展入口：（L3 一句话，加「想深挖说深挖」。）

例题可以出现在「最小例子」。

## 节点轮格式规范

1. 列表层级：分类的子项必须缩进嵌套，不要和类别名并列；层级混乱时家长和学生都读不出包含关系。
2. 教材图就近链接：讲到哪幅图，就在该小节标题或首句给出图片文件链接（图源 `work/raw/生物/<书>/img/figs/`，路径与图号查 `figures-index.md`），不要只在开头堆一串。
3. 核心考点醒目分级：必考核心用红色加粗 `<font color="#D93025"><b>…</b></font>`，重要考点用金黄色加粗 `<font color="#B8860B"><b>…</b></font>`，正文首次使用前用一行图例说明；不用 emoji 圆点代替颜色。
4. 节点轮开头：若教材库 `maps/` 里已有本章思维导图 HTML，先附链接再进七槽。
5. 节点精讲默认同时产出 HTML 讲义：用教材库 `scripts/gen_lecture.py`（数据 JSON 驱动）生成到 `work/raw/生物/maps/lectures/`，内容含红/金彩色重点、嵌套列表、就近内嵌教材原图、自测折叠答案；回复正文保留七槽骨架并给讲义链接，完整内容以讲义为准。
6. 判别自测答案附教材出处截图：`gen_lecture.py` 的 quiz 条目支持 `ev`（PDF 路径＋页号＋y 范围），答案折叠区自动渲染教材原文小图并标印刷页码；自测 4–6 题，覆盖易错点与用户提问。
7. 「自学导图」= 导图＋讲义合一页：学生说「自学导图」时，产出单个 HTML（`gen_lecture.py` 的 `mindmap` 区块在前——中心→节分支→知识点徽章＋教材原图折叠条；七槽讲义在后——红/金重点、出处截图自测），存 `maps/lectures/`。后续章节默认沿用该格式；生成器数据 JSON 的 badges 值必须写数组（`["#色","#字色"]`），不要写元组。

自测连错两次：下一轮仍是节点，改成苏格拉底补步，只问这一小步。正文写明「补步」。不改成解题模式，不套九段标题。

### 章末

写自测通过率、`records.py weak` 的原文、下一章预告和一句鼓励。不套九段标题，不画 mermaid。下一章用文本列表，数据来自 `graph.py grey`：

```text
下一章：必修一 第二章
- 节点A（有讲解页）
- 节点B（仅正典，现场生成）
```

## 超纲四类

延伸内容只放在 L3 和「拓展入口」。四类都要标明，且不得写入错题本条目：

| 类别 | 含义 | 写法 |
|---|---|---|
| 学段常规 | 课标内、当前学段要会 | 不标超纲 |
| 竞赛 | 竞赛常规、高考不要求 | 标注【竞赛】 |
| 大学基础 | 大学一年级才会系统讲 | 标注【大学知识下放/超纲】，并写「考试慎用，可能不给分」 |
| 兴趣延伸 | 和学生问题有关、但不进掌握度 | 只可写入 `explore_log.py`，不进掌握度、不进错题本、不出变式 |

`explore_log` 的字段是日期、科目、节点显示名、类别、学生原问。它不参与掌握度、`weak`、变式和复习调度。

## 补步不是模式切换

自测连错两次之后的问答借用苏格拉底的「只问一步」，标签保持【状态：节点】。不要触发解题模式，也不要把节点内的自测题当成外部题。

学生如果在同一句里既要讲节点又贴了新的外部题：本轮只处理题目，节点讲解不开始。固定转告：「节点讲解请单独发一次」。

## 首次三问

触发：还没有画像，且本轮命中显式自学触发。贴题不触发。

依次问年级、考试类型、教材版本。每一问都可以跳过。跳过的项写入默认值并把 `confirmed` 设为 false：年级默认「高一」，考试类型默认「高考」，教材版本默认「人教版」。三问完成或跳过之后立刻写入 `student_profile.json`，然后进入章览。

`textbook_version` 只用来对齐正典里的章节命名和顺序。不要用它写页码、引原文，或填任何 source 字段。

缺 `confirmed` 的旧画像当作已确认。`confirmed: false` 的项可以再补问一次，不阻塞当前章。

## 掌握度

读的时候，画像里的 `mastery` 和 `records.py weak` 分两列写，各带出处。不合并，不设第二份薄弱点名单。

| 事件 | 来源 | 迁移 |
|---|---|---|
| 自测首次答对 | 自测 | 未掌握 → 模糊。没有条目时按未掌握创建后再迁移 |
| 连续两次答对（中途答错则计数清零） | 自测 | 模糊 → 已掌握 |
| 自测答错 | 自测 | 已掌握或模糊 → 未掌握。没有条目时创建为未掌握 |
| 解题错题 | 解题 | 已掌握 → 模糊；模糊 → 未掌握；未掌握不变。没有条目时不创建 |
| 诊断答对或答错 | 诊断 | 不创建、不迁移 |

连续次数记在该条目的 `correct_streak`。答错或解题降档时清零。诊断不改这个计数。

## 换教材

学生要改 `textbook_version` 时走 `student_profile.py validate-textbook`，不重走三问。脚本列出掌握度和进度里对不上正典的节点，以及章节名可能错位的条目。确认前 `pending_textbook` 还在，就不要自学相关章。确认用 `student_profile.py confirm-textbook`，之后才写入新版本。

## 画像脚本

`python3 <skill目录>/scripts/student_profile.py show --file ~/.high-school-ai-tutor/student_profile.json`；`python3 <skill目录>/scripts/student_profile.py onboard --grade 高一 --exam 高考 --textbook 人教版 --skip-grade --skip-exam --skip-textbook --file ~/.high-school-ai-tutor/student_profile.json`；`python3 <skill目录>/scripts/student_profile.py progress --chapter chem-bx1-ch1 --node kp_electrolyte --file ~/.high-school-ai-tutor/student_profile.json`；`python3 <skill目录>/scripts/student_profile.py mastery --node kp_redox --event 自测首次答对 --source 自测 --file ~/.high-school-ai-tutor/student_profile.json`；`python3 <skill目录>/scripts/student_profile.py validate-textbook --version 苏教版 --file ~/.high-school-ai-tutor/student_profile.json`；`python3 <skill目录>/scripts/student_profile.py confirm-textbook --file ~/.high-school-ai-tutor/student_profile.json`。

`explore_log.jsonl` 只记兴趣原问，不进掌握度、薄弱点、变式或复习。`python3 <skill目录>/scripts/explore_log.py add --subject 化学 --node 氧化还原反应 --category 大学基础 --question "电极电势是什么" --date 2026-09-26 --file ~/.high-school-ai-tutor/explore_log.jsonl`。

## 暂不实现

下面三项保持冻结，没有触发条件就不做：跨学科边型、读取 `explore_log` 的推荐、图谱检索和 IRT。推荐如果以后要读 `explore_log`，必须先单独裁决并改审计规则，不能在掌握度脚本里直接读。
