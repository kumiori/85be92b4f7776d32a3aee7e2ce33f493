from __future__ import annotations

from typing import Any, Dict

from conference.question_sets import QuestionDefinition, QuestionSet, merge_questions
from conference.question_sets.shared import (
    assets_question,
    career_stage_question,
    collaboration_style_question,
    role_question,
    scale_question,
    scientific_home_question,
)


STEP_ORDER = (
    "welcome",
    "role",
    "career_stage",
    "scientific_home",
    "scale",
    "collaboration_style",
    "assets",
    "motivations",
    "obstacle",
    "challenge",
    "follow_up_interest",
    "open_question",
    "identity",
    "review",
    "done",
)

FLOW_MODES: Dict[str, Dict[str, Any]] = {
    "quick": {
        "title": "Quick pulse",
        "detail": "~ 3 minutes · first lab checkpoint",
        "accent": "📐",
        "steps": [
            "role",
            "assets",
            "motivations",
            "open_question",
        ],
    },
    "standard": {
        "title": "Standard",
        "detail": "~ 5 minutes · profile + lab session",
        "accent": "🔷",
        "steps": [
            "role",
            "scientific_home",
            "scale",
            "assets",
            "motivations",
            "obstacle",
            "challenge",
            "open_question",
        ],
    },
    "deep": {
        "title": "Deep dive",
        "detail": "~ 7 minutes · fuller lab profile",
        "accent": "🧭",
        "steps": [
            "role",
            "career_stage",
            "scientific_home",
            "scale",
            "collaboration_style",
            "assets",
            "motivations",
            "obstacle",
            "challenge",
            "follow_up_interest",
            "open_question",
        ],
    },
}

STEP_COPY = {
    "welcome": {
        "title": "D'Alembertiennes",
        "body": "A lab questionnaire for tracing positions, frictions, and possible collaborations within the D'Alembert context.",
        "note": "Anonymous first. Shared profile questions help situate you; lab-session questions remain scoped to this event.",
    },
    "role": {
        "title": "What perspective do you bring into this lab context?",
        "body": "Choose the perspectives you genuinely inhabit here.",
        "cta": "Continue",
    },
    "career_stage": {
        "title": "Career stage",
        "body": "Scientific trajectories start from different distances and tempos.",
        "cta": "Continue",
    },
    "scientific_home": {
        "title": "What is your scientific home?",
        "body": "Place and institution still shape how laboratory conversations unfold.",
        "cta": "Continue",
    },
    "scale": {
        "title": "What computational or analytical scale feels natural here?",
        "body": "Some problems stay light; others need sustained compute or long conceptual work.",
        "cta": "Continue",
    },
    "collaboration_style": {
        "title": "How do you collaborate most naturally?",
        "body": "Laboratory work has a social geometry too.",
        "cta": "Continue",
    },
    "assets": {
        "title": "What can you realistically bring into the room?",
        "body": "Choose up to three assets you would actually contribute.",
        "cta": "Continue",
    },
    "motivations": {
        "title": "Why are you here, in this lab context?",
        "body": "Choose up to three active motivations for this event.",
        "cta": "Continue",
    },
    "obstacle": {
        "title": "What blocks progress most in this lab context?",
        "body": "Choose up to two obstacles that feel structurally real for you right now.",
        "cta": "Continue",
    },
    "challenge": {
        "title": "What challenge would you join here?",
        "body": "If enough people converged, where would you put your attention in this lab setting?",
        "cta": "Continue",
    },
    "follow_up_interest": {
        "title": "Would you like to continue after the event?",
        "body": "Only about whether you want follow-up contact from this lab line.",
        "cta": "Continue",
    },
    "open_question": {
        "title": "What is one question this event should surface?",
        "body": "A question, paradox, friction, or opening worth making explicit.",
        "cta": "Continue",
    },
    "identity": {
        "title": "Alias or identity",
        "body": "Optional. Leave a name, affiliation, email, website, or remain anonymous.",
        "cta": "Continue",
    },
    "review": {
        "title": "Review before integrating",
        "body": "Profile answers travel gently; lab-session answers belong only to Dalembertiennes.",
        "cta": "Integrate",
    },
    "done": {
        "title": "Lab signal stored",
        "body": "Keep your key. It lets you reconnect later to this D'Alembertiennes line.",
        "cta": "Start again",
    },
}

QUESTION_SET = QuestionSet(
    id="dalembertiennes_v0",
    source_module=__name__,
    step_copy=STEP_COPY,
    step_order=STEP_ORDER,
    flow_modes=FLOW_MODES,
    questions=merge_questions(
        (
            role_question(
                "DALEMBERTIENNES_ROLE",
                prompt=STEP_COPY["role"]["title"],
                subtitle=STEP_COPY["role"]["body"],
            ),
            career_stage_question(
                "DALEMBERTIENNES_CAREER_STAGE",
                prompt=STEP_COPY["career_stage"]["title"],
                subtitle=STEP_COPY["career_stage"]["body"],
            ),
            scientific_home_question(
                "DALEMBERTIENNES_SCIENTIFIC_HOME",
                prompt=STEP_COPY["scientific_home"]["title"],
                subtitle=STEP_COPY["scientific_home"]["body"],
            ),
            scale_question(
                "DALEMBERTIENNES_SCALE",
                prompt=STEP_COPY["scale"]["title"],
                subtitle=STEP_COPY["scale"]["body"],
            ),
            collaboration_style_question(
                "DALEMBERTIENNES_COLLABORATION_STYLE",
                prompt=STEP_COPY["collaboration_style"]["title"],
                subtitle=STEP_COPY["collaboration_style"]["body"],
            ),
            assets_question(
                "DALEMBERTIENNES_ASSETS",
                prompt=STEP_COPY["assets"]["title"],
                subtitle=STEP_COPY["assets"]["body"],
            ),
        ),
        (
            QuestionDefinition(
                step="motivations",
                field="motivations",
                question_id="DALEMBERTIENNES_MOTIVATIONS",
                prompt=STEP_COPY["motivations"]["title"],
                subtitle=STEP_COPY["motivations"]["body"],
                input_type="multi",
                max_select=3,
                options=(
                    {"value": "theory_exchange", "label": "Theory exchange"},
                    {"value": "method_discussion", "label": "Methodological discussion"},
                    {"value": "collaboration", "label": "Potential collaboration"},
                    {"value": "lab_orientation", "label": "Orientation within the lab"},
                    {"value": "shared_language", "label": "Finding a shared language"},
                    {"value": "question_framing", "label": "Clarifying the right question"},
                ),
                required=True,
            ),
            QuestionDefinition(
                step="obstacle",
                field="obstacle",
                question_id="DALEMBERTIENNES_OBSTACLE",
                prompt=STEP_COPY["obstacle"]["title"],
                subtitle=STEP_COPY["obstacle"]["body"],
                input_type="multi",
                max_select=2,
                options=(
                    {"value": "time", "label": "Time"},
                    {"value": "coordination", "label": "Coordination"},
                    {"value": "funding", "label": "Funding"},
                    {"value": "shared_language", "label": "Shared language"},
                    {"value": "data", "label": "Data / evidence"},
                    {"value": "method_alignment", "label": "Method alignment"},
                ),
                required=True,
            ),
            QuestionDefinition(
                step="challenge",
                field="challenge",
                question_id="DALEMBERTIENNES_CHALLENGE",
                prompt=STEP_COPY["challenge"]["title"],
                subtitle=STEP_COPY["challenge"]["body"],
                input_type="single",
                options=(
                    {"value": "working_group", "label": "Working group"},
                    {"value": "shared_methods", "label": "Shared methods discussion"},
                    {"value": "shared_data", "label": "Shared data or evidence framing"},
                    {"value": "joint_note", "label": "Joint note or synthesis"},
                    {"value": "future_meeting", "label": "Future focused meeting"},
                    {"value": "none", "label": "None for now"},
                ),
                required=True,
            ),
            QuestionDefinition(
                step="follow_up_interest",
                field="follow_up_interest",
                question_id="DALEMBERTIENNES_FOLLOW_UP",
                prompt=STEP_COPY["follow_up_interest"]["title"],
                subtitle=STEP_COPY["follow_up_interest"]["body"],
                input_type="single",
                options=(
                    {"value": "yes", "label": "Yes"},
                    {"value": "maybe", "label": "Maybe"},
                    {"value": "no", "label": "No"},
                ),
                required=True,
            ),
            QuestionDefinition(
                step="open_question",
                field="open_question",
                question_id="DALEMBERTIENNES_OPEN_QUESTION",
                prompt=STEP_COPY["open_question"]["title"],
                subtitle=STEP_COPY["open_question"]["body"],
                input_type="text",
                placeholder="One precise question this event should make visible.",
                required=False,
            ),
        ),
    ),
    profile_fields=(
        "role",
        "career_stage",
        "scientific_home_country",
        "scientific_home_city",
        "scientific_home_institution",
        "scale",
        "collaboration_style",
        "assets",
    ),
    session_fields=(
        "motivations",
        "obstacle",
        "challenge",
        "follow_up_interest",
        "open_question",
        "boiler_room_contribution",
        "question_flags",
        "identity_reveal_targets",
    ),
    deferrable_fields=("open_question",),
    fingerprint_axes=(),
    fingerprint_labels={},
    follow_up_contact_values=("yes", "maybe"),
    migration_profile_fields=(
        "scientific_home_country",
        "assets",
        "collaboration_style",
    ),
)

