from __future__ import annotations

from copy import deepcopy
from datetime import datetime, timezone
import hashlib
from typing import Any, Iterable, Mapping

from infra.key_codec import hex_to_emoji, split_emoji_symbols


LOCATION_DEBOUNCE_SECONDS = 0.65
HOST_ROLES = {
    "admin",
    "owner",
    "organiser",
    "co-organiser",
    "co_organiser",
    "developer",
    "host",
}


def host_role_allowed(role: str) -> bool:
    return str(role or "").strip().lower() in HOST_ROLES


def location_lookup_due(
    *,
    query: str,
    scheduled_query: str,
    scheduled_at: float,
    attempted_query: str,
    now: float,
    debounce_seconds: float = LOCATION_DEBOUNCE_SECONDS,
) -> bool:
    token = str(query or "").strip()
    return bool(
        token
        and token == str(scheduled_query or "").strip()
        and token != str(attempted_query or "").strip()
        and float(now) - float(scheduled_at or 0.0) >= float(debounce_seconds)
    )


def parse_opencage_result(payload: Any, query: str) -> dict[str, Any]:
    token = str(query or "").strip()
    results = payload.get("results") if isinstance(payload, Mapping) else []
    if not results:
        raise LookupError("No location match found.")
    first = results[0] if isinstance(results[0], Mapping) else {}
    geometry = first.get("geometry") if isinstance(first.get("geometry"), Mapping) else {}
    components = (
        first.get("components") if isinstance(first.get("components"), Mapping) else {}
    )
    lat = geometry.get("lat")
    lng = geometry.get("lng")
    if lat is None or lng is None:
        raise LookupError("The location match did not include coordinates.")
    city = (
        components.get("city")
        or components.get("town")
        or components.get("village")
        or components.get("municipality")
        or components.get("county")
        or ""
    )
    region = (
        components.get("state")
        or components.get("region")
        or components.get("state_district")
        or ""
    )
    country = components.get("country") or ""
    latitude = float(lat)
    longitude = float(lng)
    return {
        "raw_input": token,
        "resolved_label": str(first.get("formatted") or token).strip(),
        "country": str(country or "").strip(),
        "region": str(region or "").strip(),
        "city": str(city or "").strip(),
        "approximate_latitude": latitude,
        "approximate_longitude": longitude,
        "source": "opencage",
        "confirmation_state": "pending",
        "lookup_status": "success",
        "lookup_error": "",
        # Legacy keys remain populated for existing overview and export readers.
        "coordinates": f"{latitude:.6f}, {longitude:.6f}",
        "coordinates_consent": "",
        "geocode_query": token,
        "geocode_label": str(first.get("formatted") or token).strip(),
        "geocode_source": "opencage",
    }


def location_lookup_failure(current: Any, query: str, error: str) -> dict[str, Any]:
    source = dict(current) if isinstance(current, Mapping) else {}
    source.update(
        {
            "raw_input": str(query or "").strip(),
            "resolved_label": "",
            "country": "",
            "region": "",
            "city": "",
            "approximate_latitude": None,
            "approximate_longitude": None,
            "source": "opencage",
            "confirmation_state": "lookup_failed",
            "lookup_status": "failure",
            "lookup_error": str(error or "").strip(),
            "coordinates": "",
            "coordinates_consent": "",
            "geocode_query": str(query or "").strip(),
            "geocode_label": "",
            "geocode_source": "opencage",
        }
    )
    return source


def confirm_location(current: Any) -> dict[str, Any]:
    source = dict(current) if isinstance(current, Mapping) else {}
    source["confirmation_state"] = "confirmed"
    source["coordinates_consent"] = "lookup"
    return source


def correct_location(
    current: Any,
    *,
    resolved_label: str,
    country: str,
    region: str,
    city: str,
    latitude: Any = None,
    longitude: Any = None,
) -> dict[str, Any]:
    source = dict(current) if isinstance(current, Mapping) else {}

    def _coordinate(value: Any) -> float | None:
        token = str(value or "").strip()
        if not token:
            return None
        return float(token)

    lat = _coordinate(latitude)
    lng = _coordinate(longitude)
    source.update(
        {
            "resolved_label": str(resolved_label or "").strip(),
            "country": str(country or "").strip(),
            "region": str(region or "").strip(),
            "city": str(city or "").strip(),
            "approximate_latitude": lat,
            "approximate_longitude": lng,
            "source": "manual_correction",
            "confirmation_state": "corrected",
            "lookup_status": "success",
            "lookup_error": "",
            "coordinates": (
                f"{lat:.6f}, {lng:.6f}" if lat is not None and lng is not None else ""
            ),
            "coordinates_consent": (
                "manual" if lat is not None and lng is not None else ""
            ),
            "geocode_label": str(resolved_label or "").strip(),
            "geocode_source": "manual_correction",
        }
    )
    return source


def edit_context(
    *,
    question_id: str,
    step: str,
    original_step: int,
    submitted: bool,
) -> dict[str, Any]:
    return {
        "question_id": str(question_id or "").strip(),
        "step": str(step or "").strip(),
        "return_to": "review",
        "original_step": int(original_step),
        "submitted": bool(submitted),
    }


def merge_answer_fields(
    draft: Mapping[str, Any],
    edited: Mapping[str, Any],
    fields: Iterable[str],
) -> dict[str, Any]:
    merged = deepcopy(dict(draft))
    for field in fields:
        token = str(field or "").strip()
        if token:
            merged[token] = deepcopy(edited.get(token))
    return merged


def revision_payload(
    payload: Mapping[str, Any],
    *,
    question_id: str,
    field: str,
    previous_value: Any,
    revised_at: str = "",
) -> dict[str, Any]:
    revised = deepcopy(dict(payload))
    session = (
        dict(revised.get("session"))
        if isinstance(revised.get("session"), Mapping)
        else {}
    )
    session["revision"] = {
        "kind": "answer_revision",
        "question_id": str(question_id or "").strip(),
        "field": str(field or "").strip(),
        "previous_value": deepcopy(previous_value),
        "revised_at": str(revised_at or "").strip()
        or datetime.now(timezone.utc).isoformat(),
    }
    revised["session"] = session
    return revised


def credential_hint(access_key: str, stored_hint: str = "") -> str:
    existing = str(stored_hint or "").strip()
    if existing:
        return existing
    token = str(access_key or "").strip()
    if not token:
        return ""
    symbols = split_emoji_symbols(hex_to_emoji(token))
    return "".join(symbols[-4:])


def reminder_status_by_player(events: Iterable[Mapping[str, Any]]) -> dict[str, str]:
    status: dict[str, str] = {}
    items = list(events)
    if any(str(item.get("timestamp") or "").strip() for item in items):
        ordered = sorted(
            items,
            key=lambda item: str(item.get("timestamp") or ""),
            reverse=True,
        )
    else:
        ordered = list(reversed(items))
    for event in ordered:
        event_type = str(event.get("event_type") or "").strip()
        if event_type not in {"credential_email_sent", "credential_email_failed"}:
            continue
        player_id = str(event.get("player_id") or "").strip()
        if not player_id:
            metadata = event.get("metadata")
            if isinstance(metadata, Mapping):
                player_id = str(metadata.get("player_id") or "").strip()
        if player_id and player_id not in status:
            status[player_id] = (
                "sent" if event_type == "credential_email_sent" else "failed"
            )
    return status


def participant_access_rows(
    players: Iterable[Mapping[str, Any]],
    *,
    reminder_status: Mapping[str, str] | None = None,
) -> list[dict[str, Any]]:
    reminders = reminder_status or {}
    rows: list[dict[str, Any]] = []
    for player in players:
        player_id = str(player.get("id") or "").strip()
        access_key = str(player.get("access_key") or "").strip()
        nickname = str(player.get("nickname") or "").strip()
        rows.append(
            {
                "participant_id": player_id,
                "display_name": nickname or "Anonymous participant",
                "email": str(player.get("email") or "").strip(),
                "credential_hint": credential_hint(
                    access_key, str(player.get("emoji_suffix_4") or "")
                ),
                "full_credential": access_key,
                "credential_status": "available" if access_key else "unavailable",
                "consent_status": (
                    "research consent"
                    if bool(player.get("consent_research"))
                    else "no research consent"
                ),
                "email_consent": bool(player.get("email")),
                "participant_status": str(player.get("status") or "").strip()
                or "unknown",
                "last_active": str(
                    player.get("last_seen")
                    or player.get("last_joined_on")
                    or player.get("joined_at")
                    or ""
                ).strip(),
                "reminder_status": str(reminders.get(player_id) or "not sent"),
            }
        )
    return rows


def resolve_scoped_participants(
    linked_players: Iterable[Mapping[str, Any]],
    *,
    all_players: Iterable[Mapping[str, Any]],
    submissions: Iterable[Mapping[str, Any]],
) -> tuple[list[dict[str, Any]], str]:
    linked = [dict(player) for player in linked_players]
    if linked:
        return linked, "session_relation"
    allowed_hashes = {
        str(submission.get("access_key_hash") or "").strip()
        for submission in submissions
        if str(submission.get("access_key_hash") or "").strip()
    }
    if not allowed_hashes:
        return [], "none"
    recovered: list[dict[str, Any]] = []
    for player in all_players:
        access_key = str(player.get("access_key") or "").strip()
        if not access_key:
            continue
        access_key_hash = hashlib.sha256(access_key.encode("utf-8")).hexdigest()
        if access_key_hash in allowed_hashes:
            recovered.append(dict(player))
    return recovered, "submission_hash" if recovered else "unresolved"


def credential_export_rows(
    rows: Iterable[Mapping[str, Any]], *, include_full_credentials: bool = False
) -> list[dict[str, Any]]:
    exported: list[dict[str, Any]] = []
    for row in rows:
        item = {
            "participant_id": str(row.get("participant_id") or ""),
            "display_name": str(row.get("display_name") or ""),
            "email": str(row.get("email") or ""),
            "credential_hint": str(row.get("credential_hint") or ""),
            "email_consent": bool(row.get("email_consent")),
            "last_active": str(row.get("last_active") or ""),
            "reminder_status": str(row.get("reminder_status") or ""),
        }
        if include_full_credentials:
            item["full_credential"] = str(row.get("full_credential") or "")
        exported.append(item)
    return exported


def reminder_email(
    row: Mapping[str, Any],
    *,
    route_link: str,
    event_label: str,
) -> tuple[str, str]:
    name = str(row.get("display_name") or "participant").strip()
    hint = str(row.get("credential_hint") or "").strip() or "not available"
    subject = "Your WG2 coordination access details"
    body = (
        f"Hello {name},\n\n"
        f"Here is your access reminder for {event_label}:\n\n"
        f"Access key reminder: {hint}\n\n"
        f"Continue here:\n{str(route_link or '').strip()}\n\n"
        "Your key is personal. Please do not forward it.\n\n"
        "Best,\nWG2 coordination team"
    )
    return subject, body
