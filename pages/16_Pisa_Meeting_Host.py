from __future__ import annotations

from collections import Counter
from datetime import datetime
from typing import Any, Dict, List

import pandas as pd
import streamlit as st

from conference.context import get_conference_bundle, get_conference_repo
from conference.models import FINGERPRINT_LABELS, field_option_label_map
from conference.topology import count_field, room_snapshot
from infra.app_context import get_authenticator, get_notion_repo
from infra.app_state import ensure_auth, ensure_session_state, remember_access, require_login
from infra.event_logger import list_logged_events
from ui import apply_admin_dark_mode, heading, microcopy, set_page, sidebar_debug_state


PAGE_KEY = "complexity"


def _format_timestamp(value: str) -> str:
    if not value:
        return ""
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00")).strftime("%Y-%m-%d %H:%M")
    except Exception:
        return value


def _labels_for(field: str, value: Any) -> str:
    label_map = field_option_label_map(field)
    if field == "complexity_fingerprint" and isinstance(value, dict):
        return " · ".join(
            f"{FINGERPRINT_LABELS.get(axis, axis.title())} {int(value.get(axis, 0) or 0)}"
            for axis in FINGERPRINT_LABELS
        )
    if isinstance(value, list):
        return ", ".join(label_map.get(str(item), str(item)) for item in value if str(item)) or "None"
    if isinstance(value, str):
        return label_map.get(value, value) if value else "No answer"
    return str(value or "No answer")


def _historical_session_counts(repo: Any, current_session_id: str) -> List[Dict[str, Any]]:
    sessions = [
        {
            "code": "pisa-conference-session",
            "label": "Pisa",
            "question": "Who are you?",
        },
        {
            "code": "global-session",
            "label": "UNESCO",
            "question": "What resonates?",
        },
    ]
    rows: List[Dict[str, Any]] = []
    for item in sessions:
        session = repo.resolve_session(session_code=item["code"])
        if not session:
            continue
        if str(session.get("id") or "") == str(current_session_id or ""):
            continue
        submissions = repo.group_rows_by_submission(repo.get_session_rows(session["id"]))
        rows.append(
            {
                "label": item["label"],
                "question": item["question"],
                "participants": len(submissions),
            }
        )
    return rows


def main() -> None:
    set_page()
    apply_admin_dark_mode()
    ensure_session_state()
    sidebar_debug_state()

    shell_repo = get_notion_repo()
    authenticator = get_authenticator(shell_repo)
    ensure_auth(authenticator, callback=remember_access, key="complexity-host-login")
    require_login()

    repo = get_conference_repo()
    if not repo or not repo.is_ready():
        st.error(repo.unavailable_reason if repo else "Conference repository is unavailable.")
        return

    bundle = get_conference_bundle(prefer_active=True)
    session = bundle.get("session")
    if not session:
        st.error("Conference session is missing. Ensure the shared sessions DB contains `pisa-conference-session`.")
        return

    response_rows = repo.get_session_rows(session["id"])
    submissions = repo.group_rows_by_submission(response_rows)
    snapshot = room_snapshot(submissions)
    event_log = list_logged_events(page=PAGE_KEY, session_id=session["id"], limit=100)

    heading("Complexity host")
    microcopy(
        f'{session.get("session_code", "pisa-conference-session")} · '
        "persistent profiles, session questions, neighbours, and room-level signals"
    )

    metrics = st.columns(4)
    metrics[0].metric("Submissions", len(submissions))
    metrics[1].metric("Countries", int(snapshot["countries"]))
    metrics[2].metric("Event log entries", len(event_log))
    metrics[3].metric("Follow-up signals", int(snapshot["follow_up"].get("yes", 0)) + int(snapshot["follow_up"].get("maybe", 0)))

    historical = _historical_session_counts(repo, str(session.get("id") or ""))
    if historical:
        st.subheader("Other sessions")
        st.table(
            pd.DataFrame(
                [
                    {
                        "session": item["label"],
                        "participants": int(item["participants"]),
                        "question": item["question"],
                    }
                    for item in historical
                ]
            )
        )

    overview_fields = ["role", "assets", "motivations", "obstacle", "challenge", "follow_up_interest"]
    for field in overview_fields:
        counter = count_field(submissions, field)
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
                    "assets": _labels_for("assets", row.get("assets")),
                    "obstacle": _labels_for("obstacle", row.get("obstacle")),
                    "challenge": _labels_for("challenge", row.get("challenge")),
                    "follow_up": _labels_for("follow_up_interest", row.get("follow_up_interest")),
                    "mode": str(row.get("mode") or "").replace("_", " ").title(),
                    "key": row.get("access_key_last4", ""),
                }
            )
        st.dataframe(pd.DataFrame(rows), use_container_width=True, hide_index=True)
    else:
        st.caption("No submissions yet.")

    st.subheader("Open questions")
    open_questions = [
        {
            "when": _format_timestamp(str(row.get("submitted_at", ""))),
            "question": str(row.get("open_question") or "").strip(),
        }
        for row in submissions
        if str(row.get("open_question") or "").strip()
    ]
    if open_questions:
        st.dataframe(pd.DataFrame(open_questions[:20]), use_container_width=True, hide_index=True)
    else:
        st.caption("No open questions yet.")

    st.subheader("Event log summary")
    top_log_counts = Counter(row.get("event_type", "") for row in event_log if row.get("event_type"))
    if top_log_counts:
        st.table(pd.DataFrame([{"event_type": key, "count": value} for key, value in top_log_counts.most_common()]))
    else:
        st.caption("No event log activity yet.")


if __name__ == "__main__":
    main()
