from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from conference.events import (
    UN_WG2_DEBUG_SESSION_CODE,
    UN_WG2_EVENT_LABEL,
    UN_WG2_SESSION_CODE,
    UN_WG2_TEXT_ID,
)


@dataclass(frozen=True)
class DebugSessionSpec:
    session_code: str
    production_session_code: str
    session_name: str
    session_title: str
    session_description: str
    session_order: int
    mode: str = "Non-linear"
    session_visualisation: str = "conference"


def wg2_debug_session_spec() -> DebugSessionSpec:
    """Return the single canonical persisted scope used for WG2 test runs."""
    return DebugSessionSpec(
        session_code=UN_WG2_DEBUG_SESSION_CODE,
        production_session_code=UN_WG2_SESSION_CODE,
        session_name="WG2 Debug",
        session_title=f"TEST · {UN_WG2_EVENT_LABEL}",
        session_description=(
            f"Dedicated test session for {UN_WG2_SESSION_CODE}. "
            f"Question set {UN_WG2_TEXT_ID}. Never aggregate with production."
        ),
        session_order=41,
    )


def debug_session_access_enabled(events: list[dict[str, Any]]) -> bool:
    """Reduce durable host controls; debug entry is closed by default."""
    enabled = False
    for event in sorted(events, key=lambda item: str(item.get("timestamp") or "")):
        event_type = str(event.get("event_type") or "").strip()
        if event_type == "debug_session_access_enabled":
            enabled = True
        elif event_type == "debug_session_access_disabled":
            enabled = False
    return enabled


def ensure_test_session(
    notion_repo: Any, spec: DebugSessionSpec
) -> tuple[dict[str, Any], bool]:
    """Create or reconcile one persisted test session without touching production."""
    test_code = str(spec.session_code or "").strip()
    production_code = str(spec.production_session_code or "").strip()
    if not test_code or not production_code:
        raise ValueError("Test and production session codes are required.")
    if test_code == production_code:
        raise ValueError("A test session must not reuse the production session code.")

    session = notion_repo.get_session_by_code(test_code)
    created = session is None
    if session is None:
        session = notion_repo.create_session(test_code, spec.mode)
    if not session or not session.get("id"):
        raise RuntimeError("The test session could not be created or resolved.")

    updated = notion_repo.update_session(
        str(session["id"]),
        session_active=False,
        active=False,
        session_name=spec.session_name,
        session_title=spec.session_title,
        session_description=spec.session_description,
        session_visualisation=spec.session_visualisation,
        session_order=spec.session_order,
        status="Lobby",
        mode=spec.mode,
    )
    if not updated:
        raise RuntimeError("The test session metadata could not be persisted.")
    return dict(updated), created
