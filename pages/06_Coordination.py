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

HELP_OPTIONS = [
    "comms",
    "sound",
    "development",
    "speaker outreach",
    "design",
    "funding",
    "logistics",
    "social media",
]


def main() -> None:
    set_page()
    apply_theme()
    ensure_session_state()
    repo = get_notion_repo()
    authenticator = get_authenticator(repo)
    ensure_auth(authenticator, callback=remember_access, key="coord-login")
    ensure_session_context(repo)
    require_login()
    sidebar_debug_state()

    if st.session_state.get("authentication_status"):
        authenticator.logout(button_name="Logout", location="sidebar")
    session_id = st.session_state.get("session_id")
    player_page_id = st.session_state.get("player_page_id")

    heading("Coordination Board")
    microcopy("Offer help and share availability.")

    if not repo or not session_id or not player_page_id:
        st.error("Missing session or player context.")
        return

    with st.form("coordination-form"):
        st.markdown("**I can help with…**")
        help_with = st.multiselect("Pick all that apply", HELP_OPTIONS)
        hours = st.slider("Dedicate hours this week", 0, 20, 2)
        availability = st.text_input("Availability window (optional)")
        submitted = st.form_submit_button("Submit availability")

    if submitted:
        payload = {
            "help_with": help_with,
            "hours": hours,
            "availability": availability,
        }
        repo.create_decision(
            session_id=session_id,
            player_id=player_page_id,
            decision_type="coordination",
            payload=json.dumps(payload),
        )
        st.success("Thanks, your input is saved.")


if __name__ == "__main__":
    main()
