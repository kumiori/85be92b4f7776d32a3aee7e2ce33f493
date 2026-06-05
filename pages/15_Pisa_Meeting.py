from __future__ import annotations

import hashlib
import uuid
from typing import Any, Dict, List

import streamlit as st
import streamlit.components.v1 as components

from conference.context import get_conference_bundle, get_conference_repo
from conference.flow import (
    active_question_steps,
    active_step_sequence,
    build_session_payload,
    current_step,
    first_active_question_step,
    get_draft,
    init_flow_state,
    mark_submitted,
    next_step,
    reset_flow_state,
    set_step,
    should_collect_contact,
    step_is_complete,
    update_draft,
)
from conference.models import STEP_COPY, field_option_label_map, mode_card_rows, question_by_step
from conference.repo import emoji_suffix
from conference.ui import apply_conference_styles, conference_header, summary_card
from infra.key_codec import generate_hex_key, hex_to_emoji, normalize_access_key, split_emoji_symbols
from ui import set_page, sidebar_debug_state


PAGE_KEY = "pisa-meeting"
TEXT_ID = "pisa_session_v2"
IDENTITY_STEP = "identity"


def _ensure_local_state() -> None:
    init_flow_state()
    st.session_state.setdefault("conference_device_id", uuid.uuid4().hex[:16])


def _infer_mode(submission: Dict[str, Any]) -> str:
    if submission.get("career_stage") or submission.get("research_style") or submission.get("timescale"):
        return "deep"
    if submission.get("formulation") or submission.get("reality_check") or submission.get("scale"):
        return "standard"
    return "quick"


def _hydrate_existing_submission(repo: Any, session_id: str) -> None:
    if st.session_state.get("conference_hydrated"):
        return
    draft = get_draft()
    raw_key = str(draft.get("access_key") or st.query_params.get("key", "") or "").strip()
    if not raw_key:
        st.session_state["conference_hydrated"] = True
        return
    try:
        access_key = normalize_access_key(raw_key)
    except ValueError:
        st.session_state["conference_hydrated"] = True
        return
    access_key_hash = repo.access_key_hash(access_key)
    cache_key = f"{session_id}:{access_key_hash}"
    submission = st.session_state.get("conference_submission_cache")
    if st.session_state.get("conference_submission_cache_key") != cache_key:
        submission = repo.latest_submission_by_access_key_hash(
            session_id=session_id,
            access_key_hash=access_key_hash,
        )
        st.session_state["conference_submission_cache_key"] = cache_key
        st.session_state["conference_submission_cache"] = submission
    if submission:
        hydrated = {
            key: value
            for key, value in submission.items()
            if key in get_draft()
        }
        hydrated["mode"] = str(submission.get("mode") or _infer_mode(submission))
        hydrated["access_key"] = access_key
        update_draft(**hydrated)
    else:
        update_draft(access_key=access_key)
    st.session_state["conference_hydrated"] = True


def _advance_step(step: str) -> None:
    next_step()


def _labels_for(field: str, value: Any) -> str:
    label_map = field_option_label_map(field)
    if isinstance(value, list):
        labels = [label_map.get(str(item), str(item)) for item in value]
        return ", ".join(labels) if labels else "None selected"
    if isinstance(value, str):
        return label_map.get(value, value) if value else "No answer"
    return str(value or "No answer")


def _ensure_access_key(repo: Any) -> str:
    access_key = str(get_draft().get("access_key") or "").strip()
    if access_key:
        return access_key
    access_key = generate_hex_key()
    update_draft(access_key=access_key)
    return access_key


def _submit(repo: Any, session: Dict[str, Any]) -> None:
    payload = build_session_payload(get_draft())
    access_key = _ensure_access_key(repo)
    access_key_hash = repo.access_key_hash(access_key)
    access_key_last4 = emoji_suffix(access_key)
    repo.save_session_response_set(
        session_id=session["id"],
        player_id=None,
        text_id=TEXT_ID,
        device_id=str(st.session_state.get("conference_device_id", "")),
        access_key_hash=access_key_hash,
        access_key_last4=access_key_last4,
        payload=payload,
    )
    st.session_state["conference_submission_cache_key"] = f"{session['id']}:{access_key_hash}"
    st.session_state["conference_submission_cache"] = payload | {
        "access_key_hash": access_key_hash,
        "access_key_last4": access_key_last4,
    }
    update_draft(access_key=access_key)
    mark_submitted()


def _open_confirm_send_dialog(repo: Any, session: Dict[str, Any]) -> None:
    @st.dialog("Save this key")
    def _confirm_send_dialog() -> None:
        access_key = _ensure_access_key(repo)
        emoji_key = hex_to_emoji(access_key)
        emoji_symbols = split_emoji_symbols(emoji_key)
        short_emoji = "".join(emoji_symbols[-4:]) if len(emoji_symbols) >= 4 else emoji_key
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
            "### All this interaction is anonymous. This key will give you access to your answers and what will follow. Store it safely."
        )
        if st.button("Screenshot taken", type="primary", use_container_width=True):
            _submit(repo, session)
            st.rerun()

    _confirm_send_dialog()


def _select_mode(mode: str, session_id: str) -> None:
    update_draft(mode=mode)
    set_step(first_active_question_step())
    st.rerun()


def _render_welcome(session: Dict[str, Any]) -> None:
    st.markdown("### How much time do you have?")
    for row in mode_card_rows():
        button_label = f"{row['accent']} {row['title']}\n{row['detail']}"
        if st.button(button_label, type="primary", use_container_width=True, key=f"conference_mode_{row['value']}"):
            _select_mode(str(row["value"]), session["id"])
    summary_card("Anonymous first", STEP_COPY["welcome"]["note"])


def _render_question_step(step: str) -> None:
    question = question_by_step(step)
    if not question:
        return
    field = str(question["field"])
    draft = get_draft()
    current_value = draft.get(field)
    input_type = str(question["input_type"])

    if input_type in {"single", "multi"}:
        option_map = {str(item["value"]): str(item["label"]) for item in question.get("options", [])}
        selected = st.pills(
            question["prompt"],
            list(option_map.keys()),
            default=list(current_value or []) if isinstance(current_value, list) else ([str(current_value)] if current_value else []),
            selection_mode="multi",
            key=f"conference_widget_{field}",
            format_func=lambda value: option_map.get(value, value),
            label_visibility="collapsed",
        )
        max_select = question.get("max_select")
        if isinstance(max_select, int) and len(selected) > max_select:
            selected = selected[:max_select]
        update_draft(**{field: list(selected)})
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
    contact = ""
    if should_collect_contact(draft):
        contact = st.text_input(
            "Contact",
            value=str(draft.get("contact") or ""),
            key="conference_widget_contact",
            placeholder="Optional email, website, or contact cue",
        )
    notes = st.text_area(
        "Notes",
        value=str(draft.get("notes") or ""),
        key="conference_widget_notes",
        placeholder="Optional additional note",
        max_chars=280,
        height=140,
    )
    update_draft(alias=alias, identity=identity, contact=contact, notes=notes)


def _render_review() -> None:
    payload = build_session_payload(get_draft())
    summary_card("Format", str(payload.get("mode") or "quick").replace("_", " ").title())
    for step in active_question_steps(get_draft()):
        model = question_by_step(step)
        if not model:
            continue
        field = str(model["field"])
        summary_card(model["prompt"], _labels_for(field, payload.get(field)))
    identity_parts = [
        str(payload.get("alias") or "").strip(),
        str(payload.get("identity") or "").strip(),
        str(payload.get("contact") or "").strip(),
    ]
    identity_text = " · ".join(part for part in identity_parts if part) or "Remain anonymous"
    summary_card("Alias or identity", identity_text)
    if payload.get("notes"):
        summary_card("Notes", str(payload["notes"]))


def _render_done() -> None:
    draft = get_draft()
    access_key = str(draft.get("access_key") or "")
    emoji_key = hex_to_emoji(access_key) if access_key else ""
    access_key_hash = hashlib.sha256(access_key.encode("utf-8")).hexdigest() if access_key else ""
    summary_card("Short key", "".join(split_emoji_symbols(emoji_key)[-4:]) if emoji_key else "Unavailable")
    summary_card("Hash prefix", access_key_hash[:12] if access_key_hash else "Unavailable")
    with st.expander("Full emoji key", expanded=False):
        st.markdown(
            f"<div style='font-size:2rem; line-height:1.4; text-align:center; padding:.6rem 0;'>{emoji_key or 'Unavailable'}</div>",
            unsafe_allow_html=True,
        )
    with st.expander("ASCII access key", expanded=False):
        st.code(access_key or "Unavailable")
    if st.button(STEP_COPY["done"]["cta"], use_container_width=True):
        reset_flow_state()
        st.rerun()


def _render_navigation(repo: Any, session: Dict[str, Any]) -> None:
    step = current_step()
    if step in {"welcome", "done"}:
        return
    if step == "review":
        left, right = st.columns(2)
        with left:
            if st.button("Edit", use_container_width=True):
                set_step(first_active_question_step())
                st.rerun()
        with right:
            if st.button(STEP_COPY["review"]["cta"], type="primary", use_container_width=True):
                _open_confirm_send_dialog(repo, session)
        return
    if st.button("Continue", type="primary", use_container_width=True):
        draft = get_draft()
        if not step_is_complete(step, draft):
            st.warning("Complete this step before continuing.")
            return
        _advance_step(step)
        st.rerun()


def main() -> None:
    set_page()
    apply_conference_styles()
    sidebar_debug_state()
    _ensure_local_state()

    repo = get_conference_repo()
    if not repo or not repo.is_ready():
        st.error(repo.unavailable_reason if repo else "Conference repository is unavailable.")
        return

    bundle = get_conference_bundle()
    session = bundle.get("session")
    if not session:
        st.error("Conference session is missing. Ensure `pisa-conference-session` exists in the shared sessions DB.")
        return

    _hydrate_existing_submission(repo, session["id"])
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

    if step == "welcome":
        _render_welcome(session)
    elif step == IDENTITY_STEP:
        _render_identity()
    elif step == "review":
        _render_review()
    elif step == "done":
        _render_done()
    else:
        _render_question_step(step)

    _render_navigation(repo, session)


if __name__ == "__main__":
    main()
