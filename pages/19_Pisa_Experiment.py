from __future__ import annotations

import hashlib
import uuid
from typing import Any, Dict

import streamlit as st
import streamlit.components.v1 as components

from conference.context import get_conference_bundle, get_conference_repo
from conference.events import YOUNG_TEXT_ID, conference_event_context
from conference.pisa_legacy_flow import (
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
from conference.pisa_legacy_models import STEP_COPY, field_option_label_map, mode_card_rows, question_by_step
from conference.question_flags import (
    QUESTION_FLAG_LABELS,
    QUESTION_FLAG_OPTIONS,
    normalize_question_flags,
)
from conference.repo import emoji_suffix, resolve_access_key_input
from conference.ui import apply_conference_styles, conference_header, summary_card
from infra.key_codec import generate_hex_key, hex_to_emoji, split_emoji_symbols
from ui import set_page, sidebar_debug_state


PAGE_KEY = "pisa-meeting-legacy"
TEXT_ID = YOUNG_TEXT_ID
IDENTITY_STEP = "identity"


def _ensure_local_state() -> None:
    init_flow_state()
    st.session_state.setdefault("legacy_pisa_device_id", uuid.uuid4().hex[:16])


def _infer_mode(submission: Dict[str, Any]) -> str:
    if submission.get("career_stage") or submission.get("research_style") or submission.get("timescale"):
        return "deep"
    if submission.get("formulation") or submission.get("reality_check") or submission.get("scale"):
        return "standard"
    return "quick"


def _question_prompt_by_id(question_id: str) -> str:
    for step in active_question_steps(get_draft()):
        question = question_by_step(step)
        if question and str(question.get("question_id") or "") == question_id:
            return str(question.get("prompt") or question_id)
    return question_id


def _question_flag_entries() -> Dict[str, Dict[str, Any]]:
    return normalize_question_flags(get_draft().get("question_flags"))


def _set_question_flag(question_id: str, *, flags: list[str], note: str) -> None:
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
        st.caption("Mark if the question feels incomplete, misleading, narrow, or otherwise off.")
        selected = st.pills(
            "Question issue",
            [str(item["value"]) for item in QUESTION_FLAG_OPTIONS],
            default=flags,
            selection_mode="multi",
            format_func=lambda value: QUESTION_FLAG_LABELS.get(value, value),
            key=f"legacy_pisa_flag_{question_id}",
            label_visibility="collapsed",
        )
        comment = st.text_input(
            "Optional note",
            value=note,
            key=f"legacy_pisa_flag_note_{question_id}",
            placeholder="Optional short note",
            label_visibility="collapsed",
        )
        _set_question_flag(question_id, flags=list(selected), note=comment)


def _render_question_flag_summary() -> None:
    entries = _question_flag_entries()
    if not entries:
        return
    lines: list[str] = []
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


def _hydrate_existing_submission(repo: Any, session_id: str) -> None:
    if st.session_state.get("legacy_pisa_hydrated"):
        return
    draft = get_draft()
    raw_key = str(draft.get("access_key") or st.query_params.get("key", "") or "").strip()
    if not raw_key:
        st.session_state["legacy_pisa_hydrated"] = True
        return
    access_key, _ = resolve_access_key_input(getattr(repo, "notion_repo", None), raw_key)
    if not access_key:
        st.session_state["legacy_pisa_hydrated"] = True
        return
    access_key_hash = repo.access_key_hash(access_key)
    cache_key = f"{session_id}:{access_key_hash}"
    submission = st.session_state.get("legacy_pisa_submission_cache")
    if st.session_state.get("legacy_pisa_submission_cache_key") != cache_key:
        submission = repo.latest_submission_by_access_key_hash(
            session_id=session_id,
            access_key_hash=access_key_hash,
            text_ids=[YOUNG_TEXT_ID],
        )
        st.session_state["legacy_pisa_submission_cache_key"] = cache_key
        st.session_state["legacy_pisa_submission_cache"] = submission
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
    st.session_state["legacy_pisa_hydrated"] = True


def _advance_step() -> None:
    next_step()


def _labels_for(field: str, value: Any) -> str:
    label_map = field_option_label_map(field)
    if isinstance(value, list):
        labels = [label_map.get(str(item), str(item)) for item in value]
        return ", ".join(labels) if labels else "None selected"
    if isinstance(value, str):
        return label_map.get(value, value) if value else "No answer"
    return str(value or "No answer")


def _ensure_access_key() -> str:
    access_key = str(get_draft().get("access_key") or "").strip()
    if access_key:
        return access_key
    access_key = generate_hex_key()
    update_draft(access_key=access_key)
    return access_key


def _payload_for_session(session: Dict[str, Any]) -> Dict[str, Any]:
    payload = build_session_payload(get_draft())
    context = conference_event_context(session=session)
    payload["event_slug"] = str(context.get("event_slug") or "pisa")
    payload["event_code"] = str(context.get("event_code") or session.get("session_code") or "")
    payload["event_label"] = str(
        context.get("event_label")
        or session.get("session_title")
        or session.get("session_name")
        or "Pisa"
    )
    payload["event_status"] = str(context.get("event_status") or "")
    payload["session_code"] = str(session.get("session_code") or "")
    payload["session_id"] = str(session.get("id") or "")
    payload["text_id"] = TEXT_ID
    payload["schema_id"] = TEXT_ID
    payload["question_set_id"] = TEXT_ID
    payload["response_scope"] = "event_specific"
    return payload


def _submit(repo: Any, session: Dict[str, Any]) -> None:
    payload = _payload_for_session(session)
    access_key = _ensure_access_key()
    access_key_hash = repo.access_key_hash(access_key)
    access_key_last4 = emoji_suffix(access_key)
    repo.save_session_response_set(
        session_id=session["id"],
        player_id=None,
        text_id=TEXT_ID,
        device_id=str(st.session_state.get("legacy_pisa_device_id", "")),
        access_key_hash=access_key_hash,
        access_key_last4=access_key_last4,
        payload=payload,
    )
    st.session_state["legacy_pisa_submission_cache_key"] = f"{session['id']}:{access_key_hash}"
    st.session_state["legacy_pisa_submission_cache"] = payload | {
        "access_key_hash": access_key_hash,
        "access_key_last4": access_key_last4,
    }
    update_draft(access_key=access_key)
    mark_submitted()


def _open_confirm_send_dialog(repo: Any, session: Dict[str, Any]) -> None:
    @st.dialog("Save this key")
    def _confirm_send_dialog() -> None:
        access_key = _ensure_access_key()
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
            "### All this interaction is anonymous. This access key will give you access to your answers and what will follow. Store it safely."
        )
        if st.button("Screenshot taken", type="primary", use_container_width=True):
            _submit(repo, session)
            st.rerun()

    _confirm_send_dialog()


def _select_mode(mode: str) -> None:
    update_draft(mode=mode)
    set_step(first_active_question_step())
    st.rerun()


def _render_welcome() -> None:
    row = next(
        (
            item
            for item in mode_card_rows()
            if str(item.get("value") or "") == "quick"
        ),
        {"value": "quick", "title": "Quick pulse", "detail": "~ 3 minutes", "accent": "🧊"},
    )
    st.markdown("### Let's have a quick temperature check.")
    st.caption("We will start with the quick pulse. You can extend it later.")
    button_label = f"{row['accent']} {row['title']}\n{row['detail']}"
    if st.button(
        button_label,
        type="primary",
        use_container_width=True,
        key="legacy_pisa_mode_quick",
    ):
        _select_mode("quick")
    summary_card("Anonymous first", STEP_COPY["welcome"]["note"])


def _render_question_step(step: str) -> None:
    question = question_by_step(step)
    if not question:
        return
    _render_question_flag_control(question)
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
            key=f"legacy_pisa_widget_{field}",
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
            key=f"legacy_pisa_widget_{field}",
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
        key="legacy_pisa_widget_alias",
        placeholder="Optional public alias",
    )
    identity = st.text_input(
        "Identity",
        value=str(draft.get("identity") or ""),
        key="legacy_pisa_widget_identity",
        placeholder="Optional name or affiliation",
    )
    contact = ""
    if should_collect_contact(draft):
        contact = st.text_input(
            "Contact",
            value=str(draft.get("contact") or ""),
            key="legacy_pisa_widget_contact",
            placeholder="Optional email, website, or contact cue",
        )
    update_draft(alias=alias, identity=identity, contact=contact, notes="")


def _render_review() -> None:
    payload = build_session_payload(get_draft())
    summary_card("Format", str(payload.get("mode") or "quick").replace("_", " ").title())
    for step in active_question_steps(get_draft()):
        model = question_by_step(step)
        if not model:
            continue
        field = str(model["field"])
        summary_card(model["prompt"], _labels_for(field, payload.get(field)))
    _render_question_flag_summary()
    identity_parts = [
        str(payload.get("alias") or "").strip(),
        str(payload.get("identity") or "").strip(),
        str(payload.get("contact") or "").strip(),
    ]
    identity_text = " · ".join(part for part in identity_parts if part) or "Remain anonymous"
    summary_card("Alias or identity", identity_text)


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
        _advance_step()
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

    bundle = get_conference_bundle(session_code="pisa-conference-session")
    session = bundle.get("session")
    if not session:
        st.error("Conference session is missing. Ensure `pisa-conference-session` exists in the shared sessions DB.")
        return

    conference_header("Young experiment", "", step="paused")
    st.warning(
        "Known bug: the historical Young/Pisa experiment is paused while we repair the event mapping."
    )
    st.caption(
        "Please do not add new entries here for now. "
        "Use the current Complexity page instead."
    )
    st.stop()


if __name__ == "__main__":
    main()
