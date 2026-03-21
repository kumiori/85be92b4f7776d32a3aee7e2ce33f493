from __future__ import annotations

from datetime import datetime
from typing import Any, Dict, List

import streamlit as st

from infra.app_context import get_authenticator, get_notion_repo
from infra.app_state import (
    ensure_auth,
    ensure_session_context,
    ensure_session_state,
    remember_access,
    require_login,
)
from repositories.interaction_repo import NotionInteractionRepository
from ui import apply_theme, heading, microcopy, set_page, sidebar_debug_state


def _interaction_repo(repo) -> NotionInteractionRepository:
    notion_cfg = st.secrets.get("notion", {})
    db_id = (
        notion_cfg.get("ice_interaction_responses_db_id")
        or notion_cfg.get("interaction_responses_db_id")
        or notion_cfg.get("ice_responses_db_id")
        or ""
    )
    if not db_id:
        raise ValueError("Missing interaction responses DB id in secrets.")
    return NotionInteractionRepository(repo, str(db_id))


def _score_from_choice(choice: Any) -> int | None:
    if not isinstance(choice, str):
        return None
    txt = choice.strip().lower()
    if txt.startswith("yes"):
        return 1
    if "maybe" in txt:
        return 0
    if txt.startswith("no"):
        return -1
    return None


def _extract_player_rows(
    rows: List[Dict[str, Any]],
    *,
    player_page_id: str,
    player_access_key: str,
) -> List[Dict[str, Any]]:
    out: List[Dict[str, Any]] = []
    for row in rows:
        pid = str(row.get("player_id") or "").strip()
        if pid and pid == player_page_id:
            out.append(row)
            continue
        raw_access = str(row.get("access_key") or "").strip()
        if raw_access and player_access_key and raw_access == player_access_key:
            out.append(row)
    return out


def main() -> None:
    set_page()
    apply_theme()
    ensure_session_state()
    repo = get_notion_repo()
    authenticator = get_authenticator(repo)
    ensure_auth(authenticator, callback=remember_access, key="player-dashboard-login")
    ensure_session_context(repo)
    require_login()
    sidebar_debug_state()

    heading("Your trajectory")
    microcopy(
        "This page gathers the signals you have sent so far: your responses, your sessions, and the path your participation has taken through time."
    )
    if st.session_state.get("authentication_status"):
        authenticator.logout(button_name="Logout", location="sidebar")

    if not repo:
        st.error("Notion repository unavailable.")
        return

    player_page_id = str(st.session_state.get("player_page_id") or "").strip()
    player_access_key = str(st.session_state.get("player_access_key") or "").strip()
    if not player_page_id and player_access_key:
        player = repo.get_player_by_id(player_access_key)
        if player and player.get("id"):
            player_page_id = str(player["id"])
    else:
        player = repo.get_player_by_id(player_page_id) if player_page_id else None
    if not player:
        st.error("Could not resolve your player profile.")
        return

    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Nickname", str(player.get("nickname") or "—"))
    c2.metric(
        "Access key",
        (str(player.get("access_key") or "")[-8:] or "—"),
    )
    c3.metric("Role", str(player.get("role") or "—"))
    c4.metric("Last activity", str(player.get("last_joined_on") or "—"))
    st.caption(
        "Historical responses are read-only. You can update optional metadata below."
    )

    with st.expander("Edit optional metadata", expanded=False):
        with st.form("player-metadata-form"):
            nickname = st.text_input(
                "Name or nickname",
                value=str(player.get("nickname") or ""),
            )
            intent = st.text_input(
                "Motivation (optional)",
                value=str(player.get("intent") or ""),
            )
            email = st.text_input(
                "Email (optional, for reminder)",
                value=str(player.get("email") or ""),
            )
            consent_play = st.checkbox(
                "Consent play",
                value=bool(player.get("consent_play")),
            )
            consent_research = st.checkbox(
                "Consent research",
                value=bool(player.get("consent_research")),
            )
            submit = st.form_submit_button("Save metadata", type="primary")
        if submit:
            updated = repo.update_player_metadata(
                player_page_id or str(player.get("id") or ""),
                nickname=nickname,
                intent=intent,
                email=email,
                consent_play=consent_play,
                consent_research=consent_research,
            )
            if not updated:
                st.error("Could not save metadata.")
            else:
                st.success("Metadata updated.")
                st.rerun()

    sessions = repo.list_sessions(limit=200)
    session_by_id = {str(s.get("id") or ""): s for s in sessions}
    session_ids = list(dict.fromkeys(player.get("session_ids") or []))
    if not session_ids and st.session_state.get("session_id"):
        session_ids = [str(st.session_state.get("session_id"))]

    if not session_ids:
        st.info("No joined sessions yet.")
        return

    try:
        ir = _interaction_repo(repo)
    except Exception as exc:
        st.error(f"Could not initialise interaction repository: {exc}")
        return

    all_rows: List[Dict[str, Any]] = []
    for sid in session_ids:
        try:
            rows = ir.get_responses(sid)
        except Exception:
            rows = []
        all_rows.extend(
            _extract_player_rows(
                rows,
                player_page_id=player_page_id,
                player_access_key=player_access_key,
            )
        )

    st.subheader("Sessions joined")
    session_rows = []
    for sid in session_ids:
        sess = session_by_id.get(sid) or {}
        code = str(sess.get("session_code") or sid)
        count = sum(1 for r in all_rows if str(r.get("session_id") or "") == sid)
        session_rows.append({"session": code, "responses": count})
    st.dataframe(session_rows, width="stretch")

    st.subheader("Activity timeline")
    timeline_rows = []
    for r in all_rows:
        t = str(r.get("timestamp") or r.get("created_at") or "")
        if not t:
            continue
        timeline_rows.append({"time": t, "count": 1})
    timeline_rows.sort(key=lambda x: x["time"])
    if timeline_rows:
        st.line_chart(timeline_rows, x="time", y="count")
    else:
        st.caption("No timeline data yet.")

    st.subheader("Personal signal trajectory")
    signal_rows = []
    for r in all_rows:
        if str(r.get("item_id") or "") != "ORGANISATION_SIGNAL":
            continue
        score = _score_from_choice(str(r.get("value_label") or ""))
        if score is None:
            payload = r.get("value_json")
            if isinstance(payload, dict):
                score = _score_from_choice(str(payload.get("choice") or ""))
        if score is None:
            continue
        signal_rows.append(
            {
                "time": str(r.get("timestamp") or r.get("created_at") or ""),
                "score": score,
            }
        )
    signal_rows.sort(key=lambda x: x["time"])
    if signal_rows:
        cumulative = 0
        cum_rows = []
        for row in signal_rows:
            cumulative += int(row["score"])
            cum_rows.append({"time": row["time"], "cumulative": cumulative})
        st.line_chart(cum_rows, x="time", y="cumulative")
    else:
        st.caption("No organisation signal submissions yet.")

    st.subheader("Your responses (read-only)")
    grouped: Dict[str, List[Dict[str, Any]]] = {}
    for r in all_rows:
        sid = str(r.get("session_id") or "")
        grouped.setdefault(sid, []).append(r)
    for sid, rows in grouped.items():
        sess = session_by_id.get(sid) or {}
        title = str(sess.get("session_code") or sid)
        with st.expander(title, expanded=False):
            table_rows = []
            for r in sorted(rows, key=lambda x: str(x.get("timestamp") or "")):
                answer = r.get("value_label")
                if not answer:
                    val = r.get("response_value")
                    answer = str(val) if val is not None else ""
                table_rows.append(
                    {
                        "question": str(r.get("item_id") or r.get("question_id") or ""),
                        "answer": str(answer or ""),
                        "time": str(r.get("timestamp") or r.get("created_at") or ""),
                    }
                )
            st.dataframe(table_rows, width="stretch")


if __name__ == "__main__":
    main()

