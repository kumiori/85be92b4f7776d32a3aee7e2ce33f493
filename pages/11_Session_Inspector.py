from __future__ import annotations

import json
from collections import Counter
from typing import Any, Dict, List

import pandas as pd
import streamlit as st

from infra.app_context import get_notion_repo
from infra.event_logger import get_module_logger, log_event
from models.catalog import QUESTION_CATALOG, QUESTION_BY_ID
from services.aggregator import get_overview_payload
from services.response_reader import fetch_session_responses
from ui import apply_theme, heading, set_page

LOGGER = get_module_logger("iceicebaby.session_inspector")

REPORT_ITEM_IDS = {
    "ARRIVAL_EMOTION",
    "ENVIRONMENT_CHANGE_EMOTION",
    "SOCIETAL_CHANGE_EMOTION",
    "ORGANISATION_SIGNAL",
    "COLLABORATION_READINESS",
}


def _slugify(value: str) -> str:
    return "-".join(
        part
        for part in "".join(
            ch.lower() if ch.isalnum() else "-" for ch in str(value or "")
        ).split("-")
        if part
    )


def _sessions() -> List[Dict[str, Any]]:
    repo = get_notion_repo()
    if not repo:
        return []
    sessions = repo.list_sessions(limit=200)
    return sorted(
        sessions,
        key=lambda s: (
            int(s.get("session_order", 999)),
            str(s.get("session_code", "")).upper(),
        ),
    )


def _catalog_questions_for_session(session_code: str) -> List[Dict[str, Any]]:
    target = str(session_code or "").strip().upper()
    questions = [q for q in QUESTION_CATALOG if str(q.session_id).upper() == target]
    questions.sort(key=lambda q: (int(getattr(q, "order", 9999) or 9999), str(q.id)))
    return [
        {
            "item_id": q.id,
            "order": int(getattr(q, "order", 0) or 0),
            "prompt": str(getattr(q, "prompt", "")),
            "question_type": str(getattr(q, "qtype", "")),
            "response_mode": str(getattr(q, "response_mode", "") or getattr(q, "response_type", "")),
            "required": bool(getattr(q, "required", False)),
            "active": bool(getattr(q, "active", False)),
            "visible_before_lobby": bool(getattr(q, "visible_before_lobby", False)),
        }
        for q in questions
    ]


def _row_actor(row: Dict[str, Any]) -> str:
    player_id = str(row.get("player_id") or "").strip()
    if player_id:
        return f"player:{player_id}"
    device_id = str(row.get("device_id") or "").strip()
    if device_id:
        return f"device:{device_id}"
    response_id = str(row.get("response_id") or "").strip()
    if response_id:
        return f"response:{response_id}"
    return "unknown"


def _rows_dataframe(rows: List[Dict[str, Any]]) -> pd.DataFrame:
    out: List[Dict[str, Any]] = []
    for row in rows:
        value_json = row.get("value_json")
        out.append(
            {
                "submitted_at": row.get("submitted_at") or row.get("timestamp"),
                "item_id": row.get("item_id"),
                "question_type": row.get("question_type"),
                "player_id": row.get("player_id"),
                "device_id": row.get("device_id"),
                "actor": _row_actor(row),
                "value_label": row.get("value_label"),
                "response_value": json.dumps(
                    row.get("response_value"), ensure_ascii=False
                )
                if not isinstance(row.get("response_value"), str)
                else row.get("response_value"),
                "score": row.get("score"),
                "parse_error": bool(
                    isinstance(value_json, dict) and value_json.get("parse_error")
                ),
                "value_json": json.dumps(value_json, ensure_ascii=False),
            }
        )
    return pd.DataFrame(out)


def _item_coverage(
    session_code: str,
    rows: List[Dict[str, Any]],
    payload: Dict[str, Any],
) -> pd.DataFrame:
    catalog = _catalog_questions_for_session(session_code)
    row_counts = Counter(str(r.get("item_id") or "") for r in rows)
    actor_counts: Dict[str, set[str]] = {}
    type_counts: Dict[str, Counter[str]] = {}
    latest_ts: Dict[str, str] = {}
    for row in rows:
        item_id = str(row.get("item_id") or "")
        if not item_id:
            continue
        actor_counts.setdefault(item_id, set()).add(_row_actor(row))
        qtype = str(row.get("question_type") or "").strip()
        type_counts.setdefault(item_id, Counter())[qtype or ""] += 1
        ts = str(row.get("submitted_at") or row.get("timestamp") or "")
        if ts and ts > latest_ts.get(item_id, ""):
            latest_ts[item_id] = ts

    aggregate_map = {
        str(q.get("item_id") or ""): q for q in payload.get("questions", []) if q
    }
    all_items = set(row_counts.keys()) | set(aggregate_map.keys()) | {
        str(c.get("item_id")) for c in catalog
    }
    rows_out: List[Dict[str, Any]] = []
    for item_id in sorted(
        all_items,
        key=lambda item: (
            int(getattr(QUESTION_BY_ID.get(item), "order", 9999) or 9999),
            item,
        ),
    ):
        q = QUESTION_BY_ID.get(item_id)
        cat = next((c for c in catalog if c["item_id"] == item_id), None)
        agg = aggregate_map.get(item_id) or {}
        observed_types = ", ".join(
            f"{k or '∅'}:{v}" for k, v in sorted(type_counts.get(item_id, Counter()).items())
        )
        rows_out.append(
            {
                "item_id": item_id,
                "order": int(getattr(q, "order", cat["order"] if cat else 9999) or 9999),
                "prompt": str(getattr(q, "prompt", cat["prompt"] if cat else item_id)),
                "in_catalog": bool(cat),
                "catalog_active": bool(cat["active"]) if cat else False,
                "raw_rows": int(row_counts.get(item_id, 0)),
                "unique_actors": int(len(actor_counts.get(item_id, set()))),
                "observed_types": observed_types,
                "latest_submission": latest_ts.get(item_id, ""),
                "in_aggregate": bool(agg),
                "aggregate_chart_type": str(agg.get("chart_type") or ""),
                "aggregate_question_type": str(agg.get("question_type") or ""),
                "shown_in_report": item_id in REPORT_ITEM_IDS,
            }
        )
    return pd.DataFrame(rows_out)


def _report_gap_dataframe(coverage_df: pd.DataFrame) -> pd.DataFrame:
    if coverage_df.empty:
        return coverage_df
    return coverage_df[
        (coverage_df["raw_rows"] > 0) & (~coverage_df["shown_in_report"])
    ].sort_values(by=["order", "item_id"], ascending=[True, True])


def _aggregate_dataframe(payload: Dict[str, Any]) -> pd.DataFrame:
    rows: List[Dict[str, Any]] = []
    for block in payload.get("questions", []) or []:
        counts = block.get("counts")
        entries = block.get("entries")
        timeline = block.get("timeline")
        rows.append(
            {
                "item_id": block.get("item_id"),
                "question_type": block.get("question_type"),
                "chart_type": block.get("chart_type"),
                "n_responses": block.get("n_responses"),
                "n_events": block.get("n_events"),
                "counts_keys": ", ".join(sorted((counts or {}).keys())) if isinstance(counts, dict) else "",
                "entries": len(entries or []),
                "timeline_points": len(timeline or []),
            }
        )
    return pd.DataFrame(rows)


def main() -> None:
    set_page()
    apply_theme()
    heading("Test · Session inspector")
    st.caption(
        "Internal diagnostic page. Per session, inspect raw rows, aggregate blocks, and what the Report currently renders."
    )

    sessions = _sessions()
    if not sessions:
        st.error("No sessions are available.")
        return

    session_map = {_slugify(s.get("session_code") or ""): s for s in sessions}
    options = list(session_map.keys())
    default_slug = "global-session" if "global-session" in options else options[0]

    selected_slug = st.selectbox(
        "Session",
        options=options,
        index=options.index(default_slug),
        key="session_inspector_session",
        format_func=lambda slug: (session_map.get(slug) or {}).get("session_code", slug),
        bind="query-params",
    )
    session = session_map[selected_slug]
    session_code = str(session.get("session_code") or "")

    log_event(
        module="iceicebaby.session_inspector",
        event_type="page_view",
        page="Session inspector",
        session_id=str(session.get("id") or ""),
        player_id=str(st.session_state.get("player_page_id", "")),
        device_id=str(st.session_state.get("anon_token", "")),
        metadata={"session_code": session_code},
    )

    with st.spinner("Loading session data…"):
        resolved_session, rows = fetch_session_responses(selected_slug)
        payload = get_overview_payload(selected_slug)

    coverage_df = _item_coverage(session_code, rows, payload)
    report_gap_df = _report_gap_dataframe(coverage_df)
    rows_df = _rows_dataframe(rows)
    agg_df = _aggregate_dataframe(payload)
    parse_errors = int(rows_df["parse_error"].sum()) if not rows_df.empty else 0
    unique_actors = int(rows_df["actor"].nunique()) if not rows_df.empty else 0

    m1, m2, m3, m4, m5 = st.columns(5)
    m1.metric("Raw rows", len(rows))
    m2.metric("Unique actors", unique_actors)
    m3.metric("Item IDs seen", int(coverage_df["item_id"].nunique()) if not coverage_df.empty else 0)
    m4.metric("Aggregate blocks", len(payload.get("questions", []) or []))
    m5.metric("Parse errors", parse_errors)

    st.subheader("Session metadata")
    st.json(resolved_session or session)

    tabs = st.tabs(
        [
            "Coverage",
            "Raw rows",
            "Aggregate blocks",
            "Report gap",
            "Raw JSON samples",
        ]
    )

    with tabs[0]:
        st.markdown(
            "This table compares the session catalogue, the raw stored rows, and the aggregate blocks now available."
        )
        st.dataframe(
            coverage_df.sort_values(by=["order", "item_id"], ascending=[True, True]),
            width="stretch",
            height=520,
        )

    with tabs[1]:
        st.markdown(
            "Normalised response rows as currently read from the interaction repository."
        )
        st.dataframe(
            rows_df.sort_values(by=["submitted_at", "item_id"], ascending=[False, True])
            if not rows_df.empty
            else pd.DataFrame(),
            width="stretch",
            height=520,
        )

    with tabs[2]:
        st.markdown(
            "Aggregate blocks currently produced by `aggregate_session()` for this session."
        )
        st.dataframe(agg_df, width="stretch", height=360)
        if payload.get("questions"):
            selected_item = st.selectbox(
                "Inspect aggregate block",
                options=[str(q.get("item_id") or "") for q in payload.get("questions", []) if q],
                key="session_inspector_aggregate_item",
            )
            block = next(
                (q for q in payload.get("questions", []) if str(q.get("item_id") or "") == selected_item),
                {},
            )
            st.json(block)

    with tabs[3]:
        st.markdown(
            "These item IDs have raw rows in this session but are not currently rendered by the Report page."
        )
        if report_gap_df.empty:
            st.success("No gap detected: every item with raw rows is represented in the current Report subset.")
        else:
            st.dataframe(report_gap_df, width="stretch", height=420)

    with tabs[4]:
        st.markdown(
            "Sample of the raw normalised row payloads, useful for checking fields exhaustively."
        )
        sample_size = st.slider(
            "Sample size",
            min_value=1,
            max_value=max(1, min(25, len(rows))),
            value=min(5, max(1, len(rows))),
            key="session_inspector_sample_size",
        )
        for row in rows[:sample_size]:
            st.json(row)


if __name__ == "__main__":
    main()
