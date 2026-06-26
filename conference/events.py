from __future__ import annotations

from typing import Any


YOUNG_SESSION_CODE = "pisa-conference-session"
COMPLEXITY_SESSION_CODE = "petnica_2026"
UNESCO_SESSION_CODE = "global-session"
YOUNG_TEXT_ID = "pisa_session_v2"
COMPLEXITY_TEXT_ID = "petnica_2026"
LEGACY_COMPLEXITY_TEXT_ID = "complexity_session_v2"
COMPLEXITY_EVENT_CODE = "petnica_2026"
COMPLEXITY_EVENT_LABEL = "COMPLEXITY"
COMPLEXITY_EVENT_LOCATION = "Petnica"

YOUNG_OVERVIEW_PAGE = "pages/17_Young_Overview.py"
COMPLEXITY_OVERVIEW_PAGE = "pages/20_Complexity_Overview.py"


def _normalized_code(value: Any) -> str:
    return str(value or "").strip()


def _is_reserved_non_complexity_code(value: Any) -> bool:
    token = _normalized_code(value).lower()
    return token in {
        "",
        YOUNG_SESSION_CODE.lower(),
        UNESCO_SESSION_CODE.lower(),
        "global-session",
    }


def _looks_like_complexity_session(session: Any) -> bool:
    if not isinstance(session, dict):
        return False
    code = _normalized_code(session.get("session_code"))
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
    return "complex" in haystack


def _discover_complexity_session_code(repo: Any | None = None) -> str:
    notion_repo = getattr(repo, "notion_repo", repo)
    active = getattr(notion_repo, "get_active_session", None)
    if callable(active):
        session = active()
        if _looks_like_complexity_session(session):
            return _normalized_code(session.get("session_code"))

    sessions = getattr(notion_repo, "list_sessions", None)
    if callable(sessions):
        try:
            items = sessions(limit=50)
        except TypeError:
            items = sessions()
        for preferred_code in ("COMPLEXITY", COMPLEXITY_SESSION_CODE):
            match = next(
                (
                    item
                    for item in items
                    if _normalized_code(item.get("session_code")) == preferred_code
                ),
                None,
            )
            if match:
                return _normalized_code(match.get("session_code"))
        for item in items:
            if _looks_like_complexity_session(item):
                return _normalized_code(item.get("session_code"))
        global_match = next(
            (
                item
                for item in items
                if _normalized_code(item.get("session_code")).upper() == "GLOBAL-SESSION"
            ),
            None,
        )
        if global_match:
            return _normalized_code(global_match.get("session_code"))
    return COMPLEXITY_SESSION_CODE


def current_complexity_session_code(repo: Any | None = None) -> str:
    configured = _normalized_code(
        getattr(getattr(repo, "settings", None), "default_session_code", "") or ""
    )
    if configured and not _is_reserved_non_complexity_code(configured):
        return configured
    return _discover_complexity_session_code(repo)


def complexity_text_ids() -> tuple[str, ...]:
    return (COMPLEXITY_TEXT_ID, LEGACY_COMPLEXITY_TEXT_ID)


def text_ids_for_session_code(session_code: str) -> tuple[str, ...]:
    token = str(session_code or "").strip()
    if token == YOUNG_SESSION_CODE:
        return (YOUNG_TEXT_ID,)
    if token == UNESCO_SESSION_CODE:
        return ()
    if token:
        return complexity_text_ids()
    return ()
