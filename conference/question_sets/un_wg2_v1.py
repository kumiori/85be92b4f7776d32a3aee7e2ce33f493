from __future__ import annotations

from pathlib import Path
from typing import Any, Dict

from conference.question_sets import QuestionDefinition, QuestionSet, merge_questions
from conference.question_sets.shared import follow_up_interest_question
from conference.question_sets.yaml_loader import load_question_set_yaml


STEP_ORDER = (
    "welcome",
    "participant_context",
    "participant_geography",
    "contribution_lens",
    "coordination_resonance",
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
            "participant_geography",
            "contribution_lens",
            "coordination_resonance",
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
            "WG2 needs a first coordination layer to make needs, roles, missing links, "
            "and projection-use contexts visible before the wider rollout."
        ),
        "cta": "Start the WG2 icebreaker",
    },
    "participant_context": {
        "title": "Participant context",
        "body": "First we situate who is speaking in or around WG2.",
        "context": (
            "Different roles see different constraints, interfaces, and points of leverage."
        ),
        "cta": "Continue",
    },
    "participant_geography": {
        "title": "Where are you mainly based?",
        "body": (
            "WG2 spans places, institutions, and regional situations. "
            "A lightweight location signal helps make these contexts visible."
        ),
        "context": (
            "Share only what you want to make explicit. Do not provide precise coordinates unless "
            "you choose to add them manually."
        ),
        "cta": "Continue",
    },
    "contribution_lens": {
        "title": "What can you bring to WG2 at this stage?",
        "body": (
            "This is not a formal mandate. It is a first signal about where you could be useful "
            "in the coordination layer."
        ),
        "context": "You may select more than one contribution lens.",
        "cta": "Continue",
    },
    "coordination_resonance": {
        "title": "A first resonance check",
        "body": (
            "This asks whether the core difficulty already feels like a coordination and interface "
            "problem, not only a resource problem."
        ),
        "cta": "Continue",
    },
    "coordination": {
        "title": "First coordination signal",
        "body": (
            "What should become more visible, better connected, or easier to act on first?"
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
            "This first coordination layer belongs only to the current WG2 session. "
            "Profile information is reused only where WG2 has explicitly opted into it."
        ),
        "cta": "Submit this first WG2 coordination layer",
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

_PYTHON_FALLBACK_QUESTION_SET = QuestionSet(
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
            QuestionDefinition(
                step="participant_geography",
                field="wg2_geography_context",
                question_id="UN_WG2_GEOGRAPHY_CONTEXT",
                prompt="Where are you mainly based?",
                subtitle=(
                    "You can give a country or region, an institutional location, and, only if you wish, approximate coordinates."
                ),
                input_type="geography_context",
                required=False,
                group="participant_context",
                subgroup="geography",
            ),
            QuestionDefinition(
                step="contribution_lens",
                field="wg2_contribution_lens",
                question_id="UN_WG2_CONTRIBUTION_LENS",
                prompt="What can you bring to WG2 at this stage?",
                subtitle=(
                    "This can be scientific, practical, institutional, communicative, or coordination-oriented."
                ),
                input_type="multi",
                options=(
                    {"value": "cryosphere_observations", "label": "Cryosphere observations"},
                    {"value": "climate_modelling", "label": "Climate modelling"},
                    {"value": "regional_knowledge", "label": "Regional knowledge"},
                    {"value": "risk_translation", "label": "Risk translation"},
                    {"value": "stakeholder_engagement", "label": "Stakeholder engagement"},
                    {"value": "data_infrastructure", "label": "Data infrastructure"},
                    {"value": "uncertainty_communication", "label": "Uncertainty communication"},
                    {"value": "policy_interface", "label": "Policy interface"},
                    {"value": "visualisation_mapping", "label": "Visualisation / mapping"},
                    {"value": "facilitation_coordination", "label": "Facilitation / coordination"},
                    {"value": "other", "label": "Other"},
                ),
                required=False,
                group="participant_context",
                subgroup="contribution",
                free_text_field="wg2_contribution_lens_detail",
                free_text_label="If other, specify",
                free_text_placeholder="Another contribution lens",
            ),
            QuestionDefinition(
                step="coordination_resonance",
                field="wg2_coordination_resonance",
                question_id="UN_WG2_COORDINATION_RESONANCE",
                prompt=(
                    "The main bottleneck is not only lack of resources, but lack of visibility, "
                    "coordination, and smooth interfaces between people, data, and decisions."
                ),
                subtitle="How strongly does this resonate with your view?",
                input_type="scale",
                options=(
                    {"value": "-5", "label": "-5 · Dissonates"},
                    {"value": "-4", "label": "-4"},
                    {"value": "-3", "label": "-3"},
                    {"value": "-2", "label": "-2"},
                    {"value": "-1", "label": "-1"},
                    {"value": "0", "label": "0 · Neutral"},
                    {"value": "1", "label": "1"},
                    {"value": "2", "label": "2"},
                    {"value": "3", "label": "3"},
                    {"value": "4", "label": "4"},
                    {"value": "5", "label": "5 · Strongly resonates"},
                ),
                required=False,
                group="coordination",
                subgroup="resonance",
                free_text_field="wg2_coordination_resonance_comment",
                free_text_label="Optional comment",
                free_text_placeholder="A short note if you want to qualify your score",
            ),
        ),
        (
            QuestionDefinition(
                step="coordination",
                field="wg2_coordination_signal",
                question_id="UN_WG2_COORDINATION_SIGNAL",
                prompt="What should WG2 make more visible or better coordinated first?",
                subtitle=(
                    "You can point to a need, an interface, a missing link, or one place where better coordination would unlock value."
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
        "wg2_geography_context",
        "wg2_contribution_lens",
        "wg2_contribution_lens_detail",
        "wg2_coordination_resonance",
        "wg2_coordination_resonance_comment",
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
    show_welcome_step=False,
    source_kind="python_fallback",
    source_path=str(Path(__file__).resolve()),
)


_YAML_SPEC_CANDIDATES = (
    Path(__file__).with_suffix(".yaml"),
    Path(__file__).with_name("specs") / "un_wg2_v1.yaml",
)


def _load_question_set() -> QuestionSet:
    for candidate in _YAML_SPEC_CANDIDATES:
        if candidate.exists():
            return load_question_set_yaml(candidate, source_module=__name__)
    checked = ", ".join(str(path) for path in _YAML_SPEC_CANDIDATES)
    return QuestionSet(
        **{
            **_PYTHON_FALLBACK_QUESTION_SET.__dict__,
            "source_note": f"YAML spec not found. Checked: {checked}",
        }
    )


QUESTION_SET = _load_question_set()
