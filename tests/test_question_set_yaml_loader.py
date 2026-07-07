from conference.question_sets import validate_question_set
from conference.question_sets.yaml_loader import question_set_from_yaml


def test_question_set_from_yaml_builds_runtime_question_set():
    question_set = question_set_from_yaml(
        {
            "question_set": {
                "id": "example_v1",
                "default_mode": "quick",
                "show_mode_selection": False,
                "show_welcome_step": False,
            },
            "step_order": ["welcome", "needs", "done"],
            "flow_modes": {
                "quick": {
                    "title": "Quick",
                    "detail": "2 minutes",
                    "accent": "*",
                    "steps": ["needs"],
                }
            },
            "step_copy": {
                "welcome": {"title": "Welcome", "body": "Start", "cta": "Start"},
                "needs": {"title": "Needs", "body": "Tell us", "cta": "Continue"},
                "done": {"title": "Done", "body": "Thanks", "cta": "Start again"},
            },
            "questions": [
                {
                    "step": "needs",
                    "field": "wg2_needs",
                    "question_id": "EXAMPLE_NEEDS",
                    "prompt": "What do you need?",
                    "context": "One useful signal.",
                    "input_type": "multi",
                    "options": [
                        {"value": "data", "label": "Data"},
                        {"value": "policy_interface", "label": "Policy interface"},
                    ],
                    "required": True,
                    "max_select": 2,
                    "group": "coordination",
                    "subgroup": "needs",
                    "free_text": {
                        "field": "wg2_needs_detail",
                        "label": "Add a detail",
                        "placeholder": "One sentence",
                    },
                }
            ],
            "profile_fields": [],
            "session_fields": ["wg2_needs", "wg2_needs_detail"],
            "deferrable_fields": ["wg2_needs_detail"],
            "fingerprint_axes": [],
            "fingerprint_labels": {},
            "follow_up_contact_values": ["yes", "maybe"],
            "migration_profile_fields": [],
        },
        source_module="tests.example",
    )

    assert question_set.id == "example_v1"
    assert question_set.default_mode == "quick"
    assert question_set.show_mode_selection is False
    assert question_set.show_welcome_step is False
    assert validate_question_set(question_set) == []
    assert question_set.questions[0].question_id == "EXAMPLE_NEEDS"
    assert question_set.questions[0].free_text_field == "wg2_needs_detail"
