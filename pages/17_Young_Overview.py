from __future__ import annotations

from typing import Any, Dict, List

import pandas as pd
import streamlit as st

from conference.context import get_conference_bundle, get_conference_repo
from conference.events import (
    UNESCO_SESSION_CODE,
    YOUNG_SESSION_CODE,
    YOUNG_TEXT_ID,
    complexity_text_ids,
    current_complexity_session_code,
    text_ids_for_session_code,
)
from conference.pisa_legacy_models import field_option_label_map
from conference.topology import count_field
from conference.ui import apply_conference_styles, conference_header
from ui import set_page, sidebar_debug_state


def _labels_for(field: str, value: Any) -> str:
    label_map = field_option_label_map(field)
    if isinstance(value, list):
        return (
            ", ".join(label_map.get(str(item), str(item)) for item in value if str(item))
            or "None"
        )
    if isinstance(value, str):
        return label_map.get(value, value) if value else "No answer"
    return str(value or "No answer")


def _counts_table(title: str, field: str, submissions: List[Dict[str, Any]]) -> None:
    st.markdown(f"### {title}")
    counts = dict(count_field(submissions, field))
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
    st.markdown("### Notes from the room")
    questions = [
        str(row.get("open_text") or "").strip()
        for row in submissions
        if str(row.get("open_text") or "").strip()
    ]
    if not questions:
        st.caption("No notes yet.")
        return
    for question in questions[:8]:
        st.markdown(f"- {question}")


def _other_sessions(repo: Any, current_session_id: str) -> List[Dict[str, Any]]:
    sessions = [
        {
            "code": current_complexity_session_code(repo),
            "label": "Complexity",
            "question": "What is your perspective?",
        },
        {
            "code": UNESCO_SESSION_CODE,
            "label": "UNESCO",
            "question": "What resonates?",
        },
    ]
    rows: List[Dict[str, Any]] = []
    seen_codes: set[str] = set()
    for item in sessions:
        code = str(item["code"] or "").strip()
        if not code or code in seen_codes:
            continue
        seen_codes.add(code)
        session = repo.resolve_session(session_code=code)
        if not session or str(session.get("id") or "") == str(current_session_id or ""):
            continue
        session_text_ids = (
            complexity_text_ids()
            if code == current_complexity_session_code(repo)
            else text_ids_for_session_code(code)
        )
        submissions = repo.group_rows_by_submission(
            repo.get_session_rows(
                session["id"],
                text_ids=session_text_ids,
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
    apply_conference_styles()
    sidebar_debug_state()

    repo = get_conference_repo()
    if not repo or not repo.is_ready():
        st.error(
            repo.unavailable_reason if repo else "Conference repository is unavailable."
        )
        return

    bundle = get_conference_bundle(session_code=YOUNG_SESSION_CODE)
    session = bundle.get("session")
    if not session:
        st.error(
            f"Conference session is missing. Ensure `{YOUNG_SESSION_CODE}` exists in the shared sessions DB."
        )
        return

    conference_header("Young overview", "", step="")
    st.warning(
        "Known bug: the historical Young/Pisa data is not mapped correctly right now. "
        "This overview is paused until that cohort is re-linked."
    )
    st.caption(
        "Do not use the zero counts on this page for interpretation. "
        "The current Complexity event remains active."
    )
    st.stop()

    metrics = st.columns(4)
    metrics[0].metric("Participants", len(submissions))
    metrics[1].metric("Happy to engage", int(follow_up_counts.get("happy_to_engage", 0)))
    metrics[2].metric("Maybe later", int(follow_up_counts.get("maybe_later", 0)))
    metrics[3].metric(
        "Deep dives",
        sum(1 for row in submissions if str(row.get("mode") or "") == "deep"),
    )

    historical = _other_sessions(repo, str(session.get("id") or ""))
    if historical:
        st.markdown("### Other sessions")
        for item in historical:
            st.markdown(
                f'- {item["label"]}: {int(item["participants"])} participants · question: "{item["question"]}"'
            )

    for title, field in [
        ("Point of view", "role"),
        ("Systems", "systems"),
        ("Expectations", "expectations"),
        ("Formulations", "formulation"),
        ("Reality check", "reality_check"),
        ("Scale", "scale"),
        ("Motivations", "motivations"),
        ("Obstacles", "obstacle"),
        ("Research style", "research_style"),
        ("Challenges", "challenge"),
        ("Timescales", "timescale"),
        ("Continue conversation", "continue_conversation"),
    ]:
        _counts_table(title, field, submissions)

    _open_questions(submissions)


if __name__ == "__main__":
    main()
