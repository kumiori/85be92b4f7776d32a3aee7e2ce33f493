from __future__ import annotations

from typing import Any, Dict, List


STEP_ORDER: List[str] = [
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
]


FLOW_MODES: Dict[str, Dict[str, Any]] = {
    "quick": {
        "title": "Quick pulse",
        "detail": "~ 3 minutes · profile sketch",
        "accent": "🟢",
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


FOLLOW_UP_CONTACT_VALUES = {"yes", "maybe"}
DEFERRABLE_FIELDS = {"complexity_fingerprint", "open_question"}
PROFILE_FIELDS = {
    "role",
    "career_stage",
    "scientific_home_country",
    "scientific_home_city",
    "scientific_home_institution",
    "scale",
    "collaboration_style",
    "assets",
    "complexity_fingerprint",
}
SESSION_FIELDS = {
    "motivations",
    "obstacle",
    "challenge",
    "follow_up_interest",
    "open_question",
    "identity_reveal_targets",
}
FINGERPRINT_AXES = ["theory", "data", "experiments", "mechanisms"]
FINGERPRINT_LABELS = {
    "theory": "Theory",
    "data": "Data",
    "experiments": "Experiments",
    "mechanisms": "Mechanisms",
}
MIGRATION_PROFILE_FIELDS = [
    "scientific_home_country",
    "assets",
    "collaboration_style",
    "complexity_fingerprint",
]


STEP_COPY: Dict[str, Dict[str, str]] = {
    "welcome": {
        "title": "Complexity",
        "body": "A short anonymous instrument for tracing how people think, what they can contribute, and what the room is becoming together.",
        "note": "Anonymous first. Profiles persist gently. Session questions can evolve from event to event.",
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


SESSION_QUESTIONS: List[Dict[str, Any]] = [
    {
        "step": "role",
        "field": "role",
        "question_id": "COMPLEXITY_ROLE",
        "prompt": STEP_COPY["role"]["title"],
        "subtitle": STEP_COPY["role"]["body"],
        "input_type": "multi",
        "max_select": 3,
        "options": [
            {"value": "theory", "label": "Theory"},
            {"value": "models", "label": "Models"},
            {"value": "computation", "label": "Computation"},
            {"value": "experiments", "label": "Experiments"},
            {"value": "data", "label": "Data / AI"},
            {"value": "community", "label": "Community / convening"},
        ],
        "required": True,
    },
    {
        "step": "career_stage",
        "field": "career_stage",
        "question_id": "COMPLEXITY_CAREER_STAGE",
        "prompt": STEP_COPY["career_stage"]["title"],
        "subtitle": STEP_COPY["career_stage"]["body"],
        "input_type": "single",
        "options": [
            {"value": "msc", "label": "MSc"},
            {"value": "phd", "label": "PhD"},
            {"value": "postdoc", "label": "Postdoc"},
            {"value": "faculty", "label": "Faculty / PI"},
            {"value": "industry", "label": "Industry"},
            {"value": "independent", "label": "Independent / other"},
        ],
        "required": True,
    },
    {
        "step": "scientific_home",
        "field": "scientific_home",
        "question_id": "COMPLEXITY_SCIENTIFIC_HOME",
        "prompt": STEP_COPY["scientific_home"]["title"],
        "subtitle": STEP_COPY["scientific_home"]["body"],
        "input_type": "scientific_home",
        "required": False,
    },
    {
        "step": "scale",
        "field": "scale",
        "question_id": "COMPLEXITY_SCALE",
        "prompt": STEP_COPY["scale"]["title"],
        "subtitle": STEP_COPY["scale"]["body"],
        "input_type": "single",
        "options": [
            {"value": "analytical", "label": "Mostly analytical"},
            {"value": "laptop", "label": "Laptop scale"},
            {"value": "small_parallel", "label": "Small parallel runs"},
            {"value": "hpc", "label": "HPC / sustained compute"},
        ],
        "required": True,
    },
    {
        "step": "collaboration_style",
        "field": "collaboration_style",
        "question_id": "COMPLEXITY_COLLABORATION_STYLE",
        "prompt": STEP_COPY["collaboration_style"]["title"],
        "subtitle": STEP_COPY["collaboration_style"]["body"],
        "input_type": "single",
        "options": [
            {"value": "mostly_alone", "label": "Mostly alone"},
            {"value": "small_team", "label": "Small team"},
            {"value": "distributed_network", "label": "Distributed network"},
            {"value": "large_collaboration", "label": "Large collaboration"},
            {"value": "bridge_builder", "label": "Bridge builder across groups"},
        ],
        "required": True,
    },
    {
        "step": "assets",
        "field": "assets",
        "question_id": "COMPLEXITY_ASSETS",
        "prompt": STEP_COPY["assets"]["title"],
        "subtitle": STEP_COPY["assets"]["body"],
        "input_type": "multi",
        "max_select": 3,
        "options": [
            {"value": "theory", "label": "Theory"},
            {"value": "models", "label": "Models"},
            {"value": "computation", "label": "Computation"},
            {"value": "data", "label": "Data"},
            {"value": "experiments", "label": "Experiments"},
            {"value": "software", "label": "Software"},
            {"value": "teaching", "label": "Teaching"},
            {"value": "community", "label": "Community building"},
        ],
        "required": True,
    },
    {
        "step": "motivations",
        "field": "motivations",
        "question_id": "COMPLEXITY_MOTIVATIONS",
        "prompt": STEP_COPY["motivations"]["title"],
        "subtitle": STEP_COPY["motivations"]["body"],
        "input_type": "multi",
        "max_select": 3,
        "options": [
            {"value": "understanding", "label": "Understanding"},
            {"value": "methods", "label": "Methods"},
            {"value": "application", "label": "Applications"},
            {"value": "comparison", "label": "Benchmarking / comparison"},
            {"value": "collaboration", "label": "Finding collaborators"},
            {"value": "teaching", "label": "Teaching / mentoring"},
        ],
        "required": True,
    },
    {
        "step": "obstacle",
        "field": "obstacle",
        "question_id": "COMPLEXITY_OBSTACLE",
        "prompt": STEP_COPY["obstacle"]["title"],
        "subtitle": STEP_COPY["obstacle"]["body"],
        "input_type": "multi",
        "max_select": 2,
        "options": [
            {"value": "theory", "label": "Theory"},
            {"value": "models", "label": "Models"},
            {"value": "computation", "label": "Computation"},
            {"value": "data", "label": "Data"},
            {"value": "experiments", "label": "Experiments"},
            {"value": "validation", "label": "Validation"},
            {"value": "funding", "label": "Funding"},
            {"value": "coordination", "label": "Coordination"},
        ],
        "required": True,
    },
    {
        "step": "challenge",
        "field": "challenge",
        "question_id": "COMPLEXITY_CHALLENGE",
        "prompt": STEP_COPY["challenge"]["title"],
        "subtitle": STEP_COPY["challenge"]["body"],
        "input_type": "single",
        "options": [
            {"value": "benchmark", "label": "Benchmark problems"},
            {"value": "datasets", "label": "Shared datasets"},
            {"value": "code", "label": "Shared code comparison"},
            {"value": "campaign", "label": "Experimental campaign"},
            {"value": "working_group", "label": "Theory / methods working group"},
            {"value": "learning", "label": "Learning / reading circle"},
            {"value": "none", "label": "None"},
        ],
        "required": True,
    },
    {
        "step": "follow_up_interest",
        "field": "follow_up_interest",
        "question_id": "COMPLEXITY_FOLLOW_UP",
        "prompt": STEP_COPY["follow_up_interest"]["title"],
        "subtitle": STEP_COPY["follow_up_interest"]["body"],
        "input_type": "single",
        "options": [
            {"value": "yes", "label": "Yes"},
            {"value": "maybe", "label": "Maybe"},
            {"value": "no", "label": "No"},
        ],
        "required": True,
    },
    {
        "step": "complexity_fingerprint",
        "field": "complexity_fingerprint",
        "question_id": "COMPLEXITY_FINGERPRINT",
        "prompt": STEP_COPY["complexity_fingerprint"]["title"],
        "subtitle": STEP_COPY["complexity_fingerprint"]["body"],
        "input_type": "fingerprint",
        "required": False,
    },
    {
        "step": "open_question",
        "field": "open_question",
        "question_id": "COMPLEXITY_OPEN_QUESTION",
        "prompt": STEP_COPY["open_question"]["title"],
        "subtitle": STEP_COPY["open_question"]["body"],
        "input_type": "text",
        "placeholder": "One sentence. One recurring question.",
        "required": False,
    },
]


def active_steps_for_mode(mode: str) -> List[str]:
    model = FLOW_MODES.get(str(mode or "").strip())
    if not model:
        return []
    return list(model["steps"])


def mode_card_rows() -> List[Dict[str, str]]:
    return [
        {
            "value": key,
            "title": str(item["title"]),
            "detail": str(item["detail"]),
            "accent": str(item["accent"]),
        }
        for key, item in FLOW_MODES.items()
    ]


def _set_for(field: str) -> set[str]:
    for question in SESSION_QUESTIONS:
        if question["field"] != field:
            continue
        return {str(option["value"]) for option in question.get("options", [])}
    return set()


def question_by_step(step: str) -> Dict[str, Any] | None:
    for question in SESSION_QUESTIONS:
        if question["step"] == step:
            return question
    return None


def question_by_field(field: str) -> Dict[str, Any] | None:
    for question in SESSION_QUESTIONS:
        if question["field"] == field:
            return question
    return None


def field_option_label_map(field: str) -> Dict[str, str]:
    question = question_by_field(field)
    if not question:
        return {}
    return {
        str(option["value"]): str(option["label"])
        for option in question.get("options", [])
    }


def field_for_step(step: str) -> str:
    question = question_by_step(step)
    return str(question["field"]) if question else ""


def role_set() -> set[str]:
    return _set_for("role")


def career_stage_set() -> set[str]:
    return _set_for("career_stage")


def scale_set() -> set[str]:
    return _set_for("scale")


def collaboration_style_set() -> set[str]:
    return _set_for("collaboration_style")


def assets_set() -> set[str]:
    return _set_for("assets")


def motivations_set() -> set[str]:
    return _set_for("motivations")


def obstacle_set() -> set[str]:
    return _set_for("obstacle")


def challenge_set() -> set[str]:
    return _set_for("challenge")


def follow_up_interest_set() -> set[str]:
    return _set_for("follow_up_interest")


def recommended_mode_for_fields(fields: List[str]) -> str:
    needed = set(fields)
    if "career_stage" in needed:
        return "deep"
    if needed:
        return "standard"
    return "quick"
