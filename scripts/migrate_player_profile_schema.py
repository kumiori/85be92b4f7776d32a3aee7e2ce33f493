#!/usr/bin/env python3
from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from conference.context import get_conference_repo


PROFILE_PROPERTIES = {
    "email": {"email": {}},
    "institution": {"rich_text": {}},
    "base_location": {"rich_text": {}},
    "base_location_label": {"rich_text": {}},
    "base_location_place_id": {"rich_text": {}},
    "base_location_lat": {"number": {"format": "number"}},
    "base_location_lon": {"number": {"format": "number"}},
}


def main() -> None:
    repo = get_conference_repo()
    notion_repo = getattr(repo, "notion_repo", None)
    if not repo or not repo.is_ready() or notion_repo is None:
        raise SystemExit("Conference repository is unavailable.")
    players_db_id = notion_repo._players_db_id(None)
    before = notion_repo._db_props(players_db_id)
    desired = dict(PROFILE_PROPERTIES)
    if "session" not in before:
        from infra.notion_repo import _resolve_data_source_id

        sessions_db_id = notion_repo._sessions_db_id(None)
        desired["session"] = {
            "relation": {
                "data_source_id": _resolve_data_source_id(
                    notion_repo.client, sessions_db_id
                ),
                "single_property": {},
            }
        }
    missing = {
        name: definition
        for name, definition in desired.items()
        if name not in before
    }
    if missing:
        from infra.notion_repo import _cached_retrieve, _resolve_data_source_id

        data_source_id = _resolve_data_source_id(notion_repo.client, players_db_id)
        notion_repo.client.data_sources.update(
            data_source_id=data_source_id,
            properties=missing,
        )
        _cached_retrieve.clear()
    after = notion_repo._db_props(players_db_id)
    print(
        json.dumps(
            {
                "added": sorted(missing),
                "verified": {
                    name: str((after.get(name) or {}).get("type") or "missing")
                    for name in desired
                },
                "session_membership_property": (
                    notion_repo._player_prop_name(players_db_id, "session_membership")
                    or "missing"
                ),
            },
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
