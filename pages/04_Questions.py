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
from infra.event_logger import log_event
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
    role = st.session_state.get("player_role", "None")

    heading("Question Harvest")
    microcopy(
        "Submit a bite-sized question for the session. Admins can list items in the queue."
    )

    if not repo or not session_id or not player_page_id:
        st.error("Missing session or player context.")
        return

    with st.form("question-form"):
        question = st.text_area("Question", max_chars=240)
        domains = st.pills("Domain", DOMAINS, selection_mode="multi")
        submitted = st.form_submit_button("Submit question")
    if submitted and question:
        if isinstance(domains, str):
            domains = [domains]
        domain_value = domains or "other"
        repo.create_question(
            session_id=session_id,
            text=question,
            domain=domain_value,
            submitted_by=player_page_id,
        )
        log_event(
            module="iceicebaby.responses",
            event_type="question_submit",
            player_id=str(player_page_id),
            session_id=str(session_id),
            value_label=str(question[:80]),
            metadata={"domain": domain_value},
        )
        st.success("Thanks, your input is saved.")

    st.subheader("Listed questions")
    listed = repo.list_listed_questions(session_id)
    if not listed:
        st.caption("No questions yet.")
    for q in listed:
        cols = st.columns([5, 1])
        cols[0].write(f"{q['text']}  \nDomain: {q['domain']}")
        if cols[1].button("Responded", key=f"responded-{q['id']}"):
            repo.update_question_status(q["id"], "responded")
            st.toast("Marked responded.")

    if _is_admin(role):
        st.subheader("Queue")
        pending = repo.list_questions(session_id, status="pending")
        if not pending:
            st.caption("No items in the queue.")
        for q in pending:
            st.write(f"**{q['text']}**  \nDomain: {q['domain']}")
            vote = st.selectbox(
                "Action",
                ["respond", "reword", "park"],
                key=f"vote-{q['id']}",
            )
            if st.button("Submit action", key=f"vote-btn-{q['id']}"):
                status_map = {
                    "respond": "responded",
                    "reword": "rewritten",
                    "park": "parked",
                }
                vote_map = {"respond": "approve", "reword": "rewrite", "park": "park"}
                repo.create_moderation_vote(
                    session_id=session_id,
                    question_id=q["id"],
                    voter_id=player_page_id,
                    vote=vote_map[vote],
                )
                repo.update_question_status(q["id"], status_map[vote])
                st.success("Action recorded.")


if __name__ == "__main__":
    main()
