from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any, Optional, Tuple

from infra.app_context import get_notion_repo
from infra.notion_repo import _execute_with_retry, _resolve_data_source_id
from infra.app_context import load_config


def _parse_iso(value: str) -> Optional[datetime]:
    raw = str(value or "").strip()
    if not raw:
        return None
    try:
        if raw.endswith("Z"):
            raw = raw[:-1] + "+00:00"
        parsed = datetime.fromisoformat(raw)
        if parsed.tzinfo is None:
            parsed = parsed.replace(tzinfo=timezone.utc)
        return parsed.astimezone(timezone.utc)
    except Exception:
        return None


def touch_player_presence(
    player_id: str,
    page: Optional[str] = None,
    session_slug: Optional[str] = None,
) -> Tuple[bool, str]:
    del page, session_slug
    cfg = load_config() or {}
    presence_cfg = cfg.get("presence") or {}
    if not bool(presence_cfg.get("enabled", True)):
        return True, ""
    if not bool(presence_cfg.get("update_last_seen_on_interaction", True)):
        return True, ""
    repo = get_notion_repo()
    if not repo:
        return False, "Notion repository unavailable."
    if not player_id:
        return False, "Missing player id."

    db_id = repo.players_db_id
    if not db_id:
        return False, "Players database id missing."
    if not repo._prop_exists(db_id, "last_seen"):  # noqa: SLF001
        return False, "Players schema missing 'last_seen' date property."

    target_player_id = player_id
    if "-" not in target_player_id:
        player = repo.get_player_by_id(target_player_id)
        resolved = (player or {}).get("id")
        if not resolved:
            return False, "Could not resolve player page id."
        target_player_id = str(resolved)

    try:
        now_iso = datetime.now(timezone.utc).isoformat()
        _execute_with_retry(
            repo.client.pages.update,
            page_id=target_player_id,
            properties={"last_seen": {"date": {"start": now_iso}}},
        )
        return True, ""
    except Exception as exc:
        return False, str(exc)


def count_active_users(window_minutes: int, session_id: Optional[str] = None) -> int:
    cfg = load_config() or {}
    if not bool((cfg.get("presence") or {}).get("enabled", True)):
        return 0
    repo = get_notion_repo()
    if not repo:
        return 0
    db_id = repo.players_db_id
    if not db_id or not repo._prop_exists(db_id, "last_seen"):  # noqa: SLF001
        return 0

    try:
        ds_id = _resolve_data_source_id(repo.client, db_id)
        session_prop = (
            repo._prop_name(db_id, "session", "relation")  # noqa: SLF001
            if session_id and repo._prop_exists(db_id, "session")  # noqa: SLF001
            else None
        )
        filters: list[dict[str, Any]] = [
            {
                "property": "last_seen",
                "date": {
                    "on_or_after": (
                        datetime.now(timezone.utc) - timedelta(minutes=max(1, window_minutes))
                    ).isoformat()
                },
            }
        ]
        if session_id and session_prop:
            filters.append(
                {"property": session_prop, "relation": {"contains": session_id}}
            )

        query: dict[str, Any] = {
            "data_source_id": ds_id,
            "filter": {"and": filters} if len(filters) > 1 else filters[0],
            "page_size": 100,
        }
        count = 0
        while True:
            payload = _execute_with_retry(repo.client.data_sources.query, **query)
            for page in payload.get("results", []):
                props = page.get("properties", {})
                seen = (props.get("last_seen") or {}).get("date", {})
                seen_dt = _parse_iso((seen or {}).get("start", ""))
                if seen_dt:
                    count += 1
            if not payload.get("has_more"):
                break
            query["start_cursor"] = payload.get("next_cursor")
        return count
    except Exception:
        return 0
