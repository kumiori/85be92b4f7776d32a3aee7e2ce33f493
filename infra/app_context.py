from __future__ import annotations

from pathlib import Path
from typing import Any, Dict, Optional

import streamlit as st
import yaml
from yaml.loader import SafeLoader

from infra.key_auth import AuthenticateWithKey
from infra.notion_repo import NotionRepo, init_notion_repo

CONFIG_PATH = Path(__file__).resolve().parents[1] / "config.yaml"


@st.cache_data(show_spinner=False)
def load_config() -> Dict[str, Any]:
    if not CONFIG_PATH.exists():
        return {}
    with CONFIG_PATH.open("r", encoding="utf-8") as fh:
        return yaml.load(fh, Loader=SafeLoader) or {}


def _pick_id(key: str) -> str:
    secrets_cfg = st.secrets.get("notion", {})
    if key in secrets_cfg and secrets_cfg[key]:
        return str(secrets_cfg[key])
    return ""


@st.cache_resource(show_spinner=False)
def get_notion_repo() -> Optional[NotionRepo]:
    repo = init_notion_repo(
        session_db_id=_pick_id("ice_sessions_db_id")
        or _pick_id("sessions_db_id")
        or _pick_id("sessions"),
        players_db_id=_pick_id("ice_players_db_id") or _pick_id("players"),
        statements_db_id=_pick_id("ice_statements_db_id") or _pick_id("statements"),
        responses_db_id=_pick_id("ice_responses_db_id") or _pick_id("responses"),
        questions_db_id=_pick_id("ice_questions_db_id") or _pick_id("questions"),
        moderation_votes_db_id=_pick_id("ice_moderation_votes_db_id")
        or _pick_id("moderation_votes"),
        decisions_db_id=_pick_id("ice_decisions_db_id") or _pick_id("decisions"),
        highlights_db_id=_pick_id("ice_highlights_db_id") or _pick_id("highlights"),
    )
    if repo and (not hasattr(repo, "list_decisions") or not hasattr(repo, "upsert_highlight")):
        reset_notion_repo_cache()
        repo = init_notion_repo(
            session_db_id=_pick_id("ice_sessions_db_id")
            or _pick_id("sessions_db_id")
            or _pick_id("sessions"),
            players_db_id=_pick_id("ice_players_db_id") or _pick_id("players"),
            statements_db_id=_pick_id("ice_statements_db_id") or _pick_id("statements"),
            responses_db_id=_pick_id("ice_responses_db_id") or _pick_id("responses"),
            questions_db_id=_pick_id("ice_questions_db_id") or _pick_id("questions"),
            moderation_votes_db_id=_pick_id("ice_moderation_votes_db_id")
            or _pick_id("moderation_votes"),
            decisions_db_id=_pick_id("ice_decisions_db_id") or _pick_id("decisions"),
            highlights_db_id=_pick_id("ice_highlights_db_id") or _pick_id("highlights"),
        )
    return repo


def reset_notion_repo_cache() -> None:
    try:
        get_notion_repo.clear()
    except Exception:
        pass


def get_authenticator(repo: Optional[NotionRepo]) -> AuthenticateWithKey:
    config = load_config()
    credentials = config.get("credentials", {})
    cookie = config.get("cookie", {})
    notion_secrets = st.secrets.get("notion", {})
    default_session_code = (
        notion_secrets.get("default_session_code")
        or config.get("default_session_code")
        or "GLOBAL-SESSION"
    )
    return AuthenticateWithKey(
        credentials,
        cookie.get("name", "iceice-baby"),
        cookie.get("key", "supersecret_cookie_key"),
        cookie.get("expiry_days", 3),
        notion_repo=repo,
        default_session_code=default_session_code,
    )


def get_active_session(repo: Optional[NotionRepo]) -> Optional[Dict[str, Any]]:
    if not repo:
        return None
    active = repo.get_active_session()
    if active:
        return active
    config = load_config()
    notion_secrets = st.secrets.get("notion", {})
    default_code = (
        notion_secrets.get("default_session_code")
        or config.get("default_session_code")
        or "GLOBAL-SESSION"
    )
    return repo.get_session_by_code(default_code)
