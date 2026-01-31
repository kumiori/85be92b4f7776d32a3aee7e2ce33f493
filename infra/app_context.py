from __future__ import annotations

import os
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


def _pick_id(config: Dict[str, Any], key: str, env_key: Optional[str] = None) -> str:
    notion_cfg = (config or {}).get("notion", {})
    if key in notion_cfg and notion_cfg[key]:
        return notion_cfg[key]
    secrets_cfg = st.secrets.get("notion", {})
    if key in secrets_cfg and secrets_cfg[key]:
        return secrets_cfg[key]
    if env_key:
        return os.getenv(env_key, "") or ""
    return ""


@st.cache_resource(show_spinner=False)
def get_notion_repo() -> Optional[NotionRepo]:
    config = load_config()
    return init_notion_repo(
        session_db_id=_pick_id(config, "ice_sessions_db_id")
        or _pick_id(config, "sessions_db_id")
        or _pick_id(config, "sessions"),
        players_db_id=_pick_id(config, "ice_players_db_id")
        or _pick_id(config, "players"),
        statements_db_id=_pick_id(config, "ice_statements_db_id")
        or _pick_id(config, "statements"),
        responses_db_id=_pick_id(config, "ice_responses_db_id")
        or _pick_id(config, "responses"),
        questions_db_id=_pick_id(config, "ice_questions_db_id")
        or _pick_id(config, "questions"),
        moderation_votes_db_id=_pick_id(config, "ice_moderation_votes_db_id")
        or _pick_id(config, "moderation_votes"),
        decisions_db_id=_pick_id(config, "ice_decisions_db_id")
        or _pick_id(config, "decisions"),
    )


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
