#!/usr/bin/env python3
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from conference.context import get_conference_repo
from conference.events import (
    UN_WG2_EVENT_LABEL,
    UN_WG2_EVENT_LOCATION,
    UN_WG2_SESSION_CODE,
    UN_WG2_TEXT_ID,
)


def main() -> None:
    repo = get_conference_repo()
    notion_repo = getattr(repo, "notion_repo", None)
    if not repo or not repo.is_ready() or notion_repo is None:
        raise SystemExit("Conference repo unavailable")

    session = notion_repo.get_session_by_code(UN_WG2_SESSION_CODE)
    created = False
    if not session:
        session = notion_repo.create_session(UN_WG2_SESSION_CODE, "Non-linear")
        created = True

    session = notion_repo.update_session(
        session["id"],
        session_active=False,
        active=False,
        session_name="WG2 Core",
        session_title=UN_WG2_EVENT_LABEL,
        session_description=(
            f"{UN_WG2_EVENT_LABEL} / {UN_WG2_EVENT_LOCATION} "
            f"registered questionnaire · question set {UN_WG2_TEXT_ID}"
        ),
        session_visualisation="conference",
        session_order=40,
        status="Lobby",
        mode="Non-linear",
    )

    print(
        {
            "created": created,
            "id": session.get("id"),
            "session_code": session.get("session_code"),
            "session_name": session.get("session_name"),
            "session_title": session.get("session_title"),
            "session_description": session.get("session_description"),
            "active": session.get("active"),
            "start": session.get("start"),
            "created_at": session.get("created_at"),
        }
    )


if __name__ == "__main__":
    main()
