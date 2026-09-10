from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path

from conference.events import PREDICTION_DEBUG_SESSION_CODE, PREDICTION_SESSION_CODE, UN_WG2_SESSION_CODE
from conference.host import (
    build_response_field,
    cumulative_timeline,
    host_session_options,
    load_host_snapshot,
    mask_email,
    normalize_locations,
    normalize_profile_locations,
    snapshot_metrics,
)
from conference.registry import resolve_question_set_bundle


class FakeRepo:
    def __init__(self, session_code: str, rows: list[dict]):
        self.session_code = session_code
        self.rows = rows
        self.calls: list[str] = []

    def resolve_session(self, *, session_code: str):
        self.calls.append("session")
        assert session_code == self.session_code
        return {"id": f"id-{session_code}", "session_code": session_code}

    def get_session_rows(self, session_id: str, *, text_ids=()):
        self.calls.append("responses")
        assert session_id == f"id-{self.session_code}"
        return list(self.rows)

    def group_rows_by_submission(self, rows):
        self.calls.append("group-local")
        return [dict(row) for row in rows]


def _submission(**updates):
    row = {
        "player_id": "player-1",
        "actor_key": "player-1",
        "identity": "Alice",
        "contact": "alice.smith@cornell.edu",
        "submitted_at": "2026-09-10T10:00:00Z",
        "wg2_role_lens": ["modeller"],
    }
    row.update(updates)
    return row


def test_selector_resolves_registered_production_and_test_sessions():
    options = host_session_options(include_test=True)
    by_code = {item["session_code"]: item for item in options}
    assert PREDICTION_SESSION_CODE in by_code
    assert PREDICTION_DEBUG_SESSION_CODE in by_code
    assert by_code[PREDICTION_SESSION_CODE]["test_mode"] is False
    assert by_code[PREDICTION_DEBUG_SESSION_CODE]["test_mode"] is True


def test_snapshot_is_session_scoped_and_loaded_with_bounded_remote_reads():
    repo = FakeRepo(UN_WG2_SESSION_CODE, [_submission()])
    remote_calls: list[str] = []
    snapshot = load_host_snapshot(
        UN_WG2_SESSION_CODE,
        repo=repo,
        list_players=lambda session_id: remote_calls.append("players") or [{"id": "player-1", "nickname": "Alice"}],
        list_events=lambda session_id: remote_calls.append("events") or [{"event_type": "submitted"}],
        now=lambda: datetime(2026, 9, 10, tzinfo=timezone.utc),
    )
    assert snapshot.session["session_code"] == UN_WG2_SESSION_CODE
    assert {row["player_id"] for row in snapshot.submissions} == {"player-1"}
    assert repo.calls == ["session", "responses", "group-local"]
    assert remote_calls == ["players", "events"]
    # Local views, metrics, sorting, and filtering consume the snapshot only.
    assert snapshot_metrics(snapshot)["participants"] == 1
    sorted(snapshot.participants, key=lambda row: row["last_contribution"])
    assert remote_calls == ["players", "events"]


def test_production_and_debug_snapshots_cannot_mix():
    production = FakeRepo(PREDICTION_SESSION_CODE, [{"player_id": "production", "submitted_at": "2026-09-10T10:00:00Z"}])
    debug = FakeRepo(PREDICTION_DEBUG_SESSION_CODE, [{"player_id": "debug", "submitted_at": "2026-09-10T10:01:00Z"}])
    kwargs = {"list_players": lambda _: [], "list_events": lambda _: []}
    prod_snapshot = load_host_snapshot(PREDICTION_SESSION_CODE, repo=production, **kwargs)
    debug_snapshot = load_host_snapshot(PREDICTION_DEBUG_SESSION_CODE, repo=debug, **kwargs)
    assert {row["player_id"] for row in prod_snapshot.submissions} == {"production"}
    assert {row["player_id"] for row in debug_snapshot.submissions} == {"debug"}


def test_counts_response_field_and_skip_flag_survive_normalization():
    bundle = resolve_question_set_bundle(session_code=UN_WG2_SESSION_CODE)
    question = bundle.question_set.questions[0]
    submissions = [_submission(**{question.field: "yes", "question_flags": {question.question_id: {"flags": ["unclear"]}}}), _submission(player_id="player-2", actor_key="player-2", identity="Bob", deferred_fields=[question.field])]
    field = build_response_field(submissions, bundle)
    first = next(cell for cell in field if cell["participant_id"] == "player-1" and cell["question_id"] == question.question_id)
    second = next(cell for cell in field if cell["participant_id"] == "player-2" and cell["question_id"] == question.question_id)
    assert first["status"] == "answered" and first["flagged"] is True
    assert second["status"] == "skipped" and second["skipped"] is True


def test_timeline_is_chronological_and_cumulative():
    points = cumulative_timeline([{"submitted_at": "2026-09-10T12:00:00Z"}, {"submitted_at": "2026-09-10T09:00:00Z"}, {"submitted_at": ""}])
    assert [point["cumulative"] for point in points] == [1, 2]
    assert [point["timestamp"] for point in points] == ["2026-09-10T09:00:00+00:00", "2026-09-10T12:00:00+00:00"]


def test_location_normalization_and_missing_optional_geography():
    wg2 = resolve_question_set_bundle(session_code=UN_WG2_SESSION_CODE)
    points = normalize_locations([{"wg2_main_location": {"country_region": "Italy", "coordinates": "46.07, 13.23"}}], wg2)
    assert points[0]["lat"] == 46.07 and points[0]["lng"] == 13.23
    prediction = resolve_question_set_bundle(session_code=PREDICTION_SESSION_CODE)
    assert normalize_locations([{"role": "researcher"}], prediction) == []


def test_identified_profile_is_joined_locally_and_supplies_spatial_context():
    repo = FakeRepo(PREDICTION_DEBUG_SESSION_CODE, [{"player_id": "player-1", "actor_key": "player-1", "identity": "Test Person", "submitted_at": "2026-09-10T10:00:00Z"}])
    location = {
        "display_label": "Udine, Italy",
        "place_id": "test:udine",
        "latitude": 46.071,
        "longitude": 13.234,
    }
    player_reads = []
    snapshot = load_host_snapshot(
        PREDICTION_DEBUG_SESSION_CODE,
        repo=repo,
        list_players=lambda session_id: player_reads.append(session_id) or [{"id": "player-1", "nickname": "Test Person", "email": "test.person@example.org", "institution": "Example Institute", "base_location": location}],
        list_events=lambda _: [],
    )

    assert player_reads == [f"id-{PREDICTION_DEBUG_SESSION_CODE}"]
    participant = snapshot.participants[0]
    assert participant["email"] == "t**********@e*****e.org"
    assert participant["institution"] == "Example Institute"
    assert participant["location"] == "Udine, Italy"
    assert list(snapshot.locations) == normalize_profile_locations([{"base_location": location}])


def test_email_masking_is_conservative_and_missing_is_explicit():
    assert mask_email("andres@example.com") == "a*****@e*****e.com"
    assert mask_email("alice.smith@cornell.edu") == "a**********@c*****l.edu"
    assert mask_email("") == "<missing>"


def test_legacy_host_entry_points_are_thin_generic_wrappers():
    root = Path(__file__).resolve().parents[1]
    for relative in ["pages/16_Pisa_Meeting_Host.py", "pages/23_Dalembertiennes_Host.py", "pages/27_UN_WG2_Host.py", "pages/35_Event_Host.py"]:
        source = (root / relative).read_text()
        assert "from conference.host_ui import main" in source
        assert len(source.splitlines()) <= 5
