from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from conference.flow import build_session_payload
from conference.registry import (
    bundle_inspector_rows,
    registry_validation_errors,
    resolve_question_set_bundle,
)
from conference.question_sets.complexity_v2 import QUESTION_SET as COMPLEXITY_V2_QUESTION_SET
from conference.question_sets.dalembertiennes_v1 import (
    QUESTION_SET as DALEMBERTIENNES_V1_QUESTION_SET,
)
from conference.question_sets.pisa_session_v2 import QUESTION_SET as PISA_SESSION_V2_QUESTION_SET
from conference.question_sets import question_by_step
from conference.question_sets.un_wg2_v1 import QUESTION_SET as UN_WG2_V1_QUESTION_SET


def test_registry_resolves_complexity_bundle():
    resolved = resolve_question_set_bundle(session_code="petnica_2026")

    assert resolved.question_set_id == "complexity_v2"
    assert resolved.text_id == "petnica_2026"
    assert resolved.question_set is COMPLEXITY_V2_QUESTION_SET


def test_registry_resolves_pisa_bundle():
    resolved = resolve_question_set_bundle(session_code="pisa-conference-session")

    assert resolved.question_set_id == "pisa_session_v2"
    assert resolved.text_id == "pisa_session_v2"
    assert resolved.question_set is PISA_SESSION_V2_QUESTION_SET


def test_registry_resolves_dalembertiennes_bundle():
    resolved = resolve_question_set_bundle(session_code="dalembertiennes_2026")

    assert resolved.question_set_id == "dalembertiennes_v1"
    assert resolved.text_id == "dalembertiennes_v1"
    assert resolved.question_set is DALEMBERTIENNES_V1_QUESTION_SET


def test_registry_resolves_un_wg2_yaml_bundle():
    resolved = resolve_question_set_bundle(session_code="un_wg2_core_2026")

    assert resolved.question_set_id == "un_wg2_v1"
    assert resolved.text_id == "un_wg2_v1"
    assert resolved.question_set is UN_WG2_V1_QUESTION_SET
    assert resolved.question_set_source_kind == "yaml"
    assert resolved.question_set_source_path.endswith("conference/question_sets/un_wg2_v1.yaml")


def test_un_wg2_removes_follow_up_and_collects_main_location():
    steps = list(UN_WG2_V1_QUESTION_SET.flow_modes["quick"]["steps"])
    question_fields = {question.field for question in UN_WG2_V1_QUESTION_SET.questions}
    question_ids = {question.question_id for question in UN_WG2_V1_QUESTION_SET.questions}

    assert "follow_up_interest" not in steps
    assert "follow_up_interest" not in question_fields
    assert "UN_WG2_FOLLOW_UP_INTEREST" not in question_ids
    assert "main_location" in steps
    assert "wg2_main_location" in question_fields
    assert "__always__" in set(UN_WG2_V1_QUESTION_SET.follow_up_contact_values)


def test_un_wg2_active_steps_all_use_question_action_row():
    for mode, payload in UN_WG2_V1_QUESTION_SET.flow_modes.items():
        for step in payload["steps"]:
            question = question_by_step(UN_WG2_V1_QUESTION_SET, step)
            assert question is not None, f"{mode} step {step} must render Continue / Flag / Skip"


def test_un_wg2_orders_conversation_and_merges_spatial_context():
    steps = list(UN_WG2_V1_QUESTION_SET.flow_modes["quick"]["steps"])

    assert steps[:7] == [
        "role_lens",
        "expertise",
        "support_needs",
        "work_style",
        "main_location",
        "region",
        "cryosphere_domain",
    ]
    assert len(steps) == 15
    assert steps.index("needs") > steps.index("cryosphere_domain")
    assert steps.index("contribution") > steps.index("stakeholder_group")


def test_un_wg2_profile_question_additions_are_active():
    steps = list(UN_WG2_V1_QUESTION_SET.flow_modes["quick"]["steps"])
    fields = {question.field for question in UN_WG2_V1_QUESTION_SET.questions}
    question_ids = {question.question_id for question in UN_WG2_V1_QUESTION_SET.questions}

    assert {"expertise", "support_needs", "work_style"}.issubset(steps)
    assert {
        "wg2_expertise",
        "wg2_support_needs",
        "wg2_work_style",
    }.issubset(fields)
    assert {
        "UN_WG2_EXPERTISE",
        "UN_WG2_SUPPORT_NEEDS",
        "UN_WG2_WORK_STYLE",
    }.issubset(question_ids)
    assert {
        "wg2_expertise",
        "wg2_support_needs",
        "wg2_work_style",
    }.issubset(set(UN_WG2_V1_QUESTION_SET.profile_fields))


def test_registry_validation_has_no_errors():
    assert registry_validation_errors() == []


def test_dalembertiennes_question_ids_are_event_safe():
    event_specific = [
        question.question_id
        for question in DALEMBERTIENNES_V1_QUESTION_SET.questions
        if question.origin != "shared"
    ]

    assert event_specific
    assert all(token.startswith("DALEMBERTIENNES_") for token in event_specific)


def test_bundle_inspector_reports_shared_and_event_specific_ids():
    rows = bundle_inspector_rows()
    dal = next(item for item in rows if item["event_slug"] == "dalembertiennes")

    assert dal["question_set_id"] == "dalembertiennes_v1"
    assert dal["shared_question_ids"]
    assert dal["event_specific_question_ids"]
    assert "DALEMBERTIENNES_LAB_QUESTION" in dal["event_specific_question_ids"]


def test_build_session_payload_uses_supplied_question_set():
    draft = {
        "mode": "standard",
        "role": ["theory"],
        "role_custom": "",
        "assets": ["software"],
        "career_stage": "phd",
        "lab_discuss_interest": "yes_definitely",
        "lab_discuss_interest_detail": "Only if it stays practical.",
        "lab_discussion_level": "open_reflection_group",
        "lab_discussion_level_detail": "",
        "lab_time_commitment": "one_off_yearly",
        "lab_time_commitment_other": "",
        "lab_professional_responsibility": "yes_partly",
        "lab_professional_responsibility_detail": "Depends on available support.",
        "lab_discussion_difficulty": ["lack_time", "lack_clear_data"],
        "lab_discussion_difficulty_detail": "",
        "follow_up_interest": "",
        "lab_question": "What should this lab ask first?",
        "boiler_room_contribution": "",
        "question_flags": {},
        "alias": "",
        "identity": "",
        "contact": "",
        "deferred_fields": [],
        "identity_reveal_targets": [],
        "access_key": "",
        "submitted": False,
    }

    payload = build_session_payload(
        draft,
        question_set=DALEMBERTIENNES_V1_QUESTION_SET,
    )

    assert payload["profile"]["role"] == ["theory"]
    assert payload["session"]["lab_discuss_interest"] == "yes_definitely"
    assert payload["session"]["lab_discuss_interest_detail"] == "Only if it stays practical."
    assert payload["session"]["lab_question"] == "What should this lab ask first?"
