from __future__ import annotations

from collections import Counter
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
from conference.question_flags import QUESTION_FLAG_LABELS
from conference.repo import QUESTION_BUNDLE_IDS
from conference.session_window import filter_rows_to_session_window
from conference.topology import count_field, room_snapshot
from conference.ui import apply_conference_styles, conference_header
from ui import set_page, sidebar_debug_state


def _event_context(session: Dict[str, Any]) -> Dict[str, Any]:
    return conference_event_context(session=session)


def _event_scope_text(session: Dict[str, Any]) -> str:
    context = _event_context(session)
    location = str(context.get("event_location") or "").strip()
    if location:
        return f"{context['event_label']} in {location}"
    return str(context.get("event_label") or context.get("event_code") or "this event")


def _sync_event_query(event_slug: str) -> None:
    next_params = {"event": str(event_slug or "").strip()}
    st.query_params.clear()
    st.query_params.update(next_params)


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
        key="conference-overview-event-selector",
        format_func=lambda code: (
            f"{code_to_option[code]['event_label']} · {code_to_option[code]['event_location']}"
            if str(code_to_option[code].get("event_location") or "").strip()
            else str(code_to_option[code]["event_label"])
        ),
    )
    if selected_code != current_code:
        selected = code_to_option[selected_code]
        _sync_event_query(str(selected["event_slug"]))
        st.switch_page(str(selected["overview_page"]))


def _labels_for(field: str, value: Any) -> str:
    label_map = field_option_label_map(field)
    if field == "complexity_fingerprint" and isinstance(value, dict):
        return " · ".join(
            f"{FINGERPRINT_LABELS.get(axis, axis.title())} {int(value.get(axis, 0) or 0)}"
            for axis in FINGERPRINT_LABELS
        )
    if isinstance(value, list):
        return (
            ", ".join(label_map.get(str(item), str(item)) for item in value if str(item))
            or "None"
        )
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


def _boiler_room(submissions: List[Dict[str, Any]]) -> None:
    st.markdown("### Boiler room")
    entries = [
        str(row.get("boiler_room_contribution") or "").strip()
        for row in submissions
        if str(row.get("boiler_room_contribution") or "").strip()
    ]
    if not entries:
        st.caption("No contributions dropped yet.")
        return
    for entry in entries[:8]:
        st.markdown(f"- {entry}")


def _question_flags(submissions: List[Dict[str, Any]]) -> None:
    st.markdown("### Question flags")
    counts: Counter[str] = Counter()
    notes: List[str] = []
    for row in submissions:
        payload = row.get("question_flags")
        if not isinstance(payload, dict):
            continue
        for question_id, item in payload.items():
            if not isinstance(item, dict):
                continue
            for flag in item.get("flags", []):
                counts[str(flag)] += 1
            note = str(item.get("note") or "").strip()
            if note:
                notes.append(f"{question_id}: {note}")
    if not counts and not notes:
        st.caption("No question flags yet.")
        return
    if counts:
        st.table(
            pd.DataFrame(
                [
                    {
                        "flag": QUESTION_FLAG_LABELS.get(key, key),
                        "count": value,
                    }
                    for key, value in counts.most_common()
                ]
            )
        )
    if notes:
        st.caption("Recent notes")
        for note in notes[:8]:
            st.markdown(f"- {note}")


def _other_sessions(repo: Any, current_session_id: str) -> List[Dict[str, Any]]:
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
        if not session or str(session.get("id") or "") == str(current_session_id or ""):
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


def _bundle_schema_version(row: Dict[str, Any]) -> str:
    payload = row.get("value_json")
    if not isinstance(payload, dict):
        return ""
    bundle = payload.get("bundle")
    if not isinstance(bundle, dict):
        return ""
    return str(bundle.get("schema_version") or "")


def _bundle_session_value(row: Dict[str, Any], key: str) -> str:
    payload = row.get("value_json")
    if not isinstance(payload, dict):
        return ""
    bundle = payload.get("bundle")
    if not isinstance(bundle, dict):
        return ""
    session_payload = bundle.get("session")
    if not isinstance(session_payload, dict):
        return ""
    return str(session_payload.get(key) or "")


def _debug_rows(repo: Any, session: Dict[str, Any]) -> None:
    try:
        raw_rows = repo.interaction_repo().get_responses(session["id"])
    except Exception as exc:
        st.caption(f"Debug rows unavailable: {exc}")
        return

    current_session_code = str(
        session.get("session_code") or current_complexity_session_code(repo)
    )
    active_text_ids = set(text_ids_for_session_code(current_session_code))
    session_start = str(session.get("start") or session.get("created_at") or "")
    session_end = str(session.get("end") or "")
    included_rows = filter_rows_to_session_window(
        [
            row
            for row in raw_rows
            if str(row.get("item_id") or "").strip() in QUESTION_BUNDLE_IDS
            and str(row.get("text_id") or "").strip() in active_text_ids
        ],
        session,
    )
    included_ids = {str(row.get("response_id") or "") for row in included_rows}

    debug_rows: List[Dict[str, Any]] = []
    for row in raw_rows:
        payload = row.get("value_json") if isinstance(row.get("value_json"), dict) else {}
        field = str(payload.get("field") or "")
        item_id = str(row.get("item_id") or "")
        text_id = str(row.get("text_id") or "")
        response_id = str(row.get("response_id") or "")
        if field != "session_bundle" and item_id not in QUESTION_BUNDLE_IDS:
            continue
        reasons: List[str] = []
        if item_id not in QUESTION_BUNDLE_IDS:
            reasons.append("bundle prefix mismatch")
        if text_id not in active_text_ids:
            reasons.append("text_id mismatch")
        if response_id not in included_ids and not reasons:
            reasons.append("session window excluded")
        if not reasons:
            reasons.append("included")
        debug_rows.append(
            {
                "emoji_suffix": str(payload.get("access_key_last4") or ""),
                "created": str(row.get("created_at") or row.get("timestamp") or ""),
                "bundle_prefix": item_id,
                "schema_version": _bundle_schema_version(row),
                "event_code": _bundle_session_value(row, "event_code"),
                "session_code": _bundle_session_value(row, "session_code"),
                "resolved_session_code": current_session_code,
                "text_id": text_id,
                "window_start": session_start,
                "window_end": session_end,
                "reason": ", ".join(reasons),
            }
        )

    with st.expander("Debug rows", expanded=False):
        if not debug_rows:
            st.caption("No bundle rows found for the resolved session relation.")
            return
        st.table(pd.DataFrame(debug_rows))


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

    session_code = current_complexity_session_code(repo)
    bundle = get_conference_bundle(session_code=session_code)
    session = bundle.get("session")
    if not session:
        st.error(
            "Conference session is missing. "
            f"Ensure `{session_code}` exists in the shared sessions DB, or run "
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
    event_context = _event_context(session)

    conference_header(f"{event_context['event_label']} overview", "", step="")
    st.markdown(f"### A public snapshot of {_event_scope_text(session)}.")

    metrics = st.columns(4)
    metrics[0].metric("Participants", int(snapshot["participants"]))
    metrics[1].metric("Countries", int(snapshot["countries"]))
    metrics[2].metric(
        "Follow-up yes",
        int(snapshot["follow_up"].get("yes", 0)),
    )
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

    _counts_table("Perspective", "role", dict(count_field(submissions, "role")))
    _counts_table("Computational scale", "scale", dict(count_field(submissions, "scale")))
    _counts_table(
        "Collaboration style",
        "collaboration_style",
        dict(count_field(submissions, "collaboration_style")),
    )
    _counts_table("Assets", "assets", dict(snapshot["assets"]))
    _counts_table("Motivations", "motivations", dict(snapshot["motivations"]))
    _counts_table("Obstacles", "obstacle", dict(snapshot["obstacles"]))
    _counts_table("Challenges", "challenge", dict(snapshot["challenges"]))
    _counts_table(
        "Follow-up interest",
        "follow_up_interest",
        dict(snapshot["follow_up"]),
    )

    _boiler_room(submissions)
    _question_flags(submissions)
    _open_questions(submissions)
    _debug_rows(repo, session)


if __name__ == "__main__":
    main()
