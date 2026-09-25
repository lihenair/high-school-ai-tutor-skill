#!/usr/bin/env bash
# 守卫测试：bash tests/run.sh
set -u
cd "$(dirname "$0")/.."

pass=0
fail=0

run() {
  local file=$1 mode=$2 want=$3
  shift 3
  python3 skills/high-school-ai-tutor/scripts/guard.py --mode "$mode" "$@" "tests/guard-cases/$file" >/dev/null 2>&1
  local got=$?
  if [ "$got" -eq "$want" ]; then
    pass=$((pass + 1))
  else
    fail=$((fail + 1))
    echo "FAIL $file ($mode $*): exit $got, want $want"
  fi
}

run socratic-ok.txt    socratic 0
run map-ok.txt         socratic 0
run chapter-map-ok.txt socratic 0
run problem-slice-ok.txt socratic 0
run socratic-bad.txt   socratic 1
run chapter-map-bad.txt socratic 1
run edge-bad.txt       socratic 1
run style-bad.txt      socratic 1
run full-ok.txt        full     0
run full-ok.txt        summary  0
run full-bad.txt       full     1
run no-answer.txt      full     0
run no-answer.txt      full     1 --no-student-answer
run full-ok.txt         full    1 --subject math
run math-verify-ok.txt  full    0 --subject math
run math-verify-ok.txt  full    0

run self-study/01-missing-label.txt study 1
run self-study/02-bad-state.txt study 1
run self-study/03-unknown-node.txt study 1
run self-study/04-uncovered-chapter.txt study 0
run self-study/05-node-mermaid.txt study 1
run self-study/06-end-mermaid.txt study 1
run self-study/07-overview-no-map.txt study 0
run self-study/08-overview-ok.txt study 0
run self-study/09-selftest-marked.txt study 0
run self-study/10-selftest-unmarked.txt study 1
run self-study/11-example-without-marker.txt study 0
run self-study/12-notebook-extension.txt study 1
run self-study/13-diagnosis-ask.txt study 0
run self-study/14-diagnosis-judge.txt study 0
run self-study/15-repair-step.txt study 0
run self-study/16-solve-unlabeled.txt study 0

echo "通过 $pass / $((pass + fail))"
[ "$fail" -eq 0 ]
