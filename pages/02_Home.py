from __future__ import annotations

import streamlit as st

from infra.app_context import get_authenticator, get_notion_repo
from infra.cryosphere_cracks import cryosphere_crack_points
from infra.app_state import (
    ensure_auth,
    ensure_session_context,
    ensure_session_state,
    remember_access,
    require_login,
)
from infra.event_logger import log_event
from ui import (
    apply_theme,
    heading,
    microcopy,
    set_page,
    sidebar_debug_state,
    display_centered_prompt,
    cracks_globe_block,
)


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
    cracks_globe_block(
        cryosphere_crack_points(),
        height=260,
        key="home-header-cracks",
        auto_rotate_speed=1.8,
    )

    st.write("Quick actions")
    if st.button(
        "Session 1 · Listening",
        type="primary",
        use_container_width=True,
    ):
        log_event(
            module="iceicebaby.sessions",
            event_type="session_switched",
            player_id=str(st.session_state.get("player_page_id", "")),
            session_id=str(st.session_state.get("session_id", "")),
            value_label="SESSION-1",
            metadata={"mode": "standard", "depth": 6},
        )
        st.query_params.clear()
        st.query_params.update(
            {"session": "SESSION-1", "mode": "standard", "depth": "6"}
        )
        st.switch_page("pages/30_audience_interaction_test.py")
    if st.button(
        "Session 1 · Extended mode",
        type="secondary",
        use_container_width=True,
    ):
        log_event(
            module="iceicebaby.sessions",
            event_type="session_switched",
            player_id=str(st.session_state.get("player_page_id", "")),
            session_id=str(st.session_state.get("session_id", "")),
            value_label="SESSION-1",
            metadata={"mode": "extended", "depth": 8},
        )
        st.query_params.clear()
        st.query_params.update(
            {"session": "SESSION-1", "mode": "extended", "depth": "8"}
        )
        st.switch_page("pages/30_audience_interaction_test.py")
    st.button("Session 2 (live Thu 19 March)", disabled=True, use_container_width=True)
    st.button("Session 3 (live Thu 19 March)", disabled=True, use_container_width=True)

    if st.button("Live map", use_container_width=True):
        st.switch_page("pages/08_Overview.py")

    st.button("Ask a scientist", disabled=True, use_container_width=True)
    if st.button("Coordination board", use_container_width=True):
        st.switch_page("pages/06_Coordination.py")
    if st.session_state.get("authentication_status"):
        authenticator.logout(button_name="Logout", location="sidebar")
    if repo and st.session_state.get("session_id"):
        questions = repo.list_questions(
            st.session_state["session_id"], status="approved"
        )
        st.caption(f"Posted questions: {len(questions)}")


if __name__ == "__main__":
    main()
