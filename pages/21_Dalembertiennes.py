from __future__ import annotations

import hashlib

import streamlit as st

from conference.context import get_conference_bundle, get_conference_repo
from conference.dalembertiennes import (
    PLACEHOLDER_HINT,
    PLACEHOLDER_PROMPT,
    build_placeholder_payload,
    ensure_access_key,
    ensure_state,
    event_context,
    event_scope_text,
    get_state,
    render_event_selector,
    reset_state,
    resolve_dalembertiennes_session,
    update_state,
)
from conference.repo import emoji_suffix
from conference.ui import apply_conference_styles, conference_header, summary_card
from infra.key_codec import hex_to_emoji, split_emoji_symbols
from ui import set_page, sidebar_debug_state


STATE_KEY = "dalembertiennes_placeholder_state"


def _render_scope_notice(session: dict) -> None:
    st.caption(
        f"This response belongs to {event_scope_text(session)}. "
        "It is a checkpoint write for Dalembertiennes only."
    )


def _submit(repo, session: dict) -> None:
    state = get_state(STATE_KEY)
    answer = str(state.get("answer") or "").strip()
    if not answer:
        st.warning("Enter one placeholder answer before integrating it.")
        return
    context = event_context(session)
    if not bool(context.get("write_enabled")):
        st.error(
            f"{context['event_label']} is currently {context['event_status']}. "
            "New responses are closed."
        )
        return
    payload = build_placeholder_payload(session, answer)
    access_key = ensure_access_key(STATE_KEY)
    access_key_hash = repo.access_key_hash(access_key)
    access_key_last4 = emoji_suffix(access_key)
    player = repo.upsert_conference_player(
        session_id=str(session.get("id") or ""),
        access_key=access_key,
        payload=payload,
        identity_metadata={
            "alias": "",
            "identity": "",
            "contact": "",
            "notes": "",
            "contact_label": "dalembertiennes-placeholder",
            "anonymous_first": True,
        },
    )
    repo.save_session_response_set(
        session_id=str(session.get("id") or ""),
        player_id=str((player or {}).get("id") or ""),
        text_id=str(context["text_id"]),
        device_id="dalembertiennes-placeholder",
        access_key_hash=access_key_hash,
        access_key_last4=access_key_last4,
        payload=payload,
        identity_metadata={
            "alias": "",
            "identity": "",
            "contact": "",
            "notes": "",
            "contact_label": "dalembertiennes-placeholder",
            "anonymous_first": True,
        },
    )
    update_state(STATE_KEY, submitted=True, access_key=access_key)
    st.rerun()


def _render_done(session: dict) -> None:
    state = get_state(STATE_KEY)
    access_key = str(state.get("access_key") or "").strip()
    emoji_key = hex_to_emoji(access_key) if access_key else ""
    access_key_hash = (
        hashlib.sha256(access_key.encode("utf-8")).hexdigest() if access_key else ""
    )
    st.success(f"Stored only in {event_scope_text(session)}.")
    summary_card("Placeholder answer", str(state.get("answer") or ""))
    summary_card(
        "Short key",
        "".join(split_emoji_symbols(emoji_key)[-4:]) if emoji_key else "Unavailable",
    )
    summary_card(
        "Hash prefix",
        access_key_hash[:12] if access_key_hash else "Unavailable",
    )
    if st.button(
        f"Open the {event_context(session)['event_label']} overview",
        type="primary",
        use_container_width=True,
    ):
        st.switch_page(str(event_context(session)["overview_page"]))
    if st.button("Start from a blank state", use_container_width=True):
        reset_state(STATE_KEY)
        st.rerun()


def main() -> None:
    set_page()
    apply_conference_styles()
    sidebar_debug_state()
    ensure_state(STATE_KEY)

    repo = get_conference_repo()
    if not repo or not repo.is_ready():
        st.error(repo.unavailable_reason if repo else "Conference repository is unavailable.")
        return

    session = resolve_dalembertiennes_session(repo, get_conference_bundle)
    if not session:
        st.error(
            "Dalembertiennes session is missing. "
            "Run `scripts/bootstrap_dalembertiennes_session.py` first."
        )
        return

    context = event_context(session)
    render_event_selector(
        repo,
        session,
        key="dalembertiennes-event-selector",
        target_field="questionnaire_page",
    )

    if get_state(STATE_KEY).get("submitted"):
        conference_header(context["event_label"], "", step="complete")
        _render_done(session)
        return

    conference_header(
        context["event_label"],
        "A clean placeholder checkpoint for isolating Dalembertiennes responses.",
        step="1 / 1",
    )
    _render_scope_notice(session)
    summary_card("Checkpoint", PLACEHOLDER_HINT)

    answer = st.text_area(
        PLACEHOLDER_PROMPT,
        value=str(get_state(STATE_KEY).get("answer") or ""),
        key="dalembertiennes-placeholder-answer",
        placeholder="Example: What should the laboratory ask first?",
        height=180,
    )
    update_state(STATE_KEY, answer=answer)

    if not bool(context.get("write_enabled")):
        st.warning(
            f"{context['event_label']} is currently {context['event_status']}. "
            "Overview remains visible, but new responses are closed."
        )
    if st.button(
        "Integrate placeholder answer",
        type="primary",
        use_container_width=True,
        disabled=not bool(context.get("write_enabled")),
    ):
        _submit(repo, session)


if __name__ == "__main__":
    main()
