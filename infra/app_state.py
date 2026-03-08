from __future__ import annotations

import hashlib
from typing import Dict, Optional, Tuple

import streamlit as st

from infra.app_context import get_active_session


def ensure_session_state() -> None:
    st.session_state.setdefault("player_page_id", "")
    st.session_state.setdefault("player_access_key", "")
    st.session_state.setdefault("player_name", "")
    st.session_state.setdefault("player_role", "None")
    st.session_state.setdefault("session_id", "")
    st.session_state.setdefault("session_title", "")
    st.session_state.setdefault("anon_token", "")
    st.session_state.setdefault("resonance_submitted", False)


def remember_access(payload: Dict) -> None:
    player = payload.get("player") or {}
    st.session_state["player_page_id"] = player.get("id", "")
    st.session_state["player_access_key"] = payload.get("access_key", "") or player.get(
        "access_key", ""
    )
    st.session_state["player_name"] = player.get("nickname") or "Collaborator"
    role_value = player.get("role") or "None"
    st.session_state["player_role"] = str(role_value)


def set_session(session_id: str, session_title: str) -> None:
    st.session_state["session_id"] = session_id
    st.session_state["session_title"] = session_title


def mint_anon_token(session_id: str, player_id: str, salt: str) -> str:
    seed = f"{player_id}:{session_id}:{salt}"
    return hashlib.sha256(seed.encode("utf-8")).hexdigest()


def require_login() -> None:
    if not st.session_state.get("authentication_status"):
        st.warning("Please log in first.")
        st.stop()


def ensure_auth(
    authenticator,
    callback=None,
    key: str = "auto-login",
    location: str = "sidebar",
) -> Tuple[Optional[str], Optional[bool], Optional[str]]:
    name, auth_status, username = authenticator.login(
        location=location, key=key, callback=callback
    )
    if auth_status:
        auth_model = getattr(authenticator, "auth_model", None)
        repo = getattr(auth_model, "repo", None) if auth_model else None
        candidate_id = (
            username
            or st.session_state.get("player_access_key", "")
            or st.session_state.get("player_page_id", "")
        )
        if repo and candidate_id:
            player = repo.get_player_by_id(str(candidate_id))
            if player:
                remember_access(
                    {
                        "player": player,
                        "access_key": player.get("access_key", "")
                        or st.session_state.get("player_access_key", ""),
                    }
                )
    return name, auth_status, username


def ensure_session_context(repo) -> None:
    if st.session_state.get("session_id"):
        return
    session = get_active_session(repo)
    if session:
        set_session(session.get("id", ""), session.get("session_code", "Session"))
