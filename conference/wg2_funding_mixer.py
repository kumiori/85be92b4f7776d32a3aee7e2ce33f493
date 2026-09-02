from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
import json
from statistics import median
from typing import Any, Iterable, Mapping, Sequence


LOGGER_NAME = "iceicebaby.wg2_funding_mixer"
DEFAULT_SESSION_CODE = "wg2-meeting-3"
INTERACTION_ID = "seed_funding_allocation"
TEXT_ID = "wg2_funding_mixer_v1"
TOTAL_TOKENS = 100


@dataclass(frozen=True)
class FundingChannel:
    key: str
    label: str
    description: str


CHANNELS: tuple[FundingChannel, ...] = (
    FundingChannel(
        "people", "People", "Protected time, fellows, coordination and scientific staff."
    ),
    FundingChannel(
        "knowledge",
        "Knowledge production",
        "Modelling, synthesis, data, computation and validation.",
    ),
    FundingChannel(
        "interaction",
        "Interaction & participation",
        "Workshops, travel, co-design, translation and stakeholder engagement.",
    ),
    FundingChannel(
        "infrastructure",
        "Infrastructure & tools",
        "Digital platforms, data infrastructure, visualisation and maintenance.",
    ),
    FundingChannel(
        "deployment",
        "Deployment & use cases",
        "Pilots, training, decision support and real-world application.",
    ),
    FundingChannel(
        "contingency",
        "Contingency / opportunity",
        "Capacity to react to emerging needs or opportunities.",
    ),
    FundingChannel(
        "other", "Other", "Anything important not represented above."
    ),
)
CHANNEL_KEYS = tuple(channel.key for channel in CHANNELS)


def default_allocation() -> dict[str, int]:
    return {key: 0 for key in CHANNEL_KEYS}


def normalize_partial_allocation(allocation: Mapping[str, Any]) -> dict[str, int]:
    if set(allocation) != set(CHANNEL_KEYS):
        raise ValueError("Allocation must contain exactly the seven funding channels.")
    normalized: dict[str, int] = {}
    for key in CHANNEL_KEYS:
        value = allocation[key]
        if isinstance(value, bool) or not isinstance(value, (int, float)):
            raise ValueError(f"Allocation for {key} must be a number.")
        if int(value) != value or not 0 <= int(value) <= TOTAL_TOKENS:
            raise ValueError(f"Allocation for {key} must be a whole number from 0 to 100.")
        normalized[key] = int(value)
    return normalized


def validate_allocation(allocation: Mapping[str, Any]) -> dict[str, int]:
    normalized = normalize_partial_allocation(allocation)
    if sum(normalized.values()) != TOTAL_TOKENS:
        raise ValueError("Allocation must total exactly 100 tokens.")
    return normalized


def constrain_allocation(
    allocation: Mapping[str, Any], changed_key: str, requested_value: int
) -> dict[str, int]:
    """Accept partial budgets; proportionally contract peers only above 100."""
    current = normalize_partial_allocation(allocation)
    if changed_key not in CHANNEL_KEYS:
        raise ValueError(f"Unknown funding channel: {changed_key}")
    target = max(0, min(TOTAL_TOKENS, int(requested_value)))
    candidate = dict(current)
    candidate[changed_key] = target
    overflow = sum(candidate.values()) - TOTAL_TOKENS
    if overflow <= 0:
        return candidate

    other_keys = [key for key in CHANNEL_KEYS if key != changed_key]
    other_total = sum(candidate[key] for key in other_keys)
    if other_total < overflow:
        target -= overflow - other_total
        overflow = other_total
    if other_total == 0:
        return candidate | {changed_key: min(target, TOTAL_TOKENS)}
    retained_total = other_total - overflow
    exact = {
        key: candidate[key] * retained_total / other_total for key in other_keys
    }
    floors = {key: int(exact[key]) for key in other_keys}
    leftover = retained_total - sum(floors.values())
    priority = sorted(
        other_keys,
        key=lambda key: (exact[key] - floors[key], -CHANNEL_KEYS.index(key)),
        reverse=True,
    )
    for key in priority[:leftover]:
        floors[key] += 1
    return {key: target if key == changed_key else floors[key] for key in CHANNEL_KEYS}


def rebalance_allocation(
    allocation: Mapping[str, Any], changed_key: str, requested_value: int
) -> dict[str, int]:
    """Move one channel while contracting/expanding the others proportionally."""
    current = validate_allocation(allocation)
    if changed_key not in CHANNEL_KEYS:
        raise ValueError(f"Unknown funding channel: {changed_key}")
    target = max(0, min(TOTAL_TOKENS, int(requested_value)))
    other_keys = [key for key in CHANNEL_KEYS if key != changed_key]
    remaining = TOTAL_TOKENS - target
    other_total = sum(current[key] for key in other_keys)

    if other_total == 0:
        exact = {key: remaining / len(other_keys) for key in other_keys}
    else:
        exact = {
            key: (current[key] * remaining / other_total) for key in other_keys
        }
    floors = {key: int(exact[key]) for key in other_keys}
    leftover = remaining - sum(floors.values())
    priority = sorted(
        other_keys,
        key=lambda key: (exact[key] - floors[key], -CHANNEL_KEYS.index(key)),
        reverse=True,
    )
    for key in priority[:leftover]:
        floors[key] += 1
    return {key: target if key == changed_key else floors[key] for key in CHANNEL_KEYS}


def allocation_payload(
    allocation: Mapping[str, Any],
    *,
    session_code: str,
    revision: int,
    participant_hash: str,
    other_text: str = "",
    phase: str = "before_discussion",
    submitted_at: str = "",
) -> dict[str, Any]:
    normalized = validate_allocation(allocation)
    if not str(session_code or "").strip():
        raise ValueError("A session code is required.")
    if revision < 1:
        raise ValueError("Revision must be at least 1.")
    payload = {
        "answer": normalized,
        "question_type": "other",
        "field": INTERACTION_ID,
        "interaction": INTERACTION_ID,
        "session_code": str(session_code).strip(),
        "text_id": TEXT_ID,
        "response_scope": "event_session",
        "participant_hash": str(participant_hash or "").strip(),
        "phase": str(phase or "before_discussion").strip(),
        "revision": int(revision),
        "submitted_at": submitted_at or datetime.now(timezone.utc).isoformat(),
        "total": TOTAL_TOKENS,
    }
    if normalized["other"] > 0:
        payload["other_text"] = str(other_text or "").strip()
    return payload


def backup_document(payload: Mapping[str, Any]) -> dict[str, Any]:
    """Return a portable participant backup without identity-linking fields."""
    answer = payload.get("answer")
    allocation = validate_allocation(answer if isinstance(answer, Mapping) else {})
    document: dict[str, Any] = {
        "schema": "wg2-funding-mix-backup/v1",
        "interaction": INTERACTION_ID,
        "session_code": str(payload.get("session_code") or "").strip(),
        "text_id": TEXT_ID,
        "revision": int(payload.get("revision") or 0),
        "phase": str(payload.get("phase") or "before_discussion").strip(),
        "submitted_at": str(payload.get("submitted_at") or "").strip(),
        "total": sum(allocation.values()),
        "allocation": allocation,
    }
    other_text = str(payload.get("other_text") or "").strip()
    if allocation["other"] > 0 and other_text:
        document["other_text"] = other_text
    return document


def backup_json(payload: Mapping[str, Any]) -> str:
    return json.dumps(backup_document(payload), ensure_ascii=False, indent=2) + "\n"


def mixer_rows(rows: Iterable[Mapping[str, Any]]) -> list[dict[str, Any]]:
    filtered: list[dict[str, Any]] = []
    for row in rows:
        value = row.get("value_json")
        if not isinstance(value, dict) or value.get("interaction") != INTERACTION_ID:
            continue
        answer = value.get("answer")
        try:
            allocation = validate_allocation(answer if isinstance(answer, dict) else {})
        except ValueError:
            continue
        filtered.append(dict(row) | {"mixer": value, "allocation": allocation})
    return filtered


def latest_participant_rows(rows: Iterable[Mapping[str, Any]]) -> list[dict[str, Any]]:
    latest: dict[str, dict[str, Any]] = {}
    for row in mixer_rows(rows):
        payload = row["mixer"]
        actor = str(
            payload.get("participant_hash")
            or row.get("player_id")
            or row.get("device_id")
            or row.get("response_id")
            or ""
        )
        if not actor:
            continue
        candidate_key = (
            int(payload.get("revision") or 0),
            str(payload.get("submitted_at") or row.get("timestamp") or ""),
        )
        existing = latest.get(actor)
        existing_payload = existing.get("mixer", {}) if existing else {}
        existing_key = (
            int(existing_payload.get("revision") or 0),
            str(existing_payload.get("submitted_at") or existing.get("timestamp") or "")
            if existing
            else "",
        )
        if existing is None or candidate_key > existing_key:
            latest[actor] = row
    return list(latest.values())


def aggregate_allocations(rows: Sequence[Mapping[str, Any]]) -> dict[str, Any]:
    valid_rows = mixer_rows(rows)
    latest = latest_participant_rows(valid_rows)
    traces = [row["allocation"] for row in latest]
    channels: dict[str, dict[str, float]] = {}
    for key in CHANNEL_KEYS:
        values = [allocation[key] for allocation in traces]
        channels[key] = {
            "median": float(median(values)) if values else 0.0,
            "min": float(min(values)) if values else 0.0,
            "max": float(max(values)) if values else 0.0,
        }
    return {
        "submission_count": len(traces),
        "revision_count": len(valid_rows),
        "channels": channels,
        "traces": traces,
    }
