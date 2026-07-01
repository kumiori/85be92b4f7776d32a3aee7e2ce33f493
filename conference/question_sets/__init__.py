from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, Iterable, List, Mapping, Sequence


@dataclass(frozen=True)
class QuestionDefinition:
    step: str
    field: str
    question_id: str
    prompt: str
    subtitle: str = ""
    input_type: str = "single"
    options: tuple[dict[str, str], ...] = ()
    required: bool = False
    max_select: int | None = None
    placeholder: str = ""
    origin: str = "event"
    group: str = ""
    subgroup: str = ""
    free_text_field: str = ""
    free_text_label: str = ""
    free_text_placeholder: str = ""
    free_text_required: bool = False

    @property
    def context(self) -> str:
        return self.subtitle

    def as_dict(self) -> dict[str, Any]:
        out: dict[str, Any] = {
            "step": self.step,
            "field": self.field,
            "question_id": self.question_id,
            "prompt": self.prompt,
            "subtitle": self.subtitle,
            "context": self.context,
            "input_type": self.input_type,
            "options": [dict(item) for item in self.options],
            "required": self.required,
        }
        if self.max_select is not None:
            out["max_select"] = self.max_select
        if self.placeholder:
            out["placeholder"] = self.placeholder
        if self.group:
            out["group"] = self.group
        if self.subgroup:
            out["subgroup"] = self.subgroup
        if self.free_text_field:
            out["free_text"] = {
                "field": self.free_text_field,
                "label": self.free_text_label,
                "placeholder": self.free_text_placeholder,
                "required": self.free_text_required,
            }
        return out


@dataclass(frozen=True)
class QuestionSet:
    id: str
    source_module: str
    step_copy: Mapping[str, Mapping[str, str]]
    step_order: Sequence[str]
    flow_modes: Mapping[str, Mapping[str, Any]]
    questions: Sequence[QuestionDefinition]
    profile_fields: Sequence[str]
    session_fields: Sequence[str]
    deferrable_fields: Sequence[str]
    fingerprint_axes: Sequence[str]
    fingerprint_labels: Mapping[str, str]
    follow_up_contact_values: Sequence[str]
    migration_profile_fields: Sequence[str]
    default_mode: str = "quick"
    show_mode_selection: bool = True


def question_ids(question_set: QuestionSet) -> list[str]:
    return [question.question_id for question in question_set.questions]


def question_by_step(
    question_set: QuestionSet,
    step: str,
) -> QuestionDefinition | None:
    token = str(step or "").strip()
    for question in question_set.questions:
        if question.step == token:
            return question
    return None


def question_by_field(
    question_set: QuestionSet,
    field: str,
) -> QuestionDefinition | None:
    token = str(field or "").strip()
    for question in question_set.questions:
        if question.field == token:
            return question
    return None


def field_for_step(question_set: QuestionSet, step: str) -> str:
    question = question_by_step(question_set, step)
    return str(question.field) if question else ""


def field_option_label_map(
    question_set: QuestionSet,
    field: str,
) -> dict[str, str]:
    question = question_by_field(question_set, field)
    if not question:
        return {}
    return {
        str(option["value"]): str(option["label"])
        for option in question.options
    }


def field_value_set(question_set: QuestionSet, field: str) -> set[str]:
    question = question_by_field(question_set, field)
    if not question:
        return set()
    return {str(option["value"]) for option in question.options}


def active_steps_for_mode(question_set: QuestionSet, mode: str) -> list[str]:
    spec = question_set.flow_modes.get(str(mode or "").strip())
    if not spec:
        return []
    return [str(step) for step in spec.get("steps", []) if str(step).strip()]


def mode_card_rows(question_set: QuestionSet) -> list[dict[str, str]]:
    return [
        {
            "value": key,
            "title": str(item["title"]),
            "detail": str(item["detail"]),
            "accent": str(item["accent"]),
        }
        for key, item in question_set.flow_modes.items()
    ]


def shared_question_ids(question_set: QuestionSet) -> list[str]:
    return [question.question_id for question in question_set.questions if question.origin == "shared"]


def event_specific_question_ids(question_set: QuestionSet) -> list[str]:
    return [question.question_id for question in question_set.questions if question.origin != "shared"]


def questions_as_dicts(question_set: QuestionSet) -> list[dict[str, Any]]:
    return [question.as_dict() for question in question_set.questions]


def step_copy_dict(question_set: QuestionSet) -> dict[str, dict[str, str]]:
    return {
        str(step): {str(key): str(value) for key, value in copy.items()}
        for step, copy in question_set.step_copy.items()
    }


def validate_question_set(question_set: QuestionSet) -> list[str]:
    errors: list[str] = []
    seen_ids: set[str] = set()
    seen_steps: set[str] = set()
    step_order = {str(step) for step in question_set.step_order}
    for question in question_set.questions:
        if question.question_id in seen_ids:
            errors.append(f"Duplicate question id in {question_set.id}: {question.question_id}")
        seen_ids.add(question.question_id)
        if question.step in seen_steps:
            errors.append(f"Duplicate step in {question_set.id}: {question.step}")
        seen_steps.add(question.step)
        if question.step not in step_order:
            errors.append(f"Question step missing from step_order in {question_set.id}: {question.step}")
    for mode, payload in question_set.flow_modes.items():
        for step in payload.get("steps", []):
            if str(step) not in seen_steps:
                errors.append(f"Mode {mode} references unknown step in {question_set.id}: {step}")
    return errors


def merge_questions(*groups: Iterable[QuestionDefinition]) -> tuple[QuestionDefinition, ...]:
    out: List[QuestionDefinition] = []
    for group in groups:
        out.extend(list(group))
    return tuple(out)
