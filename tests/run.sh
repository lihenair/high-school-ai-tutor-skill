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
run socratic-bad.txt   socratic 1
run full-ok.txt        full     0
run full-ok.txt        summary  0
run full-bad.txt       full     1
run no-answer.txt      full     0
run no-answer.txt      full     1 --no-student-answer

echo "通过 $pass / $((pass + fail))"
[ "$fail" -eq 0 ]
