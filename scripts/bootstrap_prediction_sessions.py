#!/usr/bin/env python3
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from conference.context import get_conference_repo
from conference.events import (
    PREDICTION_DEBUG_SESSION_CODE,
    PREDICTION_SESSION_CODE,
    event_config_for_slug,
)


def _ensure(notion_repo, slug: str, code: str, order: int) -> dict:
    config = event_config_for_slug(slug)
    session = notion_repo.get_session_by_code(code)
    created = False
    if not session:
        session = notion_repo.create_session(code, "Non-linear")
        created = True
    session = notion_repo.update_session(
        session["id"],
        session_active=False,
        active=False,
        session_name=config.label,
        session_title=config.title,
        session_description=f"{config.subtitle} · {config.place} · {config.dates}",
        session_visualisation="conference",
        session_order=order,
        status="Lobby",
        mode="Non-linear",
        start="2026-09-07",
        end="2026-09-11",
    )
    return {"created": created, "id": session.get("id"), "session_code": code}


def main() -> None:
    repo = get_conference_repo()
    notion_repo = getattr(repo, "notion_repo", None)
    if not repo or not repo.is_ready() or notion_repo is None:
        raise SystemExit("Conference repo unavailable")
    players_db_id = notion_repo._players_db_id(None)
    notion_repo.client.databases.update(
        database_id=players_db_id,
        properties={
            "institution": {"rich_text": {}},
            "base_location": {"rich_text": {}},
        },
    )
    print(
        {
            "player_profile_schema": ["institution", "base_location"],
            "production": _ensure(notion_repo, "prediction", PREDICTION_SESSION_CODE, 50),
            "debug": _ensure(notion_repo, "prediction_debug", PREDICTION_DEBUG_SESSION_CODE, 51),
        }
    )


if __name__ == "__main__":
    main()
