from __future__ import annotations

import hashlib
import re
import unicodedata
from typing import Any, Dict, List, Optional, Sequence

from conference.models import SESSION_QUESTIONS
from conference.question_flags import normalize_question_flags
from conference.settings import ConferenceSettings
from infra.key_codec import hex_to_emoji, normalize_access_key, split_emoji_symbols
from infra.event_logger import get_module_logger, log_event
from repositories.interaction_repo import NotionInteractionRepository


QUESTION_IDENTITY = "PISA_IDENTITY_BLOCK"
LEGACY_QUESTION_BUNDLE = "PISA_MEETING_BUNDLE"
COMPLEXITY_QUESTION_BUNDLE = "COMPLEXITY_BUNDLE"
DALEMBERTIENNES_QUESTION_BUNDLE = "DALEMBERTIENNES_BUNDLE"
LEGACY_DALAMBERTIENNES_QUESTION_BUNDLE = "DALAMBERTIENNES_BUNDLE"
QUESTION_BUNDLE_IDS = {
    LEGACY_QUESTION_BUNDLE,
    COMPLEXITY_QUESTION_BUNDLE,
    DALEMBERTIENNES_QUESTION_BUNDLE,
    LEGACY_DALAMBERTIENNES_QUESTION_BUNDLE,
}
ANONYMOUS_COMPLEXITY_NAME = "🌀"
ANONYMOUS_DALEMBERTIENNES_NAME = "📐"
EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")
VARIATION_SELECTORS = {0xFE0E, 0xFE0F}
ZWJ_CODEPOINT = 0x200D
KEYCAP_CODEPOINT = 0x20E3
REGIONAL_INDICATOR_MIN = 0x1F1E6
REGIONAL_INDICATOR_MAX = 0x1F1FF
SKIN_TONE_MIN = 0x1F3FB
SKIN_TONE_MAX = 0x1F3FF
CONFERENCE_LOGGER = get_module_logger("iceicebaby.conference")


def _as_list(value: Any) -> list[str]:
    if isinstance(value, list):
        return [str(item).strip() for item in value if str(item).strip()]
    if isinstance(value, tuple):
        return [str(item).strip() for item in value if str(item).strip()]
    text = str(value or "").strip()
    return [text] if text else []


def _as_text(value: Any) -> str:
    return str(value or "").strip()


def _as_fingerprint(value: Any) -> Dict[str, int]:
    source = value if isinstance(value, dict) else {}
    out: Dict[str, int] = {}
    for axis in ["theory", "data", "experiments", "mechanisms"]:
        raw = source.get(axis, 0)
        try:
            level = int(raw)
        except Exception:
            level = 0
        out[axis] = max(0, min(5, level))
    return out


def _is_regional_indicator(char: str) -> bool:
    codepoint = ord(char)
    return REGIONAL_INDICATOR_MIN <= codepoint <= REGIONAL_INDICATOR_MAX


def _is_modifier(char: str) -> bool:
    codepoint = ord(char)
    return (
        codepoint in VARIATION_SELECTORS
        or codepoint == KEYCAP_CODEPOINT
        or codepoint == ZWJ_CODEPOINT
        or SKIN_TONE_MIN <= codepoint <= SKIN_TONE_MAX
        or unicodedata.combining(char) > 0
    )


def _split_lookup_symbols(raw: str) -> list[str]:
    token = str(raw or "").strip()
    if not token:
        return []
    known = split_emoji_symbols(token)
    if known:
        return known

    symbols: list[str] = []
    idx = 0
    while idx < len(token):
        current = token[idx]
        cluster = current
        idx += 1

        if _is_regional_indicator(current) and idx < len(token) and _is_regional_indicator(token[idx]):
            cluster += token[idx]
            idx += 1
            symbols.append(cluster)
            continue

        while idx < len(token):
            next_char = token[idx]
            cluster += next_char
            idx += 1

            if ord(next_char) == ZWJ_CODEPOINT and idx < len(token):
                cluster += token[idx]
                idx += 1
                continue

            if _is_modifier(next_char):
                continue

            cluster = cluster[:-1]
            idx -= 1
            break

        symbols.append(cluster)
    return [symbol for symbol in symbols if symbol]


def resolve_access_key_input(
    notion_repo: Any,
    raw_key: str,
) -> tuple[str | None, str | None]:
    token = str(raw_key or "").strip()
    if not token:
        return None, ""
    try:
        return normalize_access_key(token), None
    except ValueError:
        pass

    symbols = _split_lookup_symbols(token)
    if not symbols:
        return None, "Access key format not recognized."
    if len(symbols) < 4:
        return None, "Add at least 4 emoji symbols to continue."

    finder = getattr(notion_repo, "find_players_by_emoji_suffix", None)
    if not callable(finder):
        return None, "Emoji suffix lookup is unavailable right now."

    suffix4 = "".join(symbols[-4:])
    matches = finder(suffix4, length=4)
    if len(matches) == 1:
        access_key = str(matches[0].get("access_key") or "").strip()
        if access_key:
            return access_key, None
        return None, "Stored access key is incomplete."
    if len(matches) > 1 and len(symbols) < 6:
        return None, "Multiple matches. Add two more emoji symbols."

    if len(symbols) >= 6:
        suffix6 = "".join(symbols[-6:])
        matches = finder(suffix6, length=6)
        if len(matches) == 1:
            access_key = str(matches[0].get("access_key") or "").strip()
            if access_key:
                return access_key, None
            return None, "Stored access key is incomplete."
        if len(matches) > 1:
            return None, "This access key is still ambiguous. Paste the full key."

    return None, "No participant was found for this access key."


def _normalize_bundle(bundle: Dict[str, Any]) -> Dict[str, Any]:
    profile = bundle.get("profile") if isinstance(bundle.get("profile"), dict) else {}
    session = bundle.get("session") if isinstance(bundle.get("session"), dict) else {}
    derived = bundle.get("derived") if isinstance(bundle.get("derived"), dict) else {}
    scientific_home = (
        profile.get("scientific_home")
        if isinstance(profile.get("scientific_home"), dict)
        else {}
    )

    role = _as_list(profile.get("role", bundle.get("role", [])))
    role_custom = _as_text(profile.get("role_custom", bundle.get("role_custom", "")))
    if role_custom and role_custom not in role:
        role.append(role_custom)
    career_stage = _as_text(profile.get("career_stage", bundle.get("career_stage", "")))
    country = _as_text(scientific_home.get("country", bundle.get("scientific_home_country", "")))
    city = _as_text(scientific_home.get("city", bundle.get("scientific_home_city", "")))
    institution = _as_text(
        scientific_home.get("institution", bundle.get("scientific_home_institution", ""))
    )
    scale = _as_text(profile.get("computational_scale", bundle.get("scale", "")))
    collaboration_style = _as_text(
        profile.get("collaboration_style", bundle.get("collaboration_style", ""))
    )
    assets = _as_list(profile.get("assets", bundle.get("assets", [])))
    fingerprint = _as_fingerprint(
        profile.get("complexity_fingerprint", bundle.get("complexity_fingerprint", {}))
    )
    motivations = _as_list(session.get("motivations", bundle.get("motivations", [])))
    obstacle = _as_list(session.get("obstacle", bundle.get("obstacle", [])))
    challenge = _as_text(session.get("challenge", bundle.get("challenge", "")))
    follow_up_interest = _as_text(
        session.get(
            "follow_up_interest",
            bundle.get("follow_up_interest", bundle.get("continue_conversation", "")),
        )
    )
    open_question = _as_text(session.get("open_question", bundle.get("open_question", bundle.get("open_text", ""))))
    boiler_room_contribution = _as_text(
        session.get(
            "boiler_room_contribution",
            bundle.get("boiler_room_contribution", bundle.get("notes", "")),
        )
    )
    question_flags = normalize_question_flags(
        session.get("question_flags", bundle.get("question_flags", {}))
    )
    deferred_fields = _as_list(session.get("deferred_fields", bundle.get("deferred_fields", [])))
    identity_reveal_targets = _as_list(
        session.get("identity_reveal_targets", bundle.get("identity_reveal_targets", []))
    )
    event_slug = _as_text(session.get("event_slug", bundle.get("event_slug", "")))
    event_code = _as_text(session.get("event_code", bundle.get("event_code", "")))
    event_label = _as_text(session.get("event_label", bundle.get("event_label", "")))
    event_location = _as_text(
        session.get("event_location", bundle.get("event_location", ""))
    )
    event_status = _as_text(session.get("event_status", bundle.get("event_status", "")))
    session_code = _as_text(session.get("session_code", bundle.get("session_code", "")))
    session_id = _as_text(session.get("session_id", bundle.get("session_id", "")))
    text_id = _as_text(session.get("text_id", bundle.get("text_id", "")))
    schema_id = _as_text(session.get("schema_id", bundle.get("schema_id", "")))
    question_set_id = _as_text(
        session.get("question_set_id", bundle.get("question_set_id", ""))
    )
    response_scope = _as_text(
        session.get("response_scope", bundle.get("response_scope", ""))
    )
    persistence_scope = _as_text(
        profile.get("persistence_scope", bundle.get("persistence_scope", ""))
    )

    return {
        "schema_version": _as_text(bundle.get("schema_version")) or "1",
        "mode": _as_text(session.get("depth", bundle.get("mode", ""))),
        "profile": {
            "role": role,
            "career_stage": career_stage,
            "scientific_home": {
                "country": country,
                "city": city,
                "institution": institution,
            },
            "computational_scale": scale,
            "collaboration_style": collaboration_style,
            "assets": assets,
            "complexity_fingerprint": fingerprint,
        },
        "session": {
            "depth": _as_text(session.get("depth", bundle.get("mode", ""))),
            "motivations": motivations,
            "obstacle": obstacle,
            "challenge": challenge,
            "follow_up_interest": follow_up_interest,
            "open_question": open_question,
            "boiler_room_contribution": boiler_room_contribution,
            "question_flags": question_flags,
            "deferred_fields": deferred_fields,
            "identity_reveal_targets": identity_reveal_targets,
            "event_slug": event_slug,
            "event_code": event_code,
            "event_label": event_label,
            "event_location": event_location,
            "event_status": event_status,
            "session_code": session_code,
            "session_id": session_id,
            "text_id": text_id,
            "schema_id": schema_id,
            "question_set_id": question_set_id,
            "response_scope": response_scope,
        },
        "derived": derived,
        "role": role,
        "role_custom": role_custom,
        "career_stage": career_stage,
        "scientific_home_country": country,
        "scientific_home_city": city,
        "scientific_home_institution": institution,
        "scale": scale,
        "collaboration_style": collaboration_style,
        "assets": assets,
        "complexity_fingerprint": fingerprint,
        "motivations": motivations,
        "obstacle": obstacle,
        "challenge": challenge,
        "follow_up_interest": follow_up_interest,
        "continue_conversation": follow_up_interest,
        "open_question": open_question,
        "boiler_room_contribution": boiler_room_contribution,
        "question_flags": question_flags,
        "open_text": open_question,
        "deferred_fields": deferred_fields,
        "identity_reveal_targets": identity_reveal_targets,
        "event_slug": event_slug,
        "event_code": event_code,
        "event_label": event_label,
        "event_location": event_location,
        "event_status": event_status,
        "session_code": session_code,
        "session_id": session_id,
        "text_id": text_id,
        "schema_id": schema_id,
        "question_set_id": question_set_id,
        "response_scope": response_scope,
        "persistence_scope": persistence_scope,
    }


def _compact_bundle(payload: Dict[str, Any]) -> Dict[str, Any]:
    if not isinstance(payload.get("profile"), dict) and not isinstance(payload.get("session"), dict):
        return payload
    profile = payload.get("profile") if isinstance(payload.get("profile"), dict) else {}
    session = payload.get("session") if isinstance(payload.get("session"), dict) else {}
    return {
        "schema_version": str(payload.get("schema_version") or "2"),
        "profile": profile,
        "session": session,
    }


def _session_bundle_value(bundle: Dict[str, Any], key: str) -> str:
    session = bundle.get("session") if isinstance(bundle.get("session"), dict) else {}
    return _as_text(session.get(key, bundle.get(key, "")))


def _bundle_id_for_text_id(text_id: str) -> str:
    token = str(text_id or "").strip()
    mapping = {
        "pisa_session_v2": LEGACY_QUESTION_BUNDLE,
        "petnica_2026": COMPLEXITY_QUESTION_BUNDLE,
        "complexity_session_v2": COMPLEXITY_QUESTION_BUNDLE,
        "dalembertiennes_v0": DALEMBERTIENNES_QUESTION_BUNDLE,
    }
    bundle_id = mapping.get(token)
    if bundle_id:
        return bundle_id
    raise ValueError(f"Unknown questionnaire text_id: {token!r}")


def _anonymous_name_for_bundle(bundle: Dict[str, Any]) -> str:
    event_slug = _session_bundle_value(bundle, "event_slug").lower()
    session_code = _session_bundle_value(bundle, "session_code").lower()
    text_id = _session_bundle_value(bundle, "text_id").lower()
    if (
        event_slug == "dalembertiennes"
        or session_code == "dalembertiennes_2026"
        or text_id == "dalembertiennes_v0"
    ):
        return ANONYMOUS_DALEMBERTIENNES_NAME
    return ANONYMOUS_COMPLEXITY_NAME


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

    def resolve_session(self, session_code: str = "", prefer_active: bool = False) -> Optional[Dict[str, Any]]:
        if not self.notion_repo:
            return None
        if session_code:
            session = self.notion_repo.get_session_by_code(session_code)
            return session
        if prefer_active:
            active = getattr(self.notion_repo, "get_active_session", None)
            if callable(active):
                session = active()
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
        identity_metadata: Optional[Dict[str, Any]] = None,
    ) -> Optional[Dict[str, Any]]:
        if not self.notion_repo or not access_key:
            return None
        normalized = _normalize_bundle(payload)
        identity = identity_metadata or {}
        nickname = (
            str(identity.get("alias") or "").strip()
            or str(identity.get("identity") or "").strip()
            or _anonymous_name_for_bundle(normalized)
        )
        intent = str(normalized.get("open_question") or normalized.get("open_text") or "").strip()
        contact = str(identity.get("contact") or "").strip()
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
                preferred_mode=str(normalized.get("mode") or "").strip() or None,
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
        identity_metadata: Optional[Dict[str, Any]] = None,
    ) -> None:
        repo = self.interaction_repo()
        compact_bundle = _compact_bundle(payload)
        normalized = _normalize_bundle(compact_bundle)
        identity = identity_metadata or {}
        event_slug = _session_bundle_value(normalized, "event_slug")
        session_code = _session_bundle_value(normalized, "session_code")
        payload_text_id = _session_bundle_value(normalized, "text_id")
        outer_text_id = str(text_id or "").strip()
        canonical_text_id = payload_text_id or outer_text_id
        question_set_id = _session_bundle_value(normalized, "question_set_id")
        response_scope = _session_bundle_value(normalized, "response_scope")
        event_status = _session_bundle_value(normalized, "event_status")

        failure_reasons: list[str] = []
        if not str(session_id or "").strip():
            failure_reasons.append("missing_session_id")
        if not canonical_text_id:
            failure_reasons.append("missing_canonical_text_id")
        if outer_text_id and payload_text_id and outer_text_id != payload_text_id:
            failure_reasons.append(
                f"text_id_mismatch_outer_{outer_text_id}_payload_{payload_text_id}"
            )
        if not session_code:
            failure_reasons.append("missing_session_code")
        if not event_slug:
            failure_reasons.append("missing_event_slug")
        if not question_set_id:
            failure_reasons.append("missing_question_set_id")
        if not response_scope:
            failure_reasons.append("missing_response_scope")
        if event_status.lower() in {"closed", "archived"}:
            failure_reasons.append(f"event_{event_status.lower()}")
        if canonical_text_id == "dalembertiennes_v0":
            if event_slug != "dalembertiennes":
                failure_reasons.append("dalembertiennes_wrong_event_slug")
            if session_code != "dalembertiennes_2026":
                failure_reasons.append("dalembertiennes_wrong_session_code")
            if question_set_id not in {"dalembertiennes_v0", "dalembertiennes_lab_questionnaire_v0"}:
                failure_reasons.append("dalembertiennes_wrong_question_set_id")

        if failure_reasons:
            metadata = {
                "reasons": failure_reasons,
                "session_code": session_code,
                "event_slug": event_slug,
                "text_id": canonical_text_id,
                "outer_text_id": outer_text_id,
                "payload_text_id": payload_text_id,
                "question_set_id": question_set_id,
                "response_scope": response_scope,
            }
            CONFERENCE_LOGGER.error("conference response write rejected %s", metadata)
            log_event(
                module="iceicebaby.conference",
                event_type="conference_response_write_failed",
                page="conference",
                player_id=str(player_id or ""),
                session_id=str(session_id or ""),
                item_id=canonical_text_id,
                status="error",
                device_id=str(device_id or ""),
                metadata=metadata,
                level="ERROR",
            )
            raise ValueError(
                "Conference response write rejected: " + ", ".join(failure_reasons)
            )

        try:
            bundle_id = _bundle_id_for_text_id(canonical_text_id)
        except ValueError as exc:
            metadata = {
                "reason": "unknown_text_id",
                "error": str(exc),
                "session_code": session_code,
                "event_slug": event_slug,
                "text_id": canonical_text_id,
                "outer_text_id": outer_text_id,
                "payload_text_id": payload_text_id,
                "question_set_id": question_set_id,
                "response_scope": response_scope,
            }
            CONFERENCE_LOGGER.error("conference response write rejected %s", metadata)
            log_event(
                module="iceicebaby.conference",
                event_type="conference_response_write_failed",
                page="conference",
                player_id=str(player_id or ""),
                session_id=str(session_id or ""),
                item_id=canonical_text_id,
                status="error",
                device_id=str(device_id or ""),
                metadata=metadata,
                level="ERROR",
            )
            raise
        try:
            repo.save_response(
                session_id=session_id,
                player_id=player_id,
                question_id=bundle_id,
                value={
                    "answer": compact_bundle,
                    "question_type": "other",
                    "field": "session_bundle",
                    "bundle": compact_bundle,
                    "mode": normalized.get("mode", ""),
                    "alias": identity.get("alias", ""),
                    "identity": identity.get("identity", ""),
                    "contact": identity.get("contact", ""),
                    "optional_text": "",
                    "access_key_hash": access_key_hash,
                    "access_key_last4": access_key_last4,
                    "source": "conference_session",
                },
                text_id=canonical_text_id,
                device_id=device_id,
            )
        except Exception as exc:
            metadata = {
                "reason": "notion_write_failed",
                "error": str(exc),
                "session_code": session_code,
                "event_slug": event_slug,
                "text_id": canonical_text_id,
                "outer_text_id": outer_text_id,
                "payload_text_id": payload_text_id,
                "question_set_id": question_set_id,
            }
            CONFERENCE_LOGGER.error("conference response write failed %s", metadata)
            log_event(
                module="iceicebaby.conference",
                event_type="conference_response_write_failed",
                page="conference",
                player_id=str(player_id or ""),
                session_id=str(session_id or ""),
                item_id=canonical_text_id,
                status="error",
                device_id=str(device_id or ""),
                metadata=metadata,
                level="ERROR",
            )
            raise

        log_event(
            module="iceicebaby.conference",
            event_type="conference_response_written",
            page="conference",
            player_id=str(player_id or ""),
            session_id=str(session_id or ""),
            item_id=canonical_text_id,
            status="ok",
            device_id=str(device_id or ""),
            metadata={
                "session_code": session_code,
                "event_slug": event_slug,
                "question_set_id": question_set_id,
                "response_scope": response_scope,
            },
        )

    def get_session_rows(
        self,
        session_id: str,
        *,
        text_ids: Optional[Sequence[str]] = None,
    ) -> List[Dict[str, Any]]:
        question_ids = {str(question["question_id"]) for question in SESSION_QUESTIONS}
        question_ids.add(QUESTION_IDENTITY)
        question_ids.update(QUESTION_BUNDLE_IDS)
        rows = self.interaction_repo().get_responses(session_id)
        filtered = [row for row in rows if str(row.get("item_id") or "") in question_ids]
        allowed_text_ids = {str(item).strip() for item in text_ids or [] if str(item).strip()}
        if not allowed_text_ids:
            return filtered
        return [
            row
            for row in filtered
            if str(row.get("text_id") or "").strip() in allowed_text_ids
        ]

    def latest_submission_by_access_key_hash(
        self,
        *,
        session_id: str,
        access_key_hash: str,
        text_ids: Optional[Sequence[str]] = None,
    ) -> Dict[str, Any] | None:
        rows = self.get_session_rows(session_id, text_ids=text_ids)
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

    def resolve_access_key(self, raw_key: str) -> tuple[str | None, str | None]:
        return resolve_access_key_input(self.notion_repo, raw_key)

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
                normalized_bundle = _normalize_bundle(bundle)
                for key, value in normalized_bundle.items():
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
