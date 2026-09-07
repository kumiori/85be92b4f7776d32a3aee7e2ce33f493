from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from conference.repo import (
    ANONYMOUS_COMPLEXITY_NAME,
    ANONYMOUS_DALEMBERTIENNES_NAME,
    ConferenceRepo,
    DALEMBERTIENNES_QUESTION_BUNDLE,
)
from conference.settings import ConferenceSettings
from infra.key_codec import hex_to_emoji, split_emoji_symbols


class _FakeNotionRepo:
    def __init__(self, matches_by_query, sessions_by_code=None):
        self.client = object()
        self._matches_by_query = matches_by_query
        self._sessions_by_code = sessions_by_code or {}
        self.upsert_calls = []
        self.metadata_calls = []

    def find_players_by_emoji_suffix(self, suffix: str, length: int = 4):
        return list(self._matches_by_query.get((suffix, length), []))

    def get_session_by_code(self, session_code: str):
        return self._sessions_by_code.get(session_code)

    def upsert_player(self, **kwargs):
        self.upsert_calls.append(dict(kwargs))
        return {"id": kwargs.get("player_id") or "player-1"}

    def update_player_metadata(self, player_id: str, **kwargs):
        self.metadata_calls.append({"player_id": player_id, **dict(kwargs)})
        return {"id": player_id, **dict(kwargs)}


class _FakeInteractionRepo:
    def __init__(self, rows):
        self._rows = list(rows)

    def get_responses(self, session_id: str):
        return list(self._rows)


class _CapturingInteractionRepo:
    def __init__(self):
        self.calls = []

    def save_response(self, **kwargs):
        self.calls.append(dict(kwargs))


def _settings() -> ConferenceSettings:
    return ConferenceSettings(
        notion_token="",
        notion_version="2025-09-03",
        session_responses_db_id="responses-db",
        default_session_code="complexity-session",
        debug=False,
    )


def test_resolve_access_key_accepts_full_canonical_key():
    repo = ConferenceRepo(_FakeNotionRepo({}), _settings())
    key = "0123456789ABCDEF0123456789ABCDEF"

    access_key, error = repo.resolve_access_key(key)

    assert access_key == key
    assert error is None


def test_resolve_access_key_restores_unique_four_emoji_suffix_lookup():
    key = "0123456789ABCDEF0123456789ABCDEF"
    suffix4 = "".join(split_emoji_symbols(hex_to_emoji(key))[-4:])
    repo = ConferenceRepo(
        _FakeNotionRepo({(suffix4, 4): [{"access_key": key}]}),
        _settings(),
    )

    access_key, error = repo.resolve_access_key(suffix4)

    assert access_key == key
    assert error is None


def test_resolve_access_key_requests_two_more_symbols_when_suffix_is_ambiguous():
    key_a = "0123456789ABCDEF0123456789ABCDEF"
    key_b = "FEDCBA9876543210FEDCBA9876543210"
    suffix4 = "".join(split_emoji_symbols(hex_to_emoji(key_a))[-4:])
    repo = ConferenceRepo(
        _FakeNotionRepo({(suffix4, 4): [{"access_key": key_a}, {"access_key": key_b}]}),
        _settings(),
    )

    access_key, error = repo.resolve_access_key(suffix4)

    assert access_key is None
    assert error == "Multiple matches. Add two more emoji symbols."


def test_resolve_access_key_uses_six_emoji_suffix_to_disambiguate():
    key_a = "0123456789ABCDEF0123456789ABCDEF"
    key_b = "FEDCBA9876543210FEDCBA9876543210"
    symbols = split_emoji_symbols(hex_to_emoji(key_a))
    suffix4 = "".join(symbols[-4:])
    suffix6 = "".join(symbols[-6:])
    repo = ConferenceRepo(
        _FakeNotionRepo(
            {
                (suffix4, 4): [{"access_key": key_a}, {"access_key": key_b}],
                (suffix6, 6): [{"access_key": key_a}],
            }
        ),
        _settings(),
    )

    access_key, error = repo.resolve_access_key(suffix6)

    assert access_key == key_a
    assert error is None


def test_resolve_access_key_accepts_legacy_suffix_symbols_outside_current_alphabet():
    legacy_suffix = "🟩⬜💥🎉"
    key = "0123456789ABCDEF0123456789ABCDEF"
    repo = ConferenceRepo(
        _FakeNotionRepo({(legacy_suffix, 4): [{"access_key": key}]}),
        _settings(),
    )

    access_key, error = repo.resolve_access_key(legacy_suffix)

    assert access_key == key
    assert error is None


def test_group_rows_by_submission_keeps_boiler_room_contribution_from_bundle():
    repo = ConferenceRepo(_FakeNotionRepo({}), _settings())

    grouped = repo.group_rows_by_submission(
        [
            {
                "item_id": "PISA_MEETING_BUNDLE",
                "player_id": "player-1",
                "response_id": "response-1",
                "timestamp": "2026-06-26T10:00:00Z",
                "value_json": {
                    "field": "session_bundle",
                    "access_key_hash": "hash-1",
                    "bundle": {
                        "schema_version": "2",
                        "profile": {
                            "role": ["theory"],
                            "career_stage": "",
                            "scientific_home": {
                                "country": "",
                                "city": "",
                                "institution": "",
                            },
                            "computational_scale": "",
                            "collaboration_style": "",
                            "assets": ["software"],
                            "complexity_fingerprint": {
                                "theory": 0,
                                "data": 0,
                                "experiments": 0,
                                "mechanisms": 0,
                            },
                        },
                        "session": {
                            "depth": "quick",
                            "motivations": ["methods"],
                            "obstacle": ["data"],
                            "challenge": "benchmark",
                            "follow_up_interest": "yes",
                            "open_question": "",
                            "boiler_room_contribution": "Poster draft",
                            "question_flags": {
                                "COMPLEXITY_ROLE": {
                                    "flags": ["unclear"],
                                    "note": "Need mixed roles",
                                }
                            },
                            "deferred_fields": [],
                            "identity_reveal_targets": [],
                        },
                    },
                },
            }
        ]
    )

    assert grouped[0]["boiler_room_contribution"] == "Poster draft"
    assert grouped[0]["question_flags"] == {
        "COMPLEXITY_ROLE": {
            "flags": ["unclear"],
            "note": "Need mixed roles",
        }
    }


def test_group_rows_by_submission_keeps_question_flags_from_flat_legacy_bundle():
    repo = ConferenceRepo(_FakeNotionRepo({}), _settings())

    grouped = repo.group_rows_by_submission(
        [
            {
                "item_id": "PISA_MEETING_BUNDLE",
                "player_id": "player-1",
                "response_id": "response-2",
                "timestamp": "2026-06-26T10:00:00Z",
                "value_json": {
                    "field": "session_bundle",
                    "access_key_hash": "hash-2",
                    "bundle": {
                        "mode": "quick",
                        "role": ["theory"],
                        "systems": ["dynamic"],
                        "expectations": "smooth_evolutions",
                        "motivations": ["fundamental_understanding"],
                        "obstacle": ["models"],
                        "challenge": "benchmarks",
                        "continue_conversation": "happy_to_engage",
                        "question_flags": {
                            "PISA_ROLE": {
                                "flags": ["too_narrow"],
                                "note": "Needs room for mixed profiles",
                            }
                        },
                    },
                },
            }
        ]
    )

    assert grouped[0]["question_flags"] == {
        "PISA_ROLE": {
            "flags": ["too_narrow"],
            "note": "Needs room for mixed profiles",
        }
    }


def test_resolve_session_with_explicit_code_does_not_fallback_to_default():
    repo = ConferenceRepo(
        _FakeNotionRepo(
            {},
            sessions_by_code={"pisa-conference-session": {"id": "young", "session_code": "pisa-conference-session"}},
        ),
        _settings(),
    )

    session = repo.resolve_session(session_code="complexity-session")

    assert session is None


def test_get_session_rows_can_filter_by_text_id():
    repo = ConferenceRepo(_FakeNotionRepo({}), _settings())
    repo._interaction_repo = _FakeInteractionRepo(
        [
            {
                "item_id": "PISA_MEETING_BUNDLE",
                "text_id": "complexity_session_v2",
            },
            {
                "item_id": "PISA_MEETING_BUNDLE",
                "text_id": "pisa_session_v2",
            },
        ]
    )

    rows = repo.get_session_rows("session-1", text_ids=["complexity_session_v2"])

    assert rows == [{"item_id": "PISA_MEETING_BUNDLE", "text_id": "complexity_session_v2"}]


def test_save_session_response_set_uses_dalembertiennes_bundle_id():
    repo = ConferenceRepo(_FakeNotionRepo({}), _settings())
    capture = _CapturingInteractionRepo()
    repo._interaction_repo = capture

    payload = {
        "schema_version": "2",
        "profile": {"persistence_scope": "persistent_profile"},
        "session": {
            "event_slug": "dalembertiennes",
            "session_code": "dalembertiennes_2026",
            "question_set_id": "dalembertiennes_v1",
            "response_scope": "event_specific",
            "event_status": "draft",
            "text_id": "dalembertiennes_v1",
            "lab_question": "placeholder",
        },
    }

    repo.save_session_response_set(
        session_id="session-1",
        player_id="player-1",
        text_id="dalembertiennes_v1",
        device_id="device-1",
        access_key_hash="hash-1",
        access_key_last4="🎯",
        payload=payload,
    )

    assert capture.calls
    assert capture.calls[0]["question_id"] == DALEMBERTIENNES_QUESTION_BUNDLE
    assert capture.calls[0]["text_id"] == "dalembertiennes_v1"


def test_save_session_response_set_uses_payload_text_id_as_canonical_text_id():
    repo = ConferenceRepo(_FakeNotionRepo({}), _settings())
    capture = _CapturingInteractionRepo()
    repo._interaction_repo = capture

    payload = {
        "schema_version": "2",
        "profile": {"persistence_scope": "persistent_profile"},
        "session": {
            "event_slug": "complexity",
            "session_code": "petnica_2026",
            "question_set_id": "complexity_v2",
            "response_scope": "event_specific",
            "event_status": "draft",
            "text_id": "petnica_2026",
            "open_question": "placeholder",
        },
    }

    repo.save_session_response_set(
        session_id="session-1",
        player_id="player-1",
        text_id="",
        device_id="device-1",
        access_key_hash="hash-1",
        access_key_last4="🎯",
        payload=payload,
    )

    assert capture.calls
    assert capture.calls[0]["question_id"] == "COMPLEXITY_BUNDLE"
    assert capture.calls[0]["text_id"] == "petnica_2026"


def test_save_session_response_set_accepts_isolated_wg2_debug_scope():
    repo = ConferenceRepo(_FakeNotionRepo({}), _settings())
    capture = _CapturingInteractionRepo()
    repo._interaction_repo = capture
    payload = {
        "schema_version": "2",
        "profile": {"persistence_scope": "persistent_profile"},
        "session": {
            "event_slug": "un_wg2_visibility_debug",
            "session_code": "un_wg2_debug_2026",
            "question_set_id": "un_wg2_v1",
            "response_scope": "debug_session",
            "event_status": "draft",
            "text_id": "un_wg2_v1",
            "test_mode": True,
            "data_classification": "debug",
        },
    }

    repo.save_session_response_set(
        session_id="debug-session-id",
        player_id="debug-player-id",
        text_id="un_wg2_v1",
        device_id="debug-device",
        access_key_hash="debug-hash",
        access_key_last4="🧪",
        payload=payload,
    )

    assert capture.calls[0]["session_id"] == "debug-session-id"
    assert capture.calls[0]["text_id"] == "un_wg2_v1"


def test_save_session_response_set_rejects_debug_slug_on_production_wg2_session():
    repo = ConferenceRepo(_FakeNotionRepo({}), _settings())
    capture = _CapturingInteractionRepo()
    repo._interaction_repo = capture
    payload = {
        "schema_version": "2",
        "profile": {"persistence_scope": "persistent_profile"},
        "session": {
            "event_slug": "un_wg2_visibility_debug",
            "session_code": "un_wg2_core_2026",
            "question_set_id": "un_wg2_v1",
            "response_scope": "event_session",
            "event_status": "draft",
            "text_id": "un_wg2_v1",
        },
    }

    try:
        repo.save_session_response_set(
            session_id="production-session-id",
            player_id="debug-player-id",
            text_id="un_wg2_v1",
            device_id="debug-device",
            access_key_hash="debug-hash",
            access_key_last4="🧪",
            payload=payload,
        )
    except ValueError as exc:
        assert "un_wg2_wrong_event_slug" in str(exc)
    else:
        raise AssertionError("Expected cross-scoped WG2 debug write to fail.")
    assert capture.calls == []


def test_save_session_response_set_rejects_text_id_mismatch():
    repo = ConferenceRepo(_FakeNotionRepo({}), _settings())
    capture = _CapturingInteractionRepo()
    repo._interaction_repo = capture

    payload = {
        "schema_version": "2",
        "profile": {"persistence_scope": "persistent_profile"},
        "session": {
            "event_slug": "dalembertiennes",
            "session_code": "dalembertiennes_2026",
            "question_set_id": "dalembertiennes_v1",
            "response_scope": "event_specific",
            "event_status": "draft",
            "text_id": "dalembertiennes_v1",
        },
    }

    try:
        repo.save_session_response_set(
            session_id="session-1",
            player_id="player-1",
            text_id="petnica_2026",
            device_id="device-1",
            access_key_hash="hash-1",
            access_key_last4="🎯",
            payload=payload,
        )
    except ValueError as exc:
        assert "text_id_mismatch_outer_petnica_2026_payload_dalembertiennes_v1" in str(exc)
    else:
        raise AssertionError("Expected text_id mismatch to be rejected.")

    assert capture.calls == []


def test_save_session_response_set_rejects_unknown_text_id():
    repo = ConferenceRepo(_FakeNotionRepo({}), _settings())
    capture = _CapturingInteractionRepo()
    repo._interaction_repo = capture

    payload = {
        "schema_version": "2",
        "profile": {"persistence_scope": "persistent_profile"},
        "session": {
            "event_slug": "mystery-event",
            "session_code": "mystery_2026",
            "question_set_id": "mystery_v0",
            "response_scope": "event_specific",
            "event_status": "draft",
            "text_id": "mystery_v0",
        },
    }

    try:
        repo.save_session_response_set(
            session_id="session-1",
            player_id="player-1",
            text_id="mystery_v0",
            device_id="device-1",
            access_key_hash="hash-1",
            access_key_last4="🎯",
            payload=payload,
        )
    except ValueError as exc:
        assert "Unknown questionnaire text_id: 'mystery_v0'" in str(exc)
    else:
        raise AssertionError("Expected unknown text_id to be rejected.")

    assert capture.calls == []


def test_upsert_conference_player_uses_dalembertiennes_anonymous_name():
    notion_repo = _FakeNotionRepo({})
    repo = ConferenceRepo(notion_repo, _settings())

    payload = {
        "schema_version": "2",
        "profile": {"persistence_scope": "persistent_profile"},
        "session": {
            "event_slug": "dalembertiennes",
            "session_code": "dalembertiennes_2026",
            "text_id": "dalembertiennes_v1",
        },
    }

    repo.upsert_conference_player(
        session_id="session-1",
        access_key="0123456789ABCDEF0123456789ABCDEF",
        payload=payload,
        identity_metadata={"alias": "", "identity": "", "contact": ""},
    )

    assert notion_repo.upsert_calls
    assert notion_repo.upsert_calls[0]["nickname"] == ANONYMOUS_DALEMBERTIENNES_NAME


def test_upsert_conference_player_keeps_complexity_anonymous_name():
    notion_repo = _FakeNotionRepo({})
    repo = ConferenceRepo(notion_repo, _settings())

    payload = {
        "schema_version": "2",
        "profile": {"persistence_scope": "persistent_profile"},
        "session": {
            "event_slug": "complexity",
            "session_code": "petnica_2026",
            "text_id": "petnica_2026",
        },
    }

    repo.upsert_conference_player(
        session_id="session-1",
        access_key="0123456789ABCDEF0123456789ABCDEF",
        payload=payload,
        identity_metadata={"alias": "", "identity": "", "contact": ""},
    )

    assert notion_repo.upsert_calls
    assert notion_repo.upsert_calls[0]["nickname"] == ANONYMOUS_COMPLEXITY_NAME
