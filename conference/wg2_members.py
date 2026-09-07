from __future__ import annotations

import base64
from datetime import datetime, timedelta, timezone
import hashlib
import hmac
import json
import re
import secrets
from typing import Any, Callable, Iterable, Mapping

from conference.question_sets import QuestionSet
from conference.wg2_schema import compare_response_bundle_to_schema
from conference.wg2_ux import host_role_allowed


WG2_SESSION_CODE = "un_wg2_core_2026"
WG2_TEXT_ID = "un_wg2_v1"
EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")


def resolve_member_route_state(
    *,
    active_player_id: str,
    player_role: str,
    candidates: Iterable[Mapping[str, Any]],
    explicitly_recovered: bool = False,
) -> tuple[str, dict[str, Any] | None]:
    """Return the member-page surface for the currently remembered player."""
    if host_role_allowed(player_role) and not explicitly_recovered:
        return "claim", None
    player_id = str(active_player_id or "").strip()
    candidate = next(
        (
            dict(item)
            for item in candidates
            if str(item.get("player_id") or "").strip() == player_id
        ),
        None,
    )
    if candidate:
        return "member", candidate
    if player_id:
        return "not_wg2_participant", None
    return "claim", None


def claim_directory_entries(
    candidates: Iterable[Mapping[str, Any]],
) -> list[dict[str, Any]]:
    """Return candidate rows displayed in the protected member directory."""
    entries: list[dict[str, Any]] = []
    for item in candidates:
        entry = dict(item)
        entry["claimable"] = bool(
            str(entry.get("identity_status") or "") == "identified"
            and str(entry.get("player_id") or "").strip()
        )
        entries.append(entry)
    return entries


def public_claiming_enabled(
    events: Iterable[Mapping[str, Any]], *, default: bool = False
) -> bool:
    """Reduce the append-only host control events to the current public state."""
    enabled = bool(default)
    ordered = sorted(events, key=lambda item: str(item.get("timestamp") or ""))
    for event in ordered:
        event_type = str(event.get("event_type") or "").strip()
        if event_type == "public_claiming_enabled":
            enabled = True
        elif event_type == "public_claiming_disabled":
            enabled = False
    return enabled


def mask_email(email: str) -> str:
    token = str(email or "").strip()
    if "@" not in token:
        return ""
    local, domain = token.split("@", 1)
    if not local or not domain:
        return ""
    return f"{local[0]}{'•' * max(2, len(local) - 1)}@{domain}"


def _value_present(value: Any) -> bool:
    if isinstance(value, Mapping):
        return any(_value_present(item) for item in value.values())
    if isinstance(value, (list, tuple, set)):
        return any(_value_present(item) for item in value)
    return bool(str(value or "").strip())


def _response_count(submission: Mapping[str, Any], schema: QuestionSet) -> int:
    profile = submission.get("profile")
    session = submission.get("session")
    profile = profile if isinstance(profile, Mapping) else submission
    session = session if isinstance(session, Mapping) else submission
    fields: list[str] = []
    for question in (*schema.questions, *schema.legacy_questions):
        field = str(question.field or "").strip()
        if field and field not in fields:
            fields.append(field)
    count = 0
    profile_fields = set(schema.profile_fields)
    for field in fields:
        source = profile if field in profile_fields else session
        value = source.get(field, submission.get(field))
        if _value_present(value):
            count += 1
    return count


def _is_wg2_submission(submission: Mapping[str, Any], session_id: str) -> bool:
    session = submission.get("session")
    session = session if isinstance(session, Mapping) else {}
    session_code = str(
        submission.get("session_code") or session.get("session_code") or ""
    ).strip()
    text_id = str(submission.get("text_id") or session.get("text_id") or "").strip()
    stored_session_id = str(
        submission.get("session_id") or session.get("session_id") or ""
    ).strip()
    if session_code != WG2_SESSION_CODE or text_id != WG2_TEXT_ID:
        return False
    return not (session_id and stored_session_id and stored_session_id != session_id)


def build_wg2_member_candidates(
    *,
    submissions: Iterable[Mapping[str, Any]],
    players: Iterable[Mapping[str, Any]],
    current_schema: QuestionSet,
    session_id: str,
) -> list[dict[str, Any]]:
    player_by_hash: dict[str, dict[str, Any]] = {}
    player_by_id: dict[str, dict[str, Any]] = {}
    for player in players:
        player_id = str(player.get("id") or "").strip()
        if player_id:
            player_by_id[player_id] = dict(player)
        access_key = str(player.get("access_key") or "").strip()
        if access_key:
            player_by_hash[hashlib.sha256(access_key.encode("utf-8")).hexdigest()] = dict(
                player
            )

    candidates_by_player: dict[str, dict[str, Any]] = {}
    for index, submission_raw in enumerate(submissions, start=1):
        submission = dict(submission_raw)
        if not _is_wg2_submission(submission, session_id):
            continue
        access_key_hash = str(submission.get("access_key_hash") or "").strip()
        related_player_id = str(submission.get("player_id") or "").strip()
        player = player_by_id.get(related_player_id) or player_by_hash.get(
            access_key_hash
        )
        if not player:
            continue
        player_id = str(player.get("id") or "").strip()
        alias = str(
            player.get("nickname")
            or submission.get("alias")
            or submission.get("identity")
            or ""
        ).strip()
        identified = bool(alias and alias not in {"🧭", "Anonymous participant"})
        email = str(player.get("email") or "").strip()
        response_id = str(
            submission.get("response_id") or submission.get("id") or ""
        ).strip()
        alignment = compare_response_bundle_to_schema(
            player_id=player_id,
            response_bundle=submission,
            previous_response_id=response_id,
            current_schema=current_schema,
        )
        candidate = {
            "player_id": player_id,
            "access_key": str(player.get("access_key") or "").strip(),
            "access_key_hash": access_key_hash,
            "display_name": (
                alias if identified else f"Anonymous participant P{index:02d}"
            ),
            "identity_status": "identified" if identified else "anonymous",
            "email": email,
            "email_mask": mask_email(email),
            "email_status": "present" if email else "absent",
            "response_count": _response_count(submission, current_schema),
            "schema": str(
                submission.get("schema_id")
                or (submission.get("session") or {}).get("schema_id")
                or submission.get("questionnaire_version")
                or "unknown"
            ),
            "last_activity": str(submission.get("submitted_at") or ""),
            "recovery_status": "recoverable" if email else "claim needed",
            "response_id": response_id,
            "submission": submission,
            "alignment": alignment,
        }
        existing = candidates_by_player.get(player_id)
        if not existing or str(candidate["last_activity"]) >= str(
            existing["last_activity"]
        ):
            candidates_by_player[player_id] = candidate
    return sorted(
        candidates_by_player.values(),
        key=lambda item: (str(item["display_name"]).lower(), str(item["player_id"])),
    )


def _validated_email(email: str) -> str:
    token = str(email or "").strip().lower()
    if not EMAIL_RE.match(token):
        raise ValueError("Enter a valid email address.")
    return token


def create_recovery_request(
    member: Mapping[str, Any],
    *,
    requested_at: str,
    request_id: str = "",
) -> dict[str, Any]:
    email = _validated_email(str(member.get("email") or ""))
    player_id = str(member.get("player_id") or "").strip()
    if not player_id:
        raise ValueError("Recovery request needs an existing player.")
    return {
        "request_id": str(request_id or secrets.token_urlsafe(12)),
        "kind": "recovery",
        "player_id": player_id,
        "display_name": str(member.get("display_name") or "Participant"),
        "email_mask": mask_email(email),
        "requested_at": str(requested_at or ""),
        "status": "pending",
    }


def create_identity_claim(
    *,
    player_id: str,
    proposed_email: str,
    requested_at: str,
    claim_id: str = "",
) -> dict[str, Any]:
    token = str(player_id or "").strip()
    if not token:
        raise ValueError("Identity claim needs an existing player.")
    email = _validated_email(proposed_email)
    return {
        "claim_id": str(claim_id or secrets.token_urlsafe(12)),
        "kind": "identity_claim",
        "player_id": token,
        "proposed_email": email,
        "email_mask": mask_email(email),
        "requested_at": str(requested_at or ""),
        "status": "pending",
    }


def reduce_recovery_events(
    events: Iterable[Mapping[str, Any]],
) -> dict[str, dict[str, Any]]:
    states: dict[str, dict[str, Any]] = {}
    ordered = sorted(events, key=lambda item: str(item.get("timestamp") or ""))
    for event in ordered:
        event_type = str(event.get("event_type") or "").strip()
        metadata = event.get("metadata")
        if not isinstance(metadata, Mapping):
            continue
        item_id = str(metadata.get("claim_id") or metadata.get("request_id") or "").strip()
        if not item_id:
            continue
        if event_type in {"identity_claim_requested", "recovery_reminder_requested"}:
            states[item_id] = {**dict(metadata), "status": "pending"}
        elif item_id in states:
            state = states[item_id]
            if event_type == "identity_claim_approved":
                state["status"] = "approved"
            elif event_type == "identity_claim_rejected":
                state["status"] = "rejected"
            elif event_type == "recovery_link_issued":
                state["status"] = "ready_to_send"
                state.update(dict(metadata))
            elif event_type == "recovery_link_sent":
                state["status"] = "sent"
            elif event_type == "recovery_link_redeemed":
                state["status"] = "redeemed"
            elif event_type == "recovery_workflow_revoked":
                state["status"] = "revoked"
    return states


def approve_identity_claim(repo: Any, claim: Mapping[str, Any]) -> dict[str, Any]:
    if str(claim.get("status") or "pending") not in {"pending", "approved"}:
        raise ValueError("Only a pending identity claim can be approved.")
    player_id = str(claim.get("player_id") or "").strip()
    player = repo.get_player_by_id(player_id)
    if not player:
        raise ValueError("The existing player could not be resolved.")
    proposed_email = _validated_email(str(claim.get("proposed_email") or ""))
    updated = repo.update_player_metadata(
        player_id,
        email=proposed_email,
    )
    if not updated:
        raise RuntimeError("The existing player could not be updated.")
    if str(updated.get("email") or "").strip().lower() != proposed_email:
        raise RuntimeError(
            "The player repository did not persist the recovery email; check the email schema."
        )
    return dict(updated)


def approve_identity_claim_with_audit(
    repo: Any,
    claim: Mapping[str, Any],
    record_approval: Callable[[], bool],
) -> dict[str, Any]:
    """Approve a claim only when its durable audit event can also be recorded.

    Notion does not provide a transaction across the players and events data
    sources. If the append-only approval event fails, restore the prior email so
    the participant record cannot silently enter an unaudited approved state.
    """
    player_id = str(claim.get("player_id") or "").strip()
    original = repo.get_player_by_id(player_id)
    if not original:
        raise ValueError("The existing player could not be resolved.")
    previous_email = str(original.get("email") or "").strip()
    updated = approve_identity_claim(repo, claim)
    if record_approval():
        return updated
    restored = repo.update_player_metadata(player_id, email=previous_email)
    if not restored or str(restored.get("email") or "").strip() != previous_email:
        raise RuntimeError(
            "Approval could not be audited and the previous email could not be restored. "
            "Do not issue a recovery link until an operator reconciles this participant."
        )
    raise RuntimeError(
        "Approval could not be recorded; the email change was rolled back."
    )


def _b64encode(value: bytes) -> str:
    return base64.urlsafe_b64encode(value).decode("ascii").rstrip("=")


def _b64decode(value: str) -> bytes:
    return base64.urlsafe_b64decode(value + "=" * (-len(value) % 4))


def issue_recovery_token(
    *,
    player_id: str,
    session_id: str,
    secret: str,
    issued_at: datetime | None = None,
    ttl_seconds: int = 3600,
    nonce: str = "",
) -> str:
    if not str(secret or ""):
        raise ValueError("Recovery signing secret is unavailable.")
    issued = issued_at or datetime.now(timezone.utc)
    if issued.tzinfo is None:
        issued = issued.replace(tzinfo=timezone.utc)
    payload = {
        "player_id": str(player_id or "").strip(),
        "session_id": str(session_id or "").strip(),
        "iat": int(issued.timestamp()),
        "exp": int((issued + timedelta(seconds=int(ttl_seconds))).timestamp()),
        "nonce": str(nonce or secrets.token_urlsafe(12)),
    }
    if not payload["player_id"] or not payload["session_id"]:
        raise ValueError("Recovery token needs player and session identity.")
    encoded = _b64encode(
        json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")
    )
    signature = _b64encode(
        hmac.new(str(secret).encode("utf-8"), encoded.encode("ascii"), hashlib.sha256).digest()
    )
    return f"{encoded}.{signature}"


def verify_recovery_token(
    token: str,
    *,
    secret: str,
    expected_session_id: str,
    now: datetime | None = None,
) -> dict[str, Any]:
    if not str(secret or ""):
        raise ValueError("Recovery signing secret is unavailable.")
    try:
        encoded, signature = str(token or "").split(".", 1)
    except ValueError as exc:
        raise ValueError("Recovery token signature is invalid.") from exc
    expected = _b64encode(
        hmac.new(str(secret).encode("utf-8"), encoded.encode("ascii"), hashlib.sha256).digest()
    )
    if not hmac.compare_digest(signature, expected):
        raise ValueError("Recovery token signature is invalid.")
    try:
        payload = json.loads(_b64decode(encoded).decode("utf-8"))
    except Exception as exc:
        raise ValueError("Recovery token payload is invalid.") from exc
    if str(payload.get("session_id") or "") != str(expected_session_id or ""):
        raise ValueError("Recovery token belongs to another session.")
    current = now or datetime.now(timezone.utc)
    if current.tzinfo is None:
        current = current.replace(tzinfo=timezone.utc)
    if int(current.timestamp()) > int(payload.get("exp") or 0):
        raise ValueError("Recovery token has expired.")
    return dict(payload)


def recovery_token_fingerprint(token: str) -> str:
    return hashlib.sha256(str(token or "").encode("utf-8")).hexdigest()


def recovery_token_state(
    events: Iterable[Mapping[str, Any]], token: str
) -> str:
    fingerprint = recovery_token_fingerprint(token)
    issued = False
    redeemed = False
    for event in events:
        metadata = event.get("metadata")
        if not isinstance(metadata, Mapping):
            continue
        if str(metadata.get("token_hash") or "") != fingerprint:
            continue
        event_type = str(event.get("event_type") or "")
        issued = issued or event_type == "recovery_link_issued"
        redeemed = redeemed or event_type == "recovery_link_redeemed"
    if redeemed:
        return "redeemed"
    if issued:
        return "issued"
    return "unknown"


def recovery_message(display_name: str, recovery_url: str) -> tuple[str, str]:
    subject = "Your WG2 trajectory recovery link"
    body = (
        f"Hello {str(display_name or 'participant').strip()},\n\n"
        "Use this one-time link to reconnect to your existing WG2 trajectory:\n\n"
        f"{str(recovery_url or '').strip()}\n\n"
        "The link expires in one hour. It does not contain your access key.\n\n"
        "Best,\nWG2 coordination team"
    )
    return subject, body
