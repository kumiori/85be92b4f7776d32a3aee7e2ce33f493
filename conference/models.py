from __future__ import annotations

from typing import Any, Dict, List

from conference.question_sets import (
    active_steps_for_mode as _active_steps_for_mode,
    field_for_step as _field_for_step,
    field_option_label_map as _field_option_label_map,
    field_value_set as _field_value_set,
    mode_card_rows as _mode_card_rows,
    question_by_field as _question_by_field,
    question_by_step as _question_by_step,
    questions_as_dicts,
    step_copy_dict,
)
from conference.question_sets.complexity_v2 import QUESTION_SET as _QUESTION_SET


STEP_ORDER: List[str] = list(_QUESTION_SET.step_order)
FLOW_MODES: Dict[str, Dict[str, Any]] = {
    str(key): dict(value) for key, value in _QUESTION_SET.flow_modes.items()
}
FOLLOW_UP_CONTACT_VALUES = set(_QUESTION_SET.follow_up_contact_values)
DEFERRABLE_FIELDS = set(_QUESTION_SET.deferrable_fields)
PROFILE_FIELDS = set(_QUESTION_SET.profile_fields)
SESSION_FIELDS = set(_QUESTION_SET.session_fields)
FINGERPRINT_AXES = list(_QUESTION_SET.fingerprint_axes)
FINGERPRINT_LABELS = dict(_QUESTION_SET.fingerprint_labels)
MIGRATION_PROFILE_FIELDS = list(_QUESTION_SET.migration_profile_fields)
STEP_COPY: Dict[str, Dict[str, str]] = step_copy_dict(_QUESTION_SET)
SESSION_QUESTIONS: List[Dict[str, Any]] = questions_as_dicts(_QUESTION_SET)


def active_steps_for_mode(mode: str) -> List[str]:
    return _active_steps_for_mode(_QUESTION_SET, mode)


def mode_card_rows() -> List[Dict[str, str]]:
    return _mode_card_rows(_QUESTION_SET)


def question_by_step(step: str) -> Dict[str, Any] | None:
    question = _question_by_step(_QUESTION_SET, step)
    return question.as_dict() if question else None


def question_by_field(field: str) -> Dict[str, Any] | None:
    question = _question_by_field(_QUESTION_SET, field)
    return question.as_dict() if question else None


def field_option_label_map(field: str) -> Dict[str, str]:
    return _field_option_label_map(_QUESTION_SET, field)


def field_for_step(step: str) -> str:
    return _field_for_step(_QUESTION_SET, step)


def _set_for(field: str) -> set[str]:
    return _field_value_set(_QUESTION_SET, field)


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
    if "career_stage" in fields:
        return "deep"
    if fields:
        return "standard"
    return "quick"
