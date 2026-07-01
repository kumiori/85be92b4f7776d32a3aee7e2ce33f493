from __future__ import annotations

import csv
import io

import streamlit as st

from conference.context import get_conference_bundle, get_conference_repo
from conference.dalembertiennes import (
    export_rows,
    event_context,
    event_scope_text,
    render_event_selector,
    resolve_dalembertiennes_session,
)
from conference.events import text_ids_for_session_code
from conference.session_window import filter_rows_to_session_window
from conference.ui import apply_conference_styles, conference_header, summary_card
from ui import set_page, sidebar_debug_state


def _csv_payload(rows: list[dict[str, str]]) -> str:
    output = io.StringIO()
    writer = csv.DictWriter(
        output,
        fieldnames=["submitted_at", "access_key_last4", "placeholder_question"],
    )
    writer.writeheader()
    writer.writerows(rows)
    return output.getvalue()


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
        key="dalembertiennes-overview-event-selector",
        target_field="overview_page",
    )

    response_rows = repo.get_session_rows(
        str(session.get("id") or ""),
        text_ids=text_ids_for_session_code(str(session.get("session_code") or "")),
    )
    filtered_rows = filter_rows_to_session_window(response_rows, session)
    submissions = repo.group_rows_by_submission(filtered_rows)
    exportable_rows = export_rows(submissions)

    conference_header(
        f"{context['event_label']} overview",
        f"Responses stored only for {event_scope_text(session)}.",
        step="overview",
    )

    metrics = st.columns(3)
    metrics[0].metric("Submissions", len(submissions))
    metrics[1].metric(
        "Placeholder answers",
        len([row for row in submissions if str(row.get("open_question") or "").strip()]),
    )
    metrics[2].metric("Other events touched", 0)

    if exportable_rows:
        st.download_button(
            "Download Dalembertiennes CSV",
            data=_csv_payload(exportable_rows),
            file_name="dalembertiennes_placeholder_export.csv",
            mime="text/csv",
            type="primary",
            use_container_width=True,
        )
    else:
        st.caption("No Dalembertiennes submissions yet.")

    st.markdown("### Placeholder answers")
    if not submissions:
        summary_card(
            "Blank state",
            "No submissions yet. Answer the placeholder question once and it should appear here only.",
        )
        return

    for item in sorted(
        submissions,
        key=lambda row: str(row.get("submitted_at") or ""),
        reverse=True,
    ):
        answer = str(item.get("open_question") or "").strip()
        if not answer:
            continue
        summary_card(
            str(item.get("submitted_at") or "Stored answer"),
            answer,
        )


if __name__ == "__main__":
    main()
