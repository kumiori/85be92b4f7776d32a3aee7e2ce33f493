#!/usr/bin/env python3
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from conference.context import get_conference_repo
from conference.test_sessions import ensure_test_session, wg2_debug_session_spec


def main() -> None:
    repo = get_conference_repo()
    notion_repo = getattr(repo, "notion_repo", None)
    if not repo or not repo.is_ready() or notion_repo is None:
        raise SystemExit("Conference repo unavailable")

    session, created = ensure_test_session(
        notion_repo,
        wg2_debug_session_spec(),
    )
    print(
        {
            "created": created,
            "id": session.get("id"),
            "session_code": session.get("session_code"),
            "session_title": session.get("session_title"),
            "status": session.get("status"),
        }
    )


if __name__ == "__main__":
    main()
