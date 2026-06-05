from __future__ import annotations

import hashlib
import re
from typing import Any, Dict, List, Optional

from conference.models import SESSION_QUESTIONS
from conference.settings import ConferenceSettings
from infra.key_codec import hex_to_emoji, split_emoji_symbols
from repositories.interaction_repo import NotionInteractionRepository


QUESTION_IDENTITY = "PISA_IDENTITY_BLOCK"
QUESTION_BUNDLE = "PISA_MEETING_BUNDLE"
EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")


def emoji_suffix(access_key: str, length: int = 4) -> str:
    symbols = split_emoji_symbols(hex_to_emoji(access_key))
    if len(symbols) < length:
        return "".join(symbols)
    return "".join(symbols[-length:])


class ConferenceRepo:
    def __init__(self, notion_repo: Any, settings: ConferenceSettings) -> None:
        self.notion_repo = notion_repo
        self.client = getattr(notion_repo, "client", None)
        self.settings = settings
        self.session_responses_db_id = str(settings.session_responses_db_id or "").strip()
        self.unavailable_reason = ""
        self._interaction_repo: Optional[NotionInteractionRepository] = None
        if not self.client:
            self.unavailable_reason = "Notion client is unavailable."

    def is_ready(self) -> bool:
        if not self.client:
            return False
        if not self.session_responses_db_id:
            self.unavailable_reason = (
                "Shared interaction responses database id is missing. "
                "Set `ice_interaction_responses_db_id` in secrets."
            )
            return False
        return True

    def interaction_repo(self) -> NotionInteractionRepository:
        if self._interaction_repo is None:
            self._interaction_repo = NotionInteractionRepository(
                self.notion_repo,
                self.session_responses_db_id,
            )
        return self._interaction_repo

    def resolve_session(self, session_code: str = "") -> Optional[Dict[str, Any]]:
        if not self.notion_repo:
            return None
        if session_code:
            session = self.notion_repo.get_session_by_code(session_code)
            if session:
                return session
        default_session = self.notion_repo.get_session_by_code(self.settings.default_session_code)
        if default_session:
            return default_session
        active = getattr(self.notion_repo, "get_active_session", None)
        if callable(active):
            session = active()
            if session:
                return session
        sessions = getattr(self.notion_repo, "list_sessions", None)
        if callable(sessions):
            items = sessions(limit=50)
            return items[0] if items else None
        return None

    def upsert_conference_player(
        self,
        *,
        session_id: str,
        access_key: str,
        payload: Dict[str, Any],
    ) -> Optional[Dict[str, Any]]:
        if not self.notion_repo or not access_key:
            return None
        nickname = (
            str(payload.get("alias") or "").strip()
            or str(payload.get("identity") or "").strip()
            or f"Pisa {emoji_suffix(access_key)}"
        )
        intent = str(payload.get("open_text") or "").strip()
        contact = str(payload.get("contact") or "").strip()
        email = contact if EMAIL_RE.match(contact) else ""
        emoji_key = hex_to_emoji(access_key)
        try:
            player = self.notion_repo.upsert_player(
                session_id=session_id,
                player_id=access_key,
                nickname=nickname,
                role="None",
                consent_play=False,
                consent_research=False,
                preferred_mode=str(payload.get("mode") or "").strip() or None,
                emoji=emoji_key,
                emoji_suffix_4=emoji_suffix(access_key, length=4),
                emoji_suffix_6=emoji_suffix(access_key, length=6),
            )
        except Exception:
            return None
        try:
            updated = self.notion_repo.update_player_metadata(
                str(player.get("id") or access_key),
                nickname=nickname,
                intent=intent or None,
                email=email or None,
            )
            return updated or player
        except Exception:
            return player

    def save_session_response_set(
        self,
        session_id: str,
        player_id: Optional[str],
        text_id: str,
        device_id: str,
        access_key_hash: str,
        access_key_last4: str,
        payload: Dict[str, Any],
    ) -> None:
        repo = self.interaction_repo()
        repo.save_response(
            session_id=session_id,
            player_id=player_id,
            question_id=QUESTION_BUNDLE,
            value={
                "answer": payload,
                "question_type": "other",
                "field": "session_bundle",
                "bundle": payload,
                "mode": payload.get("mode", ""),
                "alias": payload.get("alias", ""),
                "identity": payload.get("identity", ""),
                "contact": payload.get("contact", ""),
                "optional_text": payload.get("notes", ""),
                "access_key_hash": access_key_hash,
                "access_key_last4": access_key_last4,
                "source": "conference_session",
            },
            text_id=text_id,
            device_id=device_id,
        )

    def get_session_rows(self, session_id: str) -> List[Dict[str, Any]]:
        question_ids = {str(question["question_id"]) for question in SESSION_QUESTIONS}
        question_ids.add(QUESTION_IDENTITY)
        question_ids.add(QUESTION_BUNDLE)
        rows = self.interaction_repo().get_responses(session_id)
        return [row for row in rows if str(row.get("item_id") or "") in question_ids]

    def latest_submission_by_access_key_hash(
        self,
        *,
        session_id: str,
        access_key_hash: str,
    ) -> Dict[str, Any] | None:
        rows = self.get_session_rows(session_id)
        grouped = self.group_rows_by_submission(rows)
        matches = [
            item
            for item in grouped
            if str(item.get("access_key_hash") or "").strip() == access_key_hash
        ]
        if not matches:
            return None
        matches.sort(key=lambda item: str(item.get("submitted_at") or ""), reverse=True)
        return matches[0]

    def group_rows_by_submission(self, rows: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        by_actor: Dict[str, Dict[str, Any]] = {}
        for row in sorted(rows, key=lambda item: str(item.get("submitted_at") or item.get("timestamp") or "")):
            payload = row.get("value_json")
            if not isinstance(payload, dict):
                payload = {}
            field = str(payload.get("field") or "")
            bundle_key = str(
                payload.get("access_key_hash")
                or row.get("response_id")
                or row.get("id")
                or ""
            )
            actor_key = bundle_key if field == "session_bundle" and bundle_key else str(
                row.get("player_id") or row.get("device_id") or row.get("response_id") or row.get("id") or ""
            )
            if not actor_key:
                continue
            submission = by_actor.setdefault(
                actor_key,
                {
                    "actor_key": actor_key,
                    "access_key_hash": "",
                    "access_key_last4": "",
                    "submitted_at": "",
                },
            )
            answer = payload.get("answer", row.get("response_value"))
            submission["submitted_at"] = str(
                row.get("timestamp") or row.get("created_at") or submission.get("submitted_at") or ""
            )
            if payload.get("access_key_hash"):
                submission["access_key_hash"] = str(payload.get("access_key_hash"))
            if payload.get("access_key_last4"):
                submission["access_key_last4"] = str(payload.get("access_key_last4"))
            if field == "session_bundle":
                bundle = payload.get("bundle")
                if not isinstance(bundle, dict):
                    bundle = {}
                for key, value in bundle.items():
                    submission[str(key)] = value
                submission["alias"] = str(payload.get("alias") or bundle.get("alias") or "")
                submission["identity"] = str(payload.get("identity") or bundle.get("identity") or "")
                submission["contact"] = str(payload.get("contact") or bundle.get("contact") or "")
                submission["notes"] = str(payload.get("optional_text") or bundle.get("notes") or "")
                submission["mode"] = str(payload.get("mode") or bundle.get("mode") or "")
                continue
            if field == "identity_block":
                submission["alias"] = str(payload.get("alias") or "")
                submission["identity"] = str(payload.get("identity") or "")
                submission["contact"] = str(payload.get("contact") or "")
                submission["notes"] = str(payload.get("optional_text") or "")
                submission["mode"] = str(payload.get("mode") or "")
                continue
            submission[field] = answer
        return list(by_actor.values())

    def access_key_hash(self, access_key: str) -> str:
        return hashlib.sha256(access_key.encode("utf-8")).hexdigest()
