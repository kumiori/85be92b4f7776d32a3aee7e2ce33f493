from __future__ import annotations

from collections import defaultdict

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

LEVEL_LABELS = {
    -3: "Strong no",
    -2: "No",
    -1: "Leaning no",
    0: "Neutral",
    1: "Leaning yes",
    2: "Yes",
    3: "Strong yes",
}


def main() -> None:
    set_page()
    apply_theme()
    ensure_session_state()
    repo = get_notion_repo()
    authenticator = get_authenticator(repo)
    ensure_auth(authenticator, callback=remember_access, key="resonance-login")
    ensure_session_context(repo)
    require_login()
    sidebar_debug_state()

    if st.session_state.get("authentication_status"):
        authenticator.logout(button_name="Logout", location="sidebar")
    session_id = st.session_state.get("session_id")
    player_page_id = st.session_state.get("player_page_id")

    heading("Resonance Probe")
    microcopy("Respond to the statements below.")

    if not repo or not session_id or not player_page_id:
        st.error("Missing session or player context.")
        return

    statements = repo.list_statements(session_id)
    if not statements:
        st.info("No active statements yet.")
        return

    with st.form("resonance-form"):
        responses = {}
        for statement in statements:
            st.markdown(f"**{statement['text']}**")
            value = st.slider(
                "Resonance",
                min_value=-3,
                max_value=3,
                value=0,
                step=1,
                key=f"res-{statement['id']}",
            )
            responses[statement["id"]] = value
        note = st.text_area("Optional note")
        submitted = st.form_submit_button("Submit responses")

    if submitted:
        for statement_id, value in responses.items():
            repo.create_response(
                session_id=session_id,
                statement_id=statement_id,
                player_id=player_page_id,
                value=value,
                level_label=LEVEL_LABELS.get(value, ""),
                note=note,
            )
        st.session_state["resonance_submitted"] = True
        st.success("Thanks, your input is saved.")

    if st.session_state.get("resonance_submitted"):
        statement_ids = [s["id"] for s in statements]
        all_responses = repo.list_responses(session_id, statement_ids)
        totals = defaultdict(list)
        for response in all_responses:
            sid = (response.get("statement_id") or [None])[0]
            if sid:
                totals[sid].append(response.get("value", 0))
        chart_data = {
            s["text"]: (
                sum(totals.get(s["id"], [])) / len(totals.get(s["id"], []) or [1])
            )
            for s in statements
        }
        st.subheader("Aggregate resonance")
        st.bar_chart(chart_data)


if __name__ == "__main__":
    main()
