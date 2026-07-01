from __future__ import annotations

from conference.pisa_legacy_models import (
    FLOW_MODES,
    FOLLOW_UP_CONTACT_VALUES,
    SESSION_QUESTIONS,
    STEP_COPY,
    STEP_ORDER,
)
from conference.question_sets import QuestionDefinition, QuestionSet


QUESTION_SET = QuestionSet(
    id="pisa_session_v2",
    source_module=__name__,
    step_copy=STEP_COPY,
    step_order=tuple(STEP_ORDER),
    flow_modes=FLOW_MODES,
    questions=tuple(
        QuestionDefinition(
            step=str(question["step"]),
            field=str(question["field"]),
            question_id=str(question["question_id"]),
            prompt=str(question["prompt"]),
            subtitle=str(question.get("subtitle") or ""),
            input_type=str(question.get("input_type") or "single"),
            options=tuple(
                {
                    "value": str(option["value"]),
                    "label": str(option["label"]),
                }
                for option in question.get("options", [])
            ),
            required=bool(question.get("required")),
            max_select=question.get("max_select"),
            placeholder=str(question.get("placeholder") or ""),
        )
        for question in SESSION_QUESTIONS
    ),
    profile_fields=(
        "role",
        "career_stage",
        "systems",
        "expectations",
        "formulation",
        "reality_check",
        "scale",
        "research_style",
        "timescale",
    ),
    session_fields=(
        "motivations",
        "obstacle",
        "challenge",
        "continue_conversation",
        "open_text",
        "question_flags",
    ),
    deferrable_fields=("open_text",),
    fingerprint_axes=(),
    fingerprint_labels={},
    follow_up_contact_values=tuple(FOLLOW_UP_CONTACT_VALUES),
    migration_profile_fields=("systems", "scale", "research_style"),
)
