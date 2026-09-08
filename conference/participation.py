from __future__ import annotations

from copy import deepcopy
from datetime import datetime, timezone
import re
import uuid
from typing import Any, Mapping


EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")
PARTICIPATION_NAMESPACE = uuid.UUID("607e79d1-4d76-459b-9d58-164d98b0d866")


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def normalize_email(value: str) -> str:
    email = str(value or "").strip().lower()
    if not EMAIL_RE.match(email):
        raise ValueError(email_validation_message(value))
    return email


def email_validation_message(value: str) -> str:
    email = str(value or "").strip()
    if not email:
        return "We use your email to issue or recover access to your answers."
    if not EMAIL_RE.match(email.lower()):
        return "This email address doesn't seem complete. Can you please double-check it?"
    return ""


def participation_id_for(player_id: str, session_id: str) -> str:
    player = str(player_id or "").strip()
    session = str(session_id or "").strip()
    if not player or not session:
        raise ValueError("Participation needs player and session identity.")
    return str(uuid.uuid5(PARTICIPATION_NAMESPACE, f"{player}:{session}"))


class InMemoryParticipationRepository:
    """Reference backend for the participant/participation persistence contract."""

    def __init__(self) -> None:
        self._participants: dict[str, dict[str, Any]] = {}
        self._player_by_key: dict[str, str] = {}
        self._player_by_email: dict[str, str] = {}
        self._participations: dict[str, dict[str, Any]] = {}
        self._responses: list[dict[str, Any]] = []
        self._response_by_write_key: dict[str, dict[str, Any]] = {}

    def participants(self) -> list[dict[str, Any]]:
        return [deepcopy(item) for item in self._participants.values()]

    def create_participant(
        self,
        *,
        access_key: str,
        profile: Mapping[str, Any],
        session_ids: list[str] | None = None,
    ) -> dict[str, Any]:
        key = str(access_key or "").strip()
        if not key:
            raise ValueError("Participant needs an access key.")
        email = normalize_email(str(profile.get("email") or ""))
        if email in self._player_by_email:
            raise ValueError("A participant already uses this normalised email.")
        player_id = str(uuid.uuid4())
        participant = {
            "id": player_id,
            "access_key": key,
            "name": str(profile.get("name") or "").strip(),
            "email": email,
            "institution": str(profile.get("institution") or "").strip(),
            "base_location": deepcopy(profile.get("base_location") or ""),
            "session_ids": list(dict.fromkeys(session_ids or [])),
        }
        self._participants[player_id] = participant
        self._player_by_key[key] = player_id
        self._player_by_email[email] = player_id
        return deepcopy(participant)

    def identify_or_resolve(
        self, *, access_key: str, profile: Mapping[str, Any]
    ) -> dict[str, Any]:
        key = str(access_key or "").strip()
        email = normalize_email(str(profile.get("email") or ""))
        by_key = self._player_by_key.get(key)
        by_email = self._player_by_email.get(email)
        if by_key:
            if by_email and by_email != by_key:
                return {"status": "recovery_required", "player_id": by_email}
            return {"status": "resolved", "player_id": by_key}
        if by_email:
            return {"status": "recovery_required", "player_id": by_email}
        created = self.create_participant(access_key=key, profile=profile)
        return {"status": "created", "player_id": created["id"]}

    def get_participant(self, player_id: str) -> dict[str, Any] | None:
        item = self._participants.get(str(player_id or ""))
        return deepcopy(item) if item else None

    def ensure_participation(
        self, *, player_id: str, session_id: str, test_mode: bool = False
    ) -> dict[str, Any]:
        participant = self._participants.get(player_id)
        if not participant:
            raise ValueError("Participant does not exist.")
        if session_id not in participant["session_ids"]:
            participant["session_ids"].append(session_id)
        participation_id = participation_id_for(player_id, session_id)
        timestamp = now_iso()
        item = self._participations.setdefault(
            participation_id,
            {
                "participation_id": participation_id,
                "player_id": player_id,
                "session_id": session_id,
                "state": {},
                "current_position": "",
                "created_at": timestamp,
                "updated_at": timestamp,
                "completion_state": "not_started",
                "test_mode": bool(test_mode),
            },
        )
        return deepcopy(item)

    def checkpoint(
        self,
        participation_id: str,
        *,
        state: Mapping[str, Any],
        current_position: str,
        completion_state: str,
    ) -> dict[str, Any]:
        item = self._participations.get(participation_id)
        if not item:
            raise ValueError("Participation does not exist.")
        item.update(
            state=deepcopy(dict(state)),
            current_position=str(current_position or ""),
            completion_state=str(completion_state or "in_progress"),
            updated_at=now_iso(),
        )
        return deepcopy(item)

    def resume(self, *, player_id: str, session_id: str) -> dict[str, Any] | None:
        item = self._participations.get(participation_id_for(player_id, session_id))
        return deepcopy(item) if item else None

    def submit(
        self,
        participation_id: str,
        answers: Mapping[str, Any],
        write_idempotency_key: str,
    ) -> dict[str, Any]:
        return self._write(
            participation_id,
            answers,
            write_idempotency_key=write_idempotency_key,
            supersedes_response_id="",
        )

    def revise(
        self,
        participation_id: str,
        answers: Mapping[str, Any],
        *,
        write_idempotency_key: str,
        supersedes_response_id: str,
    ) -> dict[str, Any]:
        if not supersedes_response_id:
            raise ValueError("A revision must identify the response it supersedes.")
        return self._write(
            participation_id,
            answers,
            write_idempotency_key=write_idempotency_key,
            supersedes_response_id=supersedes_response_id,
        )

    def _write(
        self,
        participation_id: str,
        answers: Mapping[str, Any],
        *,
        write_idempotency_key: str,
        supersedes_response_id: str,
    ) -> dict[str, Any]:
        key = str(write_idempotency_key or "").strip()
        if not key:
            raise ValueError("A write idempotency key is required.")
        if key in self._response_by_write_key:
            return deepcopy(self._response_by_write_key[key])
        participation = self._participations.get(participation_id)
        if not participation:
            raise ValueError("Participation does not exist.")
        response = {
            "response_id": str(uuid.uuid4()),
            "submission_id": str(uuid.uuid4()),
            "revision_id": str(uuid.uuid4()),
            "write_idempotency_key": key,
            "supersedes_response_id": str(supersedes_response_id or ""),
            "participation_id": participation_id,
            "player_id": participation["player_id"],
            "session_id": participation["session_id"],
            "answers": deepcopy(dict(answers)),
            "test_mode": participation["test_mode"],
            "created_at": now_iso(),
        }
        self._responses.append(response)
        self._response_by_write_key[key] = response
        participation["completion_state"] = "complete"
        participation["updated_at"] = response["created_at"]
        return deepcopy(response)

    def submissions(
        self, session_id: str, *, include_test: bool = False
    ) -> list[dict[str, Any]]:
        return [
            deepcopy(item)
            for item in self._responses
            if item["session_id"] == session_id
            and (include_test or not item["test_mode"])
        ]
