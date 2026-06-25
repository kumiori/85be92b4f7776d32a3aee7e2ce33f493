from __future__ import annotations

from typing import Any, Dict, List

import pandas as pd
import streamlit as st

from conference.context import get_conference_bundle, get_conference_repo
from conference.models import FINGERPRINT_LABELS, field_option_label_map
from conference.topology import count_field, room_snapshot
from conference.ui import apply_conference_styles, conference_header
from ui import set_page, sidebar_debug_state


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


def _counts_table(title: str, field: str, counts: Dict[str, int]) -> None:
    st.markdown(f"### {title}")
    if not counts:
        st.caption("No responses yet.")
        return
    table_rows = [
        {"label": _labels_for(field, key), "count": value}
        for key, value in sorted(counts.items(), key=lambda item: (-item[1], item[0]))
    ]
    df = pd.DataFrame(table_rows)
    if len(df) <= 6:
        st.table(df)
    else:
        st.bar_chart(df.set_index("label"))


def _open_questions(submissions: List[Dict[str, Any]]) -> None:
    st.markdown("### Questions in the room")
    questions = [
        str(row.get("open_question") or "").strip()
        for row in submissions
        if str(row.get("open_question") or "").strip()
    ]
    if not questions:
        st.caption("No questions yet.")
        return
    for question in questions[:8]:
        st.markdown(f"- {question}")


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
    apply_conference_styles()
    sidebar_debug_state()

    repo = get_conference_repo()
    if not repo or not repo.is_ready():
        st.error(repo.unavailable_reason if repo else "Conference repository is unavailable.")
        return

    bundle = get_conference_bundle(prefer_active=True)
    session = bundle.get("session")
    if not session:
        st.error("Conference session is missing. Ensure `pisa-conference-session` exists in the shared sessions DB.")
        return

    submissions = repo.group_rows_by_submission(repo.get_session_rows(session["id"]))
    snapshot = room_snapshot(submissions)

    conference_header("Complexity overview", "", step="")
    st.markdown("### A public snapshot of the anonymous room.")

    metrics = st.columns(4)
    metrics[0].metric("Participants", int(snapshot["participants"]))
    metrics[1].metric("Countries", int(snapshot["countries"]))
    metrics[2].metric("Follow-up yes", int(snapshot["follow_up"].get("yes", 0)))
    metrics[3].metric("Deep dives", sum(1 for row in submissions if str(row.get("mode") or "") == "deep"))

    historical = _historical_session_counts(repo, str(session.get("id") or ""))
    if historical:
        st.markdown("### Other sessions")
        for item in historical:
            st.markdown(
                f'- {item["label"]}: {int(item["participants"])} participants · question: "{item["question"]}"'
            )

    _counts_table("Perspective", "role", dict(count_field(submissions, "role")))
    _counts_table("Assets", "assets", dict(snapshot["assets"]))
    _counts_table("Motivations", "motivations", dict(snapshot["motivations"]))
    _counts_table("Obstacles", "obstacle", dict(snapshot["obstacles"]))
    _counts_table("Challenges", "challenge", dict(snapshot["challenges"]))
    _open_questions(submissions)


if __name__ == "__main__":
    main()
