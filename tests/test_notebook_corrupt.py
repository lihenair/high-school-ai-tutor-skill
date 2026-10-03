"""错题本损坏库对抗用例：场景与断言与 tests/adversarial/nb_cases.py 等价。"""

import importlib.util
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
CASES_PATH = ROOT / "tests" / "adversarial" / "nb_cases.py"


def _load_nb_cases():
    spec = importlib.util.spec_from_file_location("nb_cases", CASES_PATH)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    module.N = str(ROOT / "skills" / "high-school-ai-tutor" / "scripts" / "notebook.py")
    return module


nb_cases = _load_nb_cases()


@pytest.mark.parametrize("case", nb_cases.CASES, ids=lambda c: c["id"])
def test_notebook_corrupt_case(case):
    problems, result = nb_cases.one(case)
    detail = ""
    if result is not None:
        detail = (result.stderr or result.stdout or "").strip().splitlines()
        detail = detail[-1][:200] if detail else ""
    assert problems == [], f"{case['id']}: {'; '.join(problems)} | {detail}"
