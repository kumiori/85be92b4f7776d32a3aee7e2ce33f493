from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict

import tomllib


DEFAULT_NOTION_VERSION = "2025-09-03"
DEFAULT_SESSION_CODE = "petnica_2026"


@dataclass(frozen=True)
class ConferenceSettings:
    notion_token: str
    notion_version: str
    session_responses_db_id: str
    default_session_code: str
    debug: bool


def _load_local_secrets() -> Dict[str, Any]:
    candidates = [
        Path.cwd() / ".streamlit" / "secrets.toml",
        Path(__file__).resolve().parents[1] / ".streamlit" / "secrets.toml",
    ]
    for path in candidates:
        if not path.exists():
            continue
        try:
            with path.open("rb") as handle:
                payload = tomllib.load(handle)
            if isinstance(payload, dict):
                return payload
        except Exception:
            return {}
    return {}


def _notion_secrets() -> Dict[str, Any]:
    secrets = _load_local_secrets().get("notion", {})
    return secrets if isinstance(secrets, dict) else {}


def _get_secret(name: str, *aliases: str, default: str = "") -> str:
    notion_secrets = _notion_secrets()

    env_value = str(os.getenv(name, "")).strip()
    if env_value:
        return env_value

    for alias in aliases:
        alias_env = str(os.getenv(alias, "")).strip()
        if alias_env:
            return alias_env
        secret_value = str(
            notion_secrets.get(alias.lower(), "") or notion_secrets.get(alias, "")
        ).strip()
        if secret_value:
            return secret_value
    return default


def load_conference_settings() -> ConferenceSettings:
    return ConferenceSettings(
        notion_token=_get_secret("NOTION_TOKEN", "api_key", "token", default=""),
        notion_version=_get_secret(
            "NOTION_VERSION",
            "notion_version",
            default=DEFAULT_NOTION_VERSION,
        ),
        session_responses_db_id=_get_secret(
            "ICE_INTERACTION_RESPONSES_DB_ID",
            "ice_interaction_responses_db_id",
            "interaction_responses_db_id",
            "ice_responses_db_id",
            default="",
        ),
        default_session_code=_get_secret(
            "CONFERENCE_SESSION_CODE",
            "conference_session_code",
            default=DEFAULT_SESSION_CODE,
        ),
        debug=_get_secret("CONFERENCE_DEBUG", "conference_debug", default="0") == "1",
    )
