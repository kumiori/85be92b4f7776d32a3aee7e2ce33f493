from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Dict, List, Optional


def _parse_iso(value: Any) -> Optional[datetime]:
    token = str(value or "").strip()
    if not token:
        return None
    try:
        parsed = datetime.fromisoformat(token.replace("Z", "+00:00"))
        if parsed.tzinfo is None:
            return parsed.replace(tzinfo=timezone.utc)
        return parsed.astimezone(timezone.utc)
    except Exception:
        return None


def filter_rows_to_session_window(
    rows: List[Dict[str, Any]], session: Dict[str, Any] | None
) -> List[Dict[str, Any]]:
    if not rows or not isinstance(session, dict):
        return rows

    start = _parse_iso(session.get("start")) or _parse_iso(session.get("created_at"))
    end = _parse_iso(session.get("end"))
    if not start and not end:
        return rows

    filtered: List[Dict[str, Any]] = []
    for row in rows:
        timestamp = _parse_iso(
            row.get("submitted_at") or row.get("timestamp") or row.get("created_at")
        )
        if timestamp is None:
            continue
        if start and timestamp < start:
            continue
        if end and timestamp > end:
            continue
        filtered.append(row)
    return filtered
