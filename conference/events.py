from __future__ import annotations

from dataclasses import dataclass
from typing import Any


YOUNG_SESSION_CODE = "pisa-conference-session"
COMPLEXITY_SESSION_CODE = "petnica_2026"
DALAMBERTIENNES_SESSION_CODE = "dalembertiennes_2026"
UNESCO_SESSION_CODE = "global-session"
YOUNG_TEXT_ID = "pisa_session_v2"
COMPLEXITY_TEXT_ID = "petnica_2026"
LEGACY_COMPLEXITY_TEXT_ID = "complexity_session_v2"
DALAMBERTIENNES_TEXT_ID = "dalembertiennes_v0"
COMPLEXITY_EVENT_CODE = COMPLEXITY_SESSION_CODE
COMPLEXITY_EVENT_LABEL = "COMPLEXITY"
COMPLEXITY_EVENT_LOCATION = "Petnica"
DALAMBERTIENNES_EVENT_CODE = DALAMBERTIENNES_SESSION_CODE
DALAMBERTIENNES_EVENT_LABEL = "D'Alembertiennes"
DALAMBERTIENNES_EVENT_LOCATION = "D'Alembert Lab"

YOUNG_OVERVIEW_PAGE = "pages/17_Young_Overview.py"
COMPLEXITY_ENTRY_PAGE = "pages/15_Pisa_Meeting.py"
COMPLEXITY_HOST_PAGE = "pages/16_Pisa_Meeting_Host.py"
COMPLEXITY_OVERVIEW_PAGE = "pages/20_Complexity_Overview.py"
DALAMBERTIENNES_ENTRY_PAGE = "pages/21_Dalembertiennes.py"
DALAMBERTIENNES_HOST_PAGE = "pages/23_Dalembertiennes_Host.py"
DALAMBERTIENNES_OVERVIEW_PAGE = "pages/22_Dalembertiennes_Overview.py"


@dataclass(frozen=True)
class ConferenceEventConfig:
    slug: str
    session_code: str
    label: str
    location: str
    text_ids: tuple[str, ...]
    primary_text_id: str
    question_set_id: str
    schema_id: str
    questionnaire_page: str
    overview_page: str
    host_page: str
    aliases: tuple[str, ...] = ()


_EVENT_CONFIGS = (
    ConferenceEventConfig(
        slug="complexity",
        session_code=COMPLEXITY_SESSION_CODE,
        label=COMPLEXITY_EVENT_LABEL,
        location=COMPLEXITY_EVENT_LOCATION,
        text_ids=(COMPLEXITY_TEXT_ID, LEGACY_COMPLEXITY_TEXT_ID),
        primary_text_id=COMPLEXITY_TEXT_ID,
        question_set_id="complexity_v2",
        schema_id="complexity_v2",
        questionnaire_page=COMPLEXITY_ENTRY_PAGE,
        overview_page=COMPLEXITY_OVERVIEW_PAGE,
        host_page=COMPLEXITY_HOST_PAGE,
        aliases=("complexity", "petnica", COMPLEXITY_SESSION_CODE),
    ),
    ConferenceEventConfig(
        slug="dalembertiennes",
        session_code=DALAMBERTIENNES_SESSION_CODE,
        label=DALAMBERTIENNES_EVENT_LABEL,
        location=DALAMBERTIENNES_EVENT_LOCATION,
        text_ids=(DALAMBERTIENNES_TEXT_ID,),
        primary_text_id=DALAMBERTIENNES_TEXT_ID,
        question_set_id=DALAMBERTIENNES_TEXT_ID,
        schema_id=DALAMBERTIENNES_TEXT_ID,
        questionnaire_page=DALAMBERTIENNES_ENTRY_PAGE,
        overview_page=DALAMBERTIENNES_OVERVIEW_PAGE,
        host_page=DALAMBERTIENNES_HOST_PAGE,
        aliases=("dalembertiennes", DALAMBERTIENNES_SESSION_CODE),
    ),
)
_EVENT_CONFIG_BY_CODE = {item.session_code: item for item in _EVENT_CONFIGS}
_EVENT_CONFIG_BY_ALIAS = {
    alias.lower(): item for item in _EVENT_CONFIGS for alias in item.aliases
}


def _normalized_code(value: Any) -> str:
    return str(value or "").strip()


def _query_param_value(name: str) -> str:
    try:
        import streamlit as st

        return str(st.query_params.get(name, "") or "").strip()
    except Exception:
        return ""


def _requested_event_token() -> str:
    return _query_param_value("event") or _query_param_value("session")


def _canonical_session_code(value: Any) -> str:
    token = _normalized_code(value)
    if not token:
        return ""
    config = _EVENT_CONFIG_BY_ALIAS.get(token.lower())
    return config.session_code if config else token


def event_config_for_session_code(session_code: str) -> ConferenceEventConfig | None:
    return _EVENT_CONFIG_BY_CODE.get(_canonical_session_code(session_code))


def _normalized_event_status(session: Any | None = None) -> str:
    raw_status = (
        str(session.get("status") or "").strip().lower()
        if isinstance(session, dict)
        else ""
    )
    if raw_status in {"archived", "archive"}:
        return "archived"
    if raw_status in {"closed", "done", "complete", "completed"}:
        return "closed"
    if raw_status in {"open", "live", "active"}:
        return "open"
    if raw_status in {"draft", "lobby", "setup", "planned"}:
        return "draft"
    is_active = bool(session.get("session_active") or session.get("active")) if isinstance(session, dict) else False
    return "open" if is_active else "draft"


def _event_write_enabled(event_status: str) -> bool:
    return str(event_status or "").strip().lower() not in {"closed", "archived"}


def conference_event_context(
    session: Any | None = None,
    *,
    session_code: str = "",
) -> dict[str, Any]:
    raw_code = session_code or (
        str(session.get("session_code") or "") if isinstance(session, dict) else ""
    )
    resolved_code = _canonical_session_code(raw_code)
    config = event_config_for_session_code(resolved_code)
    session_name = (
        str(session.get("session_name") or "").strip() if isinstance(session, dict) else ""
    )
    session_title = (
        str(session.get("session_title") or "").strip() if isinstance(session, dict) else ""
    )
    event_label = session_title or session_name or (config.label if config else resolved_code)
    event_location = config.location if config else ""
    event_status = _normalized_event_status(session)
    return {
        "event_slug": config.slug if config else resolved_code.lower(),
        "event_code": resolved_code,
        "event_label": event_label,
        "event_location": event_location,
        "session_code": resolved_code,
        "question_set_id": config.question_set_id if config else resolved_code,
        "text_id": config.primary_text_id if config else resolved_code,
        "schema_id": config.schema_id if config else resolved_code,
        "response_scope": "event_specific",
        "event_status": event_status,
        "write_enabled": _event_write_enabled(event_status),
        "questionnaire_page": (
            config.questionnaire_page if config else COMPLEXITY_ENTRY_PAGE
        ),
        "overview_page": config.overview_page if config else COMPLEXITY_OVERVIEW_PAGE,
        "host_page": config.host_page if config else COMPLEXITY_HOST_PAGE,
    }


def conference_event_options(repo: Any | None = None) -> list[dict[str, Any]]:
    options: list[dict[str, Any]] = []
    seen: set[str] = set()
    for config in _EVENT_CONFIGS:
        session = None
        if repo and hasattr(repo, "resolve_session"):
            try:
                session = repo.resolve_session(session_code=config.session_code)
            except Exception:
                session = None
        context = conference_event_context(session, session_code=config.session_code)
        code = str(context["session_code"])
        if code in seen:
            continue
        seen.add(code)
        options.append(
            {
                "event_slug": context["event_slug"],
                "session_code": code,
                "event_label": context["event_label"],
                "event_location": context["event_location"],
                "event_status": context["event_status"],
                "write_enabled": context["write_enabled"],
                "questionnaire_page": context["questionnaire_page"],
                "overview_page": context["overview_page"],
                "host_page": context["host_page"],
                "available": bool(session),
            }
        )
    return options


def _is_reserved_non_complexity_code(value: Any) -> bool:
    token = _canonical_session_code(value).lower()
    return token in {
        "",
        YOUNG_SESSION_CODE.lower(),
        UNESCO_SESSION_CODE.lower(),
        "global-session",
    }


def _looks_like_complexity_session(session: Any) -> bool:
    if not isinstance(session, dict):
        return False
    code = _canonical_session_code(session.get("session_code"))
    if _is_reserved_non_complexity_code(code):
        return False
    haystack = " ".join(
        [
            code,
            _normalized_code(session.get("session_name")),
            _normalized_code(session.get("session_title")),
            _normalized_code(session.get("session_description")),
        ]
    ).lower()
    return "complex" in haystack or "dalembert" in haystack


def _discover_complexity_session_code(repo: Any | None = None) -> str:
    notion_repo = getattr(repo, "notion_repo", repo)
    active = getattr(notion_repo, "get_active_session", None)
    if callable(active):
        session = active()
        if _looks_like_complexity_session(session):
            return _canonical_session_code(session.get("session_code"))

    sessions = getattr(notion_repo, "list_sessions", None)
    if callable(sessions):
        try:
            items = sessions(limit=50)
        except TypeError:
            items = sessions()
        for preferred_code in (
            "COMPLEXITY",
            COMPLEXITY_SESSION_CODE,
            DALAMBERTIENNES_SESSION_CODE,
        ):
            match = next(
                (
                    item
                    for item in items
                    if _canonical_session_code(item.get("session_code")) == preferred_code
                ),
                None,
            )
            if match:
                return _canonical_session_code(match.get("session_code"))
        for item in items:
            if _looks_like_complexity_session(item):
                return _canonical_session_code(item.get("session_code"))
        global_match = next(
            (
                item
                for item in items
                if _canonical_session_code(item.get("session_code")).upper()
                == "GLOBAL-SESSION"
            ),
            None,
        )
        if global_match:
            return _canonical_session_code(global_match.get("session_code"))
    return COMPLEXITY_SESSION_CODE


def current_complexity_session_code(repo: Any | None = None) -> str:
    requested = _canonical_session_code(_requested_event_token())
    if requested and not _is_reserved_non_complexity_code(requested):
        return requested
    configured = _canonical_session_code(
        getattr(getattr(repo, "settings", None), "default_session_code", "") or ""
    )
    if configured and not _is_reserved_non_complexity_code(configured):
        return configured
    return _discover_complexity_session_code(repo)


def complexity_text_ids() -> tuple[str, ...]:
    return (COMPLEXITY_TEXT_ID, LEGACY_COMPLEXITY_TEXT_ID)


def text_ids_for_session_code(session_code: str) -> tuple[str, ...]:
    token = _canonical_session_code(session_code)
    if token == YOUNG_SESSION_CODE:
        return (YOUNG_TEXT_ID,)
    if token == UNESCO_SESSION_CODE:
        return ()
    config = event_config_for_session_code(token)
    if config:
        return config.text_ids
    if token:
        return complexity_text_ids()
    return ()
