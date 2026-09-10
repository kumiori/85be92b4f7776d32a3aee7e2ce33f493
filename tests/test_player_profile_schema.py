from __future__ import annotations

from types import SimpleNamespace

import pytest

from infra.notion_repo import NotionRepo


PROFILE_SCHEMA = {
    "events": {"type": "relation", "relation": {"database_id": "sessions"}},
    "email": {"type": "email"},
    "institution": {"type": "rich_text"},
    "base_location": {"type": "rich_text"},
    "base_location_label": {"type": "rich_text"},
    "base_location_place_id": {"type": "rich_text"},
    "base_location_lat": {"type": "number"},
    "base_location_lon": {"type": "number"},
}


def _repo(schema):
    repo = object.__new__(NotionRepo)
    repo.players_db_id = "players"
    repo.session_db_id = "sessions"
    repo._db_props = lambda _db_id: schema
    return repo


def test_events_property_is_explicit_session_membership_mapping():
    repo = _repo(PROFILE_SCHEMA)
    props = repo._player_properties(
        "session-1", "key", "Test Person", "None", False, False
    )
    assert props["events"] == {"relation": [{"id": "session-1"}]}


def test_normalized_player_reconstructs_structured_base_location():
    repo = _repo(PROFILE_SCHEMA)
    page = {
        "id": "player-1",
        "properties": {
            "events": {"type": "relation", "relation": [{"id": "session-1"}]},
            "email": {"type": "email", "email": "test.person@example.org"},
            "institution": {"type": "rich_text", "rich_text": [{"plain_text": "Example Institute"}]},
            "base_location_label": {"type": "rich_text", "rich_text": [{"plain_text": "Udine, Italy"}]},
            "base_location_place_id": {"type": "rich_text", "rich_text": [{"plain_text": "test:udine"}]},
            "base_location_lat": {"type": "number", "number": 46.071},
            "base_location_lon": {"type": "number", "number": 13.234},
        },
    }
    player = repo._normalize_player(page, players_db_id="players")
    assert player["session_ids"] == ["session-1"]
    assert player["email"] == "test.person@example.org"
    assert player["institution"] == "Example Institute"
    assert player["base_location"] == {
        "display_label": "Udine, Italy",
        "place_id": "test:udine",
        "latitude": 46.071,
        "longitude": 13.234,
    }


def test_supplied_profile_field_without_schema_mapping_fails_loudly():
    repo = _repo({"events": {"type": "relation", "relation": {"database_id": "event-log"}}})
    repo.get_player_by_id = lambda *_args, **_kwargs: {"id": "player-1"}
    repo.client = SimpleNamespace()
    with pytest.raises(RuntimeError, match="canonical field `email`"):
        repo.update_player_metadata("player-1", email="test.person@example.org")


def test_events_relation_is_not_membership_when_it_targets_another_database():
    repo = _repo({"events": {"type": "relation", "relation": {"database_id": "event-log"}}})
    assert repo._player_prop_name("players", "session_membership") is None
