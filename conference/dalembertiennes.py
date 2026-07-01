from __future__ import annotations

from typing import Any, Dict, List

import streamlit as st

from conference.events import (
    DALAMBERTIENNES_SESSION_CODE,
    conference_event_context,
    conference_event_options,
)
from infra.key_codec import generate_hex_key


PLACEHOLDER_PROMPT = "What is one question this event should ask?"
PLACEHOLDER_HINT = (
    "This is a placeholder checkpoint. One answer is enough to confirm that "
    "Dalembertiennes writes stay isolated from other events."
)


def resolve_dalembertiennes_session(repo: Any, bundle_loader: Any) -> Dict[str, Any] | None:
    bundle = bundle_loader(session_code=DALAMBERTIENNES_SESSION_CODE)
    session = bundle.get("session") if isinstance(bundle, dict) else None
    return session if isinstance(session, dict) else None


def event_context(session: Dict[str, Any]) -> Dict[str, Any]:
    return conference_event_context(session=session)


def event_scope_text(session: Dict[str, Any]) -> str:
    context = event_context(session)
    location = str(context.get("event_location") or "").strip()
    if location:
        return f"{context['event_label']} in {location}"
    return str(context.get("event_label") or context.get("event_code") or "this event")


def sync_event_query(event_slug: str) -> None:
    next_params: Dict[str, str] = {"event": str(event_slug or "").strip()}
    key = str(st.query_params.get("key", "") or "").strip()
    if key:
        next_params["key"] = key
    st.query_params.clear()
    st.query_params.update(next_params)


def render_event_selector(
    repo: Any,
    session: Dict[str, Any],
    *,
    key: str,
    target_field: str,
) -> None:
    options = conference_event_options(repo)
    if len(options) <= 1:
        return
    code_to_option = {str(item["session_code"]): item for item in options}
    current_code = str(session.get("session_code") or "")
    option_codes = [str(item["session_code"]) for item in options]
    if current_code not in code_to_option:
        context = event_context(session)
        option_codes.insert(0, current_code)
        code_to_option[current_code] = {
            "event_slug": context["event_slug"],
            "session_code": current_code,
            "event_label": context["event_label"],
            "event_location": context["event_location"],
            "questionnaire_page": context["questionnaire_page"],
            "overview_page": context["overview_page"],
            "host_page": context["host_page"],
        }
    selected_code = st.selectbox(
        "Event",
        option_codes,
        index=option_codes.index(current_code),
        key=key,
        format_func=lambda code: (
            f"{code_to_option[code]['event_label']} · {code_to_option[code]['event_location']}"
            if str(code_to_option[code].get("event_location") or "").strip()
            else str(code_to_option[code]["event_label"])
        ),
    )
    if selected_code != current_code:
        selected = code_to_option[selected_code]
        sync_event_query(str(selected["event_slug"]))
        st.switch_page(str(selected[target_field]))


def build_placeholder_payload(session: Dict[str, Any], answer: str) -> Dict[str, Any]:
    context = event_context(session)
    return {
        "schema_version": "2",
        "profile": {
            "role": [],
            "role_custom": "",
            "career_stage": "",
            "scientific_home": {"country": "", "city": "", "institution": ""},
            "computational_scale": "",
            "collaboration_style": "",
            "assets": [],
            "complexity_fingerprint": {
                "theory": 0,
                "data": 0,
                "experiments": 0,
                "mechanisms": 0,
            },
            "persistence_scope": "persistent_profile",
        },
        "session": {
            "depth": "placeholder",
            "motivations": [],
            "obstacle": [],
            "challenge": "",
            "follow_up_interest": "",
            "open_question": str(answer or "").strip(),
            "boiler_room_contribution": "",
            "question_flags": {},
            "deferred_fields": [],
            "identity_reveal_targets": [],
            "event_slug": context["event_slug"],
            "event_label": context["event_label"],
            "event_code": context["event_code"],
            "event_location": context["event_location"],
            "event_status": context["event_status"],
            "session_code": str(session.get("session_code") or ""),
            "session_id": str(session.get("id") or ""),
            "text_id": context["text_id"],
            "schema_id": context["schema_id"],
            "question_set_id": context["question_set_id"],
            "response_scope": context["response_scope"],
        },
        "derived": {"neighbour_ids": []},
    }


def fresh_state() -> Dict[str, Any]:
    return {
        "answer": "",
        "access_key": "",
        "submitted": False,
    }


def ensure_state(state_key: str) -> None:
    state = st.session_state.get(state_key)
    if not isinstance(state, dict):
        st.session_state[state_key] = fresh_state()


def get_state(state_key: str) -> Dict[str, Any]:
    ensure_state(state_key)
    return dict(st.session_state.get(state_key) or {})


def update_state(state_key: str, **values: Any) -> Dict[str, Any]:
    state = get_state(state_key)
    state.update(values)
    st.session_state[state_key] = state
    return state


def reset_state(state_key: str) -> None:
    st.session_state[state_key] = fresh_state()


def ensure_access_key(state_key: str) -> str:
    state = get_state(state_key)
    access_key = str(state.get("access_key") or "").strip()
    if access_key:
        return access_key
    access_key = generate_hex_key()
    update_state(state_key, access_key=access_key)
    return access_key


def export_rows(submissions: List[Dict[str, Any]]) -> List[Dict[str, str]]:
    rows: List[Dict[str, str]] = []
    for item in submissions:
        rows.append(
            {
                "submitted_at": str(item.get("submitted_at") or ""),
                "access_key_last4": str(item.get("access_key_last4") or ""),
                "placeholder_question": str(item.get("open_question") or "").strip(),
            }
        )
    return rows
