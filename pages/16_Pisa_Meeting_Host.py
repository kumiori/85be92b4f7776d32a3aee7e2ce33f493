from __future__ import annotations

from collections import Counter
from datetime import datetime
from typing import Any, Dict, List

import pandas as pd
import streamlit as st

from conference.context import get_conference_bundle, get_conference_repo
from conference.models import field_option_label_map
from infra.app_context import get_authenticator, get_notion_repo
from infra.app_state import ensure_auth, ensure_session_state, remember_access, require_login
from infra.event_logger import list_logged_events
from ui import apply_admin_dark_mode, heading, microcopy, set_page, sidebar_debug_state


PAGE_KEY = "pisa-meeting"


def _format_timestamp(value: str) -> str:
    if not value:
        return ""
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00")).strftime("%Y-%m-%d %H:%M")
    except Exception:
        return value


def _labels_for(field: str, value: Any) -> str:
    label_map = field_option_label_map(field)
    if isinstance(value, list):
        return ", ".join(label_map.get(str(item), str(item)) for item in value if str(item)) or "None"
    if isinstance(value, str):
        return label_map.get(value, value) if value else "No answer"
    return str(value or "No answer")


def _counts(submissions: List[Dict[str, Any]], field: str) -> Counter:
    counter: Counter = Counter()
    for row in submissions:
        value = row.get(field)
        if isinstance(value, list):
            for item in value:
                if str(item):
                    counter[str(item)] += 1
        elif isinstance(value, str) and value:
            counter[value] += 1
    return counter


def main() -> None:
    set_page()
    apply_admin_dark_mode()
    ensure_session_state()
    sidebar_debug_state()

    shell_repo = get_notion_repo()
    authenticator = get_authenticator(shell_repo)
    ensure_auth(authenticator, callback=remember_access, key="pisa-host-login")
    require_login()

    repo = get_conference_repo()
    if not repo or not repo.is_ready():
        st.error(repo.unavailable_reason if repo else "Conference repository is unavailable.")
        return

    bundle = get_conference_bundle()
    session = bundle.get("session")
    if not session:
        st.error("Conference session is missing. Ensure the shared sessions DB contains `pisa-conference-session`.")
        return

    response_rows = repo.get_session_rows(session["id"])
    submissions = repo.group_rows_by_submission(response_rows)
    event_log = list_logged_events(page=PAGE_KEY, session_id=session["id"], limit=100)

    heading("Pisa session host")
    microcopy(
        f'{session.get("session_code", "pisa-conference-session")} · '
        "scientific identity, obstacles, and emerging collaboration signals"
    )

    metrics = st.columns(4)
    metrics[0].metric("Submissions", len(submissions))
    metrics[1].metric("Question rows", len(response_rows))
    metrics[2].metric("Event log entries", len(event_log))
    metrics[3].metric(
        "Follow-up signals",
        _counts(submissions, "continue_conversation").get("happy_to_engage", 0)
        + _counts(submissions, "continue_conversation").get("maybe_later", 0),
    )

    overview_fields = ["mode", "role", "systems", "expectations", "motivations", "obstacle", "challenge"]
    for field in overview_fields:
        counter = _counts(submissions, field)
        st.subheader(field.replace("_", " ").title())
        if counter:
            table_rows = [
                {"label": _labels_for(field, key), "count": value}
                for key, value in counter.most_common()
            ]
            df = pd.DataFrame(table_rows)
            if len(df) <= 6:
                st.table(df)
            else:
                st.bar_chart(df.set_index("label"))
        else:
            st.caption("No responses yet.")

    st.subheader("Latest submissions")
    if submissions:
        sorted_submissions = sorted(
            submissions,
            key=lambda item: str(item.get("submitted_at") or ""),
            reverse=True,
        )
        rows: List[Dict[str, Any]] = []
        for row in sorted_submissions[:20]:
            rows.append(
                {
                    "when": _format_timestamp(str(row.get("submitted_at", ""))),
                    "who": row.get("identity") or row.get("alias") or row.get("contact") or "Anonymous",
                    "role": _labels_for("role", row.get("role")),
                    "systems": _labels_for("systems", row.get("systems")),
                    "obstacle": _labels_for("obstacle", row.get("obstacle")),
                    "challenge": _labels_for("challenge", row.get("challenge")),
                    "continue": _labels_for("continue_conversation", row.get("continue_conversation")),
                    "mode": str(row.get("mode") or "").replace("_", " ").title(),
                    "key": row.get("access_key_last4", ""),
                }
            )
        st.dataframe(pd.DataFrame(rows), use_container_width=True, hide_index=True)
    else:
        st.caption("No submissions yet.")

    st.subheader("Event log summary")
    top_log_counts = Counter(row.get("event_type", "") for row in event_log if row.get("event_type"))
    if top_log_counts:
        st.table(pd.DataFrame([{"event_type": key, "count": value} for key, value in top_log_counts.most_common()]))
    else:
        st.caption("No event log activity yet.")

    st.subheader("Latest event log entries")
    if event_log:
        st.dataframe(
            pd.DataFrame(
                [
                    {
                        "when": _format_timestamp(str(item.get("timestamp", ""))),
                        "event_type": item.get("event_type", ""),
                        "step": str((item.get("metadata") or {}).get("step", "")),
                        "status": item.get("status", ""),
                    }
                    for item in event_log[:25]
                ]
            ),
            use_container_width=True,
            hide_index=True,
        )
    else:
        st.caption("No event log entries yet.")


if __name__ == "__main__":
    main()
