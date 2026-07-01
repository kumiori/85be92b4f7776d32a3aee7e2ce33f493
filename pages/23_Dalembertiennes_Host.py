from __future__ import annotations

from collections import defaultdict
from typing import Any

import pandas as pd
import streamlit as st

from conference.context import get_conference_bundle, get_conference_repo
from conference.dalembertiennes import (
    event_context,
    event_scope_text,
    resolve_dalembertiennes_session,
)
from conference.events import text_ids_for_session_code
from conference.registry import resolve_question_set_bundle
from conference.session_window import filter_rows_to_session_window
from conference.ui import apply_conference_styles, conference_header
from infra.event_logger import list_logged_events
from ui import set_page, sidebar_debug_state


def _pretty(token: str) -> str:
    return str(token or "").replace("_", " ").strip().title()


def _question_groups(resolved_bundle: Any) -> dict[str, dict[str, list[Any]]]:
    grouped: dict[str, dict[str, list[Any]]] = defaultdict(lambda: defaultdict(list))
    shared_ids = set(resolved_bundle.shared_question_ids)
    for question in resolved_bundle.question_set.questions:
        question_id = str(question.question_id)
        root = "Shared / reused" if question_id in shared_ids else "Dalembertiennes-specific"
        subgroup = str(getattr(question, "subgroup", "") or getattr(question, "group", "") or "general")
        grouped[root][subgroup].append(question)
    return {root: dict(children) for root, children in grouped.items()}


def _mode_step_labels(resolved_bundle: Any, mode: str) -> list[str]:
    question_set = resolved_bundle.question_set
    steps = question_set.flow_modes.get(mode, {}).get("steps", [])
    labels: list[str] = []
    for step in steps:
        copy = question_set.step_copy.get(str(step), {})
        labels.append(str(copy.get("title") or _pretty(str(step))))
    return labels


def _question_options(question: Any) -> str:
    options = getattr(question, "options", ())
    if not options:
        return ""
    return ", ".join(str(item.get("label") or item.get("value") or "") for item in options)


def _question_rows(resolved_bundle: Any) -> list[dict[str, str]]:
    rows: list[dict[str, str]] = []
    shared_ids = set(resolved_bundle.shared_question_ids)
    for index, question in enumerate(resolved_bundle.question_set.questions, start=1):
        rows.append(
            {
                "order": str(index),
                "question_id": str(question.question_id),
                "step": str(question.step),
                "field": str(question.field),
                "origin": "shared" if str(question.question_id) in shared_ids else "event",
                "group": str(getattr(question, "group", "") or ""),
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
    metrics = st.columns(4)
    metrics[0].metric("Questions", len(question_set.questions))
    metrics[1].metric("Shared", len(resolved_bundle.shared_question_ids))
    metrics[2].metric("Event-specific", len(resolved_bundle.event_specific_question_ids))
    metrics[3].metric("Modes", len(question_set.flow_modes))

    st.markdown("### Resolved bundle")
    meta_left, meta_right = st.columns(2)
    with meta_left:
        st.code(
            "\n".join(
                [
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
    for root, subgroups in _question_groups(resolved_bundle).items():
        st.markdown(f"#### {root}")
        for subgroup, questions in subgroups.items():
            with st.expander(_pretty(subgroup), expanded=subgroup in {"opening", "general"}):
                for question in questions:
                    with st.container(border=True):
                        st.markdown(f"**{_pretty(str(question.step))}**")
                        st.caption(
                            f"`{question.question_id}` · field `{question.field}` · {question.input_type} · "
                            f"{'required' if question.required else 'optional'}"
                        )
                        st.write(str(question.prompt))
                        if str(question.subtitle or "").strip():
                            st.caption(str(question.subtitle))
                        options = _question_options(question)
                        if options:
                            st.markdown(f"**Options:** {options}")
                        detail_field = str(getattr(question, "free_text_field", "") or "").strip()
                        if detail_field:
                            detail_label = str(getattr(question, "free_text_label", "") or "Detail")
                            st.caption(f"Detail field: `{detail_field}` · label: {detail_label}")

    with st.expander("Flat question table", expanded=False):
        st.dataframe(pd.DataFrame(_question_rows(resolved_bundle)), use_container_width=True)


def main() -> None:
    set_page()
    apply_conference_styles()

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
    resolved_bundle = resolve_question_set_bundle(session=session)
    sidebar_debug_state(
        debug_context={
            "current_page": "dalembertiennes_host",
            "event_log_page": "conference",
            "event_slug": resolved_bundle.event_slug,
            "session_code": resolved_bundle.session_code,
            "session_id": str(session.get("id") or ""),
            "event_label": str(context.get("event_label") or ""),
            "text_id": resolved_bundle.text_id,
            "question_set_id": resolved_bundle.question_set_id,
            "schema_id": resolved_bundle.schema_id,
            "question_set_module": resolved_bundle.question_set_module,
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

    conference_header(
        f"{context['event_label']} host",
        f"Operator view for {event_scope_text(session)}.",
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
            st.info("No Dalembertiennes submissions yet.")
    with tabs[2]:
        if event_log:
            st.dataframe(pd.DataFrame(event_log), use_container_width=True)
        else:
            st.info("No recent event log entries.")


if __name__ == "__main__":
    main()
