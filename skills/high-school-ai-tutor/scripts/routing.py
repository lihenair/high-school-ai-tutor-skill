#!/usr/bin/env python3
"""开场与一轮一态的纯函数。模式判定不读回复标签。"""

import re
import sys
from pathlib import Path

_SCRIPTS = Path(__file__).resolve().parent
if str(_SCRIPTS) not in sys.path:
    sys.path.insert(0, str(_SCRIPTS))
import nodes

STUDY_TRIGGERS = (
    r"自学\s*[:：]",
    r"学第[0-9一二三四五六七八九十百]+章",
    r"知识图谱",
    r"思维导图",
    r"这一章的知识",
    r"先把这章发出来",
    r"这一章怎么学",
)
SOLVE_TRIGGERS = (
    "直接讲解",
    "给我解析",
    "给完整解法",
    "不要引导",
    "直接讲答案",
    "直接给解析",
    "讲一下",
    "给我答案",
)
PROBLEM_TRIGGERS = (
    r"题目\s*[:：]",
    r"【题目】",
    r"(?:^|\n)\s*已知",
)
NODE_TEACH = ("讲这个节点", "节点讲解", "讲一下这个节点")
REJECT_SENTENCE = "节点讲解请单独发一次"


def _first(text, patterns):
    found = None
    for pattern in patterns:
        matched = re.search(pattern, text)
        if matched and (found is None or matched.start() < found):
            found = matched.start()
    return found


def _explicit(text):
    study_at = _first(text, STUDY_TRIGGERS)
    solve_at = _first(text, SOLVE_TRIGGERS)
    if study_at is None and solve_at is None:
        return None
    if study_at is None:
        return "solve"
    if solve_at is None:
        return "study"
    return "study" if study_at <= solve_at else "solve"


def _is_problem(text):
    return _first(text, PROBLEM_TRIGGERS) is not None


def route_opening(profile, text, needs_onboarding):
    """开场五场景。needs_onboarding 由画像层传入，避免这里读文件。"""
    explicit = _explicit(text)
    problem = _is_problem(text)
    progress = (profile or {}).get("self_study_progress") or {}
    node = progress.get("current_node") or ""
    if explicit == "study":
        if needs_onboarding:
            return {"action": "onboard", "ask_resume": False, "sentence": ""}
        return {"action": "study_chapter", "ask_resume": False, "sentence": ""}
    if explicit == "solve":
        return {"action": "solve", "ask_resume": False, "sentence": ""}
    if problem:
        label = nodes.display_for_id(node) or node
        sentence = f"回到 {label} 节点吗" if node and not needs_onboarding else ""
        return {"action": "solve", "ask_resume": bool(sentence), "sentence": sentence}
    if profile and not needs_onboarding:
        return {"action": "resume", "ask_resume": False, "sentence": ""}
    return {"action": "solve", "ask_resume": False, "sentence": ""}


def route_turn(state, text, wrong_streak=0):
    """六种切换。state 取章览、诊断、节点、章末、引导。"""
    problem = _is_problem(text)
    wants_node = any(phrase in text for phrase in NODE_TEACH)
    if wants_node and problem:
        return {"action": "solve", "defer": "node", "sentence": REJECT_SENTENCE, "label": None}
    if state == "节点" and wrong_streak >= 2 and not problem:
        return {"action": "repair", "defer": "", "sentence": "", "label": "节点"}
    if state in ("节点", "章览", "诊断", "章末") and problem:
        return {"action": "solve", "defer": state, "sentence": "", "label": None}
    if state == "引导" and ("没学过" in text):
        return {"action": "study_chapter", "defer": "解题", "sentence": "", "label": "章览"}
    return {"action": "stay", "defer": "", "sentence": "", "label": state}


def resume_prompt(node_label):
    return f"回到 {node_label} 节点吗"
