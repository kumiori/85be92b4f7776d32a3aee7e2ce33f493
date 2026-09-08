from __future__ import annotations

from conference.question_sets import QuestionDefinition, QuestionSet


# Test-only fixture for visually and behaviorally verifying the shared renderer.
# It is available only on an explicitly isolated test-mode event route.
QUESTIONS = (
    QuestionDefinition(
        step="fixture_profile",
        field="fixture_profile",
        question_id="platform_fixture_profile_v1",
        prompt="Would you like to add a profile note?",
        subtitle="This optional detail is kept separate from scientific answers.",
        input_type="text",
        placeholder="Optional profile note",
        required=False,
    ),
    QuestionDefinition(
        step="fixture_single",
        field="fixture_single",
        question_id="platform_fixture_single_v1",
        prompt="Which option best matches your test?",
        input_type="single",
        options=(
            {"value": "alpha", "label": "Alpha"},
            {"value": "beta", "label": "Beta"},
        ),
        required=True,
    ),
    QuestionDefinition(
        step="fixture_scale",
        field="fixture_scale",
        question_id="platform_fixture_scale_v1",
        prompt="How strongly does this test signal resonate?",
        input_type="scale",
        required=True,
    ),
    QuestionDefinition(
        step="fixture_text",
        field="fixture_text",
        question_id="platform_fixture_text_v1",
        prompt="What should this test preserve?",
        input_type="text",
        placeholder="Short test response",
        required=True,
    ),
)


QUESTION_SET = QuestionSet(
    id="platform_controls_fixture_v1",
    version="1",
    schema_id="questionnaire_v2",
    source_module=__name__,
    step_copy={
        "identity": {
            "title": "About you",
            "body": "A few details so you can return to your answers later.",
        },
        "fixture_profile": {"title": "Optional profile", "body": ""},
        "fixture_single": {"title": "Controls test", "body": ""},
        "fixture_scale": {"title": "Controls test", "body": ""},
        "fixture_text": {"title": "Controls test", "body": ""},
        "review": {
            "title": "Review your answers",
            "body": "Check the fixture answers before sending them.",
            "cta": "Submit test responses",
        },
        "done": {
            "title": "Test responses recorded",
            "body": "Save your key if you need to inspect this test again.",
            "cta": "Finish",
        },
    },
    step_order=("fixture_profile", "fixture_single", "fixture_scale", "fixture_text"),
    flow_modes={
        "standard": {
            "title": "Controls test",
            "detail": "",
            "accent": "",
            "steps": ["fixture_profile", "fixture_single", "fixture_scale", "fixture_text"],
        }
    },
    questions=QUESTIONS,
    profile_fields=("fixture_profile",),
    session_fields=("fixture_single", "fixture_scale", "fixture_text"),
    deferrable_fields=("fixture_single", "fixture_scale", "fixture_text"),
    fingerprint_axes=(),
    fingerprint_labels={},
    follow_up_contact_values=("__always__",),
    migration_profile_fields=(),
    default_mode="standard",
    show_mode_selection=False,
    show_welcome_step=False,
    identity_position="first",
)
