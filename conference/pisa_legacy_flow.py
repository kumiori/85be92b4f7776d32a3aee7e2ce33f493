from __future__ import annotations

from copy import deepcopy
from typing import Any, Dict, Iterable, List

import streamlit as st

from conference.pisa_legacy_models import (
    FOLLOW_UP_CONTACT_VALUES,
    STEP_ORDER,
    active_steps_for_mode,
    career_stage_set,
    challenge_set,
    continue_conversation_set,
    expectations_set,
    formulation_set,
    motivations_set,
    obstacle_set,
    question_by_step,
    reality_check_set,
    research_style_set,
    role_set,
    scale_set,
    systems_set,
    timescale_set,
)
from conference.question_flags import normalize_question_flags


DEFAULT_DRAFT: Dict[str, Any] = {
    "mode": "",
    "role": "",
    "career_stage": "",
    "systems": [],
    "expectations": "",
    "formulation": [],
    "reality_check": "",
    "scale": "",
    "motivations": [],
    "obstacle": [],
    "research_style": "",
    "challenge": "",
    "timescale": "",
    "continue_conversation": "",
    "open_text": "",
    "question_flags": {},
    "alias": "",
    "identity": "",
    "contact": "",
    "notes": "",
    "access_key": "",
    "submitted": False,
}


FIELD_ALLOWED_VALUES: Dict[str, set[str]] = {
    "role": role_set(),
    "career_stage": career_stage_set(),
    "systems": systems_set(),
    "expectations": expectations_set(),
    "formulation": formulation_set(),
    "reality_check": reality_check_set(),
    "scale": scale_set(),
    "motivations": motivations_set(),
    "obstacle": obstacle_set(),
    "research_style": research_style_set(),
    "challenge": challenge_set(),
    "timescale": timescale_set(),
    "continue_conversation": continue_conversation_set(),
}


def active_question_steps(draft: Dict[str, Any] | None = None) -> List[str]:
    source = draft or get_draft()
    return active_steps_for_mode(str(source.get("mode") or "").strip())


def active_step_sequence(draft: Dict[str, Any] | None = None) -> List[str]:
    return ["welcome", *active_question_steps(draft), "identity", "review", "done"]


def first_active_question_step(draft: Dict[str, Any] | None = None) -> str:
    steps = active_question_steps(draft)
    return steps[0] if steps else "welcome"


def should_collect_contact(draft: Dict[str, Any] | None = None) -> bool:
    source = draft or get_draft()
    value = source.get("continue_conversation")
    if isinstance(value, list):
        return any(str(item or "").strip() in FOLLOW_UP_CONTACT_VALUES for item in value)
    return str(value or "").strip() in FOLLOW_UP_CONTACT_VALUES


def init_flow_state() -> None:
    st.session_state.setdefault("legacy_pisa_step", STEP_ORDER[0])
    st.session_state.setdefault("legacy_pisa_draft", deepcopy(DEFAULT_DRAFT))


def reset_flow_state() -> None:
    st.session_state["legacy_pisa_step"] = STEP_ORDER[0]
    st.session_state["legacy_pisa_draft"] = deepcopy(DEFAULT_DRAFT)
    st.session_state.pop("legacy_pisa_hydrated", None)
    st.session_state.pop("legacy_pisa_submission_cache", None)
    st.session_state.pop("legacy_pisa_submission_cache_key", None)
    for key in list(st.session_state.keys()):
        if key.startswith("legacy_pisa_widget_") or key.startswith("legacy_pisa_log_"):
            del st.session_state[key]


def current_step() -> str:
    return str(st.session_state.get("legacy_pisa_step", STEP_ORDER[0]))


def set_step(step: str) -> None:
    if step in active_step_sequence():
        st.session_state["legacy_pisa_step"] = step


def next_step() -> None:
    step = current_step()
    sequence = active_step_sequence()
    if step not in sequence:
        st.session_state["legacy_pisa_step"] = sequence[0]
        return
    idx = sequence.index(step)
    if idx < len(sequence) - 1:
        st.session_state["legacy_pisa_step"] = sequence[idx + 1]


def get_draft() -> Dict[str, Any]:
    draft = st.session_state.get("legacy_pisa_draft")
    if not isinstance(draft, dict):
        draft = deepcopy(DEFAULT_DRAFT)
        st.session_state["legacy_pisa_draft"] = draft
    return draft


def update_draft(**values: Any) -> Dict[str, Any]:
    draft = dict(get_draft())
    draft.update(values)
    st.session_state["legacy_pisa_draft"] = draft
    return draft


def mark_submitted() -> None:
    update_draft(submitted=True)
    set_step("done")


def _normalize_single(value: Any, allowed: set[str]) -> str:
    token = str(value or "").strip()
    if not token or token not in allowed:
        return ""
    return token


def _normalize_values(values: Iterable[Any], allowed: set[str], max_select: int | None = None) -> List[str]:
    out: List[str] = []
    seen: set[str] = set()
    for value in values:
        token = str(value or "").strip()
        if not token or token not in allowed or token in seen:
            continue
        out.append(token)
        seen.add(token)
        if max_select is not None and len(out) >= max_select:
            break
    return out


def _coerce_values(value: Any) -> List[Any]:
    if isinstance(value, list):
        return value
    if isinstance(value, tuple):
        return list(value)
    token = str(value or "").strip()
    return [token] if token else []


def build_session_payload(draft: Dict[str, Any]) -> Dict[str, Any]:
    payload: Dict[str, Any] = {"mode": str(draft.get("mode") or "").strip()}
    active_fields = {
        str(question_by_step(step)["field"])
        for step in active_question_steps(draft)
        if question_by_step(step)
    }
    for field, allowed in FIELD_ALLOWED_VALUES.items():
        if field not in active_fields:
            payload[field] = [] if field in {"systems", "formulation", "motivations", "obstacle"} else ""
            continue
        question = question_by_step(_step_for_field(field))
        if question and question.get("input_type") == "multi":
            payload[field] = _normalize_values(
                _coerce_values(draft.get(field, [])),
                allowed,
                question.get("max_select"),
            )
        else:
            payload[field] = _normalize_single(draft.get(field, ""), allowed)
    payload["open_text"] = (
        str(draft.get("open_text") or "").strip()
        if "open_text" in active_question_steps(draft)
        else ""
    )
    payload["question_flags"] = normalize_question_flags(draft.get("question_flags"))
    payload["alias"] = str(draft.get("alias") or "").strip()
    payload["identity"] = str(draft.get("identity") or "").strip()
    payload["contact"] = str(draft.get("contact") or "").strip() if should_collect_contact(draft) else ""
    payload["notes"] = str(draft.get("notes") or "").strip()
    payload["contact_label"] = (
        payload["identity"]
        or payload["alias"]
        or payload["contact"]
        or "anonymous-scientist"
    )
    payload["anonymous_first"] = True
    return payload


def _step_for_field(field: str) -> str:
    return next(
        (
            item
            for item in STEP_ORDER
            if question_by_step(item) and question_by_step(item)["field"] == field
        ),
        "",
    )


def step_is_complete(step: str, draft: Dict[str, Any]) -> bool:
    payload = build_session_payload(draft)
    if step == "welcome":
        return bool(str(draft.get("mode") or "").strip())
    if step in {"identity", "review", "done"}:
        return True
    question = question_by_step(step)
    if not question:
        return False
    if step not in active_question_steps(draft):
        return True
    if question.get("input_type") == "text":
        return True
    value = payload.get(question["field"])
    if question.get("input_type") == "multi":
        return bool(value)
    return bool(str(value or "").strip())
