from __future__ import annotations

import inspect
from typing import Any, Dict, Optional

import streamlit as st
from notion_client import Client

from conference.repo import ConferenceRepo
from conference.settings import load_conference_settings
from infra.app_context import get_notion_repo


REPO_CACHE_VERSION = "2026-06-26-event-session-split-v6"


@st.cache_resource(show_spinner=False)
def _build_conference_repo(version: str) -> Optional[ConferenceRepo]:
    settings = load_conference_settings()
    base_repo = get_notion_repo()
    if base_repo:
        return ConferenceRepo(base_repo, settings)
    if settings.notion_token:
        client = Client(auth=settings.notion_token, notion_version=settings.notion_version)
        fallback = type("FallbackRepo", (), {"client": client})()
        return ConferenceRepo(fallback, settings)
    return None


def get_conference_repo() -> Optional[ConferenceRepo]:
    repo = _build_conference_repo(REPO_CACHE_VERSION)
    save_method = getattr(repo, "save_session_response_set", None) if repo else None
    resolve_method = getattr(repo, "resolve_session", None) if repo else None
    rows_method = getattr(repo, "get_session_rows", None) if repo else None
    latest_method = getattr(repo, "latest_submission_by_access_key_hash", None) if repo else None
    if repo and callable(save_method):
        try:
            save_params = inspect.signature(save_method).parameters
            resolve_params = inspect.signature(resolve_method).parameters if callable(resolve_method) else {}
            rows_params = inspect.signature(rows_method).parameters if callable(rows_method) else {}
            latest_params = (
                inspect.signature(latest_method).parameters if callable(latest_method) else {}
            )
            if (
                "payload" not in save_params
                or "prefer_active" not in resolve_params
                or "text_ids" not in rows_params
                or "text_ids" not in latest_params
            ):
                _build_conference_repo.clear()
                repo = _build_conference_repo(REPO_CACHE_VERSION)
        except Exception:
            pass
    return repo


def _resolve_conference_bundle(session_code: str = "", prefer_active: bool = False) -> Dict[str, Any]:
    repo = get_conference_repo()
    if not repo or not repo.is_ready():
        return {"session": None}
    try:
        session = repo.resolve_session(session_code=session_code, prefer_active=prefer_active)
    except TypeError:
        session = repo.resolve_session(session_code=session_code)
    return {"session": session}


@st.cache_data(ttl=5, show_spinner=False)
def get_conference_bundle(session_code: str = "", prefer_active: bool = False) -> Dict[str, Any]:
    bundle = _resolve_conference_bundle(session_code=session_code, prefer_active=prefer_active)
    if bundle.get("session") is not None:
        return bundle
    get_conference_bundle.clear()
    return _resolve_conference_bundle(session_code=session_code, prefer_active=prefer_active)
