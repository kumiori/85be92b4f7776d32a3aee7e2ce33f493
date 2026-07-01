from __future__ import annotations

from conference.question_sets import QuestionDefinition


def role_question(
    question_id: str,
    *,
    prompt: str,
    subtitle: str,
) -> QuestionDefinition:
    return QuestionDefinition(
        step="role",
        field="role",
        question_id=question_id,
        prompt=prompt,
        subtitle=subtitle,
        input_type="multi",
        max_select=3,
        options=(
            {"value": "theory", "label": "Theory"},
            {"value": "models", "label": "Models"},
            {"value": "computation", "label": "Computation"},
            {"value": "experiments", "label": "Experiments"},
            {"value": "data", "label": "Data / AI"},
            {"value": "community", "label": "Community / convening"},
        ),
        required=True,
        origin="shared",
    )


def career_stage_question(
    question_id: str,
    *,
    prompt: str,
    subtitle: str,
) -> QuestionDefinition:
    return QuestionDefinition(
        step="career_stage",
        field="career_stage",
        question_id=question_id,
        prompt=prompt,
        subtitle=subtitle,
        input_type="single",
        options=(
            {"value": "msc", "label": "MSc"},
            {"value": "phd", "label": "PhD"},
            {"value": "postdoc", "label": "Postdoc"},
            {"value": "faculty", "label": "Faculty / PI"},
            {"value": "industry", "label": "Industry"},
            {"value": "independent", "label": "Independent / other"},
        ),
        required=True,
        origin="shared",
    )


def scientific_home_question(
    question_id: str,
    *,
    prompt: str,
    subtitle: str,
) -> QuestionDefinition:
    return QuestionDefinition(
        step="scientific_home",
        field="scientific_home",
        question_id=question_id,
        prompt=prompt,
        subtitle=subtitle,
        input_type="scientific_home",
        required=False,
        origin="shared",
    )


def scale_question(
    question_id: str,
    *,
    prompt: str,
    subtitle: str,
) -> QuestionDefinition:
    return QuestionDefinition(
        step="scale",
        field="scale",
        question_id=question_id,
        prompt=prompt,
        subtitle=subtitle,
        input_type="single",
        options=(
            {"value": "analytical", "label": "Mostly analytical"},
            {"value": "laptop", "label": "Laptop scale"},
            {"value": "small_parallel", "label": "Small parallel runs"},
            {"value": "hpc", "label": "HPC / sustained compute"},
        ),
        required=True,
        origin="shared",
    )


def collaboration_style_question(
    question_id: str,
    *,
    prompt: str,
    subtitle: str,
) -> QuestionDefinition:
    return QuestionDefinition(
        step="collaboration_style",
        field="collaboration_style",
        question_id=question_id,
        prompt=prompt,
        subtitle=subtitle,
        input_type="single",
        options=(
            {"value": "mostly_alone", "label": "Mostly alone"},
            {"value": "small_team", "label": "Small team"},
            {"value": "distributed_network", "label": "Distributed network"},
            {"value": "large_collaboration", "label": "Large collaboration"},
            {"value": "bridge_builder", "label": "Bridge builder across groups"},
        ),
        required=True,
        origin="shared",
    )


def assets_question(
    question_id: str,
    *,
    prompt: str,
    subtitle: str,
) -> QuestionDefinition:
    return QuestionDefinition(
        step="assets",
        field="assets",
        question_id=question_id,
        prompt=prompt,
        subtitle=subtitle,
        input_type="multi",
        max_select=3,
        options=(
            {"value": "theory", "label": "Theory"},
            {"value": "models", "label": "Models"},
            {"value": "computation", "label": "Computation"},
            {"value": "data", "label": "Data"},
            {"value": "experiments", "label": "Experiments"},
            {"value": "software", "label": "Software"},
            {"value": "teaching", "label": "Teaching"},
            {"value": "community", "label": "Community building"},
        ),
        required=True,
        origin="shared",
    )


def follow_up_interest_question(
    question_id: str,
    *,
    prompt: str,
    subtitle: str,
) -> QuestionDefinition:
    return QuestionDefinition(
        step="follow_up_interest",
        field="follow_up_interest",
        question_id=question_id,
        prompt=prompt,
        subtitle=subtitle,
        input_type="single",
        options=(
            {"value": "yes", "label": "Yes"},
            {"value": "maybe", "label": "Maybe"},
            {"value": "no", "label": "No"},
        ),
        required=False,
        origin="shared",
    )
