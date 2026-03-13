from __future__ import annotations

import json
from io import StringIO
from typing import Any, Dict, List
from datetime import datetime
from pathlib import Path

import streamlit as st
import yaml

from infra.app_context import get_authenticator, get_notion_repo
from infra.app_state import (
    ensure_auth,
    ensure_session_context,
    ensure_session_state,
    remember_access,
    require_login,
)
from models.catalog import catalog_session_codes, questions_for_session
from ui import apply_theme, heading, microcopy, set_page, sidebar_debug_state


def _is_admin(role: str) -> bool:
    st.write(f"Current role: {role}")
    return role.lower() in {"admin", "owner", "organiser"}


def _load_statements(payload: str) -> List[Dict[str, Any]]:
    if not payload:
        return []
    try:
        data = json.loads(payload)
    except json.JSONDecodeError:
        data = yaml.safe_load(payload)
    if isinstance(data, dict):
        return data.get("statements", []) or data.get("items", []) or []
    if isinstance(data, list):
        return data
    return []


def _load_statement_set_v0() -> List[Dict[str, Any]]:
    path = Path(__file__).resolve().parents[1] / "assets" / "statement_set_v0.md"
    if not path.exists():
        return []
    raw = path.read_text(encoding="utf-8")
    items: List[Dict[str, Any]] = []
    order = 0
    for line in raw.splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        if line.lower().startswith("theme:"):
            if items:
                items[-1]["theme"] = line.split(":", 1)[1].strip()
            continue
        if line[0].isdigit() and "“" in line:
            order += 1
            text = line.split("“", 1)[1].rsplit("”", 1)[0]
            items.append({"text": text, "order": order})
    return items


def _session_sort_key(session: Dict[str, Any]) -> tuple[int, str]:
    code = str(session.get("session_code") or "").strip()
    rank = 0 if code.upper() == "GLOBAL-SESSION" else 1
    return rank, code.upper()


def _render_sessions_panel(repo) -> None:
    st.subheader("Session management")
    st.caption(
        "GLOBAL-SESSION stays active by default. Multiple additional sessions may be active at once."
    )
    sessions = repo.list_sessions(limit=200)
    if not sessions:
        st.info("No sessions found in Notion.")
        return

    sessions = sorted(sessions, key=_session_sort_key)
    try:
        supports_active_toggle = repo._prop_exists(  # noqa: SLF001
            repo._sessions_db_id(None),  # noqa: SLF001
            "active",
        )
    except Exception:
        supports_active_toggle = False

    notion_codes = {str(s.get("session_code") or "").strip() for s in sessions}
    catalog_codes = set(catalog_session_codes())
    missing = sorted(code for code in catalog_codes if code not in notion_codes)
    if missing:
        st.warning(
            "Catalogue references sessions not present in Notion: "
            + ", ".join(missing)
        )

    for session in sessions:
        session_id = str(session.get("id") or "")
        session_code = str(session.get("session_code") or "Unnamed session").strip()
        is_global = session_code.upper() == "GLOBAL-SESSION"
        is_active = bool(session.get("active"))
        status_label = "Active" if is_active else "Inactive"
        session_questions = questions_for_session(
            session_code,
            include_inactive=True,
        )

        with st.container(border=True):
            c1, c2, c3 = st.columns([4, 2, 2])
            with c1:
                st.markdown(f"**{session_code}**")
                if session.get("notes"):
                    st.caption(str(session.get("notes")))
            with c2:
                st.caption("Status")
                if is_active:
                    st.success(status_label)
                else:
                    st.warning(status_label)
            with c3:
                st.caption("Questions")
                st.metric("Count", len(session_questions))

            toggle_label = "Deactivate session" if is_active else "Activate session"
            disable_toggle = is_global and is_active
            toggle_help = (
                "GLOBAL-SESSION is pinned active."
                if disable_toggle
                else "Toggle active/inactive for this session."
            )
            if st.button(
                toggle_label,
                key=f"session-toggle-{session_id}",
                use_container_width=True,
                disabled=disable_toggle or (not supports_active_toggle),
                help=toggle_help,
            ):
                try:
                    repo.update_session(session_id, active=not is_active)
                except Exception as exc:
                    st.error(f"Failed to update session active state: {exc}")
                else:
                    st.toast(
                        f"{session_code} is now {'active' if not is_active else 'inactive'}.",
                        icon="✅",
                    )
                    st.rerun()
            if not supports_active_toggle:
                st.caption("Session DB has no `active` checkbox property to toggle.")

            with st.expander(f"Questions in {session_code}", expanded=False):
                if not session_questions:
                    st.caption("No catalogue questions linked to this session yet.")
                else:
                    for q in session_questions:
                        q_status = "Active" if q.active else "Inactive"
                        st.markdown(
                            f"- `{q.id}` • `{q.response_type}` • depth `{q.depth}` • order `{q.order}` • {q_status}"
                        )
                        st.caption(q.prompt)
                        if q.context:
                            st.caption(q.context)


def main() -> None:
    set_page()
    apply_theme()
    ensure_session_state()
    repo = get_notion_repo()
    authenticator = get_authenticator(repo)
    ensure_auth(authenticator, callback=remember_access, key="admin-login")
    ensure_session_context(repo)
    require_login()
    sidebar_debug_state()
    st.sidebar.markdown(f"**Session ID:** {st.session_state.get('session_id', 'N/A')}")
    # debug show session state in sidebar
    st.sidebar.markdown("**Session State:**")
    st.sidebar.json(st.session_state)
    role = st.session_state.get("player_role", "None")
    st.write(f"Your role: {role}")
    if not _is_admin(role):
        st.error("Admin access only.")
        return

    if st.session_state.get("authentication_status"):
        authenticator.logout(button_name="Logout", location="sidebar")
    session_id = st.session_state.get("session_id")

    heading("Admin Console")
    microcopy("Manage sessions, question catalogue mapping, and exports.")

    if not repo or not session_id:
        st.error("Missing session context.")
        return

    _render_sessions_panel(repo)

    st.subheader("Question catalogue (legacy statements import)")
    upload = st.file_uploader("Upload JSON or YAML", type=["json", "yaml", "yml"])
    if upload:
        content = StringIO(upload.getvalue().decode("utf-8")).read()
        items = _load_statements(content)
        if st.button("Import statements", type="primary"):
            for idx, item in enumerate(items, start=1):
                text = item.get("text") or item.get("statement") or ""
                theme = item.get("theme")
                order = item.get("order") or idx
                if text:
                    repo.create_statement(
                        session_id=session_id,
                        text=text,
                        theme=theme,
                        order=order,
                        active=True,
                    )
            st.success("Statements imported.")

    st.subheader("Load statement set v0")
    if st.button("Import co-creator resonance v0", type="primary"):
        items = _load_statement_set_v0()
        if not items:
            st.error("statement_set_v0.md not found or empty.")
        else:
            for idx, item in enumerate(items, start=1):
                repo.create_statement(
                    session_id=session_id,
                    text=item.get("text", ""),
                    theme=item.get("theme"),
                    order=item.get("order") or idx,
                    active=True,
                )
            st.success("Statement set v0 imported.")

    st.subheader("Export listed questions")
    listed = repo.list_listed_questions(session_id)
    if listed:
        csv_lines = ["text,domain,approve_count,park_count,rewrite_count"]
        for q in listed:
            row = [
                q["text"].replace(",", " "),
                q["domain"],
                str(q.get("approve_count", 0)),
                str(q.get("park_count", 0)),
                str(q.get("rewrite_count", 0)),
            ]
            csv_lines.append(",".join(row))
        csv_payload = "\n".join(csv_lines)
        st.download_button(
            "Download CSV snapshot",
            data=csv_payload,
            file_name="questions_snapshot.csv",
            mime="text/csv",
        )
    else:
        st.caption("No listed questions yet.")

    st.subheader("Signals")
    st.caption("Collective traces from decision micro-gestures.")

    decisions = repo.list_decisions(session_id)
    item_records: List[Dict[str, Any]] = []
    journey_records: List[Dict[str, Any]] = []
    for decision in decisions:
        dtype = decision.get("type")
        payload_text = decision.get("payload", "")
        try:
            payload = json.loads(payload_text) if payload_text else {}
        except Exception:
            payload = {}
        if dtype in {"decision_item_compact_v0", "decision_item_diff_v0"}:
            item_id = payload.get("item_id")
            if not item_id:
                continue
            if dtype == "decision_item_diff_v0":
                action = "change"
            else:
                action = payload.get("decision", "")
            item_records.append(
                {
                    "item_id": item_id,
                    "decision": action,
                    "player_id": (decision.get("player_id") or [None])[0],
                    "created_at": decision.get("created_at"),
                    "change_length": len(payload.get("proposed_change", "") or ""),
                }
            )
        if dtype == "decision_journey_v0":
            journey_records.append(payload)

    if item_records:
        st.markdown("**Collective Friction Map**")
        friction: Dict[str, Dict[str, int]] = {}
        for rec in item_records:
            bucket = friction.setdefault(
                rec["item_id"], {"keep": 0, "drop": 0, "change": 0}
            )
            if rec["decision"] in bucket:
                bucket[rec["decision"]] += 1
        friction_rows = []
        for item_id, counts in friction.items():
            total = sum(counts.values()) or 1
            friction_rows.append(
                {
                    "item": item_id,
                    "keep_%": round(counts["keep"] * 100 / total, 1),
                    "change_%": round(counts["change"] * 100 / total, 1),
                    "drop_%": round(counts["drop"] * 100 / total, 1),
                    "total": total,
                }
            )
        st.dataframe(friction_rows, use_container_width=True)

        st.markdown("**Decision Convergence Timeline**")
        timeline: Dict[str, Dict[str, int]] = {}
        for rec in item_records:
            ts = rec.get("created_at") or ""
            day = ts.split("T")[0] if "T" in ts else ts[:10]
            bucket = timeline.setdefault(day, {"keep": 0, "drop": 0, "change": 0})
            if rec["decision"] in bucket:
                bucket[rec["decision"]] += 1
        if timeline:
            timeline_rows = [
                {"date": day, **counts} for day, counts in sorted(timeline.items())
            ]
            st.area_chart(timeline_rows, x="date", y=["keep", "change", "drop"])

        st.markdown("**Participation Posture Map**")
        per_player: Dict[str, Dict[str, int]] = {}
        for rec in item_records:
            pid = rec.get("player_id") or "unknown"
            bucket = per_player.setdefault(pid, {"keep": 0, "drop": 0, "change": 0})
            if rec["decision"] in bucket:
                bucket[rec["decision"]] += 1
        posture_rows = []
        for pid, counts in per_player.items():
            total = sum(counts.values()) or 1
            posture_rows.append(
                {
                    "player": pid,
                    "intervention_rate": counts["change"] / total,
                    "acceptance_rate": counts["keep"] / total,
                    "total_actions": total,
                }
            )
        st.scatter_chart(posture_rows, x="intervention_rate", y="acceptance_rate")

    if journey_records:
        st.markdown("**Journey Flow**")
        start_counts: Dict[str, int] = {}
        end_counts: Dict[str, int] = {}
        for rec in journey_records:
            for state in rec.get("energy_start", []) or []:
                start_counts[state] = start_counts.get(state, 0) + 1
            for state in rec.get("energy_end", []) or []:
                end_counts[state] = end_counts.get(state, 0) + 1
        if start_counts:
            st.bar_chart(
                [{"state": k, "count": v} for k, v in sorted(start_counts.items())],
                x="state",
                y="count",
            )
        if end_counts:
            st.bar_chart(
                [{"state": k, "count": v} for k, v in sorted(end_counts.items())],
                x="state",
                y="count",
            )


if __name__ == "__main__":
    main()
