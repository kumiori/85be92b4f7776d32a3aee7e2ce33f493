from __future__ import annotations

from dataclasses import replace

import pytest

from conference.events import (
    event_config_for_request,
    navigation_families,
)
from conference.participation import (
    InMemoryParticipationRepository,
    email_validation_message,
)
from conference.question_sets import (
    QuestionDefinition,
    question_interactions,
    step_interactions,
)
from conference.question_state import (
    answer_question,
    flag_question,
    question_state,
    skip_question,
)
from conference.semantic_fields import LocationValue, normalize_location_value
from conference.repo import ConferenceRepo
from conference.settings import ConferenceSettings
from conference.registry import resolve_question_set_bundle
from conference.question_sets.platform_controls_fixture import QUESTION_SET as CONTROLS_FIXTURE


def _profile() -> dict[str, object]:
    return {
        "name": "Ada Lovelace",
        "email": "ada@example.org",
        "institution": "CISM",
        "base_location": {
            "display_label": "Udine, Friuli-Venezia Giulia, Italy",
            "locality": "Udine",
            "region": "Friuli-Venezia Giulia",
            "country": "Italy",
            "country_code": "IT",
            "place_id": "oc:udine",
        },
    }


def test_required_email_distinguishes_missing_from_malformed():
    assert email_validation_message("") == (
        "We use your email to issue or recover access to your answers."
    )
    assert email_validation_message("ada@") == (
        "This email address doesn't seem complete. Can you please double-check it?"
    )
    assert email_validation_message("ADA@EXAMPLE.ORG") == ""


def test_location_value_is_structured_and_rejects_arbitrary_text():
    location = normalize_location_value(_profile()["base_location"])

    assert location == LocationValue(
        display_label="Udine, Friuli-Venezia Giulia, Italy",
        locality="Udine",
        region="Friuli-Venezia Giulia",
        country="Italy",
        country_code="IT",
        place_id="oc:udine",
    )
    with pytest.raises(ValueError, match="lookup"):
        normalize_location_value("Udine")


@pytest.mark.parametrize(
    "input_type",
    ["text", "textarea", "single", "multi", "scale", "number", "location"],
)
def test_every_scientific_question_type_exposes_flag_and_skip(input_type: str):
    question = QuestionDefinition(
        step=f"step_{input_type}",
        field=f"field_{input_type}",
        question_id=f"question_{input_type}",
        prompt="Question",
        input_type=input_type,
    )

    assert question_interactions(question)["can_flag"] is True
    assert question_interactions(question)["can_skip"] is True


def test_explicit_structural_question_can_disable_skip_only():
    question = QuestionDefinition(
        step="consent",
        field="consent",
        question_id="structural_consent",
        prompt="Consent",
        skippable=False,
    )

    assert question_interactions(question)["can_flag"] is True
    assert question_interactions(question)["can_skip"] is False


def test_skipped_and_flagged_states_survive_checkpoint_reload():
    state: dict[str, object] = {}
    state = skip_question(state, "q1")
    state = flag_question(state, "q1", flagged=True)

    durable = InMemoryParticipationRepository()
    player = durable.create_participant(access_key="key", profile=_profile())
    participation = durable.ensure_participation(
        player_id=player["id"], session_id="prediction-debug"
    )
    durable.checkpoint(
        participation["participation_id"],
        state={"question_states": state},
        current_position="q2",
        completion_state="in_progress",
    )

    reloaded = durable.resume(
        player_id=player["id"], session_id="prediction-debug"
    )["state"]["question_states"]
    assert question_state(reloaded, "q1") == {
        "answer_state": "skipped",
        "flagged": True,
    }


def test_answered_state_is_distinct_from_unanswered_and_skipped():
    state = answer_question({}, "q1")

    assert question_state(state, "q1")["answer_state"] == "answered"
    assert question_state(state, "q2")["answer_state"] == "unanswered"


def test_prediction_test_query_resolves_debug_boundary_before_any_write():
    production = event_config_for_request("prediction", test=True)

    assert production.slug == "prediction_debug"
    assert production.session_code == "prediction_debug_2026"
    assert production.test_mode is True


def test_prediction_profile_declares_base_location_semantics():
    config = event_config_for_request("prediction")

    assert config.identity_policy.semantic_type_for("base_location") == "location"


def test_prediction_debug_session_reuses_the_prediction_question_set():
    bundle = resolve_question_set_bundle(session_code="prediction_debug_2026")

    assert bundle.event_slug == "prediction_debug"
    assert bundle.question_set_id == "prediction_v0"


def test_controls_fixture_covers_visible_generic_renderer_types():
    assert [question.input_type for question in CONTROLS_FIXTURE.questions] == [
        "text",
        "single",
        "scale",
        "text",
    ]
    assert all(
        question_interactions(question)["can_flag"] is True
        and question_interactions(question)["can_skip"] is True
        for question in CONTROLS_FIXTURE.questions
    )


def test_every_step_type_exposes_stable_flag_and_skip_capabilities():
    required_identity = step_interactions("identity")
    optional_profile = step_interactions(
        "fixture_profile", question=CONTROLS_FIXTURE.questions[0]
    )
    scientific = step_interactions(
        "fixture_single", question=CONTROLS_FIXTURE.questions[1]
    )
    review = step_interactions("review")

    assert (required_identity.can_flag, required_identity.can_skip) == (True, False)
    assert required_identity.skip_reason_disabled == (
        "At this stage, this is required to continue. If you think this is too "
        "restrictive, drop us a message."
    )
    assert (optional_profile.can_flag, optional_profile.can_skip) == (True, True)
    assert (scientific.can_flag, scientific.can_skip) == (True, True)
    assert (review.can_flag, review.can_skip) == (False, False)
    assert review.flag_reason_disabled
    assert review.skip_reason_disabled


def test_test_flow_write_paths_leave_production_storage_empty():
    config = event_config_for_request("prediction", test=True)
    repo = InMemoryParticipationRepository()
    player = repo.create_participant(access_key="debug-key", profile=_profile())
    participation = repo.ensure_participation(
        player_id=player["id"],
        session_id=config.session_code,
        test_mode=config.test_mode,
    )
    repo.checkpoint(
        participation["participation_id"],
        state={"question_states": skip_question({}, "q1")},
        current_position="review",
        completion_state="in_progress",
    )
    first = repo.submit(
        participation["participation_id"], {"q1": "Skipped"}, "submit-debug"
    )
    repo.revise(
        participation["participation_id"],
        {"q1": "Answer"},
        write_idempotency_key="revise-debug",
        supersedes_response_id=first["response_id"],
    )

    assert repo.submissions("prediction_2026", include_test=True) == []
    assert repo.resume(player_id=player["id"], session_id="prediction_2026") is None
    assert len(repo.submissions("prediction_debug_2026", include_test=True)) == 2


def test_production_and_debug_aggregates_are_mutually_isolated():
    repo = InMemoryParticipationRepository()
    player = repo.create_participant(access_key="key", profile=_profile())
    production = repo.ensure_participation(
        player_id=player["id"], session_id="prediction_2026"
    )
    debug = repo.ensure_participation(
        player_id=player["id"], session_id="prediction_debug_2026", test_mode=True
    )
    repo.submit(production["participation_id"], {"value": "production"}, "p")
    repo.submit(debug["participation_id"], {"value": "debug"}, "d")

    assert [r["answers"]["value"] for r in repo.submissions("prediction_2026")] == [
        "production"
    ]
    assert [
        r["answers"]["value"]
        for r in repo.submissions("prediction_debug_2026", include_test=True)
    ] == ["debug"]


def test_navigation_uses_current_conceptual_families():
    families = navigation_families()

    assert tuple(families) == (
        "Complexity",
        "Young",
        "Prediction",
        "D'Alembertiennes",
    )
    assert [item.title for item in families["Prediction"]] == [
        "Prediction",
    ]
    assert families["Prediction"][0].url_path == "prediction"
    assert all(item.title != "Scientific Event" for items in families.values() for item in items)


class _InteractionCapture:
    def __init__(self):
        self.calls = []
        self.read_calls = 0

    def get_responses_by_item(self, *_args):
        self.read_calls += 1
        return []

    def save_response(self, **kwargs):
        self.calls.append(kwargs)
        return {"response_id": "saved"}


def _conference_repo():
    notion = type("Notion", (), {"client": object()})()
    repo = ConferenceRepo(
        notion,
        ConferenceSettings(
            notion_token="",
            notion_version="2025-09-03",
            session_responses_db_id="responses",
            default_session_code="prediction_2026",
            debug=False,
        ),
    )
    repo._interaction_repo = _InteractionCapture()
    return repo


def test_prediction_response_writer_rejects_debug_metadata_on_production_code():
    repo = _conference_repo()
    payload = {
        "profile": {},
        "session": {
            "event_slug": "prediction_debug",
            "session_code": "prediction_2026",
            "question_set_id": "prediction_v0",
            "text_id": "prediction_v0",
            "response_scope": "debug_session",
            "event_status": "open",
            "test_mode": True,
            "data_classification": "debug",
        },
    }

    with pytest.raises(ValueError, match="prediction_wrong_event_slug"):
        repo.save_session_response_set(
            "production-id", "player", "prediction_v0", "device", "hash", "key", payload
        )
    assert repo._interaction_repo.calls == []


def test_prediction_checkpoint_writer_rejects_test_write_to_production_code():
    repo = _conference_repo()

    with pytest.raises(ValueError, match="debug session"):
        repo.save_participation_checkpoint(
            session_id="production-id",
            session_code="prediction_2026",
            player_id="player",
            text_id="prediction_v0",
            device_id="device",
            state={},
            current_position="q1",
            test_mode=True,
        )
    assert repo._interaction_repo.calls == []


def test_checkpoint_append_does_not_read_prior_checkpoints_first():
    repo = _conference_repo()

    repo.save_participation_checkpoint(
        session_id="production-id",
        session_code="prediction_2026",
        player_id="player",
        text_id="prediction_v0",
        device_id="device",
        state={"role": ["theory"]},
        current_position="systems",
        test_mode=False,
    )

    assert repo._interaction_repo.read_calls == 0
    assert len(repo._interaction_repo.calls) == 1
