from pathlib import Path

import pytest

from conference.question_sets import (
    active_questions,
    question_by_id,
    question_requires_reanswer,
    questions_requiring_reanswer,
    questionnaire_is_participant_facing,
)
from conference.question_sets.complexity_v2 import QUESTION_SET as PYTHON_COMPLEXITY
from conference.question_sets.yaml_loader import load_question_set_yaml, question_set_from_yaml
from conference.flow import build_session_payload


ROOT = Path(__file__).parents[1] / "conference" / "question_sets"


def _content_signature(question):
    return (
        question.step,
        question.field,
        question.prompt,
        question.subtitle,
        question.input_type,
        question.options,
        question.required,
        question.max_select,
        question.placeholder,
        question.origin,
    )


def test_complexity_yaml_is_content_equivalent_to_python_oracle():
    migrated = load_question_set_yaml(
        ROOT / "complexity.yaml", source_module="conference.question_sets.complexity"
    )

    assert migrated.id == "complexity"
    assert migrated.revision == 2
    assert migrated.status == "active"
    assert migrated.step_order == PYTHON_COMPLEXITY.step_order
    assert migrated.step_copy == PYTHON_COMPLEXITY.step_copy
    assert migrated.flow_modes == PYTHON_COMPLEXITY.flow_modes
    assert migrated.profile_fields == PYTHON_COMPLEXITY.profile_fields
    assert migrated.session_fields == PYTHON_COMPLEXITY.session_fields
    assert migrated.deferrable_fields == PYTHON_COMPLEXITY.deferrable_fields
    assert migrated.fingerprint_axes == PYTHON_COMPLEXITY.fingerprint_axes
    assert migrated.fingerprint_labels == PYTHON_COMPLEXITY.fingerprint_labels
    assert migrated.follow_up_contact_values == PYTHON_COMPLEXITY.follow_up_contact_values
    assert migrated.migration_profile_fields == PYTHON_COMPLEXITY.migration_profile_fields
    assert [_content_signature(q) for q in migrated.questions] == [
        _content_signature(q) for q in PYTHON_COMPLEXITY.questions
    ]


def test_shared_reference_keeps_semantics_and_allows_presentation_override():
    migrated = load_question_set_yaml(
        ROOT / "complexity.yaml", source_module="conference.question_sets.complexity"
    )
    role = migrated.questions[0]

    assert role.question_id == "role"
    assert role.origin == "shared"
    assert role.shared_dimension == "scientific_role"
    assert role.prompt == "What is your perspective?"
    assert role.legacy_ids == ("COMPLEXITY_ROLE",)
    assert question_by_id(migrated, "COMPLEXITY_ROLE") is role


def test_shared_option_override_requires_an_explicit_reason(tmp_path):
    path = tmp_path / "invalid.yaml"
    path.write_text(
        """questionnaire: {id: invalid, revision: 1}\nquestions:\n  - use: shared.role\n    options:\n      - {value: invented, label: Invented}\n""",
        encoding="utf-8",
    )
    with pytest.raises(ValueError, match="override_reason"):
        load_question_set_yaml(
            path,
            source_module="tests.invalid",
        )


def test_question_revision_controls_reask_without_erasing_previous_revision():
    base = {
        "step": "power",
        "field": "predictive_power",
        "id": "predictive_power",
        "prompt": "Where does predictive power come from?",
        "input_type": "text",
    }
    previous = question_set_from_yaml(
        {"questionnaire": {"id": "prediction", "revision": 1}, "questions": [{**base, "revision": 1}]},
        source_module="tests.previous",
    ).questions[0]
    current = question_set_from_yaml(
        {
            "questionnaire": {"id": "prediction", "revision": 2},
            "questions": [{
                **base,
                "revision": 2,
                "supersedes_revision": 1,
                "change": {
                    "type": "options_changed",
                    "reason": "Evidence categories changed.",
                    "reask_if_answered": True,
                    "preserve_previous_response": True,
                },
            }],
        },
        source_module="tests.current",
    ).questions[0]

    assert question_requires_reanswer(previous, current) is True
    assert current.revision.preserve_previous_response is True

    retained = question_set_from_yaml(
        {
            "questionnaire": {"id": "prediction", "revision": 2},
            "questions": [{
                **base,
                "revision": 2,
                "supersedes_revision": 1,
                "change": {"type": "copy_only", "reask_if_answered": False},
            }],
        },
        source_module="tests.retained",
    ).questions[0]
    assert question_requires_reanswer(previous, retained) is False
    current_set = question_set_from_yaml(
        {
            "questionnaire": {"id": "prediction", "revision": 2},
            "questions": [{
                **base,
                "revision": 2,
                "supersedes_revision": 1,
                "change": {"type": "semantic_change", "reask_if_answered": True},
            }],
        },
        source_module="tests.resume",
    )
    assert [q.question_id for q in questions_requiring_reanswer(
        current_set,
        {"predictive_power": {"question_id": "predictive_power", "question_revision": 1}},
    )] == ["predictive_power"]


def test_retired_question_is_historical_but_not_active():
    question_set = question_set_from_yaml(
        {
            "questionnaire": {"id": "example", "revision": 2},
            "questions": [
                {"id": "current", "step": "current", "field": "current", "prompt": "Current"},
                {"id": "old", "revision": 1, "status": "retired", "step": "old", "field": "old", "prompt": "Old"},
            ],
        },
        source_module="tests.retired",
    )

    assert [q.question_id for q in active_questions(question_set)] == ["current"]
    assert question_by_id(question_set, "old").status == "retired"


def test_questionnaire_lifecycle_is_independent_from_revision():
    review = load_question_set_yaml(
        ROOT / "prediction.yaml", source_module="conference.question_sets.prediction"
    )
    active = question_set_from_yaml(
        {"questionnaire": {"id": "prediction", "revision": 1, "status": "active"}},
        source_module="tests.active",
    )

    assert review.revision == active.revision == 1
    assert questionnaire_is_participant_facing(review) is False
    assert questionnaire_is_participant_facing(active) is True
    assert review.questions == ()
    assert review.legacy_questionnaire_ids == ("prediction_v0",)


def test_new_response_payload_carries_clean_and_exact_revision_provenance():
    questionnaire = load_question_set_yaml(
        ROOT / "complexity.yaml", source_module="conference.question_sets.complexity"
    )
    payload = build_session_payload(
        {"mode": "quick", "role": ["theory"]}, question_set=questionnaire
    )
    session = payload["session"]

    assert session["questionnaire_id"] == "complexity"
    assert session["questionnaire_revision"] == 2
    assert session["questionnaire_format"] == 2
    assert session["question_provenance"]["role"] == {
        "question_id": "role",
        "question_revision": 1,
        "status": "active",
        "shared_dimension": "scientific_role",
    }
    # Compatibility aliases remain readable during migration.
    assert session["question_set_id"] == "complexity"
    assert session["questionnaire_version"] == "2"
