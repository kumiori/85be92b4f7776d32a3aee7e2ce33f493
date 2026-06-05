from __future__ import annotations

from collections import Counter
from typing import Any, Dict, List

import pandas as pd
import streamlit as st

from conference.context import get_conference_bundle, get_conference_repo
from conference.models import FLOW_MODES, field_option_label_map
from conference.ui import apply_conference_styles, conference_header
from ui import set_page, sidebar_debug_state


def _labels_for(field: str, value: Any) -> str:
    if field == "mode":
        mode_spec = FLOW_MODES.get(str(value or "").strip(), {})
        return str(mode_spec.get("title") or value or "Unknown")
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
    apply_conference_styles()
    sidebar_debug_state()

    repo = get_conference_repo()
    if not repo or not repo.is_ready():
        st.error(repo.unavailable_reason if repo else "Conference repository is unavailable.")
        return

    bundle = get_conference_bundle()
    session = bundle.get("session")
    if not session:
        st.error("Conference session is missing. Ensure `pisa-conference-session` exists in the shared sessions DB.")
        return

    submissions = repo.group_rows_by_submission(repo.get_session_rows(session["id"]))

    conference_header("Pisa overview", "", step="")
    st.markdown("### A public snapshot of the anonymous Pisa interaction.")

    metrics = st.columns(4)
    follow_up = _counts(submissions, "continue_conversation")
    metrics[0].metric("Participants", len(submissions))
    metrics[1].metric("Happy to engage", follow_up.get("happy_to_engage", 0))
    metrics[2].metric("Maybe later", follow_up.get("maybe_later", 0))
    metrics[3].metric("Deep dives", _counts(submissions, "mode").get("deep", 0))

    for field in ["mode", "role", "systems", "motivations", "obstacle", "challenge"]:
        counter = _counts(submissions, field)
        st.markdown(f"### {field.replace('_', ' ').title()}")
        if not counter:
            st.caption("No responses yet.")
            continue
        table_rows = [
            {"label": _labels_for(field, key), "count": value}
            for key, value in counter.most_common()
        ]
        df = pd.DataFrame(table_rows)
        if len(df) <= 6:
            st.table(df)
        else:
            st.bar_chart(df.set_index("label"))


if __name__ == "__main__":
    main()
