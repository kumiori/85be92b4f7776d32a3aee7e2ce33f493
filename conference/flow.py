from __future__ import annotations

from copy import deepcopy
from typing import Any, Dict, Iterable, List

import streamlit as st

from conference.question_flags import normalize_question_flags
from conference.question_sets import (
    QuestionSet,
    active_steps_for_mode as question_set_active_steps_for_mode,
    field_for_step as question_set_field_for_step,
    field_value_set,
    mode_card_rows as question_set_mode_card_rows,
    question_by_field,
    question_by_step,
)
from conference.question_sets.complexity_v2 import QUESTION_SET as DEFAULT_QUESTION_SET


QUESTION_SET_STATE_KEY = "conference_question_set"
CURRENT_SCHEMA_VERSION = 2
MULTI_INPUT_TYPES = {"multi"}
TEXT_INPUT_TYPES = {"text"}
COMPOSITE_INPUT_TYPES = {"geography_context"}


def _resolve_question_set(question_set: QuestionSet | None = None) -> QuestionSet:
    if question_set is not None:
        return question_set
    stored = st.session_state.get(QUESTION_SET_STATE_KEY)
    if isinstance(stored, QuestionSet):
        return stored
    st.session_state[QUESTION_SET_STATE_KEY] = DEFAULT_QUESTION_SET
    return DEFAULT_QUESTION_SET


def set_active_question_set(question_set: QuestionSet) -> QuestionSet:
    st.session_state[QUESTION_SET_STATE_KEY] = question_set
    return question_set


def current_question_set() -> QuestionSet:
    return _resolve_question_set()


def _default_draft(question_set: QuestionSet) -> Dict[str, Any]:
    draft: Dict[str, Any] = {
        "mode": str(question_set.default_mode or ""),
        "boiler_room_contribution": "",
        "question_flags": {},
        "alias": "",
        "identity": "",
        "contact": "",
        "deferred_fields": [],
        "identity_reveal_targets": [],
        "access_key": "",
        "submitted": False,
    }
    for question in question_set.questions:
        field = str(question.field)
        if field == "scientific_home":
            draft.setdefault("scientific_home_country", "")
            draft.setdefault("scientific_home_city", "")
            draft.setdefault("scientific_home_institution", "")
        elif question.input_type in COMPOSITE_INPUT_TYPES:
            draft.setdefault(
                field,
                {
                    "country_region": "",
                    "institution_location": "",
                    "coordinates_consent": "",
                    "coordinates": "",
                },
            )
        elif question.input_type == "fingerprint":
            draft.setdefault(field, {axis: 0 for axis in question_set.fingerprint_axes})
        elif question.input_type in MULTI_INPUT_TYPES:
            draft.setdefault(field, [])
        else:
            draft.setdefault(field, "")
        free_text_field = str(getattr(question, "free_text_field", "") or "").strip()
        if free_text_field:
            draft.setdefault(free_text_field, "")
    return draft


def active_question_steps(
    draft: Dict[str, Any] | None = None,
    *,
    question_set: QuestionSet | None = None,
) -> List[str]:
    source = draft or get_draft(question_set=question_set)
    qset = _resolve_question_set(question_set)
    return question_set_active_steps_for_mode(
        qset,
        str(source.get("mode") or qset.default_mode or "").strip(),
    )


def active_step_sequence(
    draft: Dict[str, Any] | None = None,
    *,
    question_set: QuestionSet | None = None,
) -> List[str]:
    qset = _resolve_question_set(question_set)
    prefix = ["welcome"] if qset.show_welcome_step else []
    return [
        *prefix,
        *active_question_steps(draft, question_set=qset),
        "identity",
        "review",
        "done",
    ]


def initial_step(
    draft: Dict[str, Any] | None = None,
    *,
    question_set: QuestionSet | None = None,
) -> str:
    qset = _resolve_question_set(question_set)
    if qset.show_welcome_step:
        return "welcome"
    steps = active_question_steps(draft, question_set=qset)
    if steps:
        return steps[0]
    return "identity"


def first_active_question_step(
    draft: Dict[str, Any] | None = None,
    *,
    question_set: QuestionSet | None = None,
) -> str:
    steps = active_question_steps(draft, question_set=question_set)
    return steps[0] if steps else "welcome"


def should_collect_contact(
    draft: Dict[str, Any] | None = None,
    *,
    question_set: QuestionSet | None = None,
) -> bool:
    source = draft or get_draft(question_set=question_set)
    qset = _resolve_question_set(question_set)
    if "__always__" in set(qset.follow_up_contact_values):
        return True
    for field in ("follow_up_interest", "continue_conversation"):
        value = str(source.get(field) or "").strip()
        if value:
            return value in set(qset.follow_up_contact_values)
    return False


def init_flow_state(*, question_set: QuestionSet | None = None) -> None:
    qset = set_active_question_set(_resolve_question_set(question_set))
    st.session_state.setdefault("conference_step", initial_step(question_set=qset))
    st.session_state.setdefault("conference_draft", deepcopy(_default_draft(qset)))


def reset_flow_state(*, question_set: QuestionSet | None = None) -> None:
    qset = set_active_question_set(_resolve_question_set(question_set))
    st.session_state["conference_step"] = initial_step(question_set=qset)
    st.session_state["conference_draft"] = deepcopy(_default_draft(qset))
    st.session_state.pop("conference_hydrated", None)
    st.session_state.pop("conference_submission_cache", None)
    st.session_state.pop("conference_submission_cache_key", None)
    st.session_state.pop("conference_last_step_view", None)
    for key in list(st.session_state.keys()):
        if key.startswith("conference_widget_") or key.startswith("conference_log_"):
            del st.session_state[key]


def current_step() -> str:
    return str(st.session_state.get("conference_step", "welcome"))


def set_step(step: str, *, question_set: QuestionSet | None = None) -> None:
    if step in active_step_sequence(question_set=question_set):
        st.session_state["conference_step"] = step


def next_step(*, question_set: QuestionSet | None = None) -> None:
    step = current_step()
    sequence = active_step_sequence(question_set=question_set)
    if step not in sequence:
        st.session_state["conference_step"] = sequence[0]
        return
    idx = sequence.index(step)
    if idx < len(sequence) - 1:
        st.session_state["conference_step"] = sequence[idx + 1]


def get_draft(*, question_set: QuestionSet | None = None) -> Dict[str, Any]:
    qset = _resolve_question_set(question_set)
    draft = st.session_state.get("conference_draft")
    if not isinstance(draft, dict):
        draft = deepcopy(_default_draft(qset))
        st.session_state["conference_draft"] = draft
        return draft
    defaults = _default_draft(qset)
    merged = deepcopy(defaults)
    merged.update(draft)
    st.session_state["conference_draft"] = merged
    return merged


def update_draft(*, question_set: QuestionSet | None = None, **values: Any) -> Dict[str, Any]:
    draft = dict(get_draft(question_set=question_set))
    draft.update(values)
    st.session_state["conference_draft"] = draft
    return draft


def mark_submitted(*, question_set: QuestionSet | None = None) -> None:
    update_draft(question_set=question_set, submitted=True)
    set_step("done", question_set=question_set)


def _normalize_single(value: Any, allowed: set[str]) -> str:
    token = str(value or "").strip()
    if not token or (allowed and token not in allowed):
        return ""
    return token


def _normalize_values(values: Iterable[Any], allowed: set[str], max_select: int | None = None) -> List[str]:
    out: List[str] = []
    seen: set[str] = set()
    for value in values:
        token = str(value or "").strip()
        if not token or (allowed and token not in allowed) or token in seen:
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


def _normalize_geography_context(value: Any) -> Dict[str, str]:
    source = value if isinstance(value, dict) else {}
    consent = str(source.get("coordinates_consent") or "").strip().lower()
    coordinates = _normalize_text(source.get("coordinates"))
    if coordinates and consent not in {"yes", "manual", "lookup"}:
        consent = "manual"
    return {
        "country_region": _normalize_text(source.get("country_region")),
        "institution_location": _normalize_text(source.get("institution_location")),
        "coordinates_consent": consent,
        "coordinates": coordinates,
        "geocode_query": _normalize_text(source.get("geocode_query")),
        "geocode_label": _normalize_text(source.get("geocode_label")),
        "geocode_source": _normalize_text(source.get("geocode_source")),
    }


def _geography_context_answered(value: Dict[str, str]) -> bool:
    return any(
        str(value.get(field) or "").strip()
        for field in ("country_region", "institution_location", "coordinates")
    )


def _normalize_fingerprint(question_set: QuestionSet, value: Any) -> Dict[str, int]:
    source = value if isinstance(value, dict) else {}
    out: Dict[str, int] = {}
    for axis in question_set.fingerprint_axes:
        raw = source.get(axis, 0)
        try:
            level = int(raw)
        except Exception:
            level = 0
        out[axis] = max(0, min(5, level))
    return out


def _fingerprint_answered(question_set: QuestionSet, value: Dict[str, int]) -> bool:
    return any(int(value.get(axis, 0) or 0) > 0 for axis in question_set.fingerprint_axes)


def _active_fields(draft: Dict[str, Any], question_set: QuestionSet) -> set[str]:
    fields: set[str] = set()
    for step in active_question_steps(draft, question_set=question_set):
        field = question_set_field_for_step(question_set, step)
        if field == "scientific_home":
            fields.update(
                {
                    "scientific_home_country",
                    "scientific_home_city",
                    "scientific_home_institution",
                }
            )
            continue
        if field:
            fields.add(field)
    return fields


def _raw_deferred_fields(draft: Dict[str, Any], question_set: QuestionSet) -> List[str]:
    allowed = set(question_set.deferrable_fields)
    return [
        str(field).strip()
        for field in _coerce_values(draft.get("deferred_fields", []))
        if str(field).strip() in allowed
    ]


def is_field_answered(field: str, draft: Dict[str, Any], *, question_set: QuestionSet | None = None) -> bool:
    qset = _resolve_question_set(question_set)
    question = question_by_field(qset, field)
    if field in {"identity_reveal_targets"}:
        return bool(_coerce_values(draft.get(field, [])))
    if question and question.input_type in MULTI_INPUT_TYPES:
        return bool(_coerce_values(draft.get(field, [])))
    if question and question.input_type == "fingerprint":
        return _fingerprint_answered(qset, _normalize_fingerprint(qset, draft.get(field)))
    if question and question.input_type in COMPOSITE_INPUT_TYPES:
        return _geography_context_answered(_normalize_geography_context(draft.get(field)))
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


def normalized_deferred_fields(
    draft: Dict[str, Any] | None = None,
    *,
    question_set: QuestionSet | None = None,
) -> List[str]:
    qset = _resolve_question_set(question_set)
    source = draft or get_draft(question_set=qset)
    active = _active_fields(source, qset)
    return [
        field
        for field in _raw_deferred_fields(source, qset)
        if field in active and not is_field_answered(field, source, question_set=qset)
    ]


def defer_field(field: str, *, question_set: QuestionSet | None = None) -> None:
    qset = _resolve_question_set(question_set)
    if field not in set(qset.deferrable_fields):
        return
    draft = get_draft(question_set=qset)
    deferred = normalized_deferred_fields(draft, question_set=qset)
    if field not in deferred:
        deferred.append(field)
    update_draft(question_set=qset, deferred_fields=deferred)


def clear_deferred_field(field: str, *, question_set: QuestionSet | None = None) -> None:
    qset = _resolve_question_set(question_set)
    deferred = [name for name in _raw_deferred_fields(get_draft(question_set=qset), qset) if name != field]
    update_draft(question_set=qset, deferred_fields=deferred)


def pending_reflection_fields(
    draft: Dict[str, Any] | None = None,
    *,
    question_set: QuestionSet | None = None,
) -> List[str]:
    return normalized_deferred_fields(draft, question_set=question_set)


def profile_completion_gaps(
    draft: Dict[str, Any] | None = None,
    *,
    question_set: QuestionSet | None = None,
) -> List[str]:
    qset = _resolve_question_set(question_set)
    source = draft or get_draft(question_set=qset)
    gaps: List[str] = []
    for field in qset.migration_profile_fields:
        if field == "complexity_fingerprint":
            if not is_field_answered(field, source, question_set=qset):
                gaps.append(field)
            continue
        if field == "assets":
            if not _coerce_values(source.get("assets", [])):
                gaps.append(field)
            continue
        if not _normalize_text(source.get(field)):
            gaps.append(field)
    return gaps


def build_session_payload(
    draft: Dict[str, Any],
    *,
    question_set: QuestionSet | None = None,
) -> Dict[str, Any]:
    qset = _resolve_question_set(question_set)
    payload: Dict[str, Any] = {"schema_version": str(CURRENT_SCHEMA_VERSION)}
    active_fields = _active_fields(draft, qset)
    deferred_fields = normalized_deferred_fields(draft, question_set=qset)

    profile: Dict[str, Any] = {}
    session: Dict[str, Any] = {
        "depth": str(draft.get("mode") or "").strip(),
        "boiler_room_contribution": _normalize_text(draft.get("boiler_room_contribution")),
        "question_flags": normalize_question_flags(draft.get("question_flags")),
        "deferred_fields": deferred_fields,
        "identity_reveal_targets": _normalize_values(
            _coerce_values(draft.get("identity_reveal_targets", [])),
            set(_coerce_values(draft.get("identity_reveal_targets", []))),
        ),
    }

    if any(
        field in qset.profile_fields
        for field in ("scientific_home_country", "scientific_home_city", "scientific_home_institution")
    ):
        profile["scientific_home"] = {
            "country": _normalize_text(draft.get("scientific_home_country")) if "scientific_home_country" in active_fields else "",
            "city": _normalize_text(draft.get("scientific_home_city")) if "scientific_home_city" in active_fields else "",
            "institution": _normalize_text(draft.get("scientific_home_institution")) if "scientific_home_institution" in active_fields else "",
        }
    role_question = question_by_field(qset, "role")
    role_extra_field = (
        str(getattr(role_question, "free_text_field", "") or "").strip()
        if role_question
        else ""
    )
    if role_question:
        role_extra_value = (
            _normalize_text(draft.get(role_extra_field or "role_custom"))
            if "role" in active_fields
            else ""
        )
        profile["role_custom"] = role_extra_value
        if role_extra_field:
            profile[role_extra_field] = role_extra_value

    for question in qset.questions:
        field = str(question.field)
        target = profile if field in set(qset.profile_fields) or field == "scientific_home" else session
        free_text_field = str(getattr(question, "free_text_field", "") or "").strip()
        if field == "scientific_home":
            continue
        if field not in active_fields:
            if question.input_type == "fingerprint":
                target[field] = {axis: 0 for axis in qset.fingerprint_axes}
            elif question.input_type in COMPOSITE_INPUT_TYPES:
                target[field] = _normalize_geography_context({})
            elif question.input_type in MULTI_INPUT_TYPES:
                target[field] = []
            else:
                target[field] = ""
            if free_text_field:
                target[free_text_field] = ""
            continue
        if question.input_type == "fingerprint":
            target[field] = _normalize_fingerprint(qset, draft.get(field))
        elif question.input_type in COMPOSITE_INPUT_TYPES:
            target[field] = _normalize_geography_context(draft.get(field))
        elif question.input_type in MULTI_INPUT_TYPES:
            allowed = field_value_set(qset, field)
            target[field] = _normalize_values(_coerce_values(draft.get(field, [])), allowed, question.max_select)
        elif question.input_type == "text":
            target[field] = _normalize_text(draft.get(field))
        else:
            allowed = field_value_set(qset, field)
            target[field] = _normalize_single(draft.get(field, ""), allowed)
        if free_text_field:
            target[free_text_field] = _normalize_text(draft.get(free_text_field))

    derived = {"neighbour_ids": []}
    payload["profile"] = profile
    payload["session"] = session
    payload["derived"] = derived
    return payload


def flatten_payload(
    payload: Dict[str, Any],
    *,
    question_set: QuestionSet | None = None,
) -> Dict[str, Any]:
    qset = _resolve_question_set(question_set)
    profile = payload.get("profile") if isinstance(payload.get("profile"), dict) else {}
    session = payload.get("session") if isinstance(payload.get("session"), dict) else {}
    scientific_home = profile.get("scientific_home") if isinstance(profile.get("scientific_home"), dict) else {}
    out: Dict[str, Any] = {
        "schema_version": str(payload.get("schema_version") or CURRENT_SCHEMA_VERSION),
        "mode": str(session.get("depth") or payload.get("mode") or "").strip(),
        "role_custom": str(profile.get("role_custom") or "").strip(),
        "scientific_home_country": str(scientific_home.get("country") or "").strip(),
        "scientific_home_city": str(scientific_home.get("city") or "").strip(),
        "scientific_home_institution": str(scientific_home.get("institution") or "").strip(),
        "boiler_room_contribution": str(session.get("boiler_room_contribution") or "").strip(),
        "question_flags": normalize_question_flags(session.get("question_flags", payload.get("question_flags", {}))),
        "deferred_fields": list(session.get("deferred_fields") or []),
        "identity_reveal_targets": list(session.get("identity_reveal_targets") or []),
    }
    for question in qset.questions:
        field = str(question.field)
        if field == "scientific_home":
            continue
        source = profile if field in set(qset.profile_fields) else session
        value = source.get(field)
        if question.input_type == "fingerprint":
            out[field] = _normalize_fingerprint(qset, value)
        elif question.input_type in COMPOSITE_INPUT_TYPES:
            out[field] = _normalize_geography_context(value)
        elif question.input_type in MULTI_INPUT_TYPES:
            out[field] = list(value or [])
        else:
            out[field] = str(value or "").strip() if isinstance(value, str) or value is None else value
        free_text_field = str(getattr(question, "free_text_field", "") or "").strip()
        if free_text_field:
            out[free_text_field] = str(source.get(free_text_field) or "").strip()
    roles = out.get("role")
    role_question = question_by_field(qset, "role")
    role_extra_field = (
        str(getattr(role_question, "free_text_field", "") or "").strip()
        if role_question
        else ""
    )
    role_extra = str(out.get(role_extra_field) or out.get("role_custom") or "").strip()
    out["role_custom"] = role_extra
    if isinstance(roles, list) and role_extra and role_extra not in roles:
        roles.append(role_extra)
    return out


def build_identity_metadata(
    draft: Dict[str, Any],
    *,
    question_set: QuestionSet | None = None,
) -> Dict[str, Any]:
    alias = _normalize_text(draft.get("alias"))
    identity = _normalize_text(draft.get("identity"))
    contact = _normalize_text(draft.get("contact")) if should_collect_contact(draft, question_set=question_set) else ""
    return {
        "alias": alias,
        "identity": identity,
        "contact": contact,
        "notes": "",
        "contact_label": identity or alias or contact or "anonymous-scientist",
        "anonymous_first": True,
    }


def build_payload_view(
    draft: Dict[str, Any],
    *,
    question_set: QuestionSet | None = None,
) -> Dict[str, Any]:
    qset = _resolve_question_set(question_set)
    payload = build_session_payload(draft, question_set=qset)
    view = flatten_payload(payload, question_set=qset)
    view.update(build_identity_metadata(draft, question_set=qset))
    return view


def step_is_complete(
    step: str,
    draft: Dict[str, Any],
    *,
    question_set: QuestionSet | None = None,
) -> bool:
    qset = _resolve_question_set(question_set)
    payload = build_payload_view(draft, question_set=qset)
    if step == "welcome":
        return bool(str(draft.get("mode") or "").strip())
    if step in {"identity", "review", "done"}:
        return True
    question = question_by_step(qset, step)
    if not question:
        return False
    if step not in active_question_steps(draft, question_set=qset):
        return True
    field = str(question.field)
    if question.input_type == "scientific_home":
        return True
    if question.input_type in COMPOSITE_INPUT_TYPES:
        return True
    if field in normalized_deferred_fields(draft, question_set=qset):
        return True
    if question.input_type == "fingerprint":
        return is_field_answered(field, draft, question_set=qset)
    value = payload.get(field)
    if question.input_type in TEXT_INPUT_TYPES:
        return bool(str(value or "").strip()) or not question.required
    if question.input_type in MULTI_INPUT_TYPES:
        return bool(value) or not question.required
    complete = bool(str(value or "").strip()) or not question.required
    free_text_field = str(getattr(question, "free_text_field", "") or "").strip()
    if free_text_field and bool(getattr(question, "free_text_required", False)):
        return complete and bool(str(payload.get(free_text_field) or "").strip())
    return complete


def suggested_mode_for_missing_profile_fields(
    fields: List[str],
    *,
    question_set: QuestionSet | None = None,
) -> str:
    qset = _resolve_question_set(question_set)
    if "career_stage" in fields and "deep" in qset.flow_modes:
        return "deep"
    if fields and "standard" in qset.flow_modes:
        return "standard"
    return "quick"


def mode_label(mode: str, *, question_set: QuestionSet | None = None) -> str:
    qset = _resolve_question_set(question_set)
    spec = qset.flow_modes.get(str(mode or "").strip(), {})
    title = str(spec.get("title") or "Quick pulse")
    detail = str(spec.get("detail") or "")
    return f"{title} · {detail}" if detail else title


def infer_mode_from_submission(
    submission: Dict[str, Any],
    *,
    question_set: QuestionSet | None = None,
) -> str:
    qset = _resolve_question_set(question_set)
    value = str(submission.get("mode") or "").strip()
    if value in qset.flow_modes:
        return value
    ordered_modes = [mode for mode in ("deep", "standard", "quick") if mode in qset.flow_modes]
    for mode in ordered_modes:
        fields = [
            question_set_field_for_step(qset, step)
            for step in question_set_active_steps_for_mode(qset, mode)
        ]
        if any(is_field_answered(field, submission, question_set=qset) for field in fields if field):
            return mode
    return "quick"


def question_prompt_by_id(question_id: str, *, question_set: QuestionSet | None = None) -> str:
    qset = _resolve_question_set(question_set)
    token = str(question_id or "").strip()
    for question in qset.questions:
        if question.question_id == token:
            return str(question.prompt or token)
    return token


def mode_cards(*, question_set: QuestionSet | None = None) -> List[Dict[str, str]]:
    return question_set_mode_card_rows(_resolve_question_set(question_set))
