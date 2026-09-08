from __future__ import annotations

import streamlit as st

from conference.context import get_conference_bundle, get_conference_repo
from conference.events import event_config_for_request, text_ids_for_session_code
from conference.ui import apply_conference_styles, conference_header
from ui import set_page


def main() -> None:
    set_page()
    apply_conference_styles()
    slug = str(st.query_params.get("event") or "prediction").strip().lower()
    config = event_config_for_request(slug, test=st.query_params.get("test", ""))
    if not config:
        st.error("Unknown event.")
        return
    repo = get_conference_repo()
    bundle = get_conference_bundle(session_code=config.session_code)
    session = bundle.get("session") if isinstance(bundle, dict) else None
    if not repo or not session:
        st.error("Event session is not available.")
        return
    rows = repo.get_session_rows(
        str(session.get("id") or ""),
        text_ids=text_ids_for_session_code(config.session_code),
    )
    submissions = repo.group_rows_by_submission(rows)
    conference_header(config.title, config.subtitle, step="results")
    st.metric("Submitted contributions", len(submissions))
    st.caption(f"{config.place} · {config.dates}")
    if config.test_mode:
        st.caption("TEST MODE · isolated from production results")


if __name__ == "__main__":
    main()
