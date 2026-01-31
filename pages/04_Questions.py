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

DOMAINS = ["organisation", "science", "society", "policy", "technology", "other"]


def _is_admin(role: str) -> bool:
    return role.lower() in {"admin", "owner", "moderator"}


def main() -> None:
    set_page()
    apply_theme()
    ensure_session_state()
    repo = get_notion_repo()
    authenticator = get_authenticator(repo)
    ensure_auth(authenticator, callback=remember_access, key="questions-login")
    ensure_session_context(repo)
    require_login()
    sidebar_debug_state()

    if st.session_state.get("authentication_status"):
        authenticator.logout(button_name="Logout", location="sidebar")
    session_id = st.session_state.get("session_id")
    player_page_id = st.session_state.get("player_page_id")
    role = st.session_state.get("player_role", "Contributor")

    heading("Question Harvest")
    microcopy("Submit a bite-sized question for the session.")

    if not repo or not session_id or not player_page_id:
        st.error("Missing session or player context.")
        return

    with st.form("question-form"):
        question = st.text_area("Question", max_chars=240)
        domain = st.selectbox("Domain", DOMAINS)
        submitted = st.form_submit_button("Submit question")
    if submitted and question:
        repo.create_question(
            session_id=session_id,
            text=question,
            domain=domain,
            submitted_by=player_page_id,
        )
        st.success("Thanks, your input is saved.")

    st.subheader("Approved questions")
    approved = repo.list_questions(session_id, status="approved")
    if not approved:
        st.caption("No approved questions yet.")
    for q in approved:
        cols = st.columns([5, 1])
        cols[0].write(f"{q['text']}  \nDomain: {q['domain']}")
        if cols[1].button("Upvote", key=f"upvote-{q['id']}"):
            repo.increment_question_upvote(q["id"])
            st.toast("Upvoted.")

    if _is_admin(role):
        st.subheader("Moderation queue")
        pending = repo.list_questions(session_id, status="pending")
        if not pending:
            st.caption("No pending questions.")
        for q in pending:
            st.write(f"**{q['text']}**  \nDomain: {q['domain']}")
            vote = st.selectbox(
                "Vote",
                ["approve", "park", "rewrite"],
                key=f"vote-{q['id']}",
            )
            if st.button("Submit vote", key=f"vote-btn-{q['id']}"):
                repo.create_moderation_vote(
                    session_id=session_id,
                    question_id=q["id"],
                    voter_id=player_page_id,
                    vote=vote,
                )
                st.success("Vote recorded.")


if __name__ == "__main__":
    main()
