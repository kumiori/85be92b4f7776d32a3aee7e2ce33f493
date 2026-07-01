from __future__ import annotations

import html
import hashlib
import uuid
from collections.abc import Mapping
from typing import Any, Callable, Dict, List

import streamlit as st
import streamlit.components.v1 as components

from conference.context import get_conference_bundle, get_conference_repo
from conference.events import (
    UNESCO_SESSION_CODE,
    YOUNG_SESSION_CODE,
    conference_event_context,
    conference_event_options,
    text_ids_for_session_code,
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
from conference.question_sets import (
    QuestionDefinition,
    QuestionSet,
    field_for_step,
    field_option_label_map,
    field_value_set,
    question_by_field,
    question_by_step,
)
from conference.registry import resolve_question_set_bundle
from conference.question_flags import (
    QUESTION_FLAG_LABELS,
    QUESTION_FLAG_OPTIONS,
    normalize_question_flags,
)
from conference.repo import emoji_suffix, resolve_access_key_input
from conference.topology import count_field, room_snapshot
from conference.ui import apply_conference_styles, conference_header, summary_card
from infra.key_codec import generate_hex_key, hex_to_emoji, split_emoji_symbols
from ui import set_page, sidebar_debug_state


IDENTITY_STEP = "identity"
ENTRY_KEY = "conference_entry_mode"
LOGIN_ERROR_KEY = "conference_login_error"


def _ensure_local_state(question_set: QuestionSet) -> None:
    existing = st.session_state.get("conference_question_set")
    if isinstance(existing, QuestionSet) and str(existing.id) != str(question_set.id):
        reset_flow_state(question_set=question_set)
    init_flow_state(question_set=question_set)
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


def _event_context(session: Dict[str, Any]) -> Dict[str, Any]:
    return conference_event_context(session=session)


def _event_scope_text(session: Dict[str, Any]) -> str:
    context = _event_context(session)
    location = str(context.get("event_location") or "").strip()
    if location:
        return f"{context['event_label']} in {location}"
    return str(context.get("event_label") or context.get("event_code") or "this event")


def _sync_event_query(event_slug: str) -> None:
    next_params: Dict[str, str] = {"event": str(event_slug or "").strip()}
    key = str(st.query_params.get("key", "") or "").strip()
    if key:
        next_params["key"] = key
    st.query_params.clear()
    st.query_params.update(next_params)


def _switch_to_event_overview(session: Dict[str, Any]) -> None:
    context = _event_context(session)
    _sync_event_query(str(context["event_slug"]))
    st.switch_page(str(context["overview_page"]))


def _event_is_read_only(session: Dict[str, Any]) -> bool:
    return not bool(_event_context(session).get("write_enabled"))


def _render_event_selector(repo: Any, session: Dict[str, Any], *, selector_key: str) -> None:
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
        (row for row in mode_cards(question_set=current_question_set()) if str(row.get("value") or "") == "quick"),
        {
            "value": "quick",
            "title": "Quick pulse",
            "detail": "~ 3 minutes",
            "accent": "🧊",
        },
    )


def _question_prompt_by_id(question_id: str) -> str:
    return flow_question_prompt_by_id(question_id, question_set=current_question_set())


def _question_flag_entries() -> Dict[str, Dict[str, Any]]:
    return normalize_question_flags(get_draft(question_set=current_question_set()).get("question_flags"))


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


def _render_question_flag_control(question: QuestionDefinition) -> None:
    question_id = str(question.question_id or "").strip()
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
    return infer_mode_from_submission(submission, question_set=current_question_set())


def _labels_for(field: str, value: Any) -> str:
    if field == "mode":
        return mode_label(str(value or "quick"), question_set=current_question_set())
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
    if field_for_step(current_question_set(), str(question.step)) == "scientific_home":
        return any(str(value.get(key) or "").strip() for key in ("country", "city", "institution"))
    if input_type == "multi":
        return bool(value)
    if input_type == "fingerprint" and isinstance(value, dict):
        return any(int(value.get(axis, 0) or 0) > 0 for axis in current_question_set().fingerprint_axes)
    if isinstance(value, str):
        return bool(value.strip())
    return bool(value)


def _question_summary_body(question: QuestionDefinition, payload: Dict[str, Any]) -> str:
    field = str(question.field)
    value = _question_value(question, payload)
    if str(question.input_type) == "text":
        body = html.escape(str(value or "").strip())
    else:
        body = html.escape(_labels_for(field, value))
    free_text_field = str(getattr(question, "free_text_field", "") or "").strip()
    free_text_value = str(payload.get(free_text_field) or "").strip() if free_text_field else ""
    if free_text_value:
        free_text_label = html.escape(str(getattr(question, "free_text_label", "") or "Detail"))
        detail = html.escape(free_text_value)
        body = f"{body}<br><span style='opacity:.72'>{free_text_label}</span><br>{detail}" if body else detail
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
        if active_steps is not None and str(question.step) not in active_steps:
            continue
        if not _question_answered(question, payload):
            continue
        entries.append((_question_title(question), _question_summary_body(question, payload)))
    return entries


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
    next_mode = mode or str(get_draft(question_set=current_question_set()).get("mode") or "standard")
    target_step = _step_for_field(field) or first_active_question_step(question_set=current_question_set())
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
        st.session_state["conference_submission_cache_key"] = cache_key
        st.session_state["conference_submission_cache"] = submission
    return access_key, submission, ""


def _hydrate_existing_submission(repo: Any, session: Dict[str, Any]) -> None:
    if st.session_state.get("conference_hydrated"):
        return
    draft = get_draft(question_set=current_question_set())
    raw_key = str(
        draft.get("access_key") or st.query_params.get("key", "") or ""
    ).strip()
    if not raw_key:
        st.session_state["conference_hydrated"] = True
        return
    access_key, submission, _ = _load_submission_for_key(repo, session, raw_key)
    if access_key and submission:
        submission = _normalize_hydrated_submission(submission)
        hydrated = {
            key: value for key, value in submission.items() if key in get_draft(question_set=current_question_set())
        }
        hydrated["mode"] = str(submission.get("mode") or _infer_mode(submission))
        hydrated["access_key"] = access_key
        hydrated["submitted"] = True
        update_draft(question_set=current_question_set(), **hydrated)
        repo.upsert_conference_player(
            session_id=str(session.get("id") or ""),
            access_key=access_key,
            payload=build_session_payload(get_draft(question_set=current_question_set()), question_set=current_question_set()),
            identity_metadata=build_identity_metadata(get_draft(question_set=current_question_set()), question_set=current_question_set()),
        )
        _set_entry_mode("dashboard")
    elif access_key:
        update_draft(question_set=current_question_set(), access_key=access_key)
    st.session_state["conference_hydrated"] = True


def _advance_step() -> None:
    next_step(question_set=current_question_set())


def _normalize_hydrated_submission(submission: Dict[str, Any]) -> Dict[str, Any]:
    normalized = dict(submission)
    allowed_roles = field_value_set(current_question_set(), "role")
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
    access_key = str(get_draft(question_set=current_question_set()).get("access_key") or "").strip()
    if access_key:
        return access_key
    access_key = generate_hex_key()
    update_draft(question_set=current_question_set(), access_key=access_key)
    return access_key


def _payload_for_session(draft: Dict[str, Any], session: Dict[str, Any]) -> Dict[str, Any]:
    payload = build_session_payload(draft, question_set=current_question_set())
    profile = payload.get("profile") if isinstance(payload.get("profile"), dict) else {}
    session_payload = payload.get("session") if isinstance(payload.get("session"), dict) else {}
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
    session_payload["schema_id"] = context["schema_id"]
    session_payload["question_set_id"] = context["question_set_id"]
    session_payload["response_scope"] = context["response_scope"]
    payload["profile"] = profile
    payload["session"] = session_payload
    return payload


def _render_event_scope_notice(session: Dict[str, Any]) -> None:
    context = _event_context(session)
    body = (
        f"This response belongs to {_event_scope_text(session)}. "
        "Profile questions persist across events; session answers belong only to this event."
    )
    if _event_is_read_only(session):
        body += (
            f" This event is currently {str(context.get('event_status') or 'closed')}; "
            "new responses are read-only."
        )
    st.caption(body)


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
    identity_metadata = build_identity_metadata(draft, question_set=current_question_set())
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
        _event_context(session)["text_id"],
        str(st.session_state.get("conference_device_id", "")),
        access_key_hash,
        access_key_last4,
        payload,
        identity_metadata,
    )
    st.session_state["conference_submission_cache_key"] = (
        f"{session['id']}:{access_key_hash}:{event_context['text_id']}"
    )
    st.session_state["conference_submission_cache"] = build_payload_view(draft, question_set=current_question_set()) | {
        "access_key_hash": access_key_hash,
        "access_key_last4": access_key_last4,
        "actor_key": f"player:{str((player or {}).get('id') or '')}"
        if (player or {}).get("id")
        else f"response:{access_key_hash}",
    }
    st.session_state["conference_show_success"] = True
    update_draft(question_set=current_question_set(), access_key=access_key, submitted=True)
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
            f"### {_event_context(session)['event_label']} is making this anonymous first. "
            "This access key lets you return later to your profile and your pending reflections."
        )
        if st.button("Screenshot taken", type="primary", use_container_width=True):
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
        _set_login_error("No submission was found for this access key yet.")
        return
    submission = _normalize_hydrated_submission(submission)
    hydrated = {
        key: value
        for key, value in submission.items()
        if key in get_draft(question_set=current_question_set())
    }
    hydrated["mode"] = str(submission.get("mode") or _infer_mode(submission))
    hydrated["access_key"] = access_key
    hydrated["submitted"] = True
    update_draft(question_set=current_question_set(), **hydrated)
    repo.upsert_conference_player(
        session_id=str(session.get("id") or ""),
        access_key=access_key,
        payload=build_session_payload(get_draft(question_set=current_question_set()), question_set=current_question_set()),
        identity_metadata=build_identity_metadata(get_draft(question_set=current_question_set()), question_set=current_question_set()),
    )
    _clear_login_error()
    _set_entry_mode("dashboard")
    st.rerun()


def _resume_in_mode(mode: str) -> None:
    update_draft(question_set=current_question_set(), mode=mode, submitted=False)
    set_step(first_active_question_step(question_set=current_question_set()), question_set=current_question_set())
    _set_entry_mode("new")
    st.rerun()


def _render_entry(session: Dict[str, Any], repo: Any) -> None:
    conference_header(str(_event_context(session)["event_label"]), "", step="")
    st.markdown("### Anonymous first.")
    _render_event_scope_notice(session)
    st.markdown("### Choose how to enter.")
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
    if st.button("🔑 I already have an access key", use_container_width=True):
        _open_existing_login()
        st.rerun()
    if _entry_mode() == "existing":
        st.markdown("### Enter your emoji access key.")
        raw_key = st.text_area(
            "Access key",
            value=str(get_draft(question_set=current_question_set()).get("access_key") or ""),
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
        update_draft(question_set=current_question_set(), mode="quick")
        set_step(first_active_question_step(question_set=current_question_set()), question_set=current_question_set())
        st.rerun()
    summary_card("Anonymous first", current_question_set().step_copy["welcome"]["note"])


def _render_boiler_room_expander() -> None:
    if not _is_laptop_device():
        return
    draft = get_draft(question_set=current_question_set())
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
        update_draft(question_set=current_question_set(), boiler_room_contribution=contribution)


def _render_pills(question: QuestionDefinition, current_value: Any) -> None:
    field = str(question.field)
    option_map = {
        str(item["value"]): str(item["label"]) for item in question.options
    }
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
        if field == "role":
            custom_value = st.text_input(
                "Add one perspective label",
                value=str(get_draft(question_set=current_question_set()).get("role_custom") or ""),
                key="conference_widget_role_custom",
                placeholder="Optional extra perspective",
            )
            update_draft(question_set=current_question_set(), role_custom=str(custom_value or "").strip())
            if custom_value.strip():
                clear_deferred_field(field, question_set=current_question_set())
        if selected:
            clear_deferred_field(field, question_set=current_question_set())
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
        update_draft(question_set=current_question_set(), **{field: str(selected_single or "")})
        if selected_single:
            clear_deferred_field(field, question_set=current_question_set())

    free_text_field = str(getattr(question, "free_text_field", "") or "").strip()
    if free_text_field:
        detail_value = st.text_input(
            str(getattr(question, "free_text_label", "") or "Detail"),
            value=str(get_draft(question_set=current_question_set()).get(free_text_field) or ""),
            key=f"conference_widget_{free_text_field}",
            placeholder=str(getattr(question, "free_text_placeholder", "") or ""),
        )
        update_draft(question_set=current_question_set(), **{free_text_field: str(detail_value or "").strip()})


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
        clear_deferred_field("complexity_fingerprint", question_set=current_question_set())


def _render_question_step(step: str) -> None:
    question = question_by_step(current_question_set(), step)
    if not question:
        return
    field = str(question.field)
    draft = get_draft(question_set=current_question_set())
    current_value = draft.get(field)
    input_type = str(question.input_type)

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
            placeholder=str(question.placeholder or ""),
            max_chars=500,
            label_visibility="collapsed",
            height=180,
        )
        update_draft(question_set=current_question_set(), **{field: value})
        if str(value or "").strip():
            clear_deferred_field(field, question_set=current_question_set())


def _render_identity() -> None:
    draft = get_draft(question_set=current_question_set())
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
    if should_collect_contact(draft, question_set=current_question_set()):
        contact = st.text_input(
            "Contact",
            value=contact,
            key="conference_widget_contact",
            placeholder="Optional email, website, or contact cue",
        )
    update_draft(
        question_set=current_question_set(),
        alias=alias,
        identity=identity,
        contact=contact if should_collect_contact(draft, question_set=current_question_set()) else "",
    )


def _render_review(session: Dict[str, Any]) -> None:
    _render_boiler_room_expander()
    payload = build_payload_view(get_draft(question_set=current_question_set()), question_set=current_question_set())
    active_steps = set(active_question_steps(get_draft(question_set=current_question_set()), question_set=current_question_set()))
    summary_card("Mode", _labels_for("mode", str(payload.get("mode") or "quick")))
    summary_card("Profile", "Persistent across events unless you change it.")
    for title, body in _question_summary_entries(payload, section="profile", active_steps=active_steps):
        summary_card(title, body)

    summary_card(
        "Session",
        f"These answers belong to {_event_scope_text(session)} and can change next time.",
    )
    summary_card("Event context", _event_scope_text(session))
    for title, body in _question_summary_entries(payload, section="session", active_steps=active_steps):
        summary_card(title, body)
    if payload.get("boiler_room_contribution"):
        summary_card(
            "Boiler room contribution",
            html.escape(str(payload["boiler_room_contribution"])),
        )
    _render_question_flag_summary()

    pending = pending_reflection_fields(get_draft(question_set=current_question_set()), question_set=current_question_set())
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
            st.caption("No signals yet.")
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
    payload = build_payload_view(get_draft(question_set=current_question_set()), question_set=current_question_set())
    active_steps = set(active_question_steps(get_draft(question_set=current_question_set()), question_set=current_question_set()))
    submissions = repo.group_rows_by_submission(
        repo.get_session_rows(
            session["id"],
            text_ids=text_ids_for_session_code(str(session.get("session_code") or "")),
        )
    )
    conference_header(str(event_context["event_label"]), "", step="")
    st.markdown("### Your profile is loaded.")
    summary_card("Mode", _labels_for("mode", str(payload.get("mode") or "quick")))
    for title, body in _question_summary_entries(payload, section="profile", active_steps=active_steps):
        summary_card(title, body)
    for title, body in _question_summary_entries(payload, section="session", active_steps=active_steps):
        summary_card(title, body)
    if payload.get("boiler_room_contribution"):
        summary_card(
            "Boiler room contribution",
            html.escape(str(payload.get("boiler_room_contribution"))),
        )
    _render_question_flag_summary()

    gaps = profile_completion_gaps(get_draft(question_set=current_question_set()), question_set=current_question_set())
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
                    gaps[0], suggested_mode_for_missing_profile_fields(gaps, question_set=current_question_set())
                )
        with right:
            if st.button("Later", use_container_width=True):
                st.session_state["conference_hide_migration_prompt"] = True
                st.rerun()

    pending = pending_reflection_fields(get_draft(question_set=current_question_set()), question_set=current_question_set())
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
        for item in teasers:
            title, _, text = item.partition("|||")
            summary_card(title or "Question", html.escape(text))

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
    st.success(f"Integrated into {_event_scope_text(session)}.")
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
    if st.button(
        f"Open the {_event_context(session)['event_label']} overview",
        use_container_width=True,
        key="conference-done-open-overview",
    ):
        _switch_to_event_overview(session)
    if st.button(current_question_set().step_copy["done"]["cta"], use_container_width=True):
        reset_flow_state(question_set=current_question_set())
        _set_entry_mode("")
        st.rerun()


def _render_navigation(repo: Any, session: Dict[str, Any]) -> None:
    step = current_step()
    question = question_by_step(current_question_set(), step)
    if step in {"welcome", "done"}:
        return
    if step == "review":
        left, right, side = st.columns([1, 1, 0.55])
        with left:
            if st.button("Edit", use_container_width=True):
                set_step(first_active_question_step(question_set=current_question_set()), question_set=current_question_set())
                st.rerun()
        with right:
            review_help = None
            if _event_is_read_only(session):
                review_help = (
                    f"This event is {str(_event_context(session).get('event_status') or 'closed')}."
                )
            if st.button(
                current_question_set().step_copy["review"]["cta"],
                type="primary",
                use_container_width=True,
                disabled=_event_is_read_only(session),
                help=review_help,
            ):
                _open_confirm_send_dialog(repo, session)
        with side:
            if question:
                _render_question_flag_control(question)
        return

    if field_for_step(current_question_set(), step) in set(current_question_set().deferrable_fields):
        left, right, side = st.columns([1, 1, 0.55])
        with left:
            if st.button("Reflect later", use_container_width=True):
                defer_field(field_for_step(current_question_set(), step), question_set=current_question_set())
                _advance_step()
                st.rerun()
        with right:
            if st.button("Continue", type="primary", use_container_width=True):
                draft = get_draft(question_set=current_question_set())
                if not step_is_complete(step, draft, question_set=current_question_set()):
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
            draft = get_draft(question_set=current_question_set())
            if not step_is_complete(step, draft, question_set=current_question_set()):
                st.warning("Complete this step before continuing.")
                return
            _advance_step()
            st.rerun()
    with side:
        if question:
            _render_question_flag_control(question)


def _render_questionnaire(repo: Any, session: Dict[str, Any]) -> None:
    if _event_is_read_only(session) and not bool(get_draft(question_set=current_question_set()).get("submitted")):
        conference_header(str(_event_context(session)["event_label"]), "", step="read-only")
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
        set_step("welcome", question_set=current_question_set())
    step = current_step()
    copy = current_question_set().step_copy[step]
    sequence = active_step_sequence(question_set=current_question_set())
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
        _render_done(session)
    else:
        _render_question_step(step)

    _render_navigation(repo, session)


def run_conference_questionnaire_page(
    *,
    session_code_resolver: Callable[[Any], str],
    event_selector_key: str = "conference-event-selector",
) -> None:
    set_page()
    apply_conference_styles()
    sidebar_debug_state()

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
    _ensure_local_state(bundle_spec.question_set)

    _render_event_selector(repo, session, selector_key=event_selector_key)
    _hydrate_existing_submission(repo, session)

    mode = _entry_mode()
    if mode == "dashboard":
        _render_personal_dashboard(repo, session)
        return
    if mode == "new" or get_draft(question_set=current_question_set()).get("submitted"):
        _render_questionnaire(repo, session)
        return
    _render_entry(session, repo)
