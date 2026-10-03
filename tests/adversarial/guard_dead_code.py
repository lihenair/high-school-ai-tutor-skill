"""guard.py 死代码对抗检查（只用标准库）。

用法：python3 guard_dead_code.py [仓库根目录]
1. 下列名字不得再在 guard.py 里定义；
2. guard.py 里每个顶层 def / class / 赋值名，在仓库其它位置（含 guard.py 自身定义行以外）至少被引用一次。
引用按整词匹配，扫描 *.py *.sh *.md *.yml *.yaml *.txt *.jsonl（不含 .git、__pycache__）。
"""
import ast
import re
import sys
from pathlib import Path

ROOT = Path(sys.argv[1] if len(sys.argv) > 1 else ".").resolve()
GUARD = ROOT / "skills" / "high-school-ai-tutor" / "scripts" / "guard.py"
MUST_BE_GONE = ("_skip_paren", "_parse_five_scores", "PEP_CHEM_BX1_CH1_FORBIDDEN", "RULE_STUDY", "RULE_LABEL")
EXTS = {".py", ".sh", ".md", ".yml", ".yaml", ".txt", ".jsonl"}

src = GUARD.read_text(encoding="utf-8")
tree = ast.parse(src)
defined = {}
for node in tree.body:
    if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
        defined[node.name] = node.lineno
    elif isinstance(node, (ast.Assign, ast.AnnAssign)):
        targets = node.targets if isinstance(node, ast.Assign) else [node.target]
        for t in targets:
            for n in ast.walk(t):
                if isinstance(n, ast.Name):
                    defined.setdefault(n.id, node.lineno)
skip = {"main", "__all__"}

texts = []
for p in ROOT.rglob("*"):
    if p.is_file() and p.suffix in EXTS and ".git" not in p.parts and "__pycache__" not in p.parts:
        if p.name == Path(__file__).name:
            continue
        try:
            texts.append((p, p.read_text(encoding="utf-8")))
        except UnicodeDecodeError:
            pass

problems = []
for name in MUST_BE_GONE:
    if name in defined:
        problems.append(f"仍定义了 {name}（guard.py:{defined[name]}）")
for name, lineno in sorted(defined.items(), key=lambda kv: kv[1]):
    if name in skip or name.startswith("__"):
        continue
    pat = re.compile(rf"(?<![A-Za-z0-9_]){re.escape(name)}(?![A-Za-z0-9_])")
    count = 0
    for p, t in texts:
        hits = len(pat.findall(t))
        if p == GUARD:
            hits -= 1  # 定义本身
        count += max(hits, 0)
    if count == 0:
        problems.append(f"未被引用：{name}（guard.py:{lineno}）")

print("OK" if not problems else "\n".join(problems))
sys.exit(1 if problems else 0)
