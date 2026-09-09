from __future__ import annotations

from dataclasses import replace
from copy import deepcopy
import html
import hashlib
import time
import uuid
from collections.abc import Mapping
from typing import Any, Callable, Dict, List

import requests
import streamlit as st
import streamlit.components.v1 as components

from conference.context import get_conference_bundle, get_conference_repo
from conference.events import (
    UNESCO_SESSION_CODE,
    YOUNG_SESSION_CODE,
    conference_event_context,
    conference_event_options,
    text_ids_for_session_code,
    event_config_for_session_code,
)
from conference.participation import normalize_email
from conference.location_lookup import opencage_location_options, render_location_lookup
from conference.question_state import (
    answer_question,
    flag_question,
    question_state,
    skip_question,
)
from conference.flow import (
    active_question_steps,
    active_step_sequence,
    build_identity_metadata,
    build_session_payload,
    build_payload_view,
    clear_deferred_field,
    current_question_set,
    current_step,
    defer_field,
    first_active_question_step,
    get_draft,
    infer_mode_from_submission,
    initial_step,
    init_flow_state,
    mark_submitted,
    mode_cards,
    mode_label,
    next_step,
    pending_reflection_fields,
    profile_completion_gaps,
    question_prompt_by_id as flow_question_prompt_by_id,
    reset_flow_state,
    set_step,
    should_collect_contact,
    step_is_complete,
    suggested_mode_for_missing_profile_fields,
    update_draft,
)
from conference.public_routes import public_query_params, public_route_config
from conference.question_sets import (
    QuestionDefinition,
    QuestionSet,
    field_for_step,
    field_option_label_map,
    field_value_set,
    question_by_field,
    question_by_step,
    questions_requiring_reanswer,
    step_interactions,
)
from conference.question_sets.platform_controls_fixture import (
    QUESTION_SET as PLATFORM_CONTROLS_FIXTURE,
)
from conference.registry import resolve_question_set_bundle
from conference.question_flags import (
    QUESTION_FLAG_INTRO,
    QUESTION_FLAG_LABELS,
    QUESTION_FLAG_OPTIONS,
    normalize_question_flags,
)
from conference.question_skips import (
    QUESTION_SKIP_INTRO,
    QUESTION_SKIP_LABELS,
    QUESTION_SKIP_OPTIONS,
    normalize_question_skips,
)
from conference.repo import emoji_suffix, resolve_access_key_input
from conference.topology import count_field, room_snapshot
from conference.ui import apply_conference_styles, conference_header, summary_card
from conference.wg2_ux import (
    LOCATION_DEBOUNCE_SECONDS,
    confirm_location,
    correct_location,
    edit_context,
    location_lookup_due,
    location_lookup_failure,
    merge_answer_fields,
    parse_opencage_result,
    revision_payload,
)
from infra.event_logger import log_event, log_perf
from infra.key_codec import generate_hex_key, hex_to_emoji, split_emoji_symbols
from ui import set_page, sidebar_debug_state


IDENTITY_STEP = "identity"
ENTRY_KEY = "conference_entry_mode"
LOGIN_ERROR_KEY = "conference_login_error"
QUESTION_VALIDATION_KEY = "conference_question_validation"
EDIT_CONTEXT_KEY = "conference_edit_context"
EDIT_DRAFT_KEY = "conference_edit_draft"
SESSION_SCOPE_KEY = "conference_runtime_session_scope"
PLAYER_BINDING_KEY = "conference_checkpoint_player_binding"
OPENCAGE_ENDPOINT = "https://api.opencagedata.com/geocode/v1/json"


def _ensure_local_state(question_set: QuestionSet) -> None:
    existing = st.session_state.get("conference_question_set")
    if isinstance(existing, QuestionSet) and str(existing.id) != str(question_set.id):
        reset_flow_state(question_set=question_set)
    init_flow_state(question_set=question_set)
    st.session_state.setdefault("conference_device_id", uuid.uuid4().hex[:16])
    st.session_state.setdefault(ENTRY_KEY, "")
    st.session_state.setdefault(LOGIN_ERROR_KEY, "")
    st.session_state.setdefault("conference_hide_migration_prompt", False)


def _ensure_session_scope_state(
    session: Dict[str, Any], question_set: QuestionSet
) -> None:
    """Prevent browser draft/cache state crossing production and test sessions."""
    scope = f"{session.get('id') or ''}:{session.get('session_code') or ''}"
    if st.session_state.get(SESSION_SCOPE_KEY) == scope:
        return
    reset_flow_state(question_set=question_set)
    for key in (
        "conference_hydrated",
        "conference_submission_cache",
        "conference_submission_cache_key",
        ENTRY_KEY,
        LOGIN_ERROR_KEY,
        QUESTION_VALIDATION_KEY,
        EDIT_CONTEXT_KEY,
        EDIT_DRAFT_KEY,
        PLAYER_BINDING_KEY,
    ):
        st.session_state.pop(key, None)
    st.session_state["conference_device_id"] = uuid.uuid4().hex[:16]
    st.session_state[SESSION_SCOPE_KEY] = scope


def _set_entry_mode(mode: str) -> None:
    st.session_state[ENTRY_KEY] = mode


def _entry_mode() -> str:
    return str(st.session_state.get(ENTRY_KEY, "") or "").strip()


def _clear_login_error() -> None:
    st.session_state[LOGIN_ERROR_KEY] = ""


def _set_login_error(message: str) -> None:
    st.session_state[LOGIN_ERROR_KEY] = message


def _question_validation_messages() -> dict[str, str]:
    existing = st.session_state.get(QUESTION_VALIDATION_KEY, {})
    if isinstance(existing, dict):
        return {str(key): str(value) for key, value in existing.items()}
    return {}


def _set_question_validation(step: str, message: str) -> None:
    messages = _question_validation_messages()
    token = str(step or "").strip()
    if not token:
        return
    if str(message or "").strip():
        messages[token] = str(message).strip()
    else:
        messages.pop(token, None)
    st.session_state[QUESTION_VALIDATION_KEY] = messages


def _question_validation(step: str) -> str:
    return str(_question_validation_messages().get(str(step or "").strip(), "") or "")


def _event_context(session: Dict[str, Any]) -> Dict[str, Any]:
    return conference_event_context(session=session)


def _route_event_metadata(
    session: Dict[str, Any],
    *,
    step: str = "",
    question: QuestionDefinition | None = None,
    extra: Dict[str, Any] | None = None,
) -> Dict[str, Any]:
    context = _event_context(session)
    route = _public_route()
    metadata: Dict[str, Any] = {
        "campaign_slug": str(route.campaign_slug) if route else "",
        "public_route": str(route.path) if route else "",
        "event_slug": str(context.get("event_slug") or ""),
        "session_code": str(context.get("session_code") or ""),
        "text_id": str(context.get("text_id") or ""),
        "question_set_id": str(context.get("question_set_id") or ""),
        "schema_id": str(context.get("schema_id") or ""),
        "test_mode": bool(context.get("test_mode")),
        "response_scope": str(context.get("response_scope") or ""),
        "data_classification": (
            "debug" if context.get("test_mode") else "production"
        ),
    }
    if step:
        metadata["step"] = step
    if question:
        metadata["question_id"] = str(question.question_id or "")
        metadata["field"] = str(question.field or "")
    if extra:
        metadata.update(extra)
    return metadata


def _log_route_event(
    session: Dict[str, Any],
    *,
    event_type: str,
    step: str = "",
    question: QuestionDefinition | None = None,
    status: str = "ok",
    value_label: str = "",
    player_id: str = "",
    level: str = "INFO",
    extra: Dict[str, Any] | None = None,
) -> None:
    persist = event_type not in {
        "page_view",
        "question_answered",
        "question_continue_blocked",
    }
    log_event(
        module="iceicebaby.conference",
        event_type=event_type,
        page="conference_questionnaire",
        session_id=str(session.get("id") or ""),
        player_id=player_id,
        item_id=str((question.question_id if question else "") or step or ""),
        value_label=value_label,
        device_id=str(st.session_state.get("conference_device_id", "") or ""),
        status=status,
        metadata=_route_event_metadata(
            session, step=step, question=question, extra=extra
        ),
        level=level,
        persist=persist,
    )


def _public_route() -> Any | None:
    return public_route_config(
        str(st.session_state.get("conference_public_route_path") or "")
    )


def _public_entry_title(session: Dict[str, Any]) -> str:
    route = _public_route()
    if route:
        return str(route.welcome_title)
    return str(_event_context(session)["event_label"])


def _render_public_entry_hero(route: Any) -> None:
    title = str(route.welcome_title or "").strip()
    module = str(route.welcome_body or "").strip()
    purpose = str(route.welcome_context or "").strip()
    pilot = str(route.welcome_note or "").strip()
    kicker = ""
    metadata = ""
    display = title
    if str(route.path or "") == "un-wg2-icebreaker":
        display = title
        kicker = module
        metadata = "WG2 • Actionable Cryosphere Projections"
    elif "—" in title:
        display, _, suffix = title.partition("—")
        display = display.strip() or title
        kicker = suffix.strip()

    parts = ['<div class="entry-hero">']
    if display:
        parts.append(f'<div class="entry-display">{html.escape(display)}</div>')
    if kicker:
        parts.append(f'<div class="entry-kicker">{html.escape(kicker)}</div>')
    if metadata:
        parts.append(f'<div class="entry-meta">{html.escape(metadata)}</div>')
    if purpose or pilot:
        parts.append('<div class="entry-block-grid">')
    if purpose:
        parts.append('<div class="entry-block">')
        parts.append('<div class="entry-block-label">Purpose</div>')
        parts.append(f'<div class="entry-lead">{html.escape(purpose)}</div>')
        parts.append("</div>")
    if pilot:
        bullets = [
            token.strip(" -•")
            for token in pilot.replace(";", "\n").splitlines()
            if token.strip(" -•")
        ]
        parts.append('<div class="entry-block">')
        parts.append('<div class="entry-block-label">This pilot</div>')
        if bullets:
            parts.append('<div class="entry-note"><ul>')
            parts.extend(f"<li>{html.escape(item)}</li>" for item in bullets)
            parts.append("</ul></div>")
        else:
            parts.append(f'<div class="entry-note">{html.escape(pilot)}</div>')
        parts.append("</div>")
    if purpose or pilot:
        parts.append("</div>")
    parts.append('<div class="entry-action-title">Choose how to participate</div>')
    parts.append("</div>")
    st.markdown("\n".join(parts), unsafe_allow_html=True)


def _question_set_for_public_route(
    question_set: QuestionSet,
    public_route_path: str = "",
) -> QuestionSet:
    route = public_route_config(public_route_path)
    if not route:
        return question_set
    step_copy = {
        str(step): {str(key): str(value) for key, value in copy.items()}
        for step, copy in question_set.step_copy.items()
    }
    welcome = dict(step_copy.get("welcome", {}))
    welcome["title"] = str(route.welcome_title)
    welcome["body"] = str(route.welcome_body)
    welcome["context"] = str(route.welcome_context)
    welcome["note"] = str(route.welcome_note)
    step_copy["welcome"] = welcome
    return replace(question_set, step_copy=step_copy)


def _event_scope_text(session: Dict[str, Any]) -> str:
    context = _event_context(session)
    location = str(context.get("event_location") or "").strip()
    if location:
        return f"{context['event_label']} in {location}"
    return str(context.get("event_label") or context.get("event_code") or "this event")


def _sync_event_query(event_slug: str) -> None:
    next_params: Dict[str, str] = {
        "event": str(event_slug or "").strip(),
        **public_query_params(),
    }
    st.query_params.clear()
    st.query_params.update(next_params)


def _switch_to_event_overview(session: Dict[str, Any]) -> None:
    if str(st.session_state.get("conference_public_route_path") or "") == "prediction":
        next_params = public_query_params()
        next_params.pop("event", None)
        next_params["view"] = "results"
        st.query_params.clear()
        st.query_params.update(next_params)
        st.rerun()
        return
    context = _event_context(session)
    _sync_event_query(str(context["event_slug"]))
    st.switch_page(str(context["overview_page"]))


def _event_is_read_only(session: Dict[str, Any]) -> bool:
    return not bool(_event_context(session).get("write_enabled"))


def _render_event_selector(
    repo: Any, session: Dict[str, Any], *, selector_key: str
) -> None:
    options = conference_event_options(repo)
    if len(options) <= 1:
        return
    code_to_option = {str(item["session_code"]): item for item in options}
    current_code = str(session.get("session_code") or "")
    option_codes = [str(item["session_code"]) for item in options]
    if current_code not in code_to_option:
        option_codes.insert(0, current_code)
        code_to_option[current_code] = {
            "event_slug": str(current_code).lower(),
            "session_code": current_code,
            "event_label": str(session.get("session_title") or current_code),
            "event_location": "",
            "available": True,
        }
    selected_code = st.selectbox(
        "Event",
        option_codes,
        index=option_codes.index(current_code),
        key=selector_key,
        format_func=lambda code: (
            f"{code_to_option[code]['event_label']} · {code_to_option[code]['event_location']}"
            if str(code_to_option[code].get("event_location") or "").strip()
            else str(code_to_option[code]["event_label"])
        ),
    )
    if selected_code != current_code:
        reset_flow_state(question_set=current_question_set())
        _set_entry_mode("")
        _clear_login_error()
        selected = code_to_option[selected_code]
        _sync_event_query(str(selected["event_slug"]))
        st.switch_page(str(selected["questionnaire_page"]))


def _browser_headers() -> Dict[str, str]:
    context = getattr(st, "context", None)
    headers = getattr(context, "headers", None) if context is not None else None
    if not headers:
        return {}
    if isinstance(headers, Mapping):
        items = headers.items()
    else:
        items = getattr(headers, "items", lambda: [])()
    out: Dict[str, str] = {}
    for key, value in items:
        out[str(key).lower()] = str(value)
    return out


def _is_laptop_device() -> bool:
    user_agent = _browser_headers().get("user-agent", "").lower()
    if not user_agent:
        return False
    mobile_tokens = ("iphone", "ipod", "mobile")
    tablet_tokens = ("ipad", "tablet")
    if any(token in user_agent for token in mobile_tokens):
        return False
    if any(token in user_agent for token in tablet_tokens):
        return False
    if "android" in user_agent and "mobile" not in user_agent:
        return False
    return True


def _quick_mode_card() -> Dict[str, str]:
    return next(
        (
            row
            for row in mode_cards(question_set=current_question_set())
            if str(row.get("value") or "") == "quick"
        ),
        {
            "value": "quick",
            "title": "Quick pulse",
            "detail": "~ 3 minutes",
            "accent": "🧊",
        },
    )


def _mode_start(mode: str) -> None:
    update_draft(question_set=current_question_set(), mode=mode)
    set_step(
        first_active_question_step(question_set=current_question_set()),
        question_set=current_question_set(),
    )
    st.rerun()


def _question_prompt_by_id(question_id: str) -> str:
    if str(question_id).startswith("platform_step_"):
        step = str(question_id).removeprefix("platform_step_")
        copy = current_question_set().step_copy.get(step, {})
        return str(copy.get("title") or step.replace("_", " ").title())
    return flow_question_prompt_by_id(question_id, question_set=current_question_set())


def _question_flag_entries() -> Dict[str, Dict[str, Any]]:
    return normalize_question_flags(
        get_draft(question_set=current_question_set()).get("question_flags")
    )


def _question_skip_entries() -> Dict[str, Dict[str, Any]]:
    return normalize_question_skips(
        get_draft(question_set=current_question_set()).get("question_skips")
    )


def _set_question_skip(question_id: str, *, reasons: List[str], note: str) -> None:
    entries = _question_skip_entries()
    token = str(question_id or "").strip()
    normalized = normalize_question_skips(
        {token: {"reasons": reasons, "note": note}}
    )
    if normalized.get(token):
        entries[token] = normalized[token]
    else:
        entries.pop(token, None)
    update_draft(question_set=current_question_set(), question_skips=entries)


def _clear_question_skip(question_id: str) -> None:
    entries = _question_skip_entries()
    entries.pop(str(question_id or "").strip(), None)
    update_draft(question_set=current_question_set(), question_skips=entries)


def _clear_question_answer(question: QuestionDefinition) -> None:
    field = str(question.field or "")
    if question.input_type == "scientific_home":
        update_draft(
            question_set=current_question_set(),
            scientific_home_country="",
            scientific_home_city="",
            scientific_home_institution="",
        )
        return
    empty: Any = [] if question.input_type == "multi" else {}
    if question.input_type not in {"multi", "location", "geography_context", "fingerprint"}:
        empty = ""
    update_draft(question_set=current_question_set(), **{field: empty})


def _set_question_flag(question_id: str, *, flags: List[str], note: str) -> None:
    entries = _question_flag_entries()
    token = str(question_id or "").strip()
    if not token:
        return
    normalized = normalize_question_flags({token: {"flags": flags, "note": note}})
    if normalized.get(token):
        entries[token] = normalized[token]
    else:
        entries.pop(token, None)
    update_draft(question_set=current_question_set(), question_flags=entries)
    draft = get_draft(question_set=current_question_set())
    update_draft(
        question_set=current_question_set(),
        question_states=flag_question(
            draft.get("question_states"),
            token,
            flagged=bool(normalized.get(token)),
        ),
    )


def _render_question_flag_control(
    question: QuestionDefinition,
    session: Dict[str, Any],
    repo: Any | None = None,
) -> None:
    question_id = str(question.question_id or "").strip()
    if not question_id:
        return
    state = _question_flag_entries().get(question_id, {})
    flags = list(state.get("flags") or [])
    note = str(state.get("note") or "")
    count = len(flags) + (1 if note else 0)
    label = f"Flag ({count})" if count else "Flag"
    with st.popover(label):
        st.markdown(
            f'<div class="caption">{html.escape(QUESTION_FLAG_INTRO)}</div>',
            unsafe_allow_html=True,
        )
        selected = st.pills(
            "Question feedback",
            [str(item["value"]) for item in QUESTION_FLAG_OPTIONS],
            default=flags,
            selection_mode="multi",
            format_func=lambda value: QUESTION_FLAG_LABELS.get(value, value),
            key=f"conference_flag_{question_id}",
            label_visibility="collapsed",
        )
        comment = st.text_input(
            "Optional note",
            value=note,
            key=f"conference_flag_note_{question_id}",
            placeholder="Optional short note",
            label_visibility="collapsed",
        )
        normalized_flags = list(selected)
        normalized_note = str(comment or "").strip()
        if normalized_flags != flags or normalized_note != note:
            _set_question_flag(question_id, flags=normalized_flags, note=normalized_note)
            if repo is not None:
                _persist_participation_checkpoint(
                    repo, session, next_position=current_step()
                )
            if normalized_flags or normalized_note:
                _log_route_event(
                    session,
                    event_type="question_flagged",
                    step=str(question.step or ""),
                    question=question,
                    value_label=", ".join(normalized_flags) or normalized_note,
                    extra={"note": normalized_note},
                )


def _structural_flag_question(step: str) -> QuestionDefinition:
    copy = current_question_set().step_copy.get(step, {})
    title = str(copy.get("title") or step.replace("_", " ").title())
    return QuestionDefinition(
        step=step,
        field=f"platform_step_{step}",
        question_id=f"platform_step_{step}",
        prompt=title,
        input_type="text",
        skippable=False,
    )


def _render_step_flag_action(
    step: str,
    question: QuestionDefinition | None,
    session: Dict[str, Any],
    repo: Any,
) -> None:
    capabilities = step_interactions(step, question=question)
    if capabilities.can_flag:
        _render_question_flag_control(
            question or _structural_flag_question(step), session, repo
        )
        return
    st.button(
        "Flag",
        disabled=True,
        help=capabilities.flag_reason_disabled,
        use_container_width=True,
        key=f"conference_disabled_flag_{step}",
    )
    if capabilities.flag_reason_disabled:
        st.caption(capabilities.flag_reason_disabled)


def _render_step_skip_action(
    step: str,
    question: QuestionDefinition | None,
    session: Dict[str, Any],
    repo: Any,
) -> None:
    capabilities = step_interactions(step, question=question)
    if capabilities.can_skip and question is not None:
        if st.button(
            "Skip",
            use_container_width=True,
            key=f"conference_skip_{step}",
        ):
            _open_skip_question_dialog(question, session, repo)
        return
    st.button(
        "Skip",
        disabled=True,
        help=capabilities.skip_reason_disabled,
        use_container_width=True,
        key=f"conference_disabled_skip_{step}",
    )
    disabled_reasons = [
        reason
        for reason in (
            capabilities.flag_reason_disabled if not capabilities.can_flag else "",
            capabilities.skip_reason_disabled,
        )
        if reason
    ]
    if disabled_reasons:
        st.caption(" ".join(disabled_reasons))


def _render_question_flag_summary() -> None:
    entries = _question_flag_entries()
    if not entries:
        return
    lines: List[str] = []
    for question_id, payload in entries.items():
        labels = [
            QUESTION_FLAG_LABELS.get(str(flag), str(flag))
            for flag in payload.get("flags", [])
        ]
        body = ", ".join(labels)
        note = str(payload.get("note") or "").strip()
        if note:
            body = f"{body} · {note}" if body else note
        lines.append(f"{_question_prompt_by_id(question_id)}: {body or 'Flagged'}")
    summary_card("Question flags", "<br>".join(lines))


def _infer_mode(submission: Dict[str, Any]) -> str:
    return infer_mode_from_submission(submission, question_set=current_question_set())


def _labels_for(field: str, value: Any) -> str:
    if field == "mode":
        return mode_label(str(value or "quick"), question_set=current_question_set())
    if field in {"wg2_geography_context", "wg2_main_location"} and isinstance(value, dict):
        parts = [
            str(value.get("country_region") or "").strip(),
            str(value.get("institution_location") or "").strip(),
        ]
        geocode_label = str(value.get("geocode_label") or "").strip()
        if geocode_label:
            parts.append(f"Lookup match: {geocode_label}")
        coordinates = str(value.get("coordinates") or "").strip()
        if coordinates:
            parts.append(f"Approx. coordinates: {coordinates}")
        geocode_source = str(value.get("geocode_source") or "").strip()
        if geocode_source:
            parts.append(f"Source: {geocode_source}")
        return " · ".join(part for part in parts if part) or "No answer"
    if field == "scientific_home":
        parts = (
            [
                str(value.get("country") or "").strip(),
                str(value.get("city") or "").strip(),
                str(value.get("institution") or "").strip(),
            ]
            if isinstance(value, dict)
            else []
        )
        return " · ".join(part for part in parts if part) or "Not yet defined"
    if field == "complexity_fingerprint":
        if not isinstance(value, dict):
            return "Deferred"
        tokens = [
            f"{current_question_set().fingerprint_labels.get(axis, axis.title())} {int(value.get(axis, 0) or 0)}"
            for axis in current_question_set().fingerprint_axes
        ]
        if all(token.endswith(" 0") for token in tokens):
            return "Deferred"
        return " · ".join(tokens)
    label_map = field_option_label_map(current_question_set(), field)
    if isinstance(value, list):
        labels = [label_map.get(str(item), str(item)) for item in value if str(item)]
        return ", ".join(labels) if labels else "None selected"
    if isinstance(value, str):
        return label_map.get(value, value) if value else "No answer"
    return str(value or "No answer")


def _field_label(field: str) -> str:
    qset = current_question_set()
    labels = {
        "scientific_home_country": "Scientific home",
    }
    if field in labels:
        return labels[field]
    question = question_by_field(qset, field)
    if question:
        return str(question.prompt)
    return field.replace("_", " ").title()


def _question_title(question: QuestionDefinition) -> str:
    copy = current_question_set().step_copy.get(str(question.step), {})
    return str(copy.get("title") or question.prompt or question.field)


def _question_value(question: QuestionDefinition, payload: Dict[str, Any]) -> Any:
    field = str(question.field)
    if field == "scientific_home":
        return {
            "country": payload.get("scientific_home_country", ""),
            "city": payload.get("scientific_home_city", ""),
            "institution": payload.get("scientific_home_institution", ""),
        }
    return payload.get(field)


def _question_answered(question: QuestionDefinition, payload: Dict[str, Any]) -> bool:
    value = _question_value(question, payload)
    input_type = str(question.input_type)
    if str(question.field) == "wg2_main_location":
        region_value = payload.get("wg2_region")
        region_detail = str(payload.get("wg2_region_detail") or "").strip()
        if region_value or region_detail:
            return True
    if field_for_step(current_question_set(), str(question.step)) == "scientific_home":
        return any(
            str(value.get(key) or "").strip()
            for key in ("country", "city", "institution")
        )
    if input_type == "geography_context" and isinstance(value, dict):
        return any(
            str(value.get(key) or "").strip()
            for key in ("country_region", "institution_location", "coordinates")
        )
    if input_type == "location" and isinstance(value, dict):
        return bool(value.get("display_label") and value.get("place_id"))
    if input_type == "multi":
        return bool(value)
    if input_type == "fingerprint" and isinstance(value, dict):
        return any(
            int(value.get(axis, 0) or 0) > 0
            for axis in current_question_set().fingerprint_axes
        )
    if isinstance(value, str):
        return bool(value.strip())
    return bool(value)


def _question_summary_body(
    question: QuestionDefinition, payload: Dict[str, Any]
) -> str:
    field = str(question.field)
    value = _question_value(question, payload)
    if str(question.input_type) == "text":
        body = html.escape(str(value or "").strip())
    else:
        body = html.escape(_labels_for(field, value))
    free_text_field = str(getattr(question, "free_text_field", "") or "").strip()
    free_text_value = (
        str(payload.get(free_text_field) or "").strip() if free_text_field else ""
    )
    if free_text_value:
        free_text_label = html.escape(
            str(getattr(question, "free_text_label", "") or "Detail")
        )
        detail = html.escape(free_text_value)
        body = (
            f"{body}<br><span style='opacity:.72'>{free_text_label}</span><br>{detail}"
            if body
            else detail
        )
    return body


def _question_summary_entries(
    payload: Dict[str, Any],
    *,
    section: str,
    active_steps: set[str] | None = None,
) -> list[tuple[str, str]]:
    qset = current_question_set()
    profile_fields = set(qset.profile_fields)
    entries: list[tuple[str, str]] = []
    for question in qset.questions:
        field = str(question.field)
        is_profile = field in profile_fields or field == "scientific_home"
        if section == "profile" and not is_profile:
            continue
        if section == "session" and is_profile:
            continue
        if (
            active_steps is not None
            and str(question.step) not in active_steps
            and not (
                str(question.step) == "region"
                and "main_location" in active_steps
                and field == "wg2_region"
            )
        ):
            continue
        if not _question_answered(question, payload):
            continue
        entries.append(
            (_question_title(question), _question_summary_body(question, payload))
        )
    return entries


def _render_question_intro(
    step: str, question: QuestionDefinition | None, copy: Dict[str, str]
) -> None:
    if question:
        prompt = str(question.prompt or "").strip()
        title = str(copy.get("title") or "").strip()
        context = str(getattr(question, "context", "") or "").strip()
        if context:
            st.markdown(
                f'<div class="question-context"><span class="question-context-label">Context:</span> {html.escape(context)}</div>',
                unsafe_allow_html=True,
            )
        elif copy.get("body"):
            st.markdown(
                f'<div class="question-context"><span class="question-context-label">Context:</span> {html.escape(str(copy["body"]))}</div>',
                unsafe_allow_html=True,
            )
        if prompt and prompt != title:
            st.markdown(
                f'<div class="question-title">{html.escape(prompt)}</div>',
                unsafe_allow_html=True,
            )
        return
    if copy.get("body"):
        st.markdown(
            f'<div class="page-subtitle">{html.escape(str(copy["body"]))}</div>',
            unsafe_allow_html=True,
        )
    if copy.get("context"):
        st.markdown(
            f'<div class="helper-text">{html.escape(str(copy["context"]))}</div>',
            unsafe_allow_html=True,
        )


def _render_question_page_header(
    *,
    step_label: str,
    section_title: str,
    question: QuestionDefinition,
    copy: Dict[str, str],
) -> None:
    progress = str(step_label or "").strip()
    title = str(section_title or "").strip()
    if title and progress:
        progress = f"{progress} · {title}"
    elif title:
        progress = title
    if progress:
        st.markdown(
            f'<div class="question-progress">{html.escape(progress)}</div>',
            unsafe_allow_html=True,
        )
    _render_question_intro(str(question.step or ""), question, copy)


def _step_for_field(field: str) -> str:
    qset = current_question_set()
    for step in qset.step_order:
        if field_for_step(qset, step) == field:
            return step
    if field in {
        "scientific_home_country",
        "scientific_home_city",
        "scientific_home_institution",
    }:
        return "scientific_home"
    return ""


def _resume_at_field(field: str, mode: str | None = None) -> None:
    next_mode = mode or str(
        get_draft(question_set=current_question_set()).get("mode") or "standard"
    )
    target_step = _step_for_field(field) or first_active_question_step(
        question_set=current_question_set()
    )
    update_draft(mode=next_mode, submitted=False, question_set=current_question_set())
    set_step(target_step, question_set=current_question_set())
    _set_entry_mode("new")
    st.rerun()


def _load_submission_for_key(
    repo: Any,
    session: Dict[str, Any],
    raw_key: str,
) -> tuple[str | None, Dict[str, Any] | None, str]:
    token = str(raw_key or "").strip()
    if not token:
        return None, None, ""
    session_id = str(session.get("id") or "")
    session_code = str(session.get("session_code") or "")
    allowed_text_ids = text_ids_for_session_code(session_code)
    access_key, error = resolve_access_key_input(
        getattr(repo, "notion_repo", None), token
    )
    if not access_key:
        return None, None, str(error or "")
    access_key_hash = repo.access_key_hash(access_key)
    cache_key = f"{session_id}:{access_key_hash}:{'|'.join(allowed_text_ids)}"
    submission = st.session_state.get("conference_submission_cache")
    if st.session_state.get("conference_submission_cache_key") != cache_key:
        submission = repo.latest_submission_by_access_key_hash(
            session_id=session_id,
            access_key_hash=access_key_hash,
            text_ids=allowed_text_ids,
        )
        if not submission:
            player = getattr(repo.notion_repo, "get_player_by_access_key", lambda _key: None)(access_key)
            if player:
                checkpoint = repo.latest_participation_checkpoint(
                    session_id=session_id,
                    player_id=str(player.get("id") or ""),
                )
                if checkpoint and isinstance(checkpoint.get("state"), dict):
                    submission = dict(checkpoint["state"])
                    submission["_checkpoint_position"] = str(
                        checkpoint.get("current_position") or ""
                    )
                    submission["_checkpoint"] = True
        st.session_state["conference_submission_cache_key"] = cache_key
        st.session_state["conference_submission_cache"] = submission
    return access_key, submission, ""


def _hydrate_existing_submission(repo: Any, session: Dict[str, Any]) -> None:
    if st.session_state.get("conference_hydrated"):
        return
    draft = get_draft(question_set=current_question_set())
    raw_key = str(
        draft.get("access_key")
        or st.session_state.pop("conference_recovered_access_key", "")
        or st.query_params.get("key", "")
        or ""
    ).strip()
    if not raw_key:
        st.session_state["conference_hydrated"] = True
        return
    access_key, submission, _ = _load_submission_for_key(repo, session, raw_key)
    if access_key and submission:
        checkpoint_position = str(submission.get("_checkpoint_position") or "")
        is_checkpoint = bool(submission.get("_checkpoint"))
        submission = _normalize_hydrated_submission(submission)
        hydrated = {
            key: value
            for key, value in submission.items()
            if key in get_draft(question_set=current_question_set())
        }
        hydrated["mode"] = str(submission.get("mode") or _infer_mode(submission))
        hydrated["access_key"] = access_key
        hydrated["submitted"] = not is_checkpoint
        update_draft(question_set=current_question_set(), **hydrated)
        player = repo.upsert_conference_player(
            session_id=str(session.get("id") or ""),
            access_key=access_key,
            payload=build_session_payload(
                get_draft(question_set=current_question_set()),
                question_set=current_question_set(),
            ),
            identity_metadata=build_identity_metadata(
                get_draft(question_set=current_question_set()),
                question_set=current_question_set(),
            ),
        )
        if player and str(player.get("id") or ""):
            _bind_checkpoint_player(
                session, access_key, str(player.get("id") or "")
            )
        if is_checkpoint and checkpoint_position:
            set_step(checkpoint_position, question_set=current_question_set())
            _set_entry_mode("new")
        else:
            _set_entry_mode("dashboard")
    elif access_key:
        update_draft(question_set=current_question_set(), access_key=access_key)
    st.session_state["conference_hydrated"] = True


def _advance_step() -> None:
    next_step(question_set=current_question_set())


def _next_position() -> str:
    sequence = active_step_sequence(question_set=current_question_set())
    step = current_step()
    if step not in sequence:
        return sequence[0]
    index = sequence.index(step)
    return sequence[min(index + 1, len(sequence) - 1)]


def _bound_checkpoint_player_id(
    session: Dict[str, Any], access_key: str
) -> str:
    binding = st.session_state.get(PLAYER_BINDING_KEY)
    if not isinstance(binding, Mapping):
        return ""
    expected_key_hash = hashlib.sha256(access_key.encode("utf-8")).hexdigest()
    if str(binding.get("session_id") or "") != str(session.get("id") or ""):
        return ""
    if str(binding.get("access_key_hash") or "") != expected_key_hash:
        return ""
    return str(binding.get("player_id") or "")


def _bind_checkpoint_player(
    session: Dict[str, Any], access_key: str, player_id: str
) -> None:
    st.session_state[PLAYER_BINDING_KEY] = {
        "session_id": str(session.get("id") or ""),
        "access_key_hash": hashlib.sha256(access_key.encode("utf-8")).hexdigest(),
        "player_id": str(player_id or ""),
    }


def _persist_participation_checkpoint(
    repo: Any, session: Dict[str, Any], *, next_position: str
) -> bool:
    draft = get_draft(question_set=current_question_set())
    access_key = _ensure_access_key()
    payload = _payload_for_session(draft, session)
    config = event_config_for_session_code(str(session.get("session_code") or ""))
    try:
        player_id = _bound_checkpoint_player_id(session, access_key)
        reused_player = bool(player_id)
        player: Dict[str, Any] | None = None
        player_started = time.perf_counter()
        if not player_id and config and config.identity_policy.identified:
            profile = {
                "name": str(draft.get("name") or "").strip(),
                "email": normalize_email(str(draft.get("email") or "")),
                "institution": str(draft.get("institution") or "").strip(),
                "base_location": deepcopy(draft.get("base_location") or {}),
            }
            if not profile["name"]:
                raise ValueError("Name is required.")
            player = repo.upsert_identified_conference_player(
                session_id=str(session.get("id") or ""),
                access_key=access_key,
                payload=payload,
                identity_profile=profile,
            )
        elif not player_id:
            player = repo.upsert_conference_player(
                session_id=str(session.get("id") or ""),
                access_key=access_key,
                payload=payload,
                identity_metadata=build_identity_metadata(
                    draft, question_set=current_question_set()
                ),
            )
        if player is not None:
            player_id = str(player.get("id") or "")
        if not player_id:
            raise RuntimeError("Participant identity was not stored.")
        _bind_checkpoint_player(session, access_key, player_id)
        log_perf(
            "iceicebaby.conference",
            "checkpoint_player_resolve",
            (time.perf_counter() - player_started) * 1000.0,
            reused=reused_player,
        )
        checkpoint_started = time.perf_counter()
        repo.save_participation_checkpoint(
            session_id=str(session.get("id") or ""),
            session_code=str(session.get("session_code") or ""),
            player_id=player_id,
            text_id=str(_event_context(session).get("text_id") or ""),
            device_id=str(st.session_state.get("conference_device_id") or ""),
            state=dict(draft),
            current_position=next_position,
            completion_state="in_progress",
            test_mode=bool(_event_context(session).get("test_mode")),
        )
        log_perf(
            "iceicebaby.conference",
            "checkpoint_write",
            (time.perf_counter() - checkpoint_started) * 1000.0,
            next_position=next_position,
        )
    except Exception as exc:
        st.error(f"Could not save your progress: {exc}")
        return False
    return True


def _normalize_hydrated_submission(submission: Dict[str, Any]) -> Dict[str, Any]:
    normalized = dict(submission)
    provenance = normalized.get("question_provenance")
    if not isinstance(provenance, Mapping):
        session_block = normalized.get("session")
        provenance = (
            session_block.get("question_provenance", {})
            if isinstance(session_block, Mapping)
            else {}
        )
    reask = questions_requiring_reanswer(current_question_set(), provenance)
    if reask:
        states = deepcopy(dict(normalized.get("question_states") or {}))
        for question in reask:
            if question.input_type in {"multi"}:
                normalized[question.field] = []
            elif question.input_type in {"location", "geography_context", "scientific_home"}:
                normalized[question.field] = {}
            else:
                normalized[question.field] = ""
            prior_state = dict(states.get(question.question_id) or {})
            prior_state["answer_state"] = "unanswered"
            states[question.question_id] = prior_state
        normalized["question_states"] = states
        normalized["updated_question_ids"] = [q.question_id for q in reask]
    allowed_roles = field_value_set(current_question_set(), "role")
    role_question = question_by_field(current_question_set(), "role")
    role_extra_field = (
        str(getattr(role_question, "free_text_field", "") or "").strip()
        if role_question
        else ""
    )
    roles = normalized.get("role")
    role_values = (
        [str(item).strip() for item in roles if str(item).strip()]
        if isinstance(roles, list)
        else []
    )
    role_extra = str(
        normalized.get(role_extra_field) or normalized.get("role_custom") or ""
    ).strip()
    if not role_extra:
        extras = [item for item in role_values if item not in allowed_roles]
        role_extra = extras[0] if extras else ""
    normalized["role"] = [item for item in role_values if item in allowed_roles]
    normalized["role_custom"] = role_extra
    if role_extra_field:
        normalized[role_extra_field] = role_extra
    return normalized


def _ensure_access_key() -> str:
    access_key = str(
        get_draft(question_set=current_question_set()).get("access_key") or ""
    ).strip()
    if access_key:
        return access_key
    access_key = generate_hex_key()
    update_draft(question_set=current_question_set(), access_key=access_key)
    return access_key


def _payload_for_session(
    draft: Dict[str, Any], session: Dict[str, Any]
) -> Dict[str, Any]:
    payload = build_session_payload(draft, question_set=current_question_set())
    profile = payload.get("profile") if isinstance(payload.get("profile"), dict) else {}
    session_payload = (
        payload.get("session") if isinstance(payload.get("session"), dict) else {}
    )
    profile["persistence_scope"] = "persistent_profile"
    context = _event_context(session)
    session_payload["event_slug"] = context["event_slug"]
    session_payload["event_label"] = context["event_label"]
    session_payload["event_code"] = context["event_code"]
    session_payload["event_location"] = context["event_location"]
    session_payload["event_status"] = str(context.get("event_status") or "")
    session_payload["session_code"] = str(session.get("session_code") or "")
    session_payload["session_id"] = str(session.get("id") or "")
    session_payload["text_id"] = context["text_id"]
    session_payload["schema_id"] = str(
        current_question_set().schema_id or context["schema_id"]
    )
    session_payload["questionnaire_version"] = str(
        current_question_set().version or "1"
    )
    session_payload["question_set_id"] = context["question_set_id"]
    session_payload["questionnaire_id"] = str(current_question_set().id)
    session_payload["questionnaire_revision"] = int(current_question_set().revision)
    session_payload["questionnaire_format"] = int(current_question_set().format)
    session_payload["questionnaire_status"] = str(current_question_set().status)
    session_payload["response_scope"] = context["response_scope"]
    session_payload["test_mode"] = bool(context.get("test_mode"))
    if context.get("test_mode"):
        session_payload["data_classification"] = "debug"
    payload["profile"] = profile
    payload["session"] = session_payload
    return payload


def _render_event_scope_notice(session: Dict[str, Any]) -> None:
    context = _event_context(session)
    config = event_config_for_session_code(str(session.get("session_code") or ""))
    if config and config.identity_policy.identified:
        return
    route = _public_route()
    if str(context.get("event_slug") or "").strip() == "dalembertiennes":
        body = (
            "You are answering the D’Alembertiennes version of the climate questionnaire. "
            "Questions may evolve or may persist across events. Steal this format!"
        )
    elif route:
        body = str(route.welcome_note or "").strip()
    else:
        body = (
            f"This response belongs to {_event_scope_text(session)}. "
            "Profile questions persist across events; session answers belong only to this event."
        )
    if _event_is_read_only(session):
        body += (
            f" This event is currently {str(context.get('event_status') or 'closed')}; "
            "new responses are read-only."
        )
    st.markdown(
        f'<div class="caption">{html.escape(body)}</div>',
        unsafe_allow_html=True,
    )


def _render_test_mode_notice(session: Dict[str, Any]) -> None:
    context = _event_context(session)
    if not context.get("test_mode"):
        return
    st.caption(
        "TEST MODE · This run is isolated from production participants and results."
    )


def _open_skip_question_dialog(
    question: QuestionDefinition,
    session: Dict[str, Any],
    repo: Any,
) -> None:
    question_id = str(question.question_id or "").strip()
    field = str(question.field or "").strip()
    existing = _question_skip_entries().get(question_id, {})

    @st.dialog("Skip question")
    def _skip_dialog() -> None:
        st.markdown(f"### {question.prompt}")
        st.markdown(
            f'<div class="caption">{html.escape(QUESTION_SKIP_INTRO)}</div>',
            unsafe_allow_html=True,
        )
        selected = st.pills(
            "Why skip?",
            [str(item["value"]) for item in QUESTION_SKIP_OPTIONS],
            default=list(existing.get("reasons") or []),
            selection_mode="multi",
            format_func=lambda value: QUESTION_SKIP_LABELS.get(value, value),
            key=f"conference_skip_flags_{question_id}",
        )
        note = st.text_area(
            "Optional note",
            value=str(existing.get("note") or ""),
            key=f"conference_skip_note_{question_id}",
            placeholder="A short reason for skipping this question",
            height=140,
        )
        if st.button("Skip and continue", type="primary", use_container_width=True):
            _set_question_skip(
                question_id, reasons=list(selected), note=str(note or "").strip()
            )
            _clear_question_answer(question)
            draft = get_draft(question_set=current_question_set())
            update_draft(
                question_set=current_question_set(),
                question_states=skip_question(
                    draft.get("question_states"), question_id
                ),
            )
            if field in set(current_question_set().deferrable_fields):
                defer_field(field, question_set=current_question_set())
            _log_route_event(
                session,
                event_type="question_skipped",
                step=str(question.step or ""),
                question=question,
                value_label=", ".join(selected) or str(note or "").strip(),
                extra={"note": str(note or "").strip()},
            )
            if not _persist_participation_checkpoint(
                repo, session, next_position=_next_position()
            ):
                return
            _advance_step()
            st.rerun()

    _skip_dialog()


def _submit(repo: Any, session: Dict[str, Any]) -> None:
    if _event_is_read_only(session):
        st.error(
            f"{_event_context(session)['event_label']} is read-only right now. "
            "New responses are closed for this event."
        )
        return
    draft = get_draft(question_set=current_question_set())
    payload = _payload_for_session(draft, session)
    event_context = _event_context(session)
    identity_metadata = build_identity_metadata(
        draft, question_set=current_question_set()
    )
    access_key = _ensure_access_key()
    access_key_hash = repo.access_key_hash(access_key)
    access_key_last4 = emoji_suffix(access_key)
    try:
        config = event_config_for_session_code(str(session.get("session_code") or ""))
        if config and config.identity_policy.identified:
            player = repo.upsert_identified_conference_player(
                session_id=session["id"],
                access_key=access_key,
                payload=payload,
                identity_profile={
                    "name": draft.get("name"),
                    "email": draft.get("email"),
                    "institution": draft.get("institution"),
                    "base_location": deepcopy(draft.get("base_location") or {}),
                },
            )
        else:
            player = repo.upsert_conference_player(
                session_id=session["id"],
                access_key=access_key,
                payload=payload,
                identity_metadata=identity_metadata,
            )
        submission_id = str(
            st.session_state.get("conference_submission_id") or uuid.uuid4()
        )
        st.session_state["conference_submission_id"] = submission_id
        saved = repo.save_session_response_set(
            session["id"],
            str((player or {}).get("id") or ""),
            _event_context(session)["text_id"],
            str(st.session_state.get("conference_device_id", "")),
            access_key_hash,
            access_key_last4,
            payload,
            identity_metadata,
            submission_id=submission_id,
            revision_id=submission_id,
            write_idempotency_key=submission_id,
        )
        repo.save_participation_checkpoint(
            session_id=str(session.get("id") or ""),
            session_code=str(session.get("session_code") or ""),
            player_id=str((player or {}).get("id") or ""),
            text_id=str(event_context.get("text_id") or ""),
            device_id=str(st.session_state.get("conference_device_id") or ""),
            state=dict(draft),
            current_position="done",
            completion_state="complete",
            test_mode=bool(event_context.get("test_mode")),
        )
    except Exception as exc:
        _log_route_event(
            session,
            event_type="write_failed",
            step="review",
            status="error",
            player_id=str((locals().get("player") or {}).get("id") or ""),
            value_label=str(exc),
            level="ERROR",
            extra={"error": str(exc)},
        )
        st.error(f"Could not save this WG2 submission: {exc}")
        return
    st.session_state["conference_submission_cache_key"] = (
        f"{session['id']}:{access_key_hash}:{event_context['text_id']}"
    )
    st.session_state["conference_submission_cache"] = build_payload_view(
        draft, question_set=current_question_set()
    ) | {
        "access_key_hash": access_key_hash,
        "access_key_last4": access_key_last4,
        "actor_key": f"player:{str((player or {}).get('id') or '')}"
        if (player or {}).get("id")
        else f"response:{access_key_hash}",
        "response_id": str(saved.get("response_id") or ""),
        "submission_id": str(saved.get("submission_id") or ""),
        "revision_id": str(saved.get("revision_id") or ""),
    }
    st.session_state["conference_show_success"] = True
    update_draft(
        question_set=current_question_set(), access_key=access_key, submitted=True
    )
    _log_route_event(
        session,
        event_type="route_submitted",
        step="review",
        player_id=str((player or {}).get("id") or ""),
        value_label=access_key_last4,
        extra={
            "access_key_last4": access_key_last4,
            "submitted_mode": str(draft.get("mode") or ""),
        },
    )
    mark_submitted(question_set=current_question_set())


def _open_confirm_send_dialog(repo: Any, session: Dict[str, Any]) -> None:
    @st.dialog("Save this key")
    def _confirm_send_dialog() -> None:
        access_key = _ensure_access_key()
        emoji_key = hex_to_emoji(access_key)
        emoji_symbols = split_emoji_symbols(emoji_key)
        short_emoji = (
            "".join(emoji_symbols[-4:]) if len(emoji_symbols) >= 4 else emoji_key
        )
        st.markdown(
            f"""
            <div style="text-align:center; font-size:4.6rem; line-height:1.15; letter-spacing:0; margin: 1rem 0 1.15rem 0;">
                {short_emoji}
            </div>
            """,
            unsafe_allow_html=True,
        )
        components.html(
            f"""
            <div style="display:flex; justify-content:center; margin: .5rem 0 1rem 0; background: transparent;">
              <button
                onclick="navigator.clipboard.writeText({short_emoji!r})"
                style="
                  border: 1px solid #0f6d62;
                  border-radius: 999px;
                  background: #0f6d62;
                  color: #ffffff;
                  padding: .78rem 1.2rem;
                  font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif;
                  font-size: 1rem;
                  line-height: 1.2;
                  font-weight: 700;
                  cursor: pointer;
                  box-shadow: 0 8px 24px rgba(15, 109, 98, 0.18);
                "
              >
                ⧉ Copy the emoji key
              </button>
            </div>
            """,
            height=64,
        )
        config = event_config_for_session_code(str(session.get("session_code") or ""))
        if config and config.identity_policy.identified:
            st.markdown("### This key lets you return to your answers later.")
            st.caption("Your email can also help a host recover access if you lose the key.")
        else:
            st.markdown("### Save this key to return to your answers later.")
        if st.button("I saved a screenshot", type="primary", use_container_width=True):
            _submit(repo, session)
            st.rerun()

    _confirm_send_dialog()


def _start_new_participant() -> None:
    reset_flow_state(question_set=current_question_set())
    _clear_login_error()
    st.session_state["conference_hide_migration_prompt"] = False
    _set_entry_mode("new")
    st.rerun()


def _open_existing_login() -> None:
    _clear_login_error()
    _set_entry_mode("existing")


def _login_with_key(repo: Any, session: Dict[str, Any], raw_key: str) -> None:
    access_key, submission, error = _load_submission_for_key(repo, session, raw_key)
    if not access_key:
        _set_login_error(error or "This access key could not be decoded.")
        return
    update_draft(question_set=current_question_set(), access_key=access_key)
    if not submission:
        _set_login_error("No submission or saved progress was found for this access key yet.")
        return
    submission = _normalize_hydrated_submission(submission)
    hydrated = {
        key: value
        for key, value in submission.items()
        if key in get_draft(question_set=current_question_set())
    }
    hydrated["mode"] = str(submission.get("mode") or _infer_mode(submission))
    hydrated["access_key"] = access_key
    hydrated["submitted"] = not bool(submission.get("_checkpoint"))
    update_draft(question_set=current_question_set(), **hydrated)
    repo.upsert_conference_player(
        session_id=str(session.get("id") or ""),
        access_key=access_key,
        payload=build_session_payload(
            get_draft(question_set=current_question_set()),
            question_set=current_question_set(),
        ),
        identity_metadata=build_identity_metadata(
            get_draft(question_set=current_question_set()),
            question_set=current_question_set(),
        ),
    )
    _clear_login_error()
    checkpoint_position = str(submission.get("_checkpoint_position") or "")
    if checkpoint_position and not hydrated["submitted"]:
        set_step(checkpoint_position, question_set=current_question_set())
        _set_entry_mode("new")
    else:
        _set_entry_mode("dashboard")
    st.rerun()


def _resume_in_mode(mode: str) -> None:
    update_draft(question_set=current_question_set(), mode=mode, submitted=False)
    set_step(
        first_active_question_step(question_set=current_question_set()),
        question_set=current_question_set(),
    )
    _set_entry_mode("new")
    st.rerun()


def _render_entry(session: Dict[str, Any], repo: Any) -> None:
    route = _public_route()
    existing_credentials_allowed = True
    if route:
        with st.container(key="conference_entry_card"):
            _render_public_entry_hero(route)
            if st.button(
                "🆕 New participant",
                type="primary",
                use_container_width=True,
                disabled=_event_is_read_only(session),
                help=(
                    "New responses are closed for this event."
                    if _event_is_read_only(session)
                    else None
                ),
            ):
                _start_new_participant()
            if existing_credentials_allowed and st.button(
                "🔑 I already have an access key", use_container_width=True
            ):
                _open_existing_login()
                st.rerun()
            if existing_credentials_allowed and str(route.path or "") == "un-wg2-icebreaker" and st.button(
                "↩ I contributed before",
                use_container_width=True,
            ):
                st.switch_page("pages/32_UN_WG2_Member.py")
    else:
        conference_header(_public_entry_title(session), "", step="")
        st.markdown(
            '<div class="page-subtitle">Anonymous first.</div>',
            unsafe_allow_html=True,
        )
        _render_event_scope_notice(session)
        st.markdown(
            '<div class="entry-action-title">Choose how to enter</div>',
            unsafe_allow_html=True,
        )
        if st.button(
            "🆕 New participant",
            type="primary",
            use_container_width=True,
            disabled=_event_is_read_only(session),
            help=(
                "New responses are closed for this event."
                if _event_is_read_only(session)
                else None
            ),
        ):
            _start_new_participant()
        if existing_credentials_allowed and st.button(
            "🔑 I already have an access key", use_container_width=True
        ):
            _open_existing_login()
            st.rerun()
    if _event_context(session).get("test_mode"):
        st.caption(
            "Only a test participant key with saved progress in this debug session can "
            "be resumed here. Production progress is never loaded into test mode."
        )
    if _entry_mode() == "existing" and existing_credentials_allowed:
        st.markdown("### Enter your emoji access key.")
        with st.form("conference_existing_key_form"):
            raw_key = st.text_area(
                "Access key",
                value=str(
                    get_draft(question_set=current_question_set()).get("access_key")
                    or ""
                ),
                key="conference_existing_key",
                placeholder="Paste your 4-emoji or full access key here",
                label_visibility="collapsed",
                height=110,
            )
            open_dashboard = st.form_submit_button(
                "Open my dashboard",
                type="primary",
                use_container_width=True,
            )
        if open_dashboard:
            _login_with_key(repo, session, raw_key)
        if st.button(
            f"Open the {_event_context(session)['event_label']} overview",
            use_container_width=True,
            key="conference-entry-open-overview",
        ):
            _switch_to_event_overview(session)
        error = str(st.session_state.get(LOGIN_ERROR_KEY, "") or "")
        if error:
            st.warning(error)
    elif _event_is_read_only(session):
        st.info(
            f"{_event_context(session)['event_label']} is currently "
            f"{_event_context(session)['event_status']}. Existing responses stay visible, "
            "but new submissions are closed."
        )


def _render_welcome() -> None:
    qset = current_question_set()
    if not qset.show_mode_selection:
        cta = str(qset.step_copy["welcome"].get("cta") or "Start")
        if st.button(
            cta,
            type="primary",
            use_container_width=True,
            key="conference_mode_default",
        ):
            _mode_start(str(qset.default_mode or "standard"))
    else:
        st.markdown(
            '<div class="section-title">Choose a depth.</div>',
            unsafe_allow_html=True,
        )
        st.markdown(
            '<div class="helper-text">Quick is the lightest route. Standard and Deep expose more profile and laboratory questions, including career stage.</div>',
            unsafe_allow_html=True,
        )
        cards = mode_cards(question_set=qset)
        for row in cards:
            mode = str(row.get("value") or "").strip()
            button_label = f"{row['accent']} {row['title']}\n{row['detail']}"
            if st.button(
                button_label,
                type="primary" if mode == "quick" else "secondary",
                use_container_width=True,
                key=f"conference_mode_{mode}",
            ):
                _mode_start(mode)
    summary_card("Anonymous first", current_question_set().step_copy["welcome"]["note"])


def _render_boiler_room_expander() -> None:
    if not _is_laptop_device():
        return
    draft = get_draft(question_set=current_question_set())
    with st.expander("Optional material or note", expanded=False):
        st.markdown(
            '<div class="caption">Add a short note, a link, a document reference, or any material you want connected to this first coordination layer.</div>',
            unsafe_allow_html=True,
        )
        contribution = st.text_area(
            "Boiler room contribution",
            value=str(draft.get("boiler_room_contribution") or ""),
            key="conference_widget_boiler_room_contribution",
            placeholder="Describe what you want to bring, or paste a link.",
            max_chars=1000,
            label_visibility="collapsed",
            height=160,
        )
        update_draft(
            question_set=current_question_set(), boiler_room_contribution=contribution
        )


def _render_pills(question: QuestionDefinition, current_value: Any) -> None:
    field = str(question.field)
    option_map = {str(item["value"]): str(item["label"]) for item in question.options}
    input_type = str(question.input_type)
    if input_type == "multi":
        selected = st.pills(
            question.prompt,
            list(option_map.keys()),
            default=list(current_value or [])
            if isinstance(current_value, list)
            else [],
            selection_mode="multi",
            key=f"conference_widget_{field}",
            format_func=lambda value: option_map.get(value, value),
            label_visibility="collapsed",
        )
        max_select = question.max_select
        if isinstance(max_select, int) and len(selected) > max_select:
            selected = selected[:max_select]
        update_draft(question_set=current_question_set(), **{field: list(selected)})
        if selected:
            clear_deferred_field(field, question_set=current_question_set())
        selected_values = set(selected)
    else:
        selected_single = st.pills(
            question.prompt,
            list(option_map.keys()),
            default=str(current_value)
            if isinstance(current_value, str) and current_value
            else None,
            selection_mode="single",
            key=f"conference_widget_{field}",
            format_func=lambda value: option_map.get(value, value),
            label_visibility="collapsed",
        )
        update_draft(
            question_set=current_question_set(), **{field: str(selected_single or "")}
        )
        if selected_single:
            clear_deferred_field(field, question_set=current_question_set())
        selected_values = {str(selected_single)} if selected_single else set()

    free_text_field = str(getattr(question, "free_text_field", "") or "").strip()
    has_other_option = "other" in option_map
    show_free_text = bool(
        free_text_field
        and (not has_other_option or "other" in selected_values)
    )
    if show_free_text:
        detail_value = st.text_input(
            str(getattr(question, "free_text_label", "") or "Detail"),
            value=str(
                get_draft(question_set=current_question_set()).get(free_text_field)
                or ""
            ),
            key=f"conference_widget_{free_text_field}",
            placeholder=str(getattr(question, "free_text_placeholder", "") or ""),
        )
        update_draft(
            question_set=current_question_set(),
            **{free_text_field: str(detail_value or "").strip()},
        )
    elif free_text_field and get_draft(question_set=current_question_set()).get(
        free_text_field
    ):
        update_draft(question_set=current_question_set(), **{free_text_field: ""})


def _render_scientific_home() -> None:
    draft = get_draft(question_set=current_question_set())
    country = st.text_input(
        "Country",
        value=str(draft.get("scientific_home_country") or ""),
        key="conference_widget_scientific_home_country",
        placeholder="Country",
    )
    city = st.text_input(
        "City",
        value=str(draft.get("scientific_home_city") or ""),
        key="conference_widget_scientific_home_city",
        placeholder="City",
    )
    institution = st.text_input(
        "Institution (optional)",
        value=str(draft.get("scientific_home_institution") or ""),
        key="conference_widget_scientific_home_institution",
        placeholder="Institution (optional)",
    )
    update_draft(
        question_set=current_question_set(),
        scientific_home_country=country,
        scientific_home_city=city,
        scientific_home_institution=institution,
    )


def _opencage_api_key() -> str:
    try:
        cfg = st.secrets.get("opencage", {})
    except Exception:
        return ""
    for key in ("OPENCAGE_KEY", "api_key", "key"):
        value = str(cfg.get(key, "") or "").strip() if hasattr(cfg, "get") else ""
        if value:
            return value
    return ""


def _location_lookup_query(country_region: str, institution_location: str) -> str:
    return ", ".join(
        part
        for part in (
            str(institution_location or "").strip(),
            str(country_region or "").strip(),
        )
        if part
    )


def _lookup_location_coordinates(query: str) -> dict[str, Any]:
    token = str(query or "").strip()
    if not token:
        raise ValueError("Enter a country, region, city, or institution first.")
    api_key = _opencage_api_key()
    if not api_key:
        raise RuntimeError("OpenCage is not configured in Streamlit secrets.")
    response = requests.get(
        OPENCAGE_ENDPOINT,
        params={
            "q": token,
            "key": api_key,
            "limit": 1,
            "no_annotations": 1,
            "language": "en",
        },
        timeout=8,
    )
    response.raise_for_status()
    return parse_opencage_result(response.json(), token)


def _lookup_location_options(query: str):
    token = str(query or "").strip()
    if not token:
        return []
    api_key = _opencage_api_key()
    if not api_key:
        raise RuntimeError("Location lookup is not configured.")
    response = requests.get(
        OPENCAGE_ENDPOINT,
        params={"q": token, "key": api_key, "limit": 5, "language": "en"},
        timeout=8,
    )
    response.raise_for_status()
    return opencage_location_options(response.json())


def _render_geography_context_body(
    question: QuestionDefinition, session: Dict[str, Any]
) -> None:
    draft = get_draft(question_set=current_question_set())
    existing = draft.get(str(question.field), {})
    current = existing if isinstance(existing, dict) else {}
    country_region = st.text_input(
        "Country, region, or main base",
        value=str(current.get("country_region") or ""),
        key=f"conference_widget_{question.field}_country_region",
        placeholder="Country, region, or main base",
    )
    institution_location = st.text_input(
        "Institution or city",
        value=str(current.get("institution_location") or ""),
        key=f"conference_widget_{question.field}_institution_location",
        placeholder="Institution, city, or local context",
    )
    lookup_query = _location_lookup_query(country_region, institution_location)
    state_key = f"conference_location_lookup_{question.field}"
    now = time.monotonic()
    state = st.session_state.get(state_key)
    if not isinstance(state, dict):
        existing_query = str(
            current.get("raw_input") or current.get("geocode_query") or ""
        ).strip()
        has_existing_match = bool(
            current.get("resolved_label") or current.get("geocode_label")
        )
        state = {
            "scheduled_query": lookup_query,
            "scheduled_at": now,
            "attempted_query": lookup_query if has_existing_match and existing_query == lookup_query else "",
            "status": str(current.get("lookup_status") or "")
            or ("success" if has_existing_match else "pending"),
            "editing": False,
        }
    if lookup_query != str(state.get("scheduled_query") or ""):
        state.update(
            {
                "scheduled_query": lookup_query,
                "scheduled_at": now,
                "status": "pending" if lookup_query else "",
                "editing": False,
            }
        )
        current = {
            **current,
            "raw_input": lookup_query,
            "resolved_label": "",
            "country": "",
            "region": "",
            "city": "",
            "approximate_latitude": None,
            "approximate_longitude": None,
            "source": "",
            "confirmation_state": "pending" if lookup_query else "",
            "lookup_status": "pending" if lookup_query else "",
            "lookup_error": "",
            "coordinates": "",
            "coordinates_consent": "",
            "geocode_query": lookup_query,
            "geocode_label": "",
            "geocode_source": "",
        }
    if location_lookup_due(
        query=lookup_query,
        scheduled_query=str(state.get("scheduled_query") or ""),
        scheduled_at=float(state.get("scheduled_at") or 0.0),
        attempted_query=str(state.get("attempted_query") or ""),
        now=now,
        debounce_seconds=LOCATION_DEBOUNCE_SECONDS,
    ):
        state["attempted_query"] = lookup_query
        state["status"] = "looking_up"
        _log_route_event(
            session,
            event_type="location_lookup_started",
            step=str(question.step or ""),
            question=question,
            value_label=lookup_query,
        )
        try:
            with st.spinner("Looking up approximate coordinates..."):
                looked_up = _lookup_location_coordinates(lookup_query)
            current = {
                **current,
                **looked_up,
            }
            state["status"] = "success"
            _log_route_event(
                session,
                event_type="location_lookup_succeeded",
                step=str(question.step or ""),
                question=question,
                value_label=str(looked_up.get("resolved_label") or ""),
                extra={
                    "query": lookup_query,
                    "source": str(looked_up.get("source") or ""),
                },
            )
        except Exception as exc:
            current = location_lookup_failure(current, lookup_query, str(exc))
            state["status"] = "failure"
            _log_route_event(
                session,
                event_type="location_lookup_failed",
                step=str(question.step or ""),
                question=question,
                status="error",
                value_label=lookup_query,
                level="WARNING",
                extra={"error": str(exc)},
            )

    resolved_label = str(
        current.get("resolved_label") or current.get("geocode_label") or ""
    ).strip()
    lookup_status = str(current.get("lookup_status") or state.get("status") or "")
    if lookup_status in {"pending", "looking_up"} and lookup_query:
        st.markdown(
            '<div class="caption">Finding an approximate location…</div>',
            unsafe_allow_html=True,
        )
    if resolved_label and lookup_status == "success" and not bool(state.get("editing")):
        st.markdown(
            (
                '<div class="helper-text"><strong>Approximate location found:</strong><br>'
                f"{html.escape(resolved_label)}</div>"
            ),
            unsafe_allow_html=True,
        )
        confirm_col, edit_col = st.columns(2)
        with confirm_col:
            if st.button(
                "Looks right",
                type="primary",
                use_container_width=True,
                key=f"conference_widget_{question.field}_confirm_location",
            ):
                current = confirm_location(current)
                _log_route_event(
                    session,
                    event_type="location_lookup_confirmed",
                    step=str(question.step or ""),
                    question=question,
                    value_label=resolved_label,
                )
        with edit_col:
            if st.button(
                "Edit location",
                use_container_width=True,
                key=f"conference_widget_{question.field}_edit_location",
            ):
                state["editing"] = True
                _log_route_event(
                    session,
                    event_type="location_correction_started",
                    step=str(question.step or ""),
                    question=question,
                    value_label=resolved_label,
                )

    if lookup_status == "failure":
        st.warning(
            "We could not locate this automatically. You can continue with the text "
            "you entered or add an approximate place manually."
        )
        if st.button(
            "Add an approximate place manually",
            use_container_width=True,
            key=f"conference_widget_{question.field}_manual_location",
        ):
            state["editing"] = True

    if bool(state.get("editing")):
        manual_label = st.text_input(
            "Resolved place",
            value=resolved_label or lookup_query,
            key=f"conference_widget_{question.field}_resolved_label",
        )
        manual_city = st.text_input(
            "City",
            value=str(current.get("city") or ""),
            key=f"conference_widget_{question.field}_resolved_city",
        )
        manual_region = st.text_input(
            "Region",
            value=str(current.get("region") or ""),
            key=f"conference_widget_{question.field}_resolved_region",
        )
        manual_country = st.text_input(
            "Country",
            value=str(current.get("country") or ""),
            key=f"conference_widget_{question.field}_resolved_country",
        )
        lat_col, lng_col = st.columns(2)
        with lat_col:
            manual_latitude = st.text_input(
                "Approximate latitude (optional)",
                value=str(current.get("approximate_latitude") or ""),
                key=f"conference_widget_{question.field}_resolved_latitude",
            )
        with lng_col:
            manual_longitude = st.text_input(
                "Approximate longitude (optional)",
                value=str(current.get("approximate_longitude") or ""),
                key=f"conference_widget_{question.field}_resolved_longitude",
            )
        if st.button(
            "Save location correction",
            type="primary",
            use_container_width=True,
            key=f"conference_widget_{question.field}_save_location_correction",
        ):
            try:
                current = correct_location(
                    current,
                    resolved_label=manual_label,
                    country=manual_country,
                    region=manual_region,
                    city=manual_city,
                    latitude=manual_latitude,
                    longitude=manual_longitude,
                )
            except ValueError:
                st.warning("Use decimal numbers for latitude and longitude, or leave them blank.")
            else:
                state["editing"] = False
                state["status"] = "success"
                _log_route_event(
                    session,
                    event_type="location_corrected",
                    step=str(question.step or ""),
                    question=question,
                    value_label=str(current.get("resolved_label") or ""),
                    extra={"source": "manual_correction"},
                )

    current = {
        **current,
        "country_region": str(country_region or "").strip(),
        "institution_location": str(institution_location or "").strip(),
        "raw_input": lookup_query,
    }
    st.session_state[state_key] = state
    update_draft(
        question_set=current_question_set(),
        **{str(question.field): current},
    )


@st.fragment(run_every=0.2)
def _render_geography_context(
    question: QuestionDefinition, session: Dict[str, Any]
) -> None:
    _render_geography_context_body(question, session)


def _render_wg2_spatial_context(
    question: QuestionDefinition,
    session: Dict[str, Any],
    *,
    use_location_fragment: bool = True,
) -> None:
    if use_location_fragment:
        _render_geography_context(question, session)
    else:
        _render_geography_context_body(question, session)
    if "region" in active_question_steps(question_set=current_question_set()):
        return
    region_question = question_by_step(current_question_set(), "region")
    if not region_question:
        return
    st.markdown(
        '<div class="section-title">Which regions matter in your work?</div>',
        unsafe_allow_html=True,
    )
    if str(region_question.context or "").strip():
        st.markdown(
            f'<div class="question-context">{html.escape(str(region_question.context))}</div>',
            unsafe_allow_html=True,
        )
    draft = get_draft(question_set=current_question_set())
    _render_pills(region_question, draft.get(str(region_question.field)))


def _render_scale(question: QuestionDefinition, current_value: Any) -> None:
    try:
        default_value = int(current_value)
    except Exception:
        default_value = 0
    value = st.slider(
        "Resonance",
        min_value=-5,
        max_value=5,
        value=default_value,
        key=f"conference_widget_{question.field}",
        label_visibility="collapsed",
    )
    st.markdown(
        '<div class="caption">-5 = dissonates · 0 = neutral · 5 = strongly resonates</div>',
        unsafe_allow_html=True,
    )
    update_draft(
        question_set=current_question_set(),
        **{str(question.field): str(value)},
    )
    free_text_field = str(getattr(question, "free_text_field", "") or "").strip()
    if free_text_field:
        comment = st.text_area(
            str(getattr(question, "free_text_label", "") or "Optional comment"),
            value=str(
                get_draft(question_set=current_question_set()).get(free_text_field)
                or ""
            ),
            key=f"conference_widget_{free_text_field}",
            placeholder=str(getattr(question, "free_text_placeholder", "") or ""),
            height=120,
        )
        update_draft(
            question_set=current_question_set(),
            **{free_text_field: str(comment or "").strip()},
        )


def _render_fingerprint() -> None:
    draft = get_draft(question_set=current_question_set())
    fingerprint = draft.get("complexity_fingerprint", {})
    if not isinstance(fingerprint, dict):
        fingerprint = {}
    updated = {}
    for axis in current_question_set().fingerprint_axes:
        updated[axis] = int(
            st.slider(
                current_question_set().fingerprint_labels.get(axis, axis.title()),
                min_value=0,
                max_value=5,
                value=int(fingerprint.get(axis, 0) or 0),
                key=f"conference_widget_fp_{axis}",
            )
        )
    update_draft(question_set=current_question_set(), complexity_fingerprint=updated)
    if any(updated.values()):
        clear_deferred_field(
            "complexity_fingerprint", question_set=current_question_set()
        )


def _render_question_step(
    step: str,
    session: Dict[str, Any],
    *,
    use_location_fragment: bool = True,
) -> None:
    question = question_by_step(current_question_set(), step)
    if not question:
        return
    field = str(question.field)
    draft = get_draft(question_set=current_question_set())
    current_value = draft.get(field)
    input_type = str(question.input_type)
    if question.question_id in set(draft.get("updated_question_ids") or []):
        st.info("This question has been updated since your previous response.")

    if input_type in {"single", "multi"}:
        _render_pills(question, current_value)
        return

    if input_type == "scientific_home":
        _render_scientific_home()
        return

    if input_type == "geography_context":
        if str(question.field) == "wg2_main_location":
            _render_wg2_spatial_context(
                question,
                session,
                use_location_fragment=use_location_fragment,
            )
        elif use_location_fragment:
            _render_geography_context(question, session)
        else:
            _render_geography_context_body(question, session)
        return

    if input_type == "fingerprint":
        _render_fingerprint()
        return

    if input_type == "scale":
        _render_scale(question, current_value)
        return

    if input_type == "location":
        value = render_location_lookup(
            str(question.prompt or "Location"),
            value=current_value,
            key=f"conference_widget_{field}",
            lookup=_lookup_location_options,
            optional=not bool(question.required),
        )
        update_draft(question_set=current_question_set(), **{field: value})
        return

    if input_type == "number":
        value = st.number_input(
            str(question.prompt or field or "Value"),
            value=None if current_value in (None, "") else float(current_value),
            key=f"conference_widget_{field}",
            label_visibility="collapsed",
        )
        update_draft(question_set=current_question_set(), **{field: value})
        return

    if input_type in {"text", "textarea"}:
        value = st.text_area(
            str(question.prompt or field or "Response"),
            value=str(current_value or ""),
            key=f"conference_widget_{field}",
            placeholder=str(question.placeholder or ""),
            max_chars=500,
            label_visibility="collapsed",
            height=180,
        )
        update_draft(question_set=current_question_set(), **{field: value})
        if str(value or "").strip():
            clear_deferred_field(field, question_set=current_question_set())


def _render_identity(session: Dict[str, Any]) -> None:
    draft = get_draft(question_set=current_question_set())
    event_config = event_config_for_session_code(str(session.get("session_code") or ""))
    identified = bool(event_config and event_config.identity_policy.identified)
    if identified:
        name = st.text_input(
            "Name",
            value=str(draft.get("name") or ""),
            key="conference_widget_name",
        )
        email = st.text_input(
            "Email",
            value=str(draft.get("email") or ""),
            key="conference_widget_email",
        )
        institution = st.text_input(
            "Institution (optional)",
            value=str(draft.get("institution") or ""),
            key="conference_widget_institution",
        )
        base_location = render_location_lookup(
            "Where are you based? (optional)",
            value=draft.get("base_location"),
            key="conference_widget_base_location",
            lookup=_lookup_location_options,
        )
        update_draft(
            question_set=current_question_set(),
            name=name,
            email=email,
            institution=institution,
            base_location=base_location,
            alias=name,
            identity=name,
            contact=email,
        )
        return
    alias = st.text_input(
        "Alias",
        value=str(draft.get("alias") or ""),
        key="conference_widget_alias",
        placeholder="Optional public alias",
    )
    identity = st.text_input(
        "Name and affiliation",
        value=str(draft.get("identity") or ""),
        key="conference_widget_identity",
        placeholder="Name, affiliation, or role",
    )
    contact = str(draft.get("contact") or "")
    if should_collect_contact(draft, question_set=current_question_set()):
        contact = st.text_input(
            "Contact cue",
            value=contact,
            key="conference_widget_contact",
            placeholder="Optional email, website, or contact cue",
        )
    update_draft(
        question_set=current_question_set(),
        alias=alias,
        identity=identity,
        contact=contact
        if should_collect_contact(draft, question_set=current_question_set())
        else "",
    )


def _question_edit_fields(question: QuestionDefinition) -> list[str]:
    field = str(question.field or "").strip()
    if field == "scientific_home":
        fields = [
            "scientific_home_country",
            "scientific_home_city",
            "scientific_home_institution",
        ]
    else:
        fields = [field] if field else []
    detail_field = str(getattr(question, "free_text_field", "") or "").strip()
    if detail_field:
        fields.append(detail_field)
    return fields


def _review_questions(
    payload: Dict[str, Any],
    *,
    section: str,
    active_steps: set[str],
) -> list[QuestionDefinition]:
    profile_fields = set(current_question_set().profile_fields)
    questions: list[QuestionDefinition] = []
    for question in current_question_set().questions:
        field = str(question.field)
        is_profile = field in profile_fields or field == "scientific_home"
        if section == "profile" and not is_profile:
            continue
        if section == "session" and is_profile:
            continue
        if str(question.step) not in active_steps:
            continue
        state = question_state(payload.get("question_states"), question.question_id)
        if _question_answered(question, payload) or state["answer_state"] == "skipped":
            questions.append(question)
    return questions


def _begin_answer_edit(question: QuestionDefinition, original_step: int) -> None:
    draft = get_draft(question_set=current_question_set())
    st.session_state[EDIT_CONTEXT_KEY] = {
        **edit_context(
            question_id=str(question.question_id or ""),
            step=str(question.step or ""),
            original_step=original_step,
            submitted=bool(draft.get("submitted")),
        ),
        "previous_value": deepcopy(_question_value(question, draft)),
    }
    st.session_state[EDIT_DRAFT_KEY] = deepcopy(draft)
    st.session_state["conference_edit_validation"] = ""


def _save_answer_revision(
    repo: Any,
    session: Dict[str, Any],
    question: QuestionDefinition,
    *,
    previous_value: Any,
) -> bool:
    draft = get_draft(question_set=current_question_set())
    payload = revision_payload(
        _payload_for_session(draft, session),
        question_id=str(question.question_id or ""),
        field=str(question.field or ""),
        previous_value=previous_value,
    )
    identity_metadata = build_identity_metadata(
        draft, question_set=current_question_set()
    )
    access_key = _ensure_access_key()
    access_key_hash = repo.access_key_hash(access_key)
    access_key_last4 = emoji_suffix(access_key)
    try:
        player = repo.upsert_conference_player(
            session_id=session["id"],
            access_key=access_key,
            payload=payload,
            identity_metadata=identity_metadata,
        )
        previous_response_id = str(
            st.session_state.get("conference_submission_cache", {}).get("response_id")
            or ""
        )
        revision_id = str(uuid.uuid4())
        saved = repo.save_session_response_set(
            session["id"],
            str((player or {}).get("id") or ""),
            _event_context(session)["text_id"],
            str(st.session_state.get("conference_device_id", "")),
            access_key_hash,
            access_key_last4,
            payload,
            identity_metadata,
            submission_id=str(
                st.session_state.get("conference_submission_cache", {}).get("submission_id")
                or uuid.uuid4()
            ),
            revision_id=revision_id,
            write_idempotency_key=revision_id,
            supersedes_response_id=previous_response_id,
        )
    except Exception as exc:
        _log_route_event(
            session,
            event_type="answer_revision_failed",
            step=str(question.step or ""),
            question=question,
            status="error",
            value_label=str(exc),
            level="ERROR",
            extra={"error": str(exc)},
        )
        st.error(f"Could not save this revision: {exc}")
        return False
    st.session_state["conference_submission_cache"] = build_payload_view(
        draft, question_set=current_question_set()
    ) | {
        "access_key_hash": access_key_hash,
        "access_key_last4": access_key_last4,
        "actor_key": f"player:{str((player or {}).get('id') or '')}"
        if (player or {}).get("id")
        else f"response:{access_key_hash}",
        "response_id": str(saved.get("response_id") or ""),
        "submission_id": str(saved.get("submission_id") or ""),
        "revision_id": str(saved.get("revision_id") or ""),
    }
    _log_route_event(
        session,
        event_type="answer_revision_appended",
        step=str(question.step or ""),
        question=question,
        player_id=str((player or {}).get("id") or ""),
        value_label=_labels_for(
            str(question.field), _question_value(question, draft)
        )[:240],
        extra={"append_only": True},
    )
    return True


def _open_edit_answer_dialog(
    repo: Any, session: Dict[str, Any], question: QuestionDefinition
) -> None:
    @st.dialog("Edit this answer")
    def _edit_dialog() -> None:
        context = st.session_state.get(EDIT_CONTEXT_KEY, {})
        live_draft = deepcopy(get_draft(question_set=current_question_set()))
        edit_draft = st.session_state.get(EDIT_DRAFT_KEY)
        if not isinstance(edit_draft, dict):
            edit_draft = deepcopy(live_draft)
        st.markdown(f"### {html.escape(str(question.prompt or 'Answer'))}")
        st.session_state["conference_draft"] = deepcopy(edit_draft)
        try:
            _render_question_step(
                str(question.step or ""),
                session,
                use_location_fragment=False,
            )
            edited_now = deepcopy(get_draft(question_set=current_question_set()))
        finally:
            st.session_state["conference_draft"] = live_draft
        st.session_state[EDIT_DRAFT_KEY] = edited_now

        validation = str(st.session_state.get("conference_edit_validation") or "")
        if validation:
            st.warning(validation)
        save_col, cancel_col = st.columns(2)
        with save_col:
            if st.button(
                "Save revision",
                type="primary",
                use_container_width=True,
                key=f"conference_edit_save_{question.question_id}",
            ):
                edited_payload = build_payload_view(
                    edited_now, question_set=current_question_set()
                )
                if not _question_answered(question, edited_payload):
                    st.session_state["conference_edit_validation"] = (
                        "Add an answer before saving this revision."
                    )
                    st.rerun()
                merged = merge_answer_fields(
                    live_draft,
                    edited_now,
                    _question_edit_fields(question),
                )
                st.session_state["conference_draft"] = merged
                if bool(context.get("submitted")):
                    saved = _save_answer_revision(
                        repo,
                        session,
                        question,
                        previous_value=context.get("previous_value"),
                    )
                    if not saved:
                        return
                else:
                    _log_route_event(
                        session,
                        event_type="answer_draft_updated",
                        step=str(question.step or ""),
                        question=question,
                        value_label=_labels_for(
                            str(question.field), _question_value(question, merged)
                        )[:240],
                    )
                set_step("review", question_set=current_question_set())
                st.session_state.pop(EDIT_CONTEXT_KEY, None)
                st.session_state.pop(EDIT_DRAFT_KEY, None)
                st.session_state["conference_edit_validation"] = ""
                st.rerun()
        with cancel_col:
            if st.button(
                "Cancel",
                use_container_width=True,
                key=f"conference_edit_cancel_{question.question_id}",
            ):
                st.session_state.pop(EDIT_CONTEXT_KEY, None)
                st.session_state.pop(EDIT_DRAFT_KEY, None)
                st.session_state["conference_edit_validation"] = ""
                set_step("review", question_set=current_question_set())
                st.rerun()

    _edit_dialog()


def _render_review_answer_card(
    question: QuestionDefinition,
    payload: Dict[str, Any],
    *,
    original_step: int,
) -> None:
    card_key = f"conference_review_card_{str(question.question_id).lower()}"
    with st.container(border=True, key=card_key):
        answer_col, edit_col = st.columns(
            [8, 2],
            gap="small",
            vertical_alignment="center",
        )
        with answer_col:
            st.markdown(
                f'<div class="review-answer-title">{html.escape(str(question.prompt or _question_title(question)))}</div>',
                unsafe_allow_html=True,
            )
            state = question_state(payload.get("question_states"), question.question_id)
            answer = "Skipped" if state["answer_state"] == "skipped" else _question_summary_body(question, payload)
            flag_label = " · Flagged" if state["flagged"] else ""
            st.markdown(
                f'<div class="review-answer-body">{answer}{html.escape(flag_label)}</div>',
                unsafe_allow_html=True,
            )
        with edit_col:
            if st.button(
                "Edit",
                type="tertiary",
                icon=":material/edit:",
                width="content",
                key=f"conference_review_edit_{question.question_id}",
            ):
                _begin_answer_edit(question, original_step)
                st.rerun()


def _render_review(repo: Any, session: Dict[str, Any]) -> None:
    _render_boiler_room_expander()
    payload = build_payload_view(
        get_draft(question_set=current_question_set()),
        question_set=current_question_set(),
    )
    active_steps = set(
        active_question_steps(
            get_draft(question_set=current_question_set()),
            question_set=current_question_set(),
        )
    )
    config = event_config_for_session_code(str(session.get("session_code") or ""))
    if config and config.identity_policy.identified:
        st.markdown("### About you")
        summary_card("Name", html.escape(str(payload.get("name") or "")))
        if payload.get("institution"):
            summary_card("Institution", html.escape(str(payload.get("institution") or "")))
        location = payload.get("base_location")
        location_label = (
            str(location.get("display_label") or "")
            if isinstance(location, dict)
            else str(location or "")
        )
        if location_label:
            summary_card("Base location", html.escape(location_label))
        st.markdown("### Your answers")
        if not current_question_set().questions:
            st.caption("Scientific questions will appear here when they are available.")
    active_sequence = active_question_steps(
        get_draft(question_set=current_question_set()),
        question_set=current_question_set(),
    )
    for question in _review_questions(
        payload, section="profile", active_steps=active_steps
    ):
        _render_review_answer_card(
            question,
            payload,
            original_step=active_sequence.index(str(question.step))
            if str(question.step) in active_sequence
            else 0,
        )

    for question in _review_questions(
        payload, section="session", active_steps=active_steps
    ):
        _render_review_answer_card(
            question,
            payload,
            original_step=active_sequence.index(str(question.step))
            if str(question.step) in active_sequence
            else 0,
        )
    if payload.get("boiler_room_contribution"):
        summary_card(
            "Boiler room contribution",
            html.escape(str(payload["boiler_room_contribution"])),
        )
    _render_question_flag_summary()

    pending = pending_reflection_fields(
        get_draft(question_set=current_question_set()),
        question_set=current_question_set(),
    )
    if pending:
        summary_card(
            "Pending reflections",
            " · ".join(_field_label(field) for field in pending),
        )

    if not (config and config.identity_policy.identified):
        identity_parts = [
            str(payload.get("alias") or "").strip(),
            str(payload.get("identity") or "").strip(),
            str(payload.get("contact") or "").strip(),
        ]
        identity_text = (
            " · ".join(part for part in identity_parts if part) or "Remain anonymous"
        )
        summary_card("Alias or identity", identity_text)
    context = st.session_state.get(EDIT_CONTEXT_KEY)
    if isinstance(context, dict) and str(context.get("question_id") or ""):
        question = next(
            (
                item
                for item in current_question_set().questions
                if str(item.question_id) == str(context.get("question_id"))
            ),
            None,
        )
        if question:
            _open_edit_answer_dialog(repo, session, question)


def _question_teasers(submissions: List[Dict[str, Any]], self_actor: str) -> List[str]:
    entries: List[str] = []
    seen: set[str] = set()
    text_questions = [
        question
        for question in current_question_set().questions
        if str(question.field) in set(current_question_set().session_fields)
        and str(question.input_type) == "text"
    ]
    for item in submissions:
        if str(item.get("actor_key") or "") == self_actor:
            continue
        for question in text_questions:
            text = str(item.get(question.field) or "").strip()
            token = f"{question.field}:{text}"
            if not text or token in seen:
                continue
            entries.append(f"{_question_title(question)}|||{text}")
            seen.add(token)
            if len(entries) >= 4:
                return entries
    return entries


def _historical_session_counts(
    repo: Any, current_session_id: str
) -> List[Dict[str, Any]]:
    sessions = [
        {
            "code": YOUNG_SESSION_CODE,
            "label": "Young",
            "question": "Who are you?",
        },
        {
            "code": UNESCO_SESSION_CODE,
            "label": "UNESCO",
            "question": "What resonates?",
        },
    ]
    rows: List[Dict[str, Any]] = []
    for item in sessions:
        session = repo.resolve_session(session_code=item["code"])
        if not session:
            continue
        if str(session.get("id") or "") == str(current_session_id or ""):
            continue
        submissions = repo.group_rows_by_submission(
            repo.get_session_rows(
                session["id"],
                text_ids=text_ids_for_session_code(item["code"]),
            )
        )
        rows.append(
            {
                "label": item["label"],
                "question": item["question"],
                "participants": len(submissions),
            }
        )
    return rows


def _render_room_aggregates(submissions: List[Dict[str, Any]]) -> None:
    snapshot = room_snapshot(submissions)
    cols = st.columns(4)
    cols[0].metric("Participants", int(snapshot["participants"]))
    cols[1].metric("Countries", int(snapshot["countries"]))
    cols[2].metric("Follow-up yes", int(snapshot["follow_up"].get("yes", 0)))
    cols[3].metric("Follow-up maybe", int(snapshot["follow_up"].get("maybe", 0)))

    aggregate_questions = [
        question
        for question in current_question_set().questions
        if str(question.field) in set(current_question_set().session_fields)
        and str(question.input_type) in {"single", "multi"}
        and str(question.field) != "follow_up_interest"
    ][:3]
    for question in aggregate_questions:
        field = str(question.field)
        counter = count_field(submissions, field)
        title = _question_title(question)
        st.markdown(f"### {title}")
        if not counter:
            st.markdown(
                '<div class="caption">No signals yet.</div>',
                unsafe_allow_html=True,
            )
            continue
        lines = [
            f"{value} · {html.escape(_labels_for(field, key))}"
            for key, value in counter.most_common(4)
        ]
        summary_card(title, "<br>".join(lines))


def _render_other_sessions(repo: Any, current_session_id: str) -> None:
    historical = _historical_session_counts(repo, current_session_id)
    if not historical:
        return
    st.markdown("### Other sessions")
    for item in historical:
        summary_card(
            item["label"],
            f"{int(item['participants'])} participants · question: {item['question']}",
        )


def _render_personal_dashboard(repo: Any, session: Dict[str, Any]) -> None:
    event_context = _event_context(session)
    payload = build_payload_view(
        get_draft(question_set=current_question_set()),
        question_set=current_question_set(),
    )
    active_steps = set(
        active_question_steps(
            get_draft(question_set=current_question_set()),
            question_set=current_question_set(),
        )
    )
    submissions = repo.group_rows_by_submission(
        repo.get_session_rows(
            session["id"],
            text_ids=text_ids_for_session_code(str(session.get("session_code") or "")),
        )
    )
    conference_header(str(event_context["event_label"]), "", step="")
    config = event_config_for_session_code(str(session.get("session_code") or ""))
    if config and config.identity_policy.identified:
        st.markdown("### Your saved answers")
    else:
        st.markdown("### Your profile is loaded.")
        summary_card("Mode", _labels_for("mode", str(payload.get("mode") or "quick")))
    for title, body in _question_summary_entries(
        payload, section="profile", active_steps=active_steps
    ):
        summary_card(title, body)
    for title, body in _question_summary_entries(
        payload, section="session", active_steps=active_steps
    ):
        summary_card(title, body)
    if payload.get("boiler_room_contribution"):
        summary_card(
            "Boiler room contribution",
            html.escape(str(payload.get("boiler_room_contribution"))),
        )
    _render_question_flag_summary()

    gaps = profile_completion_gaps(
        get_draft(question_set=current_question_set()),
        question_set=current_question_set(),
    )
    if gaps and not bool(st.session_state.get("conference_hide_migration_prompt")):
        st.markdown(
            '<div class="section-title">We have added new questions</div>',
            unsafe_allow_html=True,
        )
        st.markdown(
            f'<div class="helper-text">We have added {len(gaps)} question(s) to better understand your perspective.</div>',
            unsafe_allow_html=True,
        )
        left, right = st.columns(2)
        with left:
            if st.button(
                "Yes, enthusiastically", type="primary", use_container_width=True
            ):
                _resume_at_field(
                    gaps[0],
                    suggested_mode_for_missing_profile_fields(
                        gaps, question_set=current_question_set()
                    ),
                )
        with right:
            if st.button("Later", use_container_width=True):
                st.session_state["conference_hide_migration_prompt"] = True
                st.rerun()

    pending = pending_reflection_fields(
        get_draft(question_set=current_question_set()),
        question_set=current_question_set(),
    )
    if pending:
        st.markdown(
            '<div class="section-title">Pending reflections</div>',
            unsafe_allow_html=True,
        )
        for field in pending:
            summary_card(_field_label(field), "Deferred. You can answer later.")
        if st.button(
            "Answer pending reflections", type="primary", use_container_width=True
        ):
            _resume_at_field(pending[0], str(payload.get("mode") or "standard"))

    teasers = _question_teasers(
        submissions,
        str(
            st.session_state.get("conference_submission_cache", {}).get("actor_key", "")
        ),
    )
    _render_room_aggregates(submissions)
    _render_other_sessions(repo, str(session.get("id") or ""))
    if teasers:
        st.markdown(
            '<div class="section-title">Questions in the room</div>',
            unsafe_allow_html=True,
        )
        for item in teasers:
            title, _, text = item.partition("|||")
            summary_card(title or "Question", html.escape(text))

    if st.button(
        "Review and edit individual answers",
        type="primary",
        use_container_width=True,
        key="conference-dashboard-review-edit",
    ):
        set_step("review", question_set=current_question_set())
        _set_entry_mode("new")
        st.rerun()

    mode = str(payload.get("mode") or "quick")
    if mode == "quick":
        if st.button("Continue in Standard", use_container_width=True):
            _resume_in_mode("standard")
        if st.button("Continue in Deep dive", use_container_width=True):
            _resume_in_mode("deep")
    elif mode == "standard":
        if st.button("Continue in Deep dive", type="primary", use_container_width=True):
            _resume_in_mode("deep")
        if st.button("Edit my Standard responses", use_container_width=True):
            _resume_in_mode("standard")
    else:
        if st.button(
            "Edit my Deep responses", type="primary", use_container_width=True
        ):
            _resume_in_mode("deep")

    if st.button(
        f"Open the {event_context['event_label']} overview",
        use_container_width=True,
        key="conference-dashboard-open-overview",
    ):
        _switch_to_event_overview(session)
    if st.button("Use another access key", use_container_width=True):
        _set_entry_mode("existing")
        _clear_login_error()
        st.rerun()


def _render_done(session: Dict[str, Any]) -> None:
    draft = get_draft(question_set=current_question_set())
    if st.session_state.pop("conference_show_success", False):
        st.balloons()
    context = _event_context(session)
    st.markdown(
        '<div class="helper-text">Your responses were recorded. Save this access key so you can return later.</div>',
        unsafe_allow_html=True,
    )
    access_key = str(draft.get("access_key") or "")
    emoji_key = hex_to_emoji(access_key) if access_key else ""
    access_key_hash = (
        hashlib.sha256(access_key.encode("utf-8")).hexdigest() if access_key else ""
    )
    summary_card("Your access key", emoji_key or "Unavailable")
    if context.get("test_mode"):
        with st.expander("Test diagnostics", expanded=False):
            st.write(f"Session code: {context.get('session_code') or 'Unavailable'}")
            st.write(f"Hash prefix: {access_key_hash[:12] if access_key_hash else 'Unavailable'}")
            st.code(access_key or "Unavailable")
    if st.button(
        f"Open the {_event_context(session)['event_label']} overview",
        use_container_width=True,
        key="conference-done-open-overview",
    ):
        _switch_to_event_overview(session)
    if st.button(
        current_question_set().step_copy["done"]["cta"], use_container_width=True
    ):
        reset_flow_state(question_set=current_question_set())
        _set_entry_mode("")
        st.rerun()


def _log_step_page_view(session: Dict[str, Any], step: str) -> None:
    question = question_by_step(current_question_set(), step)
    token = f"{str(session.get('id') or '')}:{step}:{str(question.question_id or '') if question else ''}"
    if st.session_state.get("conference_last_step_view") == token:
        return
    st.session_state["conference_last_step_view"] = token
    _log_route_event(
        session,
        event_type="page_view",
        step=step,
        question=question,
    )


def _render_navigation(repo: Any, session: Dict[str, Any]) -> None:
    step = current_step()
    question = question_by_step(current_question_set(), step)
    if step in {"welcome", "done"}:
        _, flag_col, skip_col = st.columns([1.6, 0.45, 0.35])
        with flag_col:
            _render_step_flag_action(step, None, session, repo)
        with skip_col:
            _render_step_skip_action(step, None, session, repo)
        return
    if step == "review":
        submitted = bool(
            get_draft(question_set=current_question_set()).get("submitted")
        )
        if submitted:
            if st.button(
                "Return to my dashboard",
                type="primary",
                use_container_width=True,
                key="conference-review-return-dashboard",
            ):
                _set_entry_mode("dashboard")
                st.rerun()
            return
        review_help = None
        if _event_is_read_only(session):
            review_help = (
                f"This event is "
                f"{str(_event_context(session).get('event_status') or 'closed')}."
            )
        primary, flag_col, skip_col = st.columns([1.6, 0.45, 0.35])
        with primary:
            if st.button(
                current_question_set().step_copy["review"]["cta"],
                type="primary",
                use_container_width=True,
                disabled=_event_is_read_only(session),
                help=review_help,
                key="conference-review-submit",
            ):
                _open_confirm_send_dialog(repo, session)
        with flag_col:
            _render_step_flag_action(step, None, session, repo)
        with skip_col:
            _render_step_skip_action(step, None, session, repo)
        return

    if question:
        validation = _question_validation(step)
        st.markdown(
            (
                f'<div class="question-validation" role="alert">{html.escape(validation)}</div>'
                if validation
                else '<div class="question-validation question-validation-empty" aria-hidden="true"></div>'
            ),
            unsafe_allow_html=True,
        )
        primary, flag_col, skip_col = st.columns([1.6, 0.45, 0.35])
        with primary:
            if st.button("Continue", type="primary", use_container_width=True):
                draft = get_draft(question_set=current_question_set())
                payload = build_payload_view(draft, question_set=current_question_set())
                answered = _question_answered(question, payload)
                if not answered:
                    _set_question_validation(
                        step, "Answer this step or skip it with a reason."
                    )
                    _log_route_event(
                        session,
                        event_type="question_continue_blocked",
                        step=step,
                        question=question,
                        status="blocked",
                    )
                    st.rerun()
                    return
                _set_question_validation(step, "")
                if answered:
                    _clear_question_skip(question.question_id)
                    update_draft(
                        question_set=current_question_set(),
                        question_states=answer_question(
                            draft.get("question_states"), question.question_id
                        ),
                    )
                    _log_route_event(
                        session,
                        event_type="question_answered",
                        step=step,
                        question=question,
                        value_label=_labels_for(
                            str(question.field),
                            _question_value(question, payload),
                        )[:240],
                    )
                if not _persist_participation_checkpoint(
                    repo, session, next_position=_next_position()
                ):
                    return
                _advance_step()
                st.rerun()
        with flag_col:
            _render_step_flag_action(step, question, session, repo)
        with skip_col:
            _render_step_skip_action(step, question, session, repo)
        return

    action, flag_col, skip_col = st.columns([1.6, 0.45, 0.35])
    with action:
        if st.button("Continue", type="primary", use_container_width=True):
            draft = get_draft(question_set=current_question_set())
            if step == IDENTITY_STEP:
                config = event_config_for_session_code(
                    str(session.get("session_code") or "")
                )
                if config and config.identity_policy.identified:
                    if not str(draft.get("name") or "").strip():
                        st.warning("Enter your name before continuing.")
                        return
                    try:
                        normalize_email(str(draft.get("email") or ""))
                    except ValueError as exc:
                        st.warning(str(exc))
                        return
            if not step_is_complete(step, draft, question_set=current_question_set()):
                st.warning("Complete this step before continuing.")
                return
            if not _persist_participation_checkpoint(
                repo, session, next_position=_next_position()
            ):
                return
            _advance_step()
            st.rerun()
    with flag_col:
        _render_step_flag_action(step, None, session, repo)
    with skip_col:
        _render_step_skip_action(step, None, session, repo)


def _render_questionnaire(repo: Any, session: Dict[str, Any]) -> None:
    if _event_is_read_only(session) and not bool(
        get_draft(question_set=current_question_set()).get("submitted")
    ):
        conference_header(
            str(_event_context(session)["event_label"]), "", step="read-only"
        )
        st.warning(
            f"{_event_context(session)['event_label']} is currently "
            f"{_event_context(session)['event_status']}. New submissions are closed."
        )
        if st.button(
            f"Open the {_event_context(session)['event_label']} overview",
            use_container_width=True,
            key="conference-read-only-open-overview",
        ):
            _switch_to_event_overview(session)
        return
    if current_step() not in active_step_sequence(question_set=current_question_set()):
        set_step(initial_step(question_set=current_question_set()), question_set=current_question_set())
    step = current_step()
    copy = current_question_set().step_copy[step]
    question = question_by_step(current_question_set(), step)
    sequence = active_step_sequence(question_set=current_question_set())
    question_sequence = [
        token
        for token in sequence
        if question_by_step(current_question_set(), str(token)) is not None
    ]
    if question and step in question_sequence:
        step_label = f"{question_sequence.index(step) + 1}/{len(question_sequence)}"
    else:
        step_index = sequence.index(step) + 1 if step in sequence else 1
        step_label = f"{step_index}/{len(sequence)}" if step != "done" else "complete"
    _log_step_page_view(session, step)
    if question:
        _render_question_page_header(
            step_label=step_label,
            section_title=str(copy.get("title") or ""),
            question=question,
            copy=copy,
        )
    else:
        conference_header(copy["title"], "", step=step_label)
        _render_question_intro(step, question, copy)

    if step == "welcome":
        _render_welcome()
    elif step == IDENTITY_STEP:
        _render_identity(session)
    elif step == "review":
        _render_review(repo, session)
    elif step == "done":
        _render_done(session)
    else:
        _render_question_step(step, session)

    _render_navigation(repo, session)


def run_conference_questionnaire_page(
    *,
    session_code_resolver: Callable[[Any], str],
    public_route_path: str = "",
) -> None:
    set_page()
    apply_conference_styles()
    st.session_state["conference_public_route_path"] = str(public_route_path or "")

    repo = get_conference_repo()
    if not repo or not repo.is_ready():
        st.error(
            repo.unavailable_reason if repo else "Conference repository is unavailable."
        )
        return

    session_code = str(session_code_resolver(repo) or "").strip()
    bundle = get_conference_bundle(session_code=session_code)
    session = bundle.get("session")
    if not session:
        st.error(
            "Conference session is missing. "
            f"Ensure `{session_code}` exists in the shared sessions DB, or run "
            "`scripts/bootstrap_dalembertiennes_session.py` for the Dalembertiennes scaffold."
        )
        return

    bundle_spec = resolve_question_set_bundle(session=session)
    use_controls_fixture = bool(
        _event_context(session).get("test_mode")
        and str(st.query_params.get("fixture") or "").strip().lower() == "controls"
    )
    base_question_set = (
        PLATFORM_CONTROLS_FIXTURE if use_controls_fixture else bundle_spec.question_set
    )
    if (
        base_question_set.status != "active"
        and not bool(_event_context(session).get("test_mode"))
    ):
        conference_header(
            str(_event_context(session).get("event_label") or "Questionnaire"),
            "",
            step=base_question_set.status,
        )
        st.info("This questionnaire is being reviewed and is not open yet.")
        return
    question_set = _question_set_for_public_route(base_question_set, public_route_path)
    _ensure_session_scope_state(session, question_set)
    _ensure_local_state(question_set)
    _render_test_mode_notice(session)
    route = public_route_config(public_route_path)
    sidebar_debug_state(
        debug_context={
            "current_page": "conference_questionnaire",
            "event_log_page": "conference",
            "event_slug": bundle_spec.event_slug,
            "session_code": bundle_spec.session_code,
            "session_id": str(session.get("id") or ""),
            "event_label": str(_event_context(session).get("event_label") or ""),
            "text_id": bundle_spec.text_id,
            "question_set_id": bundle_spec.question_set_id,
            "schema_id": bundle_spec.schema_id,
            "question_set_module": bundle_spec.question_set_module,
            "question_set_source_kind": bundle_spec.question_set_source_kind,
            "question_set_source_path": bundle_spec.question_set_source_path,
            "question_set_source_note": bundle_spec.question_set_source_note,
            "question_count": len(bundle_spec.question_ids),
            "shared_question_count": len(bundle_spec.shared_question_ids),
            "event_specific_question_count": len(
                bundle_spec.event_specific_question_ids
            ),
            "question_ids": list(bundle_spec.question_ids),
            "shared_question_ids": list(bundle_spec.shared_question_ids),
            "event_specific_question_ids": list(
                bundle_spec.event_specific_question_ids
            ),
            "public_route": str(route.path) if route else "",
            "campaign_slug": str(route.campaign_slug) if route else "",
        }
    )
    _hydrate_existing_submission(repo, session)

    mode = _entry_mode()
    if mode == "dashboard":
        _render_personal_dashboard(repo, session)
        return
    if mode == "new" or get_draft(question_set=current_question_set()).get("submitted"):
        _render_questionnaire(repo, session)
        return
    _render_entry(session, repo)
