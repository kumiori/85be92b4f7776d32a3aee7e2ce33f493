from __future__ import annotations

import streamlit as st

from infra.app_context import get_notion_repo, load_config
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


def main() -> None:
    set_page()
    apply_theme()
    sidebar_debug_state()

    cfg = load_config() or {}
    overview_cfg = cfg.get("overview") or {}
    window = int(overview_cfg.get("active_user_window_minutes", 10))
    show_debug_json = bool(overview_cfg.get("show_debug_json", True))

    heading("Overview · Collective Mirror")
    st.caption("Signals, momentum, distribution, convergence, hesitation.")

    repo = get_notion_repo()
    sessions = repo.list_sessions(limit=200) if repo else []
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
    active_global = count_active_users(window)
    sessions_active = sum(
        1 for s in sessions if (s.get("status") or "").lower() == "active"
    )

    c1, c2, c3, c4 = st.columns(4)
    c1.metric(f"Active in last {window} min", str(active_global))
    c2.metric("Participants", str(payload.get("participant_count", 0)))
    c3.metric("Responses", str(payload.get("response_count", 0)))
    c4.metric("Sessions active", str(sessions_active))
    st.caption("Only logged-in participants are counted as active.")

    if show_debug_json:
        with st.expander("Debug JSON", expanded=True):
            st.json(payload)

    st.subheader("Chart-ready blocks")
    for q in payload.get("questions", []):
        with st.container(border=True):
            st.markdown(f"**{q.get('item_id', 'UNKNOWN_ITEM')}**")
            st.caption(
                f"chart_type: {q.get('chart_type', '')} · question_type: {q.get('question_type', '')}"
            )
            if "counts" in q:
                st.json(q.get("counts", {}))
            elif "entries" in q:
                st.json(q.get("entries", []))
            else:
                st.json(q)


if __name__ == "__main__":
    main()
