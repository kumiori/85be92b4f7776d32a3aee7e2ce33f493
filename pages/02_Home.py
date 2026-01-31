from __future__ import annotations

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
    ensure_auth(authenticator, callback=remember_access, key="home-login")
    ensure_session_context(repo)
    require_login()
    sidebar_debug_state()

    heading("Session Lobby")
    session_title = st.session_state.get("session_title") or "Active session"
    microcopy(session_title)

    st.write("Quick actions")
    st.button("Ask a scientist", disabled=True, use_container_width=True)
    if st.button("Decision experiment", use_container_width=True):
        st.switch_page("pages/05_Decisions.py")
    if st.button("Coordination board", use_container_width=True):
        st.switch_page("pages/06_Coordination.py")
    if st.button("Live map", use_container_width=True):
        st.switch_page("pages/03_Resonance.py")

    if st.session_state.get("authentication_status"):
        authenticator.logout(button_name="Logout", location="sidebar")
    if repo and st.session_state.get("session_id"):
        questions = repo.list_questions(
            st.session_state["session_id"], status="approved"
        )
        st.caption(f"Approved questions: {len(questions)}")


if __name__ == "__main__":
    main()
