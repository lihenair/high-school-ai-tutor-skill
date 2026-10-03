#!/usr/bin/env python3
# ruff: noqa
"""错题本损坏库对抗用例（随 PR 入库，可改写成 pytest）。

用法：N=skills/high-school-ai-tutor/scripts/notebook.py PY=python3 python3 nb_cases.py
每条：建一个场景库 → 跑一个子命令 → 断言 退出码 / 无 Traceback / stderr 关键词 / 库文件字节不变 / 不新建文件。
"""
import hashlib, json, os, shutil, sqlite3, stat, subprocess, sys, tempfile, threading, time
from pathlib import Path

N = os.environ.get("N", "skills/high-school-ai-tutor/scripts/notebook.py")
PY = os.environ.get("PY", sys.executable)
ENTRY = {"科目": "数学", "章节/知识点": "函数单调性", "题目摘要": "f(x)=x²-2ax 在 [1,+∞) 递增求 a",
         "我的错误": "对称轴写反", "错因分类": "概念"}


def run(args, cwd, env=None):
    return subprocess.run([PY, str(Path(N).resolve()), *args], cwd=cwd, capture_output=True, text=True,
                          env={**os.environ, **(env or {})}, timeout=60)


def good_db(path, when="2026-01-01"):
    entry = Path(path).with_suffix(".json")
    entry.write_text(json.dumps(ENTRY, ensure_ascii=False), encoding="utf-8")
    r = run(["add", str(entry), "--db", str(path)], cwd=Path(path).parent)
    assert r.returncode == 0, r.stderr
    entry.unlink()
    c = sqlite3.connect(path); c.execute("UPDATE cards SET due=?", (when,)); c.commit(); c.close()


def mk_garbage(p): Path(p).write_bytes(os.urandom(4096))
def mk_trunc(p):
    good_db(p); data = Path(p).read_bytes(); Path(p).write_bytes(data[:600])
def mk_header_only(p): Path(p).write_bytes(b"SQLite format 3\x00" + b"\x00" * 84)
def mk_text(p): Path(p).write_text("这不是数据库\n", encoding="utf-8")
def mk_empty(p): Path(p).write_bytes(b"")
def mk_no_cards(p):
    c = sqlite3.connect(p); c.execute("CREATE TABLE notes(id INTEGER PRIMARY KEY, t TEXT)"); c.commit(); c.close()
def mk_missing_cols(p):
    c = sqlite3.connect(p); c.execute("CREATE TABLE cards(id INTEGER PRIMARY KEY, subject TEXT, stem TEXT)")
    c.execute("INSERT INTO cards(subject, stem) VALUES('数学','x')"); c.commit(); c.close()
def mk_bad_ease(p):
    good_db(p); c = sqlite3.connect(p); c.execute("UPDATE cards SET ease='abc'"); c.commit(); c.close()
def mk_bad_due(p):
    good_db(p); c = sqlite3.connect(p); c.execute("UPDATE cards SET due='明天'"); c.commit(); c.close()
def mk_future(p):
    good_db(p); c = sqlite3.connect(p); c.execute("UPDATE meta SET value='9' WHERE key='schema_version'"); c.commit(); c.close()
def mk_bad_version(p):
    good_db(p); c = sqlite3.connect(p); c.execute("UPDATE meta SET value='abc' WHERE key='schema_version'"); c.commit(); c.close()
def mk_legacy_v0(p):
    """v0 旧库：没有 meta 表，cards 没有 raw_node / verify_status 两列（与 #31 之前的真实建表一致）。"""
    c = sqlite3.connect(p)
    c.execute("""CREATE TABLE cards (
        id INTEGER PRIMARY KEY AUTOINCREMENT, created TEXT NOT NULL, grade TEXT DEFAULT '',
        subject TEXT NOT NULL, textbook TEXT DEFAULT '', node TEXT DEFAULT '', stem TEXT NOT NULL,
        my_error TEXT DEFAULT '', error_type TEXT DEFAULT '', error_detail TEXT DEFAULT '',
        correct_approach TEXT DEFAULT '', key_steps TEXT DEFAULT '', pitfall TEXT DEFAULT '',
        variant TEXT DEFAULT '', variant_answer TEXT DEFAULT '', mastery TEXT NOT NULL, ease REAL NOT NULL,
        interval_days INTEGER NOT NULL, reps INTEGER NOT NULL, due TEXT NOT NULL, last_review TEXT DEFAULT '',
        note TEXT DEFAULT '', UNIQUE (subject, node, stem))""")
    c.execute("INSERT INTO cards(created, subject, node, stem, mastery, ease, interval_days, reps, due) "
              "VALUES('2025-12-01','数学','函数单调性','旧题','未掌握',2.5,1,0,'2026-01-01')")
    c.commit(); c.close()
def mk_dir(p): os.mkdir(p)
def mk_readonly(p):
    good_db(p); os.chmod(p, stat.S_IRUSR | stat.S_IRGRP)
def mk_good(p): good_db(p)

CORRUPT = {"garbage": mk_garbage, "truncated": mk_trunc, "header_only": mk_header_only, "text": mk_text,
           "no_cards_table": mk_no_cards, "missing_columns": mk_missing_cols, "future_version": mk_future,
           "bad_version": mk_bad_version, "directory": mk_dir}

CASES = []
# 1 损坏库：四个子命令都要干净报错、退出码 3、不改库
for name in CORRUPT:
    for cmd in ("due", "export", "add", "review"):
        CASES.append(dict(id=f"c-{name}-{cmd}", make=name, cmd=cmd, rc=3, unchanged=True))
# 2 坏行：due / export 报错退出码 3，点名坏行，不改库；export 不留半个文件
for name in ("bad_ease", "bad_due"):
    CASES.append(dict(id=f"r-{name}-due", make=name, cmd="due", rc=3, unchanged=True, stderr_has=["1"]))
    CASES.append(dict(id=f"r-{name}-export", make=name, cmd="export", rc=3, unchanged=True, no_output=True))
# 3 不存在 / 空文件：读命令不建库
CASES += [
    dict(id="m-missing-due", make=None, cmd="due", rc=0, no_create=True),
    dict(id="m-missing-export", make=None, cmd="export", rc=2, no_create=True, no_output=True),
    dict(id="m-missing-review", make=None, cmd="review", rc=2, no_create=True),
    dict(id="m-empty-due", make="empty", cmd="due", rc=0, unchanged=True),
    dict(id="m-empty-export", make="empty", cmd="export", rc=2, unchanged=True, no_output=True),
]
# 4 正常库：读命令字节不变；只读文件也能读；旧版 v0 库读时不迁移
CASES += [
    dict(id="g-good-due", make="good", cmd="due", rc=0, unchanged=True, stdout_has=["函数单调性"]),
    dict(id="g-good-export", make="good", cmd="export", rc=0, unchanged=True),
    dict(id="g-readonly-due", make="readonly", cmd="due", rc=0, unchanged=True, stdout_has=["函数单调性"]),
    dict(id="g-readonly-export", make="readonly", cmd="export", rc=0, unchanged=True),
    dict(id="g-legacy-due", make="legacy_v0", cmd="due", rc=0, unchanged=True, stdout_has=["函数单调性"]),
    dict(id="g-legacy-export", make="legacy_v0", cmd="export", rc=0, unchanged=True),
    dict(id="g-legacy-add", make="legacy_v0", cmd="add", rc=0, unchanged=False),
    dict(id="g-readonly-add", make="readonly", cmd="add", rc=3, unchanged=True),
]
# 5 导出目标不可写：退出码 2，不改库；已存在的输出文件导出失败时不被覆盖
CASES += [
    dict(id="x-outdir-missing", make="good", cmd="export", out="nodir/错题本.xlsx", rc=2, unchanged=True),
    dict(id="x-keep-old-output", make="bad_ease", cmd="export", preexisting_output=True, rc=3, unchanged=True),
]
# 6 锁：另一个连接持有排他锁时，读写命令都干净报错（退出码 3），不挂死
CASES += [dict(id=f"l-locked-{cmd}", make="good", cmd=cmd, rc=3, unchanged=True, lock=True) for cmd in ("due", "add")]
# 7 缺 openpyxl：export 退出码 4，提示安装，不改库
CASES += [dict(id="d-no-openpyxl", make="good", cmd="export", rc=4, unchanged=True, no_openpyxl=True, stderr_has=["openpyxl"])]

MAKERS = {**CORRUPT, "bad_ease": mk_bad_ease, "bad_due": mk_bad_due, "empty": mk_empty, "good": mk_good,
          "readonly": mk_readonly, "legacy_v0": mk_legacy_v0}


def digest(p):
    p = Path(p)
    if p.is_dir():
        return "dir"
    if not p.exists():
        return None
    try:
        return hashlib.sha256(p.read_bytes()).hexdigest()
    except PermissionError:
        st = p.stat()
        return f"noperm:{st.st_size}:{st.st_mtime_ns}:{st.st_mode}"


def one(case):
    td = Path(tempfile.mkdtemp())
    try:
        db = td / "tutor.db"
        if case["make"]:
            MAKERS[case["make"]](str(db))
        before = digest(db)
        files_before = sorted(x.name for x in td.iterdir())
        out = td / case.get("out", "错题本.xlsx")
        if case.get("preexisting_output"):
            out.write_bytes(b"OLD")
        args = {"due": ["due", "--date", "2026-12-31"], "export": ["export", "-o", str(out)],
                "add": ["add", str(td / "e.json")], "review": ["review", "--id", "1", "--result", "已掌握"]}[case["cmd"]]
        if case["cmd"] == "add":
            (td / "e.json").write_text(json.dumps({**ENTRY, "题目摘要": "新题"}, ensure_ascii=False), encoding="utf-8")
            files_before = sorted(x.name for x in td.iterdir())
        args += ["--db", str(db)]
        env = {}
        if case.get("no_openpyxl"):
            shim = td / "shim"; shim.mkdir(); (shim / "openpyxl.py").write_text("raise ImportError('no openpyxl')\n")
            env["PYTHONPATH"] = str(shim)
        holder = None
        if case.get("lock"):
            holder = sqlite3.connect(db, timeout=0); holder.execute("BEGIN EXCLUSIVE")
        t0 = time.time()
        r = run(args, cwd=td, env=env)
        elapsed = time.time() - t0
        if holder:
            holder.rollback(); holder.close()
        problems = []
        if r.returncode != case["rc"]:
            problems.append(f"rc={r.returncode} want {case['rc']}")
        if "Traceback" in r.stderr or "Traceback" in r.stdout:
            problems.append("Traceback")
        if case["rc"] != 0 and not r.stderr.strip():
            problems.append("no stderr message")
        if case.get("unchanged") and digest(db) != before:
            problems.append("db modified")
        if case.get("no_create") and db.exists():
            problems.append("db created by read command")
        if case.get("no_output") and out.exists():
            problems.append("output written")
        if case.get("preexisting_output") and out.read_bytes() != b"OLD":
            problems.append("old output clobbered")
        if case["cmd"] in ("due", "export") and case["rc"] != 0 or case.get("unchanged"):
            extra = sorted(set(x.name for x in td.iterdir()) - set(files_before) - {out.name, "shim"})
            extra = [x for x in extra if not x.endswith(".xlsx")]
            if extra:
                problems.append(f"left files {extra}")
        for s in case.get("stderr_has", []):
            if s not in r.stderr:
                problems.append(f"stderr lacks {s!r}")
        for s in case.get("stdout_has", []):
            if s not in r.stdout:
                problems.append(f"stdout lacks {s!r}")
        if elapsed > 20:
            problems.append(f"slow {elapsed:.0f}s")
        return problems, r
    finally:
        for p in td.rglob("*"):
            try: os.chmod(p, 0o700 if p.is_dir() else 0o600)
            except OSError: pass
        shutil.rmtree(td, ignore_errors=True)


if __name__ == "__main__":
    bad = 0
    for c in CASES:
        probs, r = one(c)
        if probs:
            bad += 1
            print("FAIL", c["id"], "; ".join(probs), "|", (r.stderr.strip().splitlines() or [""])[-1][:90])
    print(f"{len(CASES) - bad}/{len(CASES)}")
    sys.exit(1 if bad else 0)
