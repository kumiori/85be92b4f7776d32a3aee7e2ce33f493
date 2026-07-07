from __future__ import annotations

from typing import Any

import pandas as pd
import streamlit as st

from conference.context import get_conference_bundle, get_conference_repo
from conference.events import UN_WG2_SESSION_CODE, conference_event_context, text_ids_for_session_code
from conference.registry import resolve_question_set_bundle
from conference.session_window import filter_rows_to_session_window
from conference.ui import apply_conference_styles, conference_header
from infra.event_logger import list_logged_events, log_event
from ui import set_page, sidebar_debug_state


def _resolve_un_wg2_session() -> dict[str, Any] | None:
    bundle = get_conference_bundle(session_code=UN_WG2_SESSION_CODE)
    session = bundle.get("session") if isinstance(bundle, dict) else None
    return session if isinstance(session, dict) else None


def _event_scope_text(session: dict[str, Any]) -> str:
    context = conference_event_context(session=session)
    location = str(context.get("event_location") or "").strip()
    if location:
        return f"{context['event_label']} in {location}"
    return str(context.get("event_label") or context.get("event_code") or "this event")


def _pretty(token: str) -> str:
    return str(token or "").replace("_", " ").strip().title()


WG2_GROUPS = (
    "I. Who is speaking?",
    "II. Spatial context",
    "III. Needs",
    "IV. Action",
)

WG2_STEP_GROUPS = {
    "role_lens": "I. Who is speaking?",
    "expertise": "I. Who is speaking?",
    "support_needs": "I. Who is speaking?",
    "work_style": "I. Who is speaking?",
    "main_location": "II. Spatial context",
    "region": "II. Spatial context",
    "cryosphere_domain": "II. Spatial context",
    "needs": "III. Needs",
    "policy_interface": "III. Needs",
    "uncertainty": "III. Needs",
    "timescale": "III. Needs",
    "stakeholder_group": "IV. Action",
    "contribution": "IV. Action",
    "coordination_signal": "IV. Action",
    "coordination_resonance": "IV. Action",
}


def _active_flow_steps(resolved_bundle: Any) -> list[str]:
    question_set = resolved_bundle.question_set
    default_mode = str(getattr(question_set, "default_mode", "") or "quick")
    mode_payload = question_set.flow_modes.get(default_mode) or next(
        iter(question_set.flow_modes.values()),
        {},
    )
    return [str(step) for step in mode_payload.get("steps", [])]


def _question_by_step(resolved_bundle: Any) -> dict[str, Any]:
    return {
        str(question.step): question
        for question in resolved_bundle.question_set.questions
    }


def _question_groups(resolved_bundle: Any) -> dict[str, list[Any]]:
    by_step = _question_by_step(resolved_bundle)
    grouped: dict[str, list[Any]] = {group: [] for group in WG2_GROUPS}
    for step in _active_flow_steps(resolved_bundle):
        question = by_step.get(step)
        if not question:
            continue
        group = WG2_STEP_GROUPS.get(step, "Other")
        grouped.setdefault(group, []).append(question)
    return grouped


def _disabled_questions(resolved_bundle: Any) -> list[Any]:
    active_steps = set(_active_flow_steps(resolved_bundle))
    return [
        question
        for question in resolved_bundle.question_set.questions
        if str(question.step) not in active_steps
    ]


def _mode_step_labels(resolved_bundle: Any, mode: str) -> list[str]:
    question_set = resolved_bundle.question_set
    steps = question_set.flow_modes.get(mode, {}).get("steps", [])
    labels: list[str] = []
    for step in steps:
        copy = question_set.step_copy.get(str(step), {})
        labels.append(str(copy.get("title") or _pretty(str(step))))
    return labels


def _active_question_count(resolved_bundle: Any) -> int:
    by_step = _question_by_step(resolved_bundle)
    return sum(1 for step in _active_flow_steps(resolved_bundle) if step in by_step)


def _question_options(question: Any) -> str:
    options = getattr(question, "options", ())
    if not options:
        return ""
    return ", ".join(str(item.get("label") or item.get("value") or "") for item in options)


def _question_rows(resolved_bundle: Any) -> list[dict[str, str]]:
    rows: list[dict[str, str]] = []
    shared_ids = set(resolved_bundle.shared_question_ids)
    active_steps = set(_active_flow_steps(resolved_bundle))
    for index, question in enumerate(resolved_bundle.question_set.questions, start=1):
        step = str(question.step)
        rows.append(
            {
                "order": str(index),
                "question_id": str(question.question_id),
                "step": step,
                "field": str(question.field),
                "origin": "shared" if str(question.question_id) in shared_ids else "event",
                "question_group": WG2_STEP_GROUPS.get(step, "YAML-only / other"),
                "active": "yes" if step in active_steps else "no",
                "yaml_group": str(getattr(question, "group", "") or ""),
                "subgroup": str(getattr(question, "subgroup", "") or ""),
                "input_type": str(question.input_type),
                "required": "yes" if bool(question.required) else "no",
                "prompt": str(question.prompt),
                "detail_field": str(getattr(question, "free_text_field", "") or ""),
            }
        )
    return rows


def _render_question_bundle(resolved_bundle: Any) -> None:
    question_set = resolved_bundle.question_set
    active_count = _active_question_count(resolved_bundle)
    disabled = _disabled_questions(resolved_bundle)
    metrics = st.columns(4)
    metrics[0].metric("Questions", len(question_set.questions))
    metrics[1].metric("Proposed", active_count)
    metrics[2].metric("YAML-only", len(disabled))
    metrics[3].metric("Modes", len(question_set.flow_modes))

    st.markdown("### Resolved bundle")
    meta_left, meta_right = st.columns(2)
    with meta_left:
        st.code(
            "\n".join(
                [
                    "campaign_slug  = un-cryosphere-decade",
                    f"event_slug      = {resolved_bundle.event_slug}",
                    f"session_code    = {resolved_bundle.session_code}",
                    f"text_id         = {resolved_bundle.text_id}",
                    f"question_set_id = {resolved_bundle.question_set_id}",
                    f"schema_id       = {resolved_bundle.schema_id}",
                ]
            ),
            language="text",
        )
    with meta_right:
        st.code(
            "\n".join(
                [
                    f"module          = {resolved_bundle.question_set_module}",
                    f"source_kind     = {resolved_bundle.question_set_source_kind}",
                    f"source_path     = {resolved_bundle.question_set_source_path}",
                    f"source_note     = {resolved_bundle.question_set_source_note}",
                    f"shared_ids      = {len(resolved_bundle.shared_question_ids)}",
                    f"event_ids       = {len(resolved_bundle.event_specific_question_ids)}",
                ]
            ),
            language="text",
        )

    st.markdown("### Mode structure")
    mode_columns = st.columns(max(len(question_set.flow_modes), 1))
    for column, mode in zip(mode_columns, question_set.flow_modes.keys()):
        with column:
            spec = question_set.flow_modes[mode]
            st.markdown(f"**{spec['title']}**")
            st.caption(str(spec.get("detail") or ""))
            for step_label in _mode_step_labels(resolved_bundle, str(mode)):
                st.markdown(f"- {step_label}")

    st.markdown("### Question architecture")
    for root, questions in _question_groups(resolved_bundle).items():
        with st.expander(root, expanded=True):
            if not questions:
                st.caption("No active questions in this group.")
                continue
            for index, question in enumerate(questions, start=1):
                with st.container(border=True):
                    st.markdown(f"**{index}. {str(question.prompt)}**")
                    st.caption(
                        f"`{question.question_id}` · step `{question.step}` · field `{question.field}` · "
                        f"{question.input_type} · {'required' if question.required else 'optional'}"
                    )
                    if str(question.subtitle or "").strip():
                        st.caption(str(question.subtitle))
                    options = _question_options(question)
                    if options:
                        st.markdown(f"**Options:** {options}")
                    detail_field = str(getattr(question, "free_text_field", "") or "").strip()
                    if detail_field:
                        detail_label = str(getattr(question, "free_text_label", "") or "Detail")
                        st.caption(f"Detail field: `{detail_field}` · label: {detail_label}")

    with st.expander("YAML-only or disabled questions", expanded=bool(disabled)):
        if not disabled:
            st.caption("Every question present in the YAML is active in the proposed flow.")
        for question in disabled:
            with st.container(border=True):
                st.markdown(f"**{str(question.prompt)}**")
                st.caption(
                    f"`{question.question_id}` · step `{question.step}` · field `{question.field}` · "
                    "present in YAML but not active in the proposed flow"
                )
                if str(question.subtitle or "").strip():
                    st.caption(str(question.subtitle))

    with st.expander("Flat question table", expanded=False):
        st.dataframe(pd.DataFrame(_question_rows(resolved_bundle)), use_container_width=True)


def main() -> None:
    set_page()
    apply_conference_styles()

    repo = get_conference_repo()
    if not repo or not repo.is_ready():
        st.error(repo.unavailable_reason if repo else "Conference repository is unavailable.")
        return

    session = _resolve_un_wg2_session()
    if not session:
        st.error(
            "UN WG2 session is missing. "
            "Run `scripts/bootstrap_un_wg2_session.py` first."
        )
        return

    context = conference_event_context(session=session)
    resolved_bundle = resolve_question_set_bundle(session=session)
    sidebar_debug_state(
        debug_context={
            "current_page": "un_wg2_host",
            "event_log_page": "un_wg2_host",
            "campaign_slug": "un-cryosphere-decade",
            "event_slug": resolved_bundle.event_slug,
            "session_code": resolved_bundle.session_code,
            "session_id": str(session.get("id") or ""),
            "event_label": str(context.get("event_label") or ""),
            "text_id": resolved_bundle.text_id,
            "question_set_id": resolved_bundle.question_set_id,
            "schema_id": resolved_bundle.schema_id,
            "question_set_module": resolved_bundle.question_set_module,
            "question_set_source_kind": resolved_bundle.question_set_source_kind,
            "question_set_source_path": resolved_bundle.question_set_source_path,
            "question_set_source_note": resolved_bundle.question_set_source_note,
            "question_count": len(resolved_bundle.question_ids),
            "shared_question_count": len(resolved_bundle.shared_question_ids),
            "event_specific_question_count": len(resolved_bundle.event_specific_question_ids),
            "question_ids": list(resolved_bundle.question_ids),
            "shared_question_ids": list(resolved_bundle.shared_question_ids),
            "event_specific_question_ids": list(resolved_bundle.event_specific_question_ids),
        }
    )

    response_rows = repo.get_session_rows(
        str(session.get("id") or ""),
        text_ids=text_ids_for_session_code(str(session.get("session_code") or "")),
    )
    filtered_rows = filter_rows_to_session_window(response_rows, session)
    submissions = repo.group_rows_by_submission(filtered_rows)
    event_log = list_logged_events(
        page="conference",
        session_id=str(session.get("id") or ""),
        limit=100,
    )

    log_event(
        module="iceicebaby.un_wg2",
        event_type="host_loaded",
        page="un_wg2_host",
        session_id=str(session.get("id") or ""),
        status="ok",
        metadata={
            "campaign_slug": "un-cryosphere-decade",
            "event_slug": resolved_bundle.event_slug,
            "session_code": resolved_bundle.session_code,
            "text_id": resolved_bundle.text_id,
            "question_set_id": resolved_bundle.question_set_id,
            "submissions": len(submissions),
        },
    )

    conference_header(
        f"{context['event_label']} host",
        f"Operator view for {_event_scope_text(session)}.",
        step="host",
    )

    tabs = st.tabs(["Question set", "Submissions", "Event log"])
    with tabs[0]:
        _render_question_bundle(resolved_bundle)
    with tabs[1]:
        metrics = st.columns(3)
        metrics[0].metric("Submissions", len(submissions))
        metrics[1].metric("Filtered rows", len(filtered_rows))
        metrics[2].metric("Recognized text ids", len(text_ids_for_session_code(str(session.get("session_code") or ""))))
        if submissions:
            st.dataframe(pd.DataFrame(submissions), use_container_width=True)
        else:
            st.info("No UN WG2 submissions yet.")
    with tabs[2]:
        if event_log:
            st.dataframe(pd.DataFrame(event_log), use_container_width=True)
        else:
            st.info("No recent event log entries.")


if __name__ == "__main__":
    main()
