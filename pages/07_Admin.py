from __future__ import annotations

import json
from io import StringIO
from typing import Any, Dict, List
from datetime import datetime
from pathlib import Path
from collections import defaultdict
from datetime import timezone, timedelta
import hashlib
import time

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
from infra.event_logger import (
    get_module_logger,
    log_event,
    role_claim_cooldown_state,
)
from infra.notion_repo import _cached_query
from models.catalog import (
    catalog_session_codes,
    questions_for_session,
    validate_question_catalog,
)
from models.sessions import session_spec_by_id
from repositories.interaction_repo import NotionInteractionRepository
from ui import apply_theme, heading, microcopy, set_page, sidebar_debug_state
from ui import render_orientation_sidebar, update_sidebar_task
from ui import begin_sidebar_timing, end_sidebar_timing

ADMIN_LOGGER = get_module_logger("iceicebaby.admin")
ADMIN_PLAYERS_CACHE_TTL_S = 1200.0
ADMIN_CONTACT_CACHE_TTL_S = 600.0


def _is_admin(role: str) -> bool:
    st.write(f"Current role: {role}")
    return role.lower() in {
        "admin",
        "owner",
        "organiser",
        "co-organiser",
        "co_organiser",
        "developer",
    }


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


def _session_sort_key(session: Dict[str, Any]) -> tuple[int, int, str]:
    code = str(session.get("session_code") or "").strip()
    spec = session_spec_by_id(code)
    order = int(session.get("session_order") or (spec.session_order if spec else 999))
    rank = 0 if code.upper() == "GLOBAL-SESSION" else 1
    return rank, order, code.upper()


def _normalise_identity_token(value: str) -> str:
    return " ".join(str(value or "").strip().lower().split())


def _is_hex_key_like(value: str) -> bool:
    txt = str(value or "").strip()
    if len(txt) != 32:
        return False
    return all(ch in "0123456789abcdefABCDEF" for ch in txt)


def _display_player_name(player: Dict[str, Any]) -> str:
    nickname = str(player.get("nickname") or "").strip()
    access_key = str(player.get("access_key") or "").strip()
    if not nickname:
        return "🧊"
    if _is_hex_key_like(nickname) and (not access_key or nickname.upper() == access_key.upper()):
        return "🧊"
    return nickname


def _player_name_sort_key(player: Dict[str, Any]) -> tuple[str, str]:
    display = _display_player_name(player)
    if display != "🧊":
        return ("0", display.lower())
    seed = str(player.get("access_key") or player.get("id") or "")
    digest = hashlib.sha256(seed.encode("utf-8")).hexdigest()
    return ("1", digest)


def _load_players_for_reconciliation(repo) -> List[Dict[str, Any]]:
    """
    Return all players from the players DB using the cleanest available path.

    Preferred: public repo.list_all_players().
    Fallback: direct paginated DB scan (still cached via _cached_query).
    """
    if hasattr(repo, "list_all_players"):
        return repo.list_all_players(limit=500)

    db_id = repo._players_db_id(None)  # noqa: SLF001
    out: List[Dict[str, Any]] = []
    next_cursor = None
    while True:
        query_kwargs = {"page_size": 100}
        if next_cursor:
            query_kwargs["start_cursor"] = next_cursor
        payload = _cached_query(repo.client, db_id, **query_kwargs)
        for page in payload.get("results", []):
            out.append(repo._normalize_player(page, players_db_id=db_id))  # noqa: SLF001
        if not payload.get("has_more"):
            break
        next_cursor = payload.get("next_cursor")
        if not next_cursor:
            break
    return out


def _interaction_responses_db_id() -> str:
    notion_cfg = st.secrets.get("notion", {})
    return str(
        notion_cfg.get("ice_interaction_responses_db_id")
        or notion_cfg.get("interaction_responses_db_id")
        or notion_cfg.get("ice_responses_db_id")
        or ""
    )


@st.cache_data(ttl=ADMIN_PLAYERS_CACHE_TTL_S, show_spinner=False)
def _load_players_shared_cache(_cache_key: str) -> List[Dict[str, Any]]:
    repo = get_notion_repo()
    return _load_players_for_reconciliation(repo)


@st.cache_data(ttl=ADMIN_CONTACT_CACHE_TTL_S, show_spinner=False)
def _load_contact_preferences_shared_cache(
    _cache_key: str,
    session_id: str,
) -> List[Dict[str, Any]]:
    repo = get_notion_repo()
    db_id = _interaction_responses_db_id()
    if not db_id:
        return []
    interaction_repo = NotionInteractionRepository(repo, db_id)
    return interaction_repo.get_responses_by_item(session_id, "CONTACT_METHOD")


def _clear_admin_caches() -> None:
    _load_players_shared_cache.clear()
    _load_contact_preferences_shared_cache.clear()
    for key in list(st.session_state.keys()):
        if key.startswith("admin_players_cache_v2") or key.startswith("admin_contact_prefs_v2:"):
            st.session_state.pop(key, None)


def _get_players_cached(repo, *, force: bool = False, ttl_s: float = ADMIN_PLAYERS_CACHE_TTL_S) -> List[Dict[str, Any]]:
    key = "admin_players_cache_v2"
    now_ts = time.time()
    cached = st.session_state.get(key)
    if (
        not force
        and isinstance(cached, dict)
        and (now_ts - float(cached.get("ts", 0.0)) < ttl_s)
        and isinstance(cached.get("players"), list)
    ):
        return cached.get("players", [])
    if force:
        _clear_admin_caches()
    players_db_id = str(repo._players_db_id(None))  # noqa: SLF001
    players = _load_players_shared_cache(players_db_id)
    st.session_state[key] = {"ts": now_ts, "players": players}
    return players


def _get_contact_preferences_cached(
    repo,
    session_id: str,
    *,
    force: bool = False,
    ttl_s: float = ADMIN_CONTACT_CACHE_TTL_S,
) -> List[Dict[str, Any]]:
    key = f"admin_contact_prefs_v2:{session_id}"
    now_ts = time.time()
    cached = st.session_state.get(key)
    if (
        not force
        and isinstance(cached, dict)
        and (now_ts - float(cached.get("ts", 0.0)) < ttl_s)
        and isinstance(cached.get("responses"), list)
    ):
        return cached.get("responses", [])
    if force:
        _clear_admin_caches()
    interaction_db_id = _interaction_responses_db_id()
    if not interaction_db_id:
        responses: List[Dict[str, Any]] = []
    else:
        responses = _load_contact_preferences_shared_cache(interaction_db_id, session_id)
    st.session_state[key] = {"ts": now_ts, "responses": responses}
    return responses


def _render_players_dashboard(repo, session_id: str) -> None:
    st.subheader("Players dashboard")
    st.caption("Live view of players and contact preferences.")
    refresh_players = st.button(
        "Refresh players data",
        type="secondary",
        width="stretch",
        key="admin-refresh-players-cache",
    )
    if refresh_players:
        _clear_admin_caches()
        st.toast("Admin caches refreshed.", icon="♻️")
    t0 = begin_sidebar_timing("players_load")
    try:
        players = _get_players_cached(
            repo,
            force=False,
            ttl_s=ADMIN_PLAYERS_CACHE_TTL_S,
        )
    except Exception as exc:
        end_sidebar_timing(t0, "players_load_error")
        st.error(f"Could not load players dashboard: {exc}")
        return
    end_sidebar_timing(t0, "players_load")
    if not players:
        st.info("No players found.")
        return

    contact_by_player: Dict[str, Dict[str, str]] = {}
    t1 = begin_sidebar_timing("contact_preferences_load")
    try:
        responses = _get_contact_preferences_cached(
            repo,
            session_id,
            force=False,
            ttl_s=ADMIN_CONTACT_CACHE_TTL_S,
        )
        for row in responses:
            item_id = str(row.get("item_id") or row.get("question_id") or "")
            if item_id != "CONTACT_METHOD":
                continue
            pid = str(row.get("player_id") or "").strip()
            if not pid:
                continue
            payload = row.get("value_json") if isinstance(row.get("value_json"), dict) else {}
            method = str(
                (payload or {}).get("choice")
                or row.get("response_value")
                or row.get("value_label")
                or ""
            ).strip()
            contact_value = str((payload or {}).get("contact_value") or "").strip()
            timestamp = str(row.get("timestamp") or row.get("created_at") or "")
            prev = contact_by_player.get(pid)
            if (not prev) or (timestamp >= str(prev.get("timestamp") or "")):
                contact_by_player[pid] = {
                    "method": method,
                    "contact_value": contact_value,
                    "timestamp": timestamp,
                }
    except Exception:
        # Keep dashboard available even if interaction response read fails.
        pass
    end_sidebar_timing(t1, "contact_preferences_load")

    rows = []
    name_tokens: List[tuple[str, tuple[str, str]]] = []
    no_contact_count = 0
    with_contact_pref = 0
    for p in players:
        pid = str(p.get("id") or "")
        nickname = _display_player_name(p)
        name_tokens.append((nickname or pid, _player_name_sort_key(p)))
        contact = contact_by_player.get(pid, {})
        method = str(contact.get("method") or "")
        detail = str(contact.get("contact_value") or "")
        if method:
            with_contact_pref += 1
        if "don't want to be in touch" in method.lower() or "dont want to be in touch" in method.lower():
            no_contact_count += 1
        rows.append(
            {
                "name": nickname,
                "role": str(p.get("role") or ""),
                "email": str(p.get("email") or ""),
                "last_activity": str(p.get("last_joined_on") or p.get("created_at") or ""),
                "contact_preference": method,
                "contact_detail": detail,
            }
        )
    rows.sort(key=lambda r: (str(r.get("name") or "").lower(), str(r.get("last_activity") or "")))

    c1, c2, c3 = st.columns(3)
    c1.metric("Players", len(rows))
    c2.metric("With contact preference", with_contact_pref)
    c3.metric("No contact requested", no_contact_count)
    with st.expander("All player names", expanded=True):
        ordered_names = [name for name, _ in sorted(name_tokens, key=lambda x: x[1]) if name]
        st.write(", ".join(ordered_names))
        st.caption("🧊 indicates anonymous player")
    st.dataframe(rows, width="stretch")


def _render_duplicate_players_panel(repo) -> None:
    st.subheader("Potential duplicate players")
    st.caption("Detected as suspected aliases only. No automatic merge is performed.")
    st.markdown(
        """
**Flagging rule (explicit definition)**

Define `norm(x) = lower(trim(collapse_spaces(x)))`.

A candidate group `G` means: a set of player profiles suspected to refer to the same person.

A set `G` is flagged as *suspected duplicate* iff `|G| ≥ 2` and at least one of:

1. `norm(nickname_i) = norm(nickname_j)` for some `i ≠ j`
2. `norm(email_i) = norm(email_j)` for some `i ≠ j`, with non-empty email

This module only flags candidates. It does not merge or delete records.
"""
    )
    run_key = "admin_run_duplicate_detection"
    c1, c2 = st.columns(2)
    with c1:
        if st.button("Run duplicate detection", type="primary", width="stretch"):
            st.session_state[run_key] = True
    with c2:
        if st.button("Clear results", type="secondary", width="stretch"):
            st.session_state[run_key] = False
    if not st.session_state.get(run_key, False):
        st.info("Duplicate detection is idle. Click 'Run duplicate detection' to execute.")
        return

    refresh_before_scan = st.checkbox(
        "Force refresh player cache before scan",
        value=False,
        key="admin-dup-refresh-before-scan",
    )
    t2 = begin_sidebar_timing("duplicate_detection")
    try:
        with st.spinner("Scanning players for potential duplicates..."):
            players = _get_players_cached(
                repo,
                force=bool(refresh_before_scan),
                ttl_s=ADMIN_PLAYERS_CACHE_TTL_S,
            )
    except Exception as exc:
        end_sidebar_timing(t2, "duplicate_detection_error")
        st.error(f"Could not load players for duplicate detection: {exc}")
        return
    end_sidebar_timing(t2, "duplicate_detection")
    st.caption(f"Loaded players: {len(players)}")
    if not players:
        st.caption("No players found.")
        return

    def _safe_dt(raw: str) -> datetime | None:
        txt = str(raw or "").strip()
        if not txt:
            return None
        try:
            return datetime.fromisoformat(txt.replace("Z", "+00:00"))
        except Exception:
            return None

    now_utc = datetime.now(timezone.utc)
    with_last_activity = 0
    active_24h = 0
    latest_rows = []
    for p in players:
        last_raw = str(p.get("last_joined_on") or p.get("created_at") or "")
        last_dt = _safe_dt(last_raw)
        if last_dt is not None:
            with_last_activity += 1
            if (now_utc - last_dt) <= timedelta(hours=24):
                active_24h += 1
        latest_rows.append(
            {
                "player_id": str(p.get("id") or ""),
                "nickname": str(p.get("nickname") or ""),
                "role": str(p.get("role") or ""),
                "last_activity": last_raw,
            }
        )

    stat1, stat2, stat3 = st.columns(3)
    stat1.metric("Players loaded", len(players))
    stat2.metric("With last activity", with_last_activity)
    stat3.metric("Active in last 24h", active_24h)
    latest_rows.sort(key=lambda r: r["last_activity"], reverse=True)
    with st.expander("Player activity snapshot", expanded=False):
        st.dataframe(latest_rows[:30], width="stretch")

    by_nickname: Dict[str, List[Dict[str, Any]]] = defaultdict(list)
    by_email: Dict[str, List[Dict[str, Any]]] = defaultdict(list)
    for p in players:
        nick = _normalise_identity_token(str(p.get("nickname") or ""))
        mail = _normalise_identity_token(str(p.get("email") or ""))
        if nick:
            by_nickname[nick].append(p)
        if mail:
            by_email[mail].append(p)

    candidates_by_group: Dict[str, Dict[str, Any]] = {}

    def _add_group(reason: str, key: str, members: List[Dict[str, Any]]) -> None:
        if len(members) < 2:
            return
        ids = sorted(str(m.get("id") or "") for m in members if m.get("id"))
        group_key = "|".join(ids)
        if not group_key:
            return
        if group_key not in candidates_by_group:
            candidates_by_group[group_key] = {
                "reasons": [],
                "match_keys": [],
                "members": members,
            }
        candidates_by_group[group_key]["reasons"].append(reason)
        candidates_by_group[group_key]["match_keys"].append(key)

    for key, members in by_nickname.items():
        _add_group("same nickname", key, members)
    for key, members in by_email.items():
        _add_group("same email", key, members)

    candidates = list(candidates_by_group.values())
    candidates.sort(
        key=lambda c: (
            -len(c.get("members", [])),
            ",".join(sorted(set(c.get("reasons", [])))),
            ",".join(sorted(set(c.get("match_keys", [])))),
        )
    )

    if not candidates:
        st.success("No obvious duplicate candidates detected.")
        return

    for idx, candidate in enumerate(candidates, start=1):
        reasons = sorted(set(candidate.get("reasons", [])))
        match_keys = sorted(set(candidate.get("match_keys", [])))
        members = candidate["members"]
        title = (
            f"Candidate {idx} · reasons: {', '.join(reasons)} · "
            f"keys: {', '.join(match_keys)}"
        )
        with st.expander(title, expanded=False):
            rows = []
            for m in members:
                rows.append(
                    {
                        "player_id": str(m.get("id") or ""),
                        "nickname": str(m.get("nickname") or ""),
                        "email": str(m.get("email") or ""),
                        "role": str(m.get("role") or ""),
                        "created_at": str(m.get("created_at") or ""),
                        "last_joined_on": str(m.get("last_joined_on") or ""),
                    }
                )
            st.dataframe(rows, width="stretch")
            c1, c2, c3 = st.columns(3)
            with c1:
                if st.button(
                    "Mark unrelated (session)",
                    key=f"dup-unrelated-{idx}",
                    width="stretch",
                ):
                    st.session_state[f"dup_ignore_{'|'.join(match_keys)}"] = True
                    st.toast("Marked as unrelated for this admin session.", icon="✅")
            with c2:
                if st.button(
                    "Invite merge confirmation",
                    key=f"dup-invite-{idx}",
                    width="stretch",
                    type="secondary",
                ):
                    log_event(
                        module="iceicebaby.roles",
                        event_type="duplicate_merge_invite",
                        player_id=str(st.session_state.get("player_page_id", "")),
                        session_id=str(st.session_state.get("session_id", "")),
                        metadata={
                            "reasons": reasons,
                            "match_keys": match_keys,
                            "candidate_ids": [str(m.get("id") or "") for m in members],
                        },
                    )
                    st.toast("Merge invitation event logged.", icon="📨")
            with c3:
                st.caption("Status")
                st.info("suspected")


def _render_sessions_panel(repo) -> None:
    st.subheader("Session management")
    st.caption(
        "GLOBAL-SESSION stays active by default. Multiple additional sessions may be active at once."
    )
    sessions = repo.list_sessions(limit=200)
    if not sessions:
        st.info("No sessions found in Notion.")
        return
    catalogue_errors = validate_question_catalog()
    if catalogue_errors:
        st.error("Question catalogue validation errors detected:")
        for err in catalogue_errors:
            st.caption(f"- {err}")

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
        ADMIN_LOGGER.warning(
            "missing session mapping for catalog sessions: %s", ",".join(missing)
        )
        st.warning(
            "Catalogue references sessions not present in Notion: " + ", ".join(missing)
        )

    for session in sessions:
        session_id = str(session.get("id") or "")
        session_code = str(session.get("session_code") or "Unnamed session").strip()
        spec = session_spec_by_id(session_code)
        session_name = str(
            session.get("session_name") or (spec.session_name if spec else session_code)
        )
        session_title = str(
            session.get("session_title")
            or (spec.session_title if spec else session_code)
        )
        session_description = str(
            session.get("session_description")
            or session.get("notes")
            or (spec.session_description if spec else "")
        )
        session_order = int(
            session.get("session_order") or (spec.session_order if spec else 999)
        )
        session_visualisation = str(
            session.get("session_visualisation")
            or (spec.session_visualisation if spec else "")
        )
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
                st.markdown(f"**{session_code}** · {session_name}")
                st.caption(f"Title: {session_title} · Order: {session_order}")
                if session_description:
                    st.caption(session_description)
            with c2:
                st.caption("Status")
                if is_active:
                    st.success(status_label)
                else:
                    st.warning(status_label)
            with c3:
                st.caption("Questions")
                st.metric("Count", len(session_questions))
                if session_visualisation:
                    st.caption(f"Visualisation: {session_visualisation}")

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
                    repo.update_session(session_id, session_active=not is_active)
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

            with st.expander(f"Edit {session_code} metadata", expanded=False):
                meta_name = st.text_input(
                    "Session name",
                    value=session_name,
                    key=f"session-meta-name-{session_id}",
                )
                meta_title = st.text_input(
                    "Session title",
                    value=session_title,
                    key=f"session-meta-title-{session_id}",
                )
                meta_order = st.number_input(
                    "Session order",
                    min_value=0,
                    step=1,
                    value=session_order,
                    key=f"session-meta-order-{session_id}",
                )
                meta_visual = st.text_input(
                    "Session visualisation",
                    value=session_visualisation,
                    key=f"session-meta-visual-{session_id}",
                )
                meta_desc = st.text_area(
                    "Session description",
                    value=session_description,
                    key=f"session-meta-desc-{session_id}",
                    height=80,
                )
                if st.button(
                    "Save session metadata",
                    key=f"session-meta-save-{session_id}",
                    use_container_width=True,
                    type="secondary",
                ):
                    try:
                        repo.update_session(
                            session_id,
                            session_name=meta_name,
                            session_title=meta_title,
                            session_order=int(meta_order),
                            session_description=meta_desc,
                            session_visualisation=meta_visual,
                        )
                    except Exception as exc:
                        st.error(f"Failed to update session metadata: {exc}")
                    else:
                        st.toast("Session metadata updated.", icon="✅")
                        st.rerun()

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
    st.sidebar.json(st.session_state, expanded=False)
    role = st.session_state.get("player_role", "None")
    if not _is_admin(role):
        st.error("Admin access only.")
        return

    if st.session_state.get("authentication_status"):
        authenticator.logout(button_name="Logout", location="sidebar")
    session_id = st.session_state.get("session_id")

    heading("Admin Console")
    microcopy("Manage sessions, question catalogue mapping, and exports.")
    ADMIN_LOGGER.info("admin console loaded")

    if not repo or not session_id:
        st.error("Missing session context.")
        return

    st.subheader("Role controls")
    claimant_id = (
        str(st.session_state.get("player_page_id") or "").strip()
        or str(st.session_state.get("player_access_key") or "").strip()
    )
    st.caption("Confirm you are part of the current organising thread.")
    if st.button(
        "Claim co-organiser role",
        type="secondary",
        use_container_width=False,
        disabled=not bool(claimant_id),
    ):
        st.session_state["show_claim_coorg_form"] = True

    if st.session_state.get("show_claim_coorg_form", False):
        claim_cfg = st.secrets.get("role_claim", {})
        organiser_names = [
            "Ignacio",
            "Andrés",
            "Leopold",
            "Ariane",
            "Véronique",
            "Jean-François",
            "Bruno",
        ]
        expected_absent = claim_cfg.get("absent_first_names", [])
        if isinstance(expected_absent, str):
            expected_absent = [
                v.strip() for v in expected_absent.split(",") if v.strip()
            ]
        expected_absent_set = {
            str(v).strip().lower() for v in expected_absent if str(v).strip()
        }
        expected_phrase = str(claim_cfg.get("organiser_phrase", "")).strip()

        cooldown = role_claim_cooldown_state(
            session_scope=str(st.session_state.get("session_id") or "global")
        )
        if cooldown["in_cooldown"]:
            remaining = int(cooldown["remaining_seconds"])
            st.info(
                f"Role claim is on cooldown. Try again in about {max(1, remaining // 60)} minute(s)."
            )
        with st.form("claim-coorg-form"):
            selected_absent = (
                st.pills(
                    "Which contributors could not join the call today?",
                    organiser_names,
                    selection_mode="multi",
                )
                or []
            )
            phrase = st.text_input(
                "Enter today's organiser phrase",
                type="password",
            )
            submit_claim = st.form_submit_button(
                "Verify and claim role",
                type="primary",
                disabled=bool(cooldown["in_cooldown"]),
            )
        if submit_claim:
            if cooldown["in_cooldown"]:
                st.info("Please wait before trying again.")
            else:
                selected_set = {
                    str(v).strip().lower() for v in selected_absent if str(v).strip()
                }
                names_ok = (
                    selected_set == expected_absent_set
                    if expected_absent_set
                    else bool(selected_set)
                )
                phrase_ok = (
                    bool(expected_phrase)
                    and phrase.strip().lower() == expected_phrase.lower()
                )
                if names_ok and phrase_ok:
                    updated = repo.set_player_role(
                        claimant_id,
                        "co_organiser",
                        source="self-claimed",
                    )
                    if not updated:
                        st.error("Could not update role for current participant.")
                        log_event(
                            module="iceicebaby.roles",
                            event_type="claim_coorganiser_failure",
                            player_id=str(st.session_state.get("player_page_id", "")),
                            session_id=str(st.session_state.get("session_id", "")),
                            metadata={"reason": "db_update_failed"},
                            level="ERROR",
                        )
                    else:
                        cooldown["record_success"]()
                        st.session_state["player_role"] = str(
                            updated.get("role") or "co_organiser"
                        )
                        log_event(
                            module="iceicebaby.roles",
                            event_type="claim_coorganiser_success",
                            player_id=str(updated.get("id") or claimant_id),
                            session_id=str(st.session_state.get("session_id", "")),
                            metadata={"source": "self-claimed"},
                        )
                        st.success("Role updated to co-organiser.")
                        st.rerun()
                else:
                    cooldown["record_failure"]()
                    log_event(
                        module="iceicebaby.roles",
                        event_type="claim_coorganiser_failure",
                        player_id=str(st.session_state.get("player_page_id", "")),
                        session_id=str(st.session_state.get("session_id", "")),
                        metadata={
                            "attempt": cooldown["attempts"] + 1,
                            "has_phrase": bool(phrase.strip()),
                            "selected_count": len(selected_set),
                        },
                        level="WARNING",
                    )
                    st.error("Could not verify your claim. Please check your inputs.")
                    if not expected_phrase:
                        st.info(
                            "Role-claim phrase is not configured in secrets (`role_claim.organiser_phrase`)."
                        )

    _render_sessions_panel(repo)
    _render_players_dashboard(repo, str(session_id))
    _render_duplicate_players_panel(repo)

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

    update_sidebar_task("Admin overview", done=True)
    render_orientation_sidebar(
        session_name=str(st.session_state.get("session_title") or "GLOBAL SESSION"),
        session_description="Admin console for sessions, players, and duplicate reconciliation.",
    )


if __name__ == "__main__":
    main()
