#!/usr/bin/env python3
"""guard.py regression baseline (frozen from main 4a5cb53).

Usage (from anywhere; defaults assume this file lives at <repo>/tests/baseline/):
    python3 tests/baseline/run_baseline.py [--repo PATH] [--guard PATH] [--jsonl PATH] [-v] [--gold-mode auto|off]

Rules:
  FAIL (exit 1): a case main blocked (main_exit != 0) is now allowed (exit 0),
                 or any of main's ERROR codes is no longer emitted,
                 or guard crashes (Traceback / exit not in {0,1}).
  WARN (exit 0): a case main allowed is now blocked. Reported with a count.
  EXEMPT: ids in tests/baseline/exempt.txt are reported but never fail.
          Changing exempt.txt requires maintainer approval.

Gold handling (--gold-mode auto, default): main's CLI has no --gold. If guard.py --help
advertises --gold / --no-gold, socratic cases that carry a "gold" field are run with a
temporary gold file (answer:/options: lines); other socratic cases are run with --no-gold.
If guard advertises --stem-file, cases with "stem" pass it. --gold-mode off never adds these.
Stdlib only.
"""
import argparse
import json
import os
import re
import subprocess
import sys
import tempfile
from collections import Counter
from pathlib import Path

HERE = Path(__file__).resolve().parent
ERR_RE = re.compile(r"^\[ERROR\] (\w+)", re.MULTILINE)


def load_exempt(path):
    """Map case id -> reason. Blank lines and full-line comments ignored."""
    exempt = {}
    if not path.is_file():
        return exempt
    for raw in path.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        if "#" in line:
            cid, reason = line.split("#", 1)
            cid, reason = cid.strip(), reason.strip()
        else:
            cid, reason = line, ""
        if cid:
            exempt[cid] = reason
    return exempt


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--repo", default=str(HERE.parent.parent))
    ap.add_argument("--guard", default="")
    ap.add_argument("--jsonl", default=str(HERE / "guard_baseline.jsonl"))
    ap.add_argument("--exempt", default=str(HERE / "exempt.txt"))
    ap.add_argument("--gold-mode", choices=["auto", "off"], default="auto")
    ap.add_argument("-v", "--verbose", action="store_true")
    args = ap.parse_args()

    repo = Path(args.repo).resolve()
    guard = Path(args.guard).resolve() if args.guard else (
        repo / "skills/high-school-ai-tutor/scripts/guard.py"
    )
    if not guard.is_file():
        print(f"guard.py not found: {guard}", file=sys.stderr)
        return 2
    help_text = subprocess.run(
        [sys.executable, str(guard), "--help"],
        capture_output=True,
        text=True,
        cwd=repo,
        check=False,
    ).stdout
    use_gold = args.gold_mode == "auto" and "--gold" in help_text and "--no-gold" in help_text
    use_stem = args.gold_mode == "auto" and "--stem-file" in help_text
    exempt = load_exempt(Path(args.exempt))

    jsonl_path = Path(args.jsonl)
    with jsonl_path.open(encoding="utf-8") as fh:
        cases = [json.loads(line) for line in fh if line.strip()]
    fails, warns, exempts = [], [], []
    per_cat = Counter()
    with tempfile.TemporaryDirectory() as tmp:
        tmp_path = Path(tmp)
        for case in cases:
            per_cat[case["category"]] += 1
            reply = tmp_path / "reply.txt"
            reply.write_text(case["input"], encoding="utf-8")
            cmd = [sys.executable, str(guard), "--mode", case["mode"], *case.get("args", [])]
            if case["mode"] == "socratic" and use_gold:
                if case.get("gold"):
                    gold = tmp_path / "gold.txt"
                    lines = [f"answer: {g}" for g in case["gold"]]
                    if case.get("options"):
                        lines.append(f"options: {case['options']}")
                    gold.write_text("\n".join(lines) + "\n", encoding="utf-8")
                    cmd += ["--gold", str(gold)]
                else:
                    cmd += ["--no-gold"]
            if case["mode"] == "socratic" and use_stem and case.get("stem"):
                stem = tmp_path / "stem.txt"
                stem.write_text(case["stem"], encoding="utf-8")
                cmd += ["--stem-file", str(stem)]
            cmd.append(str(reply))
            proc = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                cwd=repo,
                env={**os.environ, "PYTHONIOENCODING": "utf-8"},
                check=False,
            )
            codes = set(ERR_RE.findall(proc.stdout))
            crashed = "Traceback" in proc.stderr or proc.returncode not in (0, 1)
            missing = sorted(set(case["main_codes"]) - codes)
            snippet = case["input"][:60].replace("\n", "⏎")
            row = (
                case["id"],
                case["category"],
                case["main_exit"],
                proc.returncode,
                case["main_codes"],
                sorted(codes),
                snippet,
            )
            tag = None
            if crashed:
                tag = "CRASH"
            elif case["main_exit"] != 0 and (proc.returncode == 0 or missing):
                tag = "ALLOWED" if proc.returncode == 0 else "MISSING:" + ",".join(missing)
            elif case["main_exit"] == 0 and proc.returncode != 0:
                warns.append(("NEWBLOCK",) + row)
            if tag:
                if case["id"] in exempt:
                    exempts.append((tag,) + row)
                else:
                    fails.append((tag,) + row)

    print(f"guard: {guard}")
    print(f"cases: {len(cases)}  " + "  ".join(f"{k}={v}" for k, v in sorted(per_cat.items())))
    print(f"gold flags: {'on' if use_gold else 'off'}  stem-file: {'on' if use_stem else 'off'}")
    loaded = ", ".join(sorted(exempt)) if exempt else "(none)"
    print(f"exempt loaded: {len(exempt)}  {loaded}")
    for kind, title in ((fails, "FAIL"), (warns, "WARN"), (exempts, "EXEMPT")):
        by = Counter(r[2] for r in kind)
        extra = ""
        if kind:
            extra = "  (" + ", ".join(f"{k}={v}" for k, v in sorted(by.items())) + ")"
        print(f"{title}: {len(kind)}" + extra)
        show_rows = kind is fails or kind is exempts or args.verbose
        if show_rows:
            for r in kind:
                print(
                    f"  [{title}] {r[1]} {r[2]} {r[0]} "
                    f"main_exit={r[3]} now={r[4]} main={r[5]} now={r[6]} | {r[7]}"
                )
    return 1 if fails else 0


if __name__ == "__main__":
    sys.exit(main())
