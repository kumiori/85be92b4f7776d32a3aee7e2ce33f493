from __future__ import annotations

import pandas as pd
import streamlit as st

from conference.context import get_conference_bundle, get_conference_repo
from conference.dalembertiennes import (
    event_context,
    event_scope_text,
    export_rows,
    render_event_selector,
    resolve_dalembertiennes_session,
)
from conference.events import text_ids_for_session_code
from conference.session_window import filter_rows_to_session_window
from conference.ui import apply_conference_styles, conference_header
from infra.event_logger import list_logged_events
from ui import set_page, sidebar_debug_state


def main() -> None:
    set_page()
    apply_conference_styles()
    sidebar_debug_state()

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
        key="dalembertiennes-host-event-selector",
        target_field="host_page",
    )

    response_rows = repo.get_session_rows(
        str(session.get("id") or ""),
        text_ids=text_ids_for_session_code(str(session.get("session_code") or "")),
    )
    filtered_rows = filter_rows_to_session_window(response_rows, session)
    submissions = repo.group_rows_by_submission(filtered_rows)
    event_log = list_logged_events(
        page="conference",
        session_id=str(session.get("id") or ""),
        limit=100,
    )

    conference_header(
        f"{context['event_label']} host",
        f"Operator view for {event_scope_text(session)}.",
        step="host",
    )

    metrics = st.columns(3)
    metrics[0].metric("Submissions", len(submissions))
    metrics[1].metric("Filtered rows", len(filtered_rows))
    metrics[2].metric("Event log entries", len(event_log))

    rows = export_rows(submissions)
    if rows:
        st.dataframe(pd.DataFrame(rows), use_container_width=True)
    else:
        st.info("No Dalembertiennes submissions yet.")

    if event_log:
        st.markdown("### Recent event log")
        st.dataframe(pd.DataFrame(event_log), use_container_width=True)


if __name__ == "__main__":
    main()
