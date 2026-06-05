from __future__ import annotations

from typing import Any, Dict, List


STEP_ORDER: List[str] = [
    "welcome",
    "role",
    "career_stage",
    "systems",
    "expectations",
    "formulation",
    "reality_check",
    "scale",
    "motivations",
    "obstacle",
    "research_style",
    "challenge",
    "timescale",
    "continue_conversation",
    "open_text",
    "identity",
    "review",
    "done",
]


FLOW_MODES: Dict[str, Dict[str, Any]] = {
    "quick": {
        "title": "Quick pulse",
        "detail": "~ 3 minutes \u00b7 7 questions",
        "accent": "🟢",
        "steps": [
            "role",
            "systems",
            "expectations",
            "motivations",
            "obstacle",
            "challenge",
            "continue_conversation",
        ],
    },
    "standard": {
        "title": "Standard",
        "detail": "~ 5 minutes \u00b7 10 questions",
        "accent": "🔵",
        "steps": [
            "role",
            "systems",
            "expectations",
            "formulation",
            "reality_check",
            "scale",
            "motivations",
            "obstacle",
            "challenge",
            "continue_conversation",
        ],
    },
    "deep": {
        "title": "Deep dive",
        "detail": "~ 7 minutes \u00b7 Full exploration",
        "accent": "🟣",
        "steps": [
            "role",
            "career_stage",
            "systems",
            "expectations",
            "formulation",
            "reality_check",
            "scale",
            "motivations",
            "obstacle",
            "research_style",
            "challenge",
            "timescale",
            "continue_conversation",
            "open_text",
        ],
    },
}


FOLLOW_UP_CONTACT_VALUES = {"happy_to_engage", "maybe_later"}


STEP_COPY: Dict[str, Dict[str, str]] = {
    "welcome": {
        "title": "Orchestrating solvers for real problems",
        "body": "A short anonymous exploration of how we model complex systems, compare approaches, and identify opportunities for collaboration.",
        "note": "Anonymous first. You can leave an alias or contact at the end if you wish.",
    },
    "role": {
        "title": "What is your point of view?",
        "body": "Every problem looks different from theory, numerics, experiments, or data.",
        "cta": "Continue",
    },
    "career_stage": {
        "title": "Career stage",
        "body": "Scientific journeys start from different places.",
        "cta": "Continue",
    },
    "systems": {
        "title": "What systems do you study?",
        "body": "From static structures to evolving systems, what kinds of phenomena occupy your attention?",
        "cta": "Continue",
    },
    "expectations": {
        "title": "Any expectations?",
        "body": "When parameters change, do solutions evolve continuously or through sudden transitions?",
        "cta": "Continue",
    },
    "formulation": {
        "title": "How do you formulate the problem?",
        "body": "Different mathematical languages reveal different aspects of the same phenomenon.",
        "cta": "Continue",
    },
    "reality_check": {
        "title": "Reality check?",
        "body": "How closely do your models stay connected to measurements, observations, or experiments?",
        "cta": "Continue",
    },
    "scale": {
        "title": "How large is the playground?",
        "body": "Some questions can be answered on a laptop. Others require clusters, HPC resources, or years of computation.",
        "cta": "Continue",
    },
    "motivations": {
        "title": "What drives your work?",
        "body": "Choose up to three motivations.",
        "cta": "Continue",
    },
    "obstacle": {
        "title": "Biggest obstacle?",
        "body": "What currently slows progress the most? Choose up to two.",
        "cta": "Continue",
    },
    "research_style": {
        "title": "Where does progress usually happen?",
        "body": "Alone, in a small group, or within a larger ecosystem?",
        "cta": "Continue",
    },
    "challenge": {
        "title": "What challenge would you join?",
        "body": "If enough people shared your interest, what would you be excited to explore together?",
        "cta": "Continue",
    },
    "timescale": {
        "title": "What timescale feels natural to you?",
        "body": "Some questions need a sprint. Others need a longer horizon.",
        "cta": "Continue",
    },
    "continue_conversation": {
        "title": "Continue the conversation?",
        "body": "This remains anonymous unless you choose otherwise.",
        "cta": "Continue",
    },
    "open_text": {
        "title": "Any thoughts?",
        "body": "A benchmark, a challenge, a question, a frustration, or simply an idea worth sharing.",
        "cta": "Continue",
    },
    "identity": {
        "title": "Alias or identity",
        "body": "Optional. Leave a name, affiliation, email, website, or remain anonymous.",
        "cta": "Continue",
    },
    "review": {
        "title": "Review before integrating",
        "body": "Your responses stay local until you integrate them into a bigger picture.",
        "cta": "Integrate",
    },
    "done": {
        "title": "Session responses stored",
        "body": "Keep your short key. It lets you reconnect later. We'll rediscuss upon reaching critical mass.",
        "cta": "Start again",
    },
}


SESSION_QUESTIONS: List[Dict[str, Any]] = [
    {
        "step": "role",
        "field": "role",
        "question_id": "PISA_ROLE",
        "prompt": STEP_COPY["role"]["title"],
        "subtitle": STEP_COPY["role"]["body"],
        "input_type": "multi",
        "options": [
            {"value": "theory", "label": "Theory"},
            {"value": "numerics", "label": "Numerics"},
            {"value": "experiments", "label": "Experiments"},
            {"value": "data_ai", "label": "Data / AI"},
            {"value": "industry", "label": "Industry"},
            {"value": "other", "label": "Other"},
            {"value": "depends", "label": "Depends on the day"},
        ],
        "required": True,
    },
    {
        "step": "career_stage",
        "field": "career_stage",
        "question_id": "PISA_CAREER_STAGE",
        "prompt": STEP_COPY["career_stage"]["title"],
        "subtitle": STEP_COPY["career_stage"]["body"],
        "input_type": "multi",
        "options": [
            {"value": "msc", "label": "MSc"},
            {"value": "phd", "label": "PhD"},
            {"value": "postdoc", "label": "Postdoc"},
            {"value": "permanent_researcher", "label": "Permanent researcher"},
            {"value": "industry", "label": "Industry"},
        ],
        "required": True,
    },
    {
        "step": "systems",
        "field": "systems",
        "question_id": "PISA_SYSTEMS",
        "prompt": STEP_COPY["systems"]["title"],
        "subtitle": STEP_COPY["systems"]["body"],
        "input_type": "multi",
        "max_select": 2,
        "options": [
            {"value": "static", "label": "Static"},
            {"value": "evolutionary", "label": "Evolutionary"},
            {"value": "dynamic", "label": "Dynamic"},
            {"value": "multiphysics", "label": "Multiphysics"},
            {"value": "stochastic", "label": "Stochastic"},
        ],
        "required": True,
    },
    {
        "step": "expectations",
        "field": "expectations",
        "question_id": "PISA_EXPECTATIONS",
        "prompt": STEP_COPY["expectations"]["title"],
        "subtitle": STEP_COPY["expectations"]["body"],
        "input_type": "multi",
        "options": [
            {"value": "smooth_evolutions", "label": "Smooth evolutions"},
            {"value": "occasional_transitions", "label": "Occasional transitions"},
            {"value": "discontinuous_evolutions", "label": "Discontinuous evolutions"},
            {"value": "unsure", "label": "Unsure"},
        ],
        "required": True,
    },
    {
        "step": "formulation",
        "field": "formulation",
        "question_id": "PISA_FORMULATION",
        "prompt": STEP_COPY["formulation"]["title"],
        "subtitle": STEP_COPY["formulation"]["body"],
        "input_type": "multi",
        "max_select": 2,
        "options": [
            {"value": "strong_form_pdes", "label": "Strong form PDEs"},
            {"value": "weak_formulations", "label": "Weak formulations"},
            {"value": "variational_principles", "label": "Variational principles"},
            {"value": "energetic_formulations", "label": "Energetic formulations"},
            {"value": "mixed_approaches", "label": "Mixed approaches"},
        ],
        "required": True,
    },
    {
        "step": "reality_check",
        "field": "reality_check",
        "question_id": "PISA_REALITY_CHECK",
        "prompt": STEP_COPY["reality_check"]["title"],
        "subtitle": STEP_COPY["reality_check"]["body"],
        "input_type": "multi",
        "options": [
            {"value": "essential", "label": "Essential"},
            {"value": "valuable_not_required", "label": "Valuable but not required"},
            {"value": "rarely_available", "label": "Rarely available"},
            {"value": "purely_theoretical", "label": "Purely theoretical"},
        ],
        "required": True,
    },
    {
        "step": "scale",
        "field": "scale",
        "question_id": "PISA_SCALE",
        "prompt": STEP_COPY["scale"]["title"],
        "subtitle": STEP_COPY["scale"]["body"],
        "input_type": "multi",
        "options": [
            {"value": "mostly_analytical", "label": "Mostly analytical"},
            {"value": "serial_computations", "label": "Serial computations"},
            {"value": "small_parallel_runs", "label": "Small parallel runs"},
            {"value": "hpc_required", "label": "HPC required"},
        ],
        "required": True,
    },
    {
        "step": "motivations",
        "field": "motivations",
        "question_id": "PISA_MOTIVATIONS",
        "prompt": STEP_COPY["motivations"]["title"],
        "subtitle": STEP_COPY["motivations"]["body"],
        "input_type": "multi",
        "max_select": 3,
        "options": [
            {
                "value": "fundamental_understanding",
                "label": "Fundamental understanding",
            },
            {"value": "mathematical_theory", "label": "Mathematical theory"},
            {"value": "numerical_methods", "label": "Numerical methods"},
            {"value": "industrial_applications", "label": "Industrial applications"},
            {"value": "environmental_challenges", "label": "Environmental challenges"},
            {"value": "natural_systems", "label": "Natural systems"},
            {"value": "experimental_discovery", "label": "Experimental discovery"},
            {"value": "scientific_curiosity", "label": "Scientific curiosity"},
        ],
        "required": True,
    },
    {
        "step": "obstacle",
        "field": "obstacle",
        "question_id": "PISA_OBSTACLE",
        "prompt": STEP_COPY["obstacle"]["title"],
        "subtitle": STEP_COPY["obstacle"]["body"],
        "input_type": "multi",
        "max_select": 2,
        "options": [
            {"value": "models", "label": "Models"},
            {"value": "data", "label": "Data"},
            {"value": "computation", "label": "Computation"},
            {"value": "validation", "label": "Validation"},
            {"value": "theory", "label": "Theory"},
            {"value": "funding", "label": "Funding"},
            {"value": "collaboration", "label": "Collaboration"},
        ],
        "required": True,
    },
    {
        "step": "research_style",
        "field": "research_style",
        "question_id": "PISA_RESEARCH_STYLE",
        "prompt": STEP_COPY["research_style"]["title"],
        "subtitle": STEP_COPY["research_style"]["body"],
        "input_type": "multi",
        "options": [
            {"value": "mostly_alone", "label": "Mostly alone"},
            {"value": "small_local_team", "label": "Small local team"},
            {"value": "large_collaboration", "label": "Large collaboration"},
            {"value": "open_source_community", "label": "Open-source community"},
            {
                "value": "industry_academia_projects",
                "label": "Industry-academia projects",
            },
        ],
        "required": True,
    },
    {
        "step": "challenge",
        "field": "challenge",
        "question_id": "PISA_CHALLENGE",
        "prompt": STEP_COPY["challenge"]["title"],
        "subtitle": STEP_COPY["challenge"]["body"],
        "input_type": "multi",
        "options": [
            {"value": "benchmark_problems", "label": "Benchmark problems"},
            {"value": "shared_datasets", "label": "Shared datasets"},
            {"value": "shared_code_comparison", "label": "Shared code comparison"},
            {"value": "experimental_campaign", "label": "Experimental campaign"},
            {"value": "theory_working_group", "label": "Theory working group"},
            {"value": "open_source_tools", "label": "Open-source tools"},
            {"value": "educational_initiative", "label": "Educational initiative"},
        ],
        "required": True,
    },
    {
        "step": "timescale",
        "field": "timescale",
        "question_id": "PISA_TIMESCALE",
        "prompt": STEP_COPY["timescale"]["title"],
        "subtitle": STEP_COPY["timescale"]["body"],
        "input_type": "multi",
        "options": [
            {"value": "few_weeks", "label": "A few weeks"},
            {"value": "few_months", "label": "A few months"},
            {"value": "one_year", "label": "One year"},
            {"value": "long_term", "label": "Long-term collaboration"},
        ],
        "required": True,
    },
    {
        "step": "continue_conversation",
        "field": "continue_conversation",
        "question_id": "PISA_CONTINUE_CONVERSATION",
        "prompt": STEP_COPY["continue_conversation"]["title"],
        "subtitle": STEP_COPY["continue_conversation"]["body"],
        "input_type": "multi",
        "options": [
            {"value": "happy_to_engage", "label": "Happy to engage"},
            {"value": "maybe_later", "label": "Maybe later"},
            {"value": "just_exploring", "label": "Just exploring"},
        ],
        "required": True,
    },
    {
        "step": "open_text",
        "field": "open_text",
        "question_id": "PISA_OPEN_TEXT",
        "prompt": STEP_COPY["open_text"]["title"],
        "subtitle": STEP_COPY["open_text"]["body"],
        "input_type": "text",
        "placeholder": "Write a benchmark idea, a difficulty, or a direction worth exploring.",
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


def role_set() -> set[str]:
    return _set_for("role")


def career_stage_set() -> set[str]:
    return _set_for("career_stage")


def systems_set() -> set[str]:
    return _set_for("systems")


def expectations_set() -> set[str]:
    return _set_for("expectations")


def formulation_set() -> set[str]:
    return _set_for("formulation")


def reality_check_set() -> set[str]:
    return _set_for("reality_check")


def scale_set() -> set[str]:
    return _set_for("scale")


def motivations_set() -> set[str]:
    return _set_for("motivations")


def obstacle_set() -> set[str]:
    return _set_for("obstacle")


def research_style_set() -> set[str]:
    return _set_for("research_style")


def challenge_set() -> set[str]:
    return _set_for("challenge")


def timescale_set() -> set[str]:
    return _set_for("timescale")


def continue_conversation_set() -> set[str]:
    return _set_for("continue_conversation")
