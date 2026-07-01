from __future__ import annotations

from collections import Counter
from datetime import datetime
from typing import Any, Dict, List

import pandas as pd
import streamlit as st

from conference.context import get_conference_bundle, get_conference_repo
from conference.events import (
    UNESCO_SESSION_CODE,
    YOUNG_SESSION_CODE,
    conference_event_context,
    conference_event_options,
    current_complexity_session_code,
    text_ids_for_session_code,
)
from conference.models import FINGERPRINT_LABELS, field_option_label_map
from conference.repo import ANONYMOUS_COMPLEXITY_NAME
from conference.session_window import filter_rows_to_session_window
from conference.topology import count_field, room_snapshot
from infra.app_context import get_authenticator, get_notion_repo
from infra.app_state import ensure_auth, ensure_session_state, remember_access, require_login
from infra.event_logger import list_logged_events
from ui import apply_admin_dark_mode, heading, microcopy, set_page, sidebar_debug_state


PAGE_KEY = "complexity"


def _event_context(session: Dict[str, Any]) -> Dict[str, Any]:
    return conference_event_context(session=session)


def _event_scope_text(session: Dict[str, Any]) -> str:
    context = _event_context(session)
    location = str(context.get("event_location") or "").strip()
    if location:
        return f"{context['event_label']} in {location}"
    return str(context.get("event_label") or context.get("event_code") or "this event")


def _sync_event_query(event_slug: str) -> None:
    st.query_params.clear()
    st.query_params.update({"event": str(event_slug or "").strip()})


def _render_event_selector(repo: Any, session: Dict[str, Any]) -> None:
    options = conference_event_options(repo)
    if len(options) <= 1:
        return
    code_to_option = {str(item["session_code"]): item for item in options}
    current_code = str(session.get("session_code") or "")
    option_codes = [str(item["session_code"]) for item in options]
    if current_code not in code_to_option:
        option_codes.insert(0, current_code)
        code_to_option[current_code] = {
            "event_slug": str(current_code).lower(),
            "session_code": current_code,
            "event_label": str(session.get("session_title") or current_code),
            "event_location": "",
            "available": True,
        }
    selected_code = st.selectbox(
        "Event",
        option_codes,
        index=option_codes.index(current_code),
        key="conference-host-event-selector",
        format_func=lambda code: (
            f"{code_to_option[code]['event_label']} · {code_to_option[code]['event_location']}"
            if str(code_to_option[code].get("event_location") or "").strip()
            else str(code_to_option[code]["event_label"])
        ),
    )
    if selected_code != current_code:
        selected = code_to_option[selected_code]
        _sync_event_query(str(selected["event_slug"]))
        st.switch_page(str(selected["host_page"]))


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
            "code": YOUNG_SESSION_CODE,
            "label": "Young",
            "question": "Who are you?",
        },
        {
            "code": UNESCO_SESSION_CODE,
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
        submissions = repo.group_rows_by_submission(
            repo.get_session_rows(
                session["id"],
                text_ids=text_ids_for_session_code(item["code"]),
            )
        )
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

    session_code = current_complexity_session_code(repo)
    bundle = get_conference_bundle(session_code=session_code)
    session = bundle.get("session")
    if not session:
        st.error(
            "Conference session is missing. "
            f"Ensure the shared sessions DB contains `{session_code}`, or run "
            "`scripts/bootstrap_dalembertiennes_session.py` for the Dalembertiennes scaffold."
        )
        return

    _render_event_selector(repo, session)

    response_rows = repo.get_session_rows(
        session["id"],
        text_ids=text_ids_for_session_code(str(session.get("session_code") or "")),
    )
    filtered_rows = filter_rows_to_session_window(response_rows, session)
    submissions = repo.group_rows_by_submission(filtered_rows)
    snapshot = room_snapshot(submissions)
    event_log = list_logged_events(page=PAGE_KEY, session_id=session["id"], limit=100)
    event_context = _event_context(session)

    heading(f"{event_context['event_label']} host")
    microcopy(
        f'{session.get("session_code", session_code)} · '
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
                    "who": row.get("identity")
                    or row.get("alias")
                    or row.get("contact")
                    or ANONYMOUS_COMPLEXITY_NAME,
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
