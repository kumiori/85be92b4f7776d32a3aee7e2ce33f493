from copy import deepcopy
from pathlib import Path

from conference.question_sets import (
    QuestionDefinition,
    QuestionRevision,
    QuestionSet,
    question_by_id,
)
from conference.question_sets.yaml_loader import load_question_set_yaml, question_set_from_yaml
from conference.flow import build_session_payload
from conference.registry import resolve_question_set_bundle
from conference.repo import ConferenceRepo
from conference.wg2_schema import build_refinement_bundle, compare_response_bundle_to_schema


ROOT = Path(__file__).resolve().parents[1]


def _question_set(*questions: QuestionDefinition, legacy=()) -> QuestionSet:
    steps = tuple(question.step for question in questions)
    return QuestionSet(
        id="un_wg2_v1",
        source_module=__name__,
        step_copy={},
        step_order=steps,
        flow_modes={"quick": {"title": "Quick", "detail": "", "accent": "", "steps": list(steps)}},
        questions=questions,
        profile_fields=tuple(question.field for question in questions),
        session_fields=(),
        deferrable_fields=(),
        fingerprint_axes=(),
        fingerprint_labels={},
        follow_up_contact_values=(),
        migration_profile_fields=(),
        version="2",
        schema_id="questionnaire_v2",
        legacy_questions=legacy,
    )


def _old_role() -> QuestionDefinition:
    return QuestionDefinition(
        step="role_lens",
        field="wg2_role_lens",
        question_id="UN_WG2_ROLE_LENS",
        prompt="What is your main role or lens in WG2?",
        input_type="multi",
        options=({"value": "core_wg2_leadership", "label": "Core WG2 leadership"},),
    )


def _revised_role(*, change_type="split", reask=True) -> QuestionDefinition:
    return QuestionDefinition(
        step="role_lens",
        field="wg2_role_lens",
        question_id="UN_WG2_ROLE_LENS_V2",
        prompt="What is your main role or lens in WG2?",
        input_type="multi",
        options=(
            {"value": "core_group", "label": "Core WG2 group"},
            {"value": "leadership", "label": "WG2 leadership"},
        ),
        revision=QuestionRevision(
            supersedes="UN_WG2_ROLE_LENS",
            change_type=change_type,
            reason="Core group and leadership were previously conflated.",
            reask_if_answered=reask,
            preserve_previous_response=True,
        ),
    )


def _old_bundle() -> dict:
    return {
        "schema_version": "2",
        "profile": {"wg2_role_lens": ["core_wg2_leadership"]},
        "session": {
            "session_code": "un_wg2_core_2026",
            "text_id": "un_wg2_v1",
            "question_set_id": "un_wg2_v1",
            "schema_id": "questionnaire_v1",
        },
    }


def test_yaml_revision_contract_is_optional_and_round_trips():
    qset = question_set_from_yaml(
        {
            "question_set": {"id": "test", "version": "2", "schema_id": "questionnaire_v2"},
            "step_order": ["role"],
            "flow_modes": {"quick": {"title": "Quick", "detail": "", "accent": "", "steps": ["role"]}},
            "questions": [
                {
                    "step": "role",
                    "field": "role",
                    "question_id": "ROLE_V2",
                    "prompt": "Role?",
                    "revision": {
                        "supersedes": "ROLE_V1",
                        "change_type": "split",
                        "reason": "One option became two.",
                        "reask_if_answered": True,
                        "preserve_previous_response": True,
                    },
                }
            ],
        },
        source_module="test",
    )

    question = qset.questions[0]
    assert qset.version == "2"
    assert qset.schema_id == "questionnaire_v2"
    assert question.revision is not None
    assert question.revision.supersedes == "ROLE_V1"
    assert question.as_dict()["revision"]["change_type"] == "split"


def test_current_wg2_schema_preserves_old_role_and_activates_v2():
    qset = load_question_set_yaml(
        ROOT / "conference" / "question_sets" / "un_wg2_v1.yaml",
        source_module="conference.question_sets.un_wg2_v1",
    )

    old_question = question_by_id(qset, "UN_WG2_ROLE_LENS", include_legacy=True)
    current_question = question_by_id(qset, "UN_WG2_ROLE_LENS_V2")

    assert old_question is not None
    assert old_question.options[0] == {
        "value": "core_wg2_leadership",
        "label": "Core WG2 leadership",
    }
    assert current_question is not None
    assert {option["value"] for option in current_question.options} >= {
        "core_group",
        "leadership",
    }
    assert question_by_id(qset, "UN_WG2_ROLE_LENS") is None
    resolved = resolve_question_set_bundle(session_code="un_wg2_core_2026")
    assert resolved.schema_id == "questionnaire_v2"


def test_new_wg2_payload_records_questionnaire_schema_version():
    qset = load_question_set_yaml(
        ROOT / "conference" / "question_sets" / "un_wg2_v1.yaml",
        source_module="conference.question_sets.un_wg2_v1",
    )

    payload = build_session_payload(
        {"mode": "quick", "wg2_role_lens": ["leadership"]},
        question_set=qset,
    )

    assert payload["session"]["question_set_id"] == "un_wg2_v1"
    assert payload["session"]["schema_id"] == "questionnaire_v2"
    assert payload["session"]["questionnaire_version"] == "2"


def test_split_answer_requires_refinement_without_mutating_old_bundle():
    old = _old_role()
    current = _question_set(_revised_role(), legacy=(old,))
    bundle = _old_bundle()
    before = deepcopy(bundle)

    alignment = compare_response_bundle_to_schema(
        player_id="player-1",
        response_bundle=bundle,
        previous_response_id="response-v1",
        current_schema=current,
    )

    assert bundle == before
    assert alignment["current"] == []
    assert len(alignment["needs_refinement"]) == 1
    item = alignment["needs_refinement"][0]
    assert item["previous_question_id"] == "UN_WG2_ROLE_LENS"
    assert item["previous_answer"] == ["core_wg2_leadership"]
    assert item["previous_answer_label"] == "Core WG2 leadership"
    assert item["reason"] == "Core group and leadership were previously conflated."


def test_copy_only_revision_does_not_require_refinement():
    current = _question_set(
        _revised_role(change_type="copy_only", reask=False),
        legacy=(_old_role(),),
    )

    alignment = compare_response_bundle_to_schema(
        player_id="player-1",
        response_bundle=_old_bundle(),
        current_schema=current,
    )

    assert alignment["needs_refinement"] == []
    assert [item["question_id"] for item in alignment["current"]] == [
        "UN_WG2_ROLE_LENS_V2"
    ]


def test_native_current_schema_answer_is_not_marked_for_refinement():
    current = _question_set(_revised_role(), legacy=(_old_role(),))
    bundle = {
        "profile": {"wg2_role_lens": ["leadership"]},
        "session": {
            "schema_id": "questionnaire_v2",
            "questionnaire_version": "2",
        },
    }

    alignment = compare_response_bundle_to_schema(
        player_id="player-v2",
        response_bundle=bundle,
        current_schema=current,
    )

    assert alignment["needs_refinement"] == []
    assert [item["question_id"] for item in alignment["current"]] == [
        "UN_WG2_ROLE_LENS_V2"
    ]


def test_new_participant_schema_contains_only_current_role_question():
    current = _question_set(_revised_role(), legacy=(_old_role(),))

    assert [question.question_id for question in current.questions] == [
        "UN_WG2_ROLE_LENS_V2"
    ]
    assert [question.question_id for question in current.legacy_questions] == [
        "UN_WG2_ROLE_LENS"
    ]


def test_refinement_bundle_appends_provenance_and_leaves_old_response_unchanged():
    old = _old_role()
    current = _question_set(_revised_role(), legacy=(old,))
    original = _old_bundle()
    before = deepcopy(original)

    refined = build_refinement_bundle(
        previous_bundle=original,
        question=current.questions[0],
        current_schema=current,
        answer=["leadership"],
        previous_response_id="response-v1",
        refined_at="2026-09-05T10:00:00+00:00",
    )

    assert original == before
    assert refined["profile"]["wg2_role_lens"] == ["leadership"]
    assert refined["session"]["schema_id"] == "questionnaire_v2"
    assert refined["session"]["questionnaire_version"] == "2"
    provenance = refined["session"]["response_refinements"][0]
    assert provenance["question_id"] == "UN_WG2_ROLE_LENS_V2"
    assert provenance["supersedes"] == "UN_WG2_ROLE_LENS"
    assert provenance["previous_response_id"] == "response-v1"
    assert provenance["previous_answer"] == ["core_wg2_leadership"]
    assert provenance["answer"] == ["leadership"]


def test_refinement_provenance_survives_response_grouping():
    current = _question_set(_revised_role(), legacy=(_old_role(),))
    refined = build_refinement_bundle(
        previous_bundle=_old_bundle(),
        question=current.questions[0],
        current_schema=current,
        answer=["core_group"],
        previous_response_id="response-v1",
        refined_at="2026-09-05T10:00:00+00:00",
    )
    repo = ConferenceRepo.__new__(ConferenceRepo)

    grouped = repo.group_rows_by_submission(
        [
            {
                "id": "response-v2",
                "response_id": "response-v2",
                "player_id": "player-1",
                "session_id": "session-wg2",
                "text_id": "un_wg2_v1",
                "timestamp": "2026-09-05T10:00:00+00:00",
                "value_json": {
                    "field": "session_bundle",
                    "bundle": refined,
                    "access_key_hash": "hash-1",
                },
            }
        ]
    )

    assert grouped[0]["response_id"] == "response-v2"
    assert grouped[0]["player_id"] == "player-1"
    assert grouped[0]["schema_id"] == "questionnaire_v2"
    assert grouped[0]["questionnaire_version"] == "2"
    assert grouped[0]["response_refinements"][0]["previous_response_id"] == "response-v1"
