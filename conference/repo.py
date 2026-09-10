from __future__ import annotations

import hashlib
import re
import unicodedata
from typing import Any, Dict, List, Optional, Sequence

from conference.registry import conference_question_ids, resolve_question_set_bundle
from conference.participation import normalize_email, participation_id_for
from conference.question_flags import normalize_question_flags
from conference.question_skips import normalize_question_skips
from conference.settings import ConferenceSettings
from infra.key_codec import hex_to_emoji, normalize_access_key, split_emoji_symbols
from infra.event_logger import get_module_logger, log_event
from repositories.interaction_repo import NotionInteractionRepository


QUESTION_IDENTITY = "PISA_IDENTITY_BLOCK"
LEGACY_QUESTION_BUNDLE = "PISA_MEETING_BUNDLE"
COMPLEXITY_QUESTION_BUNDLE = "COMPLEXITY_BUNDLE"
DALEMBERTIENNES_QUESTION_BUNDLE = "DALEMBERTIENNES_BUNDLE"
LEGACY_DALAMBERTIENNES_QUESTION_BUNDLE = "DALAMBERTIENNES_BUNDLE"
UN_WG2_QUESTION_BUNDLE = "UN_WG2_BUNDLE"
PREDICTION_QUESTION_BUNDLE = "PREDICTION_BUNDLE"
PARTICIPATION_CHECKPOINT = "CONFERENCE_PARTICIPATION_CHECKPOINT"
QUESTION_BUNDLE_IDS = {
    LEGACY_QUESTION_BUNDLE,
    COMPLEXITY_QUESTION_BUNDLE,
    DALEMBERTIENNES_QUESTION_BUNDLE,
    LEGACY_DALAMBERTIENNES_QUESTION_BUNDLE,
    UN_WG2_QUESTION_BUNDLE,
    PREDICTION_QUESTION_BUNDLE,
}
ANONYMOUS_COMPLEXITY_NAME = "🌀"
ANONYMOUS_DALEMBERTIENNES_NAME = "📐"
ANONYMOUS_UN_WG2_NAME = "🧭"
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


def _resolved_question_set(bundle: Dict[str, Any]) -> Any | None:
    session = bundle.get("session") if isinstance(bundle.get("session"), dict) else {}
    session_code = _as_text(session.get("session_code", bundle.get("session_code", "")))
    text_id = _as_text(session.get("text_id", bundle.get("text_id", "")))
    try:
        return resolve_question_set_bundle(
            session_code=session_code, text_id=text_id
        ).question_set
    except Exception:
        return None


def _normalize_question_value(question: Any, value: Any) -> Any:
    input_type = str(getattr(question, "input_type", "") or "")
    if input_type == "multi":
        return _as_list(value)
    if input_type == "fingerprint":
        return _as_fingerprint(value)
    return _as_text(value)


def _primary_text_response(bundle: Dict[str, Any]) -> str:
    question_set = _resolved_question_set(bundle)
    session = bundle.get("session") if isinstance(bundle.get("session"), dict) else {}
    profile = bundle.get("profile") if isinstance(bundle.get("profile"), dict) else {}
    if question_set:
        profile_fields = set(getattr(question_set, "profile_fields", ()))
        for question in question_set.questions:
            field = str(question.field)
            if str(question.input_type) != "text":
                continue
            source = profile if field in profile_fields else session
            text = _as_text(source.get(field, bundle.get(field, "")))
            if text:
                return text
    for field in ("open_question", "open_text", "lab_question"):
        text = _as_text(session.get(field, bundle.get(field, "")))
        if text:
            return text
    return ""


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

        if (
            _is_regional_indicator(current)
            and idx < len(token)
            and _is_regional_indicator(token[idx])
        ):
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
    question_set = _resolved_question_set(bundle)
    role_question = None
    if question_set:
        role_question = next(
            (
                question
                for question in question_set.questions
                if str(question.field) == "role"
            ),
            None,
        )
    role_extra_field = (
        str(getattr(role_question, "free_text_field", "") or "").strip()
        if role_question
        else ""
    )
    role_custom = _as_text(
        profile.get(
            "role_custom",
            profile.get(
                role_extra_field,
                bundle.get("role_custom", bundle.get(role_extra_field, "")),
            ),
        )
    )
    if role_custom and role_custom not in role:
        role.append(role_custom)
    career_stage = _as_text(profile.get("career_stage", bundle.get("career_stage", "")))
    country = _as_text(
        scientific_home.get("country", bundle.get("scientific_home_country", ""))
    )
    city = _as_text(scientific_home.get("city", bundle.get("scientific_home_city", "")))
    institution = _as_text(
        scientific_home.get(
            "institution", bundle.get("scientific_home_institution", "")
        )
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
    open_question = _as_text(
        session.get(
            "open_question", bundle.get("open_question", bundle.get("open_text", ""))
        )
    )
    boiler_room_contribution = _as_text(
        session.get(
            "boiler_room_contribution",
            bundle.get("boiler_room_contribution", bundle.get("notes", "")),
        )
    )
    question_flags = normalize_question_flags(
        session.get("question_flags", bundle.get("question_flags", {}))
    )
    question_skips = normalize_question_skips(
        session.get("question_skips", bundle.get("question_skips", {}))
    )
    raw_question_states = session.get(
        "question_states", bundle.get("question_states", {})
    )
    question_states = {
        str(key): dict(value)
        for key, value in raw_question_states.items()
        if isinstance(value, dict)
    } if isinstance(raw_question_states, dict) else {}
    deferred_fields = _as_list(
        session.get("deferred_fields", bundle.get("deferred_fields", []))
    )
    identity_reveal_targets = _as_list(
        session.get(
            "identity_reveal_targets", bundle.get("identity_reveal_targets", [])
        )
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
    test_mode = bool(session.get("test_mode", bundle.get("test_mode", False)))
    data_classification = _as_text(
        session.get(
            "data_classification",
            bundle.get("data_classification", ""),
        )
    )
    questionnaire_version = _as_text(
        session.get(
            "questionnaire_version",
            bundle.get("questionnaire_version", ""),
        )
    )
    questionnaire_id = _as_text(
        session.get("questionnaire_id", bundle.get("questionnaire_id", question_set_id))
    )
    questionnaire_revision = session.get(
        "questionnaire_revision", bundle.get("questionnaire_revision", questionnaire_version)
    )
    questionnaire_format = session.get(
        "questionnaire_format", bundle.get("questionnaire_format", "")
    )
    questionnaire_status = _as_text(
        session.get("questionnaire_status", bundle.get("questionnaire_status", ""))
    )
    question_provenance = session.get(
        "question_provenance", bundle.get("question_provenance", {})
    )
    raw_refinements = session.get(
        "response_refinements",
        bundle.get("response_refinements", []),
    )
    response_refinements = [
        dict(item) for item in raw_refinements if isinstance(item, dict)
    ] if isinstance(raw_refinements, list) else []
    persistence_scope = _as_text(
        profile.get("persistence_scope", bundle.get("persistence_scope", ""))
    )
    profile_block = {
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
    }
    session_block = {
        "depth": _as_text(session.get("depth", bundle.get("mode", ""))),
        "motivations": motivations,
        "obstacle": obstacle,
        "challenge": challenge,
        "follow_up_interest": follow_up_interest,
        "open_question": open_question,
        "boiler_room_contribution": boiler_room_contribution,
        "question_flags": question_flags,
        "question_skips": question_skips,
        "question_states": question_states,
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
        "test_mode": test_mode,
        "data_classification": data_classification,
        "questionnaire_version": questionnaire_version,
        "questionnaire_id": questionnaire_id,
        "questionnaire_revision": questionnaire_revision,
        "questionnaire_format": questionnaire_format,
        "questionnaire_status": questionnaire_status,
        "question_provenance": dict(question_provenance)
        if isinstance(question_provenance, dict)
        else {},
        "response_refinements": response_refinements,
    }
    generic_values: Dict[str, Any] = {}
    if question_set:
        profile_fields = set(getattr(question_set, "profile_fields", ()))
        for question in question_set.questions:
            field = str(question.field)
            if field == "scientific_home":
                continue
            source = profile if field in profile_fields else session
            normalized_value = _normalize_question_value(
                question,
                source.get(field, bundle.get(field, "")),
            )
            generic_values[field] = normalized_value
            target = profile_block if field in profile_fields else session_block
            target[field] = normalized_value
            free_text_field = str(
                getattr(question, "free_text_field", "") or ""
            ).strip()
            if free_text_field:
                free_text_value = _as_text(
                    source.get(free_text_field, bundle.get(free_text_field, ""))
                )
                generic_values[free_text_field] = free_text_value
                target[free_text_field] = free_text_value
                if field == "role":
                    profile_block["role_custom"] = free_text_value
                    generic_values["role_custom"] = free_text_value

    return {
        "schema_version": _as_text(bundle.get("schema_version")) or "1",
        "mode": _as_text(session.get("depth", bundle.get("mode", ""))),
        "profile": profile_block,
        "session": session_block,
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
        "question_skips": question_skips,
        "question_states": question_states,
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
        "test_mode": test_mode,
        "data_classification": data_classification,
        "questionnaire_version": questionnaire_version,
        "response_refinements": response_refinements,
        "persistence_scope": persistence_scope,
        **generic_values,
    }


def _compact_bundle(payload: Dict[str, Any]) -> Dict[str, Any]:
    if not isinstance(payload.get("profile"), dict) and not isinstance(
        payload.get("session"), dict
    ):
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
        "dalembertiennes_v1": DALEMBERTIENNES_QUESTION_BUNDLE,
        "un_wg2_v1": UN_WG2_QUESTION_BUNDLE,
        "prediction_v0": PREDICTION_QUESTION_BUNDLE,
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
        or text_id in {"dalembertiennes_v0", "dalembertiennes_v1"}
    ):
        return ANONYMOUS_DALEMBERTIENNES_NAME
    if (
        event_slug == "un_wg2_visibility"
        or session_code == "un_wg2_core_2026"
        or text_id == "un_wg2_v1"
    ):
        return ANONYMOUS_UN_WG2_NAME
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
        self.session_responses_db_id = str(
            settings.session_responses_db_id or ""
        ).strip()
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

    def resolve_session(
        self, session_code: str = "", prefer_active: bool = False
    ) -> Optional[Dict[str, Any]]:
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
        default_session = self.notion_repo.get_session_by_code(
            self.settings.default_session_code
        )
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
        intent = _primary_text_response(normalized)
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

    def upsert_identified_conference_player(
        self,
        *,
        session_id: str,
        access_key: str,
        payload: Dict[str, Any],
        identity_profile: Dict[str, Any],
    ) -> Dict[str, Any]:
        name = str(identity_profile.get("name") or "").strip()
        if not name:
            raise ValueError("Name is required.")
        email = normalize_email(str(identity_profile.get("email") or ""))
        matches = self.notion_repo.find_players_by_email(email)
        key_match = self.notion_repo.get_player_by_access_key(access_key)
        if matches:
            unique_ids = {str(item.get("id") or "") for item in matches}
            if len(unique_ids) > 1:
                raise ValueError("This email is ambiguous; a host must resolve it.")
            matched = matches[0]
            if not key_match or str(key_match.get("id") or "") != str(matched.get("id") or ""):
                raise PermissionError(
                    "A participant already uses this email. Use host-assisted recovery."
                )
        player = self.upsert_conference_player(
            session_id=session_id,
            access_key=access_key,
            payload=payload,
            identity_metadata={"identity": name, "contact": email, "alias": name},
        )
        if not player:
            raise RuntimeError("Participant identity could not be persisted.")
        updated = self.notion_repo.update_player_metadata(
            str(player.get("id") or ""),
            nickname=name,
            email=email,
            institution=str(identity_profile.get("institution") or "").strip() or None,
            base_location=(
                dict(identity_profile["base_location"])
                if isinstance(identity_profile.get("base_location"), dict)
                and identity_profile.get("base_location")
                else None
            ),
        )
        return dict(updated or player)

    def save_participation_checkpoint(
        self,
        *,
        session_id: str,
        session_code: str = "",
        player_id: str,
        text_id: str,
        device_id: str,
        state: Dict[str, Any],
        current_position: str,
        completion_state: str = "in_progress",
        test_mode: bool = False,
    ) -> Dict[str, Any]:
        if test_mode and str(session_code or "").strip() != "prediction_debug_2026":
            raise ValueError("A PREDICTION test checkpoint requires the isolated debug session.")
        if str(session_code or "").strip() == "prediction_debug_2026" and not test_mode:
            raise ValueError("The PREDICTION debug session requires test mode.")
        participation_id = participation_id_for(player_id, session_id)
        safe_state = dict(state)
        safe_state.pop("access_key", None)
        checkpoint_id = str(safe_state.get("checkpoint_id") or "").strip()
        if not checkpoint_id:
            checkpoint_id = hashlib.sha256(
                f"{participation_id}:{current_position}:{safe_state!r}".encode("utf-8")
            ).hexdigest()
        value = {
            "field": "participation_checkpoint",
            "participation_id": participation_id,
            "player_id": player_id,
            "session_id": session_id,
            "state": safe_state,
            "current_position": str(current_position or ""),
            "completion_state": str(completion_state or "in_progress"),
            "checkpoint_id": checkpoint_id,
            "test_mode": bool(test_mode),
        }
        saved = self.interaction_repo().save_response(
            session_id=session_id,
            player_id=player_id,
            question_id=PARTICIPATION_CHECKPOINT,
            value=value,
            text_id=text_id,
            device_id=device_id,
        )
        return {"created": True, **value, **dict(saved or {})}

    def latest_participation_checkpoint(
        self, *, session_id: str, player_id: str
    ) -> Dict[str, Any] | None:
        participation_id = participation_id_for(player_id, session_id)
        rows = self.interaction_repo().get_responses_by_item(
            session_id, PARTICIPATION_CHECKPOINT
        )
        matches = []
        for row in rows:
            value = row.get("value_json")
            if isinstance(value, dict) and value.get("participation_id") == participation_id:
                matches.append((str(row.get("timestamp") or row.get("created_at") or ""), value))
        if not matches:
            return None
        matches.sort(key=lambda item: item[0], reverse=True)
        return dict(matches[0][1])

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
        submission_id: str = "",
        revision_id: str = "",
        write_idempotency_key: str = "",
        supersedes_response_id: str = "",
    ) -> Dict[str, Any]:
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
        test_mode = bool(normalized.get("test_mode"))
        data_classification = _session_bundle_value(normalized, "data_classification")
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
        if canonical_text_id in {"dalembertiennes_v0", "dalembertiennes_v1"}:
            if event_slug != "dalembertiennes":
                failure_reasons.append("dalembertiennes_wrong_event_slug")
            if session_code != "dalembertiennes_2026":
                failure_reasons.append("dalembertiennes_wrong_session_code")
            if question_set_id not in {
                "dalembertiennes_v0",
                "dalembertiennes_v1",
                "dalembertiennes_lab_questionnaire_v0",
            }:
                failure_reasons.append("dalembertiennes_wrong_question_set_id")
        if canonical_text_id == "un_wg2_v1":
            wg2_scope_by_session = {
                "un_wg2_core_2026": "un_wg2_visibility",
                "un_wg2_debug_2026": "un_wg2_visibility_debug",
            }
            if session_code not in wg2_scope_by_session:
                failure_reasons.append("un_wg2_wrong_session_code")
            elif event_slug != wg2_scope_by_session[session_code]:
                failure_reasons.append("un_wg2_wrong_event_slug")
            if question_set_id != "un_wg2_v1":
                failure_reasons.append("un_wg2_wrong_question_set_id")
            expected_response_scope = (
                "debug_session"
                if session_code == "un_wg2_debug_2026"
                else "event_session"
            )
            if response_scope != expected_response_scope:
                failure_reasons.append("un_wg2_wrong_response_scope")
            if session_code == "un_wg2_debug_2026":
                if not test_mode:
                    failure_reasons.append("un_wg2_debug_missing_test_mode")
                if data_classification != "debug":
                    failure_reasons.append("un_wg2_debug_wrong_data_classification")
            elif test_mode or data_classification == "debug":
                failure_reasons.append("un_wg2_production_marked_debug")
        if canonical_text_id == "prediction_v0":
            prediction_scope_by_session = {
                "prediction_2026": "prediction",
                "prediction_debug_2026": "prediction_debug",
            }
            if session_code not in prediction_scope_by_session:
                failure_reasons.append("prediction_wrong_session_code")
            elif event_slug != prediction_scope_by_session[session_code]:
                failure_reasons.append("prediction_wrong_event_slug")
            if question_set_id != "prediction_v0":
                failure_reasons.append("prediction_wrong_question_set_id")
            expected_scope = (
                "debug_session" if session_code == "prediction_debug_2026" else "event_session"
            )
            if response_scope != expected_scope:
                failure_reasons.append("prediction_wrong_response_scope")
            if session_code == "prediction_debug_2026":
                if not test_mode:
                    failure_reasons.append("prediction_debug_missing_test_mode")
                if data_classification != "debug":
                    failure_reasons.append("prediction_debug_wrong_data_classification")
            elif test_mode or data_classification == "debug":
                failure_reasons.append("prediction_production_marked_debug")

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
                "test_mode": test_mode,
                "data_classification": data_classification,
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
        submission_id = str(submission_id or hashlib.sha256(
            f"{session_id}:{access_key_hash}:{canonical_text_id}".encode("utf-8")
        ).hexdigest())
        revision_id = str(revision_id or submission_id)
        write_idempotency_key = str(write_idempotency_key or submission_id)
        existing_rows = (
            repo.get_responses_by_item(session_id, bundle_id)
            if hasattr(repo, "get_responses_by_item")
            else []
        )
        for existing in existing_rows:
            raw = existing.get("value_json")
            if isinstance(raw, dict) and str(raw.get("write_idempotency_key") or "") == write_idempotency_key:
                return {
                    "created": False,
                    "response_id": str(existing.get("response_id") or ""),
                    "submission_id": submission_id,
                    "revision_id": str(raw.get("revision_id") or revision_id),
                }
        try:
            saved = repo.save_response(
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
                    "submission_id": submission_id,
                    "revision_id": revision_id,
                    "write_idempotency_key": write_idempotency_key,
                    "supersedes_response_id": str(supersedes_response_id or ""),
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
                "test_mode": test_mode,
                "data_classification": data_classification,
            },
        )
        return {
            "created": True,
            **dict(saved or {}),
            "submission_id": submission_id,
            "revision_id": revision_id,
        }

    def get_session_rows(
        self,
        session_id: str,
        *,
        text_ids: Optional[Sequence[str]] = None,
    ) -> List[Dict[str, Any]]:
        question_ids = set(conference_question_ids())
        question_ids.add(QUESTION_IDENTITY)
        question_ids.update(QUESTION_BUNDLE_IDS)
        rows = self.interaction_repo().get_responses(session_id)
        filtered = [
            row for row in rows if str(row.get("item_id") or "") in question_ids
        ]
        allowed_text_ids = {
            str(item).strip() for item in text_ids or [] if str(item).strip()
        }
        if not allowed_text_ids:
            return filtered
        return [
            row
            for row in filtered
            if str(row.get("text_id") or "").strip() in allowed_text_ids
        ]

    def recognizes_questionnaire_text_id(self, text_id: str) -> bool:
        try:
            _bundle_id_for_text_id(text_id)
        except ValueError:
            return False
        return True

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

    def group_rows_by_submission(
        self, rows: List[Dict[str, Any]]
    ) -> List[Dict[str, Any]]:
        by_actor: Dict[str, Dict[str, Any]] = {}
        for row in sorted(
            rows,
            key=lambda item: str(
                item.get("submitted_at") or item.get("timestamp") or ""
            ),
        ):
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
            actor_key = (
                bundle_key
                if field == "session_bundle" and bundle_key
                else str(
                    row.get("player_id")
                    or row.get("device_id")
                    or row.get("response_id")
                    or row.get("id")
                    or ""
                )
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
                row.get("timestamp")
                or row.get("created_at")
                or submission.get("submitted_at")
                or ""
            )
            submission["response_id"] = str(
                row.get("response_id") or row.get("id") or ""
            )
            submission["player_id"] = str(row.get("player_id") or "")
            submission["session_id"] = str(row.get("session_id") or "")
            submission["text_id"] = str(row.get("text_id") or "")
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
                submission["alias"] = str(
                    payload.get("alias") or bundle.get("alias") or ""
                )
                submission["identity"] = str(
                    payload.get("identity") or bundle.get("identity") or ""
                )
                submission["contact"] = str(
                    payload.get("contact") or bundle.get("contact") or ""
                )
                submission["notes"] = str(
                    payload.get("optional_text") or bundle.get("notes") or ""
                )
                submission["mode"] = str(
                    payload.get("mode") or bundle.get("mode") or ""
                )
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
