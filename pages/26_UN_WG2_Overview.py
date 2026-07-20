from __future__ import annotations

import ast
from collections import Counter
import csv
from datetime import datetime, timedelta, timezone
import html
import io
import statistics
from typing import Any

import streamlit as st

from conference.context import get_conference_bundle, get_conference_repo
from conference.events import (
    UN_WG2_SESSION_CODE,
    conference_event_context,
    text_ids_for_session_code,
)
from conference.registry import resolve_question_set_bundle
from conference.session_window import filter_rows_to_session_window
from conference.ui import apply_conference_styles, summary_card
from infra.event_logger import list_logged_events, log_event
from ui import cracks_globe_block, set_page, sidebar_debug_state


FIELD_FAMILIES: dict[str, dict[str, list[str]]] = {
    "wg2_role_lens": {
        "Scientific production": ["contributing_scientist", "modeller"],
        "Observation and data": ["observer_data_provider"],
        "Regional knowledge": ["regional_expert"],
        "Decision and policy interface": ["decision_support", "policy_interface"],
        "Coordination and institutional support": [
            "core_wg2_leadership",
            "partner_institution",
            "coordination_support",
            "observer_invited_participant",
            "other",
        ],
    },
    "wg2_expertise": {
        "Cryosphere science": ["cryosphere_processes"],
        "Observation and modelling": [
            "observations",
            "modelling",
            "projections",
            "uncertainty",
        ],
        "Risk and impacts": ["risk", "impacts", "adaptation"],
        "Translation and policy": ["policy", "stakeholder_engagement"],
        "Data and visualisation": ["data_infrastructure", "visualisation"],
        "Coordination and facilitation": ["coordination", "other"],
    },
    "wg2_work_style": {
        "Delivery rhythm": ["task_based", "rapid_prototyping"],
        "Research mode": [
            "curiosity_driven",
            "data_driven",
            "field_based",
            "model_based",
            "long_form_research",
        ],
        "Synthesis and translation": [
            "synthesis_oriented",
            "facilitation_oriented",
            "stakeholder_oriented",
            "writing_oriented",
            "other",
        ],
    },
    "wg2_policy_interface": {
        "Risk and warning": [
            "risk_management",
            "early_warning",
            "disaster_risk_reduction",
        ],
        "Adaptation and planning": [
            "adaptation_planning",
            "infrastructure_planning",
            "coastal_planning",
        ],
        "Infrastructure and resources": ["water_resources"],
        "Ecosystems": ["biodiversity_ecosystems"],
        "Finance": ["finance_insurance"],
        "Policy and assessment": ["international_assessments", "national_policy"],
        "Communities and education": [
            "education_capacity_building",
            "local_communities",
            "other",
        ],
    },
}

TIME_ALIASES = {
    "immediate_2026": "immediate_next_week",
    "decade_2025_2034": "decade_scale",
}


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
            f"{key}:{item}" for key, item in value.items() if str(item).strip()
        )
    return str(value or "").strip()


def _inject_overview_styles() -> None:
    st.markdown(
        """
        <style>
        .wg2-overview-kicker {
            margin: 0 0 .45rem 0;
            font-family: var(--type-font-serif);
            font-size: clamp(1.15rem, 1.8vw, 1.35rem);
            line-height: 1.35;
            color: var(--type-soft);
        }
        .wg2-overview-title {
            margin: 0 0 1.1rem 0;
            max-width: min(780px, 100%);
            font-family: var(--type-font-sans);
            font-size: clamp(3rem, 7vw, 5.4rem);
            line-height: 1;
            font-weight: 700;
            letter-spacing: 0;
            color: var(--type-ink);
            text-wrap: balance;
        }
        .wg2-overview-lead {
            max-width: 760px;
            margin: 0 0 1.4rem 0;
            font-family: var(--type-font-sans);
            font-size: clamp(1.1rem, 1.6vw, 1.28rem);
            line-height: 1.55;
            color: var(--type-muted);
        }
        .wg2-early-signal {
            display: inline-flex;
            max-width: 760px;
            margin: .25rem 0 1.7rem 0;
            padding: .7rem .9rem;
            border: 1px solid rgba(19, 36, 52, .12);
            border-radius: .5rem;
            background: rgba(255, 255, 255, .62);
            color: var(--type-muted);
            font-family: var(--type-font-serif);
            font-size: 1rem;
            line-height: 1.45;
        }
        .wg2-section {
            margin-top: clamp(2.4rem, 6vw, 4rem);
            padding-top: 1.15rem;
            border-top: 1px solid rgba(19, 36, 52, .14);
        }
        .wg2-section-title {
            margin: 0 0 .45rem 0;
            font-family: var(--type-font-sans);
            font-size: clamp(1.65rem, 3vw, 2.25rem);
            line-height: 1.12;
            font-weight: 700;
            color: var(--type-ink);
        }
        .wg2-section-copy {
            max-width: 720px;
            margin: 0 0 1.35rem 0;
            font-size: 1.05rem;
            line-height: 1.55;
            color: var(--type-muted);
        }
        .wg2-dot-card {
            margin: 1rem 0 1.35rem 0;
            padding: 1rem;
            border: 1px solid rgba(19, 36, 52, .12);
            border-radius: .5rem;
            background: rgba(255, 255, 255, .68);
            box-shadow: 0 12px 34px rgba(19, 36, 52, .055);
        }
        .wg2-dot-title {
            margin: 0 0 .2rem 0;
            font-weight: 700;
            font-size: 1.08rem;
            color: var(--type-ink);
        }
        .wg2-dot-subtitle {
            margin: 0 0 .9rem 0;
            font-family: var(--type-font-serif);
            color: var(--type-muted);
            line-height: 1.4;
        }
        .wg2-dot-family {
            margin: .9rem 0 .45rem 0;
            font-family: var(--type-font-serif);
            font-size: .95rem;
            color: var(--type-soft);
        }
        .wg2-dot-row {
            display: grid;
            grid-template-columns: minmax(11rem, 1fr) minmax(9rem, 1fr) 2.25rem;
            gap: .75rem;
            align-items: center;
            padding: .22rem 0;
        }
        .wg2-dot-label {
            color: var(--type-ink);
            line-height: 1.3;
        }
        .wg2-dot-count {
            color: var(--type-muted);
            text-align: right;
            font-variant-numeric: tabular-nums;
        }
        .wg2-dot {
            display: inline-block;
            width: .68rem;
            height: .68rem;
            margin: 0 .12rem .12rem 0;
            border-radius: 999px;
            background: var(--conference-ink);
            vertical-align: middle;
        }
        .wg2-dot-empty {
            opacity: .16;
            outline: 1px solid var(--conference-ink);
            background: transparent;
        }
        .wg2-note-grid {
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(14rem, 1fr));
            gap: 1rem;
        }
        .wg2-note {
            padding: 1rem;
            border: 1px solid rgba(19, 36, 52, .12);
            border-radius: .5rem;
            background: rgba(255,255,255,.62);
        }
        .wg2-note-title {
            margin-bottom: .45rem;
            font-family: var(--type-font-serif);
            color: var(--type-soft);
        }
        .wg2-time-axis {
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(7.5rem, 1fr));
            gap: .55rem;
            margin-top: .85rem;
        }
        .wg2-time-item {
            min-height: 5.2rem;
            padding: .75rem;
            border: 1px solid rgba(19, 36, 52, .12);
            border-radius: .5rem;
            background: rgba(255,255,255,.64);
        }
        .wg2-time-count {
            margin-top: .55rem;
            font-size: 1.35rem;
            font-weight: 700;
            color: var(--type-ink);
        }
        .wg2-density-card {
            margin: 1.45rem 0 2rem 0;
            padding: 1rem;
            border: 1px solid rgba(19, 36, 52, .12);
            border-radius: .5rem;
            background: rgba(255,255,255,.7);
            box-shadow: 0 12px 34px rgba(19, 36, 52, .055);
        }
        .wg2-density-title {
            margin: 0 0 .2rem 0;
            font-size: 1.15rem;
            font-weight: 700;
            color: var(--type-ink);
        }
        .wg2-density-subtitle {
            max-width: 720px;
            margin: 0 0 1rem 0;
            font-family: var(--type-font-serif);
            color: var(--type-muted);
            line-height: 1.4;
        }
        .wg2-density-scroll {
            overflow-x: auto;
        }
        .wg2-density-table {
            width: 100%;
            min-width: 760px;
            border-collapse: collapse;
            font-size: .93rem;
        }
        .wg2-density-table th {
            padding: .55rem .45rem .65rem .45rem;
            border-bottom: 1px solid rgba(19, 36, 52, .16);
            text-align: left;
            font-family: var(--type-font-serif);
            font-size: .9rem;
            color: var(--type-soft);
            font-weight: 700;
        }
        .wg2-density-table td {
            padding: .55rem .45rem;
            border-bottom: 1px solid rgba(19, 36, 52, .08);
            color: var(--type-ink);
            vertical-align: top;
        }
        .wg2-density-table tr:last-child td {
            border-bottom: 0;
        }
        .wg2-density-question {
            max-width: 20rem;
            line-height: 1.32;
        }
        .wg2-density-muted {
            color: var(--type-muted);
        }
        .wg2-density-rate {
            display: flex;
            min-width: 9.2rem;
            gap: .55rem;
            align-items: center;
            font-variant-numeric: tabular-nums;
        }
        .wg2-density-bar {
            flex: 1;
            height: .46rem;
            overflow: hidden;
            border-radius: 999px;
            background: rgba(19, 36, 52, .12);
        }
        .wg2-density-fill {
            height: 100%;
            border-radius: 999px;
            background: var(--conference-ink);
        }
        .wg2-response-card {
            margin: 1.45rem 0 2rem 0;
            padding: 1rem;
            border: 1px solid rgba(19, 36, 52, .12);
            border-radius: .5rem;
            background: rgba(255,255,255,.72);
            box-shadow: 0 14px 38px rgba(19, 36, 52, .06);
        }
        .wg2-response-title {
            margin: 0 0 .25rem 0;
            font-size: clamp(1.35rem, 2.2vw, 1.75rem);
            line-height: 1.15;
            font-weight: 700;
            color: var(--type-ink);
        }
        .wg2-response-context,
        .wg2-response-math {
            max-width: 780px;
            margin: 0 0 .85rem 0;
            font-family: var(--type-font-serif);
            color: var(--type-muted);
            line-height: 1.42;
        }
        .wg2-response-math {
            padding: .68rem .78rem;
            border: 1px solid rgba(19, 36, 52, .1);
            border-radius: .42rem;
            background: rgba(246, 249, 251, .68);
            font-size: .95rem;
        }
        .wg2-response-controls {
            margin: .35rem 0 1rem 0;
        }
        .wg2-response-scroll {
            overflow-x: auto;
            padding-bottom: .25rem;
        }
        .wg2-response-table {
            border-collapse: separate;
            border-spacing: .28rem;
            min-width: 760px;
        }
        .wg2-response-table th,
        .wg2-response-table td {
            text-align: center;
            vertical-align: middle;
        }
        .wg2-response-participant,
        .wg2-response-corner {
            position: sticky;
            left: 0;
            z-index: 2;
            min-width: 4.8rem;
            padding: .18rem .45rem;
            background: rgba(255,255,255,.94);
            color: var(--type-muted);
            text-align: left !important;
            font-family: var(--type-font-serif);
            font-size: .88rem;
            font-variant-numeric: tabular-nums;
        }
        .wg2-response-corner {
            z-index: 3;
        }
        .wg2-response-section th {
            padding: .15rem .2rem .25rem .2rem;
            color: var(--type-soft);
            font-family: var(--type-font-serif);
            font-size: .82rem;
            font-weight: 700;
            border-bottom: 1px solid rgba(19, 36, 52, .14);
        }
        .wg2-response-q {
            min-width: 2.1rem;
            padding: .05rem .1rem .25rem .1rem;
            color: var(--type-muted);
            font-size: .72rem;
            font-weight: 700;
            letter-spacing: 0;
        }
        .wg2-response-cell {
            position: relative;
            width: 1.45rem;
            height: 1.45rem;
            border: 1px solid rgba(19, 36, 52, .16);
            border-radius: .18rem;
            color: #0f2433;
            font-size: .76rem;
            line-height: 1.45rem;
            font-weight: 700;
            overflow: hidden;
        }
        .wg2-response-cell[data-status="skipped"] {
            background:
                repeating-linear-gradient(
                    135deg,
                    rgba(19, 36, 52, .13),
                    rgba(19, 36, 52, .13) 2px,
                    rgba(255,255,255,.54) 2px,
                    rgba(255,255,255,.54) 5px
                ) !important;
        }
        .wg2-response-cell[data-status="viewed_unanswered"] {
            background: rgba(255,255,255,.4) !important;
            outline: 1px solid rgba(19, 36, 52, .38);
            outline-offset: -2px;
        }
        .wg2-response-cell[data-status="not_reached"] {
            background: transparent !important;
            border-color: rgba(19, 36, 52, .06);
            color: transparent;
        }
        .wg2-response-cell[data-flagged="true"]::after {
            content: "";
            position: absolute;
            top: 2px;
            right: 2px;
            width: .34rem;
            height: .34rem;
            border-radius: 999px;
            background: #5d4352;
        }
        .wg2-response-summary-row td,
        .wg2-response-summary-row th {
            padding-top: .45rem;
            color: var(--type-muted);
            font-family: var(--type-font-serif);
            font-size: .78rem;
            font-variant-numeric: tabular-nums;
        }
        .wg2-response-participant-summary {
            min-width: 5.2rem;
            color: var(--type-muted);
            font-family: var(--type-font-serif);
            font-size: .78rem;
            text-align: left !important;
        }
        .wg2-response-legend {
            display: flex;
            flex-wrap: wrap;
            gap: .7rem;
            margin-top: .7rem;
            color: var(--type-muted);
            font-family: var(--type-font-serif);
            font-size: .88rem;
        }
        .wg2-response-swatch {
            display: inline-block;
            width: .82rem;
            height: .82rem;
            margin-right: .25rem;
            border: 1px solid rgba(19, 36, 52, .16);
            border-radius: .16rem;
            vertical-align: -.1rem;
        }
        .wg2-timeline-card {
            margin: 1.45rem 0 2rem 0;
            padding: 1rem;
            border: 1px solid rgba(19, 36, 52, .12);
            border-radius: .5rem;
            background: rgba(255,255,255,.72);
            box-shadow: 0 14px 38px rgba(19, 36, 52, .06);
        }
        .wg2-timeline-title {
            margin: 0 0 .25rem 0;
            font-size: clamp(1.2rem, 2vw, 1.55rem);
            line-height: 1.15;
            font-weight: 700;
            color: var(--type-ink);
        }
        .wg2-timeline-context,
        .wg2-timeline-math {
            max-width: 780px;
            margin: 0 0 .85rem 0;
            font-family: var(--type-font-serif);
            color: var(--type-muted);
            line-height: 1.42;
        }
        .wg2-timeline-math {
            padding: .64rem .76rem;
            border: 1px solid rgba(19, 36, 52, .1);
            border-radius: .42rem;
            background: rgba(246, 249, 251, .68);
            font-size: .93rem;
        }
        .wg2-timeline-scroll {
            overflow-x: auto;
        }
        .wg2-timeline-svg {
            min-width: 760px;
            width: 100%;
            height: auto;
            display: block;
        }
        .wg2-timeline-axis {
            stroke: rgba(19, 36, 52, .32);
            stroke-width: 1;
        }
        .wg2-timeline-week {
            stroke: rgba(19, 36, 52, .08);
            stroke-width: 1;
        }
        .wg2-timeline-month {
            stroke: rgba(19, 36, 52, .2);
            stroke-width: 1;
        }
        .wg2-timeline-line {
            fill: none;
            stroke: #137f70;
            stroke-width: 3;
            stroke-linecap: round;
            stroke-linejoin: round;
        }
        .wg2-timeline-point {
            fill: #137f70;
            stroke: rgba(255,255,255,.92);
            stroke-width: 2;
        }
        .wg2-timeline-label {
            fill: var(--type-muted);
            font-family: var(--type-font-serif);
            font-size: 12px;
        }
        .wg2-timeline-ylabel {
            fill: var(--type-soft);
            font-family: var(--type-font-serif);
            font-size: 12px;
        }
        @media (max-width: 640px) {
            .wg2-dot-row {
                grid-template-columns: 1fr;
                gap: .25rem;
            }
            .wg2-dot-count {
                text-align: left;
            }
        }
        </style>
        """,
        unsafe_allow_html=True,
    )


def _question_by_field(resolved_bundle: Any, field: str) -> Any | None:
    token = str(field)
    for question in resolved_bundle.question_set.questions:
        if str(question.field) == token:
            return question
    return None


def _option_rows(resolved_bundle: Any, field: str) -> list[dict[str, str]]:
    question = _question_by_field(resolved_bundle, field)
    if not question:
        return []
    return [
        {
            "value": str(item.get("value") or ""),
            "label": str(item.get("label") or item.get("value") or ""),
        }
        for item in getattr(question, "options", ())
    ]


def _canonical_value(field: str, value: Any) -> str:
    token = str(value or "").strip()
    if not token:
        return ""
    return TIME_ALIASES.get(token, token) if field == "wg2_timescale" else token


def _field_values(item: dict[str, Any], field: str) -> list[str]:
    value = item.get(field)
    if isinstance(value, list):
        return [
            _canonical_value(field, entry)
            for entry in value
            if _canonical_value(field, entry)
        ]
    token = _canonical_value(field, value)
    return [token] if token else []


def _has_answer(value: Any) -> bool:
    if isinstance(value, dict):
        return any(_has_answer(item) for item in value.values())
    if isinstance(value, list):
        return any(_has_answer(item) for item in value)
    return bool(str(value or "").strip())


def _field_counts(submissions: list[dict[str, Any]], field: str) -> Counter[str]:
    counter: Counter[str] = Counter()
    for item in submissions:
        counter.update(_field_values(item, field))
    return counter


def _answer_count(submissions: list[dict[str, Any]], resolved_bundle: Any) -> int:
    total = 0
    for item in submissions:
        for question in resolved_bundle.question_set.questions:
            value = item.get(str(question.field))
            if _has_answer(value):
                total += 1
    return total


def _active_questions(resolved_bundle: Any) -> list[Any]:
    question_set = resolved_bundle.question_set
    mode = str(getattr(question_set, "default_mode", "") or "quick")
    flow_modes = getattr(question_set, "flow_modes", {}) or {}
    flow = flow_modes.get(mode, {}) if isinstance(flow_modes, dict) else {}
    ordered_steps = [str(step) for step in flow.get("steps", [])]
    by_step = {str(question.step): question for question in question_set.questions}
    ordered = [by_step[step] for step in ordered_steps if step in by_step]
    if ordered:
        return ordered
    return list(question_set.questions)


def _question_section(resolved_bundle: Any, step: str) -> str:
    copy = getattr(resolved_bundle.question_set, "step_copy", {}) or {}
    section = copy.get(str(step), {}) if isinstance(copy, dict) else {}
    return str(section.get("section") or section.get("title") or "Question")


def _question_flag_counts(submissions: list[dict[str, Any]]) -> Counter[str]:
    counts: Counter[str] = Counter()
    for item in submissions:
        payload = item.get("question_flags")
        if not isinstance(payload, dict):
            continue
        for question_id, detail in payload.items():
            if detail:
                counts[str(question_id)] += 1
    return counts


def _deferred_counts_by_question(
    submissions: list[dict[str, Any]],
    resolved_bundle: Any,
) -> Counter[str]:
    field_to_question = {
        str(question.field): str(question.question_id or "")
        for question in resolved_bundle.question_set.questions
    }
    counts: Counter[str] = Counter()
    for item in submissions:
        deferred = item.get("deferred_fields")
        if not isinstance(deferred, list):
            continue
        for field in deferred:
            question_id = field_to_question.get(str(field))
            if question_id:
                counts[question_id] += 1
    return counts


def _logged_skip_counts(events: list[dict[str, Any]]) -> Counter[str]:
    counts: Counter[str] = Counter()
    for event in events:
        if str(event.get("event_type") or "") != "question_skipped":
            continue
        metadata = event.get("metadata")
        if not isinstance(metadata, dict):
            metadata = {}
        question_id = str(
            event.get("item_id")
            or metadata.get("question_id")
            or metadata.get("field")
            or ""
        ).strip()
        if question_id:
            counts[question_id] += 1
    return counts


def _text_density(text: Any) -> float:
    length = len(str(text or "").strip())
    if length == 0:
        return 0.0
    if length <= 20:
        return 0.25
    if length <= 80:
        return 0.5
    if length <= 200:
        return 0.75
    return 1.0


def _effective_multi_max(question: Any) -> int:
    declared = getattr(question, "max_select", None)
    if declared:
        return max(int(declared), 1)
    options = getattr(question, "options", ()) or ()
    return max(min(len(options), 5), 1)


def _geography_density(value: Any) -> float:
    location = _parse_location(value)
    completed = 0
    if str(
        location.get("country_region") or location.get("geocode_label") or ""
    ).strip():
        completed += 1
    if str(location.get("institution_location") or "").strip():
        completed += 1
    return completed / 2


def _question_response_density(
    item: dict[str, Any],
    question: Any,
) -> tuple[float, int | None, int | None]:
    field = str(question.field)
    value = item.get(field)
    input_type = str(question.input_type or "single")
    free_text_field = str(getattr(question, "free_text_field", "") or "").strip()
    free_text = item.get(free_text_field) if free_text_field else None
    text_length = (
        len(str(free_text or value or "").strip())
        if input_type == "text" or free_text_field
        else None
    )

    if input_type == "multi":
        selection_count = len(_field_values(item, field))
        selection_density = min(selection_count / _effective_multi_max(question), 1.0)
        if free_text_field:
            return (
                min(0.75 * selection_density + 0.25 * _text_density(free_text), 1.0),
                selection_count,
                len(str(free_text or "").strip()),
            )
        return selection_density, selection_count, None
    if input_type == "text":
        text = str(value or "").strip()
        return _text_density(text), None, len(text)
    if input_type == "scale":
        return (1.0 if _has_answer(value) else 0.0), None, None
    if input_type == "geography_context":
        return _geography_density(value), None, None
    return (1.0 if _has_answer(value) else 0.0), None, None


def _participant_token(item: dict[str, Any], index: int) -> str:
    token = str(
        item.get("participant_id")
        or item.get("player_id")
        or item.get("access_key")
        or item.get("access_key_last4")
        or ""
    ).strip()
    return token or f"participant-{index:02d}"


def build_response_field_records(
    submissions: list[dict[str, Any]],
    resolved_bundle: Any,
) -> list[dict[str, Any]]:
    questions = _active_questions(resolved_bundle)
    records: list[dict[str, Any]] = []
    for participant_index, item in enumerate(
        sorted(submissions, key=lambda row: str(row.get("submitted_at") or "")),
        start=1,
    ):
        participant_id = _participant_token(item, participant_index)
        participant_label = f"P{participant_index:02d}"
        flags = item.get("question_flags")
        question_flags = flags if isinstance(flags, dict) else {}
        deferred_fields = {
            str(field) for field in item.get("deferred_fields", []) if str(field)
        }
        signal_orders: list[int] = []
        completed_submission = bool(str(item.get("submitted_at") or "").strip())
        for order, question in enumerate(questions, start=1):
            field = str(question.field)
            question_id = str(question.question_id or "")
            flagged = question_id in question_flags
            skipped = field in deferred_fields
            answered = _has_answer(item.get(field))
            if answered or skipped or flagged:
                signal_orders.append(order)
        last_signal_order = max(signal_orders, default=0)

        for order, question in enumerate(questions, start=1):
            field = str(question.field)
            question_id = str(question.question_id or "")
            flagged = question_id in question_flags
            skipped = field in deferred_fields
            answered = _has_answer(item.get(field))
            reached = completed_submission or order <= last_signal_order
            if answered:
                status = "answered"
            elif skipped:
                status = "skipped"
            elif reached:
                status = "viewed_unanswered"
            else:
                status = "not_reached"
            density, selection_count, text_length = _question_response_density(
                item, question
            )
            if status != "answered":
                density = 0.0
            records.append(
                {
                    "participant_id": participant_id,
                    "participant_label": participant_label,
                    "question_id": question_id,
                    "question_order": order,
                    "section": _question_section(resolved_bundle, str(question.step)),
                    "input_type": str(question.input_type or "single"),
                    "status": status,
                    "response_density": max(0.0, min(float(density), 1.0)),
                    "selection_count": selection_count,
                    "text_length": text_length,
                    "flagged": flagged,
                    "skipped": skipped,
                    "reached": reached,
                    "updated_at": str(item.get("submitted_at") or "") or None,
                }
            )
    return records


def _parse_location(value: Any) -> dict[str, str]:
    if isinstance(value, dict):
        return {str(key): str(item or "") for key, item in value.items()}
    if isinstance(value, str) and value.strip().startswith("{"):
        try:
            parsed = ast.literal_eval(value)
        except Exception:
            parsed = {}
        if isinstance(parsed, dict):
            return {str(key): str(item or "") for key, item in parsed.items()}
    return {}


def _base_locations(
    submissions: list[dict[str, Any]],
) -> tuple[Counter[str], list[dict[str, float | str]]]:
    places: Counter[str] = Counter()
    pinned_locations: dict[tuple[float, float, str], dict[str, float | str | int]] = {}
    for item in submissions:
        location = _parse_location(item.get("wg2_main_location"))
        label = (
            location.get("country_region")
            or location.get("geocode_label")
            or location.get("institution_location")
            or ""
        ).strip()
        if label:
            places[label] += 1
        coordinates = str(location.get("coordinates") or "").strip()
        consent = str(location.get("coordinates_consent") or "").strip().lower()
        if coordinates and consent in {"lookup", "manual"}:
            try:
                lat_text, lon_text = [
                    part.strip() for part in coordinates.split(",", 1)
                ]
                lat = round(float(lat_text), 4)
                lng = round(float(lon_text), 4)
                pin_label = label or "WG2 base location"
                key = (lat, lng, pin_label)
                current = pinned_locations.setdefault(
                    key,
                    {"lat": lat, "lng": lng, "name": pin_label, "count": 0},
                )
                current["count"] = int(current.get("count", 0)) + 1
            except Exception:
                pass
    points: list[dict[str, float | str]] = []
    for item in pinned_locations.values():
        count = int(item.get("count", 0))
        label = str(item.get("name") or "WG2 base location")
        suffix = "participant" if count == 1 else "participants"
        points.append(
            {
                "lat": float(item["lat"]),
                "lng": float(item["lng"]),
                "energy": float(8 + count * 8),
                "count": float(count),
                "name": f"{label} · {count} {suffix}",
            }
        )
    return places, points


def _globe_camera(points: list[dict[str, float | str]]) -> tuple[float, float, float]:
    if not points:
        return 20.0, 0.0, 1.75
    latitudes = [float(point["lat"]) for point in points]
    longitudes = [float(point["lng"]) for point in points]
    lat_span = max(latitudes) - min(latitudes) if len(latitudes) > 1 else 0.0
    lng_span = max(longitudes) - min(longitudes) if len(longitudes) > 1 else 0.0
    altitude = 1.25
    if max(lat_span, lng_span) > 90:
        altitude = 1.85
    elif max(lat_span, lng_span) > 35:
        altitude = 1.55
    return (
        statistics.mean(latitudes),
        statistics.mean(longitudes),
        altitude,
    )


def _parse_submitted_at(value: Any) -> datetime | None:
    token = str(value or "").strip()
    if not token:
        return None
    if token.endswith("Z"):
        token = f"{token[:-1]}+00:00"
    try:
        parsed = datetime.fromisoformat(token)
    except ValueError:
        return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


def _cumulative_submission_points(
    submissions: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    timestamps = [
        parsed
        for parsed in (
            _parse_submitted_at(item.get("submitted_at")) for item in submissions
        )
        if parsed is not None
    ]
    timestamps.sort()
    return [
        {"timestamp": timestamp, "cumulative": index}
        for index, timestamp in enumerate(timestamps, start=1)
    ]


def _floor_to_monday(value: datetime) -> datetime:
    date_value = value.date()
    monday = date_value - timedelta(days=date_value.weekday())
    return datetime.combine(monday, datetime.min.time(), tzinfo=timezone.utc)


def _ceil_to_next_monday(value: datetime) -> datetime:
    start = _floor_to_monday(value)
    if start >= value:
        return start
    return start + timedelta(days=7)


def _month_start(value: datetime) -> datetime:
    return datetime(value.year, value.month, 1, tzinfo=timezone.utc)


def _next_month(value: datetime) -> datetime:
    if value.month == 12:
        return datetime(value.year + 1, 1, 1, tzinfo=timezone.utc)
    return datetime(value.year, value.month + 1, 1, tzinfo=timezone.utc)


def _timeline_domain(points: list[dict[str, Any]]) -> tuple[datetime, datetime]:
    first = points[0]["timestamp"]
    last = points[-1]["timestamp"]
    start = _floor_to_monday(first)
    end = _ceil_to_next_monday(last)
    if end <= start:
        end = start + timedelta(days=7)
    return start, end


def _timeline_week_ticks(start: datetime, end: datetime) -> list[datetime]:
    ticks: list[datetime] = []
    cursor = start
    while cursor <= end:
        ticks.append(cursor)
        cursor += timedelta(days=7)
    return ticks


def _timeline_month_ticks(start: datetime, end: datetime) -> list[datetime]:
    ticks: list[datetime] = []
    cursor = _month_start(start)
    if cursor < start:
        cursor = _next_month(cursor)
    while cursor <= end:
        ticks.append(cursor)
        cursor = _next_month(cursor)
    return ticks


def _timeline_x(
    value: datetime,
    start: datetime,
    end: datetime,
    *,
    left: float,
    width: float,
) -> float:
    span = max((end - start).total_seconds(), 1.0)
    return left + ((value - start).total_seconds() / span) * width


def _render_opening(
    submissions: list[dict[str, Any]], resolved_bundle: Any, last_updated: str
) -> None:
    st.markdown(
        """
        <div class="wg2-overview-kicker">Working Group 2 · First Iteration</div>
        <h1 class="wg2-overview-title">Collective Visibility</h1>
        <div class="wg2-overview-lead">
            This first module maps who is present, where expertise sits, what support is needed,
            and where coordination could create value. The picture is preliminary and will become
            more meaningful as participation grows.
        </div>
        """,
        unsafe_allow_html=True,
    )
    if len(submissions) < 10:
        st.markdown(
            '<div class="wg2-early-signal">Early signal · interpret distributions as indicative that _something works_, not representative of the room.</div>',
            unsafe_allow_html=True,
        )
    metrics = st.columns(4)
    metrics[0].metric("Participants", len(submissions))
    metrics[1].metric("Completed submissions", len(submissions))
    metrics[2].metric("Questions answered", _answer_count(submissions, resolved_bundle))
    metrics[3].metric("Last contribution", last_updated)


def _density_color(value: float) -> str:
    value = max(0.0, min(float(value), 1.0))
    start = (244, 248, 250)
    end = (15, 36, 51)
    rgb = tuple(
        round(start[index] + (end[index] - start[index]) * value) for index in range(3)
    )
    return f"rgb({rgb[0]}, {rgb[1]}, {rgb[2]})"


def _compact_question_label(question: Any, order: int) -> str:
    subgroup = str(getattr(question, "subgroup", "") or "").strip()
    if subgroup:
        return subgroup[:3].upper()
    return f"Q{order}"


def _section_spans(questions: list[Any], resolved_bundle: Any) -> list[tuple[str, int]]:
    spans: list[tuple[str, int]] = []
    for question in questions:
        section = _question_section(resolved_bundle, str(question.step))
        if spans and spans[-1][0] == section:
            spans[-1] = (section, spans[-1][1] + 1)
        else:
            spans.append((section, 1))
    return spans


def _summarize_question_records(
    records: list[dict[str, Any]],
) -> dict[str, dict[str, Any]]:
    grouped: dict[str, list[dict[str, Any]]] = {}
    for record in records:
        grouped.setdefault(str(record["question_id"]), []).append(record)
    summary: dict[str, dict[str, Any]] = {}
    for question_id, rows in grouped.items():
        answered = [row for row in rows if row["status"] == "answered"]
        summary[question_id] = {
            "coverage": len(answered) / len(rows) if rows else 0.0,
            "average_density": statistics.mean(
                float(row["response_density"]) for row in answered
            )
            if answered
            else 0.0,
            "skip_count": sum(1 for row in rows if row["skipped"]),
            "flag_count": sum(1 for row in rows if row["flagged"]),
        }
    return summary


def _summarize_participant_records(
    records: list[dict[str, Any]],
) -> dict[str, dict[str, Any]]:
    grouped: dict[str, list[dict[str, Any]]] = {}
    for record in records:
        grouped.setdefault(str(record["participant_id"]), []).append(record)
    summary: dict[str, dict[str, Any]] = {}
    for participant_id, rows in grouped.items():
        answered = [row for row in rows if row["status"] == "answered"]
        reached = [row for row in rows if row["reached"]]
        summary[participant_id] = {
            "answered": len(answered),
            "reached": len(reached),
            "average_density": statistics.mean(
                float(row["response_density"]) for row in answered
            )
            if answered
            else 0.0,
            "skip_count": sum(1 for row in rows if row["skipped"]),
            "flag_count": sum(1 for row in rows if row["flagged"]),
            "first_updated": min(
                (str(row["updated_at"] or "") for row in rows if row.get("updated_at")),
                default="",
            ),
            "last_updated": max(
                (str(row["updated_at"] or "") for row in rows if row.get("updated_at")),
                default="",
            ),
        }
    return summary


def _response_field_interpretation(records: list[dict[str, Any]]) -> str:
    if not records:
        return ""
    question_summary = _summarize_question_records(records)
    participant_summary = _summarize_participant_records(records)
    supported: list[str] = []
    section_rows: dict[str, list[dict[str, Any]]] = {}
    for row in records:
        section_rows.setdefault(str(row["section"]), []).append(row)
    section_density = {
        section: statistics.mean(float(row["response_density"]) for row in rows)
        for section, rows in section_rows.items()
        if rows
    }
    if section_density:
        strongest = max(section_density, key=section_density.get)
        weakest = min(section_density, key=section_density.get)
        if section_density[strongest] > 0:
            supported.append(
                f"Response bandwidth is currently strongest in {strongest}."
            )
        if section_density[strongest] - section_density[weakest] >= 0.2:
            supported.append(f"{weakest} currently receives less response bandwidth.")
    flagged = sum(int(item["flag_count"]) for item in question_summary.values())
    skipped = sum(int(item["skip_count"]) for item in question_summary.values())
    if flagged:
        supported.append(
            f"{flagged} flag or skip-note marker(s) are visible in the field."
        )
    if skipped:
        supported.append(
            f"{skipped} deliberate skip marker(s) are visible in the field."
        )
    complete = sum(
        1
        for item in participant_summary.values()
        if item["reached"] and item["answered"] == item["reached"]
    )
    if complete:
        supported.append(
            f"{complete} participant row(s) have answered every reached question."
        )
    return " ".join(supported[:4])


def _render_response_field(
    submissions: list[dict[str, Any]],
    resolved_bundle: Any,
) -> None:
    if not submissions:
        return
    questions = _active_questions(resolved_bundle)
    records = build_response_field_records(submissions, resolved_bundle)
    if not records:
        return

    with st.container():
        st.markdown('<div class="wg2-response-controls">', unsafe_allow_html=True)
        sort_col, filter_col = st.columns([1, 1])
        with sort_col:
            sort_mode = st.selectbox(
                "Sort participants",
                [
                    "First contribution time",
                    "Most complete first",
                    "Most recent first",
                ],
                key="wg2_response_field_sort",
            )
        with filter_col:
            focus_mode = st.selectbox(
                "Show",
                ["All rows", "Rows with skips", "Rows with flags"],
                key="wg2_response_field_focus",
            )
        st.markdown("</div>", unsafe_allow_html=True)

    participant_summary = _summarize_participant_records(records)
    participant_ids = list(dict.fromkeys(str(row["participant_id"]) for row in records))
    if sort_mode == "Most complete first":
        participant_ids.sort(
            key=lambda token: (
                int(participant_summary[token]["answered"]),
                float(participant_summary[token]["average_density"]),
            ),
            reverse=True,
        )
    elif sort_mode == "Most recent first":
        participant_ids.sort(
            key=lambda token: participant_summary[token]["last_updated"], reverse=True
        )

    if focus_mode == "Rows with skips":
        participant_ids = [
            token
            for token in participant_ids
            if int(participant_summary[token]["skip_count"])
        ]
    elif focus_mode == "Rows with flags":
        participant_ids = [
            token
            for token in participant_ids
            if int(participant_summary[token]["flag_count"])
        ]

    question_summary = _summarize_question_records(records)
    record_by_pair = {
        (str(row["participant_id"]), str(row["question_id"])): row for row in records
    }
    question_by_id = {
        str(question.question_id or ""): question for question in questions
    }

    header = ['<table class="wg2-response-table">']
    header.append(
        '<thead><tr class="wg2-response-section"><th class="wg2-response-corner"></th>'
    )
    for section, span in _section_spans(questions, resolved_bundle):
        header.append(f'<th colspan="{span}">{html.escape(section)}</th>')
    header.append('<th></th></tr><tr><th class="wg2-response-corner">Participant</th>')
    for order, question in enumerate(questions, start=1):
        question_id = str(question.question_id or "")
        summary = question_summary.get(question_id, {})
        title = (
            f"{_question_section(resolved_bundle, str(question.step))}\n"
            f"{question.prompt}\n"
            f"Type: {question.input_type}\n"
            f"Coverage: {float(summary.get('coverage', 0.0)):.0%}\n"
            f"Avg density: {float(summary.get('average_density', 0.0)):.2f}\n"
            f"Skips: {int(summary.get('skip_count', 0))}\n"
            f"Flags: {int(summary.get('flag_count', 0))}"
        )
        header.append(
            f'<th class="wg2-response-q" title="{html.escape(title)}">'
            f"{html.escape(_compact_question_label(question, order))}</th>"
        )
    header.append(
        '<th class="wg2-response-participant-summary">Summary</th></tr></thead>'
    )

    body = ["<tbody>"]
    for participant_id in participant_ids:
        participant_records = [
            record
            for record in records
            if str(record["participant_id"]) == participant_id
        ]
        label = (
            str(participant_records[0]["participant_label"])
            if participant_records
            else participant_id
        )
        summary = participant_summary[participant_id]
        body.append(
            f'<tr><th class="wg2-response-participant">{html.escape(label)}</th>'
        )
        for question in questions:
            question_id = str(question.question_id or "")
            record = record_by_pair.get((participant_id, question_id))
            if not record:
                body.append(
                    '<td><div class="wg2-response-cell" data-status="missing" title="Missing record"></div></td>'
                )
                continue
            question_obj = question_by_id.get(question_id, question)
            density = float(record["response_density"])
            symbol = "x" if record["skipped"] else ""
            title = (
                f"Participant: {record['participant_label']}\n"
                f"Question: {question_obj.prompt}\n"
                f"Input type: {record['input_type']}\n"
                f"Status: {record['status']}\n"
                f"Response density: {density:.2f}\n"
                f"Selections: {record['selection_count'] if record['selection_count'] is not None else 'n/a'}\n"
                f"Text length: {record['text_length'] if record['text_length'] is not None else 'n/a'}\n"
                f"Flagged: {'yes' if record['flagged'] else 'no'}\n"
                f"Skipped: {'yes' if record['skipped'] else 'no'}"
            )
            body.append(
                "<td>"
                f'<div class="wg2-response-cell" '
                f'data-status="{html.escape(str(record["status"]))}" '
                f'data-flagged="{str(bool(record["flagged"])).lower()}" '
                f'title="{html.escape(title)}" '
                f'style="background:{_density_color(density)}">{symbol}</div>'
                "</td>"
            )
        body.append(
            '<td class="wg2-response-participant-summary">'
            f"{int(summary['answered'])}/{int(summary['reached'])} · "
            f"{float(summary['average_density']):.2f} · "
            f"S{int(summary['skip_count'])} F{int(summary['flag_count'])}"
            "</td></tr>"
        )
    body.append(
        '<tr class="wg2-response-summary-row"><th class="wg2-response-participant">Coverage</th>'
    )
    for question in questions:
        summary = question_summary.get(str(question.question_id or ""), {})
        body.append(
            '<td title="Question coverage, average density, skips, flags">'
            f"{float(summary.get('coverage', 0.0)):.0%}<br>"
            f"{float(summary.get('average_density', 0.0)):.2f}<br>"
            f"S{int(summary.get('skip_count', 0))} F{int(summary.get('flag_count', 0))}"
            "</td>"
        )
    body.append(
        '<td class="wg2-response-participant-summary">Answered<br>density<br>skips flags</td></tr>'
    )
    body.append("</tbody></table>")

    interpretation = _response_field_interpretation(records)
    if interpretation:
        interpretation_html = (
            f'<div class="wg2-response-math">{html.escape(interpretation)}</div>'
        )
    else:
        interpretation_html = ""
    st.markdown(
        """
        <div class="wg2-response-card">
            <div class="wg2-response-title">Response Field</div>
            <div class="wg2-response-context">
                Each cell represents one participant answering one question. Intensity shows response extent,
                while marks identify skips and flags. It does not measure answer quality.
            </div>
            <div class="wg2-response-math">
                Math: single choice and scale responses count as 1 when answered; multi-select responses are
                selections divided by YAML max_select; text responses use capped length buckets; geography uses
                completed non-sensitive location fields and excludes optional coordinates.
            </div>
            <div class="wg2-response-math">
                This view describes the current pilot response field; it is not yet representative of WG2 as a whole.
            </div>
            <div class="wg2-response-scroll">
        """
        + "\n".join(header + body)
        + """
            </div>
            <div class="wg2-response-legend">
                <span><span class="wg2-response-swatch" style="background:rgb(244,248,250)"></span>none/minimal</span>
                <span><span class="wg2-response-swatch" style="background:rgb(130,144,154)"></span>medium</span>
                <span><span class="wg2-response-swatch" style="background:rgb(15,36,51)"></span>substantial</span>
                <span>x = skipped</span>
                <span>corner dot = flagged / note</span>
                <span>outline = viewed unanswered</span>
            </div>
        """
        + interpretation_html
        + """
        </div>
        """,
        unsafe_allow_html=True,
    )


def _render_response_timeline(submissions: list[dict[str, Any]]) -> None:
    points = _cumulative_submission_points(submissions)
    if not points:
        return
    start, end = _timeline_domain(points)
    width = 980
    height = 260
    left = 58
    right = 24
    top = 28
    bottom = 54
    plot_width = width - left - right
    plot_height = height - top - bottom
    max_y = max(int(points[-1]["cumulative"]), 1)

    def y_pos(value: int) -> float:
        return top + plot_height - (value / max_y) * plot_height

    week_lines = []
    for tick in _timeline_week_ticks(start, end):
        x = _timeline_x(tick, start, end, left=left, width=plot_width)
        week_lines.append(
            f'<line class="wg2-timeline-week" x1="{x:.1f}" y1="{top}" x2="{x:.1f}" y2="{top + plot_height}" />'
        )
    month_lines = []
    for tick in _timeline_month_ticks(start, end):
        x = _timeline_x(tick, start, end, left=left, width=plot_width)
        month_lines.append(
            f'<line class="wg2-timeline-month" x1="{x:.1f}" y1="{top}" x2="{x:.1f}" y2="{top + plot_height + 8}" />'
            f'<text class="wg2-timeline-label" x="{x + 4:.1f}" y="{height - 14}">{html.escape(tick.strftime("%b %Y"))}</text>'
        )

    y_ticks = sorted({0, max_y, max_y // 2 if max_y > 1 else 1})
    y_tick_markup = []
    for value in y_ticks:
        y = y_pos(value)
        y_tick_markup.append(
            f'<line class="wg2-timeline-week" x1="{left}" y1="{y:.1f}" x2="{width - right}" y2="{y:.1f}" />'
            f'<text class="wg2-timeline-ylabel" x="{left - 10}" y="{y + 4:.1f}" text-anchor="end">{value}</text>'
        )

    path_parts = []
    point_markup = []
    previous_x = None
    previous_y = None
    for point in points:
        timestamp = point["timestamp"]
        cumulative = int(point["cumulative"])
        x = _timeline_x(timestamp, start, end, left=left, width=plot_width)
        y = y_pos(cumulative)
        if not path_parts:
            path_parts.append(f"M {x:.1f} {y:.1f}")
        else:
            path_parts.append(f"L {x:.1f} {previous_y:.1f} L {x:.1f} {y:.1f}")
        previous_x = x
        previous_y = y
        title = f"Submission {cumulative}\\n{timestamp.strftime('%Y-%m-%d %H:%M UTC')}\\nCumulative activity: {cumulative}"
        point_markup.append(
            f'<circle class="wg2-timeline-point" cx="{x:.1f}" cy="{y:.1f}" r="5.5">'
            f"<title>{html.escape(title)}</title>"
            "</circle>"
        )
    if previous_x is not None and previous_y is not None:
        path_parts.append(f"L {width - right:.1f} {previous_y:.1f}")

    svg = (
        f'<svg class="wg2-timeline-svg" viewBox="0 0 {width} {height}" role="img" '
        'aria-label="Cumulative WG2 icebreaker submissions over time">'
        + "".join(week_lines)
        + "".join(month_lines)
        + "".join(y_tick_markup)
        + f'<line class="wg2-timeline-axis" x1="{left}" y1="{top + plot_height}" x2="{width - right}" y2="{top + plot_height}" />'
        + f'<line class="wg2-timeline-axis" x1="{left}" y1="{top}" x2="{left}" y2="{top + plot_height}" />'
        + f'<text class="wg2-timeline-ylabel" x="18" y="{top + 6}" transform="rotate(-90 18 {top + 6})">Cumulative activity</text>'
        + f'<path class="wg2-timeline-line" d="{" ".join(path_parts)}" />'
        + "".join(point_markup)
        + "</svg>"
    )

    st.markdown(
        """
        <div class="wg2-timeline-card">
            <div class="wg2-timeline-title">Response Timeline</div>
            <div class="wg2-timeline-context">
                Cumulative activity for WG2 icebreaker submissions only. Weekly guide lines show cadence;
                month labels mark the broader time structure.
            </div>
            <div class="wg2-timeline-math">
                Math: submissions are sorted by submitted_at within the WG2 session scope. The plotted value is
                the running count of submitted response bundles, so the curve only increases.
            </div>
            <div class="wg2-timeline-scroll">
        """
        + svg
        + """
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )


def _render_question_density(
    submissions: list[dict[str, Any]],
    resolved_bundle: Any,
    events: list[dict[str, Any]],
) -> None:
    total = len(submissions)
    if not total:
        return
    flag_counts = _question_flag_counts(submissions)
    deferred_counts = _deferred_counts_by_question(submissions, resolved_bundle)
    logged_skip_counts = _logged_skip_counts(events)
    rows: list[str] = []
    for index, question in enumerate(_active_questions(resolved_bundle), start=1):
        question_id = str(question.question_id or "")
        field = str(question.field)
        answered = sum(1 for item in submissions if _has_answer(item.get(field)))
        rate = answered / total if total else 0
        skip_count = max(
            int(logged_skip_counts.get(question_id, 0)),
            int(deferred_counts.get(question_id, 0)),
        )
        flag_count = int(flag_counts.get(question_id, 0))
        density = "—"
        if str(question.input_type) == "multi":
            selection_counts = [len(_field_values(item, field)) for item in submissions]
            average = statistics.mean(selection_counts) if selection_counts else 0.0
            deviation = (
                statistics.pstdev(selection_counts)
                if len(selection_counts) > 1
                else 0.0
            )
            density = f"{average:.1f} ± {deviation:.1f}"
        rows.append(
            "<tr>"
            f"<td>{index}</td>"
            f"<td class='wg2-density-muted'>{html.escape(_question_section(resolved_bundle, str(question.step)))}</td>"
            f"<td class='wg2-density-question'>{html.escape(str(question.prompt or field))}</td>"
            "<td>"
            "<div class='wg2-density-rate'>"
            f"<span>{answered}/{total}</span>"
            "<div class='wg2-density-bar'>"
            f"<div class='wg2-density-fill' style='width:{rate * 100:.0f}%'></div>"
            "</div>"
            "</div>"
            "</td>"
            f"<td>{skip_count}</td>"
            f"<td>{flag_count}</td>"
            f"<td>{html.escape(density)}</td>"
            "</tr>"
        )
    st.markdown(
        """
        <div class="wg2-density-card">
            <div class="wg2-density-title">Question Density</div>
            <div class="wg2-density-subtitle">
                Completion by active YAML question, with skips from the event log and stored flag/skip notes from submitted bundles.
                Multi-select density reports the average number of selected options per participant, plus population standard deviation.
            </div>
            <div class="wg2-density-scroll">
                <table class="wg2-density-table">
                    <thead>
                        <tr>
                            <th>#</th>
                            <th>Block</th>
                            <th>Question</th>
                            <th>Completion</th>
                            <th>Skips</th>
                            <th>Flags / notes</th>
                            <th>Multi-select avg</th>
                        </tr>
                    </thead>
                    <tbody>
        """
        + "\n".join(rows)
        + """
                    </tbody>
                </table>
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )


def _render_section(title: str, copy: str) -> None:
    st.markdown(
        f"""
        <section class="wg2-section">
            <h2 class="wg2-section-title">{html.escape(title)}</h2>
            <div class="wg2-section-copy">{html.escape(copy)}</div>
        </section>
        """,
        unsafe_allow_html=True,
    )


def _dot_markup(count: int, total: int) -> str:
    active = "".join('<span class="wg2-dot"></span>' for _ in range(max(count, 0)))
    empty = "".join(
        '<span class="wg2-dot wg2-dot-empty"></span>'
        for _ in range(max(total - count, 0))
    )
    return active + empty


def _render_dot_field(
    *,
    title: str,
    subtitle: str,
    field: str,
    submissions: list[dict[str, Any]],
    resolved_bundle: Any,
    families: dict[str, list[str]] | None = None,
) -> None:
    counts = _field_counts(submissions, field)
    option_rows = _option_rows(resolved_bundle, field)
    label_by_value = {row["value"]: row["label"] for row in option_rows}
    ordered_values = [row["value"] for row in option_rows]
    grouped = families or {"Selections": ordered_values}
    lines = [
        '<div class="wg2-dot-card">',
        f'<div class="wg2-dot-title">{html.escape(title)}</div>',
        f'<div class="wg2-dot-subtitle">{html.escape(subtitle)}</div>',
    ]
    for family, values in grouped.items():
        family_values = [value for value in values if value in label_by_value]
        if not family_values:
            continue
        lines.append(f'<div class="wg2-dot-family">{html.escape(family)}</div>')
        for value in family_values:
            count = int(counts.get(value, 0))
            lines.append(
                '<div class="wg2-dot-row">'
                f'<div class="wg2-dot-label">{html.escape(label_by_value[value])}</div>'
                f"<div>{_dot_markup(count, len(submissions))}</div>"
                f'<div class="wg2-dot-count">{count}</div>'
                "</div>"
            )
    lines.append("</div>")
    st.markdown("\n".join(lines), unsafe_allow_html=True)


def _render_time_axis(submissions: list[dict[str, Any]], resolved_bundle: Any) -> None:
    counts = _field_counts(submissions, "wg2_timescale")
    cards = [
        '<div class="wg2-dot-card">',
        '<div class="wg2-dot-title">Time horizons</div>',
        '<div class="wg2-dot-subtitle">Ordered as a temporal axis, including aliases from earlier submissions.</div>',
        '<div class="wg2-time-axis">',
    ]
    for row in _option_rows(resolved_bundle, "wg2_timescale"):
        value = row["value"]
        cards.append(
            '<div class="wg2-time-item">'
            f"<div>{html.escape(row['label'])}</div>"
            f'<div class="wg2-time-count">{int(counts.get(value, 0))}</div>'
            "</div>"
        )
    cards.append("</div></div>")
    st.markdown("\n".join(cards), unsafe_allow_html=True)


def _render_text_entries(text_entries: list[tuple[str, str]]) -> None:
    if not text_entries:
        summary_card("Open reflections", "No free-text signals yet.")
        return
    lines = ['<div class="wg2-note-grid">']
    for title, text in text_entries:
        lines.append(
            f"""
            <div class="wg2-note">
                <div class="wg2-note-title">{html.escape(title)}</div>
                <div>{html.escape(text)}</div>
            </div>
            """
        )
    lines.append("</div>")
    st.markdown("\n".join(lines), unsafe_allow_html=True)


def _export_rows(
    submissions: list[dict[str, Any]], resolved_bundle: Any
) -> list[dict[str, str]]:
    rows: list[dict[str, str]] = []
    export_fields = {
        str(field)
        for field in (
            *resolved_bundle.question_set.profile_fields,
            *resolved_bundle.question_set.session_fields,
        )
        if str(field)
        not in {"question_flags", "identity_reveal_targets", "boiler_room_contribution"}
    }
    for item in submissions:
        row = {
            "submitted_at": str(item.get("submitted_at") or ""),
            "access_key_last4": str(item.get("access_key_last4") or ""),
        }
        for question in resolved_bundle.question_set.questions:
            field = str(question.field)
            if field not in export_fields:
                continue
            row[field] = _stringify(item.get(field))
            free_text_field = str(
                getattr(question, "free_text_field", "") or ""
            ).strip()
            if free_text_field:
                row[free_text_field] = _stringify(item.get(free_text_field))
        rows.append(row)
    return rows


def _text_question_entries(
    submissions: list[dict[str, Any]], resolved_bundle: Any
) -> list[tuple[str, str]]:
    entries: list[tuple[str, str]] = []
    for question in resolved_bundle.question_set.questions:
        if str(question.input_type) != "text":
            continue
        title = str(
            resolved_bundle.question_set.step_copy.get(str(question.step), {}).get(
                "title"
            )
            or question.prompt
        )
        for item in sorted(
            submissions,
            key=lambda row: str(row.get("submitted_at") or ""),
            reverse=True,
        ):
            text = str(item.get(question.field) or "").strip()
            if text:
                entries.append((title, text))
    return entries


def _flag_count(submissions: list[dict[str, Any]]) -> int:
    total = 0
    for item in submissions:
        payload = item.get("question_flags")
        if isinstance(payload, dict):
            total += len(payload)
    return total


def main() -> None:
    set_page()
    apply_conference_styles()
    _inject_overview_styles()

    repo = get_conference_repo()
    if not repo or not repo.is_ready():
        st.error(
            repo.unavailable_reason if repo else "Conference repository is unavailable."
        )
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
            "current_page": "un_wg2_overview",
            "event_log_page": "un_wg2_overview",
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
            "event_specific_question_count": len(
                resolved_bundle.event_specific_question_ids
            ),
            "question_ids": list(resolved_bundle.question_ids),
            "shared_question_ids": list(resolved_bundle.shared_question_ids),
            "event_specific_question_ids": list(
                resolved_bundle.event_specific_question_ids
            ),
        }
    )

    response_rows = repo.get_session_rows(
        str(session.get("id") or ""),
        text_ids=text_ids_for_session_code(str(session.get("session_code") or "")),
    )
    filtered_rows = filter_rows_to_session_window(response_rows, session)
    submissions = repo.group_rows_by_submission(filtered_rows)
    logged_events = list_logged_events(
        page="conference",
        session_id=str(session.get("id") or ""),
        limit=500,
    )
    exportable_rows = _export_rows(submissions, resolved_bundle)
    text_entries = _text_question_entries(submissions, resolved_bundle)
    flags = _flag_count(submissions)
    last_updated = (
        max((str(item.get("submitted_at") or "") for item in submissions), default="")
        or "—"
    )

    log_event(
        module="iceicebaby.un_wg2",
        event_type="overview_loaded",
        page="un_wg2_overview",
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

    _render_opening(submissions, resolved_bundle, last_updated)
    _render_response_field(submissions, resolved_bundle)
    _render_response_timeline(submissions)
    _render_question_density(submissions, resolved_bundle, logged_events)

    identity_block = "\n".join(
        [
            "campaign_slug = un-cryosphere-decade",
            f"event_slug = {resolved_bundle.event_slug}",
            f"session_code = {resolved_bundle.session_code}",
            f"text_id = {resolved_bundle.text_id}",
            f"question_set_id = {resolved_bundle.question_set_id}",
            f"schema_id = {resolved_bundle.schema_id}",
        ]
    )

    if not submissions:
        summary_card(
            "Blank state",
            "No UN WG2 submissions yet. Once participants answer the pilot route, the collective mirror will appear here.",
        )
    else:
        _render_section(
            "I. Who is speaking?",
            "What kinds of people, capacities, and working styles are currently visible in this first WG2 signal?",
        )
        _render_dot_field(
            title="Roles and lenses",
            subtitle="Each dot is one participant selection.",
            field="wg2_role_lens",
            submissions=submissions,
            resolved_bundle=resolved_bundle,
            families=FIELD_FAMILIES["wg2_role_lens"],
        )
        _render_dot_field(
            title="Capability constellation",
            subtitle="Areas where current experience could help WG2 build, interpret, translate, or use projections.",
            field="wg2_expertise",
            submissions=submissions,
            resolved_bundle=resolved_bundle,
            families=FIELD_FAMILIES["wg2_expertise"],
        )
        _render_dot_field(
            title="How this group tends to work",
            subtitle="A working ecology, not a ranking of personalities.",
            field="wg2_work_style",
            submissions=submissions,
            resolved_bundle=resolved_bundle,
            families=FIELD_FAMILIES["wg2_work_style"],
        )

        _render_section(
            "II. Spatial context",
            "Separate where people are based from where their work is situated. A participant can connect from one place and work on another region or cryosphere system.",
        )
        places, points = _base_locations(submissions)
        place_text = (
            ", ".join(f"{place} ({count})" for place, count in places.most_common())
            if places
            else "No declared base locations yet."
        )
        summary_card("Where we connect from", html.escape(place_text))
        if points:
            camera_lat, camera_lng, camera_altitude = _globe_camera(points)
            cracks_globe_block(
                points,
                height=560,
                key="wg2-base-location-globe",
                auto_rotate_speed=0.45,
                camera_lat=camera_lat,
                camera_lng=camera_lng,
                camera_altitude=camera_altitude,
                point_color="#137f70",
                point_value_label="Participants",
            )
        _render_dot_field(
            title="Where our work is situated",
            subtitle="Regional focus is distinct from where participants are based.",
            field="wg2_region",
            submissions=submissions,
            resolved_bundle=resolved_bundle,
        )
        _render_dot_field(
            title="Cryosphere domains",
            subtitle="Systems where current work, expertise, or decision context is focused.",
            field="wg2_cryosphere_domain",
            submissions=submissions,
            resolved_bundle=resolved_bundle,
        )

        _render_section(
            "III. Collective needs",
            "This section compares what WG2 needs to coordinate better with where individual members are asking for support.",
        )
        left, right = st.columns(2)
        with left:
            _render_dot_field(
                title="What WG2 needs",
                subtitle="Collective coordination needs.",
                field="wg2_needs",
                submissions=submissions,
                resolved_bundle=resolved_bundle,
            )
        with right:
            _render_dot_field(
                title="Where members need support",
                subtitle="Individual support requests that coordination could reduce.",
                field="wg2_support_needs",
                submissions=submissions,
                resolved_bundle=resolved_bundle,
            )

        _render_section(
            "IV. Projection-to-decision interfaces",
            "The operational core: where projections should inform decisions, who they should serve, what uncertainty guidance is needed, and which time horizons matter.",
        )
        _render_dot_field(
            title="Where projections should connect to decisions",
            subtitle="Decision interfaces grouped by family.",
            field="wg2_policy_interface",
            submissions=submissions,
            resolved_bundle=resolved_bundle,
            families=FIELD_FAMILIES["wg2_policy_interface"],
        )
        _render_dot_field(
            title="Who projections should serve",
            subtitle="Stakeholders and audiences currently visible in the first signal.",
            field="wg2_stakeholder_group",
            submissions=submissions,
            resolved_bundle=resolved_bundle,
        )
        _render_dot_field(
            title="What must be made clearer?",
            subtitle="Uncertainty guidance requested by participants.",
            field="wg2_uncertainty_need",
            submissions=submissions,
            resolved_bundle=resolved_bundle,
        )
        _render_time_axis(submissions, resolved_bundle)

        _render_section(
            "V. Immediate coordination signals",
            "Open responses are kept as short traces. They are not interpreted as consensus.",
        )
        _render_text_entries(text_entries)

    with st.expander("Operator scope and export", expanded=False):
        st.code(identity_block, language="text")
        st.caption(f"Flagged questions: {flags}")
        if exportable_rows:
            st.download_button(
                "Download UN WG2 CSV",
                data=_csv_payload(exportable_rows),
                file_name="un_wg2_v1_export.csv",
                mime="text/csv",
                type="primary",
                use_container_width=True,
            )
        else:
            st.caption("No UN WG2 submissions yet.")


if __name__ == "__main__":
    main()
