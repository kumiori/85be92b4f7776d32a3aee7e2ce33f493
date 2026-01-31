from __future__ import annotations

import json

import streamlit as st

from infra.app_context import get_authenticator, get_notion_repo
from infra.app_state import (
    ensure_auth,
    ensure_session_context,
    ensure_session_state,
    remember_access,
    require_login,
)
from ui import apply_theme, heading, microcopy, set_page, sidebar_debug_state


def main() -> None:
    set_page()
    apply_theme()
    ensure_session_state()
    repo = get_notion_repo()
    authenticator = get_authenticator(repo)
    ensure_auth(authenticator, callback=remember_access, key="decisions-login")
    ensure_session_context(repo)
    require_login()
    sidebar_debug_state()

    if st.session_state.get("authentication_status"):
        authenticator.logout(button_name="Logout", location="sidebar")
    session_id = st.session_state.get("session_id")
    player_page_id = st.session_state.get("player_page_id")

    heading("Decision Tool")
    microcopy("Two quick micro-decisions.")

    if not repo or not session_id or not player_page_id:
        st.error("Missing session or player context.")
        return

    with st.form("decision-form"):
        st.markdown("**Application filling status**")
        status = st.radio(
            "Status", ["final", "minor edits", "major rework"], horizontal=True
        )
        changes = st.text_area("Suggested changes", max_chars=240)

        st.markdown("**Journey A → B**")
        a_val = st.text_input("A (initial)")
        b_val = st.text_input("B (final)")

        submitted = st.form_submit_button("Submit decisions")

    if submitted:
        payload = {
            "application_status": status,
            "suggested_changes": changes,
            "journey": {"A": a_val, "B": b_val},
        }
        repo.create_decision(
            session_id=session_id,
            player_id=player_page_id,
            decision_type="micro_decision",
            payload=json.dumps(payload),
        )
        st.success("Thanks, your input is saved.")


if __name__ == "__main__":
    main()
