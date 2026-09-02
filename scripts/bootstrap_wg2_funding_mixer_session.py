#!/usr/bin/env python3
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from conference.context import get_conference_repo
from conference.wg2_funding_mixer import DEFAULT_SESSION_CODE, TEXT_ID


def main() -> None:
    repo = get_conference_repo()
    notion_repo = getattr(repo, "notion_repo", None)
    if not repo or not repo.is_ready() or notion_repo is None:
        raise SystemExit("Conference repo unavailable")

    session = notion_repo.get_session_by_code(DEFAULT_SESSION_CODE)
    created = False
    if not session:
        session = notion_repo.create_session(DEFAULT_SESSION_CODE, "Non-linear")
        created = True

    session = notion_repo.update_session(
        session["id"],
        session_active=False,
        active=False,
        session_name="WG2 Meeting 3",
        session_title="WG2 — 100 seed tokens",
        session_description=(
            "WG2 coordination meeting funding mixer · "
            f"interaction seed_funding_allocation · text {TEXT_ID}"
        ),
        session_visualisation="funding_mixer",
        session_order=41,
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
            "status": session.get("status"),
        }
    )


if __name__ == "__main__":
    main()
