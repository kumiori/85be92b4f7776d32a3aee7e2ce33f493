from __future__ import annotations

from datetime import datetime

import altair as alt
import pandas as pd
import streamlit as st

from infra.app_context import get_notion_repo, load_config
from infra.event_logger import log_event, get_module_logger
from models.catalog import QUESTION_BY_ID
from services.aggregator import get_overview_payload
from services.presence import count_active_users
from ui import apply_theme, heading, set_page, sidebar_debug_state


def _slugify(value: str) -> str:
    return "-".join(
        part
        for part in "".join(
            ch.lower() if ch.isalnum() else "-" for ch in str(value or "")
        ).split("-")
        if part
    )


def _counts_rows(counts: dict) -> list[dict]:
    rows = [{"id": str(k), "value": int(v)} for k, v in (counts or {}).items()]
    rows.sort(key=lambda x: x["value"], reverse=True)
    return rows


def _feedback_label(raw: str) -> str:
    token = str(raw or "").strip().lower()
    mapping = {
        "faces:0": "😞 Very difficult",
        "faces:1": "🙁 Difficult",
        "faces:2": "😐 Mixed",
        "faces:3": "🙂 Positive",
        "faces:4": "😄 Very positive",
    }
    return mapping.get(token, raw)


def _render_bar(
    title: str,
    counts: dict,
    *,
    horizontal: bool = True,
    height: int = 260,
    label_transform=None,
) -> None:
    rows = _counts_rows(counts)
    if label_transform:
        for row in rows:
            row["id"] = str(label_transform(row["id"]))
    if not rows:
        st.caption(f"{title}: no data yet.")
        return
    df = pd.DataFrame(rows)
    if horizontal:
        chart = (
            alt.Chart(df)
            .mark_bar()
            .encode(
                x=alt.X("value:Q", title="Count", axis=alt.Axis(format="d")),
                y=alt.Y("id:N", sort="-x", title=None),
                tooltip=["id:N", alt.Tooltip("value:Q", format=".0f")],
            )
            .properties(title=title, height=height)
        )
    else:
        chart = (
            alt.Chart(df)
            .mark_bar()
            .encode(
                x=alt.X("id:N", sort="-y", title=None),
                y=alt.Y("value:Q", title="Count", axis=alt.Axis(format="d")),
                tooltip=["id:N", alt.Tooltip("value:Q", format=".0f")],
            )
            .properties(title=title, height=height)
        )
    st.altair_chart(chart, width="stretch")


def _render_signal_timeline(title: str, timeline: list[dict]) -> None:
    points = []
    for item in timeline or []:
        t = item.get("t")
        y = item.get("cumulative", item.get("score"))
        if t is None or y is None:
            continue
        try:
            dt = datetime.fromisoformat(str(t).replace("Z", "+00:00"))
        except Exception:
            continue
        points.append({"t": dt, "score": float(y)})
    points.sort(key=lambda x: x["t"])
    if not points:
        st.caption(f"{title}: no timeline yet.")
        return
    df = pd.DataFrame(points)
    chart = (
        alt.Chart(df)
        .mark_circle(size=180)
        .encode(
            x=alt.X("t:T", title="Time"),
            y=alt.Y("score:Q", title="Score", axis=alt.Axis(format="d")),
            tooltip=[alt.Tooltip("t:T", title="Time"), alt.Tooltip("score:Q", format=".0f")],
        )
        .properties(title=title, height=260)
    )
    st.altair_chart(chart, width="stretch")


def _render_signal_glyphs(counts: dict) -> None:
    yes_n = int((counts or {}).get("yes", 0))
    maybe_n = int((counts or {}).get("maybe", 0))
    no_n = int((counts or {}).get("no", 0))

    def _block(color: str, n: int) -> str:
        if n <= 0:
            return ""
        circles = "".join(
            f"<span style='display:inline-block;width:42px;height:42px;border-radius:50%;background:{color};margin:3px;'></span>"
            for _ in range(n)
        )
        return f"<span style='display:inline-flex;flex-wrap:wrap;max-width:100%;margin-right:10px'>{circles}</span>"

    html = (
        "<div style='display:flex;flex-wrap:wrap;align-items:center;gap:8px'>"
        f"{_block('#2e7d32', yes_n)}"
        f"{_block('#fbc02d', maybe_n)}"
        f"{_block('#c62828', no_n)}"
        "</div>"
    )
    st.markdown(html, unsafe_allow_html=True)
    st.caption("Legend: green = yes · yellow = maybe · red = no")


def _question_lookup(payload: dict) -> dict[str, dict]:
    return {str(q.get("item_id", "")): q for q in payload.get("questions", [])}


def _question_order(item_id: str) -> int:
    q = QUESTION_BY_ID.get(str(item_id or ""))
    if not q:
        return 9999
    try:
        return int(getattr(q, "order", 9999) or 9999)
    except Exception:
        return 9999


def _question_title(item_id: str, fallback: str = "") -> str:
    q = QUESTION_BY_ID.get(str(item_id or ""))
    if q and getattr(q, "prompt", None):
        return str(q.prompt)
    return fallback or str(item_id or "Question")


def _render_question_prompt(item_id: str) -> None:
    q = QUESTION_BY_ID.get(item_id)
    if q:
        st.caption(f"Question: {q.prompt}")
    else:
        st.caption(f"Question ID: {item_id}")


def main() -> None:
    set_page()
    apply_theme()
    sidebar_debug_state()

    cfg = load_config() or {}
    overview_cfg = cfg.get("overview") or {}
    window = int(overview_cfg.get("active_user_window_minutes", 10))
    show_debug_json = bool(overview_cfg.get("show_debug_json", True))

    heading("Live Map of the Room")
    st.caption("Signals, momentum, distribution, convergence, hesitation.")
    log_event(
        module="iceicebaby.overview",
        event_type="page_view",
        page="Overview",
        player_id=str(st.session_state.get("player_page_id", "")),
        session_id=str(st.session_state.get("session_id", "")),
        device_id=str(st.session_state.get("anon_token", "")),
        status="ok",
    )

    repo = get_notion_repo()
    sessions = repo.list_sessions(limit=200) if repo else []
    sessions = sorted(
        sessions,
        key=lambda s: (
            int(s.get("session_order", 999)),
            str(s.get("session_code", "")).upper(),
        ),
    )
    session_labels = [s.get("session_code") or "Session" for s in sessions]
    session_map = {_slugify(s.get("session_code") or ""): s for s in sessions}
    default_slug = _slugify(
        str(overview_cfg.get("default_session_slug") or "global-session")
    )
    options = list(session_map.keys()) or [default_slug]
    default_index = options.index(default_slug) if default_slug in options else 0

    selected_slug = st.selectbox(
        "Session",
        options=options,
        index=default_index,
        format_func=lambda slug: (session_map.get(slug) or {}).get(
            "session_code", slug
        ),
    )

    payload = get_overview_payload(selected_slug)
    if not payload:
        get_module_logger("iceicebaby.overview").warning("overview payload empty")
    log_event(
        module="iceicebaby.overview",
        event_type="overview_loaded",
        page="Overview",
        player_id=str(st.session_state.get("player_page_id", "")),
        session_id=str((session_map.get(selected_slug) or {}).get("id", "")),
        device_id=str(st.session_state.get("anon_token", "")),
        status="ok",
        value_label=str(selected_slug),
        metadata={"question_count": len(payload.get("questions", []))},
    )
    active_global = count_active_users(window)
    sessions_active = sum(
        1
        for s in sessions
        if bool(s.get("session_active", s.get("active")))
        or (s.get("status") or "").lower() == "active"
    )

    c1, c2, c3, c4 = st.columns(4)
    c1.metric(f"Active in last {window} min", str(active_global))
    c2.metric("Participants", str(payload.get("participant_count", 0)))
    c3.metric("Responses", str(payload.get("response_count", 0)))
    c4.metric("Sessions active", str(sessions_active))
    st.caption("Only logged-in participants are counted as active.")

    if show_debug_json:
        with st.expander("Debug JSON", expanded=False):
            st.json(payload)
    ordered_questions = sorted(
        payload.get("questions", []),
        key=lambda q: (
            _question_order(str(q.get("item_id", ""))),
            str(q.get("item_id", "")),
        ),
    )

    st.subheader("Session signals (question order)")
    if not ordered_questions:
        st.caption("No aggregated question data yet.")

    for q in ordered_questions:
        item_id = str(q.get("item_id", ""))
        chart_type = str(q.get("chart_type", ""))
        with st.container(border=True):
            if item_id == "ORGANISATION_SIGNAL":
                st.markdown("**Collective entry signal**")
                _render_question_prompt(item_id)
                _render_signal_glyphs(q.get("counts", {}))
                _render_signal_timeline(
                    "Collective signal over time", q.get("timeline", [])
                )
                continue

            _render_question_prompt(item_id)

            if chart_type in {
                "emotion_frequency",
                "choice_distribution",
                "signal_distribution",
            }:
                label_transform = _feedback_label if item_id == "FINAL_FEEDBACK" else None
                _render_bar(
                    _question_title(item_id, item_id),
                    q.get("counts", {}),
                    horizontal=True,
                    label_transform=label_transform,
                )
                if item_id == "FINAL_FEEDBACK":
                    st.caption(
                        "Feedback scale: 😞 very difficult · 🙁 difficult · 😐 mixed · 🙂 positive · 😄 very positive"
                    )
                continue

            if chart_type == "latest_text":
                st.markdown(f"**{_question_title(item_id, item_id)}**")
                entries = q.get("entries", []) or []
                if not entries:
                    st.caption("No text entries yet.")
                for entry in entries[:10]:
                    st.markdown(f"- {str(entry.get('text') or '').strip()}")
                continue

            st.caption(
                f"No dedicated renderer for chart_type='{chart_type}'. Showing raw block."
            )
            st.json(q)

    with st.expander("Developer blocks", expanded=False):
        for q in payload.get("questions", []):
            with st.container(border=True):
                st.markdown(f"**{q.get('item_id', 'UNKNOWN_ITEM')}**")
                st.caption(
                    f"chart_type: {q.get('chart_type', '')} · question_type: {q.get('question_type', '')}"
                )
                st.json(q)


if __name__ == "__main__":
    main()
