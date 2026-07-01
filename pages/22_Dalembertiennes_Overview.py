from __future__ import annotations

import csv
import html
import io
from typing import Any

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
from conference.ui import apply_conference_styles, conference_header, summary_card
from ui import set_page, sidebar_debug_state


def _csv_payload(rows: list[dict[str, str]]) -> str:
    output = io.StringIO()
    fieldnames = list(rows[0].keys()) if rows else ["submitted_at", "access_key_last4"]
    writer = csv.DictWriter(output, fieldnames=fieldnames)
    writer.writeheader()
    writer.writerows(rows)
    return output.getvalue()


def _stringify(value: Any) -> str:
    if isinstance(value, list):
        return " | ".join(str(item).strip() for item in value if str(item).strip())
    if isinstance(value, dict):
        return " | ".join(
            f"{key}:{item}"
            for key, item in value.items()
            if str(item).strip()
        )
    return str(value or "").strip()


def _export_rows(submissions: list[dict[str, Any]], resolved_bundle: Any) -> list[dict[str, str]]:
    rows: list[dict[str, str]] = []
    session_fields = {
        str(field)
        for field in resolved_bundle.question_set.session_fields
        if str(field) not in {"question_flags", "identity_reveal_targets", "boiler_room_contribution"}
    }
    for item in submissions:
        row = {
            "submitted_at": str(item.get("submitted_at") or ""),
            "access_key_last4": str(item.get("access_key_last4") or ""),
        }
        for question in resolved_bundle.question_set.questions:
            field = str(question.field)
            if field not in session_fields:
                continue
            row[field] = _stringify(item.get(field))
            free_text_field = str(getattr(question, "free_text_field", "") or "").strip()
            if free_text_field:
                row[free_text_field] = _stringify(item.get(free_text_field))
        rows.append(row)
    return rows


def _text_question_entries(submissions: list[dict[str, Any]], resolved_bundle: Any) -> list[tuple[str, str]]:
    entries: list[tuple[str, str]] = []
    for question in resolved_bundle.question_set.questions:
        if str(question.input_type) != "text":
            continue
        title = str(resolved_bundle.question_set.step_copy.get(str(question.step), {}).get("title") or question.prompt)
        for item in sorted(
            submissions,
            key=lambda row: str(row.get("submitted_at") or ""),
            reverse=True,
        ):
            text = str(item.get(question.field) or "").strip()
            if text:
                entries.append((title, text))
    return entries


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
            "current_page": "dalembertiennes_overview",
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
    exportable_rows = _export_rows(submissions, resolved_bundle)
    text_entries = _text_question_entries(submissions, resolved_bundle)

    conference_header(
        f"{context['event_label']} overview",
        f"Responses stored only for {event_scope_text(session)}.",
        step="overview",
    )

    metrics = st.columns(4)
    metrics[0].metric("Submissions", len(submissions))
    metrics[1].metric("Text responses", len(text_entries))
    metrics[2].metric("Question set", len(resolved_bundle.question_ids))
    metrics[3].metric("Other events touched", 0)

    if exportable_rows:
        st.download_button(
            "Download Dalembertiennes CSV",
            data=_csv_payload(exportable_rows),
            file_name="dalembertiennes_v1_export.csv",
            mime="text/csv",
            type="primary",
            use_container_width=True,
        )
    else:
        st.caption("No Dalembertiennes submissions yet.")

    st.markdown("### Free-text responses")
    if not text_entries:
        summary_card(
            "Blank state",
            "No Dalembertiennes submissions yet. Once participants answer the questionnaire, free-text prompts will appear here.",
        )
        return

    for title, text in text_entries:
        summary_card(title, html.escape(text))


if __name__ == "__main__":
    main()
