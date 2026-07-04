from __future__ import annotations

from typing import Any, Dict

from conference.question_sets import QuestionDefinition, QuestionSet, merge_questions
from conference.question_sets.shared import follow_up_interest_question


STEP_ORDER = (
    "welcome",
    "participant_context",
    "coordination",
    "open_reflection",
    "follow_up_interest",
    "identity",
    "review",
    "done",
)

FLOW_MODES: Dict[str, Dict[str, Any]] = {
    "quick": {
        "title": "Icebreaker",
        "detail": "~ 5 minutes · first coordination layer",
        "accent": "🧭",
        "steps": [
            "participant_context",
            "coordination",
            "open_reflection",
            "follow_up_interest",
        ],
    },
}

STEP_COPY = {
    "welcome": {
        "title": "Working Group 2 — First Iteration",
        "body": "Actionable Cryosphere Projections",
        "note": (
            "This pilot is the first coordination layer of WG2. "
            "The aim is to make the group visible to itself before broader coordination begins."
        ),
        "cta": "Start the WG2 icebreaker",
    },
    "participant_context": {
        "title": "Participant context",
        "body": "First we situate who is speaking in or around WG2.",
        "cta": "Continue",
    },
    "coordination": {
        "title": "First coordination signal",
        "body": (
            "This is the first smoke-test question for the WG2 coordination route. "
            "It proves that a route-specific answer can be written, read back, and kept isolated."
        ),
        "cta": "Continue",
    },
    "open_reflection": {
        "title": "Open reflection",
        "body": "Where would coordination create immediate value for you?",
        "cta": "Continue",
    },
    "follow_up_interest": {
        "title": "Stay in touch?",
        "body": "Would you like to remain reachable as this coordination layer evolves?",
        "cta": "Continue",
    },
    "identity": {
        "title": "Name, affiliation, email",
        "body": "Optional. Leave a name, affiliation, email, or remain anonymous for now.",
        "cta": "Continue",
    },
    "review": {
        "title": "Review before integrating",
        "body": (
            "This pilot belongs only to the first WG2 icebreaker session. "
            "Profile information may later be reused only if WG2 explicitly opts into it."
        ),
        "cta": "Integrate",
    },
    "done": {
        "title": "Thank you.",
        "body": (
            "This first route is intentionally small. Its role is to make a first coordination "
            "signal visible before the broader WG2 platform expands."
        ),
        "cta": "Start again",
    },
}

QUESTION_SET = QuestionSet(
    id="un_wg2_v1",
    source_module=__name__,
    step_copy=STEP_COPY,
    step_order=STEP_ORDER,
    flow_modes=FLOW_MODES,
    questions=merge_questions(
        (
            QuestionDefinition(
                step="participant_context",
                field="role_in_decade",
                question_id="UN_WG2_ROLE_IN_DECADE",
                prompt="What is your role in or around WG2 at this stage?",
                subtitle=(
                    "This is a lightweight positioning question for the pilot, not a formal title or hierarchy."
                ),
                input_type="single",
                options=(
                    {"value": "core_leadership", "label": "Core WG2 leadership"},
                    {"value": "contributing_scientist", "label": "Contributing scientist"},
                    {"value": "partner_institution", "label": "Partner institution"},
                    {"value": "coordination_support", "label": "Coordination support"},
                    {"value": "observer", "label": "Observer / invited participant"},
                    {"value": "other", "label": "Other"},
                ),
                required=False,
                origin="shared",
                free_text_field="role_in_decade_detail",
                free_text_label="If other, specify",
                free_text_placeholder="Your role in a few words",
            ),
        ),
        (
            QuestionDefinition(
                step="coordination",
                field="wg2_coordination_signal",
                question_id="UN_WG2_COORDINATION_SIGNAL",
                prompt="What should WG2 make more visible or better coordinated first?",
                subtitle=(
                    "This is the first mock coordination signal for the route. "
                    "It is here to prove identity, write scope, and readback."
                ),
                input_type="text",
                required=False,
                placeholder="One first coordination signal for WG2",
                group="coordination",
                subgroup="smoke_test",
            ),
            QuestionDefinition(
                step="open_reflection",
                field="collaboration_preferences",
                question_id="UN_WG2_COLLABORATION_PREFERENCES",
                prompt="Where would coordination create immediate value for you?",
                subtitle=(
                    "You can mention collaborations, missing links, shared needs, or one place where WG2 could reduce friction."
                ),
                input_type="text",
                required=False,
                placeholder="One area where coordination would help right now",
                group="coordination",
                subgroup="open_reflection",
            ),
            follow_up_interest_question(
                "UN_WG2_FOLLOW_UP_INTEREST",
                prompt=STEP_COPY["follow_up_interest"]["title"],
                subtitle=STEP_COPY["follow_up_interest"]["body"],
            ),
        ),
    ),
    profile_fields=(
        "role_in_decade",
    ),
    session_fields=(
        "wg2_coordination_signal",
        "collaboration_preferences",
        "follow_up_interest",
        "boiler_room_contribution",
        "question_flags",
        "identity_reveal_targets",
    ),
    deferrable_fields=(
        "wg2_coordination_signal",
        "collaboration_preferences",
    ),
    fingerprint_axes=(),
    fingerprint_labels={},
    follow_up_contact_values=("yes", "maybe"),
    migration_profile_fields=("role_in_decade",),
    default_mode="quick",
    show_mode_selection=False,
)
