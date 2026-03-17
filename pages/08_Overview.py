from __future__ import annotations

from datetime import datetime

import altair as alt
import pandas as pd
import streamlit as st

from infra.app_context import get_notion_repo, load_config
from infra.event_logger import log_event, get_module_logger
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


def _render_bar(
    title: str,
    counts: dict,
    *,
    horizontal: bool = True,
    height: int = 260,
) -> None:
    rows = _counts_rows(counts)
    if not rows:
        st.caption(f"{title}: no data yet.")
        return
    df = pd.DataFrame(rows)
    if horizontal:
        chart = (
            alt.Chart(df)
            .mark_bar()
            .encode(
                x=alt.X("value:Q", title="Count"),
                y=alt.Y("id:N", sort="-x", title=None),
                tooltip=["id:N", "value:Q"],
            )
            .properties(title=title, height=height)
        )
    else:
        chart = (
            alt.Chart(df)
            .mark_bar()
            .encode(
                x=alt.X("id:N", sort="-y", title=None),
                y=alt.Y("value:Q", title="Count"),
                tooltip=["id:N", "value:Q"],
            )
            .properties(title=title, height=height)
        )
    st.altair_chart(chart, use_container_width=True)


def _render_signal_timeline(title: str, timeline: list[dict]) -> None:
    points = []
    for item in timeline or []:
        t = item.get("t")
        y = item.get("score")
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
        .mark_line(point=True)
        .encode(
            x=alt.X("t:T", title="Time"),
            y=alt.Y("score:Q", title="Score"),
            tooltip=[alt.Tooltip("t:T", title="Time"), "score:Q"],
        )
        .properties(title=title, height=260)
    )
    st.altair_chart(chart, use_container_width=True)


def _question_lookup(payload: dict) -> dict[str, dict]:
    return {str(q.get("item_id", "")): q for q in payload.get("questions", [])}


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
    qmap = _question_lookup(payload)
    st.subheader("Collective entry signal")
    sig = qmap.get("ORGANISATION_SIGNAL")
    if sig:
        _render_bar("Organisation signal", sig.get("counts", {}), horizontal=False)
        _render_signal_timeline("Organisation signal timeline", sig.get("timeline", []))
    else:
        st.caption("No organisation signal data yet.")

    st.subheader("Emotional field")
    for item_id, title in [
        ("ARRIVAL_EMOTION", "Arrival emotion"),
        ("ENVIRONMENT_CHANGE_EMOTION", "Emotion toward environmental change"),
        ("SOCIETAL_CHANGE_EMOTION", "Emotion toward societal change"),
    ]:
        q = qmap.get(item_id)
        if q:
            _render_bar(title, q.get("counts", {}), horizontal=True)

    st.subheader("Position and readiness")
    for item_id, title in [
        ("COLLABORATION_READINESS", "Collaboration readiness"),
        ("PERSONAL_AGENCY", "Personal agency"),
    ]:
        q = qmap.get(item_id)
        if q:
            _render_bar(title, q.get("counts", {}), horizontal=True)

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
