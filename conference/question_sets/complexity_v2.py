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
    "complexity_fingerprint",
    "open_question",
    "identity",
    "review",
    "done",
)

FLOW_MODES: Dict[str, Dict[str, Any]] = {
    "quick": {
        "title": "Quick impulse",
        "detail": "~ 3 minutes • just a sketch",
        "accent": "🧊",
        "steps": [
            "role",
            "assets",
            "motivations",
            "obstacle",
            "challenge",
            "follow_up_interest",
        ],
    },
    "standard": {
        "title": "Standard",
        "detail": "~ 5 minutes · profile + session",
        "accent": "🔵",
        "steps": [
            "role",
            "scientific_home",
            "scale",
            "collaboration_style",
            "assets",
            "motivations",
            "obstacle",
            "challenge",
            "follow_up_interest",
            "complexity_fingerprint",
            "open_question",
        ],
    },
    "deep": {
        "title": "Deep dive",
        "detail": "~ 7 minutes · fuller profile",
        "accent": "🟠",
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
            "complexity_fingerprint",
            "open_question",
        ],
    },
}

FINGERPRINT_AXES = ("theory", "data", "experiments", "mechanisms")
FINGERPRINT_LABELS = {
    "theory": "Theory",
    "data": "Data",
    "experiments": "Experiments",
    "mechanisms": "Mechanisms",
}

STEP_COPY = {
    "welcome": {
        "title": "Complexity",
        "body": "An anonymous instrument for tracing thoughts, perceptions, and positions.",
        "note": "Anonymous first. Profiles persist gently. Session questions will evolve from time to time.",
    },
    "role": {
        "title": "What is your perspective?",
        "body": "People are mixtures. Choose the perspectives you genuinely inhabit.",
        "cta": "Continue",
    },
    "career_stage": {
        "title": "Career stage",
        "body": "Scientific trajectories start from different distances and tempos.",
        "cta": "Continue",
    },
    "scientific_home": {
        "title": "What is your scientific home?",
        "body": "Topology matters. Scientific communities emerge from places, institutions, and networks.",
        "cta": "Continue",
    },
    "scale": {
        "title": "What computational scale feels natural?",
        "body": "Some questions fit on a laptop. Others need clusters, patient runs, or longer numerical horizons.",
        "cta": "Continue",
    },
    "collaboration_style": {
        "title": "How do you collaborate most naturally?",
        "body": "Progress has a social geometry too.",
        "cta": "Continue",
    },
    "assets": {
        "title": "What can you contribute?",
        "body": "Choose up to three assets you would realistically bring into a collective effort.",
        "cta": "Continue",
    },
    "motivations": {
        "title": "What drives you right now?",
        "body": "Choose up to three active motivations for this moment.",
        "cta": "Continue",
    },
    "obstacle": {
        "title": "What slows progress most right now?",
        "body": "Choose up to two obstacles. This is the session layer, not your permanent identity.",
        "cta": "Continue",
    },
    "challenge": {
        "title": "What challenge would you join here?",
        "body": "If enough people converged, where would you put your attention?",
        "cta": "Continue",
    },
    "follow_up_interest": {
        "title": "Would you like to continue discussions?",
        "body": "Only about whether you would like to continue discussions after the event.",
        "cta": "Continue",
    },
    "complexity_fingerprint": {
        "title": "What gives you confidence?",
        "body": "A compact complexity fingerprint. Set the resonance of each source from 0 to 5.",
        "cta": "Continue",
    },
    "open_question": {
        "title": "What question keeps you awake?",
        "body": "A challenge, paradox, obstacle, or curiosity you return to repeatedly.",
        "cta": "Continue",
    },
    "identity": {
        "title": "Alias or identity",
        "body": "Optional. Leave a name, affiliation, email, website, or remain anonymous.",
        "cta": "Continue",
    },
    "review": {
        "title": "Review before integrating",
        "body": "Profile persists. Session signals describe this event. You can defer reflective questions and return later.",
        "cta": "Integrate",
    },
    "done": {
        "title": "Signal stored",
        "body": "Keep your key. It lets Complexity remember your profile and your pending reflections.",
        "cta": "Start again",
    },
}

QUESTION_SET = QuestionSet(
    id="complexity_v2",
    source_module=__name__,
    step_copy=STEP_COPY,
    step_order=STEP_ORDER,
    flow_modes=FLOW_MODES,
    questions=merge_questions(
        (
            role_question(
                "COMPLEXITY_ROLE",
                prompt=STEP_COPY["role"]["title"],
                subtitle=STEP_COPY["role"]["body"],
            ),
            career_stage_question(
                "COMPLEXITY_CAREER_STAGE",
                prompt=STEP_COPY["career_stage"]["title"],
                subtitle=STEP_COPY["career_stage"]["body"],
            ),
            scientific_home_question(
                "COMPLEXITY_SCIENTIFIC_HOME",
                prompt=STEP_COPY["scientific_home"]["title"],
                subtitle=STEP_COPY["scientific_home"]["body"],
            ),
            scale_question(
                "COMPLEXITY_SCALE",
                prompt=STEP_COPY["scale"]["title"],
                subtitle=STEP_COPY["scale"]["body"],
            ),
            collaboration_style_question(
                "COMPLEXITY_COLLABORATION_STYLE",
                prompt=STEP_COPY["collaboration_style"]["title"],
                subtitle=STEP_COPY["collaboration_style"]["body"],
            ),
            assets_question(
                "COMPLEXITY_ASSETS",
                prompt=STEP_COPY["assets"]["title"],
                subtitle=STEP_COPY["assets"]["body"],
            ),
        ),
        (
            QuestionDefinition(
                step="motivations",
                field="motivations",
                question_id="COMPLEXITY_MOTIVATIONS",
                prompt=STEP_COPY["motivations"]["title"],
                subtitle=STEP_COPY["motivations"]["body"],
                input_type="multi",
                max_select=3,
                options=(
                    {"value": "understanding", "label": "Understanding"},
                    {"value": "methods", "label": "Methods"},
                    {"value": "application", "label": "Applications"},
                    {"value": "comparison", "label": "Benchmarking / comparison"},
                    {"value": "collaboration", "label": "Finding collaborators"},
                    {"value": "teaching", "label": "Teaching / mentoring"},
                ),
                required=True,
            ),
            QuestionDefinition(
                step="obstacle",
                field="obstacle",
                question_id="COMPLEXITY_OBSTACLE",
                prompt=STEP_COPY["obstacle"]["title"],
                subtitle=STEP_COPY["obstacle"]["body"],
                input_type="multi",
                max_select=2,
                options=(
                    {"value": "theory", "label": "Theory"},
                    {"value": "models", "label": "Models"},
                    {"value": "computation", "label": "Computation"},
                    {"value": "data", "label": "Data"},
                    {"value": "experiments", "label": "Experiments"},
                    {"value": "validation", "label": "Validation"},
                    {"value": "funding", "label": "Funding"},
                    {"value": "coordination", "label": "Coordination"},
                ),
                required=True,
            ),
            QuestionDefinition(
                step="challenge",
                field="challenge",
                question_id="COMPLEXITY_CHALLENGE",
                prompt=STEP_COPY["challenge"]["title"],
                subtitle=STEP_COPY["challenge"]["body"],
                input_type="single",
                options=(
                    {"value": "benchmark", "label": "Benchmark problems"},
                    {"value": "datasets", "label": "Shared datasets"},
                    {"value": "code", "label": "Shared code comparison"},
                    {"value": "campaign", "label": "Experimental campaign"},
                    {"value": "working_group", "label": "Theory / methods working group"},
                    {"value": "learning", "label": "Learning / reading circle"},
                    {"value": "none", "label": "None"},
                ),
                required=True,
            ),
            QuestionDefinition(
                step="follow_up_interest",
                field="follow_up_interest",
                question_id="COMPLEXITY_FOLLOW_UP",
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
                step="complexity_fingerprint",
                field="complexity_fingerprint",
                question_id="COMPLEXITY_FINGERPRINT",
                prompt=STEP_COPY["complexity_fingerprint"]["title"],
                subtitle=STEP_COPY["complexity_fingerprint"]["body"],
                input_type="fingerprint",
                required=False,
            ),
            QuestionDefinition(
                step="open_question",
                field="open_question",
                question_id="COMPLEXITY_OPEN_QUESTION",
                prompt=STEP_COPY["open_question"]["title"],
                subtitle=STEP_COPY["open_question"]["body"],
                input_type="text",
                placeholder="One sentence. One recurring question.",
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
        "complexity_fingerprint",
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
    deferrable_fields=("complexity_fingerprint", "open_question"),
    fingerprint_axes=FINGERPRINT_AXES,
    fingerprint_labels=FINGERPRINT_LABELS,
    follow_up_contact_values=("yes", "maybe"),
    migration_profile_fields=(
        "scientific_home_country",
        "assets",
        "collaboration_style",
        "complexity_fingerprint",
    ),
)

