# Guard regression baseline

Frozen snapshot of `guard.py` on **main `4a5cb53`**: 699 cases in
`guard_baseline.jsonl` (each row records `id`, `mode`, `input`, `main_exit`,
and `main_codes`). The runner re-executes current `guard.py` and compares.

This suite does **not** change skill logic. It only fails CI when current
guard is *weaker* than that snapshot.

## How to run

From the repo root (stdlib only; no extra packages):

```text
python3 tests/baseline/run_baseline.py
```

Optional flags: `--repo PATH`, `--guard PATH`, `--jsonl PATH`, `--exempt PATH`,
`-v` (print every WARN row), `--gold-mode auto|off`.

`tests/run.sh` invokes the same command, so CI fails on any regression.

## Rule: blocked-on-main must stay blocked

- **FAIL (exit 1):** a case main blocked (`main_exit != 0`) is now allowed
  (exit 0), **or** any of main's ERROR codes is no longer emitted, **or**
  guard crashes (`Traceback` / exit not in `{0,1}`).
- **WARN (exit 0):** a case main allowed is now blocked. The run still
  succeeds.

## How WARNs are shown

The summary always prints a `WARN: N` count, grouped by category. Individual
WARN rows are printed only with `-v`. FAIL rows are always printed.

Example (counts only, no FAIL):

```text
FAIL: 0
WARN: 12  (E1-leak-gold=3, study-node=9)
```

## Exemptions

`exempt.txt` lists known **main false-blocks**. Those case ids are still
reported (`EXEMPT` in the summary / rows) but **never fail** the run.

**Changing `exempt.txt` requires maintainer approval.**
