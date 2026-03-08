from __future__ import annotations

import streamlit as st

from infra.app_context import get_authenticator, get_notion_repo
from infra.app_state import ensure_auth, ensure_session_state, remember_access, require_login
from infra.notion_repo import _execute_with_retry, _resolve_data_source_id
from ui import apply_theme, heading, set_page, sidebar_debug_state


def _dump_player(repo, candidate: str):
    if not candidate:
        return None, "empty candidate"
    player = repo.get_player_by_id(candidate) if repo else None
    return player, candidate


def main() -> None:
    set_page()
    apply_theme()
    ensure_session_state()
    sidebar_debug_state()

    heading("Test · Player Profile")
    repo = get_notion_repo()
    authenticator = get_authenticator(repo)
    ensure_auth(
        authenticator,
        callback=remember_access,
        key="player-profile-login",
        location="main",
    )
    require_login()

    username = str(st.session_state.get("username") or "")
    player_access_key = str(st.session_state.get("player_access_key") or "")
    player_page_id = str(st.session_state.get("player_page_id") or "")

    st.subheader("Session State")
    st.json(
        {
            "authentication_status": st.session_state.get("authentication_status"),
            "name": st.session_state.get("name"),
            "username": username,
            "player_access_key": player_access_key,
            "player_page_id": player_page_id,
            "player_role": st.session_state.get("player_role"),
            "player_name": st.session_state.get("player_name"),
        }
    )

    if not repo:
        st.error("Notion repo unavailable.")
        return

    st.subheader("Player Lookups")
    by_username, key1 = _dump_player(repo, username)
    by_access, key2 = _dump_player(repo, player_access_key)
    by_page, key3 = _dump_player(repo, player_page_id)

    c1, c2, c3 = st.columns(3)
    with c1:
        st.caption(f"Lookup by username: `{key1}`")
        st.json(by_username or {})
    with c2:
        st.caption(f"Lookup by access key: `{key2}`")
        st.json(by_access or {})
    with c3:
        st.caption(f"Lookup by page id: `{key3}`")
        st.json(by_page or {})

    resolved = by_username or by_access or by_page
    if resolved and resolved.get("id"):
        st.subheader("Raw Notion Player Page")
        try:
            raw_page = repo.client.pages.retrieve(page_id=resolved.get("id"))
            st.json(raw_page.get("properties", {}))
        except Exception as exc:
            st.error(f"Could not retrieve raw player page: {exc}")

    with st.expander("Raw Query Payload (used by normalization)", expanded=False):
        try:
            players_db_id = repo.players_db_id
            ds_id = _resolve_data_source_id(repo.client, players_db_id)
            access_prop = (
                "access_key" if repo._prop_exists(players_db_id, "access_key") else "player_id"  # noqa: SLF001
            )
            lookup_value = username or player_access_key
            payload = _execute_with_retry(
                repo.client.data_sources.query,
                data_source_id=ds_id,
                filter={
                    "property": access_prop,
                    "rich_text": {"equals": lookup_value},
                },
                page_size=1,
            )
            results = payload.get("results", [])
            if not results:
                st.warning("No query results for this access key.")
            else:
                st.json(results[0].get("properties", {}))
        except Exception as exc:
            st.error(f"Could not query raw payload: {exc}")

    authenticator.logout(button_name="Logout", location="main")


if __name__ == "__main__":
    main()
