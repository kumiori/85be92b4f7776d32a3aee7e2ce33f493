from __future__ import annotations

import hashlib
import uuid
from collections.abc import Mapping
from typing import Any, Dict, List

import streamlit as st
import streamlit.components.v1 as components

from conference.context import get_conference_bundle, get_conference_repo
from conference.events import (
    COMPLEXITY_EVENT_CODE,
    COMPLEXITY_EVENT_LABEL,
    COMPLEXITY_EVENT_LOCATION,
    COMPLEXITY_TEXT_ID,
    COMPLEXITY_OVERVIEW_PAGE,
    UNESCO_SESSION_CODE,
    YOUNG_SESSION_CODE,
    complexity_text_ids,
    current_complexity_session_code,
    text_ids_for_session_code,
)
from conference.flow import (
    active_question_steps,
    active_step_sequence,
    build_identity_metadata,
    build_session_payload,
    build_payload_view,
    clear_deferred_field,
    current_step,
    defer_field,
    first_active_question_step,
    get_draft,
    init_flow_state,
    mark_submitted,
    mode_label,
    next_step,
    pending_reflection_fields,
    profile_completion_gaps,
    reset_flow_state,
    set_step,
    should_collect_contact,
    step_is_complete,
    suggested_mode_for_missing_profile_fields,
    update_draft,
)
from conference.models import (
    DEFERRABLE_FIELDS,
    FINGERPRINT_AXES,
    FINGERPRINT_LABELS,
    STEP_COPY,
    STEP_ORDER,
    field_for_step,
    field_option_label_map,
    mode_card_rows,
    question_by_step,
    role_set,
)
from conference.question_flags import (
    QUESTION_FLAG_LABELS,
    QUESTION_FLAG_OPTIONS,
    normalize_question_flags,
)
from conference.repo import emoji_suffix, resolve_access_key_input
from conference.topology import room_snapshot
from conference.ui import apply_conference_styles, conference_header, summary_card
from infra.key_codec import generate_hex_key, hex_to_emoji, split_emoji_symbols
from ui import set_page, sidebar_debug_state


PAGE_KEY = "complexity"
TEXT_ID = COMPLEXITY_TEXT_ID
IDENTITY_STEP = "identity"
ENTRY_KEY = "conference_entry_mode"
LOGIN_ERROR_KEY = "conference_login_error"
def _ensure_local_state() -> None:
    init_flow_state()
    st.session_state.setdefault("conference_device_id", uuid.uuid4().hex[:16])
    st.session_state.setdefault(ENTRY_KEY, "")
    st.session_state.setdefault(LOGIN_ERROR_KEY, "")
    st.session_state.setdefault("conference_hide_migration_prompt", False)


def _set_entry_mode(mode: str) -> None:
    st.session_state[ENTRY_KEY] = mode


def _entry_mode() -> str:
    return str(st.session_state.get(ENTRY_KEY, "") or "").strip()


def _clear_login_error() -> None:
    st.session_state[LOGIN_ERROR_KEY] = ""


def _set_login_error(message: str) -> None:
    st.session_state[LOGIN_ERROR_KEY] = message


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
        (row for row in mode_card_rows() if str(row.get("value") or "") == "quick"),
        {
            "value": "quick",
            "title": "Quick pulse",
            "detail": "~ 3 minutes",
            "accent": "🧊",
        },
    )


def _question_prompt_by_id(question_id: str) -> str:
    for step in active_question_steps(get_draft()):
        question = question_by_step(step)
        if question and str(question.get("question_id") or "") == question_id:
            return str(question.get("prompt") or question_id)
    return question_id


def _question_flag_entries() -> Dict[str, Dict[str, Any]]:
    return normalize_question_flags(get_draft().get("question_flags"))


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
    update_draft(question_flags=entries)


def _render_question_flag_control(question: Dict[str, Any]) -> None:
    question_id = str(question.get("question_id") or "").strip()
    if not question_id:
        return
    state = _question_flag_entries().get(question_id, {})
    flags = list(state.get("flags") or [])
    note = str(state.get("note") or "")
    count = len(flags) + (1 if note else 0)
    label = f"Flag ({count})" if count else "Flag"
    with st.popover(label):
        st.caption(
            "Mark if the question feels incomplete, misleading, narrow, or otherwise off."
        )
        selected = st.pills(
            "Question issue",
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
        _set_question_flag(question_id, flags=list(selected), note=comment)


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
    if submission.get("career_stage"):
        return "deep"
    if (
        submission.get("collaboration_style")
        or submission.get("scientific_home_country")
        or submission.get("complexity_fingerprint")
        or submission.get("open_question")
    ):
        return "standard"
    return "quick"


def _labels_for(field: str, value: Any) -> str:
    if field == "mode":
        return mode_label(str(value or "quick"))
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
            f"{FINGERPRINT_LABELS.get(axis, axis.title())} {int(value.get(axis, 0) or 0)}"
            for axis in FINGERPRINT_AXES
        ]
        if all(token.endswith(" 0") for token in tokens):
            return "Deferred"
        return " · ".join(tokens)
    label_map = field_option_label_map(field)
    if isinstance(value, list):
        labels = [label_map.get(str(item), str(item)) for item in value if str(item)]
        return ", ".join(labels) if labels else "None selected"
    if isinstance(value, str):
        return label_map.get(value, value) if value else "No answer"
    return str(value or "No answer")


def _field_label(field: str) -> str:
    labels = {
        "scientific_home_country": "Scientific home",
        "assets": "Assets",
        "collaboration_style": "Collaboration style",
        "complexity_fingerprint": "What gives you confidence?",
        "open_question": "What question keeps you awake?",
    }
    return labels.get(field, field.replace("_", " ").title())


def _step_for_field(field: str) -> str:
    for step in STEP_ORDER:
        if field_for_step(step) == field:
            return step
    if field in {
        "scientific_home_country",
        "scientific_home_city",
        "scientific_home_institution",
    }:
        return "scientific_home"
    return ""


def _resume_at_field(field: str, mode: str | None = None) -> None:
    next_mode = mode or str(get_draft().get("mode") or "standard")
    target_step = _step_for_field(field) or first_active_question_step()
    update_draft(mode=next_mode, submitted=False)
    set_step(target_step)
    _set_entry_mode("new")
    st.rerun()


def _load_submission_for_key(
    repo: Any,
    session_id: str,
    raw_key: str,
) -> tuple[str | None, Dict[str, Any] | None, str]:
    token = str(raw_key or "").strip()
    if not token:
        return None, None, ""
    access_key, error = resolve_access_key_input(
        getattr(repo, "notion_repo", None), token
    )
    if not access_key:
        return None, None, str(error or "")
    access_key_hash = repo.access_key_hash(access_key)
    cache_key = f"{session_id}:{access_key_hash}"
    submission = st.session_state.get("conference_submission_cache")
    if st.session_state.get("conference_submission_cache_key") != cache_key:
        submission = repo.latest_submission_by_access_key_hash(
            session_id=session_id,
            access_key_hash=access_key_hash,
            text_ids=complexity_text_ids(),
        )
        st.session_state["conference_submission_cache_key"] = cache_key
        st.session_state["conference_submission_cache"] = submission
    return access_key, submission, ""


def _hydrate_existing_submission(repo: Any, session_id: str) -> None:
    if st.session_state.get("conference_hydrated"):
        return
    draft = get_draft()
    raw_key = str(
        draft.get("access_key") or st.query_params.get("key", "") or ""
    ).strip()
    if not raw_key:
        st.session_state["conference_hydrated"] = True
        return
    access_key, submission, _ = _load_submission_for_key(repo, session_id, raw_key)
    if access_key and submission:
        submission = _normalize_hydrated_submission(submission)
        hydrated = {
            key: value for key, value in submission.items() if key in get_draft()
        }
        hydrated["mode"] = str(submission.get("mode") or _infer_mode(submission))
        hydrated["access_key"] = access_key
        hydrated["submitted"] = True
        update_draft(**hydrated)
        repo.upsert_conference_player(
            session_id=session_id,
            access_key=access_key,
            payload=build_session_payload(get_draft()),
            identity_metadata=build_identity_metadata(get_draft()),
        )
        _set_entry_mode("dashboard")
    elif access_key:
        update_draft(access_key=access_key)
    st.session_state["conference_hydrated"] = True


def _advance_step() -> None:
    next_step()


def _normalize_hydrated_submission(submission: Dict[str, Any]) -> Dict[str, Any]:
    normalized = dict(submission)
    allowed_roles = role_set()
    roles = normalized.get("role")
    role_values = (
        [str(item).strip() for item in roles if str(item).strip()]
        if isinstance(roles, list)
        else []
    )
    role_custom = str(normalized.get("role_custom") or "").strip()
    if not role_custom:
        extras = [item for item in role_values if item not in allowed_roles]
        role_custom = extras[0] if extras else ""
    normalized["role"] = [item for item in role_values if item in allowed_roles]
    normalized["role_custom"] = role_custom
    return normalized


def _ensure_access_key() -> str:
    access_key = str(get_draft().get("access_key") or "").strip()
    if access_key:
        return access_key
    access_key = generate_hex_key()
    update_draft(access_key=access_key)
    return access_key


def _payload_for_session(draft: Dict[str, Any], session: Dict[str, Any]) -> Dict[str, Any]:
    payload = build_session_payload(draft)
    profile = payload.get("profile") if isinstance(payload.get("profile"), dict) else {}
    session_payload = payload.get("session") if isinstance(payload.get("session"), dict) else {}
    profile["persistence_scope"] = "persistent_profile"
    session_payload["event_label"] = COMPLEXITY_EVENT_LABEL
    session_payload["event_code"] = COMPLEXITY_EVENT_CODE
    session_payload["event_location"] = COMPLEXITY_EVENT_LOCATION
    session_payload["session_code"] = str(session.get("session_code") or "")
    session_payload["session_id"] = str(session.get("id") or "")
    session_payload["text_id"] = TEXT_ID
    session_payload["schema_id"] = "complexity_v2"
    session_payload["response_scope"] = "event_specific"
    payload["profile"] = profile
    payload["session"] = session_payload
    return payload


def _render_event_scope_notice(session: Dict[str, Any]) -> None:
    st.caption(
        f"This response belongs to {COMPLEXITY_EVENT_LABEL} in {COMPLEXITY_EVENT_LOCATION}. "
        "Profile questions persist across events; session answers belong only to this event."
    )


def _submit(repo: Any, session: Dict[str, Any]) -> None:
    draft = get_draft()
    payload = _payload_for_session(draft, session)
    identity_metadata = build_identity_metadata(draft)
    access_key = _ensure_access_key()
    access_key_hash = repo.access_key_hash(access_key)
    access_key_last4 = emoji_suffix(access_key)
    player = repo.upsert_conference_player(
        session_id=session["id"],
        access_key=access_key,
        payload=payload,
        identity_metadata=identity_metadata,
    )
    repo.save_session_response_set(
        session["id"],
        str((player or {}).get("id") or ""),
        TEXT_ID,
        str(st.session_state.get("conference_device_id", "")),
        access_key_hash,
        access_key_last4,
        payload,
        identity_metadata,
    )
    st.session_state["conference_submission_cache_key"] = (
        f"{session['id']}:{access_key_hash}"
    )
    st.session_state["conference_submission_cache"] = build_payload_view(draft) | {
        "access_key_hash": access_key_hash,
        "access_key_last4": access_key_last4,
        "actor_key": f"player:{str((player or {}).get('id') or '')}"
        if (player or {}).get("id")
        else f"response:{access_key_hash}",
    }
    st.session_state["conference_show_success"] = True
    update_draft(access_key=access_key, submitted=True)
    mark_submitted()


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
            <div style="text-align:center; font-size:4.6rem; line-height:1.15; letter-spacing:.16em; margin: 1rem 0 1.15rem 0;">
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
        st.markdown(
            "### Complexity is making this anonymous first. Simply, this access key lets you return later to your profile and your pending reflections."
        )
        if st.button("Screenshot taken", type="primary", use_container_width=True):
            _submit(repo, session)
            st.rerun()

    _confirm_send_dialog()


def _start_new_participant() -> None:
    reset_flow_state()
    _clear_login_error()
    st.session_state["conference_hide_migration_prompt"] = False
    _set_entry_mode("new")
    st.rerun()


def _open_existing_login() -> None:
    _clear_login_error()
    _set_entry_mode("existing")


def _login_with_key(repo: Any, session_id: str, raw_key: str) -> None:
    access_key, submission, error = _load_submission_for_key(repo, session_id, raw_key)
    if not access_key:
        _set_login_error(error or "This access key could not be decoded.")
        return
    update_draft(access_key=access_key)
    if not submission:
        _set_login_error("No submission was found for this access key yet.")
        return
    submission = _normalize_hydrated_submission(submission)
    hydrated = {key: value for key, value in submission.items() if key in get_draft()}
    hydrated["mode"] = str(submission.get("mode") or _infer_mode(submission))
    hydrated["access_key"] = access_key
    hydrated["submitted"] = True
    update_draft(**hydrated)
    repo.upsert_conference_player(
        session_id=session_id,
        access_key=access_key,
        payload=build_session_payload(get_draft()),
        identity_metadata=build_identity_metadata(get_draft()),
    )
    _clear_login_error()
    _set_entry_mode("dashboard")
    st.rerun()


def _resume_in_mode(mode: str) -> None:
    update_draft(mode=mode, submitted=False)
    set_step(first_active_question_step())
    _set_entry_mode("new")
    st.rerun()


def _render_entry(session: Dict[str, Any], repo: Any) -> None:
    conference_header("Pattenrs and Complexity", "", step="")
    st.markdown("### Anonymous first.")
    _render_event_scope_notice(session)
    st.markdown("### Choose how to enter.")
    if st.button("🆕 New participant", type="primary", use_container_width=True):
        _start_new_participant()
    if st.button("🔑 I already have an access key", use_container_width=True):
        _open_existing_login()
        st.rerun()
    if _entry_mode() == "existing":
        st.markdown("### Enter your emoji access key.")
        raw_key = st.text_area(
            "Access key",
            value=str(get_draft().get("access_key") or ""),
            key="conference_existing_key",
            placeholder="Paste your 4-emoji or full access key here",
            label_visibility="collapsed",
            height=110,
        )
        st.button(
            "Open my dashboard",
            type="primary",
            use_container_width=True,
            disabled=True,
            help="Disabled for now while the overview page takes over this material.",
        )
        st.page_link(
            COMPLEXITY_OVERVIEW_PAGE,
            label="Open the Complexity overview",
            use_container_width=True,
            icon=":material/travel_explore:",
        )
        error = str(st.session_state.get(LOGIN_ERROR_KEY, "") or "")
        if error:
            st.warning(error)


def _render_welcome() -> None:
    row = _quick_mode_card()
    st.markdown("### Let's have a quick temperature check.")
    st.caption("We will start with the quick pulse. You can extend it later.")
    button_label = f"{row['accent']} {row['title']}\n{row['detail']}"
    if st.button(
        button_label,
        type="primary",
        use_container_width=True,
        key="conference_mode_quick",
    ):
        update_draft(mode="quick")
        set_step(first_active_question_step())
        st.rerun()
    summary_card("Anonymous first", STEP_COPY["welcome"]["note"])


def _render_boiler_room_expander() -> None:
    if not _is_laptop_device():
        return
    draft = get_draft()
    with st.expander("Drop your contribution in the boiler room", expanded=False):
        st.caption(
            "Poster, lecture, presentation, text, images, data. You name it. Leave a short note or a link."
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
        update_draft(boiler_room_contribution=contribution)


def _render_pills(question: Dict[str, Any], current_value: Any) -> None:
    field = str(question["field"])
    option_map = {
        str(item["value"]): str(item["label"]) for item in question.get("options", [])
    }
    input_type = str(question["input_type"])
    if input_type == "multi":
        selected = st.pills(
            question["prompt"],
            list(option_map.keys()),
            default=list(current_value or [])
            if isinstance(current_value, list)
            else [],
            selection_mode="multi",
            key=f"conference_widget_{field}",
            format_func=lambda value: option_map.get(value, value),
            label_visibility="collapsed",
        )
        max_select = question.get("max_select")
        if isinstance(max_select, int) and len(selected) > max_select:
            selected = selected[:max_select]
        update_draft(**{field: list(selected)})
        if field == "role":
            custom_value = st.text_input(
                "Add one perspective label",
                value=str(get_draft().get("role_custom") or ""),
                key="conference_widget_role_custom",
                placeholder="Optional extra perspective",
            )
            update_draft(role_custom=str(custom_value or "").strip())
            if custom_value.strip():
                clear_deferred_field(field)
        if selected:
            clear_deferred_field(field)
        return

    selected_single = st.pills(
        question["prompt"],
        list(option_map.keys()),
        default=str(current_value)
        if isinstance(current_value, str) and current_value
        else None,
        selection_mode="single",
        key=f"conference_widget_{field}",
        format_func=lambda value: option_map.get(value, value),
        label_visibility="collapsed",
    )
    update_draft(**{field: str(selected_single or "")})
    if selected_single:
        clear_deferred_field(field)


def _render_scientific_home() -> None:
    draft = get_draft()
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
        scientific_home_country=country,
        scientific_home_city=city,
        scientific_home_institution=institution,
    )


def _render_fingerprint() -> None:
    draft = get_draft()
    fingerprint = draft.get("complexity_fingerprint", {})
    if not isinstance(fingerprint, dict):
        fingerprint = {}
    updated = {}
    for axis in FINGERPRINT_AXES:
        updated[axis] = int(
            st.slider(
                FINGERPRINT_LABELS.get(axis, axis.title()),
                min_value=0,
                max_value=5,
                value=int(fingerprint.get(axis, 0) or 0),
                key=f"conference_widget_fp_{axis}",
            )
        )
    update_draft(complexity_fingerprint=updated)
    if any(updated.values()):
        clear_deferred_field("complexity_fingerprint")


def _render_question_step(step: str) -> None:
    question = question_by_step(step)
    if not question:
        return
    field = str(question["field"])
    draft = get_draft()
    current_value = draft.get(field)
    input_type = str(question["input_type"])

    if input_type in {"single", "multi"}:
        _render_pills(question, current_value)
        return

    if input_type == "scientific_home":
        _render_scientific_home()
        return

    if input_type == "fingerprint":
        _render_fingerprint()
        return

    if input_type == "text":
        value = st.text_area(
            "",
            value=str(current_value or ""),
            key=f"conference_widget_{field}",
            placeholder=str(question.get("placeholder") or ""),
            max_chars=500,
            label_visibility="collapsed",
            height=180,
        )
        update_draft(**{field: value})
        if str(value or "").strip():
            clear_deferred_field(field)


def _render_identity() -> None:
    draft = get_draft()
    alias = st.text_input(
        "Alias",
        value=str(draft.get("alias") or ""),
        key="conference_widget_alias",
        placeholder="Optional public alias",
    )
    identity = st.text_input(
        "Identity",
        value=str(draft.get("identity") or ""),
        key="conference_widget_identity",
        placeholder="Optional name or affiliation",
    )
    contact = str(draft.get("contact") or "")
    if should_collect_contact(draft):
        contact = st.text_input(
            "Contact",
            value=contact,
            key="conference_widget_contact",
            placeholder="Optional email, website, or contact cue",
        )
    update_draft(
        alias=alias,
        identity=identity,
        contact=contact if should_collect_contact(draft) else "",
    )


def _render_review(session: Dict[str, Any]) -> None:
    _render_boiler_room_expander()
    payload = build_payload_view(get_draft())
    summary_card("Mode", _labels_for("mode", str(payload.get("mode") or "quick")))
    summary_card("Profile", "Persistent across events unless you change it.")
    summary_card("Perspective", _labels_for("role", payload.get("role")))
    if payload.get("career_stage"):
        summary_card(
            "Career stage", _labels_for("career_stage", payload.get("career_stage"))
        )
    summary_card(
        "Scientific home",
        _labels_for(
            "scientific_home",
            {
                "country": payload.get("scientific_home_country", ""),
                "city": payload.get("scientific_home_city", ""),
                "institution": payload.get("scientific_home_institution", ""),
            },
        ),
    )
    if payload.get("scale"):
        summary_card("Computational scale", _labels_for("scale", payload.get("scale")))
    if payload.get("collaboration_style"):
        summary_card(
            "Collaboration style",
            _labels_for("collaboration_style", payload.get("collaboration_style")),
        )
    summary_card("Assets", _labels_for("assets", payload.get("assets")))
    if "complexity_fingerprint" in active_question_steps(get_draft()):
        summary_card(
            "Complexity fingerprint",
            _labels_for(
                "complexity_fingerprint", payload.get("complexity_fingerprint")
            ),
        )

    summary_card(
        "Session",
        "These answers belong to this Complexity event and can change next time.",
    )
    summary_card("Event context", f"{COMPLEXITY_EVENT_LABEL} · {COMPLEXITY_EVENT_LOCATION}")
    summary_card("Motivations", _labels_for("motivations", payload.get("motivations")))
    summary_card("Obstacle", _labels_for("obstacle", payload.get("obstacle")))
    summary_card("Challenge", _labels_for("challenge", payload.get("challenge")))
    summary_card(
        "Follow-up interest",
        _labels_for("follow_up_interest", payload.get("follow_up_interest")),
    )
    if payload.get("open_question"):
        summary_card("Open question", str(payload["open_question"]))
    if payload.get("boiler_room_contribution"):
        summary_card(
            "Boiler room contribution",
            str(payload["boiler_room_contribution"]),
        )
    _render_question_flag_summary()

    pending = pending_reflection_fields(get_draft())
    if pending:
        summary_card(
            "Pending reflections",
            " · ".join(_field_label(field) for field in pending),
        )

    identity_parts = [
        str(payload.get("alias") or "").strip(),
        str(payload.get("identity") or "").strip(),
        str(payload.get("contact") or "").strip(),
    ]
    identity_text = (
        " · ".join(part for part in identity_parts if part) or "Remain anonymous"
    )
    summary_card("Alias or identity", identity_text)


def _question_teasers(submissions: List[Dict[str, Any]], self_actor: str) -> List[str]:
    entries: List[str] = []
    seen: set[str] = set()
    for item in submissions:
        if str(item.get("actor_key") or "") == self_actor:
            continue
        text = str(item.get("open_question") or "").strip()
        if not text or text in seen:
            continue
        entries.append(text)
        seen.add(text)
        if len(entries) >= 4:
            break
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

    for title, field, counter in [
        ("The room can bring…", "assets", snapshot["assets"]),
        ("The room is trying to solve…", "obstacle", snapshot["obstacles"]),
        ("The room would join…", "challenge", snapshot["challenges"]),
    ]:
        st.markdown(f"### {title}")
        if not counter:
            st.caption("No signals yet.")
            continue
        lines = [
            f"{value} · {_labels_for(field, key)}"
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
    payload = build_payload_view(get_draft())
    submissions = repo.group_rows_by_submission(
        repo.get_session_rows(session["id"], text_ids=complexity_text_ids())
    )
    conference_header("Complexity", "", step="")
    st.markdown("### Your profile is loaded.")
    summary_card("Mode", _labels_for("mode", str(payload.get("mode") or "quick")))
    summary_card("Perspective", _labels_for("role", payload.get("role")))
    summary_card("Assets", _labels_for("assets", payload.get("assets")))
    if payload.get("challenge"):
        summary_card(
            "Current challenge", _labels_for("challenge", payload.get("challenge"))
        )
    if payload.get("open_question"):
        summary_card("Open question", str(payload.get("open_question")))
    if payload.get("boiler_room_contribution"):
        summary_card(
            "Boiler room contribution",
            str(payload.get("boiler_room_contribution")),
        )
    _render_question_flag_summary()

    gaps = profile_completion_gaps(get_draft())
    if gaps and not bool(st.session_state.get("conference_hide_migration_prompt")):
        st.markdown("### We’ve added new questions")
        st.caption(
            f"We have added {len(gaps)} question(s) to better understand your perspective."
        )
        left, right = st.columns(2)
        with left:
            if st.button(
                "Yes, enthusiastically", type="primary", use_container_width=True
            ):
                _resume_at_field(
                    gaps[0], suggested_mode_for_missing_profile_fields(gaps)
                )
        with right:
            if st.button("Later", use_container_width=True):
                st.session_state["conference_hide_migration_prompt"] = True
                st.rerun()

    pending = pending_reflection_fields(get_draft())
    if pending:
        st.markdown("### Pending reflections")
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
        st.markdown("### Questions in the room")
        for text in teasers:
            summary_card("Open question", text)

    mode = str(payload.get("mode") or "quick")
    if mode == "quick":
        if st.button("Continue in Standard", type="primary", use_container_width=True):
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

    st.page_link(
        COMPLEXITY_OVERVIEW_PAGE,
        label="Open the Complexity overview",
        use_container_width=True,
        icon=":material/travel_explore:",
    )
    if st.button("Use another access key", use_container_width=True):
        _set_entry_mode("existing")
        _clear_login_error()
        st.rerun()


def _render_done() -> None:
    draft = get_draft()
    if st.session_state.pop("conference_show_success", False):
        st.balloons()
    st.success("Integrated into the current Complexity event.")
    access_key = str(draft.get("access_key") or "")
    emoji_key = hex_to_emoji(access_key) if access_key else ""
    access_key_hash = (
        hashlib.sha256(access_key.encode("utf-8")).hexdigest() if access_key else ""
    )
    summary_card(
        "Short key",
        "".join(split_emoji_symbols(emoji_key)[-4:]) if emoji_key else "Unavailable",
    )
    summary_card(
        "Hash prefix", access_key_hash[:12] if access_key_hash else "Unavailable"
    )
    with st.expander("Full emoji key", expanded=False):
        st.markdown(
            f"<div style='font-size:2rem; line-height:1.4; text-align:center; padding:.6rem 0;'>{emoji_key or 'Unavailable'}</div>",
            unsafe_allow_html=True,
        )
    with st.expander("ASCII access key", expanded=False):
        st.code(access_key or "Unavailable")
    st.button(
        "Open my dashboard",
        type="primary",
        use_container_width=True,
        disabled=True,
        help="Disabled for now while the overview page takes over this material.",
    )
    st.page_link(
        COMPLEXITY_OVERVIEW_PAGE,
        label="Open the Complexity overview",
        use_container_width=True,
        icon=":material/travel_explore:",
    )
    if st.button(STEP_COPY["done"]["cta"], use_container_width=True):
        reset_flow_state()
        _set_entry_mode("")
        st.rerun()


def _render_navigation(repo: Any, session: Dict[str, Any]) -> None:
    step = current_step()
    question = question_by_step(step)
    if step in {"welcome", "done"}:
        return
    if step == "review":
        left, right, side = st.columns([1, 1, 0.55])
        with left:
            if st.button("Edit", use_container_width=True):
                set_step(first_active_question_step())
                st.rerun()
        with right:
            if st.button(
                STEP_COPY["review"]["cta"], type="primary", use_container_width=True
            ):
                _open_confirm_send_dialog(repo, session)
        with side:
            if question:
                _render_question_flag_control(question)
        return

    if field_for_step(step) in DEFERRABLE_FIELDS:
        left, right, side = st.columns([1, 1, 0.55])
        with left:
            if st.button("Reflect later", use_container_width=True):
                defer_field(field_for_step(step))
                _advance_step()
                st.rerun()
        with right:
            if st.button("Continue", type="primary", use_container_width=True):
                draft = get_draft()
                if not step_is_complete(step, draft):
                    st.warning("Answer this step or defer it for later.")
                    return
                _advance_step()
                st.rerun()
        with side:
            if question:
                _render_question_flag_control(question)
        return

    action, side = st.columns([1, 0.55])
    with action:
        if st.button("Continue", type="primary", use_container_width=True):
            draft = get_draft()
            if not step_is_complete(step, draft):
                st.warning("Complete this step before continuing.")
                return
            _advance_step()
            st.rerun()
    with side:
        if question:
            _render_question_flag_control(question)


def _render_questionnaire(repo: Any, session: Dict[str, Any]) -> None:
    if current_step() not in active_step_sequence():
        set_step("welcome")
    step = current_step()
    copy = STEP_COPY[step]
    sequence = active_step_sequence()
    step_index = sequence.index(step) + 1 if step in sequence else 1
    step_label = f"{step_index} / {len(sequence)}" if step != "done" else "complete"
    conference_header(copy["title"], "", step=step_label)
    if copy.get("body"):
        st.markdown(f"### {copy['body']}")
    _render_event_scope_notice(session)

    if step == "welcome":
        _render_welcome()
    elif step == IDENTITY_STEP:
        _render_identity()
    elif step == "review":
        _render_review(session)
    elif step == "done":
        _render_done()
    else:
        _render_question_step(step)

    _render_navigation(repo, session)


def main() -> None:
    set_page()
    apply_conference_styles()
    sidebar_debug_state()
    _ensure_local_state()

    repo = get_conference_repo()
    if not repo or not repo.is_ready():
        st.error(
            repo.unavailable_reason if repo else "Conference repository is unavailable."
        )
        return

    session_code = current_complexity_session_code(repo)
    bundle = get_conference_bundle(session_code=session_code)
    session = bundle.get("session")
    if not session:
        st.error(
            f"Conference session is missing. Ensure `{session_code}` exists in the shared sessions DB."
        )
        return

    _hydrate_existing_submission(repo, session["id"])

    mode = _entry_mode()
    if mode == "dashboard":
        _render_personal_dashboard(repo, session)
        return
    if mode == "new" or get_draft().get("submitted"):
        _render_questionnaire(repo, session)
        return
    _render_entry(session, repo)


if __name__ == "__main__":
    main()
