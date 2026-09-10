from __future__ import annotations

from typing import Any

import pandas as pd
import streamlit as st

from conference.context import get_conference_repo
from conference.events import event_config_for_request, event_config_for_session_code
from conference.host import HostSnapshot, host_session_options, load_host_snapshot, snapshot_metrics
from conference.wg2_ux import host_role_allowed
from infra.app_context import get_authenticator, get_notion_repo
from infra.app_state import ensure_auth, ensure_session_state, require_login
from infra.event_logger import list_logged_events
from ui import cracks_globe_block, set_page, sidebar_debug_state


def _snapshot(session_code: str, *, refresh: bool = False) -> HostSnapshot:
    cache = st.session_state.setdefault("host_snapshot_cache", {})
    if refresh:
        cache.pop(session_code, None)
    if session_code not in cache:
        repo = get_conference_repo()
        if not repo or not repo.is_ready():
            raise RuntimeError(repo.unavailable_reason if repo else "Conference repository is unavailable.")
        cache[session_code] = load_host_snapshot(
            session_code,
            repo=repo,
            list_players=repo.notion_repo.list_players,
            list_events=lambda session_id: list_logged_events(page="conference", session_id=session_id, limit=250),
        )
    return cache[session_code]


def _render_summary(snapshot: HostSnapshot) -> None:
    metrics = snapshot_metrics(snapshot)
    columns = st.columns(4)
    columns[0].metric("Participants", metrics["participants"])
    columns[1].metric("Completed submissions", metrics["completed_submissions"])
    columns[2].metric("Questions answered", metrics["questions_answered"])
    columns[3].metric("Last contribution", metrics["last_contribution"])


def _render_response_field(snapshot: HostSnapshot) -> None:
    st.subheader("Response Field")
    st.caption("Operational coverage only: density is not a measure of answer quality. ⚑ marks flagged answers; S marks skips.")
    if not snapshot.response_field:
        st.info("No response field is available yet.")
        return
    rows = []
    for cell in snapshot.response_field:
        if cell["skipped"]:
            mark = "S"
        elif cell["status"] == "answered":
            mark = "●" if float(cell["response_density"]) >= 0.66 else "◐" if float(cell["response_density"]) > 0 else "○"
        elif cell["status"] == "viewed_unanswered":
            mark = "○"
        else:
            mark = "·"
        if cell["flagged"]:
            mark += " ⚑"
        rows.append({"Participant": cell["participant_label"], "Question": f"{cell['section']} · {cell['question_label']}", "State": mark})
    frame = pd.DataFrame(rows).pivot(index="Participant", columns="Question", values="State")
    st.dataframe(frame, width="stretch")


def _render_timeline(snapshot: HostSnapshot) -> None:
    st.subheader("Response Timeline")
    if not snapshot.timeline:
        st.info("No completed submissions have timestamps yet.")
        return
    frame = pd.DataFrame(snapshot.timeline)
    frame["timestamp"] = pd.to_datetime(frame["timestamp"], utc=True)
    st.line_chart(frame, x="timestamp", y="cumulative", x_label="Contribution time", y_label="Cumulative completed submissions")


def _render_spatial(snapshot: HostSnapshot) -> None:
    st.subheader("Spatial Context")
    if not snapshot.locations:
        st.info("This questionnaire has no optional geographic coordinates to display.")
        return
    dimensions = sorted({str(item["dimension"]) for item in snapshot.locations})
    st.caption("Location dimensions: " + ", ".join(dimensions))
    cracks_globe_block(list(snapshot.locations), key=f"host-{snapshot.questionnaire.session_code}", point_value_label="Participants")


def _participant_frame(snapshot: HostSnapshot) -> pd.DataFrame:
    columns = ["participant_id", "display_name", "email", "institution", "location", "submission_status", "first_contribution", "last_contribution"]
    return pd.DataFrame(snapshot.participants, columns=columns)


def _render_question_set(snapshot: HostSnapshot) -> None:
    bundle = snapshot.questionnaire
    question_set = bundle.question_set
    columns = st.columns(4)
    columns[0].metric("Questions", len(question_set.questions))
    columns[1].metric("Shared questions", len(bundle.shared_question_ids))
    columns[2].metric("Event-specific questions", len(bundle.event_specific_question_ids))
    columns[3].metric("Modes", len(question_set.flow_modes))
    st.code("\n".join([
        f"questionnaire_id = {bundle.questionnaire_id}", f"revision         = {bundle.questionnaire_revision}",
        f"session_code     = {bundle.session_code}", f"schema           = {bundle.schema_id}",
        f"source_kind      = {bundle.question_set_source_kind}", f"source_path      = {bundle.question_set_source_path}",
    ]), language="text")
    for mode, spec in question_set.flow_modes.items():
        st.markdown(f"**{spec.get('title') or mode}**")
        step_by_id = {question.step: question for question in question_set.questions}
        for step in spec.get("steps", []):
            question = step_by_id.get(step)
            if question:
                st.write(f"{question.question_id} · {question.prompt}")


def main(*, session_code_override: str = "") -> None:
    set_page()
    ensure_session_state()
    sidebar_debug_state()
    notion_repo = get_notion_repo()
    ensure_auth(get_authenticator(notion_repo), key="generic-host-login")
    require_login()
    if not host_role_allowed(str(st.session_state.get("player_role") or "")):
        st.error("Host or admin access only.")
        return

    options = host_session_options(include_test=True)
    by_code = {item["session_code"]: item for item in options}
    requested_event = str(st.query_params.get("event") or "").strip()
    if not requested_event and session_code_override:
        override_config = event_config_for_session_code(session_code_override)
        requested_event = override_config.slug if override_config else ""
    requested = event_config_for_request(requested_event, test=st.query_params.get("test", "")) if requested_event else None
    initial = (requested.session_code if requested else "") or session_code_override
    if initial not in by_code:
        initial = next((item["session_code"] for item in options if not item["test_mode"]), "")
    st.title("Host")
    selected_code = st.selectbox("Session / event", list(by_code), index=list(by_code).index(initial), format_func=lambda code: by_code[code]["label"], key="generic-host-session")
    selected = by_code[selected_code]
    if selected["test_mode"]:
        st.warning("TEST MODE · all host data is scoped to the isolated debug session")
    refresh = st.button("Refresh data", icon=":material/refresh:")
    try:
        snapshot = _snapshot(selected_code, refresh=refresh)
    except (RuntimeError, ValueError) as exc:
        st.error(str(exc))
        return
    st.caption(f"{snapshot.session.get('session_code')} · refreshed {snapshot.loaded_at}")
    view = st.segmented_control("Host view", ["Overview", "Participants", "Question set", "Submissions", "Event log"], default="Overview", key="generic-host-view")
    if view == "Overview":
        _render_summary(snapshot)
        _render_response_field(snapshot)
        _render_timeline(snapshot)
        _render_spatial(snapshot)
        st.subheader("Recent participants")
        st.dataframe(_participant_frame(snapshot).sort_values("last_contribution", ascending=False).head(10), hide_index=True, width="stretch")
    elif view == "Participants":
        st.dataframe(_participant_frame(snapshot), hide_index=True, width="stretch")
    elif view == "Question set":
        _render_question_set(snapshot)
    elif view == "Submissions":
        st.dataframe(pd.DataFrame(snapshot.submissions), hide_index=True, width="stretch") if snapshot.submissions else st.info("No submissions yet.")
    elif view == "Event log":
        st.dataframe(pd.DataFrame(snapshot.events), hide_index=True, width="stretch") if snapshot.events else st.info("No recent event log entries.")
