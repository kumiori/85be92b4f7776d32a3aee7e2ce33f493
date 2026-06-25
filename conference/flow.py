from __future__ import annotations

from copy import deepcopy
from typing import Any, Dict, Iterable, List

import streamlit as st

from conference.models import (
    DEFERRABLE_FIELDS,
    FINGERPRINT_AXES,
    FOLLOW_UP_CONTACT_VALUES,
    FLOW_MODES,
    MIGRATION_PROFILE_FIELDS,
    PROFILE_FIELDS,
    SESSION_FIELDS,
    STEP_ORDER,
    active_steps_for_mode,
    assets_set,
    career_stage_set,
    challenge_set,
    collaboration_style_set,
    field_for_step,
    follow_up_interest_set,
    motivations_set,
    question_by_step,
    role_set,
    scale_set,
)


DEFAULT_DRAFT: Dict[str, Any] = {
    "mode": "",
    "role": [],
    "career_stage": "",
    "scientific_home_country": "",
    "scientific_home_city": "",
    "scientific_home_institution": "",
    "scale": "",
    "collaboration_style": "",
    "assets": [],
    "motivations": [],
    "obstacle": [],
    "challenge": "",
    "follow_up_interest": "",
    "complexity_fingerprint": {axis: 0 for axis in FINGERPRINT_AXES},
    "open_question": "",
    "alias": "",
    "identity": "",
    "contact": "",
    "deferred_fields": [],
    "identity_reveal_targets": [],
    "access_key": "",
    "submitted": False,
}


FIELD_ALLOWED_VALUES: Dict[str, set[str]] = {
    "role": role_set(),
    "career_stage": career_stage_set(),
    "scale": scale_set(),
    "collaboration_style": collaboration_style_set(),
    "assets": assets_set(),
    "motivations": motivations_set(),
    "obstacle": {
        "theory",
        "models",
        "computation",
        "data",
        "experiments",
        "validation",
        "funding",
        "coordination",
    },
    "challenge": challenge_set(),
    "follow_up_interest": follow_up_interest_set(),
}


MULTI_FIELDS = {"role", "assets", "motivations", "obstacle", "identity_reveal_targets"}
TEXT_FIELDS = {
    "scientific_home_country",
    "scientific_home_city",
    "scientific_home_institution",
    "open_question",
    "alias",
    "identity",
    "contact",
    "access_key",
}

CURRENT_SCHEMA_VERSION = 2


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
    value = str(source.get("follow_up_interest") or "").strip()
    return value in FOLLOW_UP_CONTACT_VALUES


def init_flow_state() -> None:
    st.session_state.setdefault("conference_step", STEP_ORDER[0])
    st.session_state.setdefault("conference_draft", deepcopy(DEFAULT_DRAFT))


def reset_flow_state() -> None:
    st.session_state["conference_step"] = STEP_ORDER[0]
    st.session_state["conference_draft"] = deepcopy(DEFAULT_DRAFT)
    st.session_state.pop("conference_hydrated", None)
    st.session_state.pop("conference_submission_cache", None)
    st.session_state.pop("conference_submission_cache_key", None)
    for key in list(st.session_state.keys()):
        if key.startswith("conference_widget_") or key.startswith("conference_log_"):
            del st.session_state[key]


def current_step() -> str:
    return str(st.session_state.get("conference_step", STEP_ORDER[0]))


def set_step(step: str) -> None:
    if step in active_step_sequence():
        st.session_state["conference_step"] = step


def next_step() -> None:
    step = current_step()
    sequence = active_step_sequence()
    if step not in sequence:
        st.session_state["conference_step"] = sequence[0]
        return
    idx = sequence.index(step)
    if idx < len(sequence) - 1:
        st.session_state["conference_step"] = sequence[idx + 1]


def get_draft() -> Dict[str, Any]:
    draft = st.session_state.get("conference_draft")
    if not isinstance(draft, dict):
        draft = deepcopy(DEFAULT_DRAFT)
        st.session_state["conference_draft"] = draft
    return draft


def update_draft(**values: Any) -> Dict[str, Any]:
    draft = dict(get_draft())
    draft.update(values)
    st.session_state["conference_draft"] = draft
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


def _normalize_text(value: Any) -> str:
    return str(value or "").strip()


def _normalize_fingerprint(value: Any) -> Dict[str, int]:
    source = value if isinstance(value, dict) else {}
    out: Dict[str, int] = {}
    for axis in FINGERPRINT_AXES:
        raw = source.get(axis, 0)
        try:
            level = int(raw)
        except Exception:
            level = 0
        out[axis] = max(0, min(5, level))
    return out


def _fingerprint_answered(value: Dict[str, int]) -> bool:
    return any(int(value.get(axis, 0) or 0) > 0 for axis in FINGERPRINT_AXES)


def _active_fields(draft: Dict[str, Any]) -> set[str]:
    fields: set[str] = set()
    for step in active_question_steps(draft):
        field = field_for_step(step)
        if field:
            fields.add(field)
    return fields


def _raw_deferred_fields(draft: Dict[str, Any]) -> List[str]:
    return [
        str(field).strip()
        for field in _coerce_values(draft.get("deferred_fields", []))
        if str(field).strip() in DEFERRABLE_FIELDS
    ]


def is_field_answered(field: str, draft: Dict[str, Any]) -> bool:
    if field in {"role", "assets", "motivations", "obstacle", "identity_reveal_targets"}:
        return bool(_coerce_values(draft.get(field, [])))
    if field == "complexity_fingerprint":
        return _fingerprint_answered(_normalize_fingerprint(draft.get(field)))
    if field == "scientific_home":
        return any(
            _normalize_text(draft.get(key))
            for key in (
                "scientific_home_country",
                "scientific_home_city",
                "scientific_home_institution",
            )
        )
    return bool(_normalize_text(draft.get(field)))


def normalized_deferred_fields(draft: Dict[str, Any] | None = None) -> List[str]:
    source = draft or get_draft()
    active = _active_fields(source)
    return [
        field
        for field in _raw_deferred_fields(source)
        if field in active and not is_field_answered(field, source)
    ]


def defer_field(field: str) -> None:
    if field not in DEFERRABLE_FIELDS:
        return
    draft = get_draft()
    deferred = normalized_deferred_fields(draft)
    if field not in deferred:
        deferred.append(field)
    update_draft(deferred_fields=deferred)


def clear_deferred_field(field: str) -> None:
    deferred = [name for name in _raw_deferred_fields(get_draft()) if name != field]
    update_draft(deferred_fields=deferred)


def pending_reflection_fields(draft: Dict[str, Any] | None = None) -> List[str]:
    return normalized_deferred_fields(draft)


def profile_completion_gaps(draft: Dict[str, Any] | None = None) -> List[str]:
    source = draft or get_draft()
    gaps: List[str] = []
    for field in MIGRATION_PROFILE_FIELDS:
        if field == "complexity_fingerprint":
            if not is_field_answered(field, source):
                gaps.append(field)
            continue
        if field == "assets":
            if not _coerce_values(source.get("assets", [])):
                gaps.append(field)
            continue
        if not _normalize_text(source.get(field)):
            gaps.append(field)
    return gaps


def build_session_payload(draft: Dict[str, Any]) -> Dict[str, Any]:
    payload: Dict[str, Any] = {"schema_version": str(CURRENT_SCHEMA_VERSION)}
    active_fields = _active_fields(draft)

    role = _normalize_values(_coerce_values(draft.get("role", [])), FIELD_ALLOWED_VALUES["role"], 3)
    career_stage = _normalize_single(draft.get("career_stage", ""), FIELD_ALLOWED_VALUES["career_stage"])
    scale = _normalize_single(draft.get("scale", ""), FIELD_ALLOWED_VALUES["scale"])
    collaboration_style = _normalize_single(
        draft.get("collaboration_style", ""),
        FIELD_ALLOWED_VALUES["collaboration_style"],
    )
    assets = _normalize_values(_coerce_values(draft.get("assets", [])), FIELD_ALLOWED_VALUES["assets"], 3)
    motivations = _normalize_values(_coerce_values(draft.get("motivations", [])), FIELD_ALLOWED_VALUES["motivations"], 3)
    obstacle = _normalize_values(_coerce_values(draft.get("obstacle", [])), FIELD_ALLOWED_VALUES["obstacle"], 2)
    challenge = _normalize_single(draft.get("challenge", ""), FIELD_ALLOWED_VALUES["challenge"])
    follow_up_interest = _normalize_single(
        draft.get("follow_up_interest", ""),
        FIELD_ALLOWED_VALUES["follow_up_interest"],
    )
    complexity_fingerprint = _normalize_fingerprint(draft.get("complexity_fingerprint"))
    open_question = (
        _normalize_text(draft.get("open_question"))
        if "open_question" in active_fields
        else ""
    )

    deferred_fields = normalized_deferred_fields(draft)

    profile = {
        "role": role,
        "career_stage": career_stage if "career_stage" in active_fields else "",
        "scientific_home": {
            "country": _normalize_text(draft.get("scientific_home_country")),
            "city": _normalize_text(draft.get("scientific_home_city")),
            "institution": _normalize_text(draft.get("scientific_home_institution")),
        }
        if "scientific_home" in active_fields
        else {"country": "", "city": "", "institution": ""},
        "computational_scale": scale if "scale" in active_fields else "",
        "collaboration_style": collaboration_style if "collaboration_style" in active_fields else "",
        "assets": assets if "assets" in active_fields else [],
        "complexity_fingerprint": complexity_fingerprint if "complexity_fingerprint" in active_fields else {axis: 0 for axis in FINGERPRINT_AXES},
    }
    session = {
        "depth": str(draft.get("mode") or "").strip(),
        "motivations": motivations if "motivations" in active_fields else [],
        "obstacle": obstacle if "obstacle" in active_fields else [],
        "challenge": challenge if "challenge" in active_fields else "",
        "follow_up_interest": follow_up_interest if "follow_up_interest" in active_fields else "",
        "open_question": open_question,
        "deferred_fields": deferred_fields,
        "identity_reveal_targets": _normalize_values(
            _coerce_values(draft.get("identity_reveal_targets", [])),
            set(_coerce_values(draft.get("identity_reveal_targets", []))),
        ),
    }
    derived = {"neighbour_ids": []}

    payload["profile"] = profile
    payload["session"] = session
    payload["derived"] = derived
    return payload


def flatten_payload(payload: Dict[str, Any]) -> Dict[str, Any]:
    profile = payload.get("profile") if isinstance(payload.get("profile"), dict) else {}
    session = payload.get("session") if isinstance(payload.get("session"), dict) else {}
    scientific_home = (
        profile.get("scientific_home")
        if isinstance(profile.get("scientific_home"), dict)
        else {}
    )
    out = {
        "schema_version": str(payload.get("schema_version") or CURRENT_SCHEMA_VERSION),
        "mode": str(session.get("depth") or payload.get("mode") or "").strip(),
        "role": list(profile.get("role") or []),
        "career_stage": str(profile.get("career_stage") or "").strip(),
        "scientific_home_country": str(scientific_home.get("country") or "").strip(),
        "scientific_home_city": str(scientific_home.get("city") or "").strip(),
        "scientific_home_institution": str(scientific_home.get("institution") or "").strip(),
        "scale": str(profile.get("computational_scale") or "").strip(),
        "collaboration_style": str(profile.get("collaboration_style") or "").strip(),
        "assets": list(profile.get("assets") or []),
        "complexity_fingerprint": _normalize_fingerprint(profile.get("complexity_fingerprint")),
        "motivations": list(session.get("motivations") or []),
        "obstacle": list(session.get("obstacle") or []),
        "challenge": str(session.get("challenge") or "").strip(),
        "follow_up_interest": str(session.get("follow_up_interest") or "").strip(),
        "continue_conversation": str(session.get("follow_up_interest") or "").strip(),
        "open_question": str(session.get("open_question") or "").strip(),
        "open_text": str(session.get("open_question") or "").strip(),
        "deferred_fields": list(session.get("deferred_fields") or []),
        "identity_reveal_targets": list(session.get("identity_reveal_targets") or []),
    }
    return out


def build_identity_metadata(draft: Dict[str, Any]) -> Dict[str, Any]:
    alias = _normalize_text(draft.get("alias"))
    identity = _normalize_text(draft.get("identity"))
    contact = _normalize_text(draft.get("contact")) if should_collect_contact(draft) else ""
    return {
        "alias": alias,
        "identity": identity,
        "contact": contact,
        "notes": "",
        "contact_label": identity or alias or contact or "anonymous-scientist",
        "anonymous_first": True,
    }


def build_payload_view(draft: Dict[str, Any]) -> Dict[str, Any]:
    payload = build_session_payload(draft)
    view = flatten_payload(payload)
    view.update(build_identity_metadata(draft))
    return view


def step_is_complete(step: str, draft: Dict[str, Any]) -> bool:
    payload = build_payload_view(draft)
    if step == "welcome":
        return bool(str(draft.get("mode") or "").strip())
    if step in {"identity", "review", "done"}:
        return True
    question = question_by_step(step)
    if not question:
        return False
    if step not in active_question_steps(draft):
        return True
    field = str(question["field"])
    if field in normalized_deferred_fields(draft):
        return True
    input_type = str(question.get("input_type") or "")
    if input_type == "scientific_home":
        return True
    if input_type == "fingerprint":
        return is_field_answered("complexity_fingerprint", draft)
    value = payload.get(field)
    if input_type == "text":
        return bool(str(value or "").strip())
    if input_type == "multi":
        return bool(value)
    return bool(str(value or "").strip())


def suggested_mode_for_missing_profile_fields(fields: List[str]) -> str:
    if "career_stage" in fields:
        return "deep"
    if fields:
        return "standard"
    return "quick"


def mode_label(mode: str) -> str:
    spec = FLOW_MODES.get(str(mode or "").strip(), {})
    title = str(spec.get("title") or "Quick pulse")
    detail = str(spec.get("detail") or "")
    return f"{title} · {detail}" if detail else title
