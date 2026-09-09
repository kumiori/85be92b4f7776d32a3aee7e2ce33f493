from __future__ import annotations

from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from conference.events import event_config_for_slug
from conference.participation import InMemoryParticipationRepository


def _profile(email: str = "Ada@Example.ORG") -> dict[str, str]:
    return {
        "name": "Ada Lovelace",
        "email": email,
        "institution": "CISM",
        "base_location": "Udine",
    }


def test_prediction_event_has_distinct_production_and_debug_sessions():
    event = event_config_for_slug("prediction")

    assert event is not None
    assert event.session_code == "prediction_2026"
    assert event.test_session_code == "prediction_debug_2026"
    assert event.session_code != event.test_session_code
    assert event.identity_policy.required_fields == ("name", "email")
    assert event.persistence_policy == "integration_only"


def test_existing_participant_joins_prediction_without_losing_membership():
    repo = InMemoryParticipationRepository()
    player = repo.create_participant(
        access_key="ice-key",
        profile=_profile(),
        session_ids=["ice-session"],
    )

    joined = repo.ensure_participation(
        player_id=player["id"], session_id="prediction-session"
    )

    assert repo.get_participant(player["id"])["session_ids"] == [
        "ice-session",
        "prediction-session",
    ]
    assert joined["player_id"] == player["id"]


def test_event_aggregates_are_isolated_by_persisted_session():
    repo = InMemoryParticipationRepository()
    player = repo.create_participant(access_key="key", profile=_profile())
    ice = repo.ensure_participation(player_id=player["id"], session_id="ice-session")
    prediction = repo.ensure_participation(
        player_id=player["id"], session_id="prediction-session"
    )
    repo.submit(ice["participation_id"], {"signal": "ice"}, "ice-write")
    repo.submit(
        prediction["participation_id"], {"signal": "prediction"}, "prediction-write"
    )

    assert [row["answers"]["signal"] for row in repo.submissions("ice-session")] == [
        "ice"
    ]
    assert [
        row["answers"]["signal"]
        for row in repo.submissions("prediction-session")
    ] == ["prediction"]


def test_partial_prediction_checkpoint_survives_browser_state_loss_and_resumes():
    durable = InMemoryParticipationRepository()
    player = durable.create_participant(access_key="key", profile=_profile())
    participation = durable.ensure_participation(
        player_id=player["id"], session_id="prediction-session"
    )
    durable.checkpoint(
        participation["participation_id"],
        state={"answers": {"q1": "partial"}},
        current_position="q2",
        completion_state="in_progress",
    )

    resumed = durable.resume(
        player_id=player["id"], session_id="prediction-session"
    )

    assert resumed["state"] == {"answers": {"q1": "partial"}}
    assert resumed["current_position"] == "q2"
    assert resumed["completion_state"] == "in_progress"


def test_normalized_email_cannot_create_ambiguous_duplicate_participation():
    repo = InMemoryParticipationRepository()
    first = repo.create_participant(access_key="key-one", profile=_profile())

    second = repo.identify_or_resolve(access_key="key-two", profile=_profile("ada@example.org"))

    assert second["status"] == "recovery_required"
    assert second["player_id"] == first["id"]
    assert len(repo.participants()) == 1


def test_double_submission_is_idempotent_but_revision_is_append_only():
    repo = InMemoryParticipationRepository()
    player = repo.create_participant(access_key="key", profile=_profile())
    participation = repo.ensure_participation(
        player_id=player["id"], session_id="prediction-session"
    )

    first = repo.submit(
        participation["participation_id"], {"answer": "A"}, "same-write"
    )
    retry = repo.submit(
        participation["participation_id"], {"answer": "A"}, "same-write"
    )
    revision = repo.revise(
        participation["participation_id"],
        {"answer": "B"},
        write_idempotency_key="revision-write",
        supersedes_response_id=first["response_id"],
    )

    assert retry["response_id"] == first["response_id"]
    assert len(repo.submissions("prediction-session")) == 2
    assert revision["response_id"] != first["response_id"]
    assert revision["supersedes_response_id"] == first["response_id"]


def test_prediction_debug_data_never_appears_in_production_results():
    repo = InMemoryParticipationRepository()
    player = repo.create_participant(access_key="key", profile=_profile())
    production = repo.ensure_participation(
        player_id=player["id"], session_id="prediction-production"
    )
    debug = repo.ensure_participation(
        player_id=player["id"], session_id="prediction-debug", test_mode=True
    )
    repo.submit(production["participation_id"], {"answer": "production"}, "p")
    repo.submit(debug["participation_id"], {"answer": "debug"}, "d")

    assert [
        row["answers"]["answer"]
        for row in repo.submissions("prediction-production", include_test=False)
    ] == ["production"]
