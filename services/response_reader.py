from __future__ import annotations

import json
import re
from typing import Any, Dict, Optional, Tuple

import streamlit as st

from infra.app_context import get_active_session, get_notion_repo, load_config
from infra.event_logger import get_module_logger
from repositories.interaction_repo import NotionInteractionRepository

LOGGER = get_module_logger("iceicebaby.responses")


def _slugify(value: str) -> str:
    txt = re.sub(r"[^a-zA-Z0-9]+", "-", str(value or "").strip().lower())
    return txt.strip("-")


def _interaction_db_id() -> str:
    notion_cfg = st.secrets.get("notion", {})
    return str(
        notion_cfg.get("ice_interaction_responses_db_id")
        or notion_cfg.get("interaction_responses_db_id")
        or notion_cfg.get("ice_responses_db_id")
        or ""
    )


def _resolve_session(session_slug: Optional[str]) -> Optional[Dict[str, Any]]:
    repo = get_notion_repo()
    if not repo:
        return None
    sessions = repo.list_sessions(limit=200)
    by_slug = {_slugify(s.get("session_code", "")): s for s in sessions}
    requested = _slugify(session_slug or "")
    if requested and requested in by_slug:
        return by_slug[requested]
    if session_slug:
        for s in sessions:
            if str(s.get("id", "")) == str(session_slug):
                return s

    cfg = load_config() or {}
    default_slug = _slugify(
        (((cfg.get("overview") or {}).get("default_session_slug")) or "global-session")
    )
    if default_slug in by_slug:
        return by_slug[default_slug]
    active = get_active_session(repo)
    if active:
        return active
    LOGGER.warning("active session not found; fallback to first available session")
    return sessions[0] if sessions else None


def normalize_response_row(
    notion_row: Dict[str, Any],
    session_slug: str,
    session_name: str,
) -> Dict[str, Any]:
    raw_json = notion_row.get("value_json")
    parsed_json: Dict[str, Any] | list[Any] | str
    if isinstance(raw_json, (dict, list)):
        parsed_json = raw_json
    elif isinstance(raw_json, str):
        try:
            parsed_json = json.loads(raw_json)
        except Exception:
            LOGGER.warning("malformed response JSON for response_id=%s", notion_row.get("response_id", ""))
            parsed_json = {"parse_error": True, "raw": raw_json}
    else:
        parsed_json = {}

    return {
        "response_id": notion_row.get("response_id", ""),
        "session_slug": session_slug,
        "session_name": session_name,
        "player_id": notion_row.get("player_id"),
        "device_id": notion_row.get("device_id"),
        "submitted_at": notion_row.get("timestamp", notion_row.get("created_at", "")),
        "timestamp": notion_row.get("timestamp", notion_row.get("created_at", "")),
        "question_id": notion_row.get("question_id", notion_row.get("item_id", "")),
        "item_id": notion_row.get("item_id", notion_row.get("question_id", "")),
        "response_value": notion_row.get("response_value", notion_row.get("value")),
        "value_label": notion_row.get("value_label", ""),
        "value_json": parsed_json,
        "question_type": notion_row.get("question_type", ""),
        "score": notion_row.get("score"),
        "access_key": notion_row.get("access_key", ""),
    }


def fetch_session_responses(session_slug: Optional[str] = None) -> Tuple[Dict[str, Any], list[Dict[str, Any]]]:
    repo = get_notion_repo()
    if not repo:
        return {}, []
    interaction_db_id = _interaction_db_id()
    if not interaction_db_id:
        return {}, []
    session = _resolve_session(session_slug)
    if not session:
        return {}, []
    session_id = str(session.get("id") or "")
    session_name = str(session.get("session_name") or session.get("session_code") or "Session")
    session_slug_raw = str(session.get("session_id") or session.get("session_code") or session_name)
    normalized_slug = _slugify(session_slug_raw)
    if not session_id:
        return {}, []

    interaction_repo = NotionInteractionRepository(repo, interaction_db_id)
    rows = interaction_repo.get_responses(session_id)
    return session, [
        normalize_response_row(r, normalized_slug, session_name) for r in rows
    ]
